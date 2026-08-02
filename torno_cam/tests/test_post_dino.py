# -*- coding: utf-8 -*-
"""Trava as divergencias INTENCIONAIS do dialeto Dino em relacao ao pos fiel."""

from types import SimpleNamespace

from torno_cam.engine.strategies import build_nodes
from torno_cam.engine.program import ProgramConfig, entry_from_nodes, assemble_program
from torno_cam.engine.post.linuxcnc_dino import LinuxCNCDinoPost
from torno_cam.engine.defaults import default_params

import pytest


def _gen(op_key, **over):
    p = default_params(op_key)
    p.update(over)
    nodes = build_nodes(SimpleNamespace(**p))
    entry = entry_from_nodes(p["title"], nodes)
    cfg = ProgramConfig(title="TESTE", unitSystem="metric", feedMode="REV")
    return assemble_program(cfg, [entry], LinuxCNCDinoPost())


def test_rosca_usa_g33_nao_g32():
    g = _gen("THREAD_EXTERNAL")
    assert "G33" in g and " K" in g
    assert "G32" not in g


def test_rosca_g33_tem_passo_em_k():
    g = _gen("THREAD_EXTERNAL", pitch=1.5)
    assert "K1.5" in g


def test_furacao_emite_rpm():
    # roughingSFM=1000 (RPM) com cssMode=False -> G97 S1000
    g = _gen("DRILL", roughingSFM=1000, maxSpindleRPM=2500)
    assert "G97 S1000 M3" in g


def test_comentario_sem_nao_ascii():
    g = _gen("DRILL", drillDiameter=10)
    assert u"Ø" not in g
    assert "BROCA 10" in g   # 'BROCA Ø10' sanitizado
    # nenhum caractere fora de ASCII no programa inteiro
    g.encode("ascii")


def test_ciclo_fixo_bloqueado():
    with pytest.raises(NotImplementedError):
        _gen("OD_TURN", useCannedCycle=True)


def test_travessao_sanitizado():
    # RAIO ... — IGNORADO  vira '-'
    g = _gen("OD_TURN", filletRadius=50, finalX=38, initialX=50)
    assert u"—" not in g
