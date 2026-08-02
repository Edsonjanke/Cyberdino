# -*- coding: utf-8 -*-
"""CHANFRO / RAIO — painel conversational com 4 variantes.

modo (CHANFRO/RAIO) x lado (EXTERNO/INTERNO) = 4 desenhos diferentes, cada um
com o seu conjunto de campos. Trocar modo ou lado troca a imagem e os campos;
os valores digitados ficam nos widgets e sobrevivem a troca.

Retangulos medidos com torno_cam_ui/tools/detecta_caixas.py
(cham_od / cham_id / rad_od / rad_id).
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine
from .panels import WCS, DIRS, COOL

MODOS = [(u"Chanfro", "CHAMFER"), (u"Raio", "RADIUS")]
LADOS = [(u"Externo", "OD"), (u"Interno", "ID")]

# opcoes por campo (o dicionario de cada chave vale em todas as variantes)
OPC = {
    "toolNumber":    dict(integer=True, minimum=1),
    "chamferAngle":  dict(minimum=1.0),
    "roughingDOC":   dict(minimum=0.001),
    "finishDOC":     dict(minimum=0.0),
    "toolClearance": dict(minimum=0.0),
}
MAXC = {"toolNumber": 2, "chamferAngle": 3, "roughingDOC": 5,
        "finishDOC": 5, "toolClearance": 5, "x": 7, "zStart": 7, "zEnd": 7}

# variante -> (imagem, aspect do container, {campo: retangulo medido})
VARIANTES = {
    "CHAMFER_OD": ("chamfer-od-bg.png", 1456.0 / 735.0, {
        "toolNumber":    (0.14492, 0.02585, 0.04739, 0.07891),
        "zEnd":          (0.18407, 0.11973, 0.12157, 0.07891),
        "zStart":        (0.31593, 0.11973, 0.12157, 0.07891),
        "finishDOC":     (0.85027, 0.17823, 0.12225, 0.07891),
        "roughingDOC":   (0.57005, 0.25034, 0.12157, 0.07755),
        "chamferAngle":  (0.38736, 0.37551, 0.10852, 0.07891),
        "x":             (0.04739, 0.46122, 0.12157, 0.08027),
        "toolClearance": (0.57005, 0.48435, 0.12157, 0.07891),
    }),
    "CHAMFER_ID": ("chamfer-id-bg.png", 1445.0 / 720.0, {
        "toolNumber":    (0.14385, 0.00972, 0.06570, 0.08056),
        "zEnd":          (0.18811, 0.10694, 0.12102, 0.07917),
        "zStart":        (0.31950, 0.10694, 0.12172, 0.07917),
        "roughingDOC":   (0.66598, 0.14444, 0.12172, 0.08056),
        "toolClearance": (0.61480, 0.24306, 0.12172, 0.08056),
        "x":             (0.05048, 0.27222, 0.12172, 0.08056),
        "finishDOC":     (0.84094, 0.50694, 0.12172, 0.08056),
        "chamferAngle":  (0.38174, 0.56111, 0.10858, 0.08056),
    }),
    "RADIUS_OD": ("radius-od-bg.png", 1442.0 / 720.0, {
        "toolNumber":    (0.07346, 0.01528, 0.08108, 0.07917),
        "zEnd":          (0.18850, 0.11250, 0.12128, 0.07778),
        "zStart":        (0.32017, 0.11250, 0.12197, 0.07778),
        "finishDOC":     (0.85586, 0.16944, 0.12128, 0.07917),
        "roughingDOC":   (0.57519, 0.24306, 0.12128, 0.07778),
        "x":             (0.05128, 0.45556, 0.12197, 0.07917),
        "toolClearance": (0.57519, 0.47778, 0.12128, 0.07917),
    }),
    "RADIUS_ID": ("radius-id-bg.png", 1438.0 / 720.0, {
        "toolNumber":    (0.07371, 0.02222, 0.07928, 0.07639),
        "zEnd":          (0.18776, 0.11667, 0.11961, 0.07639),
        "zStart":        (0.31711, 0.11667, 0.11961, 0.07639),
        "finishDOC":     (0.66759, 0.17361, 0.11961, 0.07639),
        "roughingDOC":   (0.85814, 0.17361, 0.11961, 0.07639),
        "toolClearance": (0.69332, 0.31250, 0.11961, 0.07778),
        "x":             (0.05216, 0.45417, 0.11961, 0.07778),
        "chamferAngle":  (0.40542, 0.45417, 0.12031, 0.07778),
    }),
}

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class ChamferForm(QWidget):
    """Mesma interface dos outros forms (changed / collect / load)."""

    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(ChamferForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._extra = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        variante = self._variante()
        imagem, aspect, _r = VARIANTES[variante]
        self._panel = ImageOverlayPanel(imagem, aspect=aspect)
        root.addWidget(self._panel, 1)

        # um campo por chave (uniao das 4 variantes)
        chaves = set()
        for _img, _asp, rects in VARIANTES.values():
            chaves.update(rects)
        for key in sorted(chaves):
            e = OverlayEdit(**OPC.get(key, {}))
            e.committed.connect(self._on_changed)
            self._edits[key] = e

        root.addWidget(self._build_strip())
        self._aplicar_variante()
        self.load(self.params)

    # ── variante (modo x lado) ──────────────────────────────────────────
    def _variante(self):
        modo = self.params.get("mode", "CHAMFER")
        lado = self.params.get("side", "OD")
        chave = "{}_{}".format(modo, lado)
        return chave if chave in VARIANTES else "CHAMFER_OD"

    def _aplicar_variante(self):
        imagem, aspect, rects = VARIANTES[self._variante()]
        itens = [(self._edits[k], r, MAXC.get(k, 7)) for k, r in rects.items()]
        self._panel.reconfigurar(imagem, aspect, itens)

    def _on_variante_mudou(self, *_a):
        for chave in ("mode", "side"):
            w = self._extra.get(chave)
            if w is not None:
                self.params[chave] = w.committed_value()
        self._aplicar_variante()
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
            ("side",          u"Lado",         "combo", LADOS),
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
            col = i % 6
            row = (i // 6) * 2
            lab = QLabel(label)
            lab.setStyleSheet(_LABEL_QSS)
            if kind == "text":
                w = TouchLine()
                w.textChanged.connect(self._on_changed)
            elif kind == "combo":
                w = TouchCombo(spec[3])
                if key in ("mode", "side"):
                    w.currentIndexChanged.connect(self._on_variante_mudou)
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
        self._aplicar_variante()

    def collect(self):
        for key, e in self._edits.items():
            self.params[key] = e.commit()
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        self.params["operationType"] = "CHAMFER"
        # Arco do modo RAIO com geometria exata (senao o LinuxCNC recusa:
        # "Radius to end of arc differs from radius to start").
        self.params["fixArcOvercut"] = True
        # o engine usa chamferLength so como rotulo; mantem coerente com o Z
        self.params["chamferLength"] = abs(self.params.get("zEnd", 0)
                                           - self.params.get("zStart", 0))
        return copy.deepcopy(self.params)
