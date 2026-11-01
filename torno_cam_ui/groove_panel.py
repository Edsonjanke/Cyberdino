# -*- coding: utf-8 -*-
"""CANAL / CORTE, telas 10 e 11 do padrao novo (handoff telas de ciclo,
2026-11-01).

CANAL: mergulhos alternando o sentido + acabamento em duas metades.
CORTE: sangria com bicadas e retorno, com quebra-canto opcional."""

from .ciclo_form import (CicloForm, celulas_config, celulas_corte,
                         DICA_SO_ACABAMENTO)

MODOS = [(u"CANAL", "GROOVE"), (u"CORTE", "PART")]

DICA_CORTE_SEM_ACAB = u"O corte não tem passe de acabamento."

DICA_CICLO = (u"Ciclo G75 não existe no LinuxCNC 2.9. "
              u"Use o modo linha a linha.")


class GrooveForm(CicloForm):
    TELAS = {"GROOVE": "10-canal", "PART": "11-corte"}
    OPERACAO = "GROOVE"
    CHAVES_DE_TELA = ("mode",)
    CAMPOS = {
        "ferramenta":              ("toolNumber",    dict(integer=True, minimum=1)),
        "z_inicio":                ("zStart",        {}),
        "inicio_em_z":             ("zStart",        {}),
        "x_inicial":               ("initialX",      {}),
        "x_final":                 ("finalX",        {}),
        "z_fim":                   ("zEnd",          {}),
        "largura_da_ferramenta":   ("toolWidth",     dict(minimum=0.001)),
        "prof_desbaste":           ("roughingDOC",   dict(minimum=0.001)),
        "prof_acabamento":         ("finishDOC",     dict(minimum=0.0)),
        "afastamento_g0":          ("toolClearance", dict(minimum=0.0)),
        "retracao":                ("retract",       dict(minimum=0.0)),
        "incremento":              ("peck",          dict(minimum=0.0)),
        "largura_do_quebra_canto": ("edgeBreak",     dict(minimum=0.0)),
    }
    TRAVADAS = {"useCannedCycle": DICA_CICLO}

    def _opcoes_da_tela(self):
        # SOMENTE ACABAMENTO so no CANAL (o CORTE nao tem passe de acabamento)
        if self._chave_tela() == "PART":
            self._faixa.desligar("finishOnly", DICA_CORTE_SEM_ACAB)
        else:
            self._faixa.ligar("finishOnly", DICA_SO_ACABAMENTO)

    def _chave_tela(self):
        m = self.params.get("mode", "GROOVE")
        return m if m in self.TELAS else "GROOVE"

    def linhas_faixa(self):
        modo = ("mode", u"MODO", "combo", MODOS, "")
        mergulho = ("plungeFPR", u"AVANÇO MERGULHO", "num",
                    dict(decimals=3, step=0.01), "MM/V")
        return [(u"CONFIG.", celulas_config(modo, depois=[mergulho])),
                (u"CORTE", celulas_corte())]

    def _pos_collect(self, params):
        # desconta a largura do sangrador em Z (corte em -5 com pastilha
        # de 3 -> ferramenta em -8), senao a peca sai curta
        params["compensarLargura"] = True
        # quebra-canto do CORTE como no desenho (handoff 7.3)
        params["quebraCantoDesenho"] = True
        # largura do canal segue o Z (o engine usa zStart/zEnd; o campo e' rotulo)
        params["grooveWidth"] = abs(params.get("zEnd", 0) - params.get("zStart", 0))
