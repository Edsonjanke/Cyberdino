# -*- coding: utf-8 -*-
"""Ferramentas do servidor MCP do torno.

O agente so' escolhe operacoes e parametros; o G-code sai do mesmo motor da
aba GERAR PGM, com as mesmas chaves que os formularios da aba acrescentam
(ver `preparar`). `salvar_programa` recebe as OPERACOES (nunca texto de
G-code), remonta o programa e so' grava se o interpretador do LinuxCNC
aceitar: nao ha como salvar G-code escrito a mao pelo agente.

Cada funcao devolve (texto, erro). O texto vai para o agente.
"""

import json
import os
import re
import subprocess
import tempfile
import unicodedata
from types import SimpleNamespace

from ..engine.defaults import default_params
from ..engine.strategies import build_nodes, EngineError
from ..engine.program import ProgramConfig, entry_from_nodes, assemble_program
from ..engine.post.linuxcnc_dino import LinuxCNCDinoPost
from ..engine import roscas, furacao

_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MARCA_ARQUIVO = "ARQUIVO_SALVO:"

# ── operacoes ────────────────────────────────────────────────────────────────
TIPOS = {
    "FACE": "FACE", "FACEAR": "FACE", "FACEAMENTO": "FACE",
    "OD_TURN": "OD_TURN", "DESBASTE_EXT": "OD_TURN", "DESBASTE_EXTERNO": "OD_TURN",
    "ID_TURN": "ID_TURN", "DESBASTE_INT": "ID_TURN", "DESBASTE_INTERNO": "ID_TURN",
    "DRILL": "DRILL", "FURAR": "DRILL", "FURACAO": "DRILL",
    "CHAMFER": "CHAMFER", "CHANFRO": "CHAMFER", "RAIO": "CHAMFER",
    "GROOVE": "GROOVE", "CANAL": "GROOVE", "CORTE": "GROOVE",
    "THREAD": "THREAD", "ROSCA": "THREAD",
}

COMUNS = {
    "title": "titulo da operacao (vai no comentario do G-code)",
    "toolNumber": "numero da ferramenta na torre (T e H)",
    "workOffset": "zero peca: G54 a G59",
    "spindleDir": "sentido do fuso: CW (M3) ou CCW (M4)",
    "coolant": "refrigeracao: FLOOD (M8), MIST (M7), AIR ou OFF",
    "pausaNoFinal": "true = M5 e M0 no fim da operacao (para medir)",
    "ferramentaFinal": "true = no fim chama a ferramenta da 1a operacao do programa",
    "afastamentoFinalZAbs": "Z absoluto para onde a ferramenta vai no fim (null = nao vai)",
    "afastamentoFinalXAbs": "X absoluto (diametro) para onde vai no fim, depois do Z",
}
CORTE = {
    "roughingSFM": "Vc de desbaste, m/min (G96)",
    "finishingSFM": "Vc de acabamento, m/min",
    "maxSpindleRPM": "RPM maxima (D do G96)",
    "roughingFPR": "avanco de desbaste, mm/volta",
    "finishingFPR": "avanco de acabamento, mm/volta",
}

OPERACOES = {
    "FACE": dict(
        nome="FACEAR",
        resumo="Faceamento da face da peca, do X INICIAL ate o X FINAL.",
        chaves=dict(COMUNS, **CORTE, **{
            "initialX": "X INICIAL: diametro bruto da peca (mm)",
            "finalX": "X FINAL: ate onde faceia (0 = centro; com sinal contrario ao X INICIAL passa do centro, ex. -1)",
            "zStart": "Z INICIAL: sobremetal a facear, positivo (ex. facear 3 mm = 3)",
            "zEnd": "Z FINAL: sempre 0 (a face acabada e' o zero peca)",
            "chamferSize": "chanfro a 45 graus no canto do X INICIAL com a face (0 = sem)",
            "roughingDOC": "profundidade de desbaste por passe em Z",
            "finishDOC": "sobremetal do passe de acabamento",
            "toolClearance": "afastamento G0 (raio/Z)",
            "finishOnly": "true = so o passe de acabamento",
            "useCannedCycle": "true = desbaste com o ciclo G72 do LinuxCNC",
        })),
    "OD_TURN": dict(
        nome="DESBASTE EXTERNO",
        resumo="Torneamento externo: reduz do X INICIAL ao X FINAL, do Z INICIAL ate o Z FINAL (ressalto).",
        chaves=dict(COMUNS, **CORTE, **{
            "initialX": "X INICIAL: diametro bruto",
            "finalX": "X FINAL: diametro acabado",
            "zStart": "Z INICIAL: face da peca",
            "zEnd": "Z FINAL: fim do diametro (posicao do ressalto, negativo)",
            "filletRadius": "raio de canto no pe do ressalto (0 = sem)",
            "chamferEntry": "chanfro 45 graus na ponta do X FINAL (0 = sem)",
            "chamferExit": "chanfro 45 graus no ressalto, no X INICIAL (0 = sem)",
            "roughingDOC": "profundidade de desbaste por passe (no raio)",
            "finishDOC": "sobremetal de acabamento (no raio)",
            "toolClearance": "afastamento G0",
            "useConstantSurface": "true = G96 com D (Vc constante)",
            "finishOnly": "true = so o passe de acabamento",
            "useCannedCycle": "true = desbaste com o ciclo G71 do LinuxCNC",
        })),
    "ID_TURN": dict(
        nome="DESBASTE INTERNO",
        resumo="Mandrilamento: abre o furo do X INICIAL (furo de partida) ao X FINAL, da face ate o Z FINAL.",
        chaves=dict(COMUNS, **CORTE, **{
            "mode": "BASIC (so o furo) ou EXTENDED (furo com fundo, raio e face interna)",
            "initialX": "X INICIAL: diametro do furo de partida (pre-furo)",
            "finalX": "X FINAL: diametro acabado do furo",
            "zStart": "Z INICIO: face da peca",
            "zEnd": "Z FIM: fundo do furo (negativo)",
            "chamferSize": "chanfro 45 graus na boca do furo (0 = sem)",
            "idRoughDOC": "profundidade de desbaste por passe (no raio)",
            "finishDOC": "sobremetal de acabamento",
            "toolClearance": "afastamento G0",
            "filletRadius": "EXTENDED: raio de canto no fundo",
            "pilotEnd": "EXTENDED: Z do fim do furo piloto",
            "faceRoughDOC": "EXTENDED: profundidade por passe no faceamento interno",
            "finishOnly": "true = so o passe de acabamento",
            "useCannedCycle": "true = desbaste com o ciclo G71 (so no BASIC)",
        })),
    "DRILL": dict(
        nome="FURAR",
        resumo="Furacao no centro (X0) do Z INICIAL ate o Z FINAL.",
        chaves=dict(COMUNS, **{
            "drillDiameter": "diametro da broca (mm)",
            "furoDeCentro": "true = furo de centro (broca de centro): sempre G81, sem bicada nem espera",
            "material": "ACO, INOX ou ALUMINIO (para a tabela de corte)",
            "usarTabela": "true = RPM, avanco e bicada pela tabela de furacao (material + diametro)",
            "zStart": "Z INICIAL: aproximacao (face)",
            "zEnd": "Z FINAL: profundidade (negativo)",
            "peckDepth": "PASSO (Q): bicada em mm; 0 = fura direto (G81)",
            "dwellSeconds": "tempo de espera no fundo, s",
            "roughingSFM": "ROTACAO em RPM (G97)",
            "maxSpindleRPM": "RPM maxima",
            "roughingFPR": "avanco, mm/volta",
            "toolClearance": "afastamento G0",
            "useCannedCycle": "sempre ligado pela regra da oficina: furacao sai em ciclo "
                              "(G81 direto, G82 com espera, G83 com bicada)",
        })),
    "CHAMFER": dict(
        nome="CHANFRO / RAIO",
        resumo="Chanfro ou raio numa aresta existente, externo ou interno.",
        chaves=dict(COMUNS, **CORTE, **{
            "mode": "CHAMFER ou RADIUS",
            "side": "OD (externo) ou ID (interno)",
            "x": "X: diametro da aresta",
            "zStart": "Z INICIAL: face",
            "zEnd": "Z FINAL: fim do chanfro/raio em Z (negativo)",
            "chamferAngle": "angulo do chanfro em graus (CHAMFER)",
            "roughingDOC": "passe de desbaste",
            "finishDOC": "passe de acabamento",
            "toolClearance": "afastamento G0",
            "finishOnly": "true = so o passe de acabamento",
        })),
    "GROOVE": dict(
        nome="CANAL / CORTE",
        resumo="Canal (GROOVE) entre o Z INICIO e o Z FIM, ou corte/sangria (PART) no Z INICIO.",
        chaves=dict(COMUNS, **CORTE, **{
            "mode": "GROOVE (canal) ou PART (corte)",
            "initialX": "X INICIAL: diametro da peca",
            "finalX": "X FINAL: diametro do fundo do canal (no corte, ate onde corta)",
            "zStart": "Z INICIO: lado do canal / posicao do corte",
            "zEnd": "Z FIM: outro lado do canal (GROOVE)",
            "toolWidth": "largura da ferramenta (pastilha)",
            "roughingDOC": "profundidade por nivel (GROOVE)",
            "finishDOC": "sobremetal de acabamento (GROOVE)",
            "plungeFPR": "avanco de mergulho, mm/volta",
            "retract": "retracao entre bicadas (PART)",
            "peck": "incremento por bicada no raio (PART)",
            "edgeBreak": "largura do quebra-canto 45 graus (PART, 0 = sem)",
            "toolClearance": "afastamento G0",
            "finishOnly": "true = so o acabamento (GROOVE)",
        })),
    "THREAD": dict(
        nome="ROSCA",
        resumo="Rosca externa ou interna pela tabela (metrica, polegada ou NPT).",
        chaves=dict(COMUNS, **{
            "rosca": "nome da rosca na tabela (use buscar_rosca), ex. 'M12 x 1.75'",
            "side": "EXTERNAL ou INTERNAL",
            "zStart": "INICIO Z: entrada (acima da face)",
            "zEnd": "FIM Z: fim da rosca (negativo)",
            "clearance": "afastamento G0",
            "springPasses": "passes de mola",
            "minorDiameter": "diametro menor (0 = automatico)",
            "depthOfCut": "PROFUNDIDADE DE CORTE: profundidade do 1o passe, que sai como o J do G76, "
                          "em diametro (G7); os passes seguintes reduzem com area constante. 0 = automatico",
            "spindleRPM": "rotacao G97 (a tabela ja sugere)",
            "useCannedCycle": "true = ciclo G76 com saida em rampa de 1 passo (L2), sem canal de saida; nao vale para NPT",
        })),
}

# chaves de processo que podem vir do que esta na aba GERAR PGM agora
_PROCESSO = ("toolNumber", "workOffset", "spindleDir", "coolant", "roughingSFM",
             "finishingSFM", "maxSpindleRPM", "roughingFPR", "finishingFPR",
             "toolClearance", "roughingDOC", "finishDOC", "idRoughDOC", "faceRoughDOC",
             "toolWidth", "plungeFPR", "retract", "peck", "edgeBreak", "springPasses",
             "clearance", "useConstantSurface", "material")


def _estado_da_aba():
    """Parametros salvos pela aba GERAR PGM (torno_cam_ui.json)."""
    try:
        from torno_cam_ui import state
        return (state.load_state() or {}).get("params", {}) or {}
    except Exception:
        return {}


def _tipo(nome):
    chave = re.sub(r"[^A-Z_]", "", unicodedata.normalize("NFKD", str(nome or ""))
                   .encode("ascii", "ignore").decode().upper().replace(" ", "_").replace("/", "_"))
    if chave not in TIPOS:
        raise ValueError(u"tipo de operacao desconhecido: {!r}. Use: {}".format(
            nome, ", ".join(sorted(OPERACOES))))
    return TIPOS[chave]


def _normaliza_rosca(texto):
    t = str(texto or "").upper().replace(",", ".").replace("X", " X ")
    return re.sub(r"\s+", " ", t).strip()


def _acha_rosca(nome):
    alvo = _normaliza_rosca(nome)
    for it in roscas.todas():
        if _normaliza_rosca(it["nome"]) == alvo:
            return it
    return None


def preparar(tipo, parametros, estado=None):
    """Monta os params de uma operacao como a aba GERAR PGM monta: defaults,
    processo da aba, o que o agente pediu e as chaves que os formularios
    acrescentam no collect(). Devolve (op_key, params)."""
    op = _tipo(tipo)
    pedido = dict(parametros or {})
    validas = set(OPERACOES[op]["chaves"])
    estranhas = sorted(k for k in pedido if k not in validas)
    if estranhas:
        raise ValueError(u"parametros desconhecidos em {}: {}. Validos: {}".format(
            op, ", ".join(estranhas), ", ".join(sorted(validas))))

    chave_defaults = "THREAD_EXTERNAL" if op == "THREAD" else op
    p = default_params(chave_defaults)
    salvo = (estado if estado is not None else _estado_da_aba()).get(chave_defaults) or {}
    for k in _PROCESSO:
        if k in salvo and salvo[k] is not None:
            p[k] = salvo[k]
    # o que vem do estado da aba nunca liga ciclo/opcoes sem o agente pedir
    for k in ("finishOnly", "useCannedCycle", "pausaNoFinal", "ferramentaFinal"):
        p[k] = False
    p["afastamentoFinalZAbs"] = None
    p["afastamentoFinalXAbs"] = None

    rosca = pedido.pop("rosca", None)
    usar_tabela = bool(pedido.pop("usarTabela", False))
    furo_de_centro = bool(pedido.pop("furoDeCentro", False))
    p.update(pedido)

    if op == "FACE":
        # Regra do Edson: o faceamento termina SEMPRE em Z0 e o sobremetal e'
        # para mais, no Z INICIAL (facear 3 mm = Z3 ate Z0).
        if "zEnd" not in pedido:
            p["zEnd"] = 0.0
        if abs(float(p["zEnd"])) > 1e-9:
            raise ValueError(u"no faceamento o Z FINAL e' sempre 0 (a face acabada e' o zero "
                             u"peca); o sobremetal vai no Z INICIAL, positivo. Ex.: facear 3 mm "
                             u"= zStart 3, zEnd 0")
        if float(p["zStart"]) <= 0:
            raise ValueError(u"no faceamento o Z INICIAL e' o sobremetal, positivo (ex.: facear "
                             u"3 mm = zStart 3). Pergunte ao operador quanto facear")
        p["finishOnlyManual"] = True
        p["cicloLinuxCNC"] = True
    elif op == "OD_TURN":
        p["cicloLinuxCNC"] = True
    elif op == "ID_TURN":
        p["finishOnlyManual"] = True
        p["cicloLinuxCNC"] = True
        p["useConstantSurface"] = True
        if p.get("mode") == "EXTENDED":
            p["useCannedCycle"] = False
    elif op == "DRILL":
        # Regra do Edson: furacao SEMPRE em ciclo (G81 direto, G82 com espera,
        # G83 com bicada), nunca linha a linha.
        p["useCannedCycle"] = True
        if usar_tabela:
            t = furacao.parametros(str(p.get("material", "ACO")).upper(), float(p["drillDiameter"]))
            p["roughingSFM"] = t["rpm"]
            p["roughingFPR"] = t["avanco"]
            if "peckDepth" not in pedido:
                p["peckDepth"] = t["bicada"]
        if furo_de_centro:
            # Regra do Edson: furo de centro e' sempre G81 (quebra-cavaco 0,
            # sem espera no fundo), mesmo que a tabela sugira bicada
            p["peckDepth"] = 0.0
            p["dwellSeconds"] = 0
        p["finishingSFM"] = p["roughingSFM"]
        p["forcePeckCycle"] = True
    elif op == "CHAMFER":
        p["fixArcOvercut"] = True
        p["chamferLength"] = abs(p.get("zEnd", 0) - p.get("zStart", 0))
    elif op == "GROOVE":
        p["compensarLargura"] = True
        p["quebraCantoDesenho"] = True
        p["grooveWidth"] = abs(p.get("zEnd", 0) - p.get("zStart", 0))
        p["useCannedCycle"] = False           # G75 nao existe no LinuxCNC
        if p.get("mode") == "PART":
            p["finishOnly"] = False
    elif op == "THREAD":
        if rosca:
            it = _acha_rosca(rosca)
            if it is None:
                raise ValueError(u"rosca {!r} nao esta na tabela; use buscar_rosca".format(rosca))
            _aplicar_rosca(p, it)
        p["taperTrueAngle"] = True
        p["passes"] = 0                       # como na tela: sai da profundidade
        interna = str(p.get("side", "EXTERNAL")).upper() in ("INTERNAL", "ID")
        p["threadDepthFactor"] = roscas.altura_filete(p.get("tabela"), interna)
        p["side"] = "INTERNAL" if interna else "EXTERNAL"
        p["operationType"] = "THREAD_INTERNAL" if interna else "THREAD_EXTERNAL"
        if p.get("xEnd") != p.get("xStart"):
            p["useCannedCycle"] = False       # G76 nao faz conicidade

    p["toolOffset"] = p.get("toolNumber", 1)
    if op != "THREAD":
        p["operationType"] = op
    return op, p


def _aplicar_rosca(p, it):
    """Igual ao _aplicar_rosca do thread_panel: titulo, tipo, passo, RPM e X
    pelo lado (externa = diametro nominal, interna = D1), NPT conica."""
    interna = str(p.get("side", "EXTERNAL")).upper() in ("INTERNAL", "ID")
    p["title"] = it["titulo"]
    p["threadType"] = "imperial" if it.get("tpi") else "metric"
    p["pitch"] = it["passo"]
    p["tpi"] = it.get("tpi") or 0.0
    p["spindleRPM"] = it["rpm"]
    p["xStart"], p["xEnd"], p["taperAngle"] = roscas.extremos(
        it, interna, p["zStart"], p["zEnd"])
    p["rosca"] = it["nome"]
    p["tabela"] = it["tabela"]


def montar(titulo, operacoes, estado=None):
    """Monta o programa inteiro. Devolve (gcode, resumo das operacoes)."""
    if not operacoes:
        raise ValueError(u"nenhuma operacao")
    entradas, resumo = [], []
    for i, o in enumerate(operacoes, 1):
        if not isinstance(o, dict) or "tipo" not in o:
            raise ValueError(u"operacao {}: use {{\"tipo\": ..., \"parametros\": {{...}}}}".format(i))
        op, p = preparar(o["tipo"], o.get("parametros") or {}, estado)
        rotulo = p.get("title") or OPERACOES[op]["nome"]
        try:
            entradas.append(entry_from_nodes(rotulo, build_nodes(SimpleNamespace(**p))))
        except (EngineError, ValueError, NotImplementedError) as e:
            raise ValueError(u"operacao {} ({}): {}".format(i, OPERACOES[op]["nome"], e))
        resumo.append(u"{}. {} - {} - T{:02d} {}".format(
            i, OPERACOES[op]["nome"], rotulo, int(p["toolNumber"]), p.get("workOffset", "")))
    titulo = titulo or entradas[0].title
    gcode = assemble_program(ProgramConfig(title=titulo, unitSystem="metric", feedMode="REV"),
                             entradas, LinuxCNCDinoPost())
    return gcode, resumo


# ── validacao no interpretador do LinuxCNC ───────────────────────────────────
def _ini():
    ini = os.environ.get("INI_FILE_NAME")
    if ini and os.path.isfile(ini):
        return ini
    return os.path.join(_RAIZ, "Dino_Evo.ini")


def _tabela_ferramentas(ini):
    try:
        import linuxcnc
        t = linuxcnc.ini(ini).find("EMCIO", "TOOL_TABLE")
    except Exception:
        t = None
    t = t or "tool.tbl"
    return t if os.path.isabs(t) else os.path.join(os.path.dirname(ini), t)


_MOV = re.compile(r"(STRAIGHT_FEED|STRAIGHT_TRAVERSE|ARC_FEED)\(([^)]*)\)")
_ERRO = re.compile(r"error|nested|not possible|unknown|cannot|invalid|unspecified", re.I)


def validar(gcode):
    """Roda o rs274 (interpretador do LinuxCNC) no programa. Devolve
    (ok, mensagem, limites) com os limites dos cortes em X (diametro) e Z."""
    ini = _ini()
    fd, caminho = tempfile.mkstemp(suffix=".ngc")
    with os.fdopen(fd, "w") as f:
        f.write(gcode if gcode.endswith("\n") else gcode + "\n")
    try:
        r = subprocess.run(["rs274", "-g", "-i", ini, "-t", _tabela_ferramentas(ini), caminho],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=60,
                           cwd=os.path.dirname(ini))
    except FileNotFoundError:
        return True, u"rs274 nao encontrado: validacao pulada", None
    except subprocess.TimeoutExpired:
        return False, u"o interpretador demorou demais (programa travado?)", None
    finally:
        os.unlink(caminho)
    saida = r.stdout.decode("utf-8", "replace")
    erros = [l.strip() for l in saida.splitlines()
             if _ERRO.search(l) and "COMMENT" not in l]
    xs, zs = [], []
    for l in saida.splitlines():
        m = _MOV.search(l)
        if m and m.group(1) != "STRAIGHT_TRAVERSE":
            v = [float(a) for a in m.group(2).split(",")[:3]]
            xs.append(v[0] * 2.0)      # canonico em raio
            zs.append(v[2])
    limites = None
    if xs:
        limites = {"X_min": round(min(xs), 3), "X_max": round(max(xs), 3),
                   "Z_min": round(min(zs), 3), "Z_max": round(max(zs), 3)}
    if erros:
        return False, u"; ".join(erros[:3]), limites
    return True, u"ok", limites


# ── ferramentas ──────────────────────────────────────────────────────────────
def listar_operacoes():
    estado = _estado_da_aba()
    blocos = []
    for op, d in OPERACOES.items():
        base = default_params("THREAD_EXTERNAL" if op == "THREAD" else op)
        salvo = estado.get("THREAD_EXTERNAL" if op == "THREAD" else op) or {}
        linhas = [u"## {} (tipo: {})".format(d["nome"], op), d["resumo"]]
        for k, desc in d["chaves"].items():
            atual = salvo.get(k) if k in _PROCESSO and k in salvo else base.get(k)
            linhas.append(u"- {}: {} (atual: {})".format(k, desc, json.dumps(atual, ensure_ascii=False)))
        blocos.append("\n".join(linhas))
    return ("Unidades: mm, X em DIAMETRO (G7), Z0 na face, Z negativo entra na peca. "
            "Ferramenta negativa (lado -X): todos os X da operacao negativos (X INICIAL, "
            "X FINAL, X do chanfro); a rosca nao aceita X negativo. "
            "Faceamento: Z FINAL sempre 0, sobremetal positivo no Z INICIAL. "
            "Furacao: sempre em ciclo (G81/G82/G83); furo de centro = furoDeCentro true, sempre G81. "
            "Valores 'atual' sao os da aba GERAR PGM; use-os quando o operador nao disser.\n\n"
            + "\n\n".join(blocos)), False


def buscar_rosca(texto, tabela=None):
    alvo = _normaliza_rosca(texto)
    numero = re.findall(r"[\d.]+", alvo)
    achadas = []
    for it in roscas.todas():
        if tabela and it["tabela"] != str(tabela).upper():
            continue
        nome = _normaliza_rosca(it["nome"])
        if alvo in nome or (numero and nome.startswith(("M" + numero[0] + " ", numero[0]))):
            achadas.append(it)
    if not achadas:
        return u"Nenhuma rosca encontrada para {!r}. Tabelas: METRICA, POLEGADA, NPT.".format(texto), False
    linhas = [u"- {nome}: passo {passo} mm, diametro {bitola} mm, crista da interna {menor} mm, "
              u"broca {broca} mm, RPM {rpm} ({tabela}, {tipo})".format(**it) for it in achadas[:15]]
    return u"Roscas encontradas (use o 'nome' exato no parametro rosca):\n" + "\n".join(linhas), False


def sugerir_furacao(material, diametro):
    t = furacao.parametros(str(material).upper(), float(diametro))
    return (u"Tabela de furacao ({} broca {} mm, HSS com refrigeracao): RPM {}, avanco {} mm/volta, "
            u"bicada {} mm".format(str(material).upper(), diametro, t["rpm"], t["avanco"], t["bicada"])), False


def gerar_programa(titulo="", operacoes=None):
    try:
        gcode, resumo = montar(titulo, operacoes)
    except ValueError as e:
        return u"Nao gerei: {}".format(e), True
    ok, msg, lim = validar(gcode)
    texto = [u"Programa gerado ({} linhas).".format(gcode.count("\n") + 1)]
    texto += resumo
    texto.append(u"Validacao no LinuxCNC: {}".format(u"OK" if ok else u"ERRO: " + msg))
    if lim:
        texto.append(u"Limites dos cortes: X {X_min} a {X_max} (diametro), Z {Z_min} a {Z_max}".format(**lim))
    texto.append(u"\n" + gcode)
    return u"\n".join(texto), not ok


def salvar_programa(titulo="", operacoes=None):
    try:
        gcode, resumo = montar(titulo, operacoes)
    except ValueError as e:
        return u"Nao salvei: {}".format(e), True
    ok, msg, lim = validar(gcode)
    if not ok:
        return u"Nao salvei: o LinuxCNC recusou o programa: {}".format(msg), True
    from torno_cam_ui import state
    pasta = os.environ.get("AGENTE_PASTA_PROGRAMAS") or state.program_prefix()
    os.makedirs(pasta, exist_ok=True)
    nome = titulo or (operacoes[0].get("parametros") or {}).get("title") or "programa"
    caminho = state.unique_path(pasta, state.sanitize_filename(nome))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(gcode + "\n")
    linhas = [u"Programa validado e salvo.", MARCA_ARQUIVO + " " + caminho] + resumo
    if lim:
        linhas.append(u"Limites dos cortes: X {X_min} a {X_max}, Z {Z_min} a {Z_max}".format(**lim))
    linhas.append(u"A aba carrega o arquivo no LinuxCNC sozinha (sem dar partida no ciclo).")
    return u"\n".join(linhas), False


_OPS_SCHEMA = {
    "type": "array", "minItems": 1,
    "description": "Operacoes na ordem de usinagem.",
    "items": {"type": "object", "required": ["tipo"], "properties": {
        "tipo": {"type": "string", "description": "FACE, OD_TURN, ID_TURN, DRILL, CHAMFER, GROOVE ou THREAD"},
        "parametros": {"type": "object", "description": "Chaves da operacao (ver listar_operacoes). "
                       "O que nao for informado vem da aba GERAR PGM."},
    }},
}

FERRAMENTAS = [
    dict(nome="listar_operacoes", funcao=listar_operacoes,
         descricao="Lista as operacoes do gerador do torno, os parametros de cada uma (com unidade e "
                   "valor atual da aba GERAR PGM) e as convencoes de eixo. Chame antes de montar.",
         esquema={"type": "object", "properties": {}}),
    dict(nome="buscar_rosca", funcao=buscar_rosca,
         descricao="Procura roscas nas tabelas (metrica, polegada UNC/UNF, NPT). Ex.: 'M12', 'M12x1.5', '1/2 UNC'.",
         esquema={"type": "object", "required": ["texto"], "properties": {
             "texto": {"type": "string"},
             "tabela": {"type": "string", "description": "METRICA, POLEGADA ou NPT (opcional)"}}}),
    dict(nome="sugerir_furacao", funcao=sugerir_furacao,
         descricao="RPM, avanco e bicada da tabela de furacao para material e diametro de broca.",
         esquema={"type": "object", "required": ["material", "diametro"], "properties": {
             "material": {"type": "string", "description": "ACO, INOX ou ALUMINIO"},
             "diametro": {"type": "number"}}}),
    dict(nome="gerar_programa", funcao=gerar_programa,
         descricao="Monta o programa pelo gerador do torno, valida no interpretador do LinuxCNC e "
                   "devolve o G-code, o resumo e os limites dos cortes. Nao salva.",
         esquema={"type": "object", "required": ["operacoes"], "properties": {
             "titulo": {"type": "string", "description": "nome do programa e do arquivo"},
             "operacoes": _OPS_SCHEMA}}),
    dict(nome="salvar_programa", funcao=salvar_programa,
         descricao="Remonta o programa com as mesmas operacoes, valida e salva o .ngc na pasta de "
                   "programas do LinuxCNC (nunca sobrescreve). A aba AGENTE IA carrega o arquivo.",
         esquema={"type": "object", "required": ["operacoes"], "properties": {
             "titulo": {"type": "string"},
             "operacoes": _OPS_SCHEMA}}),
]
