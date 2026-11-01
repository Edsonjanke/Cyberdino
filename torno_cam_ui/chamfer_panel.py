# -*- coding: utf-8 -*-
"""CHANFRO / RAIO, telas 06 a 09 do padrao novo (handoff telas de ciclo,
2026-11-01): modo (CHANFRO/RAIO) x lado (EXTERNO/INTERNO) = 4 desenhos.
Trocar modo ou lado troca o desenho e os campos; os valores ficam."""

from .ciclo_form import (CicloForm, celulas_config, celulas_corte,
                         DICA_SO_ACABAMENTO)

MODOS = [(u"CHANFRO", "CHAMFER"), (u"RAIO", "RADIUS")]
LADOS = [(u"EXTERNO", "OD"), (u"INTERNO", "ID")]


class ChamferForm(CicloForm):
    TELAS = {
        "CHAMFER_OD": "06-chanfro-externo",
        "CHAMFER_ID": "07-chanfro-interno",
        "RADIUS_OD":  "08-raio-externo",
        "RADIUS_ID":  "09-raio-interno",
    }
    OPERACAO = "CHAMFER"
    CHAVES_DE_TELA = ("mode", "side")
    CAMPOS = {
        "ferramenta":              ("toolNumber",    dict(integer=True, minimum=1)),
        "z_final":                 ("zEnd",          {}),
        "z_fim":                   ("zEnd",          {}),
        "z_inicial":               ("zStart",        {}),
        "z_inicio":                ("zStart",        {}),
        "x":                       ("x",             {}),
        "angulo_do_chanfro_graus": ("chamferAngle",  dict(minimum=1.0)),
        "angulo_de_entrada_graus": ("chamferAngle",  dict(minimum=1.0)),
        "passe_acabamento":        ("finishDOC",     dict(minimum=0.0)),
        "prof_acabamento":         ("finishDOC",     dict(minimum=0.0)),
        "passe_desbaste":          ("roughingDOC",   dict(minimum=0.001)),
        "prof_desbaste":           ("roughingDOC",   dict(minimum=0.001)),
        "afastamento_g0":          ("toolClearance", dict(minimum=0.0)),
    }

    LIGADAS = {"finishOnly": DICA_SO_ACABAMENTO}

    def _chave_tela(self):
        chave = "{}_{}".format(self.params.get("mode", "CHAMFER"),
                               self.params.get("side", "OD"))
        return chave if chave in self.TELAS else "CHAMFER_OD"

    def linhas_faixa(self):
        modo = ("mode", u"MODO", "combo", MODOS, "")
        lado = ("side", u"LADO", "combo", LADOS, "")
        return [(u"CONFIG.", celulas_config(modo, lado)),
                (u"CORTE", celulas_corte())]

    def _pos_collect(self, params):
        # Arco do modo RAIO com geometria exata (senao o LinuxCNC recusa:
        # "Radius to end of arc differs from radius to start").
        params["fixArcOvercut"] = True
        # o engine usa chamferLength so como rotulo; mantem coerente com o Z
        params["chamferLength"] = abs(params.get("zEnd", 0) - params.get("zStart", 0))
