# -*- coding: utf-8 -*-
"""DESBASTE EXT, tela 02 do padrao novo (handoff telas de ciclo, 2026-11-01).

CHANFRO SAIDA e CHANFRO ENTRADA sao campos novos (secao 7.1 c do handoff).
As opcoes GERAR CICLO e SOMENTE ACABAMENTO, que ficavam soltas no desenho,
agora estao na faixa padrao."""

from .ciclo_form import (CicloForm, celulas_config, celulas_corte,
                         DICA_SO_ACABAMENTO)
from .panels import YESNO

DICA_CICLO = (u"Desbaste com o ciclo G71 do LinuxCNC (perfil numa sub). "
              u"O acabamento sai linha a linha.")


class ODForm(CicloForm):
    TELAS = {"OD": "02-desbaste-ext"}
    OPERACAO = "OD_TURN"
    CAMPOS = {
        "chanfro_saida":   ("chamferExit",   dict(minimum=0.0)),
        "chanfro_entrada": ("chamferEntry",  dict(minimum=0.0)),
        "ferramenta":      ("toolNumber",    dict(integer=True, minimum=1)),
        "z_final":         ("zEnd",          {}),
        "x_inicial":       ("initialX",      {}),
        "x_final":         ("finalX",        {}),
        "raio_de_canto":   ("filletRadius",  dict(minimum=0.0)),
        "z_inicial":       ("zStart",        {}),
        "afastamento_g0":  ("toolClearance", dict(minimum=0.0)),
        "prof_acabamento": ("finishDOC",     dict(minimum=0.0)),
        "prof_desbaste":   ("roughingDOC",   dict(minimum=0.001)),
    }
    LIGADAS = {"finishOnly": DICA_SO_ACABAMENTO, "useCannedCycle": DICA_CICLO}

    def _pos_collect(self, params):
        # G71 no formato do LinuxCNC 2.9 (so desbaste)
        params["cicloLinuxCNC"] = True

    def linhas_faixa(self):
        css = ("useConstantSurface", u"CSS (G96)", "combo", YESNO, "")
        return [(u"CONFIG.", celulas_config(depois=[css])),
                (u"CORTE", celulas_corte())]
