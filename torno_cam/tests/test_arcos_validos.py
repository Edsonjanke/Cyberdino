# -*- coding: utf-8 -*-
"""Todo arco emitido tem de fechar: a distancia do centro ao ponto inicial
precisa ser igual a distancia do centro ao ponto final.

Motivo: o engine do EvoCAM soma o sobrecorte (0.5) ao raio FINAL do arco no
modo RAIO sem mover o centro. O LinuxCNC recusa com
"Radius to end of arc differs from radius to start" — foi erro real na maquina.
O dialeto corrige com fixArcOvercut; este teste garante que nao volta.
"""

import math
import re
from types import SimpleNamespace

from torno_cam.engine.defaults import default_params
from torno_cam.engine.strategies import build_nodes
from torno_cam.engine.program import ProgramConfig, entry_from_nodes, assemble_program
from torno_cam.engine.post.linuxcnc_dino import LinuxCNCDinoPost

_PALAVRA = re.compile(r"([XZIK])(-?\d+\.?\d*)")


def _arcos_fecham(gcode):
    """Devolve a lista de erros (raio_inicio, raio_fim) dos arcos do programa."""
    erros = []
    x = z = 0.0
    for linha in gcode.splitlines():
        campos = dict((m.group(1), float(m.group(2)))
                      for m in _PALAVRA.finditer(linha))
        if linha.startswith(("G2 ", "G3 ")):
            # X vem em diametro; o arco e' calculado em raio
            xi, zi = x / 2.0, z
            xf = campos.get("X", x) / 2.0
            zf = campos.get("Z", z)
            cx = xi + campos.get("I", 0.0)
            cz = zi + campos.get("K", 0.0)
            r1 = math.hypot(xi - cx, zi - cz)
            r2 = math.hypot(xf - cx, zf - cz)
            erros.append((linha.strip(), r1, r2))
            x, z = campos.get("X", x), campos.get("Z", z)
        elif linha.startswith(("G0 ", "G1 ")):
            x, z = campos.get("X", x), campos.get("Z", z)
    return erros


def _gera(chave, **over):
    p = default_params(chave)
    p.update(over)
    nos = build_nodes(SimpleNamespace(**p))
    return assemble_program(
        ProgramConfig(title="t", unitSystem="metric", feedMode="REV"),
        [entry_from_nodes("t", nos)], LinuxCNCDinoPost())


CASOS = [
    ("CHAMFER", dict(mode="RADIUS", side="OD", fixArcOvercut=True)),
    ("CHAMFER", dict(mode="RADIUS", side="ID", x=30.0, zEnd=-3.0,
                     fixArcOvercut=True)),
    ("CHAMFER", dict(mode="RADIUS", side="OD", x=50.0, zEnd=-5.0,
                     roughingDOC=4.0, finishDOC=0.0, toolClearance=1.0,
                     fixArcOvercut=True)),          # o caso que falhou na maquina
    ("CHAMFER", dict(mode="RADIUS", side="OD", x=-50.0, fixArcOvercut=True)),
    ("OD_TURN", dict(filletRadius=3.0)),
    ("ID_TURN", dict(mode="EXTENDED", filletRadius=2.0, pilotEnd=-20.0)),
]


def test_arcos_fecham():
    for chave, over in CASOS:
        gcode = _gera(chave, **over)
        arcos = _arcos_fecham(gcode)
        for linha, r1, r2 in arcos:
            assert abs(r1 - r2) < 1e-4, (
                "%s %s: arco nao fecha (%s): raio inicio=%.4f fim=%.4f"
                % (chave, over, linha, r1, r2))


def test_sem_o_flag_o_bug_do_app_permanece():
    """Documenta que o comportamento fiel ao EvoCAM continua disponivel — e'
    o que mantem os goldens validos."""
    gcode = _gera("CHAMFER", mode="RADIUS", side="OD")
    ruins = [a for a in _arcos_fecham(gcode) if abs(a[1] - a[2]) > 1e-4]
    assert ruins, "sem fixArcOvercut o arco deveria continuar como no app"


# ── Ciclo de rosca G76 ───────────────────────────────────────────────────────
def _g76(gcode):
    for l in gcode.splitlines():
        if l.startswith("G76"):
            return dict((m.group(1), float(m.group(2)))
                        for m in re.finditer(r"([PZIJKQH])(-?\d+\.?\d*)", l))
    return None


def test_g76_corta_a_profundidade_certa():
    """O pos do EvoCAM emitia I=-profundidade E K=profundidade: o pico descia
    uma profundidade e o ciclo cortava outra = rosca com o DOBRO. Aqui I e' o
    deslocamento do pico (a folga), entao o fundo cai em pico -/+ K.

    Os valores saem em DIAMETRO (o programa fica em G7 o tempo todo), entao
    valem o dobro do que o engine calcula em raio."""
    for lado, sinal in (("EXTERNAL", -1), ("INTERNAL", +1)):
        p = default_params("THREAD_EXTERNAL")
        p.update(dict(side=lado, useCannedCycle=True,
                      operationType=("THREAD_INTERNAL" if lado == "INTERNAL"
                                     else "THREAD_EXTERNAL")))
        g = _gera_thread(p)
        c = _g76(g)
        assert c, "nao emitiu G76 para " + lado
        # I = deslocamento do pico = -/+ folga, em diametro
        assert abs(c["I"] - sinal * p["clearance"] * 2) < 1e-6, (lado, c)
        # K = profundidade do fio em diametro; nunca o dobro do fio
        assert 0 < c["K"] < 2 * p["pitch"], (lado, c)
        assert c["J"] < c["K"], ("primeiro passe deve ser menor que o fundo", c)
        # Q em GRAUS (29.5 para fio de 60), nao em decimos
        assert 0 <= c["Q"] <= 45, (lado, c)


def test_g76_nao_troca_de_modo_no_meio_do_programa():
    """O programa fica SEMPRE em diametro (G7): nada de entrar em G8 para o
    ciclo e voltar. Medido no rs274 partindo do raio 11 com I-2.5 J0.2:
    em G8 o primeiro passe cai no raio 8.30 e em G7 no 9.65 (metade), entao
    ficar em G7 so' e' correto com I/J/K escritos em diametro."""
    p = default_params("THREAD_EXTERNAL")
    p.update(dict(useCannedCycle=True))
    g = _gera_thread(p)
    assert "G8" not in [l.split()[0] for l in g.splitlines() if l.strip()], g
    modo = [l.split()[0] for l in g.splitlines()
            if l.strip() and l.split()[0] in ("G7", "G8")]
    assert modo == ["G7"], ("so pode declarar diametro, uma vez", modo)


def _gera_thread(p):
    nos = build_nodes(SimpleNamespace(**p))
    return assemble_program(
        ProgramConfig(title="t", unitSystem="metric", feedMode="REV"),
        [entry_from_nodes("t", nos)], LinuxCNCDinoPost())


def test_todo_programa_declara_modo_de_trajetoria():
    """Sem G64/G61 explicito o programa herda o modo que a maquina estiver —
    um G61 deixado por outro programa mudaria o resultado sem aviso."""
    for chave in ("FACE", "OD_TURN", "ID_TURN", "DRILL", "CHAMFER", "GROOVE",
                  "THREAD_EXTERNAL"):
        g = _gera(chave)
        modo = [l for l in g.splitlines() if l.startswith(("G64", "G61"))]
        assert modo, "%s: programa sem modo de trajetoria" % chave
        assert "P0.01" in modo[0] or modo[0].startswith("G61"), (chave, modo[0])


def test_sangrador_desconta_a_largura_em_z():
    """Corte em -5 com sangrador de 3 -> ferramenta em Z-8 (senao a peca sai
    3 mm curta). Regra do operador, confirmada na maquina."""
    p = default_params("GROOVE")
    p.update(dict(mode="PART", zStart=-5.0, finalX=0.0, toolWidth=3.0,
                  compensarLargura=True))
    g = _gera_bruto(p)
    zs = set(float(m) for m in re.findall(r"Z(-?\d+\.?\d*)", g))
    assert -8.0 in zs, "corte deveria posicionar em Z-8, achei %s" % sorted(zs)
    assert -5.0 not in zs, "Z-5 e' a face da peca, nao a posicao da ferramenta"


def test_canal_sai_com_a_largura_pedida():
    """Canal de 0 a -10 com sangrador de 3: a referencia varre -10..-3, e o
    corpo da pastilha completa ate 0 — parede a parede da exatamente 10 mm."""
    p = default_params("GROOVE")
    p.update(dict(mode="GROOVE", zStart=0.0, zEnd=-10.0, toolWidth=3.0,
                  finishDOC=0.0, compensarLargura=True))
    g = _gera_bruto(p)
    merg = [float(m) for m in re.findall(r"G1 X-?\d+\.?\d* Z(-?\d+\.?\d*)", g)]
    assert merg, "nenhum mergulho"
    assert min(merg) >= -10.0001 and max(merg) <= -3.0 + 1e-4, sorted(set(merg))


def _gera_bruto(p):
    nos = build_nodes(SimpleNamespace(**p))
    return assemble_program(
        ProgramConfig(title="t", unitSystem="metric", feedMode="REV"),
        [entry_from_nodes("t", nos)], LinuxCNCDinoPost())


# ── Furacao: quem manda no ciclo e' o PASSO (Q) digitado ────────────────────
def _gera_furo(**extra):
    p = default_params("DRILL")
    p.update(dict(useCannedCycle=True, forcePeckCycle=True,
                  drillDiameter=10.0, zStart=2.0, zEnd=-60.0))
    p.update(extra)
    return _gera_bruto(p)


def test_passo_zero_fura_direto_sem_bicar():
    """Furo de 62 mm com broca de 10 (6x o diametro): a regra do app mandaria
    G83 de qualquer jeito. Se o operador digitou PASSO 0, ele quer o furo
    direto — e' ele que sabe se a broca sai cavaco sozinha."""
    g = _gera_furo(peckDepth=0.0)
    assert "G81" in g and "G83" not in g, g


def test_passo_menor_que_o_furo_bica_no_passo_digitado():
    g = _gera_furo(peckDepth=8.0)
    linha = [l for l in g.splitlines() if l.startswith("G83")]
    assert linha, g
    assert "Q8" in linha[0], linha[0]


def test_passo_maior_que_o_furo_nao_faz_sentido_bicar():
    """Bicada de 100 num furo de 62: a primeira bicada ja passa do fundo."""
    g = _gera_furo(peckDepth=100.0)
    assert "G81" in g and "G83" not in g, g
