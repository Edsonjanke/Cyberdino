"""Port de strategies/ThreadStrategy.ts (rosca)."""

from ..nodes import ToolpathBuilder
from ..threading_engine import ThreadingEngine, ThreadingInput
from ..jsutil import round4, js_num


def generate_thread(p):
    thread_type = getattr(p, "threadType", None) or (
        "imperial" if p.unitSystem == "imperial" else "metric")
    is_imperial = thread_type == "imperial"

    inp = ThreadingInput(
        threadType="imperial" if is_imperial else "metric",
        pitch=(None if is_imperial else (p.pitch if p.pitch > 0 else None)),
        tpi=((p.tpi if p.tpi > 0 else None) if is_imperial else None),
        threadAngle=p.threadAngle or 60,
        xStart=p.xStart,
        xEnd=(p.xEnd if p.xEnd != p.xStart else None),
        zStart=p.zStart,
        zEnd=p.zEnd,
        clearance=p.clearance,
        side=p.side,
        passes=(p.passes if p.passes > 0 else None),
        springPasses=p.springPasses,
        spindleRPM=p.spindleRPM,
        minorDiameter=(p.minorDiameter if p.minorDiameter > 0 else None),
        infeedAngle=p.infeedAngle or 0,
    )

    result = ThreadingEngine.calculate(inp)
    b = ToolpathBuilder()

    b.comment("ROSCA {}: {}".format(
        "EXTERNA" if p.side == "EXTERNAL" else "INTERNA", p.title))
    b.workOffset(p.workOffset)
    b.toolCall(p.toolNumber, p.toolOffset, "ROSCA T{}".format(js_num(p.toolNumber)))

    b.spindleOn(cssMode=False, dir=p.spindleDir, rpm=p.spindleRPM)
    if p.coolant != "OFF":
        b.coolantOn(p.coolant)

    x_clear = (round4(p.xStart + p.clearance * 2) if p.side == "EXTERNAL"
               else round4(p.xStart - p.clearance * 2))

    if p.useCannedCycle:
        b.comment("G76 CICLO AUTOMATICO DE ROSCA")
        b.rapid(x=x_clear, z=round4(p.zStart + p.clearance))

        thread_depth = result.workingDepth
        first_cut_depth = result.passes[0].depth if result.passes else thread_depth / 4
        min_cut_depth = first_cut_depth * 0.1

        final_x = (round4(p.xStart - thread_depth * 2) if p.side == "EXTERNAL"
                   else round4(p.xStart + thread_depth * 2))

        b.cannedThreadCycle(
            finishPasses=1,
            springPasses=p.springPasses,
            threadAngle=p.threadAngle or 60,
            minCutDepth=round4(min_cut_depth),
            finishAllowance=0,
            finalX=final_x,
            finalZ=round4(p.zEnd),
            threadDepth=round4(thread_depth),
            firstCutDepth=round4(first_cut_depth),
            pitch=result.pitch,
            # a ferramenta esta uma folga acima do diametro da rosca, entao o
            # pico fica a -folga (externa) / +folga (interna) da linha atual
            peakOffset=round4(-p.clearance if p.side == "EXTERNAL"
                              else p.clearance),
        )
    else:
        z_lead = round4(p.zStart + result.leadIn)
        z_end_lead = round4(p.zEnd - result.leadOut)

        for pas in result.passes:
            b.comment("Passe {}{} prof={}".format(
                js_num(pas.index), " (mola)" if pas.isSpringPass else "",
                js_num(round4(pas.depth))))
            b.rapid(x=x_clear)
            b.rapid(z=z_lead)
            b.rapid(x=round4(pas.xPosition))

            end_x = ThreadingEngine.taper_end_x(inp, pas.depth)
            if end_x is not None:
                b.threadFeed(x=round4(end_x), z=z_end_lead, pitch=result.pitch)
            else:
                b.threadFeed(z=z_end_lead, pitch=result.pitch)

            b.rapid(x=x_clear)

    b.coolantOff()
    b.rapid(x=x_clear, z=round4(p.zStart + p.clearance))
    b.spindleOff()
    return b.build()
