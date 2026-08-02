# -*- coding: utf-8 -*-
"""Tabela de parametros de corte para FURACAO.

Brocas de 3,0 a 30,0 mm de 0,5 em 0,5 mm, para tres materiais.
Os valores sao para broca de ACO RAPIDO (HSS) com refrigeracao — o caso do
dia a dia da oficina. Com broca de metal duro da para subir bastante a
velocidade; ai e' so editar a tabela.

Como usar: a aba GERAR PGM (painel FURAR) tem o seletor de MATERIAL; ao
escolher o material ou mudar o diametro, os campos RPM, avanco e bicada sao
preenchidos por esta tabela.

Base de calculo (editavel em MATERIAIS):
  RPM     = Vc * 1000 / (pi * D)   limitado ao RPM maximo da maquina
  avanco  = fator * D              (mm por volta), com piso e teto
  bicada  = mult * D               (profundidade de cada bicada)

Os numeros de partida sao conservadores de proposito: e' mais barato subir
o avanco depois do que quebrar broca. Ajuste com o que a maquina aguentar.
"""

import math

# RPM maximo util da maquina (caixa de marchas: 2360 na marcha mais alta)
RPM_MAXIMO = 2360

MATERIAIS = {
    "ACO": dict(
        nome=u"Aco 1045",
        vc=25.0,            # m/min
        fator_avanco=0.018,  # mm/volta por mm de diametro
        avanco_min=0.05, avanco_max=0.45,
        mult_bicada=3.0,     # bicada = 3 x diametro
    ),
    "INOX": dict(
        nome=u"Inox 304",
        vc=14.0,
        fator_avanco=0.012,
        avanco_min=0.04, avanco_max=0.32,
        mult_bicada=2.0,     # inox encrua: bicada menor, sem esfregar
    ),
    "ALUMINIO": dict(
        nome=u"Aluminio",
        vc=70.0,
        fator_avanco=0.025,
        avanco_min=0.06, avanco_max=0.60,
        mult_bicada=4.0,
    ),
}

# ordem para o combo da UI
ORDEM = ("ACO", "INOX", "ALUMINIO")

DIAMETRO_MIN = 3.0
DIAMETRO_MAX = 30.0
PASSO_DIAMETRO = 0.5


def diametros():
    """3.0, 3.5, ... 30.0"""
    n = int(round((DIAMETRO_MAX - DIAMETRO_MIN) / PASSO_DIAMETRO)) + 1
    return [round(DIAMETRO_MIN + i * PASSO_DIAMETRO, 1) for i in range(n)]


def _clamp(v, minimo, maximo):
    return max(minimo, min(maximo, v))


def parametros(material, diametro):
    """Parametros de corte para (material, diametro da broca).

    Diametro fora da tabela e' limitado a faixa 3..30. Devolve sempre um dict
    com rpm (int), avanco (mm/volta) e bicada (mm)."""
    m = MATERIAIS.get(material) or MATERIAIS["ACO"]
    d = _clamp(float(diametro or DIAMETRO_MIN), DIAMETRO_MIN, DIAMETRO_MAX)

    rpm = m["vc"] * 1000.0 / (math.pi * d)
    rpm = int(round(_clamp(rpm, 1.0, RPM_MAXIMO)))

    avanco = _clamp(m["fator_avanco"] * d, m["avanco_min"], m["avanco_max"])
    bicada = m["mult_bicada"] * d

    return dict(rpm=rpm, avanco=round(avanco, 3), bicada=round(bicada, 1))


def tabela(material):
    """Lista [(diametro, rpm, avanco, bicada)] — util para conferir/imprimir."""
    return [(d,) + tuple(parametros(material, d)[k]
                         for k in ("rpm", "avanco", "bicada"))
            for d in diametros()]


def imprimir(material=None):
    """Mostra a tabela no terminal (conferencia rapida)."""
    for chave in ([material] if material else ORDEM):
        m = MATERIAIS[chave]
        print("\n=== %s (Vc %g m/min, HSS com refrigeracao) ==="
              % (m["nome"], m["vc"]))
        print("  Ø mm    RPM   avanco mm/v   bicada mm")
        for d, rpm, av, bic in tabela(chave):
            print("  %5.1f  %5d      %5.3f       %5.1f" % (d, rpm, av, bic))


if __name__ == "__main__":
    imprimir()
