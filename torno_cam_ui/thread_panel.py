# -*- coding: utf-8 -*-
"""ROSCA — painel conversational, externa e interna.

Cada lado tem o seu desenho (thread-bg.png / thread-internal-bg.png).
Retangulos medidos com torno_cam_ui/tools/detecta_caixas.py (rosca_ext/int).

Dois campos do desenho (PROF. PASSE e ENTRADA) ficam DESABILITADOS: o engine
os ignora — ele deriva a profundidade dos passes pela lei da raiz e as entradas
por 2.5x/1.5x o passo. Mostrar habilitado seria enganar o operador.
"""

import copy
import math

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
    "taperAngle":   dict(decimals=4),
}
MAXC = {"toolNumber": 2, "spindleRPM": 4, "passes": 2, "tpi": 4,
        "taperAngle": 6,
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
        "taperAngle":   (0.21165, 0.25665, 0.09511, 0.06243),
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
        "taperAngle":   (0.21469, 0.21935, 0.10847, 0.06412),
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
            if key == "taperAngle":
                e.committed.connect(self._on_conicidade_editada)
            elif key in ("xStart", "xEnd", "zStart", "zEnd"):
                e.committed.connect(self._on_extremos_editados)
            else:
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
            ("tabela",        u"Tabela",        "combo", roscas.TABELAS),
            ("rosca",         u"Rosca",         "roscas"),
            ("side",          u"Lado",          "combo", SIDES),
            ("threadType",    u"Tipo",          "combo", TTYPE),
            ("springPasses",  u"Passes mola",   "int",   dict(maximum=10)),
            ("minorDiameter", u"Ø menor (0=auto)", "num", dict(decimals=3, suffix="mm")),
            ("workOffset",    u"Zero peca",     "combo", WCS),
            ("spindleDir",    u"Fuso",          "combo", DIRS),
            ("coolant",       u"Refrigeracao",  "combo", COOL),
            ("roughingFPR",   u"Avanco",        "num",   dict(decimals=3, suffix="mm/v", step=0.01)),
        ]
        for i, spec in enumerate(specs):
            key, label, kind = spec[0], spec[1], spec[2]
            col = i % 5
            row = (i // 5) * 2
            lab = QLabel(label)
            lab.setStyleSheet(_LABEL_QSS)
            if kind == "roscas":
                w = ComboRoscas(self._itens_da_tabela())
                w.currentIndexChanged.connect(self._aplicar_rosca)
            elif kind == "text":
                w = TouchLine()
                w.textChanged.connect(self._on_changed)
            elif kind == "combo":
                w = TouchCombo(spec[3])
                if key == "side":
                    w.currentIndexChanged.connect(self._on_lado_mudou)
                elif key == "tabela":
                    w.currentIndexChanged.connect(self._on_tabela_mudou)
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
        # embaixo da ULTIMA linha de campos (a faixa cresceu com o seletor de
        # tabela; fixar a linha 4 fazia a dica cair por cima dos campos)
        grid.addWidget(dica, ((len(specs) - 1) // 5) * 2 + 2, 0, 1, 5)
        return box

    def _itens_da_tabela(self):
        tab = self.params.get("tabela") or roscas.TAB_METRICA
        return [dict(it, cor=roscas.COR[it["tipo"]]) for it in roscas.lista(tab)]

    def _on_tabela_mudou(self, *_a):
        """Metrica / polegada / NPT: troca a lista e ja aplica a primeira."""
        w = self._extra.get("tabela")
        if w is not None:
            self.params["tabela"] = w.committed_value()
        combo = self._extra.get("rosca")
        if combo is not None:
            combo.recarregar(self._itens_da_tabela())
        self._aplicar_rosca()

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
            # polegada e NPT sao chamadas por fios/pol: o engine usa o tpi e
            # ignora o passo. O passo vai preenchido so' para leitura.
            imperial = bool(it.get("tpi"))
            self.params["threadType"] = "imperial" if imperial else "metric"
            tw = self._extra.get("threadType")
            if tw is not None:
                tw.blockSignals(True)
                tw.set_value(self.params["threadType"])
                tw.blockSignals(False)

            x_inicial = it["broca"] if interna else it["bitola"]
            x_final = x_inicial
            if it.get("conicidade"):
                # NPT: o diametro cresce ao entrar na peca (1:16). Sem isso a
                # rosca sairia cilindrica e a conexao nao vedaria.
                # o diametro da tabela vale na FACE (z=0) e cresce ao entrar
                # na peca: D(z) = D0 - z/16. Assim os dois extremos saem do
                # mesmo cone, sem depender de onde comeca a aproximacao.
                z0 = self._valor("zStart", 0.0)
                z1 = self._valor("zEnd", -it.get("comprimento", 10.0))
                x_inicial = round(it["bitola"] - z0 * it["conicidade"], 4)
                if interna:
                    x_inicial = round(it["broca"] - z0 * it["conicidade"], 4)
                x_final = round(x_inicial - (z1 - z0) * it["conicidade"], 4)
                self._travar_ciclo(True)
            else:
                self._travar_ciclo(False)

            conic = it.get("conicidade") or 0.0
            valores = {
                "pitch": it["passo"],
                "tpi": it.get("tpi", 0.0),
                "spindleRPM": it["rpm"],
                "xStart": x_inicial,
                "xEnd": x_final,
                # angulo por lado que corresponde a conicidade da tabela
                "taperAngle": round(math.degrees(math.atan(conic / 2.0)), 4),
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

    # ── conicidade <-> X final ──────────────────────────────────────────
    # O angulo e' POR LADO (como se le no desenho): o diametro muda
    # 2 x tg(angulo) por mm ao entrar na peca. NPT 1:16 = 1.7899 graus.
    def _on_conicidade_editada(self, *_a):
        try:
            ang = self._valor("taperAngle", 0.0)
            x0 = self._valor("xStart", 0.0)
            z0, z1 = self._valor("zStart", 0.0), self._valor("zEnd", 0.0)
            novo = x0 + 2.0 * math.tan(math.radians(ang)) * (z0 - z1)
            e = self._edits.get("xEnd")
            if e is not None:
                e.blockSignals(True)
                e.set_value(round(novo, 4))
                e.blockSignals(False)
        except Exception:
            pass
        self._on_changed()

    def _on_extremos_editados(self, *_a):
        """Mexeu num X ou num Z: a conicidade mostrada segue os extremos."""
        try:
            x0, x1 = self._valor("xStart", 0.0), self._valor("xEnd", 0.0)
            z0, z1 = self._valor("zStart", 0.0), self._valor("zEnd", 0.0)
            ang = 0.0
            if z0 != z1:
                ang = math.degrees(math.atan(((x1 - x0) / 2.0) / (z0 - z1)))
            e = self._edits.get("taperAngle")
            if e is not None:
                e.blockSignals(True)
                e.set_value(round(ang, 4))
                e.blockSignals(False)
        except Exception:
            pass
        self._on_changed()

    def _valor(self, chave, padrao=0.0):
        e = self._edits.get(chave)
        if e is None:
            return padrao
        try:
            e.commit()               # le o que estiver digitado
            return e.value()
        except Exception:
            return padrao

    def _travar_ciclo(self, travar):
        """G76 nao faz conicidade — na NPT o ciclo tem que sair de cena.

        Se deixasse ligado, o LinuxCNC cortaria uma rosca CILINDRICA com o
        diametro do inicio: passaria no calibre de boca e nao vedaria."""
        t = self._toggles.get("useCannedCycle")
        if t is None:
            return
        if travar:
            t.blockSignals(True)
            t.setChecked(False)
            t.blockSignals(False)
            self.params["useCannedCycle"] = False
        t.setEnabled(not travar)
        t.setToolTip(u"O G76 nao faz rosca conica. A NPT sai linha a linha."
                     if travar else u"")

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
        # cone ancorado em (zStart,xStart)-(zEnd,xEnd); sem isso a entrada e a
        # saida da rosca "abrem" o cone (ver strategies/thread.py)
        self.params["taperTrueAngle"] = True
        self.params["operationType"] = ("THREAD_INTERNAL"
                                        if lado in ("INTERNAL", "ID")
                                        else "THREAD_EXTERNAL")
        return copy.deepcopy(self.params)
