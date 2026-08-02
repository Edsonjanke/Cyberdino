"""Montagem do programa — port de gcode.handler.ts (extracao do TOOL_CALL) +
TornoCAM/lib/generateTornoProgram.ts (um cabecalho / um M2 para varias ops).

`entry_from_nodes` extrai o primeiro no TOOL_CALL da estrategia e o usa como
tool call da operacao (removendo-o dos nos, para nao sair duplicado). Isso
combina o comportamento single-op do handler com a montagem multi-op."""

from dataclasses import dataclass
from typing import List

from .nodes import ToolCall


@dataclass
class ProgramConfig:
    title: str = "PROGRAMA"
    unitSystem: str = "metric"      # 'metric' | 'imperial'
    feedMode: str = "REV"           # 'REV' | 'MIN'
    programNumber: int = 1000


@dataclass
class OperationEntry:
    title: str
    tool_call: ToolCall
    nodes: List[object]


def entry_from_nodes(title, nodes):
    """Constroi uma OperationEntry a partir dos nos de uma estrategia,
    extraindo o primeiro TOOL_CALL (igual ao POST_PROCESS do handler)."""
    idx = next((i for i, n in enumerate(nodes) if n.type == "TOOL_CALL"), -1)
    if idx >= 0:
        tool_call = nodes[idx]
        filtered = nodes[:idx] + nodes[idx + 1:]
    else:
        tool_call = ToolCall(toolNumber=1, toolOffset=1, description="")
        filtered = list(nodes)
    return OperationEntry(title=title, tool_call=tool_call, nodes=filtered)


def assemble_program(config, entries, post):
    """Gera o G-code final de um programa (varias operacoes, um cabecalho)."""
    return post.generate(config, entries)
