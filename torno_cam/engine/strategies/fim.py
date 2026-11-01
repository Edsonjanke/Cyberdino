# -*- coding: utf-8 -*-
"""Fim da operacao, na ordem: AFASTAMENTO FINAL, CHAMAR FERRAMENTA NO FINAL e
USAR PAUSA NO FINAL. Vai depois da saida normal da estrategia (e do M5,
nas que desligam o fuso). Sem as opcoes, nada muda.

- Ferramenta: a da primeira operacao do programa (o program.py resolve).
- Pausa: (PAUSA NO FINAL), M5 e M0. O programa continua no CYCLE START."""

from . import afastamento


def aplicar(b, p):
    afastamento.aplicar(b, p)
    if getattr(p, "ferramentaFinal", False):
        b.comment(u"CHAMA FERRAMENTA NO FINAL")
        b.firstToolCall()
    if getattr(p, "pausaNoFinal", False):
        b.comment(u"PAUSA NO FINAL")
        if not b.spindle_stopped():
            b.spindleOff()
        b.pause()
