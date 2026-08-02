# -*- coding: utf-8 -*-
"""FURACAO — painel conversational sobre a imagem de referencia.

Mesma ideia do faceamento, mas a geometria do desenho e outra: o container do
app tem aspect ratio 1440x720 (= o da propria imagem, sem faixa preta) e cada
campo tem largura/altura em PORCENTAGEM do container — a caixa E o campo,
ancorada pelo canto superior-esquerdo. Coordenadas copiadas do DrillPanel.tsx.
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit, OverlayToggle, responsive
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine
from .panels import WCS, DIRS, COOL
from torno_cam.engine import furacao

# aspect ratio do container no app (igual ao da imagem: 1440x720)
DRILL_AR = 1440.0 / 720.0

# Retangulos MEDIDOS no proprio drill-bg.png (fracao da imagem: x, y, larg, alt).
FIELDS = [
    ("toolNumber",    (0.07361, 0.01806, 0.07917, 0.07778), 2, dict(integer=True, minimum=1)),
    ("zStart",        (0.32153, 0.05833, 0.11875, 0.07778), 6, {}),
    ("toolClearance", (0.46528, 0.15972, 0.11875, 0.07778), 5, dict(minimum=0.0)),
    ("peckDepth",     (0.15208, 0.23472, 0.11875, 0.07639), 5, dict(minimum=0.0)),
    ("drillDiameter", (0.51528, 0.52500, 0.10208, 0.09028), 5, dict(minimum=0.001)),
    ("roughingSFM",   (0.87222, 0.27361, 0.10694, 0.07917), 4, dict(integer=True, minimum=1)),
    ("dwellSeconds",  (0.87153, 0.54167, 0.10694, 0.07917), 4, dict(minimum=0.0)),
    ("zEnd",          (0.20208, 0.85833, 0.12014, 0.08056), 7, {}),
]

TOGGLE = ("useCannedCycle", 8.0, 65.0, u"GERAR CICLO", "#4caf50")

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class DrillForm(QWidget):
    """Mesma interface do OpForm/FaceForm (changed / collect / load)."""

    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(DrillForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._toggles = {}
        self._extra = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._panel = ImageOverlayPanel("drill-bg.png", aspect=DRILL_AR)
        root.addWidget(self._panel, 1)

        def input_font(cw):
            return responsive(cw, 14, 0.024, 28)

        def label_font(cw):
            return responsive(cw, 11, 0.014, 16)

        for key, rect, max_chars, opts in FIELDS:
            e = OverlayEdit(**opts)
            e.committed.connect(self._on_changed)
            self._edits[key] = e
            if key == "drillDiameter":
                e.committed.connect(self._aplicar_tabela)
            self._panel.add_box_item(e, rect, max_chars=max_chars)

        key, top, left, texto, cor = TOGGLE
        t = OverlayToggle(texto, cor)
        t.toggled.connect(self._on_changed)
        self._toggles[key] = t
        self._panel.add_item(t, top, left, font_fn=label_font)
        # Ciclo de furacao LIBERADO: o dialeto LinuxCNCDinoPost corrige plano
        # (G17), unidade da pausa (segundos) e usa G82 quando ha pausa.
        t.setToolTip(u"Gera ciclo fixo G81/G82/G83 (com G17 no lugar de G18, "
                     u"como o LinuxCNC exige para furar em Z).")

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
            ("material",      u"Material",     "combo",
             [(furacao.MATERIAIS[k]["nome"], k) for k in furacao.ORDEM]),
            ("title",         u"Titulo",       "text"),
            ("workOffset",    u"Zero peca",    "combo", WCS),
            ("spindleDir",    u"Fuso",         "combo", DIRS),
            ("coolant",       u"Refrigeracao", "combo", COOL),
            ("maxSpindleRPM", u"RPM max",      "int",   dict(suffix="rpm", step=50)),
            ("roughingFPR",   u"Avanco",       "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
        ]
        for i, spec in enumerate(specs):
            key, label, kind = spec[0], spec[1], spec[2]
            lab = QLabel(label)
            lab.setStyleSheet(_LABEL_QSS)
            if kind == "text":
                w = TouchLine()
                w.textChanged.connect(self._on_changed)
            elif kind == "combo":
                w = TouchCombo(spec[3])
                if key == "material":
                    w.currentIndexChanged.connect(self._aplicar_tabela)
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
            grid.addWidget(lab, 0, i)
            grid.addWidget(w, 1, i)
            grid.setColumnStretch(i, 1)
        return box

    # ── tabela de parametros de corte ───────────────────────────────────
    def _aplicar_tabela(self, *_a):
        """Preenche RPM, avanco e bicada a partir do material + diametro da
        broca (ver torno_cam/engine/furacao.py). O operador pode sobrescrever
        qualquer campo depois — a tabela e' ponto de partida, nao trava."""
        try:
            w = self._extra.get("material")
            material = w.committed_value() if w is not None else "ACO"
            diam = self._edits["drillDiameter"].commit()
            par = furacao.parametros(material, diam)
            for chave, valor in (("roughingSFM", par["rpm"]),
                                 ("peckDepth", par["bicada"])):
                e = self._edits.get(chave)
                if e is not None:
                    e.blockSignals(True)
                    e.set_value(valor)
                    e.blockSignals(False)
            av = self._extra.get("roughingFPR")
            if av is not None:
                av.blockSignals(True)
                av.setValue(par["avanco"])
                av.blockSignals(False)
        except Exception:
            pass
        self._on_changed()

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
        # o campo do desenho e RPM (nao Vc): o engine usa roughingSFM como
        # rotacao quando css_mode=False, entao o valor vai direto.
        self.params["finishingSFM"] = self.params.get("roughingSFM")
        for key, t in self._toggles.items():
            self.params[key] = bool(t.isChecked())
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        self.params["operationType"] = "DRILL"
        # A bicada digitada vale: sem isso o app so usaria G83 acima de 3x o
        # diametro e um furo raso sairia direto, ignorando o PECK DEPTH.
        self.params["forcePeckCycle"] = True
        return copy.deepcopy(self.params)
