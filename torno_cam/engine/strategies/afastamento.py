# -*- coding: utf-8 -*-
"""AFASTAMENTO FINAL Z / X: posicao ABSOLUTA (no zero peca, X em diametro)
para onde a ferramenta vai no fim da operacao.

Vem depois da saida normal da operacao (a que usa o AFASTAMENTO G0), entao a
ferramenta ja saiu da peca: sobe em Z primeiro e depois vai em X, em G0, com
o comentario (Afastamento Final). Campo vazio (None), ou ausente como nos
goldens do EvoCAM, nao gera nada; 0 e' posicao valida (X0, Z0)."""

from ..jsutil import round4

CHAVE_Z = "afastamentoFinalZAbs"
CHAVE_X = "afastamentoFinalXAbs"


def _valor(p, chave):
    v = getattr(p, chave, None)
    if v is None or v == "":
        return None
    return float(v)


def aplicar(b, p):
    """Acrescenta (Afastamento Final), G0 Z e G0 X com o que foi preenchido."""
    z = _valor(p, CHAVE_Z)
    x = _valor(p, CHAVE_X)
    if z is None and x is None:
        return
    b.comment(u"Afastamento Final")
    if z is not None:
        b.rapid(z=round4(z))
    if x is not None:
        b.rapid(x=round4(x))
