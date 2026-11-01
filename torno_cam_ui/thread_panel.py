# -*- coding: utf-8 -*-
"""ROSCA, telas 12 (externa) e 13 (interna) do padrao novo (handoff telas de
ciclo, 2026-11-01).

Dois campos do desenho (PROFUNDIDADE DE CORTE e COMPRIMENTO DA ROSCA) ficam
so de leitura: o engine os ignora, ele deriva a profundidade dos passes pela
lei da raiz e as entradas por 2.5x/1.5x o passo. PASSADAS DE ACABAMENTO
(so na interna) nao tem logica no engine: caixa desabilitada.
"""

import math

from torno_cam.engine import roscas

from .ciclo_form import CicloForm, celulas_config
from .widgets import ComboRoscas
from .panels import WCS, DIRS, COOL, SIDES, TTYPE

# campos que o engine NAO usa (derivados internamente)
IGNORADOS = ("depthOfCut", "leadInLength")

TABELAS = [(u"MÉTRICA", roscas.TAB_METRICA),
           (u"POLEGADA UNC/UNF", roscas.TAB_POLEGADA),
           (u"NPT (CÔNICA)", roscas.TAB_NPT)]

DICA_CICLO = u"Gera o ciclo G76 do LinuxCNC (I, J e K em diâmetro, no G7)."


class ThreadForm(CicloForm):
    TELAS = {"EXTERNAL": "12-rosca-externa", "INTERNAL": "13-rosca-interna"}
    OPERACAO = "THREAD_EXTERNAL"
    CAMPOS = {
        "ferramenta":            ("toolNumber",   dict(integer=True, minimum=1)),
        "fim_z":                 ("zEnd",         {}),
        "inicio_z":              ("zStart",       {}),
        "angulo_de_saida_taper": ("taperAngle",   dict(decimals=4)),
        "afastamento_g0":        ("clearance",    dict(minimum=0.0)),
        "inicio_x":              ("xStart",       {}),
        "fim_x":                 ("xEnd",         {}),
        "comprimento_da_rosca":  ("leadInLength", dict(minimum=0.0)),
        "rotacao_do_fuso_rpm":   ("spindleRPM",   dict(integer=True, minimum=1)),
        "profundidade_de_corte": ("depthOfCut",   dict(minimum=0.0)),
        "rosca_polegadas":       ("tpi",          dict(minimum=0.0)),
        "passo_pol":             ("pitch",        dict(minimum=0.0)),
        "numero_de_passadas":    ("passes",       dict(integer=True, minimum=0)),
        # "passadas_de_acabamento" (so na interna): sem logica no engine
    }
    LIGADAS = {"useCannedCycle": DICA_CICLO}

    # ── tela ───────────────────────────────────────────────────────────
    def _lado(self):
        s = self.params.get("side", "EXTERNAL")
        return "INTERNAL" if s in ("INTERNAL", "ID") else "EXTERNAL"

    def _chave_tela(self):
        return self._lado()

    def _pos_init(self):
        for chave in IGNORADOS:
            e = self._edits.get(chave)
            if e is not None:
                e.setReadOnly(True)
                e.setToolTip(u"O gerador calcula este valor sozinho: profundidade "
                             u"pela lei da raiz e entrada de 2,5 vezes o passo.")

    def linhas_faixa(self):
        rosca = [
            ("tabela",       u"TABELA",      "combo",  TABELAS, ""),
            ("rosca",        u"ROSCA",       "roscas", None,    ""),
            ("side",         u"LADO",        "combo",  SIDES,   ""),
            ("threadType",   u"TIPO",        "combo",  TTYPE,   ""),
            ("springPasses", u"PASSES MOLA", "int",    dict(maximum=10), ""),
        ]
        config = [
            ("minorDiameter", u"Ø MENOR (0 = AUTO)", "num", dict(decimals=3), "MM"),
            ("workOffset",    u"ZERO PEÇA",    "combo", WCS,  ""),
            ("spindleDir",    u"FUSO",         "combo", DIRS, ""),
            ("coolant",       u"REFRIGERAÇÃO", "combo", COOL, ""),
            ("roughingFPR",   u"AVANÇO",       "num",   dict(decimals=3, step=0.01), "MM/V"),
        ]
        return [(u"ROSCA", rosca), (u"CONFIG.", config)]

    def _criar_extra(self, chave, tipo, arg):
        if tipo == "roscas":
            w = ComboRoscas(self._itens_da_tabela())
            w.currentIndexChanged.connect(self._aplicar_rosca)
            return w
        return super(ThreadForm, self)._criar_extra(chave, tipo, arg)

    def _ao_mudar_extra(self, chave):
        if chave == "side":
            w = self._extra.get("side")
            if w is not None:
                self.params["side"] = w.committed_value()
            self._aplicar_tela()
            self._aplicar_rosca()
        elif chave == "tabela":
            self._on_tabela_mudou()
        else:
            self._on_changed()

    def _ao_editar(self, chave):
        if chave == "taperAngle":
            self._on_conicidade_editada()
        elif chave in ("xStart", "xEnd", "zStart", "zEnd"):
            self._on_extremos_editados()
        else:
            self._on_changed()

    # ── tabela de roscas ───────────────────────────────────────────────
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
                # NPT: o diametro da tabela vale na FACE (z=0) e cresce ao
                # entrar na peca: D(z) = D0 - z/16. Os dois extremos saem do
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

    # ── conicidade <-> X final ─────────────────────────────────────────
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
        """G76 nao faz conicidade: na NPT o ciclo tem que sair de cena.
        Se deixasse ligado, o LinuxCNC cortaria uma rosca CILINDRICA com o
        diametro do inicio: passaria no calibre de boca e nao vedaria."""
        t = self._faixa.opcoes.get("useCannedCycle")
        if t is None:
            return
        if travar:
            t.blockSignals(True)
            t.setChecked(False)
            t.blockSignals(False)
            self.params["useCannedCycle"] = False
        t.setEnabled(not travar)
        t.setToolTip(u"O G76 não faz rosca cônica. A NPT sai linha a linha."
                     if travar else DICA_CICLO)

    # ── coleta ─────────────────────────────────────────────────────────
    def _pos_collect(self, params):
        lado = params.get("side", "EXTERNAL")
        # titulo sempre vem da rosca selecionada
        w = self._extra.get("rosca")
        it = w.item_atual() if w is not None else None
        if it:
            params["title"] = it["titulo"]
        # cone ancorado em (zStart,xStart)-(zEnd,xEnd); sem isso a entrada e a
        # saida da rosca "abrem" o cone (ver strategies/thread.py)
        params["taperTrueAngle"] = True
        params["operationType"] = ("THREAD_INTERNAL" if lado in ("INTERNAL", "ID")
                                   else "THREAD_EXTERNAL")
