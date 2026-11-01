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


# ── conferido contra o GCODE-ROSCAS.md (01/11/2026) ─────────────────────────
from torno_cam.agente import ferramentas as fe


def _programa(rosca, side, z0, z1):
    g, _ = fe.montar("t", [{"tipo": "ROSCA", "parametros": dict(
        rosca=rosca, side=side, zStart=z0, zEnd=z1, toolNumber=1,
        useCannedCycle=True, springPasses=2, depthOfCut=0)}], {})
    return g.splitlines()


def _palavra(linha, letra):
    return float(re.search(r" %s(-?[\d.]+)" % letra, linha).group(1))


def test_altura_do_filete_por_perfil():
    """Secao 7: 0.6134 externa, 0.5413 interna, 0.8 na NPT (no raio)."""
    assert R.altura_filete(R.TAB_METRICA, False) == 0.6134
    assert R.altura_filete(R.TAB_POLEGADA, True) == 0.5413
    assert R.altura_filete(R.TAB_NPT, False) == R.altura_filete(R.TAB_NPT, True) == 0.8


def test_m10x15_externa_igual_ao_8_1():
    g76 = next(l for l in _programa("M10 x 1.5", "EXTERNAL", 2, -20) if l.startswith("G76"))
    assert _palavra(g76, "P") == 1.5 and _palavra(g76, "K") == 1.84   # fundo 8.16
    assert _palavra(g76, "I") < 0                                     # externa


def test_m20x15_interna_igual_ao_8_2():
    """Crista no D1 18.376, K1.624 e fundo no nominal 20.0. Antes partia da
    broca 18.5 com a altura da externa e o fundo ia a 20.34: porca frouxa."""
    linhas = _programa("M20 x 1.5", "INTERNAL", 2, -18)
    g76 = next(l for l in linhas if l.startswith("G76"))
    x = next(_palavra(" " + l, "X") for l in reversed(linhas[:linhas.index(g76)])
             if l.startswith("G0") and " X" in " " + l)
    assert _palavra(g76, "I") > 0                                     # interna
    assert round(x + _palavra(g76, "I"), 3) == 18.376                  # crista
    assert _palavra(g76, "K") == 1.624
    assert round(x + _palavra(g76, "I") + _palavra(g76, "K"), 3) == 20.0


def _passes_g33(linhas):
    return [(_palavra(l, "X"), _palavra(l, "Z")) for l in linhas if l.startswith("G33")]


def test_npt_corta_a_altura_de_0_8_passo():
    """Secao 9.5: NPT 1/2-14 tem h = 0.8 x 1.81429 = 1.451 no raio. Com a
    altura da metrica (0.6134) sobrava 0.34 mm no raio: nao rosqueava."""
    it = R.buscar('NPT 1/2" - 14')
    h = 0.8 * 25.4 / 14
    x, z = _passes_g33(_programa(it["nome"], "EXTERNAL", 0, -14))[-1]
    crista = it["bitola"] - z * it["conicidade"]
    assert abs((crista - x) / 2.0 - h) < 0.002
    x, z = _passes_g33(_programa(it["nome"], "INTERNAL", 0, -14))[-1]
    crista = it["menor"] + z * it["conicidade"]
    assert abs((x - crista) / 2.0 - h) < 0.002


def test_npt_interna_fecha_ao_entrar_na_luva():
    """Na luva o diametro DIMINUI para dentro (a ponta do tubo vai mais
    fundo). Antes o cone saia invertido."""
    it = R.buscar('NPT 1/2" - 14')
    x0, x1, ang = R.extremos(it, True, 0.0, -16.0)
    assert abs(x0 - it["menor"]) < 1e-6 and abs(x0 - x1 - 1.0) < 1e-3 and ang < 0
    x0, x1, ang = R.extremos(it, False, 0.0, -16.0)
    assert abs(x1 - x0 - 1.0) < 1e-3 and ang > 0
    # E1 - 0.8p da ASME B1.20.1: (0.77843 - 0.05714) x 25.4
    assert abs(it["menor"] - 18.321) < 0.002


def test_passo_em_polegada_com_5_casas():
    """Secao 9.1: arredondar 25.4/fios acumula erro em rosca longa."""
    g76 = next(l for l in _programa('1/2" - 13 UNC', "EXTERNAL", 2, -20) if l.startswith("G76"))
    assert " P1.95385 " in g76
    linhas = _programa('NPT 1/2" - 14', "EXTERNAL", 0, -14)
    assert all(" K1.81429" in l for l in linhas if l.startswith("G33"))


def test_g76_sai_em_rampa_de_um_passo():
    """L2 com E = passo: o fundo vai ate FIM Z + passo e a rampa sincronizada
    sobe ate a crista no FIM Z (medido no rs274), sem canal de saida."""
    g76 = next(l for l in _programa("M10 x 1.5", "EXTERNAL", 2, -20) if l.startswith("G76"))
    assert g76.endswith(" E1.5 L2"), g76
    g76 = next(l for l in _programa('1/2" - 13 UNC', "EXTERNAL", 2, -20) if l.startswith("G76"))
    assert " E1.9538 L2" in g76, g76


def test_rampa_nunca_passa_de_metade_da_linha_de_conducao():
    """O LinuxCNC recusa E maior que metade da linha de conducao: numa rosca
    curta (Z0.5 ate Z-2 = 2.5 mm) o E fica em 1.25, nao no passo 1.5."""
    g, _ = fe.montar("t", [{"tipo": "ROSCA", "parametros": dict(
        rosca="M10 x 1.5", side="EXTERNAL", zStart=0, zEnd=-2, clearance=0.5,
        toolNumber=1, useCannedCycle=True, springPasses=2, depthOfCut=0)}], {})
    g76 = next(l for l in g.splitlines() if l.startswith("G76"))
    assert " E1.25 L2" in g76, g76
