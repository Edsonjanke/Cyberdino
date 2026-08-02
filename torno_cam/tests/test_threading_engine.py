# -*- coding: utf-8 -*-
"""Testes de comportamento do ThreadingEngine (portados do ThreadingEngine.test.ts)."""

import math

import pytest

from torno_cam.engine.threading_engine import ThreadingEngine, ThreadingInput


def _inp(**over):
    base = dict(threadType="metric", threadAngle=60, xStart=25.0, zStart=2.0,
                zEnd=-25.0, clearance=2.5, side="EXTERNAL", springPasses=2,
                spindleRPM=800, infeedAngle=0, pitch=1.0)
    base.update(over)
    return ThreadingInput(**base)


def test_working_depth_60deg_metric():
    r = ThreadingEngine.calculate(_inp(pitch=1.0))
    assert r.workingDepth == pytest.approx(0.6134, abs=1e-9)
    assert r.pitch == 1.0


def test_pitch_from_tpi():
    r = ThreadingEngine.calculate(_inp(pitch=None, tpi=20, threadType="imperial"))
    assert r.pitch == pytest.approx(25.4 / 20)


def test_auto_pass_count_clamped():
    # pitch 1 -> ceil((0.6134/0.2)^2)=ceil(9.4)=10 passes de desbaste + 2 mola
    r = ThreadingEngine.calculate(_inp(pitch=1.0, springPasses=2))
    rough = [p for p in r.passes if not p.isSpringPass]
    spring = [p for p in r.passes if p.isSpringPass]
    assert len(rough) == 10
    assert len(spring) == 2
    assert r.totalPasses == 12


def test_auto_pass_count_min3_max40():
    fine = ThreadingEngine.calculate(_inp(pitch=0.3, springPasses=0))
    assert 3 <= len([p for p in fine.passes if not p.isSpringPass]) <= 40


def test_explicit_passes():
    r = ThreadingEngine.calculate(_inp(pitch=1.0, passes=6, springPasses=1))
    assert len([p for p in r.passes if not p.isSpringPass]) == 6
    assert len([p for p in r.passes if p.isSpringPass]) == 1


def test_depths_monotonic_and_sqrt_law():
    r = ThreadingEngine.calculate(_inp(pitch=1.0, springPasses=0))
    depths = [p.depth for p in r.passes]
    assert depths == sorted(depths)
    assert depths[-1] == pytest.approx(r.workingDepth, abs=1e-9)


def test_external_x_position():
    r = ThreadingEngine.calculate(_inp(pitch=1.0, side="EXTERNAL", xStart=25.0))
    first = r.passes[0]
    assert first.xPosition == pytest.approx(25.0 - first.depth * 2)


def test_taper_end_x():
    inp = _inp(pitch=1.0, xEnd=24.0)
    r = ThreadingEngine.calculate(inp)
    ex = ThreadingEngine.taper_end_x(inp, r.passes[0].depth)
    assert ex is not None
    assert ex == pytest.approx((25.0 + (24.0 - 25.0)) - r.passes[0].depth * 2)


def test_validate_errors():
    with pytest.raises(ValueError):
        ThreadingEngine.calculate(_inp(zStart=5.0, zEnd=5.0))
    with pytest.raises(ValueError):
        ThreadingEngine.calculate(_inp(pitch=1.0, tpi=20))
    with pytest.raises(ValueError):
        ThreadingEngine.calculate(_inp(pitch=None, tpi=None))
