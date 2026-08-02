# -*- coding: utf-8 -*-
"""Paridade string-a-string: o engine Python deve reproduzir EXATAMENTE o
G-code gerado pelo engine TS (LinuxCNCPost fiel) para cada caso golden.

Goldens gerados por Evo-CNC-Guia/packages/postprocessor/src/golden/golden.spec.ts
(ver tests/golden/README.md). Rode: python3 -m pytest torno_cam/tests -q
"""

import difflib
import glob
import json
import os
from types import SimpleNamespace

import pytest

from torno_cam.engine.strategies import build_nodes
from torno_cam.engine.program import ProgramConfig, entry_from_nodes, assemble_program
from torno_cam.engine.post.linuxcnc import LinuxCNCPost

_GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")


def _cases():
    for params_path in sorted(glob.glob(os.path.join(_GOLDEN_DIR, "*.params.json"))):
        case_id = os.path.basename(params_path)[:-len(".params.json")]
        yield case_id


def _assemble_case(case_id):
    with open(os.path.join(_GOLDEN_DIR, case_id + ".params.json"), encoding="utf-8") as f:
        data = json.load(f)
    cfg = ProgramConfig(
        title=data["config"]["title"],
        unitSystem=data["config"]["unitSystem"],
        feedMode=data["config"].get("feedMode", "REV"),
        programNumber=data["config"].get("programNumber", 1000),
    )
    entries = [entry_from_nodes(op["label"], build_nodes(SimpleNamespace(**op["params"])))
               for op in data["ops"]]
    return assemble_program(cfg, entries, LinuxCNCPost())


@pytest.mark.parametrize("case_id", list(_cases()))
def test_golden_parity(case_id):
    with open(os.path.join(_GOLDEN_DIR, case_id + ".ngc"), encoding="utf-8") as f:
        expected = f.read()
    got = _assemble_case(case_id)
    if got != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), got.splitlines(),
            fromfile="golden(TS)", tofile="python", lineterm=""))
        pytest.fail("Divergencia em '{}':\n{}".format(case_id, diff))


def test_golden_dir_nao_vazio():
    assert list(_cases()), "Nenhum golden encontrado — rode o gerador TS primeiro"
