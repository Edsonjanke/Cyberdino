# -*- coding: utf-8 -*-
"""DESBASTE INT, telas 03 (basico) e 04 (avancado) do padrao novo
(handoff telas de ciclo, 2026-11-01). E' a tela que definiu o padrao.

Trocar o MODO troca o desenho e o conjunto de campos; os valores ficam nos
widgets e sobrevivem a troca. CHANFRO e' campo novo, na boca do furo
(secao 7.1 b do handoff)."""

from .ciclo_form import (CicloForm, celulas_config, celulas_corte,
                         DICA_SO_ACABAMENTO)

MODOS = [(u"BÁSICO", "BASIC"), (u"AVANÇADO", "EXTENDED")]

DICA_CICLO = (u"Desbaste com o ciclo G71 do LinuxCNC (perfil numa sub). "
              u"O acabamento sai linha a linha.")
DICA_SEM_CICLO = u"No modo AVANÇADO não há ciclo: o desbaste sai linha a linha."


class IDForm(CicloForm):
    TELAS = {"BASIC": "03-desbaste-int", "EXTENDED": "04-desbaste-int-avancado"}
    OPERACAO = "ID_TURN"
    CHAVES_DE_TELA = ("mode",)
    CAMPOS = {
        "ferramenta":        ("toolNumber",    dict(integer=True, minimum=1)),
        "z_inicio":          ("zStart",        {}),
        "z_fim":             ("zEnd",          {}),
        "chanfro":           ("chamferSize",   dict(minimum=0.0)),
        "x_final":           ("finalX",        {}),
        "x_inicial":         ("initialX",      {}),
        "prof_desbaste":     ("idRoughDOC",    dict(minimum=0.001)),
        "prof_desb_interno": ("idRoughDOC",    dict(minimum=0.001)),
        "prof_acabamento":   ("finishDOC",     dict(minimum=0.0)),
        "afastamento_g0":    ("toolClearance", dict(minimum=0.0)),
        # so no avancado
        "raio_de_canto":     ("filletRadius",  dict(minimum=0.0)),
        "fim_do_piloto":     ("pilotEnd",      {}),
        "prof_desb_da_face": ("faceRoughDOC",  dict(minimum=0.0)),
    }
    LIGADAS = {"finishOnly": DICA_SO_ACABAMENTO, "useCannedCycle": DICA_CICLO}

    def _opcoes_da_tela(self):
        # o G71 so existe no modo BASICO
        if self._chave_tela() == "EXTENDED":
            self._faixa.desligar("useCannedCycle", DICA_SEM_CICLO)
        else:
            self._faixa.ligar("useCannedCycle", DICA_CICLO)

    def _pos_collect(self, params):
        # SOMENTE ACABAMENTO tambem linha a linha e G71 no formato do
        # LinuxCNC 2.9 (so desbaste)
        params["finishOnlyManual"] = True
        params["cicloLinuxCNC"] = True
        # Vc em m/min com limite de RPM: G96 D<RPM MAXIMA> S<Vc>
        params["useConstantSurface"] = True

    def _chave_tela(self):
        m = self.params.get("mode", "BASIC")
        return m if m in self.TELAS else "BASIC"

    def linhas_faixa(self):
        modo = ("mode", u"MODO", "combo", MODOS, "")
        return [(u"CONFIG.", celulas_config(modo)),
                (u"CORTE", celulas_corte())]
