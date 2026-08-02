# -*- coding: utf-8 -*-
"""FACEAMENTO — painel conversational sobre a imagem de referencia.

Os campos ficam em cima dos retangulos desenhados na propria imagem (o mesmo
face-bg.png do EvoCAM), nas coordenadas percentuais originais do app. Os
parametros que nao aparecem no desenho (zero peca, fuso, refrigeracao,
velocidades e avancos) ficam numa faixa compacta embaixo.
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit, OverlayToggle, responsive
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine
from .panels import WCS, DIRS, COOL


# Retangulos MEDIDOS no proprio face-bg.png (fracao da imagem: x, y, larg, alt).
# Detectados varrendo os tracos brancos do desenho, entao o campo cai exatamente
# dentro da caixa — nada de posicao ajustada no olho.
# (chave, retangulo, maior valor esperado em caracteres, opcoes do campo)
FIELDS = [
    ("toolNumber",    (0.12891, 0.01806, 0.07812, 0.06667), 2, dict(integer=True, minimum=1)),
    ("toolClearance", (0.68164, 0.03819, 0.09297, 0.07083), 5, dict(minimum=0.0)),
    ("zEnd",          (0.30391, 0.09097, 0.09375, 0.07083), 7, {}),
    ("roughingDOC",   (0.68125, 0.13819, 0.09453, 0.07153), 5, dict(minimum=0.001)),
    ("finishDOC",     (0.68125, 0.23681, 0.09453, 0.07222), 5, dict(minimum=0.0)),
    ("initialX",      (0.01055, 0.44444, 0.14844, 0.07014), 7, {}),
    ("finalX",        (0.45078, 0.47708, 0.12852, 0.07153), 7, {}),
    ("zStart",        (0.32773, 0.77222, 0.09844, 0.07014), 7, {}),
]

TOGGLES = [
    ("useCannedCycle", 75.00, 45.00, u"GERAR CICLO",        "#4caf50"),
    ("finishOnly",     82.19, 44.91, u"SOMENTE ACABAMENTO", "#ffd600"),
]

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class FaceForm(QWidget):
    """Mesma interface do OpForm (changed / collect / load), mas com o
    formulario desenhado sobre a imagem."""

    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(FaceForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._toggles = {}
        self._extra = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # ── imagem + campos por cima ────────────────────────────────────
        self._panel = ImageOverlayPanel("face-bg.png")
        root.addWidget(self._panel, 1)

        def input_font(cw):
            return responsive(cw, 14, 0.024, 28)

        def label_font(cw):
            return responsive(cw, 11, 0.014, 16)

        for key, rect, max_chars, opts in FIELDS:
            e = OverlayEdit(**opts)
            e.committed.connect(self._on_changed)
            self._edits[key] = e
            self._panel.add_box_item(e, rect, max_chars=max_chars)

        for key, top, left, text, color in TOGGLES:
            t = OverlayToggle(text, color)
            t.toggled.connect(self._on_changed)
            self._toggles[key] = t
            self._panel.add_item(t, top, left, font_fn=label_font)

        # Ciclo fixo (G71/G72) ainda nao validado neste controlador — o
        # dialeto LinuxCNCDinoPost bloqueia. Fica visivel (igual a imagem)
        # mas desabilitado para nao gerar codigo invalido.
        canned = self._toggles["useCannedCycle"]
        canned.setEnabled(False)
        canned.setToolTip(u"Ciclo fixo ainda nao validado neste controlador "
                          u"(LinuxCNC 2.9). Use o modo linha a linha.")

        # ── faixa de dados que nao estao no desenho ─────────────────────
        root.addWidget(self._build_strip())

        self.load(self.params)

    # ── faixa inferior ──────────────────────────────────────────────────
    def _build_strip(self):
        box = QFrame()
        box.setStyleSheet('QFrame { background: #242729; border: 1px solid #3A3F43;'
                          ' border-radius: 4px; }')
        grid = QGridLayout(box)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)

        specs = [
            ("title",         u"Titulo",        "text"),
            ("workOffset",    u"Zero peca",     "combo", WCS),
            ("spindleDir",    u"Fuso",          "combo", DIRS),
            ("coolant",       u"Refrigeracao",  "combo", COOL),
            ("roughingSFM",   u"Vc desb",       "num",   dict(decimals=0, suffix="m/min", step=5)),
            ("finishingSFM",  u"Vc acab",       "num",   dict(decimals=0, suffix="m/min", step=5)),
            ("maxSpindleRPM", u"RPM max",       "int",   dict(suffix="rpm", step=50)),
            ("roughingFPR",   u"Av desb",       "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
            ("finishingFPR",  u"Av acab",       "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
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
            # Deixa encolher: sem isso a largura minima da faixa empurraria o
            # painel da imagem e apareceria barra de rolagem em telas menores.
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
            self.params[key] = e.commit()      # forca ler o texto digitado
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        for key, t in self._toggles.items():
            self.params[key] = bool(t.isChecked())
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        self.params["operationType"] = "FACE"
        return copy.deepcopy(self.params)
