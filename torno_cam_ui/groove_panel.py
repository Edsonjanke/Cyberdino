# -*- coding: utf-8 -*-
"""CANAL / CORTE — painel conversational com dois modos.

CANAL: mergulhos alternando o sentido + acabamento em duas metades.
CORTE: sangria com bicadas e retorno, com quebra de aresta opcional.

Cada modo tem o seu desenho (groove-bg.png / corte.png) e o seu conjunto de
campos. Retangulos medidos com torno_cam_ui/tools/detecta_caixas.py.
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit, OverlayToggle, responsive
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine
from .panels import WCS, DIRS, COOL

MODOS = [(u"Canal", "GROOVE"), (u"Corte", "PART")]

OPC = {
    "toolNumber":    dict(integer=True, minimum=1),
    "toolWidth":     dict(minimum=0.001),
    "roughingDOC":   dict(minimum=0.001),
    "finishDOC":     dict(minimum=0.0),
    "toolClearance": dict(minimum=0.0),
    "retract":       dict(minimum=0.0),
    "peck":          dict(minimum=0.0),
    "edgeBreak":     dict(minimum=0.0),
}
MAXC = {"toolNumber": 2, "toolWidth": 5, "roughingDOC": 5, "finishDOC": 5,
        "toolClearance": 5, "retract": 5, "peck": 5, "edgeBreak": 5,
        "initialX": 7, "finalX": 7, "zStart": 7, "zEnd": 7}

VARIANTES = {
    "GROOVE": ("groove-bg.png", 1455.0 / 736.0, {
        "toolNumber":    (0.06807, 0.01146, 0.08140, 0.08166),
        "toolWidth":     (0.69333, 0.04871, 0.12140, 0.08166),
        "zStart":        (0.26667, 0.11461, 0.12211, 0.08166),
        "roughingDOC":   (0.68211, 0.15903, 0.12140, 0.08166),
        "finishDOC":     (0.61965, 0.27077, 0.12140, 0.08166),
        "initialX":      (0.05193, 0.45989, 0.12211, 0.08166),
        "finalX":        (0.40000, 0.45989, 0.12281, 0.08166),
        "toolClearance": (0.55649, 0.60458, 0.12211, 0.08309),
        "zEnd":          (0.22316, 0.82521, 0.12211, 0.08166),
    }),
    "PART": ("corte.png", 1465.0 / 720.0, {
        "toolNumber":    (0.15007, 0.01250, 0.11937, 0.07778),
        "zStart":        (0.26808, 0.11528, 0.11937, 0.07639),
        "retract":       (0.67121, 0.09306, 0.11937, 0.07778),
        "peck":          (0.80764, 0.09306, 0.11937, 0.07778),
        "toolWidth":     (0.67121, 0.28472, 0.11937, 0.07639),
        "initialX":      (0.05389, 0.45972, 0.11937, 0.07639),
        "finalX":        (0.40177, 0.45972, 0.11937, 0.07639),
        "toolClearance": (0.55662, 0.60278, 0.12005, 0.07778),
        "edgeBreak":     (0.72237, 0.87361, 0.11869, 0.07778),
    }),
}

# GERAR CICLO so existe no desenho do canal (o corte nao tem ciclo fixo)
TOGGLE_CANAL = ("useCannedCycle", 6.29, 47.52, u"GERAR CICLO", "#4caf50")

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class GrooveForm(QWidget):
    """Mesma interface dos outros forms (changed / collect / load)."""

    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(GrooveForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._toggles = {}
        self._extra = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        modo = self._modo()
        imagem, aspect, _r = VARIANTES[modo]
        self._panel = ImageOverlayPanel(imagem, aspect=aspect)
        root.addWidget(self._panel, 1)

        chaves = set()
        for _img, _asp, rects in VARIANTES.values():
            chaves.update(rects)
        for key in sorted(chaves):
            e = OverlayEdit(**OPC.get(key, {}))
            e.committed.connect(self._on_changed)
            self._edits[key] = e

        key, top, left, texto, cor = TOGGLE_CANAL
        t = OverlayToggle(texto, cor)
        t.toggled.connect(self._on_changed)
        self._toggles[key] = t
        self._panel.add_item(t, top, left,
                             font_fn=lambda cw: responsive(cw, 11, 0.014, 16))
        # G75 nao existe no LinuxCNC 2.9 — mesma trava das outras operacoes.
        t.setEnabled(False)
        t.setToolTip(u"Ciclo G75 nao existe no LinuxCNC 2.9. "
                     u"Use o modo linha a linha.")

        root.addWidget(self._build_strip())
        self._aplicar_modo()
        self.load(self.params)

    # ── modo ────────────────────────────────────────────────────────────
    def _modo(self):
        m = self.params.get("mode", "GROOVE")
        return m if m in VARIANTES else "GROOVE"

    def _aplicar_modo(self):
        modo = self._modo()
        imagem, aspect, rects = VARIANTES[modo]
        itens = [(self._edits[k], r, MAXC.get(k, 7)) for k, r in rects.items()]
        self._panel.reconfigurar(imagem, aspect, itens)
        # o toggle de ciclo so faz sentido no canal
        self._toggles["useCannedCycle"].setVisible(modo == "GROOVE")

    def _on_modo_mudou(self, *_a):
        w = self._extra.get("mode")
        if w is not None:
            self.params["mode"] = w.committed_value()
        self._aplicar_modo()
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
            ("plungeFPR",     u"Av mergulho",  "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
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
        self._aplicar_modo()

    def collect(self):
        for key, e in self._edits.items():
            self.params[key] = e.commit()
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        for key, t in self._toggles.items():
            self.params[key] = bool(t.isChecked())
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        self.params["operationType"] = "GROOVE"
        # desconta a largura do sangrador em Z (corte em -5 com pastilha
        # de 3 -> ferramenta em -8), senao a peca sai curta
        self.params["compensarLargura"] = True
        # largura do canal segue o Z (o engine usa zStart/zEnd; o campo e' rotulo)
        self.params["grooveWidth"] = abs(self.params.get("zEnd", 0)
                                         - self.params.get("zStart", 0))
        return copy.deepcopy(self.params)
