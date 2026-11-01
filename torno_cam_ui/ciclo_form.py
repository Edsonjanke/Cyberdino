# -*- coding: utf-8 -*-
"""Base comum das telas de ciclo (handoff "telas de ciclo", 2026-11-01).

Cada operacao declara:
- TELAS   : chave da tela -> nome do JSON em torno_cam_ui/ciclos/
- CAMPOS  : id do campo no JSON -> (chave do params, opcoes do CampoCiclo)
- LIGADAS / TRAVADAS : opcoes da faixa padrao com logica nesta operacao
- linhas_faixa() : as celulas da faixa inferior
e herda daqui o painel, a faixa padrao, a faixa inferior e o load/collect.

As chaves do params sao as mesmas de antes (trabalhos salvos continuam
abrindo); so os textos da tela mudaram.
"""

import copy

from qtpy.QtWidgets import QWidget, QVBoxLayout
from qtpy.QtCore import Signal

from .ciclo_panel import (CicloPanel, CampoCiclo, FaixaPadrao, FaixaInferior,
                          carregar_tela)
from .widgets import TouchDoubleSpin, TouchIntSpin, TouchCombo, TouchLine


class CicloForm(QWidget):
    """Mesma interface dos forms antigos (changed / collect / load)."""

    changed = Signal()

    TELAS = {}
    CAMPOS = {}
    OPERACAO = ""
    LIGADAS = {}          # chave da opcao -> dica
    TRAVADAS = {}         # chave da opcao -> dica (tem logica, mas bloqueada)
    CHAVES_DE_TELA = ()   # extras que trocam o desenho (modo, lado)

    def __init__(self, default_params, parent=None):
        super(CicloForm, self).__init__(parent)
        self.params = copy.deepcopy(default_params)
        self._edits = {}      # chave do params -> CampoCiclo
        self._vazios = {}     # id do JSON sem logica -> CampoCiclo desabilitado
        self._extra = {}      # chave do params -> widget da faixa inferior
        self._telas = {}      # cache dos JSON

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        self._panel = CicloPanel(self._tela(self._chave_tela()))
        root.addWidget(self._panel, 1)

        for _id, (chave, opcoes) in self.CAMPOS.items():
            if chave in self._edits:
                continue
            e = CampoCiclo(**opcoes)
            e.committed.connect(lambda _c=chave: self._ao_editar(_c))
            self._edits[chave] = e

        self._faixa = FaixaPadrao(self._panel, self._on_changed)
        # AFASTAMENTO FINAL Z / X tem logica nas 13 telas (engine/strategies/
        # afastamento.py)
        for chave in ("afastamentoFinalZAbs", "afastamentoFinalXAbs"):
            self._faixa.ligar(chave, DICA_AFASTAMENTO_FINAL)
        # PAUSA e FERRAMENTA no final valem nas 13 telas (engine/strategies/fim.py)
        self._faixa.ligar("pausaNoFinal", DICA_PAUSA)
        self._faixa.ligar("ferramentaFinal", DICA_FERRAMENTA_FINAL)
        for chave, dica in self.LIGADAS.items():
            self._faixa.ligar(chave, dica)
        for chave, dica in self.TRAVADAS.items():
            self._faixa.travar(chave, dica)

        linhas = []
        for titulo, celulas in self.linhas_faixa():
            itens = []
            for cel in celulas:
                chave, rotulo, tipo, arg, unidade = cel
                w = self._criar_extra(chave, tipo, arg)
                self._extra[chave] = w
                itens.append((rotulo, w, unidade))
            linhas.append((titulo, itens))
        root.addWidget(FaixaInferior(linhas))

        self._pos_init()
        self._aplicar_tela()
        self.load(self.params)

    # ── ganchos ────────────────────────────────────────────────────────────
    def linhas_faixa(self):
        return []

    def _pos_init(self):
        pass

    def _chave_tela(self):
        return list(self.TELAS)[0]

    def _ao_editar(self, chave):
        self._on_changed()

    def _ao_mudar_extra(self, chave):
        if chave in self.CHAVES_DE_TELA:
            w = self._extra.get(chave)
            if w is not None:
                self.params[chave] = w.committed_value()
            self._aplicar_tela()
        self._on_changed()

    def _pos_collect(self, params):
        pass

    def _opcoes_da_tela(self):
        """Liga/desliga opcoes que dependem do modo (chamado a cada troca de
        desenho)."""
        pass

    # ── construcao ─────────────────────────────────────────────────────────
    def _tela(self, chave):
        nome = self.TELAS[chave]
        if nome not in self._telas:
            self._telas[nome] = carregar_tela(nome)
        return self._telas[nome]

    def _criar_extra(self, chave, tipo, arg):
        if tipo == "text":
            w = TouchLine()
            w.textChanged.connect(self._on_changed)
        elif tipo == "combo":
            w = TouchCombo(arg)
            w.currentIndexChanged.connect(lambda _i, _c=chave: self._ao_mudar_extra(_c))
        elif tipo == "int":
            w = TouchIntSpin(**(arg or {}))
            w.valueChanged.connect(self._on_changed)
        else:
            w = TouchDoubleSpin(**(arg or {}))
            w.valueChanged.connect(self._on_changed)
        return w

    def _aplicar_tela(self):
        tela = self._tela(self._chave_tela())
        itens = []
        for c in tela.get("campos", []):
            if c.get("grupo") == "faixa_padrao":
                continue                         # vem da FaixaPadrao
            cx = c["caixa"]
            caixa = (cx["x"], cx["y"], cx["w"], cx["h"])
            fonte = c.get("fonte_valor", 38.0)
            mapeado = self.CAMPOS.get(c["id"])
            if mapeado is not None:
                itens.append((self._edits[mapeado[0]], caixa, fonte))
            else:
                # campo do desenho sem logica no engine: caixa visivel e
                # desabilitada (vai para o relatorio do handoff)
                v = self._vazios.get(c["id"])
                if v is None:
                    v = CampoCiclo()
                    v.setText(u"")
                    v.setReadOnly(True)
                    v.setEnabled(False)
                    v.setToolTip(u"Sem lógica no gerador ainda.")
                    self._vazios[c["id"]] = v
                itens.append((v, caixa, fonte))
        self._panel.set_tela(tela, itens)
        self._opcoes_da_tela()

    # ── interface usada pela aba ───────────────────────────────────────────
    def _on_changed(self, *_a):
        self.changed.emit()

    def load(self, params):
        self.params = copy.deepcopy(params)
        for chave, e in self._edits.items():
            v = self.params.get(chave, 0)
            e.blockSignals(True)
            e.set_value(v if v is not None else 0)
            e.blockSignals(False)
        self._faixa.load(self.params)
        for chave, w in self._extra.items():
            v = self.params.get(chave)
            w.blockSignals(True)
            if isinstance(w, TouchLine):
                w.set_value(v if v is not None else "")
            elif hasattr(w, "set_value"):
                w.set_value(v)
            else:
                w.setValue(v if v is not None else 0)
            w.blockSignals(False)
        self._aplicar_tela()

    def collect(self):
        for chave, e in self._edits.items():
            self.params[chave] = e.commit()        # le o que estiver digitado
        self.params["toolOffset"] = self.params.get("toolNumber", 1)
        self._faixa.collect(self.params)
        for chave, w in self._extra.items():
            self.params[chave] = w.committed_value()
        self.params["operationType"] = self.OPERACAO
        self._pos_collect(self.params)
        return copy.deepcopy(self.params)

    def tela_atual(self):
        """Nome do JSON da tela que esta na frente (usado pela aba)."""
        return self.TELAS[self._chave_tela()]


# ── celulas que se repetem nas telas ─────────────────────────────────────────
def celulas_config(*antes, **kw):
    """TITULO, ZERO PECA, FUSO, REFRIGERACAO (+ celulas extras antes/depois)."""
    from .panels import WCS, DIRS, COOL
    base = [
        ("title",      u"TÍTULO",       "text",  None, ""),
        ("workOffset", u"ZERO PEÇA",    "combo", WCS,  ""),
        ("spindleDir", u"FUSO",         "combo", DIRS, ""),
        ("coolant",    u"REFRIGERAÇÃO", "combo", COOL, ""),
    ]
    return list(antes) + base + list(kw.get("depois", []))


def celulas_corte():
    """VC DESBASTE, VC ACABAMENTO, RPM MAXIMA, AVANCO DESBASTE e ACABAMENTO."""
    return [
        ("roughingSFM",   u"VC DESBASTE",       "num", dict(decimals=0, step=5),     "M/MIN"),
        ("finishingSFM",  u"VC ACABAMENTO",     "num", dict(decimals=0, step=5),     "M/MIN"),
        ("maxSpindleRPM", u"RPM MÁXIMA",        "int", dict(step=50),                "RPM"),
        ("roughingFPR",   u"AVANÇO DESBASTE",   "num", dict(decimals=3, step=0.01),  "MM/V"),
        ("finishingFPR",  u"AVANÇO ACABAMENTO", "num", dict(decimals=3, step=0.01),  "MM/V"),
    ]


DICA_SO_ACABAMENTO = u"Faz só o passe de acabamento."

DICA_PAUSA = (u"No fim da operação, depois de afastar: desliga o fuso (M5) e "
              u"para o programa (M0). Continua no CYCLE START.")

DICA_FERRAMENTA_FINAL = (u"No fim da operação, chama a ferramenta da primeira "
                         u"operação do programa.")

DICA_AFASTAMENTO_FINAL = (u"Posição absoluta no fim da operação (X em diâmetro). "
                          u"Depois da saída normal, vai em G0 primeiro em Z e "
                          u"depois em X. Vazio = não usa.")
