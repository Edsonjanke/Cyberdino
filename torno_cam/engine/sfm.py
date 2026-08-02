"""Port de feeds-speeds/SFMCalculator.ts.

NOTA (bug preservado por paridade): com cssMode=False, calc_spindle_speed
retorna rpm = sfm diretamente (o campo 'sfm' carrega o RPM). Por isso a
furacao no engine original emite G97 S<vc> em vez do RPM calculado. O
dialeto Dino corrige isso na Fase 1."""

import math

from .jsutil import js_round


def rpm_from_sfm(sfm, diameter_inches):
    if diameter_inches <= 0:
        return 0
    return (sfm * 12) / (math.pi * diameter_inches)


def rpm_from_css(css_mm_per_min, diameter_mm):
    if diameter_mm <= 0:
        return 0
    return (css_mm_per_min * 1000) / (math.pi * diameter_mm)


def clamp_rpm(rpm, max_rpm):
    return min(max(0, rpm), max_rpm)


def calc_spindle_speed(sfm, diameter, max_rpm, metric, css_mode):
    """Retorna dict {rpm, sfm, cssMode, maxRPM} (rpm arredondado via Math.round)."""
    if css_mode:
        rpm = rpm_from_css(sfm, diameter) if metric else rpm_from_sfm(sfm, diameter)
    else:
        rpm = sfm  # modo RPM fixo: o campo sfm carrega o RPM
    return {
        "rpm": js_round(clamp_rpm(rpm, max_rpm)),
        "sfm": sfm,
        "cssMode": css_mode,
        "maxRPM": max_rpm,
    }
