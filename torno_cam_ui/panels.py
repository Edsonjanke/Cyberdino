# -*- coding: utf-8 -*-
"""Especificacao dos campos por operacao + OpForm (constroi o formulario a
partir da spec e le/escreve o dict de params)."""

import copy

from qtpy.QtWidgets import QWidget, QGridLayout, QLabel
from qtpy.QtCore import Qt, Signal

from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine


# ── Opcoes de combo reutilizaveis ────────────────────────────────────────────
WCS = [("G54", "G54"), ("G55", "G55"), ("G56", "G56"),
       ("G57", "G57"), ("G58", "G58"), ("G59", "G59")]
DIRS = [("M3 horario", "CW"), ("M4 anti-horario", "CCW")]
COOL = [("M8 fluido", "FLOOD"), ("M7 nevoa", "MIST"), ("Ar", "AIR"), ("Sem", "OFF")]
YESNO = [("Nao", False), ("Sim", True)]
SIDES = [("Externa", "EXTERNAL"), ("Interna", "INTERNAL")]
TTYPE = [("Metrica (passo)", "metric"), ("Imperial (fios/pol)", "imperial")]


def F(key, label, kind, **kw):
    d = dict(key=key, label=label, kind=kind)
    d.update(kw)
    return d


_COMMON_HEAD = [
    F("title", "Titulo", "text"),
    F("workOffset", "Zero peca", "combo", options=WCS),
    F("toolNumber", "Ferramenta T", "int", minimum=1, maximum=99),
    F("toolOffset", "Corretor H", "int", minimum=0, maximum=99),
    F("spindleDir", "Fuso", "combo", options=DIRS),
    F("coolant", "Refrigeracao", "combo", options=COOL),
]

_SPEEDS = [
    F("roughingSFM", "Vc desbaste", "num", decimals=0, suffix="m/min", step=5),
    F("finishingSFM", "Vc acabamento", "num", decimals=0, suffix="m/min", step=5),
    F("maxSpindleRPM", "RPM max", "int", suffix="rpm", step=50),
    F("roughingFPR", "Avanco desb", "num", suffix="mm/v", step=0.01),
    F("finishingFPR", "Avanco acab", "num", suffix="mm/v", step=0.01),
]

FACE_FIELDS = _COMMON_HEAD + [
    F("initialX", u"Ø inicial", "num", suffix="mm"),
    F("finalX", u"Ø final", "num", suffix="mm"),
    F("zStart", "Z inicial", "num", suffix="mm"),
    F("zEnd", "Z final", "num", suffix="mm"),
] + _SPEEDS + [
    F("roughingDOC", "Prof. desbaste", "num", suffix="mm", step=0.1),
    F("finishDOC", "Sobremetal acab", "num", suffix="mm", step=0.05),
    F("toolClearance", "Folga", "num", suffix="mm", step=0.5),
    F("finishOnly", "So acabamento", "combo", options=YESNO),
]

OD_FIELDS = _COMMON_HEAD + [
    F("initialX", u"Ø inicial", "num", suffix="mm"),
    F("finalX", u"Ø final", "num", suffix="mm"),
    F("zStart", "Z inicial", "num", suffix="mm"),
    F("zEnd", "Z final", "num", suffix="mm"),
    F("filletRadius", "Raio canto", "num", suffix="mm", step=0.5),
] + _SPEEDS + [
    F("roughingDOC", "Prof. desbaste", "num", suffix="mm", step=0.1),
    F("finishDOC", "Sobremetal acab", "num", suffix="mm", step=0.05),
    F("toolClearance", "Folga", "num", suffix="mm", step=0.5),
    F("useConstantSurface", "CSS (G96)", "combo", options=YESNO),
    F("finishOnly", "So acabamento", "combo", options=YESNO),
]

DRILL_FIELDS = _COMMON_HEAD + [
    F("drillDiameter", u"Ø broca", "num", suffix="mm"),
    F("zStart", "Z inicial", "num", suffix="mm"),
    F("zEnd", "Z final", "num", suffix="mm"),
    F("peckDepth", "Bicada (0=direto)", "num", suffix="mm", step=0.5),
    F("dwellSeconds", "Pausa fundo", "num", decimals=2, suffix="s", step=0.1),
    F("roughingSFM", "RPM", "int", minimum=0, maximum=100000, suffix="rpm", step=50),
    F("maxSpindleRPM", "RPM max", "int", suffix="rpm", step=50),
    F("roughingFPR", "Avanco", "num", suffix="mm/v", step=0.01),
    F("toolClearance", "Folga", "num", suffix="mm", step=0.5),
]

THREAD_FIELDS = _COMMON_HEAD + [
    F("side", "Lado", "combo", options=SIDES),
    F("threadType", "Tipo", "combo", options=TTYPE),
    F("xStart", u"Ø inicial", "num", suffix="mm"),
    F("xEnd", u"Ø final (conico)", "num", suffix="mm"),
    F("zStart", "Z inicial", "num", suffix="mm"),
    F("zEnd", "Z final", "num", suffix="mm"),
    F("clearance", "Folga", "num", suffix="mm", step=0.5),
    F("pitch", "Passo", "num", suffix="mm", step=0.05),
    F("tpi", "Fios/pol", "num", decimals=2, step=1.0),
    F("spindleRPM", "RPM", "int", minimum=1, maximum=100000, suffix="rpm", step=50),
    F("passes", "Passes (0=auto)", "int", minimum=0, maximum=60),
    F("springPasses", "Passes mola", "int", minimum=0, maximum=10),
    F("minorDiameter", u"Ø menor (0=auto)", "num", suffix="mm"),
]


_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 11pt "Bebas Kai"; }'


class OpForm(QWidget):
    """Formulario de uma operacao. Mantem um dict `params` (copia do default)
    e sincroniza com os widgets."""

    changed = Signal()

    def __init__(self, fields, default_params, parent=None):
        super(OpForm, self).__init__(parent)
        self._fields = fields
        self.params = copy.deepcopy(default_params)
        self._widgets = {}

        grid = QGridLayout(self)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(6, 6, 6, 6)

        for i, spec in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            lab = QLabel(spec["label"])
            lab.setStyleSheet(_LABEL_QSS)
            w = self._make_widget(spec)
            self._widgets[spec["key"]] = w
            grid.addWidget(lab, row, col)
            grid.addWidget(w, row, col + 1)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.load(self.params)

    def _make_widget(self, spec):
        kind = spec["kind"]
        if kind == "text":
            w = TouchLine()
            w.textChanged.connect(self.changed)
            return w
        if kind == "int":
            w = TouchIntSpin(minimum=spec.get("minimum", 0),
                             maximum=spec.get("maximum", 999999),
                             step=spec.get("step", 1),
                             suffix=spec.get("suffix", ""))
            w.valueChanged.connect(self.changed)
            return w
        if kind == "num":
            w = TouchDoubleSpin(decimals=spec.get("decimals", 3),
                                minimum=spec.get("minimum", -99999.0),
                                maximum=spec.get("maximum", 99999.0),
                                step=spec.get("step", 0.1),
                                suffix=spec.get("suffix", ""))
            w.valueChanged.connect(self.changed)
            return w
        if kind == "combo":
            w = TouchCombo(spec["options"])
            w.currentIndexChanged.connect(self.changed)
            return w
        raise ValueError("kind desconhecido: " + kind)

    def load(self, params):
        self.params = copy.deepcopy(params)
        for spec in self._fields:
            key = spec["key"]
            w = self._widgets[key]
            val = self.params.get(key)
            if spec["kind"] in ("num", "int"):
                w.blockSignals(True)
                w.setValue(val if val is not None else 0)
                w.blockSignals(False)
            elif spec["kind"] == "combo":
                w.blockSignals(True)
                w.set_value(val)
                w.blockSignals(False)
            elif spec["kind"] == "text":
                w.blockSignals(True)
                w.set_value(val if val is not None else "")
                w.blockSignals(False)

    def collect(self):
        """Le os widgets para o dict params e devolve uma copia pronta para o
        engine (com operationType coerente para rosca)."""
        for spec in self._fields:
            key = spec["key"]
            self.params[key] = self._widgets[key].committed_value()
        if "side" in self.params:
            self.params["operationType"] = (
                "THREAD_EXTERNAL" if self.params["side"] == "EXTERNAL"
                else "THREAD_INTERNAL")
        return copy.deepcopy(self.params)
