"""Port de strategies/FaceStrategy.ts (faceamento)."""

import math

from ..nodes import ToolpathBuilder
from ..sfm import calc_spindle_speed
from ..jsutil import round4, js_num
from . import chanfro, fim


def generate_face(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    # X FINAL com sinal contrario ao X INICIAL passa do centro (X50 -> X-1):
    # o raio final fica negativo no lado da ferramenta. Antes o abs()
    # espelhava e o passe parava em X1.
    end_r = p.finalX * sign / 2
    clear_r = start_r + p.toolClearance

    def sx(v):
        return round4(v * sign)

    z_dir = 1 if p.zEnd >= p.zStart else -1

    total_axial = abs(p.zEnd - p.zStart)
    finish_stock = abs(p.finishDOC)
    rough_stock = max(0, total_axial - finish_stock)
    num_passes = max(1, math.ceil(rough_stock / p.roughingDOC)) if rough_stock > 0.0001 else 0
    axi_doc = round4(rough_stock / num_passes) if num_passes > 0 else 0

    # chanfro no canto entre o X INICIAL e a face (handoff 7.1 a)
    C = chanfro.tamanho(p, "chamferSize")
    if C > 0 and C > start_r - end_r + 1e-9:
        chanfro.nao_cabe(u"O chanfro", C, u"a face", start_r - end_r)

    b.comment("FACEAMENTO: {}".format(p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset, "FACEAMENTO T{}".format(js_num(p.toolNumber)))

    spindle = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs(p.initialX),
                                 max_rpm=p.maxSpindleRPM, metric=is_metric, css_mode=True)
    b.spindleOn(cssMode=True, dir=p.spindleDir, rpm=spindle["rpm"], sfm=spindle["sfm"],
                maxRPM=p.maxSpindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    z_approach = round4(p.zStart - z_dir * abs(p.toolClearance))

    # A UI liga as duas flags; sem elas (goldens do EvoCAM) fica como era:
    # - finishOnlyManual: SOMENTE ACABAMENTO tambem no modo linha a linha
    #   (o app so olhava a opcao no ciclo fixo);
    # - cicloLinuxCNC: o G72 do LinuxCNC 2.9 faz so o desbaste, com o perfil
    #   numa sub; o acabamento continua linha a linha (Vc de acabamento e
    #   chanfro).
    so_acab = p.finishOnly and getattr(p, "finishOnlyManual", False)
    ciclo_lcnc = getattr(p, "cicloLinuxCNC", False)

    def perfil():
        from ..nodes import Linear
        return [Linear(z=round4(p.zEnd), feed=p.finishingFPR),
                Linear(x=sx(end_r * 2), feed=p.finishingFPR)]

    if p.useCannedCycle and not p.finishOnly and not ciclo_lcnc:
        b.comment("G72 CICLO AUTOMATICO DE FACEAMENTO")
        b.rapid(x=sx(clear_r * 2), z=z_approach)
        profile = perfil()
        b.cannedRoughCycle(
            cycleCode="G72",
            depthOfCut=p.roughingDOC,
            retract=p.toolClearance,
            finishStockX=round4(p.finishDOC * 2),
            finishStockZ=round4(p.finishDOC),
            roughFeed=p.roughingFPR,
            finishFeed=p.finishingFPR,
            profile=profile,
            generateFinish=True,
        )
    else:
        b.rapid(x=sx(clear_r * 2), z=z_approach)

        if p.useCannedCycle and not p.finishOnly:
            # ponto inicial do G72: fora da peca em X, na face bruta em Z
            b.comment("G72 DESBASTE, CICLO DO LINUXCNC")
            b.rapid(z=round4(p.zStart))
            b.cannedRoughCycle(
                cycleCode="G72",
                depthOfCut=p.roughingDOC,
                retract=p.toolClearance,
                finishStockX=round4(p.finishDOC * 2),
                finishStockZ=round4(p.finishDOC),
                roughFeed=p.roughingFPR,
                finishFeed=p.finishingFPR,
                profile=perfil(),
                generateFinish=False,
            )
            b.rapid(z=z_approach)       # o ciclo termina no centro, na face bruta
            num_passes = 0
        elif so_acab:
            num_passes = 0

        current_z = p.zStart
        for _i in range(num_passes):
            current_z = round4(current_z + z_dir * axi_doc)
            retract_z = round4(current_z - z_dir * abs(p.toolClearance))
            b.rapid(x=sx(clear_r * 2))
            b.rapid(z=round4(current_z))
            b.linear(feed=p.roughingFPR, x=sx(clear_r * 2), z=round4(current_z))
            b.linear(feed=p.roughingFPR, x=sx(end_r * 2), z=round4(current_z))
            b.rapid(z=retract_z)

        # o chanfro vai no passe de acabamento; sem sobremetal de acabamento,
        # o passe sai so para levar o chanfro
        if finish_stock > 0.0001 or C > 0 or so_acab:
            fin_spin = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs(p.initialX),
                                          max_rpm=p.maxSpindleRPM, metric=is_metric,
                                          css_mode=True)
            b.comment("ACABAMENTO FACEAMENTO")
            b.spindleSpeed(fin_spin["rpm"], fin_spin["sfm"], True)

            fin_retract_z = round4(p.zEnd - z_dir * abs(p.toolClearance))
            b.rapid(x=sx(clear_r * 2))
            if C > 0:
                # chega pela linha do chanfro prolongada FOLGA para fora da
                # peca: Z = face - C - e (lado da peca), X = D + 2e
                z_fora = round4(p.zEnd + z_dir * (C + chanfro.FOLGA))
                b.rapid(z=z_fora)
                b.linear(feed=p.finishingFPR, x=sx((start_r + chanfro.FOLGA) * 2), z=z_fora)
                b.linear(feed=p.finishingFPR, x=sx((start_r - C) * 2), z=round4(p.zEnd),
                         comment=chanfro.comentario(C))
            else:
                b.rapid(z=round4(p.zEnd))
                b.linear(feed=p.finishingFPR, x=sx(clear_r * 2), z=round4(p.zEnd))
            b.linear(feed=p.finishingFPR, x=sx(end_r * 2), z=round4(p.zEnd))
            b.rapid(z=fin_retract_z)

    b.coolantOff()
    b.rapid(x=sx(clear_r * 2))
    b.rapid(z=z_approach)
    fim.aplicar(b, p)
    return b.build()
