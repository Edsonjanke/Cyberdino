# -*- coding: utf-8 -*-
"""Servidor MCP do agente (torno_cam/agente): protocolo e ferramentas.

A paridade com a aba GERAR PGM (mesmos valores -> mesmo G-code) foi conferida
com os formularios reais; aqui fica travado o que nao depende de Qt."""

import io
import json
import os
import shutil

import pytest

from torno_cam.agente import servidor_mcp, ferramentas as fe

TEM_RS274 = shutil.which("rs274") is not None


def _rpc(*msgs):
    entrada = io.StringIO("".join(json.dumps(m) + "\n" for m in msgs))
    saida = io.StringIO()
    servidor_mcp.main(entrada, saida)
    return [json.loads(l) for l in saida.getvalue().splitlines()]


# ── protocolo ────────────────────────────────────────────────────────────────
def test_initialize_e_lista_de_ferramentas():
    r = _rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18"}},
             {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(r) == 2                       # notificacao nao tem resposta
    assert r[0]["result"]["serverInfo"]["name"] == "torno"
    nomes = [t["name"] for t in r[1]["result"]["tools"]]
    assert nomes == ["listar_operacoes", "buscar_rosca", "sugerir_furacao",
                     "gerar_programa", "salvar_programa"]


def test_metodo_desconhecido_e_json_invalido():
    entrada = io.StringIO('nao e json\n{"jsonrpc":"2.0","id":9,"method":"x"}\n')
    saida = io.StringIO()
    servidor_mcp.main(entrada, saida)
    r = [json.loads(l) for l in saida.getvalue().splitlines()]
    assert r[0]["error"]["code"] == -32700 and r[1]["error"]["code"] == -32601


def test_ferramenta_desconhecida_vira_erro_e_nao_derruba():
    r = _rpc({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "rodar_maquina", "arguments": {}}})
    assert r[0]["result"]["isError"]


# ── preparar: as mesmas chaves que os formularios da aba acrescentam ────────
def test_flags_da_tela_por_operacao():
    vazio = {}
    _, p = fe.preparar("FACE", {"zStart": 3}, vazio)
    assert p["finishOnlyManual"] and p["cicloLinuxCNC"] and p["toolOffset"] == p["toolNumber"]
    _, p = fe.preparar("DESBASTE_INT", {"mode": "EXTENDED", "useCannedCycle": True}, vazio)
    assert p["useConstantSurface"] and p["useCannedCycle"] is False
    _, p = fe.preparar("FURAR", {"roughingSFM": 900}, vazio)
    assert p["forcePeckCycle"] and p["finishingSFM"] == 900
    _, p = fe.preparar("CANAL", {"mode": "PART", "finishOnly": True}, vazio)
    assert p["compensarLargura"] and p["quebraCantoDesenho"]
    assert p["useCannedCycle"] is False and p["finishOnly"] is False
    with pytest.raises(ValueError):          # G75 nao existe: nem e' parametro do canal
        fe.preparar("CANAL", {"useCannedCycle": True}, vazio)
    _, p = fe.preparar("CHANFRO", {"zStart": 0, "zEnd": -1.5}, vazio)
    assert p["fixArcOvercut"] and p["chamferLength"] == 1.5


def test_rosca_pela_tabela():
    _, p = fe.preparar("ROSCA", {"rosca": "m12x1,75", "side": "INTERNAL"}, {})
    assert p["operationType"] == "THREAD_INTERNAL" and p["taperTrueAngle"]
    assert p["pitch"] == 1.75 and p["xStart"] == p["xEnd"] == 10.106  # D1
    assert p["threadDepthFactor"] == 0.5413
    _, p = fe.preparar("ROSCA", {"rosca": "M12 x 1.75"}, {})
    assert p["operationType"] == "THREAD_EXTERNAL" and p["xStart"] == 12.0


def test_processo_vem_da_aba_e_geometria_nao():
    estado = {"FACE": {"toolNumber": 7, "roughingSFM": 99, "initialX": 999.0,
                       "useCannedCycle": True}}
    _, p = fe.preparar("FACE", {"initialX": 40, "zStart": 3}, estado)
    assert p["toolNumber"] == 7 and p["roughingSFM"] == 99
    assert p["initialX"] == 40                       # geometria e' do pedido
    assert p["useCannedCycle"] is False              # opcao so' se o agente pedir


def test_parametro_desconhecido_e_tipo_desconhecido():
    with pytest.raises(ValueError):
        fe.preparar("FACE", {"diametro": 50}, {})
    with pytest.raises(ValueError):
        fe.preparar("MANDRILAR", {}, {})


def test_montar_varias_operacoes():
    g, resumo = fe.montar("Eixo", [
        {"tipo": "FACE", "parametros": {"initialX": 50, "zStart": 3, "zEnd": 0}},
        {"tipo": "OD_TURN", "parametros": {"initialX": 50, "finalX": 38, "zStart": 0,
                                           "zEnd": -40, "chamferEntry": 0.5}},
    ], {})
    assert g.splitlines()[0] == "(Eixo)" and "(CHANFRO ENTRADA 0.5 X 45)" in g
    assert len(resumo) == 2


# ── gerar / salvar ───────────────────────────────────────────────────────────
@pytest.mark.skipif(not TEM_RS274, reason="rs274 (LinuxCNC) nao instalado")
def test_gerar_valida_no_linuxcnc():
    texto, erro = fe.gerar_programa("T", [{"tipo": "FACE", "parametros": {
        "initialX": 50, "finalX": -1, "zStart": 3, "zEnd": 0}}])
    assert not erro and "Validacao no LinuxCNC: OK" in texto and "X -1.0" in texto


def test_geometria_impossivel_volta_como_erro():
    texto, erro = fe.gerar_programa("T", [{"tipo": "FACE", "parametros": {
        "initialX": 50, "zStart": 3, "zEnd": 0, "chamferSize": 40}}])
    assert erro and "chanfro" in texto


@pytest.mark.skipif(not TEM_RS274, reason="rs274 (LinuxCNC) nao instalado")
def test_salvar_grava_sem_sobrescrever(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTE_PASTA_PROGRAMAS", str(tmp_path))
    ops = [{"tipo": "FACE", "parametros": {"initialX": 50, "zStart": 3, "zEnd": 0}}]
    t1, e1 = fe.salvar_programa("Peça 1", ops)
    t2, e2 = fe.salvar_programa("Peça 1", ops)
    assert not e1 and not e2
    caminhos = [l.split(fe.MARCA_ARQUIVO, 1)[1].strip() for l in (t1 + "\n" + t2).splitlines()
                if l.startswith(fe.MARCA_ARQUIVO)]
    assert [os.path.basename(c) for c in caminhos] == ["Peca_1.ngc", "Peca_1-1.ngc"]
    assert open(caminhos[0]).read().startswith("(Peça 1)") or "(Peca 1)" in open(caminhos[0]).read()


def test_salvar_nao_aceita_gcode_solto():
    # a ferramenta so' recebe operacoes: G-code escrito a mao nao tem por onde entrar
    esquema = next(f for f in fe.FERRAMENTAS if f["nome"] == "salvar_programa")["esquema"]
    assert set(esquema["properties"]) == {"titulo", "operacoes"}
    texto, erro = fe.salvar_programa("x", [{"tipo": "FACE", "parametros": {"gcode": "G0 X0"}}])
    assert erro


# ── regra do faceamento: termina em Z0, sobremetal para mais ─────────────────
def test_faceamento_termina_em_z0():
    _, p = fe.preparar("FACE", {"zStart": 3}, {})
    assert p["zStart"] == 3 and p["zEnd"] == 0.0     # Z FINAL vale 0 sem pedir
    with pytest.raises(ValueError, match="sempre 0"):
        fe.preparar("FACE", {"zStart": 3, "zEnd": 0.1}, {})
    with pytest.raises(ValueError, match="sobremetal"):
        fe.preparar("FACE", {"zStart": 0}, {})       # sem dizer quanto facear
    with pytest.raises(ValueError, match="sobremetal"):
        fe.preparar("FACE", {"zStart": -3, "zEnd": 0}, {})


# ── regra da ferramenta negativa: todos os X negativos ───────────────────────
@pytest.mark.skipif(not TEM_RS274, reason="rs274 (LinuxCNC) nao instalado")
@pytest.mark.parametrize("tipo,parametros", [
    ("FACE", {"initialX": -50, "finalX": 0, "zStart": 3, "chamferSize": 0.5}),
    ("FACE", {"initialX": -50, "finalX": 1, "zStart": 3}),          # passa do centro
    ("OD_TURN", {"initialX": -50, "finalX": -38, "zStart": 0, "zEnd": -40,
                 "chamferEntry": 0.5, "useCannedCycle": True}),
    ("ID_TURN", {"initialX": -20, "finalX": -28, "zStart": 0, "zEnd": -30, "chamferSize": 0.5}),
    ("CHAMFER", {"x": -50, "zStart": 0, "zEnd": -2}),
    ("GROOVE", {"initialX": -50, "finalX": -40, "zStart": -5, "zEnd": -10}),
])
def test_ferramenta_negativa_gera_e_valida(tipo, parametros):
    texto, erro = fe.gerar_programa("Neg", [{"tipo": tipo, "parametros": parametros}])
    assert not erro and "Validacao no LinuxCNC: OK" in texto, texto
    corpo = texto.split("\n(Neg)\n", 1)[1]
    import re
    xs = [float(m) for l in corpo.splitlines() if l.startswith(("G1 ", "G0 "))
          for m in re.findall(r"\bX(-?[\d.]+)", l.split("(")[0])]
    assert min(xs) < 0                               # trabalhou no lado -X


def test_rosca_com_ferramenta_negativa_vira_erro_claro():
    texto, erro = fe.gerar_programa("R", [{"tipo": "THREAD", "parametros": {
        "rosca": "M12 x 1.75", "zStart": 2, "zEnd": -20, "xStart": -12, "xEnd": -12}}])
    assert erro


# ── regra da furacao: sempre em ciclo ────────────────────────────────────────
@pytest.mark.skipif(not TEM_RS274, reason="rs274 (LinuxCNC) nao instalado")
@pytest.mark.parametrize("parametros,ciclo", [
    ({"peckDepth": 0}, "G81 X0 Z-25"),                         # furo direto
    ({"peckDepth": 5}, "G83 X0 Z-25"),                         # com bicada
    ({"peckDepth": 0, "dwellSeconds": 1}, "G82 X0 Z-25"),      # com espera no fundo
    ({"peckDepth": 5, "useCannedCycle": False}, "G83 X0 Z-25"),  # pedir sem ciclo nao vale
])
def test_furacao_sempre_em_ciclo(parametros, ciclo):
    base = {"drillDiameter": 10, "zStart": 2, "zEnd": -25}
    base.update(parametros)
    texto, erro = fe.gerar_programa("Furo", [{"tipo": "DRILL", "parametros": base}])
    assert not erro and "Validacao no LinuxCNC: OK" in texto, texto
    linhas = texto.splitlines()
    assert any(l.startswith(ciclo) for l in linhas), texto
    assert "G17  (PLANO XY: EIXO DE FURACAO = Z)" in linhas and "G80" in linhas
    assert "(FURACAO MANUAL - LINHA A LINHA)" not in texto


# ── regra do furo de centro: sempre G81 (quebra-cavaco 0) ────────────────────
@pytest.mark.skipif(not TEM_RS274, reason="rs274 (LinuxCNC) nao instalado")
def test_furo_de_centro_sempre_g81():
    texto, erro = fe.gerar_programa("Centro", [{"tipo": "FURAR", "parametros": {
        "furoDeCentro": True, "drillDiameter": 3, "zStart": 2, "zEnd": -5,
        "peckDepth": 2, "dwellSeconds": 1, "material": "ACO", "usarTabela": True}}])
    assert not erro and "Validacao no LinuxCNC: OK" in texto, texto
    linhas = texto.splitlines()
    assert any(l.startswith("G81 X0 Z-5") for l in linhas), texto
    assert not any(l.startswith(("G83", "G82")) for l in linhas)
    _, p = fe.preparar("FURAR", {"furoDeCentro": True, "drillDiameter": 3, "peckDepth": 2}, {})
    assert p["peckDepth"] == 0 and p["dwellSeconds"] == 0 and p["useCannedCycle"]
