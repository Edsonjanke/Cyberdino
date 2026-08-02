# -*- coding: utf-8 -*-
"""DESBASTE INTERNO — painel conversational com dois modos.

BASICO   : passes longitudinais alargando o furo + acabamento (8 campos).
AVANCADO : desbaste ate o pilot end, faceamento interno e raio de filete
           (os mesmos 8 + RAIO, PROF. FACE e FIM DO PILOTO).

Cada modo tem o SEU desenho (id-turn-bg.png / id-turn-ext-bg.png), entao
trocar o modo troca a imagem e o conjunto de campos. Os valores digitados
ficam nos widgets e sobrevivem a troca.

Retangulos medidos com torno_cam_ui/tools/detecta_caixas.py (id_basic/id_ext).
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit, OverlayToggle, responsive
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine
from .panels import WCS, DIRS, COOL

# opcoes do campo de modo (valor = o que o engine espera)
MODOS = [(u"Basico", "BASIC"), (u"Avancado", "EXTENDED")]

# (chave, retangulo, max_chars, opcoes do campo)
CAMPOS_BASICO = [
    ("toolNumber",    (0.07015, 0.01389, 0.08047, 0.07778), 2, dict(integer=True, minimum=1)),
    ("zStart",        (0.21527, 0.10000, 0.11967, 0.07917), 7, {}),
    ("zEnd",          (0.13067, 0.20139, 0.11967, 0.07917), 7, {}),
    ("finalX",        (0.37620, 0.25278, 0.12105, 0.07917), 7, {}),
    ("initialX",      (0.34182, 0.78056, 0.12105, 0.07778), 7, {}),
    ("idRoughDOC",    (0.81637, 0.04028, 0.12036, 0.07778), 5, dict(minimum=0.001)),
    ("finishDOC",     (0.76272, 0.15417, 0.12105, 0.07639), 5, dict(minimum=0.0)),
    ("toolClearance", (0.71114, 0.26667, 0.12105, 0.07639), 5, dict(minimum=0.0)),
]

CAMPOS_AVANCADO = [
    ("toolNumber",    (0.06944, 0.01806, 0.08125, 0.07778), 2, dict(integer=True, minimum=1)),
    ("zStart",        (0.21736, 0.10278, 0.12153, 0.07778), 7, {}),
    ("zEnd",          (0.13056, 0.20417, 0.12222, 0.07917), 7, {}),
    ("finalX",        (0.38125, 0.25556, 0.12222, 0.07917), 7, {}),
    ("initialX",      (0.34653, 0.78333, 0.12292, 0.07778), 7, {}),
    ("idRoughDOC",    (0.82708, 0.04444, 0.12292, 0.07778), 5, dict(minimum=0.001)),
    ("finishDOC",     (0.77292, 0.15694, 0.12292, 0.07778), 5, dict(minimum=0.0)),
    ("toolClearance", (0.72083, 0.26806, 0.12292, 0.07778), 5, dict(minimum=0.0)),
    # so no avancado
    ("filletRadius",  (0.01875, 0.78333, 0.12292, 0.07778), 5, dict(minimum=0.0)),
    ("pilotEnd",      (0.15556, 0.89306, 0.12292, 0.07778), 7, {}),
    ("faceRoughDOC",  (0.61181, 0.78333, 0.12222, 0.07778), 5, dict(minimum=0.0)),
]

IMAGENS = {
    "BASIC":    ("id-turn-bg.png", 1454.0 / 720.0, CAMPOS_BASICO),
    "EXTENDED": ("id-turn-ext-bg.png", 1440.0 / 720.0, CAMPOS_AVANCADO),
}

TOGGLES = [
    ("useCannedCycle", 72.45, 54.73, u"GERAR CICLO",        "#4caf50"),
    ("finishOnly",     65.55, 57.36, u"SOMENTE ACABAMENTO", "#ffd600"),
]

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class IDForm(QWidget):
    """Mesma interface dos outros forms (changed / collect / load)."""

    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(IDForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._toggles = {}
        self._extra = {}
        self._modo = self.params.get("mode", "BASIC")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        imagem, aspect, _campos = IMAGENS[self._modo]
        self._panel = ImageOverlayPanel(imagem, aspect=aspect)
        root.addWidget(self._panel, 1)

        def label_font(cw):
            return responsive(cw, 11, 0.014, 16)

        # Cria UM campo por chave (a uniao dos dois modos); quem nao aparece no
        # modo atual fica escondido, mas guarda o valor.
        vistos = {}
        for lista in (CAMPOS_BASICO, CAMPOS_AVANCADO):
            for key, _rect, _mc, opts in lista:
                if key in vistos:
                    continue
                e = OverlayEdit(**opts)
                e.committed.connect(self._on_changed)
                self._edits[key] = e
                vistos[key] = True

        for key, top, left, texto, cor in TOGGLES:
            t = OverlayToggle(texto, cor)
            t.toggled.connect(self._on_changed)
            self._toggles[key] = t
            self._panel.add_item(t, top, left, font_fn=label_font)

        # G71 do EvoCAM e invalido no LinuxCNC 2.9 — mesma trava das outras ops.
        canned = self._toggles["useCannedCycle"]
        canned.setEnabled(False)
        canned.setToolTip(u"Ciclo G71 ainda nao validado neste controlador "
                          u"(LinuxCNC 2.9). Use o modo linha a linha.")

        root.addWidget(self._build_strip())
        self._aplicar_modo(self._modo)
        self.load(self.params)

    # ── troca de modo ───────────────────────────────────────────────────
    def _aplicar_modo(self, modo):
        self._modo = modo if modo in IMAGENS else "BASIC"
        imagem, aspect, campos = IMAGENS[self._modo]
        itens = [(self._edits[key], rect, mc) for key, rect, mc, _o in campos]
        self._panel.reconfigurar(imagem, aspect, itens)

    def _on_modo_mudou(self, *_a):
        w = self._extra.get("mode")
        if w is None:
            return
        self._aplicar_modo(w.committed_value())
        self._on_changed()

    # ── faixa com o que nao esta no desenho ─────────────────────────────
    def _build_strip(self):
        box = QFrame()
        box.setStyleSheet('QFrame { background: #242729; border: 1px solid #3A3F43;'
                          ' border-radius: 4px; }')
        grid = QGridLayout(box)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        specs = [
            ("mode",          u"Modo",         "combo", MODOS),
            ("title",         u"Titulo",       "text"),
            ("workOffset",    u"Zero peca",    "combo", WCS),
            ("spindleDir",    u"Fuso",         "combo", DIRS),
            ("coolant",       u"Refrigeracao", "combo", COOL),
            ("roughingSFM",   u"Vc desb",      "num",   dict(decimals=0, suffix="m/min", step=5)),
            ("finishingSFM",  u"Vc acab",      "num",   dict(decimals=0, suffix="m/min", step=5)),
            ("maxSpindleRPM", u"RPM max",      "int",   dict(suffix="rpm", step=50)),
            ("roughingFPR",   u"Av desb",      "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
            ("finishingFPR",  u"Av acab",      "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
        ]
        for i, spec in enumerate(specs):
            key, label, kind = spec[0], spec[1], spec[2]
            col = i % 5
            row = (i // 5) * 2
            lab = QLabel(label)
            lab.setStyleSheet(_LABEL_QSS)
            if kind == "text":
                w = TouchLine()
                w.textChanged.connect(self._on_changed)
            elif kind == "combo":
                w = TouchCombo(spec[3])
                if key == "mode":
                    w.currentIndexChanged.connect(self._on_modo_mudou)
                else:
                    w.currentIndexChanged.connect(self._on_changed)
            elif kind == "int":
                w = TouchIntSpin(**spec[3])
                w.valueChanged.connect(self._on_changed)
            else:
                w = TouchDoubleSpin(**spec[3])
                w.valueChanged.connect(self._on_changed)
            w.setMinimumWidth(70)
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            self._extra[key] = w
            grid.addWidget(lab, row, col)
            grid.addWidget(w, row + 1, col)
            grid.setColumnStretch(col, 1)
        return box

    # ── interface usada pela aba ────────────────────────────────────────
    def _on_changed(self, *_a):
        self.changed.emit()

    def load(self, params):
        self.params = copy.deepcopy(params)
        for key, e in self._edits.items():
            v = self.params.get(key, 0)
            e.blockSignals(True)
            e.set_value(v if v is not None else 0)
            e.blockSignals(False)
        for key, t in self._toggles.items():
            t.blockSignals(True)
            t.setChecked(bool(self.params.get(key, False)))
            t.blockSignals(False)
        for key, w in self._extra.items():
            v = self.params.get(key)
            w.blockSignals(True)
            if isinstance(w, TouchCombo):
                w.set_value(v)
            elif isinstance(w, TouchLine):
                w.set_value(v if v is not None else "")
            else:
                w.setValue(v if v is not None else 0)
            w.blockSignals(False)
        self._aplicar_modo(self.params.get("mode", "BASIC"))

    def collect(self):
        for key, e in self._edits.items():
            self.params[key] = e.commit()
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        for key, t in self._toggles.items():
            self.params[key] = bool(t.isChecked())
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        self.params["operationType"] = "ID_TURN"
        return copy.deepcopy(self.params)
