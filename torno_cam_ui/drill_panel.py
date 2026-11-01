# -*- coding: utf-8 -*-
"""FURAR, tela 05 do padrao novo (handoff telas de ciclo, 2026-11-01).

RPM, avanco e bicada saem da tabela de furacao (torno_cam/engine/furacao.py)
ao trocar o MATERIAL ou o diametro da broca; o operador pode sobrescrever.
GERAR CICLO esta liberado: o dialeto LinuxCNCDinoPost corrige plano (G17),
unidade da pausa (segundos) e usa G82 quando ha pausa."""

from torno_cam.engine import furacao

from .ciclo_form import CicloForm, celulas_config

# nomes com acento so' na tela (o engine guarda a chave: ACO, INOX, ALUMINIO)
NOME_MATERIAL = {"ACO": u"AÇO 1045", "INOX": u"INOX 304", "ALUMINIO": u"ALUMÍNIO"}

DICA_CICLO = (u"Gera ciclo fixo G81/G82/G83 (com G17 no lugar de G18, "
              u"como o LinuxCNC exige para furar em Z).")


class DrillForm(CicloForm):
    TELAS = {"DRILL": "05-furar"}
    OPERACAO = "DRILL"
    CAMPOS = {
        "ferramenta":       ("toolNumber",    dict(integer=True, minimum=1)),
        "z_inicial":        ("zStart",        {}),
        "afastamento_g0":   ("toolClearance", dict(minimum=0.0)),
        "passo_q":          ("peckDepth",     dict(minimum=0.0)),
        "rotacao_rpm":      ("roughingSFM",   dict(integer=True, minimum=1)),
        "da_broca":         ("drillDiameter", dict(minimum=0.001)),
        "tempo_espera_seg": ("dwellSeconds",  dict(minimum=0.0)),
        "z_final":          ("zEnd",          {}),
    }
    LIGADAS = {"useCannedCycle": DICA_CICLO}

    def linhas_faixa(self):
        materiais = [(NOME_MATERIAL.get(k, furacao.MATERIAIS[k]["nome"]), k)
                     for k in furacao.ORDEM]
        material = ("material", u"MATERIAL", "combo", materiais, "")
        corte = [
            ("maxSpindleRPM", u"RPM MÁXIMA", "int", dict(step=50),               "RPM"),
            ("roughingFPR",   u"AVANÇO",     "num", dict(decimals=3, step=0.01), "MM/V"),
        ]
        return [(u"CONFIG.", celulas_config(material)),
                (u"CORTE", corte)]

    def _ao_editar(self, chave):
        if chave == "drillDiameter":
            self._aplicar_tabela()
        else:
            self._on_changed()

    def _ao_mudar_extra(self, chave):
        if chave == "material":
            self._aplicar_tabela()
        else:
            super(DrillForm, self)._ao_mudar_extra(chave)

    def _aplicar_tabela(self, *_a):
        """Preenche RPM, avanco e bicada a partir do material + diametro da
        broca. A tabela e' ponto de partida, nao trava."""
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

    def _pos_collect(self, params):
        # o campo do desenho e RPM (nao Vc): o engine usa roughingSFM como
        # rotacao quando css_mode=False, entao o valor vai direto.
        params["finishingSFM"] = params.get("roughingSFM")
        # A bicada digitada vale: sem isso o app so usaria G83 acima de 3x o
        # diametro e um furo raso sairia direto, ignorando o PASSO (Q).
        params["forcePeckCycle"] = True
