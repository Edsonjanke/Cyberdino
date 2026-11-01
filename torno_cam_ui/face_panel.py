# -*- coding: utf-8 -*-
"""FACEAR, tela 01 do padrao novo (handoff telas de ciclo, 2026-11-01).

Desenho, rotulos e posicoes em ciclos/01-facear.json. CHANFRO e' campo novo
(chanfro a 45 graus no passe de acabamento, secao 7.1 a do handoff)."""

from .ciclo_form import (CicloForm, celulas_config, celulas_corte,
                         DICA_SO_ACABAMENTO)

DICA_CICLO = (u"Desbaste com o ciclo G72 do LinuxCNC (perfil numa sub). "
              u"O acabamento sai linha a linha.")


class FaceForm(CicloForm):
    TELAS = {"FACE": "01-facear"}
    OPERACAO = "FACE"
    CAMPOS = {
        "ferramenta":      ("toolNumber",    dict(integer=True, minimum=1)),
        "chanfro":         ("chamferSize",   dict(minimum=0.0)),
        "z_final":         ("zEnd",          {}),
        "x_inicial":       ("initialX",      {}),
        "x_final":         ("finalX",        {}),
        "z_inicial":       ("zStart",        {}),
        "afastamento_g0":  ("toolClearance", dict(minimum=0.0)),
        "prof_desbaste":   ("roughingDOC",   dict(minimum=0.001)),
        "prof_acabamento": ("finishDOC",     dict(minimum=0.0)),
    }
    LIGADAS = {"finishOnly": DICA_SO_ACABAMENTO, "useCannedCycle": DICA_CICLO}

    def linhas_faixa(self):
        return [(u"CONFIG.", celulas_config()),
                (u"CORTE", celulas_corte())]

    def _pos_collect(self, params):
        # SOMENTE ACABAMENTO tambem linha a linha e G72 no formato do
        # LinuxCNC 2.9 (so desbaste); sem as flags o engine faz como o EvoCAM
        params["finishOnlyManual"] = True
        params["cicloLinuxCNC"] = True
