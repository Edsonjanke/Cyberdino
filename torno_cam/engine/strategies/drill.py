# -*- coding: utf-8 -*-
"""Port de strategies/DrillStrategy.ts (furacao)."""

from ..nodes import ToolpathBuilder
from ..sfm import calc_spindle_speed
from ..jsutil import round4, js_round, js_num


def _auto_cycle_code(depth, diameter):
    return "G83" if abs(depth) > 3 * diameter else "G81"


def _cycle_code(p, total_depth):
    """Escolhe G81 (direto) ou G83 (bicada).

    Regra do app: G83 so acima de 3x o diametro. Isso IGNORA o campo PASSO
    (Q) nos dois sentidos — em furo raso o operador digita bicada e a maquina
    fura de uma vez so; em furo fundo ele digita ZERO e a maquina bica assim
    mesmo, com o passo igual ao diametro.

    Com `forcePeckCycle` (a UI liga) quem manda e' o que esta digitado:
      Q = 0            -> G81, fura direto (pedido do operador)
      0 < Q < profund. -> G83, bica no passo digitado
      Q >= profundidade -> G81, uma bicada so' ja passa do fundo

    O flag e opcional de proposito: os goldens gerados pelo engine TS nao o
    tem, entao a paridade byte-a-byte continua valendo."""
    if getattr(p, "forcePeckCycle", False):
        peck = getattr(p, "peckDepth", 0) or 0
        if peck <= 0:
            return "G81"
        return "G83" if peck < abs(total_depth) else "G81"
    return _auto_cycle_code(total_depth, p.drillDiameter)


def generate_drill(p):
    b = ToolpathBuilder()

    b.comment(u"FURACAO: {} Ø{}".format(p.title, js_num(p.drillDiameter)))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset, u"BROCA Ø{}".format(js_num(p.drillDiameter)))

    spindle = calc_spindle_speed(sfm=p.roughingSFM, diameter=p.drillDiameter,
                                 max_rpm=p.maxSpindleRPM,
                                 metric=(p.unitSystem == "metric"), css_mode=False)
    b.spindleOn(cssMode=False, dir=p.spindleDir, rpm=spindle["rpm"])
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    approach_z = round4(p.zStart + p.toolClearance)
    depth = round4(p.zEnd)
    feed = p.roughingFPR
    total_depth = abs(p.zEnd - p.zStart)

    b.rapid(x=0, z=approach_z)

    if p.useCannedCycle:
        cycle_code = _cycle_code(p, total_depth)
        if cycle_code == "G83":
            peck = p.peckDepth if p.peckDepth > 0 else p.drillDiameter
            b.comment("CICLO G83 - FURO PROFUNDO PECK={}".format(js_num(peck)))
            b.cycle(cycleCode="G83", x=0, z=depth, r=round4(p.zStart), f=feed, q=peck,
                    p=(js_round(p.dwellSeconds * 1000) if p.dwellSeconds > 0 else None))
        else:
            b.comment("CICLO G81 - FURO SIMPLES")
            b.cycle(cycleCode="G81", x=0, z=depth, r=round4(p.zStart), f=feed,
                    p=(js_round(p.dwellSeconds * 1000) if p.dwellSeconds > 0 else None))
    else:
        b.comment("FURACAO MANUAL - LINHA A LINHA")
        if p.peckDepth > 0 and total_depth > p.peckDepth:
            current_z = p.zStart
            peck_step = p.peckDepth
            while round4(current_z) > round4(p.zEnd):
                current_z = max(current_z - peck_step, p.zEnd)
                b.linear(feed=feed, x=0, z=round4(current_z))
                if p.dwellSeconds > 0:
                    b.dwell(p.dwellSeconds)
                b.rapid(x=0, z=approach_z)
        else:
            b.linear(feed=feed, x=0, z=depth)
            if p.dwellSeconds > 0:
                b.dwell(p.dwellSeconds)
            b.rapid(x=0, z=approach_z)

    b.coolantOff()
    b.rapid(x=0, z=approach_z)
    b.spindleOff()
    return b.build()
