import os
import re
import bisect
import atexit

import hal as _hal
import linuxcnc

from qtpy import uic
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QWidget, QPushButton, QApplication, QLabel

from qtpyvcp.plugins import getPlugin
from qtpyvcp.widgets.input_widgets.gcode_text_edit import GcodeTextEdit
from qtpyvcp.widgets.display_widgets.vtk_backplot.vtk_backplot import VTKBackPlot


# setPlainText cria um novo QTextDocument cada vez que um NGC e carregado,
# o que descarta a defaultFont do documento. Reaplicar a fonte do widget
# (definida em probe_basic_custom.ui) para o texto do G-code respeita-la.
_original_gcode_setPlainText = GcodeTextEdit.setPlainText


def _patched_gcode_setPlainText(self, p_str):
    _original_gcode_setPlainText(self, p_str)
    self.document().setDefaultFont(self.font())


GcodeTextEdit.setPlainText = _patched_gcode_setPlainText


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


def _wire_touch_off_wear_clear():
    # Apos touch_off_x/z, zera o desgaste correspondente da ferramenta atual
    # (comportamento Fanuc: touch redefine o offset total e o wear daquele eixo
    # volta a zero).
    from qtpy.QtWidgets import QAbstractButton
    tool_tbl = None
    btn_x = None
    btn_z = None
    for top in QApplication.topLevelWidgets():
        if tool_tbl is None:
            tool_tbl = top.findChild(QWidget, "tooltable")
        if btn_x is None:
            btn_x = top.findChild(QAbstractButton, "touch_off_x")
        if btn_z is None:
            btn_z = top.findChild(QAbstractButton, "touch_off_z")
        if tool_tbl is not None and btn_x is not None and btn_z is not None:
            break
    if tool_tbl is None:
        return
    slot = getattr(tool_tbl, "clearWearAxisCurrentTool", None)
    if slot is None:
        return
    if btn_x is not None:
        btn_x.clicked.connect(lambda _=False: slot('x'))
    if btn_z is not None:
        btn_z.clicked.connect(lambda _=False: slot('z'))


def _wire_gcode_top_buttons():
    """Conecta os botoes 'RUN FROM LINE' e 'SAVE' do topo aos metodos do editor de G-code,
    e habilita edicao do editor (setReadOnly(False))."""
    for top in QApplication.topLevelWidgets():
        run_btn = top.findChild(QPushButton, "run_from_here_top_btn")
        save_btn = top.findChild(QPushButton, "save_gcode_top_btn")
        editor = top.findChild(GcodeTextEdit, "gcodetextedit_2") \
            or top.findChild(GcodeTextEdit, "gcodetextedit")
        if editor is None:
            continue

        editor.setReadOnly(False)
        editor.readonly = False

        if run_btn is not None:
            try:
                run_btn.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            run_btn.clicked.connect(editor.runFromHere)

        if save_btn is not None:
            try:
                save_btn.clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            save_btn.clicked.connect(lambda _=False, ed=editor: ed.saveFile())

        return


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


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)
        # Wirear depois do event loop comecar (main window ja estara montada)
        QTimer.singleShot(0, _wire_gcode_top_buttons)
        QTimer.singleShot(0, _wire_auto_clear_backplot)
        QTimer.singleShot(0, _wire_speed_readouts)
        QTimer.singleShot(0, _start_spindle_controller)
        QTimer.singleShot(0, _wire_touch_off_wear_clear)
