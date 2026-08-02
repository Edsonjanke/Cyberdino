# -*- coding: utf-8 -*-
"""Tabelas de rosca: metrica, polegada (UNC/UNF) e NPT.

O operador escolhe a rosca pelo nome e o painel preenche passo, diametro e
RPM. Se a tabela mentir, a peca sai errada sem nenhum aviso — por isso os
valores conferidos aqui sao os da norma, nao os que o codigo calculou.
"""

import math
import re
from types import SimpleNamespace

from torno_cam.engine import roscas as R
from torno_cam.engine.defaults import default_params
from torno_cam.engine.strategies import build_nodes
from torno_cam.engine.program import ProgramConfig, entry_from_nodes, assemble_program
from torno_cam.engine.post.linuxcnc_dino import LinuxCNCDinoPost


# ── metrica ─────────────────────────────────────────────────────────────────
def test_metrica_continua_como_estava():
    itens = R.lista(R.TAB_METRICA)
    assert len(itens) == 97
    m8 = R.buscar("M8 x 1.25")
    assert m8["passo"] == 1.25 and m8["tipo"] == R.PADRAO
    assert m8["broca"] == 6.75            # D - passo, regra de oficina
    assert m8["titulo"] == u"Rosca M8 X 1.25 mm"


# ── polegada ────────────────────────────────────────────────────────────────
def test_polegada_passo_sai_dos_fios():
    for it in R.lista(R.TAB_POLEGADA):
        assert abs(it["passo"] - 25.4 / it["tpi"]) < 1e-4, it["nome"]


def test_polegada_unc_e_unf_com_as_cores_certas():
    itens = R.lista(R.TAB_POLEGADA)
    unc = [i for i in itens if i["comentario"] == u"UNC"]
    unf = [i for i in itens if i["comentario"] == u"UNF"]
    assert len(unc) == 20 and len(unf) == 18   # 1.3/4 e 2 so tem UNC
    assert all(R.COR[i["tipo"]] == "#4caf50" for i in unc)
    assert all(R.COR[i["tipo"]] == "#ffd600" for i in unf)


def test_polegada_valores_conhecidos():
    meia = R.buscar('1/2" - 13 UNC')
    assert abs(meia["bitola"] - 12.7) < 1e-6        # 0.5" em mm
    assert abs(meia["passo"] - 1.9538) < 1e-3
    # bitola numerada nao leva aspas ("#10", nao '#10"')
    assert R.buscar(u"#10 - 24 UNC") is not None


# ── NPT ─────────────────────────────────────────────────────────────────────
def test_npt_tem_conicidade_de_1_para_16():
    itens = R.lista(R.TAB_NPT)
    assert len(itens) == 13
    for it in itens:
        assert it["tipo"] == R.CONICA
        assert abs(it["conicidade"] - 1.0 / 16.0) < 1e-9
        assert R.COR[it["tipo"]] == "#40C4FF"


def test_npt_diametro_maior_na_ponta():
    """1/2-14: E0 = 0.75843", filete NPT = 0.8 x passo, entao o maior na
    ponta e' (0.75843 + 0.8/14) x 25.4 = 20.716 mm."""
    meia = R.buscar('NPT 1/2" - 14')
    assert abs(meia["bitola"] - 20.716) < 0.002
    assert abs(meia["passo"] - 25.4 / 14) < 1e-4
    assert abs(meia["comprimento"] - 13.56) < 0.02      # L2 da norma


def test_npt_diametro_cresce_ao_entrar_na_peca():
    meia = R.buscar('NPT 1/2" - 14')
    x = R.x_final_conico(meia, 0.0, -16.0)
    assert abs(x - (meia["bitola"] + 1.0)) < 1e-3      # 16 mm -> 1 mm


def test_buscar_acha_em_qualquer_tabela():
    for nome in ("M8 x 1.25", '1/2" - 13 UNC', 'NPT 1/2" - 14'):
        assert R.buscar(nome) is not None, nome


# ── o que a conicidade faz no G-code ────────────────────────────────────────
def _gera(**extra):
    p = default_params("THREAD_EXTERNAL")
    p.update(dict(threadType="imperial", tpi=14.0, xStart=20.59, xEnd=22.28,
                  zStart=2.0, zEnd=-25.0))
    p.update(extra)
    return assemble_program(
        ProgramConfig(title="t", unitSystem="metric", feedMode="REV"),
        [entry_from_nodes("t", build_nodes(SimpleNamespace(**p)))],
        LinuxCNCDinoPost())


def test_rosca_conica_nunca_sai_em_ciclo():
    """G76 nao tem palavra de conicidade: com o ciclo ligado ele cortaria um
    CILINDRO no diametro do inicio — passa no calibre de boca e nao veda."""
    linhas = _gera(useCannedCycle=True).splitlines()
    assert not [l for l in linhas if l.startswith("G76")]
    assert [l for l in linhas if "ROSCA CONICA" in l], "faltou avisar no programa"


def _conicidade_do_gcode(gcode):
    linhas = gcode.splitlines()
    i = next(i for i, l in enumerate(linhas) if l.startswith("G33"))
    x0 = float(re.search(r"X(-?[\d.]+)", linhas[i - 1]).group(1))
    z0 = float(re.search(r"Z(-?[\d.]+)", linhas[i - 2]).group(1))
    m = re.search(r"X(-?[\d.]+) Z(-?[\d.]+)", linhas[i])
    return (float(m.group(1)) - x0) / (z0 - float(m.group(2)))


def test_cone_exato_da_a_conicidade_pedida():
    """Sem a flag o app espalhava a conicidade INTEIRA entre a entrada e a
    saida da rosca, que sao mais longas que ela: o cone saia mais aberto
    (1:20 no lugar de 1:16) e a NPT nao vedaria."""
    assert abs(1 / _conicidade_do_gcode(_gera(taperTrueAngle=True)) - 16.0) < 0.1
    frouxo = 1 / _conicidade_do_gcode(_gera())
    assert frouxo > 18.0, "sem a flag o comportamento do app deveria continuar"
