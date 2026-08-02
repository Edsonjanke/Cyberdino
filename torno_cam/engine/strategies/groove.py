# -*- coding: utf-8 -*-
"""Port de strategies/GrooveStrategy.ts (canal e corte/sangria).

CANAL: mergulhos individuais em cada posicao Z dentro de cada nivel de
       profundidade, alternando o sentido (esq->dir, dir->esq) entre niveis.
       Acabamento em duas metades — o sangrador so desce, nunca sobe cortando.
CORTE: sangria com bicadas e retorno, com quebra de aresta opcional antes.
"""

import math

from ..nodes import ToolpathBuilder
from ..sfm import calc_spindle_speed
from ..jsutil import round4


def generate_groove(p):
    if p.mode == "PART":
        return _corte(p)
    return _canal(p)


def _compensacao(p):
    """Largura do sangrador a descontar em Z, ou 0 se a compensacao estiver
    desligada.

    A referencia do sangrador (onde o corretor esta zerado) e' a aresta de Z
    MAIS NEGATIVO; o corpo da pastilha se estende `toolWidth` no sentido +Z.
    Entao, para uma parede/face ficar no Z pedido, a ferramenta e' posicionada
    uma largura ANTES: corte em Z-5 com sangrador de 3 -> ferramenta em Z-8.

    Sem isto a peca sai CURTA pela largura da pastilha (e o canal sai mais
    largo que o pedido). O engine do EvoCAM nao faz essa conta — por isso e'
    opcional (`compensarLargura`, que a UI liga) e a paridade continua valendo.
    """
    if not getattr(p, "compensarLargura", False):
        return 0.0
    return abs(getattr(p, "toolWidth", 0.0) or 0.0)


# ── CANAL ────────────────────────────────────────────────────────────────────
def _canal(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    x_sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    target_r = abs(p.finalX) / 2
    clear_r = start_r + p.toolClearance
    z_clear = p.zStart + abs(p.toolClearance)

    def sx(v):
        return round4(v * x_sign)

    largura = abs(p.zEnd - p.zStart)
    z_dir = -1 if p.zEnd < p.zStart else 1

    # Compensacao da largura do sangrador: as PAREDES do canal ficam em
    # z_lo/z_hi; a REFERENCIA da ferramenta varre de z_lo ate z_hi - largura.
    comp = _compensacao(p)
    z_lo = min(p.zStart, p.zEnd)
    z_hi = max(p.zStart, p.zEnd)
    ref_lo = round4(z_lo)                 # parede de z_lo: cortada pela referencia
    ref_hi = round4(z_hi - comp)          # parede de z_hi: cortada pela aresta +Z
    vao = abs(ref_hi - ref_lo)            # quanto a referencia precisa caminhar

    def ref_da_parede(z):
        """Onde por a referencia para a parede sair no Z pedido."""
        return ref_hi if z > z_lo else ref_lo

    passo = min(p.toolWidth * 0.8, largura)
    n_merg = max(1, int(math.ceil(vao / passo))) if vao > 1e-9 else 1
    passo_real = vao / n_merg if n_merg else 0.0

    radial_total = start_r - target_r - abs(p.finishDOC)
    n_prof = (max(1, int(math.ceil(radial_total / p.roughingDOC)))
              if radial_total > 0.0001 else 0)
    doc_prof = round4(radial_total / n_prof) if n_prof > 0 else 0

    folga_retorno = 0.5   # sobe 0.5mm acima do nivel ja cortado

    b.comment(u"CANAL: {}".format(p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset, u"CANAL T{}".format(p.toolNumber))

    spin = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs(p.initialX),
                              max_rpm=p.maxSpindleRPM, metric=is_metric,
                              css_mode=True)
    b.spindleOn(cssMode=True, dir=p.spindleDir, rpm=spin["rpm"], sfm=spin["sfm"],
                maxRPM=p.maxSpindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    b.rapid(x=sx(clear_r * 2), z=round4(z_clear))

    sin45 = math.sqrt(0.5)
    cos45 = math.sqrt(0.5)

    def acabamento():
        fin_x = sx(target_r * 2)
        z_meio = round4((ref_lo + ref_hi) / 2)
        ext = abs(p.toolClearance)
        appr_ext_z = round4(ext * cos45)

        fin = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs(p.finalX),
                                 max_rpm=p.maxSpindleRPM, metric=is_metric,
                                 css_mode=True)
        b.comment("ACABAMENTO CANAL")
        b.spindleSpeed(fin["rpm"], fin["sfm"], True)

        # 1a metade: parede do zStart ate o meio
        ref_ini = ref_da_parede(p.zStart)
        appr_z1 = round4(ref_ini - z_dir * appr_ext_z)
        b.rapid(x=sx(clear_r * 2))
        b.rapid(z=appr_z1)
        b.linear(x=sx(start_r * 2), z=ref_ini, feed=p.finishingFPR)
        b.linear(x=fin_x, z=ref_ini, feed=p.plungeFPR)
        b.linear(x=fin_x, z=z_meio, feed=p.finishingFPR)
        b.rapid(x=sx(clear_r * 2))

        # 2a metade: parede do zEnd ate o meio
        ref_fim = ref_da_parede(p.zEnd)
        appr_z2 = round4(ref_fim + z_dir * appr_ext_z)
        b.rapid(z=appr_z2)
        b.linear(x=sx(start_r * 2), z=ref_fim, feed=p.finishingFPR)
        b.linear(x=fin_x, z=ref_fim, feed=p.plungeFPR)
        b.linear(x=fin_x, z=z_meio, feed=p.finishingFPR)
        b.rapid(x=sx(clear_r * 2))

    if p.useCannedCycle:
        b.comment("G75 CICLO AUTOMATICO DE CANAL")
        b.cannedGrooveCycle(
            retract=p.toolClearance,
            finalX=sx(target_r * 2),
            finalZ=ref_da_parede(p.zEnd),
            peckX=p.roughingDOC,
            stepZ=min(p.toolWidth * 0.8, largura),
            feed=p.plungeFPR,
        )
        if p.finishDOC > 0:
            acabamento()
    else:
        for d in range(n_prof):
            prof_r = round4(start_r - doc_prof * (d + 1))
            ant_r = start_r if d == 0 else round4(start_r - doc_prof * d)
            prof_x = sx(prof_r * 2)
            esq_para_dir = (d % 2 == 0)

            retorno_r = clear_r if d == 0 else round4(ant_r + folga_retorno)
            retorno_x = sx(retorno_r * 2)

            # a referencia caminha entre ref_lo e ref_hi (ja compensados)
            ini = ref_hi if z_dir < 0 else ref_lo
            posicoes = [round4(ini - z_dir * passo_real * pl * -1)
                        for pl in range(n_merg + 1)]
            posicoes = [max(ref_lo, min(ref_hi, z)) for z in posicoes]
            if not esq_para_dir:
                posicoes.reverse()

            for pl_z in posicoes:
                b.rapid(x=retorno_x)
                b.rapid(z=round4(pl_z))
                b.linear(x=prof_x, z=round4(pl_z), feed=p.plungeFPR)

        if p.finishDOC > 0:
            acabamento()

    b.coolantOff()
    b.rapid(x=sx(clear_r * 2), z=round4(z_clear))
    return b.build()


# ── CORTE (sangria) ──────────────────────────────────────────────────────────
def _corte(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    x_sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    target_r = abs(p.finalX) / 2
    clear_r = start_r + p.toolClearance
    # a face da peca fica em zStart; a referencia vai uma largura antes
    z_corte = round4(p.zStart - _compensacao(p))

    def sx(v):
        return round4(v * x_sign)

    tem_quebra = p.edgeBreak > 0

    prof_total = start_r - target_r
    bicada = p.peck if p.peck > 0 else prof_total
    n_bicadas = max(1, int(math.ceil(prof_total / bicada)))
    bicada_real = round4(prof_total / n_bicadas)

    b.comment(u"CORTE: {}".format(p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset, u"CORTE T{}".format(p.toolNumber))

    spin = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs(p.initialX),
                              max_rpm=p.maxSpindleRPM, metric=is_metric,
                              css_mode=True)
    b.spindleOn(cssMode=True, dir=p.spindleDir, rpm=spin["rpm"], sfm=spin["sfm"],
                maxRPM=p.maxSpindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    b.rapid(x=sx(clear_r * 2), z=round4(z_corte + abs(p.toolClearance)))

    if tem_quebra:
        b.comment("QUEBRA DE ARESTA")
        b.rapid(x=sx(start_r * 2), z=round4(z_corte))
        b.linear(x=sx((start_r - p.edgeBreak) * 2),
                 z=round4(z_corte - p.edgeBreak), feed=p.plungeFPR)
        b.rapid(x=sx(clear_r * 2), z=round4(z_corte - p.edgeBreak))
        b.rapid(x=sx(clear_r * 2), z=round4(z_corte))

    b.comment("CORTE COM RETORNO")
    atual_r = start_r
    for i in range(n_bicadas):
        bic_r = round4(atual_r - bicada_real)
        bic_x = sx(max(target_r, bic_r) * 2)

        b.rapid(x=sx((atual_r + p.retract) * 2), z=round4(z_corte))
        if i > 0:
            b.rapid(x=sx((atual_r + 0.5) * 2), z=round4(z_corte))
        b.linear(x=bic_x, z=round4(z_corte), feed=p.plungeFPR)
        if i < n_bicadas - 1:
            b.rapid(x=sx((atual_r + p.retract) * 2), z=round4(z_corte))

        atual_r = max(target_r, bic_r)

    b.rapid(x=sx(clear_r * 2), z=round4(z_corte))
    b.coolantOff()
    b.rapid(x=sx(clear_r * 2), z=round4(z_corte + abs(p.toolClearance)))
    return b.build()
