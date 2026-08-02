#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Acha os retangulos brancos desenhados em volta de cada campo de um
`*-bg.png` do EvoCAM e imprime a tabela FIELDS pronta para colar no painel.

Por que existe: posicionar campo por campo no olho e' lento e impreciso. Como
o desenho ja tem a caixa de cada valor, da para medir e cair exatamente dentro.

USO
---
    python3 torno_cam_ui/tools/detecta_caixas.py <painel>

    <painel> = face | drill | chamfer | groove | idturn  (ver SEEDS abaixo)

Para um painel novo:
 1. copie a imagem:  cp Evo-CNC-Guia/apps/desktop/public/<x>-bg.png torno_cam_ui/images/
 2. abra o *Panel.tsx correspondente e copie a tabela POS/POSITIONS
    (top/left em % do container) para SEEDS aqui embaixo;
 3. confira o aspect ratio do container no TSX (IMG_W/IMG_H) e ponha em SEEDS;
 4. rode este script e cole a saida no painel Python.

Cuidado com o aspect ratio: quando o container do app NAO tem a mesma
proporcao da imagem (caso do faceamento), a imagem fica centrada com uma faixa
fina em cima/embaixo, e a conversao de % do container para fracao da imagem
precisa desse ajuste — e' o que `_conversor` faz.
"""

import json
import os
import sys

try:
    from PIL import Image
except ImportError:
    sys.exit("Precisa do Pillow: sudo apt install python3-pil")

AQUI = os.path.dirname(os.path.abspath(__file__))
IMAGENS = os.path.join(os.path.dirname(AQUI), "images")

LIMIAR = 110          # acima disso o pixel e' traco branco do desenho


# painel -> (arquivo, aspect ratio do container no app, {campo: (top%, left%)})
SEEDS = {
    "face": ("face-bg.png", 3500.0 / 1756.0, {
        "toolNumber": (2.22, 8.15), "zEnd": (10.54, 27.40),
        "initialX": (47.22, 5.73), "finalX": (46.30, 41.11),
        "zStart": (83.38, 30.39), "toolClearance": (4.95, 64.61),
        "roughingDOC": (15.85, 64.51), "finishDOC": (26.80, 64.55),
    }),
    "od": ("od-turn-bg.png", 1431.0 / 736.0, {
        "toolNumber": (5.42, 9.02), "zEnd": (11.16, 25.04),
        "initialX": (47.18, 6.66), "finalX": (46.80, 41.00),
        "filletRadius": (80.11, 18.41), "zStart": (90.18, 31.27),
        "toolClearance": (57.01, 68.32), "finishDOC": (67.41, 77.77),
        "roughingDOC": (77.42, 77.47),
    }),
    # desbaste interno: uma imagem por modo (mesmos campos, posicoes diferentes)
    "id_basic": ("id-turn-bg.png", 1454.0 / 720.0, {
        "toolNumber": (1.90, 7.75), "zStart": (10.50, 21.79),
        "zEnd": (20.60, 13.56), "finalX": (25.80, 37.90),
        "initialX": (78.20, 34.97), "idRoughDOC": (4.30, 81.83),
        "finishDOC": (15.60, 76.23), "toolClearance": (26.80, 71.70),
        "filletRadius": (78.20, 2.85), "pilotEnd": (89.20, 15.40),
        "faceRoughDOC": (78.20, 60.90),
    }),
    "id_ext": ("id-turn-ext-bg.png", 1440.0 / 720.0, {
        "toolNumber": (1.50, 7.56), "zStart": (10.30, 21.98),
        "zEnd": (20.40, 13.56), "finalX": (25.60, 38.09),
        "initialX": (78.00, 34.59), "idRoughDOC": (4.30, 81.73),
        "finishDOC": (15.60, 76.42), "toolClearance": (26.80, 71.70),
        "filletRadius": (78.20, 2.75), "pilotEnd": (89.20, 15.40),
        "faceRoughDOC": (78.20, 60.61),
    }),
    "cham_od": ("chamfer-od-bg.png", 1456.0 / 735.0, {
        "toolNumber": (2.60, 13.66), "zEnd": (12.0, 18.78), "zStart": (12.0, 31.5),
        "finishDOC": (17.90, 83.56), "roughingDOC": (24.9, 56.9),
        "chamferAngle": (37.40, 38.98), "x": (46.30, 5.65), "toolClearance": (48.3, 56.9),
    }),
    "cham_id": ("chamfer-id-bg.png", 1445.0 / 720.0, {
        "toolNumber": (1.04, 13.74), "zEnd": (10.8, 18.5), "zStart": (10.8, 31.6),
        "roughingDOC": (14.6, 66.1), "toolClearance": (24.4, 61.0), "x": (27.4, 4.9),
        "finishDOC": (50.6, 83.4), "chamferAngle": (55.8, 37.8),
    }),
    "rad_od": ("radius-od-bg.png", 1442.0 / 720.0, {
        "toolNumber": (1.8, 7.77), "zEnd": (11.3, 18.7), "zStart": (11.3, 31.7),
        "finishDOC": (17.1, 84.03), "roughingDOC": (24.3, 56.9),
        "x": (45.79, 5.57), "toolClearance": (47.6, 56.9),
    }),
    "rad_id": ("radius-id-bg.png", 1438.0 / 720.0, {
        "toolNumber": (2.2, 7.3), "zEnd": (11.7, 18.6), "zStart": (11.5, 31.6),
        "finishDOC": (17.4, 66.6), "roughingDOC": (17.4, 85.7),
        "toolClearance": (31.3, 69.2), "x": (45.4, 5.1), "chamferAngle": (45.4, 40.5),
    }),
    "groove": ("groove-bg.png", 1455.0 / 736.0, {
        "toolNumber": (1.63, 6.95), "toolWidth": (4.84, 69.37), "zStart": (11.82, 27.00),
        "roughingDOC": (16.22, 68.08), "finishDOC": (27.21, 61.88),
        "initialX": (46.41, 5.53), "finalX": (46.41, 40.28),
        "toolClearance": (60.96, 55.73), "zEnd": (82.64, 22.42),
    }),
    "part": ("corte.png", 1465.0 / 720.0, {
        "toolNumber": (1.77, 16.88), "zStart": (11.88, 26.80), "retract": (9.25, 67.04),
        "peck": (9.85, 80.79), "toolWidth": (28.40, 67.04), "initialX": (45.76, 5.42),
        "finalX": (46.07, 40.24), "toolClearance": (60.13, 55.88), "edgeBreak": (87.12, 71.97),
    }),
    "rosca_ext": ("thread-bg.png", 1450.0 / 720.0, {
        "toolNumber": (1.3, 7.91), "zEnd": (8.3, 17.2), "zStart": (8.3, 30.9),
        "clearance": (13.1, 48.8), "xStart": (29.0, 55.2), "spindleRPM": (22.73, 86.99),
        "depthOfCut": (52.1, 55.4), "tpi": (79.6, 74.1), "pitch": (79.23, 84.99),
        "xEnd": (89.2, 46.2), "leadInLength": (87.8, 18.1), "passes": (89.81, 71.35),
        "springPasses": (90.0, 95.0),
    }),
    "rosca_int": ("thread-internal-bg.png", 1456.0 / 731.0, {
        "toolNumber": (2.6, 8.43), "zEnd": (9.21, 17.96), "zStart": (9.4, 31.0),
        "clearance": (14.0, 48.6), "xEnd": (29.7, 54.8), "spindleRPM": (23.8, 85.63),
        "depthOfCut": (52.0, 55.1), "tpi": (78.4, 73.4), "pitch": (78.4, 84.8),
        "xStart": (87.7, 46.0), "leadInLength": (86.3, 18.5), "passes": (88.4, 70.37),
        "springPasses": (88.03, 92.92),
    }),
    "drill": ("drill-bg.png", 1440.0 / 720.0, {
        "toolNumber": (1.7, 7.3), "zStart": (5.8, 32.2),
        "toolClearance": (16.0, 46.5), "peckDepth": (23.3, 15.1),
        "drillDiameter": (53.0, 51.0), "roughingSFM": (27.4, 87.2),
        "dwellSeconds": (54.0, 87.1), "zEnd": (85.8, 20.1),
    }),
}


def _conversor(img_w, img_h, aspect_container):
    """(top%, left%) do container -> (x, y) em fracao da imagem.

    A imagem e' desenhada em 'contain' dentro do container. Se ela for mais
    larga que o container, encosta nas laterais e sobra faixa em cima/embaixo.
    """
    ar_img = float(img_w) / float(img_h)
    if ar_img > aspect_container:          # imagem mais larga: ajusta por largura
        escala_y = ar_img / aspect_container
        desloc_y = (escala_y - 1.0) / 2.0
        return lambda t, l: (l / 100.0, t / 100.0 * escala_y - desloc_y)
    escala_x = aspect_container / ar_img
    desloc_x = (escala_x - 1.0) / 2.0
    return lambda t, l: (l / 100.0 * escala_x - desloc_x, t / 100.0)


def detecta(caminho, seeds, aspect_container):
    im = Image.open(caminho).convert("L")
    W, H = im.size
    px = im.load()
    conv = _conversor(W, H, aspect_container)
    achados = {}
    def caixa_da_semente(sx, sy):
        """Varre para os 4 lados a partir da semente e devolve a caixa, ou None."""
        def varre(dx, dy, limite):
            x, y, n = sx, sy, 0
            while 0 < x < W - 1 and 0 < y < H - 1 and n < limite:
                x += dx
                y += dy
                n += 1
                if px[x, y] > LIMIAR:
                    return (x, y)
            return None

        esq = varre(-1, 0, int(0.25 * W))
        dir_ = varre(1, 0, int(0.25 * W))
        cima = varre(0, -1, int(0.20 * H))
        baixo = varre(0, 1, int(0.20 * H))
        if not all((esq, dir_, cima, baixo)):
            return None
        x0, x1, y0, y1 = esq[0], dir_[0], cima[1], baixo[1]
        larg, alt = x1 - x0, y1 - y0
        # descarta caixa implausivel (traco solto do desenho, nao um campo)
        if not (0.02 * W <= larg <= 0.22 * W and 0.03 * H <= alt <= 0.16 * H):
            return None
        return (x0 / W, y0 / H, larg / float(W), alt / float(H),
                "%dx%d" % (larg, alt))

    # A ancora do TSX e' o canto superior-esquerdo do CAMPO, que as vezes cai
    # alguns pixels FORA do retangulo desenhado. Por isso tentamos varias
    # sementes para dentro, em vez de depender de um unico deslocamento.
    OFFSETS = [(0.012, 0.025), (0.025, 0.025), (0.040, 0.030),
               (0.012, 0.045), (0.030, 0.050), (0.055, 0.035),
               (0.020, 0.015), (0.045, 0.060)]

    for nome, (top, left) in seeds.items():
        fx, fy = conv(top, left)
        achados[nome] = None
        for dx, dy in OFFSETS:
            sx = max(1, min(W - 2, int(fx * W) + int(dx * W)))
            sy = max(1, min(H - 2, int(fy * H) + int(dy * H)))
            r = caixa_da_semente(sx, sy)
            if r is not None:
                achados[nome] = r
                break
    return achados


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SEEDS:
        sys.exit("uso: detecta_caixas.py (%s)" % " | ".join(sorted(SEEDS)))
    painel = sys.argv[1]
    arquivo, aspect, seeds = SEEDS[painel]
    caminho = os.path.join(IMAGENS, arquivo)
    if not os.path.exists(caminho):
        sys.exit("nao achei %s (copie de Evo-CNC-Guia/apps/desktop/public/)" % caminho)

    achados = detecta(caminho, seeds, aspect)
    print("# %s — retangulos medidos em %s" % (painel.upper(), arquivo))
    print("# (chave, (x, y, largura, altura) em fracao da imagem, max_chars, opcoes)")
    print("FIELDS = [")
    for nome, v in achados.items():
        if v is None:
            print('    # %-14s NAO DETECTADO — ajuste a semente no SEEDS' % nome)
            continue
        print('    ("%s", (%.5f, %.5f, %.5f, %.5f), 7, {}),   # %s px'
              % (nome, v[0], v[1], v[2], v[3], v[4]))
    print("]")
    print()
    print("# Ajuste max_chars (o 7) para o maior valor que CADA campo recebe:")
    print("#   2 = numero de ferramenta | 4 = RPM/pausa | 5 = profundidade/folga")
    print("#   6-7 = coordenada X/Z. Quanto menor, MAIOR a fonte naquele campo.")
    faltando = [k for k, v in achados.items() if v is None]
    if faltando:
        print("\n# ATENCAO: nao detectados: %s" % ", ".join(faltando))
    return 0


if __name__ == "__main__":
    sys.exit(main())
