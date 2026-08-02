# -*- coding: utf-8 -*-
"""DESBASTE EXTERNO — painel conversational sobre a imagem de referencia.

Mesmo esquema do faceamento/furacao: os campos caem em cima dos retangulos
MEDIDOS no proprio od-turn-bg.png (ver torno_cam_ui/tools/detecta_caixas.py).
O que nao aparece no desenho fica na faixa de baixo.
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit, OverlayToggle, responsive
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine
from .panels import WCS, DIRS, COOL, YESNO

# aspect ratio do container no app (ODTurnPanel.tsx: IMG_W/IMG_H)
OD_AR = 1431.0 / 736.0

# (chave, retangulo medido na imagem, maior valor em caracteres, opcoes)
FIELDS = [
    ("toolNumber",    (0.06978, 0.04212, 0.08025, 0.07745), 2, dict(integer=True, minimum=1)),
    ("zEnd",          (0.24285, 0.10326, 0.12003, 0.07609), 7, {}),
    ("initialX",      (0.04815, 0.45788, 0.12073, 0.07745), 7, {}),
    ("finalX",        (0.40684, 0.45788, 0.12073, 0.07745), 7, {}),
    ("filletRadius",  (0.18353, 0.79212, 0.12142, 0.07745), 5, dict(minimum=0.0)),
    ("zStart",        (0.30775, 0.89266, 0.12003, 0.07745), 7, {}),
    ("toolClearance", (0.69225, 0.56114, 0.12003, 0.07609), 5, dict(minimum=0.0)),
    ("finishDOC",     (0.78576, 0.66304, 0.12073, 0.07745), 5, dict(minimum=0.0)),
    ("roughingDOC",   (0.78576, 0.76495, 0.12073, 0.07745), 5, dict(minimum=0.001)),
]

# toggles: posicao em % do container (nao tem retangulo desenhado)
TOGGLES = [
    ("useCannedCycle", 21.70, 44.90, u"GERAR CICLO",        "#4caf50"),
    ("finishOnly",     27.80, 44.90, u"SOMENTE ACABAMENTO", "#ffd600"),
]

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class ODForm(QWidget):
    """Mesma interface do OpForm/FaceForm (changed / collect / load)."""

    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(ODForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._toggles = {}
        self._extra = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._panel = ImageOverlayPanel("od-turn-bg.png", aspect=OD_AR)
        root.addWidget(self._panel, 1)

        def label_font(cw):
            return responsive(cw, 11, 0.014, 16)

        for key, rect, max_chars, opts in FIELDS:
            e = OverlayEdit(**opts)
            e.committed.connect(self._on_changed)
            self._edits[key] = e
            self._panel.add_box_item(e, rect, max_chars=max_chars)

        for key, top, left, texto, cor in TOGGLES:
            t = OverlayToggle(texto, cor)
            t.toggled.connect(self._on_changed)
            self._toggles[key] = t
            self._panel.add_item(t, top, left, font_fn=label_font)

        # G71 do EvoCAM e invalido no LinuxCNC 2.9 (palavras I/R/F que nao
        # existem, sub O100 depois da chamada e sempre com o mesmo numero).
        # Fica visivel, igual ao desenho, mas desabilitado ate ser corrigido.
        canned = self._toggles["useCannedCycle"]
        canned.setEnabled(False)
        canned.setToolTip(u"Ciclo G71 ainda nao validado neste controlador "
                          u"(LinuxCNC 2.9). Use o modo linha a linha.")

        root.addWidget(self._build_strip())
        self.load(self.params)

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
            ("title",              u"Titulo",       "text"),
            ("workOffset",         u"Zero peca",    "combo", WCS),
            ("spindleDir",         u"Fuso",         "combo", DIRS),
            ("coolant",            u"Refrigeracao", "combo", COOL),
            ("useConstantSurface", u"CSS (G96)",    "combo", YESNO),
            ("roughingSFM",        u"Vc desb",      "num",   dict(decimals=0, suffix="m/min", step=5)),
            ("finishingSFM",       u"Vc acab",      "num",   dict(decimals=0, suffix="m/min", step=5)),
            ("maxSpindleRPM",      u"RPM max",      "int",   dict(suffix="rpm", step=50)),
            ("roughingFPR",        u"Av desb",      "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
            ("finishingFPR",       u"Av acab",      "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
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
        self._panel.relayout()

    def collect(self):
        for key, e in self._edits.items():
            self.params[key] = e.commit()
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        for key, t in self._toggles.items():
            self.params[key] = bool(t.isChecked())
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        self.params["operationType"] = "OD_TURN"
        return copy.deepcopy(self.params)
