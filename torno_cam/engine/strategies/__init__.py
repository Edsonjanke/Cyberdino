"""Estrategias de torno + dispatcher build_nodes()."""

from .face import generate_face
from .drill import generate_drill
from .od_turn import generate_od_turn
from .id_turn import generate_id_turn
from .chamfer import generate_chamfer
from .groove import generate_groove
from .thread import generate_thread


class EngineError(Exception):
    """Erro de geracao com mensagem em PT-BR para exibir na UI."""


def build_nodes(p):
    """Despacha um params (SimpleNamespace/objeto com atributos) para a
    estrategia certa e retorna a lista de nos. Espelha o switch do
    gcode.handler.ts."""
    op = p.operationType
    if op == "FACE":
        return generate_face(p)
    if op == "OD_TURN":
        return generate_od_turn(p).nodes
    if op == "ID_TURN":
        return generate_id_turn(p).nodes
    if op == "CHAMFER":
        return generate_chamfer(p)
    if op == "GROOVE":
        return generate_groove(p)
    if op == "DRILL":
        return generate_drill(p)
    if op in ("THREAD_EXTERNAL", "THREAD_INTERNAL"):
        return generate_thread(p)
    raise EngineError("Operacao '{}' ainda nao implementada".format(op))


__all__ = ["build_nodes", "EngineError", "generate_face", "generate_drill",
           "generate_od_turn", "generate_id_turn", "generate_chamfer", "generate_groove",
           "generate_thread"]
