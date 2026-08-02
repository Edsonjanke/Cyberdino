# -*- coding: utf-8 -*-
"""Vetores de paridade numerica capturados do Node/V8 (ver probe no historico)."""

import pytest

from torno_cam.engine.jsutil import js_round, round4, js_tofixed, js_num
from torno_cam.engine.post.format_utils import fmt


@pytest.mark.parametrize("x,expected", [
    (2.5, 3), (-2.5, -2), (2.4, 2), (-2.4, -2), (0.5, 1), (-0.5, 0),
    (379375.0, 379375),
])
def test_js_round(x, expected):
    assert js_round(x) == expected


@pytest.mark.parametrize("x,nd,expected", [
    (37.9375, 3, "37.938"),
    (-37.9375, 3, "-37.938"),
    (0.0625, 3, "0.063"),
    (-0.0625, 3, "-0.063"),
    (0.1875, 3, "0.188"),
    (-0.1875, 3, "-0.188"),
    (0.6125, 3, "0.613"),
    (0.615, 3, "0.615"),
    (38.0, 3, "38.000"),
    (0.0, 3, "0.000"),
    (2.5, 0, "3"),
    (-2.5, 0, "-3"),
])
def test_js_tofixed(x, nd, expected):
    assert js_tofixed(x, nd) == expected


@pytest.mark.parametrize("x,expected", [
    (38.0, "38"), (-38.0, "-38"), (0.25, "0.25"), (0.0, "0"),
    (-37.9375, "-37.938"), (50.0, "50"), (0.1, "0.1"),
])
def test_fmt(x, expected):
    assert fmt(x) == expected


@pytest.mark.parametrize("x,expected", [
    (10.0, "10"), (10, "10"), (2.5, "2.5"), (0.1235, "0.1235"),
    (1, "1"), (800, "800"), (0.6134, "0.6134"),
])
def test_js_num(x, expected):
    assert js_num(x) == expected


def test_round4():
    assert round4(-37.9375) == -37.9375
    assert round4(0.123456) == 0.1235
    assert round4(-0.0) == 0.0
