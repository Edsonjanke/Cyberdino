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
CONICA = "CONICA"          # NPT: rosca conica, 1:16 no diametro

# cores usadas pela UI (pedido do usuario). A conica ganhou cor propria
# porque nao e' "mais fina" nem "mais grossa" — e' outra coisa, e sai com
# X inicial diferente do X final.
COR = {PADRAO: "#4caf50", FINO: "#ffd600", CONICA: "#40C4FF"}

# ── POLEGADA: serie unificada UNC (grossa) e UNF (fina) ──────────────────────
# (nome nominal, diametro em polegada, fios/pol UNC, fios/pol UNF)
UNIFICADA = [
    (u"#6",     0.1380, 32,  40),
    (u"#8",     0.1640, 32,  36),
    (u"#10",    0.1900, 24,  32),
    (u"#12",    0.2160, 24,  28),
    (u"1/4",    0.2500, 20,  28),
    (u"5/16",   0.3125, 18,  24),
    (u"3/8",    0.3750, 16,  24),
    (u"7/16",   0.4375, 14,  20),
    (u"1/2",    0.5000, 13,  20),
    (u"9/16",   0.5625, 12,  18),
    (u"5/8",    0.6250, 11,  18),
    (u"3/4",    0.7500, 10,  16),
    (u"7/8",    0.8750,  9,  14),
    (u"1",      1.0000,  8,  12),
    (u"1.1/8",  1.1250,  7,  12),
    (u"1.1/4",  1.2500,  7,  12),
    (u"1.3/8",  1.3750,  6,  12),
    (u"1.1/2",  1.5000,  6,  12),
    (u"1.3/4",  1.7500,  5, None),
    (u"2",      2.0000,  4.5, None),
]

# ── NPT: conica, 1:16 no diametro (1.7899 graus por lado) ────────────────────
# (nome, fios/pol, E0 = diametro primitivo na ponta do tubo [pol],
#  L2 = comprimento util da rosca [pol], broca de referencia [pol])
# E0 e L2 sao da ASME B1.20.1. O diametro MAIOR na ponta sai de E0 + 0.8/n
# (altura do filete NPT = 0.8 x passo).
NPT_TABELA = [
    (u"1/16",   27,   0.27118, 0.2611, 0.2500),
    (u"1/8",    27,   0.36351, 0.2639, 0.3390),
    (u"1/4",    18,   0.47739, 0.4018, 0.4375),
    (u"3/8",    18,   0.61201, 0.4078, 0.5781),
    (u"1/2",    14,   0.75843, 0.5337, 0.7188),
    (u"3/4",    14,   0.96768, 0.5457, 0.9219),
    (u"1",      11.5, 1.21363, 0.6828, 1.1563),
    (u"1.1/4",  11.5, 1.55713, 0.7068, 1.5000),
    (u"1.1/2",  11.5, 1.79609, 0.7235, 1.7344),
    (u"2",      11.5, 2.26902, 0.7565, 2.2188),
    (u"2.1/2",  8,    2.71953, 1.1375, 2.6250),
    (u"3",      8,    3.34062, 1.2000, 3.2500),
    (u"4",      8,    4.33438, 1.3000, 4.2500),
]

POLEGADA_MM = 25.4
CONICIDADE_NPT = 1.0 / 16.0    # mm de diametro por mm de comprimento

# identificadores das tabelas (o que a UI mostra no seletor)
TAB_METRICA, TAB_POLEGADA, TAB_NPT = "METRICA", "POLEGADA", "NPT"
TABELAS = [(u"Metrica", TAB_METRICA),
           (u"Polegada UNC/UNF", TAB_POLEGADA),
           (u"NPT (conica)", TAB_NPT)]

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


def _itens_metricos():
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
                tabela=TAB_METRICA,
                tpi=0.0,
                comentario=u"Padrao" if tipo == PADRAO else u"Fina",
                conicidade=0.0,
            ))
    return itens


def _itens_polegada():
    """UNC (grossa, verde) e UNF (fina, amarela).

    O passo em mm sai de 25.4/fios — e' ele que o torno usa, mas o campo
    'fios/pol' tambem vai preenchido porque e' assim que a rosca e' chamada.
    """
    itens = []
    for nome, pol, unc, unf in UNIFICADA:
        for fios, tipo, serie in ((unc, PADRAO, u"UNC"), (unf, FINO, u"UNF")):
            if not fios:
                continue
            bitola = round(pol * POLEGADA_MM, 4)
            passo = round(POLEGADA_MM / fios, 4)
            # bitola numerada (#6, #10) nao leva aspas de polegada
            chamada = nome if nome.startswith(u"#") else nome + u'"'
            itens.append(dict(
                nome=u'%s - %g %s' % (chamada, fios, serie),
                bitola=bitola,
                passo=passo,
                tipo=tipo,
                broca=round(bitola - passo, 3),
                rpm=rpm_sugerido(bitola),
                titulo=u'Rosca %s - %g %s' % (chamada, fios, serie),
                tabela=TAB_POLEGADA,
                tpi=float(fios),
                comentario=serie,
                conicidade=0.0,
            ))
    return itens


def _itens_npt():
    """NPT: conica 1:16 no diametro.

    'bitola' e' o diametro MAIOR na ponta do tubo (onde a rosca comeca);
    'conicidade' diz quanto o diametro cresce por mm ao entrar na peca.
    Quem calcula o X final e' o painel, que sabe o comprimento da rosca.
    """
    itens = []
    for nome, fios, e0, l2, furo in NPT_TABELA:
        passo = round(POLEGADA_MM / fios, 4)
        maior = round((e0 + 0.8 / fios) * POLEGADA_MM, 4)   # filete NPT = 0.8p
        itens.append(dict(
            nome=u'NPT %s" - %g' % (nome, fios),
            bitola=maior,
            passo=passo,
            tipo=CONICA,
            broca=round(furo * POLEGADA_MM, 3),
            rpm=rpm_sugerido(maior),
            titulo=u'Rosca NPT %s" - %g' % (nome, fios),
            tabela=TAB_NPT,
            tpi=float(fios),
            comentario=u"Conica 1:16",
            conicidade=CONICIDADE_NPT,
            comprimento=round(l2 * POLEGADA_MM, 2),   # comprimento util padrao
        ))
    return itens


def lista(tabela=TAB_METRICA):
    """Roscas da tabela pedida.

    Cada item: dict(nome, bitola, passo, tipo, broca, rpm, titulo, tabela,
    tpi, comentario, conicidade). Metrica vem em ordem de bitola, com o
    passo padrao antes dos finos.
    """
    if tabela == TAB_POLEGADA:
        return _itens_polegada()
    if tabela == TAB_NPT:
        return _itens_npt()
    return _itens_metricos()


def todas():
    """Todas as tabelas juntas — usado para reencontrar uma rosca salva."""
    return _itens_metricos() + _itens_polegada() + _itens_npt()


def x_final_conico(item, z_inicial, z_final):
    """Diametro no fim da rosca conica (o X do outro extremo).

    O diametro cresce ao entrar na peca: 1:16 quer dizer 1 mm de diametro a
    cada 16 mm. Sem isso a NPT sairia cilindrica e nao vedaria."""
    conic = item.get("conicidade") or 0.0
    if not conic:
        return item["bitola"]
    return round(item["bitola"] + abs(z_final - z_inicial) * conic, 4)


def buscar(nome):
    for it in todas():
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
