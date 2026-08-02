"""Port de strategies/FaceStrategy.ts (faceamento)."""

import math

from ..nodes import ToolpathBuilder
from ..sfm import calc_spindle_speed
from ..jsutil import round4, js_num


def generate_face(p):
    b = ToolpathBuilder()
    is_metric = p.unitSystem == "metric"

    sign = -1 if p.initialX < 0 else 1
    start_r = abs(p.initialX) / 2
    end_r = abs(p.finalX) / 2
    clear_r = start_r + p.toolClearance

    def sx(v):
        return round4(v * sign)

    z_dir = 1 if p.zEnd >= p.zStart else -1

    total_axial = abs(p.zEnd - p.zStart)
    finish_stock = abs(p.finishDOC)
    rough_stock = max(0, total_axial - finish_stock)
    num_passes = max(1, math.ceil(rough_stock / p.roughingDOC)) if rough_stock > 0.0001 else 0
    axi_doc = round4(rough_stock / num_passes) if num_passes > 0 else 0

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

    if p.useCannedCycle and not p.finishOnly:
        b.comment("G72 CICLO AUTOMATICO DE FACEAMENTO")
        b.rapid(x=sx(clear_r * 2), z=z_approach)
        from ..nodes import Linear
        profile = []
        profile.append(Linear(z=round4(p.zEnd), feed=p.finishingFPR))
        profile.append(Linear(x=sx(end_r * 2), feed=p.finishingFPR))
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

        current_z = p.zStart
        for _i in range(num_passes):
            current_z = round4(current_z + z_dir * axi_doc)
            retract_z = round4(current_z - z_dir * abs(p.toolClearance))
            b.rapid(x=sx(clear_r * 2))
            b.rapid(z=round4(current_z))
            b.linear(feed=p.roughingFPR, x=sx(clear_r * 2), z=round4(current_z))
            b.linear(feed=p.roughingFPR, x=sx(end_r * 2), z=round4(current_z))
            b.rapid(z=retract_z)

        if finish_stock > 0.0001:
            fin_spin = calc_spindle_speed(sfm=p.finishingSFM, diameter=abs(p.initialX),
                                          max_rpm=p.maxSpindleRPM, metric=is_metric,
                                          css_mode=True)
            b.comment("ACABAMENTO FACEAMENTO")
            b.spindleSpeed(fin_spin["rpm"], fin_spin["sfm"], True)

            fin_retract_z = round4(p.zEnd - z_dir * abs(p.toolClearance))
            b.rapid(x=sx(clear_r * 2))
            b.rapid(z=round4(p.zEnd))
            b.linear(feed=p.finishingFPR, x=sx(clear_r * 2), z=round4(p.zEnd))
            b.linear(feed=p.finishingFPR, x=sx(end_r * 2), z=round4(p.zEnd))
            b.rapid(z=fin_retract_z)

    b.coolantOff()
    b.rapid(x=sx(clear_r * 2))
    b.rapid(z=z_approach)
    return b.build()
