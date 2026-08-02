# -*- coding: utf-8 -*-
"""Port de strategies/IDTurnStrategy.ts (desbaste interno / mandrilamento).

Trabalha internamente em raio; emite em diametro (X = 2r). Suporta X negativo.

Dois modos:
- BASICO   : passes longitudinais alargando o furo + passe de acabamento.
- AVANCADO : desbaste longitudinal ate o pilot end, depois faceamento interno,
             e no acabamento parede -> arco do filete -> face.

Convencao do ID: initialX = furo de partida (menor), finalX = furo final
(maior). Os passes AUMENTAM o diametro.
"""

import math
from dataclasses import dataclass
from typing import List

from ..nodes import ToolpathBuilder, Linear
from ..sfm import calc_spindle_speed
from ..jsutil import round4, js_round


@dataclass
class IDTurnResult:
    nodes: List[object]
    numRoughPasses: int
    actualDOC: float
    estimatedCycleTimeSec: int


def _nullish(valor, alternativa):
    """Equivalente ao `??` do TS: so cai na alternativa se for None.
    ATENCAO: zero NAO e' nullish — pilotEnd=0 continua 0 (o default do app)."""
    return alternativa if valor is None else valor


def generate_id_turn(p):
    if getattr(p, "mode", "BASIC") == "EXTENDED":
        return _id_turn_avancado(p)
    return _id_turn_basico(p)


# ══════════════════════════════════════════════════════════════════════════════
# MODO BASICO
# ══════════════════════════════════════════════════════════════════════════════
def _id_turn_basico(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    x_sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    target_r = abs(p.finalX) / 2
    finish_r = target_r - p.finishDOC
    z_clear = p.zStart + abs(p.toolClearance)

    def sx(v):
        return round4(v * x_sign)

    total_rough = round4(finish_r - start_r)
    tem_desbaste = total_rough > 0.0001

    num_passes = 0
    doc_real = 0
    if tem_desbaste:
        num_passes = max(1, int(math.ceil(total_rough / p.idRoughDOC)))
        doc_real = round4(total_rough / num_passes)

    b.comment(u"DESBASTE INT: {}".format(p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset,
               u"DESBASTE INT T{}".format(p.toolNumber))

    rough = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs(p.initialX),
                               max_rpm=p.maxSpindleRPM, metric=is_metric,
                               css_mode=False)
    b.spindleOn(cssMode=False, dir=p.spindleDir, rpm=rough["rpm"],
                sfm=rough["sfm"], maxRPM=p.maxSpindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    if p.useCannedCycle and not p.finishOnly:
        b.comment("G71 CICLO AUTOMATICO DE DESBASTE INTERNO")
        b.rapid(x=sx((start_r - p.toolClearance) * 2), z=round4(z_clear))
        profile = [
            Linear(x=sx(target_r * 2), feed=p.finishingFPR),
            Linear(z=round4(p.zEnd), feed=p.finishingFPR),
        ]
        b.cannedRoughCycle(
            depthOfCut=p.idRoughDOC,
            retract=p.toolClearance,
            finishStockX=round4(-p.finishDOC * 2),   # negativo: furo cresce
            finishStockZ=round4(p.finishDOC),
            roughFeed=p.roughingFPR,
            finishFeed=p.finishingFPR,
            profile=profile,
            generateFinish=True,
        )
    else:
        b.rapid(x=sx(start_r * 2), z=round4(z_clear))

        atual_r = start_r
        for _i in range(num_passes):
            passe_r = round4(atual_r + doc_real)
            passe_x = sx(passe_r * 2)
            recuo_r = passe_r - p.toolClearance

            b.rapid(x=passe_x, z=round4(z_clear))
            b.linear(x=passe_x, z=round4(p.zEnd), feed=p.roughingFPR)
            b.rapid(x=sx(recuo_r * 2), z=round4(p.zEnd))
            b.rapid(x=sx(recuo_r * 2), z=round4(z_clear))

            atual_r = passe_r

        if p.finishDOC > 0:
            fin = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs(p.finalX),
                                     max_rpm=p.maxSpindleRPM, metric=is_metric,
                                     css_mode=False)
            b.comment("PASSE DE ACABAMENTO")
            b.spindleSpeed(fin["rpm"], fin["sfm"], False)

            fin_x = sx(target_r * 2)
            b.rapid(x=sx((target_r - p.toolClearance) * 2), z=round4(z_clear))
            b.linear(x=fin_x, z=round4(z_clear), feed=p.finishingFPR)
            b.linear(x=fin_x, z=round4(p.zEnd), feed=p.finishingFPR)
            b.linear(x=sx((target_r - p.toolClearance) * 2), z=round4(p.zEnd),
                     feed=p.finishingFPR)

    b.coolantOff()
    b.rapid(x=sx(start_r * 2), z=round4(z_clear))

    return IDTurnResult(nodes=b.build(), numRoughPasses=num_passes,
                        actualDOC=doc_real,
                        estimatedCycleTimeSec=_tempo(p, num_passes, is_metric))


# ══════════════════════════════════════════════════════════════════════════════
# MODO AVANCADO — desbaste ID + faceamento interno + raio de filete
# ══════════════════════════════════════════════════════════════════════════════
def _id_turn_avancado(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    x_sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    target_r = abs(p.finalX) / 2
    R = p.filletRadius
    z_clear = p.zStart + abs(p.toolClearance)

    def sx(v):
        return round4(v * x_sign)

    # centro do arco do filete (onde a parede do furo encontra a face)
    arc_cx = target_r - R
    arc_cz = p.zEnd + R

    b.comment(u"DESBASTE INT AVANÇADO: {}".format(p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset,
               u"DESBASTE INT T{}".format(p.toolNumber))

    rough = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs(p.initialX),
                               max_rpm=p.maxSpindleRPM, metric=is_metric,
                               css_mode=False)
    b.spindleOn(cssMode=False, dir=p.spindleDir, rpm=rough["rpm"],
                sfm=rough["sfm"], maxRPM=p.maxSpindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    finish_r = target_r - p.finishDOC
    total_id = round4(finish_r - start_r)
    num_id = 0
    doc_id = 0
    if total_id > 0.0001:
        num_id = max(1, int(math.ceil(total_id / p.idRoughDOC)))
        doc_id = round4(total_id / num_id)

    safe_r = (R - p.finishDOC * 2) if R > 0 else 0
    pilot_end = _nullish(getattr(p, "pilotEnd", None), p.zEnd)
    rough_z_end = round4(pilot_end)

    b.comment("--- Desbaste ID (passes longitudinais) ---")
    b.rapid(x=sx(start_r * 2), z=round4(z_clear))

    atual_r = start_r
    for _i in range(num_id):
        passe_r = round4(atual_r + doc_id)
        passe_x = sx(passe_r * 2)

        # encurta o passe na zona do filete (escada), nunca passa do rough_z_end
        passe_z_end = rough_z_end
        if R > 0 and passe_r >= arc_cx:
            dx = passe_r - arc_cx
            d_sq = safe_r * safe_r - dx * dx
            if d_sq > 0:
                z_inter = round4(arc_cz - math.sqrt(d_sq))
                if z_inter > rough_z_end:
                    passe_z_end = z_inter
            else:
                d_sq_real = R * R - dx * dx
                if d_sq_real > 0:
                    passe_z_end = round4(arc_cz - math.sqrt(d_sq_real)
                                         + p.finishDOC * 2)
                else:
                    passe_z_end = round4(arc_cz)
            if passe_z_end < rough_z_end:
                passe_z_end = rough_z_end

        recuo_r = passe_r - p.toolClearance

        b.rapid(x=passe_x, z=round4(z_clear))
        b.linear(x=passe_x, z=passe_z_end, feed=p.roughingFPR)
        b.rapid(x=sx(recuo_r * 2), z=passe_z_end)
        b.rapid(x=sx(recuo_r * 2), z=round4(z_clear))

        atual_r = passe_r

    # ── faceamento interno ────────────────────────────────────────────────
    face_doc = _nullish(getattr(p, "faceRoughDOC", None), p.idRoughDOC)
    face_z_ini = round4(pilot_end)
    face_z_fim = round4(p.zEnd + p.finishDOC * 2)
    total_face = abs(face_z_ini - face_z_fim)

    if total_face > 0.0001 and face_doc > 0:
        b.comment("--- Faceamento interno ---")
        num_face = max(1, int(math.ceil(total_face / face_doc)))
        doc_face = round4(total_face / num_face)

        face_x_base = round4(target_r - p.finishDOC * 2)
        face_x_fim = round4(start_r)
        safe_r_face = R - p.finishDOC * 2

        for i in range(num_face):
            passe_z = round4(face_z_ini - (i + 1) * doc_face)

            face_x_ini = face_x_base
            if R > 0:
                dz = arc_cz - passe_z
                d_sq_face = safe_r_face * safe_r_face - dz * dz
                if d_sq_face > 0:
                    x_lim = round4(arc_cx + math.sqrt(d_sq_face))
                    if x_lim < face_x_ini:
                        face_x_ini = x_lim
                elif dz > safe_r_face:
                    d_sq_real = R * R - dz * dz
                    if d_sq_real > 0:
                        x_lim = round4(arc_cx + math.sqrt(d_sq_real)
                                       - p.finishDOC * 2)
                        if x_lim < face_x_ini:
                            face_x_ini = x_lim

            recuo_z = round4(passe_z + p.toolClearance)

            b.rapid(x=sx(face_x_ini * 2), z=recuo_z)
            b.linear(x=sx(face_x_ini * 2), z=passe_z, feed=p.roughingFPR)
            b.linear(x=sx(face_x_fim * 2), z=passe_z, feed=p.roughingFPR)
            b.rapid(x=sx(face_x_fim * 2), z=recuo_z)

        b.rapid(x=sx(face_x_fim * 2), z=round4(z_clear))

    # ── acabamento ────────────────────────────────────────────────────────
    if p.finishDOC > 0:
        fin = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs(p.finalX),
                                 max_rpm=p.maxSpindleRPM, metric=is_metric,
                                 css_mode=False)
        b.comment("PASSE DE ACABAMENTO")
        b.spindleSpeed(fin["rpm"], fin["sfm"], False)

        fin_x = sx(target_r * 2)
        b.rapid(x=sx((target_r - p.toolClearance) * 2), z=round4(z_clear))
        b.linear(x=fin_x, z=round4(z_clear), feed=p.finishingFPR)

        if R > 0:
            b.linear(x=fin_x, z=round4(p.zEnd + R), feed=p.finishingFPR)
            arc_i = round4((arc_cx - target_r) * x_sign)
            b.arc(x=sx(arc_cx * 2), z=round4(p.zEnd), i=arc_i, k=0,
                  feed=p.finishingFPR, dir="CCW" if x_sign > 0 else "CW")
            if pilot_end < p.zEnd:
                b.linear(x=sx(arc_cx * 2), z=round4(pilot_end),
                         feed=p.finishingFPR)
        else:
            b.linear(x=fin_x, z=round4(p.zEnd), feed=p.finishingFPR)

        b.linear(x=sx(start_r * 2), z=round4(p.zEnd), feed=p.finishingFPR)

    b.coolantOff()
    b.rapid(x=sx(start_r * 2), z=round4(z_clear))

    return IDTurnResult(nodes=b.build(), numRoughPasses=num_id,
                        actualDOC=doc_id,
                        estimatedCycleTimeSec=_tempo(p, num_id, is_metric))


def _tempo(p, num_passes, is_metric):
    comprimento = abs(p.zEnd - p.zStart)
    dia_medio = (abs(p.initialX) + abs(p.finalX)) / 2
    rpm = calc_spindle_speed(sfm=p.roughingSFM, diameter=dia_medio,
                             max_rpm=p.maxSpindleRPM, metric=is_metric,
                             css_mode=False)["rpm"]
    avanco = p.roughingFPR * rpm
    seg = (comprimento * num_passes / avanco) * 60 if avanco > 0 else 0
    return js_round(seg)
