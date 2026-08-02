# -*- coding: utf-8 -*-
"""Tabela de roscas METRICAS ISO, de M2 a M50.

Para cada bitola: o passo PADRAO (grosso) e os passos FINOS.
Na UI o passo padrao aparece em VERDE e os finos em AMARELO — assim da para
escolher no toque sem ler tabela de bolso.

Ao escolher a rosca, o painel preenche:
  - passo
  - diametro: na EXTERNA o nominal; na INTERNA o furo (broca) antes de roscar
  - RPM sugerido (conservador; rosca em torno retrofit nao gosta de pressa)

Broca (furo antes de roscar) = D - passo. E' a regra de oficina, que da ~77%
de altura de filete — o que se usa na pratica, porque 100% quebra macho e nao
aumenta resistencia de forma util.
"""

import math

# bitola -> (passo padrao, [passos finos])
METRICA = {
    2.0:  (0.40, [0.25]),
    2.5:  (0.45, [0.35]),
    3.0:  (0.50, [0.35]),
    3.5:  (0.60, [0.35]),
    4.0:  (0.70, [0.50]),
    5.0:  (0.80, [0.50]),
    6.0:  (1.00, [0.75]),
    7.0:  (1.00, [0.75]),
    8.0:  (1.25, [1.00, 0.75]),
    9.0:  (1.25, [1.00, 0.75]),
    10.0: (1.50, [1.25, 1.00, 0.75]),
    11.0: (1.50, [1.00, 0.75]),
    12.0: (1.75, [1.50, 1.25, 1.00]),
    14.0: (2.00, [1.50, 1.25, 1.00]),
    16.0: (2.00, [1.50, 1.00]),
    18.0: (2.50, [2.00, 1.50, 1.00]),
    20.0: (2.50, [2.00, 1.50, 1.00]),
    22.0: (2.50, [2.00, 1.50, 1.00]),
    24.0: (3.00, [2.00, 1.50, 1.00]),
    27.0: (3.00, [2.00, 1.50, 1.00]),
    30.0: (3.50, [3.00, 2.00, 1.50, 1.00]),
    33.0: (3.50, [3.00, 2.00, 1.50]),
    36.0: (4.00, [3.00, 2.00, 1.50]),
    39.0: (4.00, [3.00, 2.00, 1.50]),
    42.0: (4.50, [4.00, 3.00, 2.00, 1.50]),
    45.0: (4.50, [4.00, 3.00, 2.00, 1.50]),
    48.0: (5.00, [4.00, 3.00, 2.00, 1.50]),
    50.0: (5.00, [4.00, 3.00, 2.00, 1.50]),
}

PADRAO = "PADRAO"
FINO = "FINO"

# cores usadas pela UI (pedido do usuario)
COR = {PADRAO: "#4caf50", FINO: "#ffd600"}

# Rosca em torno retrofit: sem pressa. Vc baixo e teto apertado, porque a
# ferramenta precisa sair do filete no fim de cada passe.
VC_ROSCA = 45.0      # m/min
RPM_MAXIMO = 700


def _nome(bitola, passo):
    b = ("%g" % bitola)
    return u"M%s x %g" % (b, passo)


def titulo(bitola, passo):
    """Titulo do programa: 'Rosca M8 X 1.25 mm'."""
    return u"Rosca M%g X %g mm" % (bitola, passo)


def broca(bitola, passo):
    """Diametro do furo antes de roscar (rosca interna)."""
    return round(bitola - passo, 3)


def rpm_sugerido(bitola):
    rpm = VC_ROSCA * 1000.0 / (math.pi * max(1.0, bitola))
    return int(round(max(40.0, min(RPM_MAXIMO, rpm))))


def lista():
    """Todas as roscas, em ordem de bitola; padrao antes dos finos.

    Cada item: dict(nome, bitola, passo, tipo, broca, rpm).
    """
    itens = []
    for bitola in sorted(METRICA):
        grosso, finos = METRICA[bitola]
        for passo, tipo in [(grosso, PADRAO)] + [(f, FINO) for f in finos]:
            itens.append(dict(
                nome=_nome(bitola, passo),
                bitola=bitola,
                passo=passo,
                tipo=tipo,
                broca=broca(bitola, passo),
                rpm=rpm_sugerido(bitola),
                titulo=titulo(bitola, passo),
            ))
    return itens


def buscar(nome):
    for it in lista():
        if it["nome"] == nome:
            return it
    return None


def imprimir():
    print("bitola   passo   tipo     broca   rpm")
    for it in lista():
        print("  %-9s %5.2f  %-7s %6.2f  %4d"
              % (it["nome"], it["passo"], it["tipo"], it["broca"], it["rpm"]))


if __name__ == "__main__":
    imprimir()
