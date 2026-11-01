# -*- coding: utf-8 -*-
"""Mudancas do gerador do handoff "telas de ciclo" (secao 7), com os exemplos
da especificacao: chanfro a 45 graus, G81 com PASSO Q = 0, quebra-canto do
CORTE e comentarios sem parenteses por dentro."""

from types import SimpleNamespace

import pytest

from torno_cam.engine.strategies import build_nodes, EngineError
from torno_cam.engine.program import ProgramConfig, entry_from_nodes, assemble_program
from torno_cam.engine.post.linuxcnc_dino import LinuxCNCDinoPost
from torno_cam.engine.defaults import default_params


def _gen(op_key, **over):
    p = default_params(op_key)
    p.update(over)
    nodes = build_nodes(SimpleNamespace(**p))
    entry = entry_from_nodes(p["title"], nodes)
    cfg = ProgramConfig(title=p["title"], unitSystem="metric", feedMode="REV")
    return assemble_program(cfg, [entry], LinuxCNCDinoPost())


def _sem_chave(op_key, chaves, **over):
    """Programa como era antes: params sem os campos novos de chanfro."""
    p = default_params(op_key)
    p.update(over)
    for c in chaves:
        p.pop(c, None)
    nodes = build_nodes(SimpleNamespace(**p))
    entry = entry_from_nodes(p["title"], nodes)
    cfg = ProgramConfig(title=p["title"], unitSystem="metric", feedMode="REV")
    return assemble_program(cfg, [entry], LinuxCNCDinoPost())


def _trecho(g, linhas):
    """As linhas aparecem em sequencia no programa."""
    todas = g.splitlines()
    n = len(linhas)
    return any(todas[i:i + n] == linhas for i in range(len(todas) - n + 1))


# ── 7.1 chanfro = 0: programa identico ao de antes ───────────────────────────
@pytest.mark.parametrize("op_key,chaves,over", [
    ("FACE", ["chamferSize"], dict(zStart=3.0)),
    ("ID_TURN", ["chamferSize"], dict()),
    ("ID_TURN", ["chamferSize"], dict(mode="EXTENDED", filletRadius=1.0)),
    ("OD_TURN", ["chamferEntry", "chamferExit"], dict()),
    ("OD_TURN", ["chamferEntry", "chamferExit"],
     dict(initialX=-60.0, finalX=-20.0, zEnd=-50.0, filletRadius=1.0)),
])
def test_chanfro_zero_nao_muda_nada(op_key, chaves, over):
    assert _gen(op_key, **over) == _sem_chave(op_key, chaves, **over)


# ── 7.1 a/b/c: exemplos da especificacao ─────────────────────────────────────
def test_chanfro_facear():
    g = _gen("FACE", zStart=3.0, chamferSize=0.5)
    assert _trecho(g, [
        "G0 X55",
        "G0 Z-1.4",
        "G1 X52 Z-1.4 F0.12",
        "G1 X49 Z0.1 (CHANFRO 0.5 X 45)",
        "G1 X0 Z0.1",
    ]), g


@pytest.mark.parametrize("modo", ["BASIC", "EXTENDED"])
def test_chanfro_desbaste_int(modo):
    g = _gen("ID_TURN", mode=modo, chamferSize=0.5)
    assert _trecho(g, [
        "G0 X31 Z4.5",
        "G1 X31 Z3.5 F0.08",
        "G1 X28 Z2 (CHANFRO 0.5 X 45)",
        "G1 X28 Z-30",
    ]), g


def test_chanfros_desbaste_ext():
    g = _gen("OD_TURN", initialX=-60.0, finalX=-20.0, zEnd=-50.0,
             chamferEntry=0.5, chamferExit=0.5)
    assert _trecho(g, [
        "G0 X-17 Z5",
        "G1 X-17 Z3.5 F0.12",
        "G1 X-20 Z2 (CHANFRO ENTRADA 0.5 X 45)",
        "G1 X-20 Z-50",
    ]), g
    assert _trecho(g, [
        "G1 X-59 Z-50",
        "G1 X-60 Z-50.5 (CHANFRO SAIDA 0.5 X 45)",
    ]), g


def test_chanfro_com_somente_acabamento():
    g = _gen("OD_TURN", finishOnly=True, chamferEntry=1.0)
    assert "(CHANFRO ENTRADA 1 X 45)" in g


@pytest.mark.parametrize("op_key,over", [
    ("FACE", dict(zStart=3.0, chamferSize=30.0)),             # maior que a face
    ("ID_TURN", dict(chamferSize=40.0)),                      # maior que a parede
    ("OD_TURN", dict(chamferEntry=20.0)),                     # maior que o raio
    ("OD_TURN", dict(initialX=-60.0, finalX=-20.0, zEnd=-50.0,
                     chamferExit=25.0)),                      # maior que o ressalto
])
def test_chanfro_que_nao_cabe_da_erro(op_key, over):
    with pytest.raises(EngineError):
        _gen(op_key, **over)


# ── 7.2 Furar: Q = 0 -> G17 / G81 / G80 / G18 ────────────────────────────────
def test_furar_q_zero_gera_g81():
    g = _gen("DRILL", peckDepth=0.0, forcePeckCycle=True)
    assert _trecho(g, [
        "G0 X0 Z4.5",
        "(CICLO G81 - FURO DIRETO, PASSO Q = 0)",
        "G17  (PLANO XY: EIXO DE FURACAO = Z)",
        "G81 X0 Z-25 R4.5 G95 F0.12",
        "G80",
        "G18  (VOLTA AO PLANO XZ DO TORNO)",
    ]), g


def test_furar_q_maior_que_zero_continua_igual():
    com = _gen("DRILL", peckDepth=2.0, forcePeckCycle=True)
    sem = _gen("DRILL", peckDepth=2.0)
    assert com == sem
    linhas = com.splitlines()
    assert not [l for l in linhas if l.startswith("G81")]
    assert _trecho(com, ["G1 X0 Z0 G95 F0.12", "G0 X0 Z4.5", "G1 X0 Z-2"]), com


# ── 7.3 Corte: quebra-canto conforme o desenho ───────────────────────────────
def test_quebra_canto_do_corte():
    g = _gen("GROOVE", mode="PART", compensarLargura=True, quebraCantoDesenho=True)
    assert _trecho(g, [
        "(QUEBRA DE ARESTA)",
        "G0 X50 Z-2.7",
        "G1 X49.4 Z-3 G95 F0.05",
        "G0 X55 Z-3",
        "(CORTE COM RETORNO)",
    ]), g


# ── 7.5 nenhum comentario com parenteses por dentro ──────────────────────────
def _aninhado(linha):
    nivel = 0
    for ch in linha:
        if ch == "(":
            nivel += 1
            if nivel > 1:
                return True
        elif ch == ")":
            nivel -= 1
    return False


@pytest.mark.parametrize("op_key,over", [
    ("ID_TURN", dict(mode="EXTENDED")),
    ("THREAD_EXTERNAL", dict()),
    ("FACE", dict(title=u"Eixo (lado A)")),
    ("DRILL", dict(title=u"Furo (centro)")),
])
def test_sem_comentario_aninhado(op_key, over):
    g = _gen(op_key, **over)
    assert not [l for l in g.splitlines() if _aninhado(l)], g


def test_comentario_do_desbaste_int_avancado():
    g = _gen("ID_TURN", mode="EXTENDED")
    assert "(--- DESBASTE ID: PASSES LONGITUDINAIS ---)" in g


# ── Facear: X FINAL do outro lado do centro ──────────────────────────────────
def test_facear_passa_do_centro():
    g = _gen("FACE", zStart=3.0, initialX=50.0, finalX=-1.0)
    assert "G1 X-1 Z0.1" in g and "G1 X1 Z0.1" not in g, g


def test_facear_lado_negativo_passa_do_centro():
    g = _gen("FACE", zStart=3.0, initialX=-50.0, finalX=1.0)
    assert "G1 X1 Z0.1" in g and "G1 X-1 Z0.1" not in g, g


def test_facear_mesmo_sinal_continua_igual():
    assert _gen("FACE", zStart=3.0, finalX=10.0) == _sem_chave(
        "FACE", [], zStart=3.0, finalX=10.0)


# ── AFASTAMENTO FINAL (posicao absoluta) ─────────────────────────────────────
_OPS_AF = [
    ("FACE", dict(zStart=3.0)),
    ("OD_TURN", dict()),
    ("ID_TURN", dict()),
    ("ID_TURN", dict(mode="EXTENDED")),
    ("DRILL", dict()),
    ("CHAMFER", dict()),
    ("CHAMFER", dict(side="ID", x=30.0)),
    ("GROOVE", dict()),
    ("GROOVE", dict(mode="PART")),
    ("THREAD_EXTERNAL", dict()),
    ("THREAD_EXTERNAL", dict(side="INTERNAL", xStart=20.0, xEnd=20.0)),
]

_CHAVES_AF = ["afastamentoFinalZAbs", "afastamentoFinalXAbs"]


@pytest.mark.parametrize("op_key,over", _OPS_AF)
def test_afastamento_final_vazio_nao_muda_nada(op_key, over):
    assert _gen(op_key, **over) == _sem_chave(op_key, _CHAVES_AF, **over)


@pytest.mark.parametrize("op_key,over", _OPS_AF)
def test_afastamento_final_absoluto(op_key, over):
    g = _gen(op_key, afastamentoFinalZAbs=150.0, afastamentoFinalXAbs=-80.0, **over)
    sem = _sem_chave(op_key, _CHAVES_AF, **over).splitlines()
    linhas = g.splitlines()
    # a saida normal continua igual; o bloco novo vem logo depois dela
    i = linhas.index("(Afastamento Final)")
    assert linhas[i + 1:i + 3] == ["G0 Z150", "G0 X-80"], g
    assert linhas[:i] + linhas[i + 3:] == sem, g


def test_afastamento_final_so_z():
    g = _gen("OD_TURN", afastamentoFinalZAbs=100.0)
    assert _trecho(g, ["(Afastamento Final)", "G0 Z100", "M2"]), g


def test_afastamento_final_aceita_zero():
    g = _gen("DRILL", afastamentoFinalXAbs=0.0)
    assert _trecho(g, ["M5", "(Afastamento Final)", "G0 X0", "M2"]), g


# ── SOMENTE ACABAMENTO linha a linha ─────────────────────────────────────────
_SO_ACAB = dict(finishOnly=True, finishOnlyManual=True)


def _cortes(g):
    """Linhas de corte (G1/G2/G3) do programa."""
    return [l for l in g.splitlines() if l.split(" ")[0] in ("G1", "G2", "G3")]


def test_somente_acabamento_facear():
    g = _gen("FACE", zStart=3.0, **_SO_ACAB)
    assert _cortes(g) == ["G1 X55 Z0.1 G95 F0.12", "G1 X0 Z0.1"], g


@pytest.mark.parametrize("modo,saida", [("BASIC", "G1 X24 Z-30"),
                                         ("EXTENDED", "G1 X20 Z-30")])
def test_somente_acabamento_desbaste_int(modo, saida):
    g = _gen("ID_TURN", mode=modo, **_SO_ACAB)
    assert "(PASSE DE ACABAMENTO)" in g
    assert "Faceamento interno" not in g and "LONGITUDINAIS" not in g
    # so o passe final: entra no X FINAL, desce ate o Z FIM e sai
    assert _cortes(g) == ["G1 X28 Z4.5 G95 F0.08", "G1 X28 Z-30", saida], g


def test_somente_acabamento_sem_flag_fica_como_o_evocam():
    # goldens face_finish_only / id_*_finish_only: o app ignora a opcao
    assert _gen("FACE", zStart=3.0, finishOnly=True) == _gen("FACE", zStart=3.0)


def test_somente_acabamento_chanfro():
    g = _gen("CHAMFER", finishOnly=True)
    assert "(ACABAMENTO CHANFRO)" in g
    cortes = _cortes(g)
    assert len(cortes) == 3 and cortes[0].endswith("F0.08"), g   # entra, chanfra, sai


def test_somente_acabamento_canal():
    g = _gen("GROOVE", finishOnly=True, compensarLargura=True)
    linhas = g.splitlines()
    assert "(ACABAMENTO CANAL)" in g
    # nenhum mergulho de desbaste antes do acabamento
    i = linhas.index("(ACABAMENTO CANAL)")
    assert not _cortes("\n".join(linhas[:i])), g


# ── GERAR CICLO: G71 / G72 do LinuxCNC so no desbaste ────────────────────────
_CICLO = dict(useCannedCycle=True, cicloLinuxCNC=True)


def test_g72_facear():
    g = _gen("FACE", zStart=3.0, **_CICLO)
    assert _trecho(g, ["(G72 DESBASTE, CICLO DO LINUXCNC)", "G0 Z3",
                       "O101 sub", "G1 Z0.1", "G1 X0", "O101 endsub",
                       "G72 Q101 D0.25 I2 R2.5 G95 F0.25", "G0 Z5.5"]), g
    assert "(ACABAMENTO FACEAMENTO)" in g and "G70" not in g


def test_g71_desbaste_ext_com_chanfro_no_acabamento():
    g = _gen("OD_TURN", chamferEntry=0.5, **_CICLO)
    assert _trecho(g, ["(G71 DESBASTE, CICLO DO LINUXCNC)", "G0 X50 Z5",
                       "O101 sub", "G1 X38", "G1 Z-38", "O101 endsub",
                       "G71 Q101 D0.25 I2.5 R2.5 G95 F0.25", "G0 X55", "G0 Z5"]), g
    assert "(CHANFRO ENTRADA 0.5 X 45)" in g and "G70" not in g


def test_g71_desbaste_int():
    g = _gen("ID_TURN", **_CICLO)
    assert _trecho(g, ["G0 X20 Z4.5", "(G71 DESBASTE INTERNO, CICLO DO LINUXCNC)",
                       "O101 sub", "G1 X28", "G1 Z-30", "O101 endsub",
                       "G71 Q101 D0.2 I1.5 R2 G95 F0.15", "G0 Z4.5"]), g
    assert "(PASSE DE ACABAMENTO)" in g


def test_dois_ciclos_no_programa_usam_subs_diferentes():
    from torno_cam.engine.defaults import default_params
    entradas = []
    for op, over in (("FACE", dict(zStart=3.0)), ("OD_TURN", {})):
        p = default_params(op); p.update(_CICLO); p.update(over)
        entradas.append(entry_from_nodes(p["title"], build_nodes(SimpleNamespace(**p))))
    g = assemble_program(ProgramConfig(title="T", unitSystem="metric", feedMode="REV"),
                         entradas, LinuxCNCDinoPost())
    assert "G72 Q101" in g and "G71 Q102" in g and "O102 sub" in g, g


# ── PAUSA e FERRAMENTA no final ──────────────────────────────────────────────
def test_pausa_no_final():
    g = _gen("OD_TURN", pausaNoFinal=True)
    assert _trecho(g, ["(PAUSA NO FINAL)", "M5", "M0", "M2"]), g


def test_pausa_nao_repete_m5():
    g = _gen("DRILL", pausaNoFinal=True)
    assert _trecho(g, ["M5", "(PAUSA NO FINAL)", "M0", "M2"]), g


def test_ferramenta_no_final_chama_a_primeira_do_programa():
    from torno_cam.engine.defaults import default_params
    entradas = []
    for op, over in (("FACE", dict(zStart=3.0)),
                     ("ID_TURN", dict(ferramentaFinal=True, pausaNoFinal=True,
                                      afastamentoFinalZAbs=100.0))):
        p = default_params(op); p.update(over)
        entradas.append(entry_from_nodes(p["title"], build_nodes(SimpleNamespace(**p))))
    g = assemble_program(ProgramConfig(title="T", unitSystem="metric", feedMode="REV"),
                         entradas, LinuxCNCDinoPost())
    # afastamento, depois a ferramenta da 1a operacao (T01), depois a pausa
    assert _trecho(g, ["(Afastamento Final)", "G0 Z100",
                       "(CHAMA FERRAMENTA NO FINAL)", "T01 M6 G43 H1",
                       "(PAUSA NO FINAL)", "M5", "M0", "M2"]), g


def test_opcoes_desligadas_nao_mudam_nada():
    for op in ("FACE", "OD_TURN", "ID_TURN", "DRILL", "CHAMFER", "GROOVE",
               "THREAD_EXTERNAL"):
        assert _gen(op, pausaNoFinal=False, ferramentaFinal=False) == _gen(op)


# ── Desbaste Int em G96 com limite de RPM; G95 em cada operacao ──────────────
@pytest.mark.parametrize("modo", ["BASIC", "EXTENDED"])
def test_desbaste_int_g96_com_d(modo):
    g = _gen("ID_TURN", mode=modo, useConstantSurface=True)
    assert "G96 D1800 S120 M3" in g and "G96 D1800 S145 M3" in g, g
    assert "G97" not in g, g


def test_desbaste_int_sem_a_chave_fica_como_o_evocam():
    assert "G97 S120 M3" in _gen("ID_TURN")


def test_g95_na_primeira_linha_de_avanco_de_cada_operacao():
    from torno_cam.engine.defaults import default_params
    entradas = []
    # as duas operacoes com o mesmo avanco: o F da 2a seria omitido (modal)
    for op, over in (("ID_TURN", dict(useConstantSurface=True)),
                     ("ID_TURN", dict(useConstantSurface=True, toolNumber=3))):
        p = default_params(op); p.update(over)
        entradas.append(entry_from_nodes(p["title"], build_nodes(SimpleNamespace(**p))))
    g = assemble_program(ProgramConfig(title="T", unitSystem="metric", feedMode="REV"),
                         entradas, LinuxCNCDinoPost())
    com_g95 = [l for l in g.splitlines() if "G95 F" in l]
    assert com_g95 == ["G1 X22.533 Z-30 G95 F0.15"] * 2, g
