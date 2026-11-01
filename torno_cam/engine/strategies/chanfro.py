# -*- coding: utf-8 -*-
"""Chanfro a 45 graus no passe de acabamento (Facear, Desbaste Int e Ext).

Handoff "telas de ciclo", secao 7.1: a ferramenta chega pela propria linha do
chanfro, prolongada FOLGA mm (no raio e em Z) para fora da peca, e o chanfro
sai no avanco de acabamento com o comentario (CHANFRO C X 45).

Com o campo em 0 (ou ausente, como nos goldens do EvoCAM) nada muda."""

from .erros import EngineError
from ..jsutil import js_num

# prolongamento da linha do chanfro para fora da peca (e = 1,0 mm)
FOLGA = 1.0


def tamanho(p, chave):
    """Valor do chanfro em mm; 0 quando o campo nao existe."""
    v = getattr(p, chave, 0) or 0
    v = float(v)
    if v < 0:
        raise EngineError(u"O chanfro não pode ser negativo.")
    return v


def comentario(c, nome=u""):
    """'CHANFRO 0.5 X 45' ou 'CHANFRO ENTRADA 0.5 X 45'."""
    meio = u" {}".format(nome) if nome else u""
    return u"CHANFRO{} {} X 45".format(meio, js_num(c))


def nao_cabe(nome, c, onde, limite):
    raise EngineError(
        u"{} de {} não cabe: {} tem só {}. Diminua o chanfro.".format(
            nome, js_num(c), onde, js_num(round(limite, 4))))
