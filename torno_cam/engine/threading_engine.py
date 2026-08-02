"""Port de strategies/threading/ThreadingEngine.ts + threading/types.ts."""

import math
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ThreadingInput:
    threadType: str
    threadAngle: float
    xStart: float
    zStart: float
    zEnd: float
    clearance: float
    side: str
    springPasses: int
    spindleRPM: float
    infeedAngle: float
    pitch: Optional[float] = None
    tpi: Optional[float] = None
    xEnd: Optional[float] = None
    passes: Optional[int] = None
    minorDiameter: Optional[float] = None


@dataclass
class ThreadPass:
    index: int
    depth: float
    incrementalDepth: float
    isSpringPass: bool
    xPosition: float


@dataclass
class ThreadingResult:
    pitch: float
    threadAngle: float
    theoreticalDepth: float
    workingDepth: float
    leadIn: float
    leadOut: float
    taperAngle: Optional[float]
    passes: List[ThreadPass]
    totalPasses: int


class ThreadingEngine:

    @staticmethod
    def calculate(inp):
        ThreadingEngine._validate(inp)

        pitch = 25.4 / inp.tpi if inp.tpi is not None else inp.pitch
        angle_rad = (inp.threadAngle / 2) * math.pi / 180
        H = (pitch / 2) / math.tan(angle_rad)
        theoretical_depth = H

        if inp.minorDiameter is not None and inp.minorDiameter > 0:
            working_depth = abs(inp.xStart - inp.minorDiameter) / 2
        elif inp.threadAngle == 60:
            working_depth = 0.6134 * pitch
        else:
            working_depth = 0.7 * H

        lead_in = pitch * 2.5
        lead_out = pitch * 1.5

        taper_angle = None
        if inp.xEnd is not None and inp.xEnd != inp.xStart:
            taper_angle = math.atan2(
                abs(inp.xEnd - inp.xStart) / 2,
                abs(inp.zEnd - inp.zStart),
            )

        passes = ThreadingEngine._calculate_passes(inp, pitch, working_depth, taper_angle)

        return ThreadingResult(
            pitch=pitch, threadAngle=inp.threadAngle,
            theoreticalDepth=theoretical_depth, workingDepth=working_depth,
            leadIn=lead_in, leadOut=lead_out, taperAngle=taper_angle,
            passes=passes, totalPasses=len(passes),
        )

    @staticmethod
    def _validate(inp):
        has_pitch = inp.pitch is not None and inp.pitch > 0
        has_tpi = inp.tpi is not None and inp.tpi > 0
        if inp.pitch is not None and inp.pitch <= 0:
            raise ValueError("pitch must be > 0")
        if inp.tpi is not None and inp.tpi <= 0:
            raise ValueError("tpi must be > 0")
        if has_pitch and has_tpi:
            raise ValueError("Provide pitch OR tpi, not both")
        if not has_pitch and not has_tpi:
            raise ValueError("Either pitch or tpi is required")
        if inp.zStart == inp.zEnd:
            raise ValueError("zStart and zEnd must differ")
        if inp.xStart <= 0:
            raise ValueError("xStart must be > 0")
        if inp.spindleRPM <= 0:
            raise ValueError("spindleRPM must be > 0")

    @staticmethod
    def _calculate_passes(inp, pitch, working_depth, taper_angle):
        roughing_passes = inp.passes if inp.passes is not None else 0
        if roughing_passes <= 0:
            first_pass_depth = 0.2 * pitch
            roughing_passes = math.ceil((working_depth / first_pass_depth) ** 2)
            roughing_passes = max(3, min(40, roughing_passes))

        max_depth_per_pass = 0.5 * pitch

        raw_depths = []
        for n in range(1, roughing_passes + 1):
            raw_depths.append(working_depth * math.sqrt(n / roughing_passes))

        final_depths = []
        prev_depth = 0.0
        for d in raw_depths:
            inc = d - prev_depth
            if inc > max_depth_per_pass:
                sub_steps = math.ceil(inc / max_depth_per_pass)
                for s in range(1, sub_steps + 1):
                    final_depths.append(prev_depth + (inc * s) / sub_steps)
            else:
                final_depths.append(d)
            prev_depth = d

        passes = []
        prev = 0.0
        for i, depth in enumerate(final_depths):
            incremental_depth = depth - prev
            prev = depth
            x_position = ThreadingEngine._calc_x_position(inp, depth, taper_angle)
            passes.append(ThreadPass(
                index=i + 1, depth=depth, incrementalDepth=incremental_depth,
                isSpringPass=False, xPosition=x_position,
            ))

        final_depth = working_depth
        final_x = ThreadingEngine._calc_x_position(inp, final_depth, taper_angle)
        for _s in range(inp.springPasses):
            passes.append(ThreadPass(
                index=len(passes) + 1, depth=final_depth, incrementalDepth=0.0,
                isSpringPass=True, xPosition=final_x,
            ))

        return passes

    @staticmethod
    def _calc_x_position(inp, depth, _taper_angle):
        if inp.side == "EXTERNAL":
            return inp.xStart - depth * 2
        return inp.xStart + depth * 2

    @staticmethod
    def taper_end_x(inp, depth):
        if inp.xEnd is None or inp.xEnd == inp.xStart:
            return None
        taper_shift = inp.xEnd - inp.xStart
        if inp.side == "EXTERNAL":
            return (inp.xStart + taper_shift) - depth * 2
        return (inp.xStart + taper_shift) + depth * 2
