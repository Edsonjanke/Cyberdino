# -*- coding: utf-8 -*-
"""Servidor MCP (Model Context Protocol) por stdio, sem dependencias.

O Debian 12 do torno nao tem o pacote `mcp` do Python; o protocolo e'
JSON-RPC 2.0, uma mensagem por linha no stdin/stdout, e so' precisamos de
quatro metodos: initialize, tools/list, tools/call e ping. As ferramentas
vem de `ferramentas.FERRAMENTAS`.

Uso (o Claude Code chama assim, pelo --mcp-config):
    python3 <config>/torno_cam/agente/servidor_mcp.py

Nada vai para o stdout alem das respostas: mensagens de diagnostico vao para
o stderr (o stdout e' o canal do protocolo).
"""

import json
import os
import sys
import traceback

# raiz do config no sys.path, para `import torno_cam...` rodando como script
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from torno_cam.agente.ferramentas import FERRAMENTAS  # noqa: E402

NOME = "torno"
VERSAO = "1.0.0"
PROTOCOLO_PADRAO = "2025-06-18"


def _resposta(id_, resultado):
    return {"jsonrpc": "2.0", "id": id_, "result": resultado}


def _erro(id_, codigo, mensagem):
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": codigo, "message": mensagem}}


def lista_de_ferramentas():
    return [{"name": f["nome"], "description": f["descricao"],
             "inputSchema": f["esquema"]} for f in FERRAMENTAS]


def chamar(nome, argumentos):
    """Executa uma ferramenta e devolve o resultado no formato do MCP."""
    f = next((f for f in FERRAMENTAS if f["nome"] == nome), None)
    if f is None:
        return {"content": [{"type": "text", "text": "Ferramenta desconhecida: " + nome}],
                "isError": True}
    try:
        texto, erro = f["funcao"](**(argumentos or {}))
    except TypeError as e:
        texto, erro = "Argumentos invalidos para {}: {}".format(nome, e), True
    except Exception as e:      # a ferramenta nao pode derrubar o servidor
        traceback.print_exc(file=sys.stderr)
        texto, erro = "Erro em {}: {}".format(nome, e), True
    return {"content": [{"type": "text", "text": texto}], "isError": bool(erro)}


def tratar(msg):
    """Uma mensagem JSON-RPC -> resposta (ou None para notificacoes)."""
    metodo = msg.get("method")
    id_ = msg.get("id")
    if id_ is None:             # notificacao (ex.: notifications/initialized)
        return None
    if metodo == "initialize":
        pedido = (msg.get("params") or {}).get("protocolVersion") or PROTOCOLO_PADRAO
        return _resposta(id_, {
            "protocolVersion": pedido,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": NOME, "version": VERSAO},
        })
    if metodo == "ping":
        return _resposta(id_, {})
    if metodo == "tools/list":
        return _resposta(id_, {"tools": lista_de_ferramentas()})
    if metodo == "tools/call":
        p = msg.get("params") or {}
        return _resposta(id_, chamar(p.get("name", ""), p.get("arguments") or {}))
    return _erro(id_, -32601, "Metodo nao suportado: {}".format(metodo))


def main(entrada=sys.stdin, saida=sys.stdout):
    for linha in entrada:
        linha = linha.strip()
        if not linha:
            continue
        try:
            msg = json.loads(linha)
        except ValueError:
            resp = _erro(None, -32700, "JSON invalido")
        else:
            resp = tratar(msg)
        if resp is not None:
            saida.write(json.dumps(resp, ensure_ascii=False) + "\n")
            saida.flush()


if __name__ == "__main__":
    main()
