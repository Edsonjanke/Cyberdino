# -*- coding: utf-8 -*-
"""Port de strategies/ChamferStrategy.ts (chanfro e raio, OD e ID).

CHANFRO: corte reto (G1) no angulo pedido; cada passe desloca paralelo a
         superficie, por DOC perpendicular.
RAIO   : corte em arco (G2/G3), quarto de circulo; cada passe aumenta o raio.

Nos dois modos a entrada e a saida sao a 45 graus, e os passes vao do mais
profundo (d = sobremetal) ate o contorno final (d = 0).
"""

import math

from ..nodes import ToolpathBuilder
from ..sfm import calc_spindle_speed
from ..jsutil import round4, js_num


def generate_chamfer(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"
    is_od = p.side == "OD"
    is_raio = p.mode == "RADIUS"

    x_sign = -1 if p.x < 0 else 1
    raio = abs(p.x) / 2

    def sx(v):
        return round4(v * x_sign)

    # Angulo: no modo RAIO o quarto de circulo equivale a 45 graus
    ang = math.pi / 4 if is_raio else (p.chamferAngle * math.pi) / 180
    sin_a = math.sin(ang)
    cos_a = math.cos(ang)

    prof_z = abs(p.zEnd - p.zStart)
    prof_r = prof_z if is_raio else round4(prof_z * math.tan(ang))

    alvo_r = round4(raio - prof_r) if is_od else round4(raio + prof_r)
    dir_sign = 1 if is_od else -1

    prof_perp = prof_r * cos_a
    sobremetal = abs(p.finishDOC)
    tem_acab = sobremetal > 0.0001
    n_total = max(1, int(math.ceil(prof_perp / p.roughingDOC)))

    folga = abs(p.toolClearance)
    sin45 = math.sqrt(0.5)     # Math.SQRT1_2
    cos45 = math.sqrt(0.5)

    if is_raio:
        desc = u"RAIO: {} {} R{}".format(p.title, p.side, js_num(prof_z))
    else:
        desc = u"CHANFRO: {} {} {}° x {}".format(
            p.title, p.side, js_num(p.chamferAngle), js_num(prof_z))
    b.comment(desc)
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset,
               u"{} T{}".format(u"RAIO" if is_raio else u"CHANFRO", p.toolNumber))

    spin = calc_spindle_speed(sfm=p.roughingSFM, diameter=abs(p.x),
                              max_rpm=p.maxSpindleRPM, metric=is_metric,
                              css_mode=True)
    b.spindleOn(cssMode=True, dir=p.spindleDir, rpm=spin["rpm"], sfm=spin["sfm"],
                maxRPM=p.maxSpindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    # No modo RAIO o EvoCAM soma o sobrecorte ao raio FINAL do arco sem mover o
    # centro — isso quebra a geometria (raio do inicio != raio do fim) e o
    # LinuxCNC recusa com "Radius to end of arc differs from radius to start".
    # Com `fixArcOvercut` (a UI liga) o arco termina no raio exato; o sobrecorte
    # continua acontecendo no movimento de saida a 45 graus, logo depois.
    # Opcional de proposito: sem o flag o comportamento e' identico ao do app,
    # entao os goldens seguem valendo.
    arco_exato = bool(getattr(p, "fixArcOvercut", False))

    def passe(d, avanco, primeiro):
        sobra = 0.5   # overcut: estende o corte alem da superficie
        if is_raio:
            ini_r = alvo_r
            ini_z = round4(p.zStart + d)
            sobra_arco = 0.0 if arco_exato else sobra
            fim_r = round4(raio + d * dir_sign + sobra_arco * dir_sign)
            fim_z = p.zEnd
        else:
            off_r = d * dir_sign * cos_a
            off_z = d * sin_a
            ext_r = sobra * cos_a * dir_sign
            ext_z = sobra * sin_a
            ini_r = round4(alvo_r + off_r - ext_r)
            ini_z = round4(p.zStart + off_z + ext_z)
            fim_r = round4(raio + off_r + ext_r)
            fim_z = round4(p.zEnd + off_z - ext_z)

        appr_r = round4(ini_r - dir_sign * folga * sin45)
        appr_z = round4(ini_z + folga * cos45)
        saida_r = round4(fim_r + dir_sign * folga * sin45)
        saida_z = round4(fim_z - folga * cos45)

        if primeiro:
            b.rapid(x=sx(appr_r * 2), z=appr_z)
        else:
            b.rapid(z=appr_z)
            b.rapid(x=sx(appr_r * 2))

        b.linear(x=sx(ini_r * 2), z=ini_z, feed=avanco)

        if is_raio:
            arc_k = round4(p.zEnd - ini_z)
            if is_od:
                arc_dir = "CCW" if x_sign > 0 else "CW"
            else:
                arc_dir = "CW" if x_sign > 0 else "CCW"
            b.arc(x=sx(fim_r * 2), z=fim_z, i=0, k=arc_k, feed=avanco, dir=arc_dir)
        else:
            b.linear(x=sx(fim_r * 2), z=fim_z, feed=avanco)

        b.linear(x=sx(saida_r * 2), z=saida_z, feed=avanco)

    if tem_acab:
        prof_desb = max(0, prof_perp - sobremetal)
        n_desb = (max(1, int(math.ceil(prof_desb / p.roughingDOC)))
                  if prof_desb > 0.0001 else 0)
        for i in range(n_desb - 1, -1, -1):
            d = round4(sobremetal + i * p.roughingDOC)
            passe(d, p.roughingFPR, i == n_desb - 1)

        fin = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs(p.x),
                                 max_rpm=p.maxSpindleRPM, metric=is_metric,
                                 css_mode=True)
        b.comment(u"ACABAMENTO {}".format(u"RAIO" if is_raio else u"CHANFRO"))
        b.spindleSpeed(fin["rpm"], fin["sfm"], True)
        passe(0, p.finishingFPR, False)
    else:
        for i in range(n_total - 1, -1, -1):
            d = round4(i * p.roughingDOC)
            passe(d, p.roughingFPR, i == n_total - 1)

    b.coolantOff()
    b.rapid(z=round4(p.zStart + folga))
    b.rapid(x=sx((raio + folga if is_od else raio - folga) * 2))
    b.spindleOff()

    return b.build()
