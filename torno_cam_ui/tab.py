# -*- coding: utf-8 -*-
"""Aba GERAR PGM — gerador conversational de torno (port do EvoCAM).

Constroi o formulario por operacao, mostra o G-code ao vivo e grava/carrega
o .ngc no LinuxCNC. O engine (torno_cam) e Python puro; esta aba so faz a UI
e a integracao com o qtpyvcp/LinuxCNC.
"""

import os
import sys
from types import SimpleNamespace

# Garante torno_cam importavel (raiz do config no sys.path)
_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_ROOT = os.path.dirname(_HERE)   # torno_cam_ui -> raiz do config
if _CONFIG_ROOT not in sys.path:
    sys.path.insert(0, _CONFIG_ROOT)

from qtpy.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QStackedWidget, QButtonGroup, QPlainTextEdit, QScrollArea,
    QSizePolicy, QFrame, QApplication,
)
from qtpy.QtCore import Qt, QTimer

from torno_cam.engine.defaults import default_params
from torno_cam.engine.strategies import build_nodes, EngineError
from torno_cam.engine.program import ProgramConfig, entry_from_nodes, assemble_program
from torno_cam.engine.post.linuxcnc_dino import LinuxCNCDinoPost

from .panels import OpForm, FACE_FIELDS, OD_FIELDS, DRILL_FIELDS, THREAD_FIELDS
from .face_panel import FaceForm
from .drill_panel import DrillForm
from .od_panel import ODForm
from .id_panel import IDForm
from .chamfer_panel import ChamferForm
from .groove_panel import GrooveForm
from .thread_panel import ThreadForm
from . import state

try:
    from qtpyvcp.actions import program_actions
except Exception:
    program_actions = None


# (rotulo da aba, chave default, campos, chave do estado)
OPS = [
    (u"FACEAR", "FACE", FACE_FIELDS),
    (u"DESBASTE EXT", "OD_TURN", OD_FIELDS),
    (u"DESBASTE INT", "ID_TURN", None),
    (u"FURAR", "DRILL", DRILL_FIELDS),
    (u"CHANFRO/RAIO", "CHAMFER", None),
    (u"CANAL/CORTE", "GROOVE", None),
    (u"ROSCA", "THREAD_EXTERNAL", None),
]

_OP_BTN_QSS = """
QPushButton {
    background: #2E3234; color: #E6E6E6; border: 1px solid #3A3F43;
    border-radius: 4px; padding: 8px; font: 14pt "Bebas Kai"; min-height: 44px;
}
QPushButton:checked { background: #00838F; color: white; }
"""

_ACT_QSS = """
QPushButton {
    background: #2E3234; color: #E6E6E6; border: 1px solid #3A3F43;
    border-radius: 4px; padding: 8px; font: 14pt "Bebas Kai"; min-height: 46px;
}
QPushButton:pressed { background: #3E4448; }
"""

_PRIMARY_QSS = """
QPushButton {
    background: #157A30; color: white; border: 1px solid #0c5c22;
    border-radius: 4px; padding: 8px; font: 15pt "Bebas Kai"; min-height: 52px;
}
QPushButton:pressed { background: #157a30; }
"""

_HEAD_QSS = 'QLabel { color: #26C6DA; font: 15pt "Bebas Kai"; }'
_HINT_QSS = 'QLabel { color: #FFB300; font: 10pt "Bebas Kai"; }'
# Mesmas cores do editor de G-code da pagina principal (regra GcodeTextEdit
# do probe_basic_custom.qss: fundo preto, texto branco).
_PREVIEW_QSS = ('QPlainTextEdit { background:#000000; color:#FFFFFF;'
                ' border:1px solid #3A3F43; border-radius:4px;'
                ' font-family:"DejaVu Sans Mono", monospace; font-size:11pt; }')


# Widgets do ProbeBasic escondidos enquanto esta aba esta na frente, para o
# desenho ocupar a tela toda (mais facil de acertar os campos no touch):
# os 5 QFrames da faixa inferior (todos de altura fixa 340px, por isso e tudo
# ou nada) + o painel lateral direito (JOG / ZERO PECA / DRO / EDITAR e o
# "STATUS DA MAQUINA", 253px de largura fixa).
_CHROME = (
    "main_control_qframe_2",      # CYCLE START, PARAR, user buttons, LIGAR, E-STOP
    "main_dro_qframe_3",          # T, DESG X/Z, C graus
    "main_dro_qframe_2",          # DRO grande G54 WORK
    "jog_and_spindle_qframe",     # G96/G97, avanco, sentido do fuso
    "main_override_tool_qframe",  # sliders de override
    "side_bar",                   # painel lateral inteiro
)


class UserTab(QWidget):
    def __init__(self, parent=None):
        super(UserTab, self).__init__(parent)
        self.setObjectName("GERAR_PGM")     # vira a aba "GERAR PGM"
        self._chrome_cache = None
        self._tabw_cache = None
        self._tabw_max_h = None             # teto original (restaurado ao sair)
        self.setStyleSheet("QWidget { background: #242729; }")

        self._queue = []          # lista de (label, params_dict)
        self._preview_mode = "current"   # 'current' | 'queue'
        self._forms = []

        self._saved = state.load_state()

        self._build_ui()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._regenerate)

        self._select_op(0)
        self._regenerate()

    # ── Construcao da UI ─────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Coluna 1: seletor de operacao
        col1 = QVBoxLayout()
        col1.setSpacing(6)
        lab = QLabel(u"OPERACAO")
        lab.setStyleSheet(_HEAD_QSS)
        col1.addWidget(lab)
        self._op_group = QButtonGroup(self)
        self._op_group.setExclusive(True)
        for i, (name, _key, _fields) in enumerate(OPS):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(_OP_BTN_QSS)
            btn.clicked.connect(lambda _c=False, idx=i: self._select_op(idx))
            self._op_group.addButton(btn, i)
            col1.addWidget(btn)
        col1.addStretch(1)
        c1 = QWidget()
        c1.setLayout(col1)
        c1.setFixedWidth(190)
        root.addWidget(c1)

        # Coluna 2: uma pagina por operacao.
        # O scroll fica em CADA formulario simples, nunca em volta do stack:
        # do contrario a largura minima dos formularios largos (grade de 2
        # colunas) forcaria barra de rolagem tambem no painel da imagem,
        # cortando o desenho.
        self._stack = QStackedWidget()
        for (name, key, fields) in OPS:
            saved = self._saved.get("params", {}).get(key)
            base = saved if saved else default_params(key)
            # FACE ja usa o painel conversational sobre a imagem de referencia;
            # as demais operacoes seguem no formulario simples ate serem
            # convertidas (uma de cada vez, apos validar).
            if key == "FACE":
                form = FaceForm(base)
                page = form
            elif key == "DRILL":
                form = DrillForm(base)
                page = form
            elif key == "OD_TURN":
                form = ODForm(base)
                page = form
            elif key == "ID_TURN":
                form = IDForm(base)
                page = form
            elif key == "CHAMFER":
                form = ChamferForm(base)
                page = form
            elif key == "GROOVE":
                form = GrooveForm(base)
                page = form
            elif key == "THREAD_EXTERNAL":
                form = ThreadForm(base)
                page = form
            else:
                form = OpForm(fields, base)
                page = QScrollArea()
                page.setWidgetResizable(True)
                page.setWidget(form)
                page.setFrameShape(QFrame.NoFrame)
            form.changed.connect(self._on_form_changed)
            self._forms.append(form)
            self._stack.addWidget(page)
        root.addWidget(self._stack, 1)

        # Coluna 3: fila + preview + acoes
        col3 = QVBoxLayout()
        col3.setSpacing(6)
        h = QLabel(u"PROGRAMA")
        h.setStyleSheet(_HEAD_QSS)
        col3.addWidget(h)

        self._queue_list = QListWidget()
        self._queue_list.setStyleSheet(
            'QListWidget { background:#1E2224; color:#E6E6E6;'
            ' border:1px solid #3A3F43; border-radius:4px; font: 12pt "Bebas Kai"; }')
        # Some quando a fila esta vazia (caso normal: uma operacao so) para o
        # G-code ocupar o espaco; reaparece do tamanho do conteudo ao ADICIONAR.
        self._queue_list.setVisible(False)
        col3.addWidget(self._queue_list)

        # Preview em QPlainTextEdit (previsivel): o editor real de programa
        # (aba ARQUIVO) mostra o .ngc so depois do SALVAR+CARREGAR.
        self._preview = QPlainTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(_PREVIEW_QSS)
        col3.addWidget(self._preview, 1)

        self._status = QLabel(u"")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(_HINT_QSS)
        col3.addWidget(self._status)

        # botoes de acao
        row1 = QHBoxLayout()
        for text, slot in ((u"GERAR", self._on_gerar),
                           (u"ADICIONAR", self._on_adicionar),
                           (u"REMOVER", self._on_remover),
                           (u"LIMPAR", self._on_limpar)):
            b = QPushButton(text)
            b.setStyleSheet(_ACT_QSS)
            b.clicked.connect(slot)
            row1.addWidget(b)
        col3.addLayout(row1)

        save = QPushButton(u"SALVAR + CARREGAR")
        save.setStyleSheet(_PRIMARY_QSS)
        save.clicked.connect(self._on_salvar_carregar)
        col3.addWidget(save)

        c3 = QWidget()
        c3.setLayout(col3)
        c3.setFixedWidth(470)
        root.addWidget(c3)

    # ── Modo imersivo (tela cheia desta aba) ─────────────────────────────────
    # O QTabWidget usa um QStackedWidget por dentro, que mostra/esconde a
    # pagina ao trocar de aba — entao showEvent/hideEvent chegam certos, sem
    # depender do indice nem do texto da aba.
    def showEvent(self, event):
        super(UserTab, self).showEvent(event)
        self._set_imersivo(True)
        # Registra os tamanhos reais um instante depois do layout assentar.
        QTimer.singleShot(300, self._diagnostico)

    def _diagnostico(self):
        try:
            f = self._current_form()
            if hasattr(f, "_panel"):
                f._panel.diagnostico()
        except Exception:
            pass

    def hideEvent(self, event):
        super(UserTab, self).hideEvent(event)
        self._set_imersivo(False)

    def _find_widget(self, name):
        """Lookup robusto: findChild na janela e, se falhar, varredura em
        allWidgets (mesmo padrao usado no customs.py — findChild sozinho ja
        falhou antes para widgets carregados a parte)."""
        win = self.window()
        if win is not None:
            w = win.findChild(QWidget, name)
            if w is not None:
                return w
        app = QApplication.instance()
        if app is not None:
            for w in app.allWidgets():
                try:
                    if w.objectName() == name:
                        return w
                except RuntimeError:
                    continue        # widget C++ ja destruido
        return None

    def _chrome(self):
        if self._chrome_cache is None:
            found = [self._find_widget(n) for n in _CHROME]
            found = [w for w in found if w is not None]
            # so guarda no cache quando a janela ja esta montada; fora do
            # ProbeBasic (teste headless) a lista fica vazia e nada acontece.
            if found:
                self._chrome_cache = found
            return found
        return self._chrome_cache

    def _tab_widget(self):
        if self._tabw_cache is None:
            self._tabw_cache = self._find_widget("tabWidget")
        return self._tabw_cache

    def _set_imersivo(self, ligado):
        """Esconde/restaura a faixa inferior e o painel lateral.

        Protegido: se o layout do ProbeBasic mudar e algum widget sumir, a aba
        continua funcionando normalmente (so nao entra em tela cheia)."""
        try:
            for w in self._chrome():
                w.setVisible(not ligado)

            # Sem levantar este teto (680px no .ui) o espaco liberado fica
            # vazio e a imagem nao cresce.
            tw = self._tab_widget()
            if tw is not None:
                if self._tabw_max_h is None:
                    self._tabw_max_h = tw.maximumHeight()
                tw.setMaximumHeight(16777215 if ligado else self._tabw_max_h)
        except Exception:
            pass

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _current_form(self):
        return self._forms[self._stack.currentIndex()]

    def _select_op(self, idx):
        self._stack.setCurrentIndex(idx)
        btn = self._op_group.button(idx)
        if btn is not None:
            btn.setChecked(True)
        self._preview_mode = "current"
        self._regenerate()

    def _on_form_changed(self):
        if self._preview_mode == "current":
            self._debounce.start()
        self._persist()

    def _set_preview_text(self, text):
        try:
            self._preview.setPlainText(text)
        except Exception:
            pass

    def _post(self):
        return LinuxCNCDinoPost()

    def _program_config(self, title):
        return ProgramConfig(title=title, unitSystem="metric", feedMode="REV")

    def _build_entry(self, label, params):
        nodes = build_nodes(SimpleNamespace(**params))
        return entry_from_nodes(label, nodes)

    def _regenerate(self):
        try:
            if self._preview_mode == "queue" and self._queue:
                title = self._queue[0][1].get("title", "PROGRAMA")
                entries = [self._build_entry(lbl, prm) for (lbl, prm) in self._queue]
                gcode = assemble_program(self._program_config(title), entries, self._post())
                self._status.setText(u"Fila: {} operacao(oes)".format(len(self._queue)))
            else:
                params = self._current_form().collect()
                entries = [self._build_entry(params.get("title", "OP"), params)]
                gcode = assemble_program(self._program_config(params.get("title", "PROGRAMA")),
                                         entries, self._post())
                self._status.setText(u"")
            self._set_preview_text(gcode)
        except EngineError as e:
            self._status.setText(u"Erro: {}".format(e))
        except Exception as e:
            self._status.setText(u"Erro ao gerar: {}".format(e))

    # ── Acoes ────────────────────────────────────────────────────────────────
    def _on_gerar(self):
        self._preview_mode = "current"
        self._regenerate()

    def _on_adicionar(self):
        try:
            params = self._current_form().collect()
        except Exception as e:
            self._status.setText(u"Erro nos campos: {}".format(e))
            return
        name = OPS[self._stack.currentIndex()][0]
        label = params.get("title") or name
        self._queue.append((label, params))
        self._refresh_queue_list()
        self._preview_mode = "queue"
        self._persist()
        self._regenerate()

    def _on_remover(self):
        row = self._queue_list.currentRow()
        if row < 0 or row >= len(self._queue):
            return
        del self._queue[row]
        self._refresh_queue_list()
        self._preview_mode = "queue" if self._queue else "current"
        self._persist()
        self._regenerate()

    def _on_limpar(self):
        self._queue = []
        self._refresh_queue_list()
        self._preview_mode = "current"
        self._persist()
        self._regenerate()

    def _refresh_queue_list(self):
        self._queue_list.clear()
        for i, (label, _p) in enumerate(self._queue):
            self._queue_list.addItem(QListWidgetItem(u"{}. {}".format(i + 1, label)))
        self._update_queue_visibility()

    def _update_queue_visibility(self):
        """Fila vazia = escondida (o G-code fica com todo o espaco). Visivel,
        cresce com o conteudo ate 5 linhas."""
        n = len(self._queue)
        self._queue_list.setVisible(n > 0)
        if n:
            linha = self._queue_list.sizeHintForRow(0) if n else 24
            if linha <= 0:
                linha = 24
            self._queue_list.setFixedHeight(min(n, 5) * linha + 8)

    def _on_salvar_carregar(self):
        try:
            if self._queue:
                title = self._queue[0][1].get("title", "PROGRAMA")
                entries = [self._build_entry(lbl, prm) for (lbl, prm) in self._queue]
            else:
                params = self._current_form().collect()
                title = params.get("title", "PROGRAMA")
                entries = [self._build_entry(title, params)]
            gcode = assemble_program(self._program_config(title), entries, self._post())
        except Exception as e:
            self._status.setText(u"Erro ao gerar: {}".format(e))
            return

        directory = state.program_prefix()
        try:
            if not os.path.isdir(directory):
                os.makedirs(directory)
            path = state.unique_path(directory, state.sanitize_filename(title))
            with open(path, "w", encoding="utf-8") as f:
                f.write(gcode + "\n")
        except Exception as e:
            self._status.setText(u"Erro ao gravar: {}".format(e))
            return

        loaded = False
        if program_actions is not None:
            try:
                program_actions.load(path)
                loaded = True
            except Exception as e:
                self._status.setText(u"Gravado, mas falhou ao carregar: {}".format(e))
        self._set_preview_text(gcode)
        base = os.path.basename(path)
        self._status.setText(
            u"Carregado: {}".format(base) if loaded else u"Gravado: {}".format(base))

    # ── Persistencia ─────────────────────────────────────────────────────────
    def _persist(self):
        try:
            params_by_key = {}
            for (name, key, _fields), form in zip(OPS, self._forms):
                params_by_key[key] = form.collect()
            state.save_state({
                "params": params_by_key,
                "queue": [{"label": lbl, "params": prm} for (lbl, prm) in self._queue],
            })
        except Exception:
            pass
