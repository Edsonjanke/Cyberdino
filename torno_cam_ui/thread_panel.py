# -*- coding: utf-8 -*-
"""ROSCA — painel conversational, externa e interna.

Cada lado tem o seu desenho (thread-bg.png / thread-internal-bg.png).
Retangulos medidos com torno_cam_ui/tools/detecta_caixas.py (rosca_ext/int).

Dois campos do desenho (PROF. PASSE e ENTRADA) ficam DESABILITADOS: o engine
os ignora — ele deriva a profundidade dos passes pela lei da raiz e as entradas
por 2.5x/1.5x o passo. Mostrar habilitado seria enganar o operador.
"""

import copy

from qtpy.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
                            QSizePolicy)
from qtpy.QtCore import Signal

from .image_panel import ImageOverlayPanel, OverlayEdit, OverlayToggle, responsive
from .widgets import (TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine,
                      ComboRoscas)
from torno_cam.engine import roscas
from .panels import WCS, DIRS, COOL, SIDES, TTYPE

OPC = {
    "toolNumber":   dict(integer=True, minimum=1),
    "spindleRPM":   dict(integer=True, minimum=1),
    "passes":       dict(integer=True, minimum=0),
    "clearance":    dict(minimum=0.0),
    "pitch":        dict(minimum=0.0),
    "tpi":          dict(minimum=0.0),
    "depthOfCut":   dict(minimum=0.0),
    "leadInLength": dict(minimum=0.0),
}
MAXC = {"toolNumber": 2, "spindleRPM": 4, "passes": 2, "tpi": 4,
        "pitch": 5, "clearance": 5, "depthOfCut": 5, "leadInLength": 5,
        "xStart": 7, "xEnd": 7, "zStart": 7, "zEnd": 7}

# campos que o engine NAO usa (derivados internamente)
IGNORADOS = ("depthOfCut", "leadInLength")

VARIANTES = {
    # desenho em PT-BR (1819x865). Retangulos remedidos com detecta_caixas.py
    "EXTERNAL": ("thread-bg.png", 1819.0 / 865.0, {
        "toolNumber":   (0.08961, 0.03353, 0.06927, 0.05896),
        "zEnd":         (0.18966, 0.09249, 0.09346, 0.06358),
        "zStart":       (0.31116, 0.09249, 0.09291, 0.06358),
        "clearance":    (0.50027, 0.10867, 0.09456, 0.06358),
        "xStart":       (0.55305, 0.26821, 0.09346, 0.06127),
        "spindleRPM":   (0.90984, 0.24046, 0.08301, 0.06358),
        "depthOfCut":   (0.56185, 0.49942, 0.09896, 0.06821),
        "tpi":          (0.73502, 0.82543, 0.09951, 0.06936),
        "pitch":        (0.87191, 0.82543, 0.10500, 0.06936),
        "xEnd":         (0.45355, 0.91908, 0.09621, 0.06474),
        "leadInLength": (0.17702, 0.89480, 0.12754, 0.05665),
        "passes":       (0.72128, 0.92139, 0.03903, 0.05434),
    }),
    # desenho em PT-BR (1770x889). O X de cima e' o FIM X e o de baixo o INICIO X
    "INTERNAL": ("thread-internal-bg.png", 1770.0 / 889.0, {
        "toolNumber":   (0.09887, 0.01687, 0.06949, 0.06187),
        "zEnd":         (0.19266, 0.08324, 0.10113, 0.06749),
        "zStart":       (0.31412, 0.08324, 0.10791, 0.06749),
        "clearance":    (0.49718, 0.09899, 0.10395, 0.06524),
        "spindleRPM":   (0.91921, 0.21710, 0.07119, 0.06299),
        "xEnd":         (0.55028, 0.24634, 0.10339, 0.06524),
        "depthOfCut":   (0.55311, 0.48931, 0.10452, 0.06524),
        "tpi":          (0.72768, 0.76828, 0.10621, 0.06524),
        "pitch":        (0.87627, 0.76828, 0.10734, 0.06524),
        "leadInLength": (0.18475, 0.84589, 0.12599, 0.06524),
        "passes":       (0.75085, 0.88076, 0.04463, 0.05624),
        "xStart":       (0.46328, 0.91789, 0.10678, 0.06187),
    }),
}

TOGGLE = ("useCannedCycle", 7.96, 87.91, u"GERAR CICLO", "#4caf50")

_LABEL_QSS = 'QLabel { color: #9BB0B5; font: 10pt "Bebas Kai"; }'


class ThreadForm(QWidget):
    changed = Signal()

    def __init__(self, default_params, parent=None):
        super(ThreadForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}
        self._toggles = {}
        self._extra = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        imagem, aspect, _r = VARIANTES[self._lado()]
        self._panel = ImageOverlayPanel(imagem, aspect=aspect)
        root.addWidget(self._panel, 1)

        chaves = set()
        for _i, _a, rects in VARIANTES.values():
            chaves.update(rects)
        for key in sorted(chaves):
            e = OverlayEdit(**OPC.get(key, {}))
            e.committed.connect(self._on_changed)
            if key in IGNORADOS:
                e.setReadOnly(True)
                e.setToolTip(u"O engine calcula este valor sozinho "
                             u"(profundidade pela lei da raiz, entrada 2.5x o passo).")
            self._edits[key] = e

        key, top, left, texto, cor = TOGGLE
        t = OverlayToggle(texto, cor)
        t.toggled.connect(self._on_changed)
        self._toggles[key] = t
        self._panel.add_item(t, top, left,
                             font_fn=lambda cw: responsive(cw, 11, 0.014, 16))
        t.setToolTip(u"Gera ciclo G76 do LinuxCNC (embrulhado em G8, que e' "
                     u"como o controlador le I/J/K em raio).")

        root.addWidget(self._build_strip())
        self._aplicar_lado()
        self.load(self.params)

    def _lado(self):
        s = self.params.get("side", "EXTERNAL")
        return "INTERNAL" if s in ("INTERNAL", "ID") else "EXTERNAL"

    def _aplicar_lado(self):
        imagem, aspect, rects = VARIANTES[self._lado()]
        itens = [(self._edits[k], r, MAXC.get(k, 7)) for k, r in rects.items()]
        self._panel.reconfigurar(imagem, aspect, itens)

    def _on_lado_mudou(self, *_a):
        w = self._extra.get("side")
        if w is not None:
            self.params["side"] = w.committed_value()
        self._aplicar_lado()
        self._aplicar_rosca()

    def _build_strip(self):
        box = QFrame()
        box.setStyleSheet('QFrame { background: #242729; border: 1px solid #3A3F43;'
                          ' border-radius: 4px; }')
        grid = QGridLayout(box)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        specs = [
            ("rosca",         u"Rosca metrica", "roscas"),
            ("side",          u"Lado",          "combo", SIDES),
            ("threadType",    u"Tipo",          "combo", TTYPE),
            ("springPasses",  u"Passes mola",   "int",   dict(maximum=10)),
            ("minorDiameter", u"Ø menor (0=auto)", "num", dict(decimals=3, suffix="mm")),
            ("workOffset",    u"Zero peca",     "combo", WCS),
            ("spindleDir",    u"Fuso",          "combo", DIRS),
            ("coolant",       u"Refrigeracao",  "combo", COOL),
            ("maxSpindleRPM", u"RPM max",       "int",   dict(suffix="rpm", step=50)),
            ("roughingFPR",   u"Avanco",        "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
        ]
        for i, spec in enumerate(specs):
            key, label, kind = spec[0], spec[1], spec[2]
            col = i % 5
            row = (i // 5) * 2
            lab = QLabel(label)
            lab.setStyleSheet(_LABEL_QSS)
            if kind == "roscas":
                itens = [dict(it, cor=roscas.COR[it["tipo"]])
                         for it in roscas.lista()]
                w = ComboRoscas(itens)
                w.currentIndexChanged.connect(self._aplicar_rosca)
            elif kind == "text":
                w = TouchLine()
                w.textChanged.connect(self._on_changed)
            elif kind == "combo":
                w = TouchCombo(spec[3])
                if key == "side":
                    w.currentIndexChanged.connect(self._on_lado_mudou)
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
        # dica do back-tool: M4 faz rosca DIREITA nesta maquina
        dica = QLabel(u"M4 = rosca direita (torre atras do centro)")
        dica.setStyleSheet('QLabel { color: #FFB300; font: 9pt "Bebas Kai"; }')
        grid.addWidget(dica, 4, 0, 1, 5)
        return box

    def _aplicar_rosca(self, *_a):
        """Preenche passo, diametro e RPM a partir da tabela de roscas.

        No lado EXTERNO o diametro e' o nominal (M10 -> 10). No INTERNO e' o
        furo antes de roscar (D - passo), que e' de onde a ferramenta parte.
        O operador pode ajustar qualquer campo depois."""
        try:
            w = self._extra.get("rosca")
            it = w.item_atual() if w is not None else None
            if not it:
                return
            interna = self._lado() == "INTERNAL"
            # o titulo e' sempre a rosca escolhida (nao ha campo p/ digitar)
            self.params["title"] = it["titulo"]
            valores = {
                "pitch": it["passo"],
                "tpi": 0.0,
                "spindleRPM": it["rpm"],
                "xStart": it["broca"] if interna else it["bitola"],
                "xEnd": it["broca"] if interna else it["bitola"],
            }
            for chave, valor in valores.items():
                e = self._edits.get(chave)
                if e is not None:
                    e.blockSignals(True)
                    e.set_value(valor)
                    e.blockSignals(False)
        except Exception:
            pass
        self._on_changed()

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
            # combos e campos de texto (inclusive o ComboRoscas) expoem
            # set_value; so os spinboxes usam setValue
            if hasattr(w, "set_value"):
                w.set_value(v if v is not None else "")
            else:
                w.setValue(v if v is not None else 0)
            w.blockSignals(False)
        self._aplicar_lado()

    def collect(self):
        for key, e in self._edits.items():
            self.params[key] = e.commit()
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        for key, t in self._toggles.items():
            self.params[key] = bool(t.isChecked())
        for key, w in self._extra.items():
            self.params[key] = w.committed_value()
        lado = self.params.get("side", "EXTERNAL")
        # titulo sempre vem da rosca selecionada
        w = self._extra.get("rosca")
        it = w.item_atual() if w is not None else None
        if it:
            self.params["title"] = it["titulo"]
        self.params["operationType"] = ("THREAD_INTERNAL"
                                        if lado in ("INTERNAL", "ID")
                                        else "THREAD_EXTERNAL")
        return copy.deepcopy(self.params)
