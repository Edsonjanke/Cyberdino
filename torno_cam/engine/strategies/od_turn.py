# -*- coding: utf-8 -*-
"""Port de strategies/ODTurnStrategy.ts (desbaste externo).

Trabalha internamente em raio; emite em diametro (X = 2r). Suporta X negativo.
Retorna ODTurnResult (nodes + metadados de passes)."""

import math
from dataclasses import dataclass
from typing import List

from ..nodes import ToolpathBuilder, Linear, Arc
from ..sfm import calc_spindle_speed
from ..jsutil import round4, js_round, js_num
from . import chanfro, fim


@dataclass
class ODTurnResult:
    nodes: List[object]
    numRoughPasses: int
    actualDOC: float
    estimatedCycleTimeSec: int


def generate_od_turn(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    x_sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    target_r = abs(p.finalX) / 2
    finish_r = target_r + p.finishDOC
    clear_r = start_r + p.toolClearance
    z_clear = p.zStart + abs(p.toolClearance)

    def sx(v):
        return round4(v * x_sign)

    abs_dia_initial = abs(p.initialX)
    abs_dia_final = abs(p.finalX)

    total_rough_depth = round4(start_r - finish_r)
    has_rough_passes = total_rough_depth > 0.0001 and not p.finishOnly

    num_passes = 0
    actual_doc = 0
    if has_rough_passes:
        num_passes = max(1, math.ceil(total_rough_depth / p.roughingDOC))
        actual_doc = round4(total_rough_depth / num_passes)

    b.comment("DESBASTE EXT: {}".format(p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset, "DESBASTE EXT T{}".format(js_num(p.toolNumber)))

    if p.finishOnly:
        fin_spindle = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs_dia_final,
                                         max_rpm=p.maxSpindleRPM, metric=is_metric,
                                         css_mode=p.useConstantSurface)
        if p.useConstantSurface:
            b.comment("G50 S{}".format(js_num(p.maxSpindleRPM)))
        b.spindleOn(cssMode=fin_spindle["cssMode"], dir=p.spindleDir,
                    rpm=fin_spindle["rpm"], sfm=fin_spindle["sfm"], maxRPM=p.maxSpindleRPM)
    else:
        rough_spindle = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs_dia_initial,
                                           max_rpm=p.maxSpindleRPM, metric=is_metric,
                                           css_mode=p.useConstantSurface)
        if p.useConstantSurface:
            b.comment("G50 S{}".format(js_num(p.maxSpindleRPM)))
        b.spindleOn(cssMode=rough_spindle["cssMode"], dir=p.spindleDir,
                    rpm=rough_spindle["rpm"], sfm=rough_spindle["sfm"],
                    maxRPM=p.maxSpindleRPM)

    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    R = p.filletRadius

    # chanfros de entrada (ponta do X FINAL) e de saida (ressalto no X
    # INICIAL), handoff 7.1 c. zd = sentido do corte em Z (-1 no normal).
    c_ent = chanfro.tamanho(p, "chamferEntry")
    c_sai = chanfro.tamanho(p, "chamferExit")
    zd = -1 if p.zEnd < p.zStart else 1
    raio_pe = R if R > 0 else 0.0
    if c_ent > 0:
        if c_ent > target_r + 1e-9:
            chanfro.nao_cabe(u"O chanfro de entrada", c_ent, u"o raio do X FINAL", target_r)
        if c_ent + raio_pe > abs(p.zStart - p.zEnd) + 1e-9:
            chanfro.nao_cabe(u"O chanfro de entrada", c_ent, u"o comprimento em Z",
                             abs(p.zStart - p.zEnd) - raio_pe)
    if c_sai > 0 and c_sai + raio_pe > start_r - target_r + 1e-9:
        chanfro.nao_cabe(u"O chanfro de saída", c_sai, u"o ressalto",
                         start_r - target_r - raio_pe)

    # cicloLinuxCNC (a UI liga): o G71 do LinuxCNC 2.9 faz so o desbaste, com
    # o perfil numa sub; o acabamento continua linha a linha. Sem a flag
    # (goldens do EvoCAM) fica como era.
    ciclo_lcnc = getattr(p, "cicloLinuxCNC", False)

    def perfil():
        profile = [Linear(x=sx(target_r * 2), feed=p.finishingFPR)]
        if R > 0:
            z_travel = abs(p.zStart - p.zEnd)
            if R >= z_travel:
                profile.append(Linear(z=round4(p.zEnd), feed=p.finishingFPR))
            else:
                fillet_z_start = round4(p.zEnd + R)
                profile.append(Linear(z=fillet_z_start, feed=p.finishingFPR))
                profile.append(Arc(x=sx((target_r + R) * 2), z=round4(p.zEnd),
                                   i=R * x_sign, k=0, feed=p.finishingFPR,
                                   dir="CW" if x_sign > 0 else "CCW"))
        else:
            profile.append(Linear(z=round4(p.zEnd), feed=p.finishingFPR))
        return profile

    if p.useCannedCycle and not p.finishOnly and not ciclo_lcnc:
        b.comment("G71 CICLO AUTOMATICO DE DESBASTE")
        b.rapid(x=sx(clear_r * 2), z=round4(z_clear))

        profile = perfil()

        b.cannedRoughCycle(
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
        if not p.finishOnly:
            b.rapid(x=sx(clear_r * 2), z=round4(z_clear))

        if p.useCannedCycle and not p.finishOnly:
            # ponto inicial do G71: no diametro bruto, acima da face
            b.comment("G71 DESBASTE, CICLO DO LINUXCNC")
            b.rapid(x=sx(start_r * 2), z=round4(z_clear))
            b.cannedRoughCycle(
                cycleCode="G71",
                depthOfCut=p.roughingDOC,
                retract=p.toolClearance,
                finishStockX=round4(p.finishDOC * 2),
                finishStockZ=round4(p.finishDOC),
                roughFeed=p.roughingFPR,
                finishFeed=p.finishingFPR,
                profile=perfil(),
                generateFinish=False,
            )
            # o ciclo termina no diametro bruto, no pe do ressalto: sai em X
            # e depois em Z
            b.rapid(x=sx(clear_r * 2))
            b.rapid(z=round4(z_clear))
            num_passes = 0

        arc_cx = target_r + R
        arc_cz = p.zEnd + R
        safe_r = R - p.finishDOC * 2
        rough_z_end = round4(p.zEnd + p.finishDOC)

        current_r = start_r
        for _i in range(num_passes):
            pass_r = round4(current_r - actual_doc)
            pass_x = sx(pass_r * 2)

            pass_z_end = rough_z_end
            if R > 0 and pass_r <= arc_cx:
                dx = pass_r - arc_cx
                d_sq = safe_r * safe_r - dx * dx
                if d_sq > 0:
                    z_intersect = round4(arc_cz - math.sqrt(d_sq))
                    if z_intersect > rough_z_end:
                        pass_z_end = z_intersect
                else:
                    d_sq_real = R * R - dx * dx
                    if d_sq_real > 0:
                        pass_z_end = round4(arc_cz - math.sqrt(d_sq_real) + p.finishDOC * 2)
                    else:
                        pass_z_end = round4(arc_cz)

            b.rapid(x=sx((pass_r + p.toolClearance) * 2), z=round4(z_clear))
            b.linear(feed=p.roughingFPR, x=pass_x, z=round4(z_clear))
            b.linear(feed=p.roughingFPR, x=pass_x, z=pass_z_end)
            retract_r = pass_r + p.toolClearance
            b.rapid(x=sx(retract_r * 2), z=pass_z_end)
            b.rapid(x=sx(retract_r * 2), z=round4(z_clear))
            current_r = pass_r

        if p.finishOnly or p.finishDOC > 0 or c_ent > 0 or c_sai > 0:
            b.comment("PASSE DE ACABAMENTO")
            if not p.finishOnly:
                fin_spindle = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs_dia_final,
                                                 max_rpm=p.maxSpindleRPM, metric=is_metric,
                                                 css_mode=p.useConstantSurface)
                b.spindleSpeed(fin_spindle["rpm"], fin_spindle["sfm"], fin_spindle["cssMode"])

            if c_ent > 0:
                # chega pela linha do chanfro: X = D - 2C - 2e, Z = face + e
                x_fora = sx((target_r - c_ent - chanfro.FOLGA) * 2)
                b.rapid(x=x_fora, z=round4(z_clear))
                b.linear(feed=p.finishingFPR, x=x_fora,
                         z=round4(p.zStart - zd * chanfro.FOLGA))
                b.linear(feed=p.finishingFPR, x=sx(target_r * 2),
                         z=round4(p.zStart + zd * c_ent),
                         comment=chanfro.comentario(c_ent, u"ENTRADA"))
            else:
                b.rapid(x=sx((target_r + p.toolClearance) * 2), z=round4(z_clear))
                b.linear(feed=p.finishingFPR, x=sx(target_r * 2), z=round4(z_clear))

            if p.filletRadius > 0:
                z_travel = abs(p.zStart - p.zEnd)
                if R >= z_travel:
                    b.comment(u"RAIO R{} EXCEDE CURSO Z {} — IGNORADO".format(
                        js_num(R), js_num(round4(z_travel))))
                    b.linear(feed=p.finishingFPR, x=sx(target_r * 2), z=round4(p.zEnd))
                else:
                    fillet_z_start = round4(p.zEnd + R)
                    b.linear(feed=p.finishingFPR, x=sx(target_r * 2), z=fillet_z_start)
                    b.arc(x=sx((target_r + R) * 2), z=round4(p.zEnd), i=R * x_sign, k=0,
                          feed=p.finishingFPR, dir="CW" if x_sign > 0 else "CCW")
            else:
                b.linear(feed=p.finishingFPR, x=sx(target_r * 2), z=round4(p.zEnd))

            if c_sai > 0:
                # sobe a face do ressalto ate o inicio do chanfro e sai a 45
                z_sai = round4(p.zEnd + zd * c_sai)
                b.linear(feed=p.finishingFPR, x=sx((start_r - c_sai) * 2), z=round4(p.zEnd))
                b.linear(feed=p.finishingFPR, x=sx(start_r * 2), z=z_sai,
                         comment=chanfro.comentario(c_sai, u"SAIDA"))
                # afasta 1 mm no raio, como no fim do passe sem chanfro
                b.linear(feed=p.finishingFPR, x=sx((start_r + 1) * 2), z=z_sai)
            else:
                b.linear(feed=p.finishingFPR, x=sx((start_r + 1) * 2), z=round4(p.zEnd))

    b.coolantOff()
    b.rapid(x=sx(clear_r * 2), z=round4(z_clear))
    fim.aplicar(b, p)

    nodes = b.build()

    cut_length = abs(p.zEnd - p.zStart)
    avg_dia = (abs_dia_initial + abs_dia_final) / 2
    avg_rpm = calc_spindle_speed(sfm=p.roughingSFM, diameter=avg_dia,
                                 max_rpm=p.maxSpindleRPM, metric=is_metric,
                                 css_mode=p.useConstantSurface)["rpm"]
    feed_ipm = p.roughingFPR * avg_rpm
    rough_time_sec = (cut_length * num_passes / feed_ipm) * 60 if feed_ipm > 0 else 0

    return ODTurnResult(
        nodes=nodes,
        numRoughPasses=num_passes,
        actualDOC=actual_doc,
        estimatedCycleTimeSec=js_round(rough_time_sec),
    )
