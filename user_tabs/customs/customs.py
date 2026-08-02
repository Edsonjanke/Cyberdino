import os
import re
import json
import bisect
import atexit

import hal as _hal
import linuxcnc

from qtpy import uic
from qtpy.QtCore import QTimer, QEvent, QSettings, QObject
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import QWidget, QPushButton, QApplication, QLabel

from qtpyvcp.plugins import getPlugin
from qtpyvcp.actions import program_actions
from qtpyvcp.utilities.logger import getLogger
from qtpyvcp.widgets.input_widgets.gcode_text_edit import GcodeTextEdit
from qtpyvcp.widgets.display_widgets.vtk_backplot.vtk_backplot import VTKBackPlot

LOG = getLogger(__name__)


# setPlainText cria um novo QTextDocument cada vez que um NGC e carregado,
# o que descarta a defaultFont do documento. Reaplicar a fonte do widget
# (definida em probe_basic_custom.ui) para o texto do G-code respeita-la.
_original_gcode_setPlainText = GcodeTextEdit.setPlainText


def _patched_gcode_setPlainText(self, p_str):
    _original_gcode_setPlainText(self, p_str)
    self.document().setDefaultFont(self.font())


GcodeTextEdit.setPlainText = _patched_gcode_setPlainText


# Forcar MAIUSCULAS ao digitar/editar G-code. O interpretador aceita minusculas,
# mas o padrao de oficina e maiuscula (X, Z, G, M...). Interceptamos o texto do
# QKeyEvent e, se tiver letra minuscula, repassamos um evento equivalente com o
# texto ja em uppercase. Setas, backspace, atalhos (Ctrl+C/V), Enter etc. passam
# intactos porque so mexemos quando event.text() tem conteudo alfabetico.
_original_gcode_keyPressEvent = GcodeTextEdit.keyPressEvent


def _patched_gcode_keyPressEvent(self, event):
    txt = event.text()
    if txt and txt != txt.upper():
        event = QKeyEvent(
            QEvent.KeyPress, event.key(), event.modifiers(), txt.upper())
    _original_gcode_keyPressEvent(self, event)


GcodeTextEdit.keyPressEvent = _patched_gcode_keyPressEvent


# Find/Replace tambem deve inserir em MAIUSCULA. O replaceText/replaceAllText
# do qtpyvcp fazem cursor.insertText(replace) direto no documento, escapando do
# patch de keyPressEvent. Envolvemos os dois pra forcar o replace em uppercase.
_original_replaceText = GcodeTextEdit.replaceText
_original_replaceAllText = GcodeTextEdit.replaceAllText


def _patched_replaceText(self, search, replace):
    _original_replaceText(self, search, (replace or "").upper())


def _patched_replaceAllText(self, search, replace):
    _original_replaceAllText(self, search, (replace or "").upper())


GcodeTextEdit.replaceText = _patched_replaceText
GcodeTextEdit.replaceAllText = _patched_replaceAllText


# O teclado virtual aparece ABAIXO do campo focado. Como o FindReplaceDialog
# abre centralizado (400x200), o teclado cobre os botoes Find/Replace/Close.
# Reposicionamos o dialog no TOPO da tela ao abrir, deixando a metade de baixo
# livre pro teclado.
_original_findDialog = GcodeTextEdit.findDialog


def _patched_findDialog(self, *args, **kwargs):
    _original_findDialog(self, *args, **kwargs)
    try:
        dlg = self.dialog
        screen = QApplication.primaryScreen().availableGeometry()
        # centraliza horizontalmente, cola no topo (com uma folga)
        x = screen.x() + (screen.width() - dlg.width()) // 2
        y = screen.y() + 20
        dlg.move(x, y)
        dlg.raise_()
    except Exception:
        pass


GcodeTextEdit.findDialog = _patched_findDialog


# =============================================================================
# HAL component 'dino_spindle' - salva RPM atual no PARA e religa na RPM salva
# =============================================================================
# Necessario para G96 (CSS): nesse modo o S e velocidade de superficie, nao RPM.
# halui.spindle.0.forward usa S literal como RPM, errado em G96. Aqui salvamos
# a RPM real (spindle.0.speed-out, calculada pelo interp pra X atual) e religamos
# via linuxcnc.command.spindle(dir, rpm) que envia EMC_SPINDLE_ON direto sem
# precisar trocar modo (funciona em AUTO paused).
#
# Pins criados em escopo de modulo pra existir antes do postgui_fix.hal:
#   save        (bit IN)  - pulsa no PARA SPINDLE: snapshot RPM atual
#   restore-cw  (bit IN)  - pulsa no LIGA M3: spindle fwd na RPM salva
#   restore-ccw (bit IN)  - pulsa no LIGA M4: spindle rev na RPM salva
#   speed-in    (float IN)- wire em spindle.0.speed-out (RPM atual comandada)
#   css-d       (float IN)- wire em motion.analog-out-05 (D do G96, setado por o<g96>)
_hal_spindle = None
_hal_pin_save = None
_hal_pin_restore_cw = None
_hal_pin_restore_ccw = None
_hal_pin_speed_in = None
_hal_pin_css_d = None

try:
    _hal_spindle = _hal.component('dino_spindle')
    _hal_pin_save = _hal_spindle.newpin('save', _hal.HAL_BIT, _hal.HAL_IN)
    _hal_pin_restore_cw = _hal_spindle.newpin('restore-cw', _hal.HAL_BIT, _hal.HAL_IN)
    _hal_pin_restore_ccw = _hal_spindle.newpin('restore-ccw', _hal.HAL_BIT, _hal.HAL_IN)
    _hal_pin_speed_in = _hal_spindle.newpin('speed-in', _hal.HAL_FLOAT, _hal.HAL_IN)
    _hal_pin_css_d = _hal_spindle.newpin('css-d', _hal.HAL_FLOAT, _hal.HAL_IN)
    _hal_spindle.ready()
    atexit.register(lambda: _hal_spindle.exit() if _hal_spindle else None)
except _hal.error as e:
    # Reload em dev: componente ja existe. Nao quebrar.
    print("[customs.py] HAL component dino_spindle: {}".format(e))


class SpindleSaveRestore:
    """Poll 50ms detecta rising edge nos pins save/restore-cw/restore-ccw.
       Sempre rastreia ultima RPM nao-zero (entao funciona mesmo se snapshot
       acontecer ja com spindle parando). cmd.spindle envia comando direto sem
       trocar modo - funciona em AUTO paused."""

    def __init__(self):
        self._last_nonzero = 0.0
        self._saved = 0.0
        self._prev_save = False
        self._prev_cw = False
        self._prev_ccw = False
        self._cmd = linuxcnc.command()
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll)
        self._timer.start(50)

    def _poll(self):
        if _hal_pin_save is None:
            return
        try:
            cur_speed = abs(float(_hal_pin_speed_in.value))
            save = bool(_hal_pin_save.value)
            cw = bool(_hal_pin_restore_cw.value)
            ccw = bool(_hal_pin_restore_ccw.value)
        except Exception:
            return

        if cur_speed > 0.1:
            self._last_nonzero = cur_speed

        if save and not self._prev_save:
            self._saved = self._last_nonzero

        if cw and not self._prev_cw and self._saved > 0:
            try:
                self._cmd.spindle(linuxcnc.SPINDLE_FORWARD, self._saved)
            except Exception as e:
                print("[dino_spindle] cmd.spindle FWD {} falhou: {}".format(self._saved, e))

        if ccw and not self._prev_ccw and self._saved > 0:
            try:
                self._cmd.spindle(linuxcnc.SPINDLE_REVERSE, self._saved)
            except Exception as e:
                print("[dino_spindle] cmd.spindle REV {} falhou: {}".format(self._saved, e))

        self._prev_save = save
        self._prev_cw = cw
        self._prev_ccw = ccw


_spindle_controller = None


def _start_spindle_controller():
    global _spindle_controller
    if _spindle_controller is None:
        _spindle_controller = SpindleSaveRestore()


def _find_tooltable():
    """Acha o widget WearToolTable de forma robusta.

    findChild(QWidget, "tooltable") a partir de topLevelWidgets falhava em
    runtime (aviso 'Nao achei a tabela'); allWidgets() enumera TODO widget
    vivo independente da arvore de janelas, e casamos por objectName OU
    isinstance da classe real (mesma instancia de modulo: o .ui promove via
    header dino_widgets.wear_tool_table -> mesmo sys.modules)."""
    try:
        from dino_widgets.wear_tool_table import WearToolTable
    except Exception:
        WearToolTable = None
    for w in QApplication.allWidgets():
        try:
            if w.objectName() == "tooltable" or \
               (WearToolTable is not None and isinstance(w, WearToolTable)):
                if hasattr(w, "clearWearAxisCurrentTool"):
                    return w
        except RuntimeError:
            continue  # widget C++ ja destruido
    return None


def _wire_touch_off_wear_clear():
    # Apos touch_off_x/z, zera o desgaste correspondente da ferramenta atual
    # (comportamento Fanuc: touch redefine o offset total e o wear daquele eixo
    # volta a zero).
    from qtpy.QtWidgets import QAbstractButton
    btn_x = None
    btn_z = None
    for top in QApplication.topLevelWidgets():
        if btn_x is None:
            btn_x = top.findChild(QAbstractButton, "touch_off_x")
        if btn_z is None:
            btn_z = top.findChild(QAbstractButton, "touch_off_z")
        if btn_x is not None and btn_z is not None:
            break

    def _clear(axis):
        tbl = _find_tooltable()
        slot = getattr(tbl, "clearWearAxisCurrentTool", None) if tbl else None
        if slot is not None:
            slot(axis)

    if btn_x is not None:
        btn_x.clicked.connect(lambda _=False: _clear('x'))
    if btn_z is not None:
        btn_z.clicked.connect(lambda _=False: _clear('z'))


def _find_offsettable():
    """Acha o widget WearOffsetTable (tabela ZERO PECA) — mesmo esquema
    robusto do _find_tooltable (allWidgets + objectName OU isinstance)."""
    try:
        from dino_widgets.wear_offset_table import WearOffsetTable
    except Exception:
        WearOffsetTable = None
    for w in QApplication.allWidgets():
        try:
            if w.objectName() == "offset_table" or \
               (WearOffsetTable is not None and isinstance(w, WearOffsetTable)):
                if hasattr(w, "clearWearAxisActive"):
                    return w
        except RuntimeError:
            continue  # widget C++ ja destruido
    return None


def _wire_offset_zero_wear_clear():
    """ZERO X / ZERO Z / ZERO ALL tambem zeram o WEAR daquele eixo do
    zero-peca ATIVO (igual o touch-off zera o wear da ferramenta): o botao
    reescreve o offset total via G10 L20, entao um desgaste residual viraria
    'geometria fantasma' na tabela ZERO PECA (geom = total - wear).

    Em vez de amarrar em objectNames, varre TODOS os MDIButtons cujo comando
    zera eixo via G10 L20 (contem X0/Z0 literal) — pega o painel do offset
    DRO (zero_x/z_button_offset), o DRO principal (zero_x/z/all_button) e
    qualquer botao futuro com o mesmo padrao."""
    from qtpy.QtWidgets import QAbstractButton

    def _clear(axes):
        tbl = _find_offsettable()
        if tbl is None:
            LOG.warning("Zero-peca: tabela de offsets nao achada p/ zerar wear")
            return
        for ax in axes:
            try:
                tbl.clearWearAxisActive(ax)
            except Exception as e:
                LOG.warning("Zero-peca: falha zerando wear %s: %s", ax, e)

    wired = 0
    for w in QApplication.allWidgets():
        try:
            if not isinstance(w, QAbstractButton):
                continue
            cmd = w.property('MDICommand')
        except RuntimeError:
            continue
        if not cmd:
            continue
        cmd = str(cmd).upper()
        if 'G10 L20' not in cmd:
            continue
        axes = tuple(ax for ax, tag in (('x', 'X0'), ('z', 'Z0')) if tag in cmd)
        if not axes:
            continue
        w.clicked.connect(lambda _=False, a=axes: _clear(a))
        wired += 1
    LOG.info("Zero-peca: %d botoes ZERO ligados ao auto-zero do wear", wired)


def _run_from_line_armed(editor, set_line_n=None):
    """RUN FROM LINE: arma o programa na linha PAUSADO.

    Fonte da linha:
      - se o SET LINE N estiver aceso e tiver uma linha salva -> usa a salva;
      - senao -> usa a linha do cursor no editor.

    Em vez de rodar direto, posiciona o interp na linha e pausa. So usina quando
    o operador apertar Cycle Start/Resume. So atua se o programa estiver IDLE
    (nao reinicia no meio de um corte em andamento)."""
    STATUS = getPlugin('status')
    try:
        interp = STATUS.interp_state.value
    except Exception:
        interp = None
    if interp != linuxcnc.INTERP_IDLE:
        return

    line = None
    if set_line_n is not None:
        line = set_line_n.active_line()   # None se botao apagado / sem linha salva
    if line is None:
        line = editor.getCurrentLine()

    program_actions.run(line)     # AUTO_RUN a partir da linha (seta modo AUTO internamente)
    program_actions.pause()       # AUTO_PAUSE imediato -> arma pausado, antes de qualquer movimento

    # Backstop: reassere o pause apos o task controller transicionar pra RUNNING,
    # cobrindo a corrida AUTO_RUN/AUTO_PAUSE (pausar ja-pausado e no-op).
    def _ensure_paused():
        try:
            if STATUS.interp_state.value != linuxcnc.INTERP_PAUSED:
                program_actions.pause()
        except Exception:
            pass
    QTimer.singleShot(120, _ensure_paused)

    # Aviso na tela (plugin notifications vem habilitado no ProbeBasic).
    # Some sozinho quando o operador aperta CYCLE START (interp sai de PAUSED).
    try:
        notif = getPlugin('notifications')
        notif.captureMessage(
            'info',
            u"Programa armado na linha {}. Aperte CYCLE START para iniciar.".format(line))
        _dismiss_armed_notice_on_resume(notif)
    except Exception:
        pass


def _dismiss_armed_notice_on_resume(notif):
    """Fecha o aviso de 'programa armado' assim que o programa sai do PAUSED
    (operador apertou CYCLE START/Resume). Captura o widget recem-criado e o
    remove via o mesmo caminho do botao X (NativeNotification.onClicked)."""
    disp = getattr(notif, 'notification_dispatcher', None)
    msgs = getattr(disp, 'activeMessages', None) if disp is not None else None
    if not msgs:
        return
    widget = msgs[-1]  # a notificacao que acabamos de inserir

    STATUS = getPlugin('status')
    state = {'done': False}
    # Conecta direto no sinal (qtpyvcp DataChannel.notify nao tem 'remove');
    # guardamos o signal pra desconectar depois.
    signal = STATUS.interp_state.signal

    def _close(*_a, **_k):
        if state['done']:
            return
        state['done'] = True
        try:
            signal.disconnect(_on_interp)
        except (TypeError, RuntimeError):
            pass
        # Fecha do mesmo jeito que o botao X faria, se ainda estiver na tela.
        try:
            if widget in disp.activeMessages:
                disp.mainLayout.removeWidget(widget)
                disp.activeMessages.remove(widget)
                widget.deleteLater()
                disp.nMessages -= 1
                if disp.nMessages <= 0:
                    disp.hide()
        except Exception:
            pass

    def _on_interp(*_a, **_k):
        # PAUSED -> qualquer outro estado = resume/stop: dispensa o aviso.
        try:
            if STATUS.interp_state.value != linuxcnc.INTERP_PAUSED:
                _close()
        except Exception:
            _close()

    signal.connect(_on_interp)
    # Backstop: se nada acontecer, o aviso some em 60s pra nao ficar preso.
    QTimer.singleShot(60000, _close)


class _SetLineN:
    """Gerencia o botao 'SET LINE N' (checkable) do editor.

    - Aceso: memoriza a linha do cursor no momento do clique e o RUN FROM LINE
      passa a usar essa linha fixa (ignora o cursor). O botao mostra 'LINE N XX'.
    - Apagado: RUN FROM LINE volta a usar o cursor. Texto volta a 'SET LINE N'.
    - Persiste por PROGRAMA: a linha e salva em QSettings chaveada pelo caminho do
      NGC carregado (STATUS.file), entao cada arquivo lembra a propria linha entre
      sessoes. Ao trocar de arquivo, recarrega o estado salvo daquele arquivo.
    """

    def __init__(self, btn, editor):
        self._btn = btn
        self._editor = editor
        self._settings = QSettings("DinoEvo", "RunFromLineN")
        self._cur_file = None
        btn.setCheckable(True)
        btn.toggled.connect(self._on_toggled)
        STATUS = getPlugin('status')
        STATUS.file.notify(self._on_file_change)
        self._on_file_change(STATUS.file.value)

    def _key(self, path):
        # chave por arquivo; '' se nenhum arquivo carregado
        return "line/{}".format(path or "")

    def _on_file_change(self, path, *_a, **_k):
        self._cur_file = path
        saved = self._settings.value(self._key(path), None)
        try:
            saved = int(saved) if saved is not None else None
        except (TypeError, ValueError):
            saved = None
        # Ajusta o botao ao estado salvo do arquivo, sem disparar save de volta.
        self._btn.blockSignals(True)
        self._btn.setChecked(saved is not None)
        self._btn.blockSignals(False)
        self._refresh_text(saved)

    def _on_toggled(self, checked):
        if checked:
            line = self._editor.getCurrentLine()
            self._settings.setValue(self._key(self._cur_file), int(line))
            self._settings.sync()
            self._refresh_text(line)
        else:
            self._settings.remove(self._key(self._cur_file))
            self._settings.sync()
            self._refresh_text(None)

    def _refresh_text(self, line):
        if line is not None:
            self._btn.setText("LINHA N {}".format(line))
        else:
            self._btn.setText("DEF. LINHA N")

    def active_line(self):
        """Linha salva se o botao estiver aceso; senao None (usa cursor)."""
        if not self._btn.isChecked():
            return None
        saved = self._settings.value(self._key(self._cur_file), None)
        try:
            return int(saved) if saved is not None else None
        except (TypeError, ValueError):
            return None


def _find_button(name):
    """Acha um botao por objectName de forma robusta (allWidgets), igual
    _find_tooltable. findChild a partir de topLevelWidgets e fragil pra botoes
    que vivem em sub-widgets carregados a parte (ex.: user_buttons via
    uic.loadUi) — o mesmo motivo do bug da tooltable (commit e45d73f)."""
    for w in QApplication.allWidgets():
        try:
            if isinstance(w, QPushButton) and w.objectName() == name:
                return w
        except RuntimeError:
            continue  # widget C++ ja destruido
    return None


def _wire_gcode_top_buttons():
    """Conecta os botoes 'RUN FROM LINE' e 'SET LINE N' aos metodos do editor
    de G-code. O editor comeca READ-ONLY: so fica editavel no modo EDIT
    (ver _wire_edit_mode). SAVE/FIND/COPY/PASTE agora moram na aba EDIT.

    SET LINE N e RUN FROM LINE (de baixo) moram nos user_buttons (widget
    carregado por uic.loadUi), entao sao achados por _find_button/allWidgets,
    nao por findChild (que falha pra sub-widgets — ver tooltable, e45d73f)."""
    editor = None
    for top in QApplication.topLevelWidgets():
        editor = top.findChild(GcodeTextEdit, "gcodetextedit_2") \
            or top.findChild(GcodeTextEdit, "gcodetextedit")
        if editor is not None:
            break
    if editor is None:
        return

    # Comeca travado; o modo EDIT destrava (evita edicao acidental).
    editor.EditorReadOnly(True)

    run_btn = _find_button("run_from_here_top_btn")
    set_n_btn = _find_button("set_line_n_top_btn")
    # Botao 'RUN FROM LINE' do painel inferior (era o MIST). Mesma logica.
    run_btn_bottom = _find_button("run_from_line_bottom_btn")

    set_line_n = None
    if set_n_btn is not None:
        set_line_n = _SetLineN(set_n_btn, editor)
        # guarda a ref no widget pra nao ser coletada pelo GC
        set_n_btn._dino_set_line_n = set_line_n

    for rb in (run_btn, run_btn_bottom):
        if rb is not None:
            try:
                rb.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            rb.clicked.connect(
                lambda _=False, ed=editor, sln=set_line_n: _run_from_line_armed(ed, sln))


class _EditShortcutBlocker(QObject):
    """Event filter: enquanto o editor estiver EDITAVEL (modo EDIT), impede que
    atalhos globais do LinuxCNC (jog por teclado, F-keys de spindle/coolant,
    home, etc.) disparem enquanto se digita o G-code.

    Mecanismo canonico do Qt: quando uma tecla casa com um shortcut, o Qt manda
    um evento ShortcutOverride ao widget focado ANTES de acionar o atalho. Se
    aceitarmos esse evento, a tecla e entregue como digitacao normal ao editor
    em vez de acionar o atalho -> nenhum eixo se move / nada liga por engano.

    Fora do modo EDIT o editor e read-only, entao o filtro fica inerte."""

    def __init__(self, editor):
        super(_EditShortcutBlocker, self).__init__(editor)
        self._editor = editor

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.ShortcutOverride and not self._editor.isReadOnly():
                # Aceita -> Qt entrega como KeyPress normal ao editor,
                # nao dispara o shortcut global.
                event.accept()
                return True
        except Exception:
            pass
        return False


def _wire_edit_mode():
    """Modo EDIT (aba do painel direito): destrava o editor SO quando a aba EDIT
    esta selecionada; senao mantem read-only. Tambem bloqueia atalhos de teclado
    enquanto edita (seguranca: nao mover eixos / ligar spindle sem querer).
    Wira os botoes da aba EDIT (FIND/REPL, SAVE, COPIAR, COLAR)."""
    editor = edit_tab = None
    find_b = save_b = copy_b = paste_b = None
    for top in QApplication.topLevelWidgets():
        editor = editor or top.findChild(GcodeTextEdit, "gcodetextedit_2") \
            or top.findChild(GcodeTextEdit, "gcodetextedit")
        edit_tab = edit_tab or top.findChild(QPushButton, "edit_tab")
        find_b = find_b or top.findChild(QPushButton, "edit_find_btn")
        save_b = save_b or top.findChild(QPushButton, "edit_save_btn")
        copy_b = copy_b or top.findChild(QPushButton, "edit_copy_btn")
        paste_b = paste_b or top.findChild(QPushButton, "edit_paste_btn")
    if editor is None:
        return

    # Bloqueador de atalhos: instala um event filter no editor. So atua quando
    # o editor esta editavel (modo EDIT). Guarda ref pra nao ser coletado.
    blocker = _EditShortcutBlocker(editor)
    editor.installEventFilter(blocker)
    editor._dino_shortcut_blocker = blocker

    # Gate: aba EDIT aceso -> destrava; apagado -> trava.
    if edit_tab is not None:
        def _on_edit_toggled(checked, ed=editor):
            ed.EditorReadOnly(not checked)
        edit_tab.toggled.connect(_on_edit_toggled)
        # estado inicial coerente (aba comeca desmarcada -> read-only)
        editor.EditorReadOnly(not edit_tab.isChecked())

    # Botoes da aba EDIT
    if find_b is not None:
        find_b.clicked.connect(lambda _=False, ed=editor: ed.findDialog())
    if save_b is not None:
        save_b.clicked.connect(lambda _=False, ed=editor: ed.saveFile())
    if copy_b is not None:
        copy_b.clicked.connect(lambda _=False, ed=editor: ed.copy())
    if paste_b is not None:
        paste_b.clicked.connect(lambda _=False, ed=editor: ed.paste())


def _wire_auto_clear_backplot():
    """Auto-limpa o rastro (clearLivePlot) do VTKBackPlot em:
       - carga de novo NGC (STATUS.file)
       - inicio de execucao (interp IDLE -> READING/WAITING)
       - fim de execucao (interp READING/WAITING -> IDLE)"""
    backplot = None
    for top in QApplication.topLevelWidgets():
        backplot = top.findChild(VTKBackPlot, "vtkbackplot")
        if backplot is not None:
            break
    if backplot is None:
        return

    # Logo EVO (completa, mono branco) como marca d'agua no canto inferior
    # direito do backplot.
    # vtkLogoRepresentation SEM widget precisa de SetRenderer() +
    # BuildRepresentation() explicitos (sem isso a geometria nao e construida
    # e nada aparece). Adiada 3s pro render window GL ja estar inicializado.
    def _add_backplot_logo(bp=backplot):
        try:
            import vtk
            # Simbolo MONO BRANCO: sobre o fundo escuro do backplot a versao
            # colorida some (62% da arte tem contraste 1.22 contra o fundo; o
            # cobre fica em 2.24, abaixo do minimo 3.0). O branco da 13.19.
            logo_path = os.path.join(
                os.environ.get('CONFIG_DIR') or os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'logo', 'evo-horizontal-branco.png')
            if not os.path.exists(logo_path):
                print("[customs.py] logo nao encontrada: %s" % logo_path)
                return
            reader = vtk.vtkPNGReader()
            reader.SetFileName(logo_path)
            reader.Update()
            logo_rep = vtk.vtkLogoRepresentation()
            logo_rep.SetImage(reader.GetOutput())
            logo_rep.SetRenderer(bp.renderer)     # <- essencial sem widget
            # A logo completa e' larga (829x256 = 3.24:1). Sem
            # ProportionalResizeOn ela sairia esmagada dentro de um quadrado.
            logo_rep.ProportionalResizeOn()
            logo_rep.SetPosition(0.72, 0.02)      # canto inferior direito
            logo_rep.SetPosition2(0.25, 0.13)     # 25% da largura, altura pela proporcao
            # 0.35 era calibrado para o splash colorido; com o simbolo BRANCO
            # puro ficava quase invisivel. 0.50 aparece sem competir com as
            # linhas do percurso.
            logo_rep.GetImageProperty().SetOpacity(0.50)
            logo_rep.BuildRepresentation()        # <- constroi a geometria
            bp.renderer.AddViewProp(logo_rep)
            # ref pra nao ser coletado + refresh
            bp._dino_logo = (reader, logo_rep)
            try:
                bp.renderer.GetRenderWindow().Render()
            except Exception:
                pass
        except Exception as e:
            print("[customs.py] logo no backplot falhou: {}".format(e))
    # ATIVA desde 2026-08-02, com a arte oficial (logo/evo-simbolo-branco.png).
    # Para desligar, troque True -> False.
    _LOGO_BACKPLOT_ATIVA = True
    if _LOGO_BACKPLOT_ATIVA:
        QTimer.singleShot(3000, _add_backplot_logo)

    # PAN sempre ativo: o botao mouse do backplot faz pan por padrao (sem
    # precisar apertar PAN toda vez). Deixa o pan_button 'checked' pra refletir.
    try:
        backplot.enable_panning(True)
        for top in QApplication.topLevelWidgets():
            pan_btn = top.findChild(QPushButton, "pan_button")
            if pan_btn is not None:
                pan_btn.setChecked(True)
                break
    except Exception:
        pass

    # Auto-enquadrar nos PROGRAM EXTENTS toda vez que um programa e carregado
    # (equivale a apertar PGM EXT automaticamente). Slot nativo do VTKBackPlot.
    try:
        backplot.setProgramViewWhenLoadingProgram(True)
    except Exception:
        pass

    STATUS = getPlugin('status')

    STATUS.file.notify(lambda *_a, **_k: backplot.clearLivePlot())

    state = {'prev': None}

    def on_interp(new_state, *_a, **_k):
        prev = state['prev']
        state['prev'] = new_state
        if prev is None or prev == new_state:
            return
        if prev == linuxcnc.INTERP_IDLE or new_state == linuxcnc.INTERP_IDLE:
            backplot.clearLivePlot()

    STATUS.interp_state.notify(on_interp)


_G96_D_RE = re.compile(r'G96\b[^;(\n]*?\bD\s*([0-9.]+)', re.IGNORECASE)
_g96_d_lines = []   # paralelos, sorted by line: [(line_num, d_value)]


def _parse_file_for_g96_d(filepath):
    """Varre o NGC carregado e indexa toda linha que tem 'G96 ... D<num>'.
    Usado pra mostrar MAX RPM mesmo quando o programa usa G96 cru (sem o<g96>)."""
    global _g96_d_lines
    _g96_d_lines = []
    if not filepath or not os.path.exists(filepath):
        return
    try:
        with open(filepath, 'r') as f:
            for i, line in enumerate(f, start=1):
                # ignora comentarios (; e parenteses)
                code = line.split(';', 1)[0]
                code = re.sub(r'\([^)]*\)', '', code)
                m = _G96_D_RE.search(code)
                if m:
                    try:
                        _g96_d_lines.append((i, float(m.group(1))))
                    except ValueError:
                        pass
    except Exception as e:
        print("[customs.py] parse G96 D em {} falhou: {}".format(filepath, e))


def _d_from_file(motion_line):
    """Retorna o ultimo D programado em ou antes de motion_line. 0 se nenhum."""
    if not _g96_d_lines or not motion_line:
        return 0.0
    keys = [x[0] for x in _g96_d_lines]
    idx = bisect.bisect_right(keys, motion_line) - 1
    if idx >= 0:
        return _g96_d_lines[idx][1]
    return 0.0


def _wire_speed_readouts():
    """Atualiza os QLabels do painel CUSTOMS (feed_per_unit, feed_unit_per_rev,
    rpm_s_word, css_max_rpm) com o feed/S programados em tempo real."""
    labels = {}
    for top in QApplication.topLevelWidgets():
        for name in ("feed_per_unit", "feed_unit_per_rev",
                     "rpm_s_word", "css_max_rpm"):
            if name in labels:
                continue
            w = top.findChild(QLabel, name)
            if w is not None:
                labels[name] = w
        if len(labels) == 4:
            break
    if not labels:
        return

    STATUS = getPlugin('status')

    def on_file_change(filepath, *_a, **_k):
        _parse_file_for_g96_d(filepath)

    def refresh(*_a, **_k):
        gcodes = STATUS.gcodes.value or ()
        in_g95 = "G95" in gcodes
        in_g96 = "G96" in gcodes
        settings = STATUS.settings.value or (0, 0.0, 0.0)
        feed = settings[1] if len(settings) > 1 else 0.0
        sword = settings[2] if len(settings) > 2 else 0.0
        if "feed_per_unit" in labels:
            labels["feed_per_unit"].setText("---" if in_g95 else "{:.1f}".format(feed))
        if "feed_unit_per_rev" in labels:
            labels["feed_unit_per_rev"].setText("{:.4f}".format(feed) if in_g95 else "---")
        if "rpm_s_word" in labels:
            labels["rpm_s_word"].setText("{:.0f}".format(sword))
        if "css_max_rpm" in labels:
            # Em G97 (RPM fixo) nao ha clamp CSS -> "---".
            # Em G96: prefere D parseado do arquivo (na linha em execucao);
            # fallback pro HAL pin (D setado por o<g96> via M68).
            if in_g96:
                d_file = _d_from_file(STATUS.motion_line.value)
                d_hal = float(_hal_pin_css_d.value or 0.0) if _hal_pin_css_d is not None else 0.0
                d_val = d_file if d_file > 0 else d_hal
                labels["css_max_rpm"].setText("{:.0f}".format(d_val) if d_val > 0 else "---")
            else:
                labels["css_max_rpm"].setText("---")

    STATUS.settings.notify(refresh)
    STATUS.gcodes.notify(refresh)
    STATUS.motion_line.notify(refresh)
    STATUS.file.notify(on_file_change)

    # Parse o arquivo ja carregado (se houver) e dispara refresh inicial.
    current_file = STATUS.file.value
    if current_file:
        _parse_file_for_g96_d(current_file)

    # Poll do HAL pin css-d (motion.analog-out-05 nao gera notify do qtpyvcp).
    css_d_timer = QTimer()
    css_d_timer.timeout.connect(refresh)
    css_d_timer.start(500)
    _wire_speed_readouts._css_d_timer = css_d_timer

    refresh()


def _wire_cycle_start_pulse():
    """Faz o CYCLE START PULSAR (verde claro/escuro) enquanto o programa roda.

    O QSS define SafeCycleStart:disabled[pulse="on"/"off"]; aqui um timer de
    600ms alterna a property 'pulse' (com unpolish/polish pra reavaliar o
    estilo). Roda = interp ocupado E nao pausado. Parado/pausado -> sem pulso."""
    btn = None
    for top in QApplication.topLevelWidgets():
        btn = top.findChild(QPushButton, "cycle_start_button")
        if btn is not None:
            break
    if btn is None:
        return

    STATUS = getPlugin('status')
    state = {'on': False}

    def _set_pulse(value):
        btn.setProperty('pulse', value)
        st = btn.style()
        st.unpolish(btn)
        st.polish(btn)

    def _tick():
        state['on'] = not state['on']
        _set_pulse('on' if state['on'] else 'off')

    timer = QTimer()
    timer.timeout.connect(_tick)

    def _update(*_a, **_k):
        try:
            running = (STATUS.interp_state.value != linuxcnc.INTERP_IDLE
                       and not bool(STATUS.paused.value))
        except Exception:
            running = False
        if running and not timer.isActive():
            timer.start(600)
        elif not running and timer.isActive():
            timer.stop()
            _set_pulse('')   # volta ao estilo base

    STATUS.interp_state.notify(_update)
    STATUS.paused.notify(_update)
    _wire_cycle_start_pulse._timer = timer
    _update()


class _WearAdjustDialog(object):
    """Dialogo NAO-modal pra somar ajuste de desgaste (atalho DESG X/Z).

    Precisa ser nao-modal: QInputDialog e modal de aplicacao e BLOQUEIA os
    cliques no teclado virtual (que e outra janela top-level). Nao-modal +
    posicionado no topo = teclado abre embaixo e funciona (mesmo padrao do
    FindReplaceDialog). Spinbox com locale C: o teclado virtual envia '.' e
    o locale pt_BR rejeitaria (mesma correcao do delegate da tabela)."""

    def __init__(self, parent):
        from qtpy.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                    QDoubleSpinBox, QPushButton, QLabel)
        from qtpy.QtCore import Qt, QLocale
        self._cb = None
        self._axis = None
        d = QDialog(parent)
        d.setWindowTitle(u"Ajuste de desgaste")
        d.setWindowFlags(d.windowFlags() | Qt.WindowStaysOnTopHint)
        d.setModal(False)                       # <- essencial pro teclado virtual
        d.setMinimumWidth(420)
        lay = QVBoxLayout(d)
        self._label = QLabel(d)
        self._label.setWordWrap(True)
        lay.addWidget(self._label)
        self._spin = QDoubleSpinBox(d)
        self._spin.setDecimals(4)
        self._spin.setRange(-10.0, 10.0)
        self._spin.setValue(0.0)
        self._spin.setLocale(QLocale(QLocale.C))  # aceita '.' do teclado virtual
        self._spin.setMinimumHeight(48)
        self._spin.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._spin)
        row = QHBoxLayout()
        cancel = QPushButton(u"CANCELAR", d)
        ok = QPushButton(u"APLICAR", d)
        for b in (cancel, ok):
            b.setMinimumHeight(48)
            b.setFocusPolicy(Qt.NoFocus)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        cancel.clicked.connect(d.hide)
        ok.clicked.connect(self._apply)
        # Enter (fisico ou do teclado virtual) = APLICAR direto.
        self._spin.lineEdit().returnPressed.connect(self._apply)
        self._dlg = d

    def _apply(self):
        # Commita o texto digitado ANTES de ler: os botoes tem NoFocus, entao
        # clicar neles nao gera focus-out e o QDoubleSpinBox ainda nao teria
        # interpretado o texto (value() devolveria o valor antigo/0.0).
        self._spin.interpretText()
        val = float(self._spin.value())
        self._dlg.hide()
        if self._cb is not None and abs(val) > 1e-9:
            self._cb(self._axis, val)

    def open_for(self, axis, tnum, callback):
        from qtpy.QtWidgets import QApplication
        self._axis = axis
        self._cb = callback
        unidade = u" (em DIAMETRO)" if axis == 'x' else u""
        self._label.setText(
            u"T{} - valor a SOMAR ao desgaste {}{}.\nNegativo subtrai.".format(
                tnum, axis.upper(), unidade))
        self._spin.setValue(0.0)
        # topo-centro da tela: teclado virtual abre embaixo sem cobrir
        d = self._dlg
        d.show()
        try:
            screen = QApplication.primaryScreen().availableGeometry()
            d.move(screen.x() + (screen.width() - d.width()) // 2,
                   screen.y() + 20)
            d.raise_()
        except Exception:
            pass
        self._spin.setFocus()      # foco -> teclado numerico virtual aparece
        self._spin.selectAll()


def _wire_tool_wear_info():
    """Botoes 'DESG X n' / 'DESG Z n' (embaixo do campo T): mostram o desgaste
    da ferramenta ATIVA e, ao clicar, abrem um dialogo pra SOMAR um ajuste ao
    desgaste (atalho, sem ir na aba FERRAMENTAS). Mesma semantica incremental
    da tabela: X digitado em DIAMETRO (convertido pra raio no model); Z direto.
    Leitura do tool_wear.json (wear em RAIO; X exibido x2 em G7)."""
    btn_x = btn_z = None
    for top in QApplication.topLevelWidgets():
        btn_x = btn_x or top.findChild(QPushButton, "desg_x_btn")
        btn_z = btn_z or top.findChild(QPushButton, "desg_z_btn")
    if btn_x is None and btn_z is None:
        return

    wear_path = os.path.join(os.environ.get('CONFIG_DIR') or '.', 'tool_wear.json')
    STATUS = getPlugin('status')

    def _load_wear():
        try:
            with open(wear_path, 'r') as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return {}

    def _cur_tool():
        try:
            return int(STATUS.tool_in_spindle.value or 0)
        except Exception:
            return 0

    def refresh(*_a, **_k):
        tnum = _cur_tool()
        w = _load_wear().get(str(tnum), {}) if tnum else {}
        xr = float(w.get('x', 0.0))
        zr = float(w.get('z', 0.0))
        # X em diametro (x2) exceto se estiver em modo raio (G8).
        gcodes = STATUS.gcodes.value or ()
        xw = xr if "G8" in gcodes else xr * 2.0
        if btn_x is not None:
            btn_x.setText("DESG X {:.4f}".format(xw))
        if btn_z is not None:
            btn_z.setText("DESG Z {:.4f}".format(zr))

    # Dialogo unico, reutilizado (nao-modal -> teclado virtual funciona).
    dialog = _WearAdjustDialog(btn_x or btn_z)

    def _apply_adjust(axis, val):
        # Lookup no momento do clique via _find_tooltable (allWidgets +
        # isinstance) - o findChild por topLevelWidgets falhava em runtime.
        tbl = _find_tooltable()
        adjust = getattr(tbl, "adjustWearAxisCurrentTool", None) if tbl else None
        if adjust is None:
            try:
                getPlugin('notifications').captureMessage(
                    'warn', u"Nao achei a tabela de ferramentas - ajuste nao aplicado.")
            except Exception:
                pass
            return
        ok = adjust(axis, float(val))
        if ok is False:
            try:
                getPlugin('notifications').captureMessage(
                    'warn', u"Ajuste de desgaste nao aplicado (ferramenta invalida?).")
            except Exception:
                pass
        refresh()

    def _adjust(axis):
        tnum = _cur_tool()
        if tnum <= 0:
            try:
                getPlugin('notifications').captureMessage(
                    'warn', u"Nenhuma ferramenta ativa - carregue uma ferramenta (M6) antes.")
            except Exception:
                pass
            return
        dialog.open_for(axis, tnum, _apply_adjust)

    if btn_x is not None:
        btn_x.clicked.connect(lambda _=False: _adjust('x'))
    if btn_z is not None:
        btn_z.clicked.connect(lambda _=False: _adjust('z'))

    STATUS.tool_in_spindle.notify(refresh)
    STATUS.gcodes.notify(refresh)
    # Re-le o JSON periodicamente (auto-save altera o arquivo; sem sinal Qt).
    timer = QTimer()
    timer.timeout.connect(refresh)
    timer.start(1000)
    _wire_tool_wear_info._timer = timer
    refresh()


def _hide_probe_tab():
    """Oculta a aba APALPADOR (probing_tab) da barra de abas principal.

    Usa removeTab, NAO delete: a pagina e todos os widgets de probe continuam
    vivos (so saem da barra), entao as referencias do probe_basic.py
    (self.probe_tab_widget, self.probe_help_widget, etc.) seguem validas e o
    boot nao quebra. Acha o QTabWidget que contem a pagina 'probing_tab' via
    allWidgets (robusto). Reversivel: basta nao agendar a chamada.
    (setTabVisible exigiria Qt>=5.15; removeTab funciona em qualquer versao.)"""
    from qtpy.QtWidgets import QTabWidget
    for tw in QApplication.allWidgets():
        try:
            if not isinstance(tw, QTabWidget):
                continue
            for i in range(tw.count()):
                page = tw.widget(i)
                if page is not None and page.objectName() == "probing_tab":
                    tw.removeTab(i)
                    LOG.info("Aba APALPADOR (probing_tab) ocultada via removeTab")
                    return
        except RuntimeError:
            continue  # widget C++ ja destruido


def _wire_jog_continuous():
    """Adiciona um botao CONT no topo da pilha de incrementos de jog.

    O JogIncrementWidget so mostra incrementos discretos (pula o 0), entao o
    jog fica preso em passo — o modo contínuo e o setting
    'machine.jog.mode-incremental' = False, que nenhum botao ativava.

    CONT (checkable, autoExclusive com os botoes de incremento por serem
    filhos do mesmo widget) ativa contínuo; clicar em qualquer incremento
    volta pra passo. Os botoes de jog X/Z ja existentes passam a mover
    contínuo enquanto segurados."""
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QAbstractButton
    from qtpyvcp.utilities.settings import setSetting

    try:
        from qtpyvcp.widgets.input_widgets.jog_increment import JogIncrementWidget
    except Exception:
        JogIncrementWidget = None

    jw = None
    for w in QApplication.allWidgets():
        try:
            if w.objectName() == "jogincrement" or \
               (JogIncrementWidget is not None and isinstance(w, JogIncrementWidget)):
                jw = w
                break
        except RuntimeError:
            continue
    if jw is None:
        LOG.warning("Jog continuo: JogIncrementWidget nao encontrado")
        return
    if jw.findChild(QAbstractButton, "jog_cont_btn") is not None:
        return  # ja adicionado (evita duplicar em reload)

    lay = jw.layout()
    if lay is None:
        LOG.warning("Jog continuo: layout do JogIncrementWidget ausente")
        return

    try:
        from qtpyvcp.widgets.button_widgets.led_button import LEDButton
        cont = LEDButton(jw)
    except Exception:
        cont = QPushButton(jw)     # fallback: botao comum
    cont.setObjectName("jog_cont_btn")
    cont.setText(u"CONT")
    cont.setCheckable(True)
    cont.setAutoExclusive(True)    # mutuamente exclusivo com os incrementos
    cont.setFocusPolicy(Qt.NoFocus)
    cont.setMinimumSize(50, 42)
    cont.setStyleSheet('QPushButton { font: 15pt "Bebas Kai"; }')
    lay.insertWidget(0, cont)
    try:
        jw.placeLed()              # estiliza o LED do CONT igual aos demais
    except Exception:
        pass

    cont.clicked.connect(
        lambda _=False: setSetting("machine.jog.mode-incremental", False))
    for pair in getattr(jw, "_buttons_by_value", []):
        try:
            pair[0].clicked.connect(
                lambda _=False: setSetting("machine.jog.mode-incremental", True))
        except Exception:
            pass
    LOG.info("Jog continuo: botao CONT adicionado")


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)
        # Wirear depois do event loop comecar (main window ja estara montada)
        QTimer.singleShot(0, _wire_gcode_top_buttons)
        QTimer.singleShot(0, _wire_edit_mode)
        QTimer.singleShot(0, _wire_auto_clear_backplot)
        QTimer.singleShot(0, _wire_speed_readouts)
        QTimer.singleShot(0, _start_spindle_controller)
        QTimer.singleShot(0, _wire_touch_off_wear_clear)
        QTimer.singleShot(0, _wire_offset_zero_wear_clear)
        QTimer.singleShot(0, _wire_tool_wear_info)
        QTimer.singleShot(0, _wire_cycle_start_pulse)
        QTimer.singleShot(0, _hide_probe_tab)
        QTimer.singleShot(0, _wire_jog_continuous)
