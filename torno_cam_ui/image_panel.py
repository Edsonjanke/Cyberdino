# -*- coding: utf-8 -*-
"""Painel conversational sobre imagem de fundo (estilo Fanuc/Tormach).

Reproduz FIELMENTE a geometria do EvoCAM para os campos cairem em cima dos
retangulos ja desenhados na imagem:

- um container com aspect ratio fixo 3500x1756 (o mesmo do app), centralizado
  na area disponivel;
- a imagem desenhada dentro do container em modo "contain" (a imagem real e
  um pouco mais larga, entao sobra uma faixa fina em cima/embaixo — reproduzir
  isso e justamente o que mantem o alinhamento);
- cada campo ancorado pelo CANTO SUPERIOR-ESQUERDO em (left%, top%) do
  container, com largura e fonte responsivas: clamp(largura_container * fator,
  minimo, maximo) — identico ao responsiveSize()/DragPos do app.
"""

import os

from qtpy.QtWidgets import QWidget, QLineEdit, QCheckBox
from qtpy.QtCore import Qt, Signal, QRect
from qtpy.QtGui import QPainter, QPixmap

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")

CONTAINER_AR = 3500.0 / 1756.0

# Fonte dos valores: a mesma condensada que o resto da interface usa (DROs,
# botoes) e que combina com os rotulos desenhados nas imagens. Sendo estreita,
# cabe um numero MUITO maior na mesma caixa que uma monoespacada.
NUM_FONT = "Bebas Kai"

# Fracao do maior tamanho que caberia na caixa. 1.0 = numero encostando na
# folga minima. Ajustado com o usuario olhando a maquina: 0.80 -> 0.60.
ESCALA_FONTE = 0.60

_metricas_cache = {}


def metricas_do_numero(familia):
    """Avanco do digito e altura da maiuscula, em fracao do tamanho da fonte.

    Medido na fonte de verdade (nao chutado), para o calculo do tamanho valer
    para qualquer fonte que venha a ser usada."""
    if familia in _metricas_cache:
        return _metricas_cache[familia]
    from qtpy.QtGui import QFont, QFontMetricsF
    f = QFont(familia)
    f.setBold(True)
    f.setPixelSize(200)                 # base grande = medida precisa
    fm = QFontMetricsF(f)
    m = (fm.horizontalAdvance("0") / 200.0,
         fm.capHeight() / 200.0,
         fm.ascent() / 200.0,
         fm.descent() / 200.0)
    _metricas_cache[familia] = m
    return m


def responsive(container_w, minimum, factor, maximum):
    """Equivalente ao responsiveSize(min, factor, max) do app."""
    return int(round(min(maximum, max(minimum, container_w * factor))))


class OverlayEdit(QLineEdit):
    """Campo transparente sobre a imagem — o retangulo ja vem desenhado nela.

    Commit no estilo do app: o valor so e aplicado ao sair do campo (ou Enter);
    texto invalido volta ao ultimo valor bom. `commit()` forca a leitura do que
    esta digitado (mesma ideia do interpretText() dos spinboxes, necessario no
    touch quando o operador aperta GERAR sem sair do campo)."""

    committed = Signal()

    def __init__(self, decimals=2, minimum=None, integer=False, parent=None):
        super(OverlayEdit, self).__init__(parent)
        self._decimals = decimals
        self._minimum = minimum
        self._integer = integer
        self._value = 0.0
        self.setAlignment(Qt.AlignCenter)
        self.setFrame(False)
        self.setStyleSheet(
            'QLineEdit { background: transparent; color: #FFFFFF; border: none;'
            ' padding: 0px; selection-background-color: #00838F; }')
        self.editingFinished.connect(self._on_editing_finished)
        self.textEdited.connect(self._virgula_para_ponto)

    def _virgula_para_ponto(self, texto):
        """Vírgula vira ponto na hora da digitação (teclado BR / habito)."""
        if "," in texto:
            pos = self.cursorPosition()
            self.setText(texto.replace(",", "."))
            self.setCursorPosition(pos)

    # -- valor -----------------------------------------------------------
    def set_value(self, v):
        self._value = int(v) if self._integer else float(v)
        self.setText(self._fmt(self._value))

    def value(self):
        return self._value

    def _fmt(self, v):
        if self._integer:
            return str(int(v))
        return "{:.{}f}".format(float(v), self._decimals)

    def commit(self):
        return self._parse(emit=False)

    def _on_editing_finished(self):
        self._parse(emit=True)

    def _parse(self, emit):
        txt = self.text().strip().replace(",", ".")
        try:
            v = int(float(txt)) if self._integer else float(txt)
        except ValueError:
            self.setText(self._fmt(self._value))    # invalido: restaura
            return self._value
        if self._minimum is not None and v < self._minimum:
            v = self._minimum
        changed = (v != self._value)
        self._value = v
        self.setText(self._fmt(v))
        if emit and changed:
            self.committed.emit()
        return v

    def restyle(self, font_px):
        # A fonte VAI NA FOLHA DE ESTILO DO WIDGET, nao so em setFont():
        # o tema do ProbeBasic tem uma regra de aplicacao
        #     VCPLineEdit, QLineEdit { font: 15pt "Bebas Kai"; }
        # e folha de estilo da aplicacao SOBREPOE setFont(). Era por isso que o
        # numero saia em 15pt (~20px) na maquina, ignorando o tamanho calculado.
        # A folha do proprio widget tem precedencia sobre a da aplicacao.
        f = self.font()
        f.setFamily(NUM_FONT)
        f.setBold(True)
        f.setPixelSize(font_px)
        self.setFont(f)                    # mantem fontMetrics() coerente
        self.setStyleSheet(
            'QLineEdit { background: transparent; color: #FFFFFF; border: none;'
            ' padding: 0px; selection-background-color: #00838F;'
            ' font-family: "%s"; font-size: %dpx; font-weight: bold; }'
            % (NUM_FONT, int(font_px)))


class OverlayToggle(QCheckBox):
    """Checkbox com moldura, igual aos toggles do app (verde/ambar quando ON)."""

    def __init__(self, text, color="#4caf50", parent=None):
        super(OverlayToggle, self).__init__(text, parent)
        self._color = color
        self.setCursor(Qt.PointingHandCursor)
        # alvo de toque: 32px era um terco menor que os demais botoes e errava
        # com luva. 48px e' a referencia para painel industrial.
        self.setMinimumHeight(48)
        self.restyle(12)

    def restyle(self, font_px):
        f = self.font()
        f.setBold(True)
        f.setPixelSize(font_px)
        self.setFont(f)
        box = max(12, int(font_px * 1.15))
        # font-size aqui tambem (e nao so setFont): o tema do ProbeBasic define
        # fonte por folha de estilo, que sobrepoe setFont().
        self.setStyleSheet("""
QCheckBox {{
    color: #FFFFFF;
    border: 2px solid #8b9bb4;
    border-radius: 4px;
    padding: 3px 10px;
    spacing: 8px;
    background: rgba(0, 0, 0, 140);
    font-family: "Bebas Kai";
    font-size: {f}px;
    font-weight: bold;
}}
QCheckBox:checked {{ color: {c}; border-color: {c}; }}
QCheckBox:disabled {{ color: #6b7580; border-color: #4a525c; }}
QCheckBox::indicator {{
    width: {b}px; height: {b}px;
    border: 2px solid #8b9bb4; border-radius: 3px;
    background: transparent;
}}
QCheckBox::indicator:checked {{ background: {c}; border-color: {c}; }}
QCheckBox::indicator:disabled {{ border-color: #4a525c; }}
""".format(c=self._color, b=box, f=int(font_px)))


class ImageOverlayPanel(QWidget):
    """Desenha a imagem de fundo e posiciona os campos em coordenadas %."""

    def __init__(self, image_name, parent=None, aspect=CONTAINER_AR):
        super(ImageOverlayPanel, self).__init__(parent)
        self._pix = QPixmap(os.path.join(IMAGES_DIR, image_name))
        self._aspect = float(aspect)   # cada desenho tem o seu (ver painel)
        self._items = []
        self._boxes = []               # (widget, rect_fracao_da_imagem, razao_fonte)
        self.setMinimumSize(520, 260)

    def add_box_item(self, widget, rect, max_chars=7, folga=0.06):
        """Coloca o campo EXATAMENTE sobre o retangulo desenhado na imagem.

        `rect` = (x, y, largura, altura) em fracao da imagem (0..1), medido
        direto no PNG. O campo ocupa a caixa inteira (area de toque cheia) e a
        fonte vai ao MAIOR tamanho que cabe (ver _maior_fonte_que_cabe),
        limitada pela altura da caixa e por `max_chars` — o maior valor que
        aquele campo recebe. Por isso TOOL/RPM ficam bem maiores que os campos
        de coordenada. `folga` e a margem ate o traco desenhado."""
        widget.setParent(self)
        self._boxes.append((widget, tuple(rect), float(folga), int(max_chars)))
        widget.show()

    def reconfigurar(self, image_name, aspect, itens):
        """Troca o desenho e o conjunto de campos (usado por operacoes com mais
        de um modo, ex.: desbaste interno basico x avancado).

        `itens` = [(widget, rect, max_chars)]. Os widgets ja registrados que
        ficarem de fora sao escondidos — os valores continuam neles, entao
        alternar o modo nao perde o que foi digitado."""
        anteriores = [w for (w, _r, _f, _m) in self._boxes]
        self._pix = QPixmap(os.path.join(IMAGES_DIR, image_name))
        self._aspect = float(aspect)
        self._boxes = [(w, tuple(r), 0.06, int(mc)) for (w, r, mc) in itens]
        atuais = set(id(w) for (w, _r, _f, _m) in self._boxes)
        for w in anteriores:
            if id(w) not in atuais:
                w.hide()
        for (w, _r, _f, _m) in self._boxes:
            w.setParent(self)
            w.show()
        self.update()
        self.relayout()

    def add_item(self, widget, top, left, size_fn=None, font_fn=None,
                 height_fn=None, width_pct=None, height_pct=None):
        """Posicao sempre em % do container (canto sup-esq), como no app.

        Tamanho aceita dois modos, conforme o painel de origem:
        - size_fn/height_fn: px calculados da largura do container (faceamento)
        - width_pct/height_pct: % do container (furacao)
        height_fn/height_pct fazem a area de toque cobrir o retangulo desenhado;
        o widget cresce a partir do CENTRO do texto, entao o alinhamento nao muda."""
        widget.setParent(self)
        self._items.append((widget, float(top), float(left), size_fn, font_fn,
                            height_fn, width_pct, height_pct))
        widget.show()

    # -- geometria -------------------------------------------------------
    def _container_rect(self):
        w = float(self.width())
        h = float(self.height())
        cw = w
        ch = cw / self._aspect
        if ch > h:                      # limitado pela altura
            ch = h
            cw = ch * self._aspect
        return (w - cw) / 2.0, (h - ch) / 2.0, cw, ch

    def _image_rect(self, cx, cy, cw, ch):
        if self._pix.isNull():
            return QRect(int(cx), int(cy), int(cw), int(ch))
        ar = float(self._pix.width()) / float(self._pix.height())
        if ar > self._aspect:           # imagem mais larga: ajusta pela largura
            iw, ih = cw, cw / ar
        else:
            ih, iw = ch, ch * ar
        return QRect(int(round(cx + (cw - iw) / 2.0)),
                     int(round(cy + (ch - ih) / 2.0)),
                     int(round(iw)), int(round(ih)))

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.black)
        if not self._pix.isNull():
            cx, cy, cw, ch = self._container_rect()
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.drawPixmap(self._image_rect(cx, cy, cw, ch), self._pix)
        p.end()

    def resizeEvent(self, event):
        super(ImageOverlayPanel, self).resizeEvent(event)
        self.relayout()

    def diagnostico(self):
        """Uma linha com os tamanhos reais, para descobrir por que a fonte sai
        pequena na maquina (ela e proporcional ao painel). Some sozinho quando
        o arquivo de diagnostico nao existir/nao puder ser escrito."""
        try:
            cx, cy, cw, ch = self._container_rect()
            ir = self._image_rect(cx, cy, cw, ch)
            fontes = [w.font().pixelSize() for (w, _r, _ra, _mc) in self._boxes]
            msg = ("painel=%dx%d container=%dx%d imagem=%dx%d fonte=%s..%s px\n"
                   % (self.width(), self.height(), int(cw), int(ch),
                      ir.width(), ir.height(),
                      min(fontes) if fontes else "-", max(fontes) if fontes else "-"))
            caminho = os.path.join(os.path.dirname(IMAGES_DIR), "..",
                                   "torno_cam_diag.log")
            with open(os.path.abspath(caminho), "a") as fh:
                fh.write(msg)
        except Exception:
            pass

    def _maior_fonte_que_cabe(self, larg, alt, max_chars, folga_rel):
        """MAIOR fonte que ainda cabe dentro do retangulo desenhado.

        Calculado com as metricas reais da fonte (nao por tentativa):
        o QLineEdit centra a linha ascendente+descendente, entao a linha de
        base fica em (alt + (asc-desc)*F)/2. Dai vem os tres limites:

          base dentro da caixa : (asc-desc)*F <= alt - 2*folga
          topo do digito dentro: cap*F <= (alt + (asc-desc)*F)/2 - folga
          digitos cabem na linha: max_chars*avanco*F <= larg - 2*folga

        `folga_rel` reserva uma margem proporcional para o numero nao encostar
        no traco desenhado da caixa."""
        avanco, cap, asc, desc = metricas_do_numero(NUM_FONT)
        fh = max(2.0, alt * folga_rel)
        # Margem lateral menor que a vertical: o numero e centrado na caixa, e
        # o traco lateral fica longe. Segurar a largura aqui so encolheria os
        # campos de coordenada a toa.
        fw = max(2.0, larg * folga_rel * 0.4)
        limites = []
        if asc - desc > 0:
            limites.append((alt - 2 * fh) / (asc - desc))
        base = cap - (asc - desc) / 2.0
        if base > 0:
            limites.append((alt / 2.0 - fh) / base)
        if max_chars > 0 and avanco > 0:
            limites.append((larg - 2 * fw) / (max_chars * avanco))
        if not limites:
            return 8
        return max(8, int(min(limites) * ESCALA_FONTE))

    def relayout(self):
        cx, cy, cw, ch = self._container_rect()
        if cw <= 0 or ch <= 0:
            return

        # Campos ancorados no retangulo real do desenho (medido no PNG).
        ir = self._image_rect(cx, cy, cw, ch)
        for (w, (bx, by, bw, bh), razao, max_chars) in self._boxes:
            x = ir.x() + bx * ir.width()
            y = ir.y() + by * ir.height()
            larg = bw * ir.width()
            alt = bh * ir.height()
            fpx = self._maior_fonte_que_cabe(larg, alt, max_chars, razao)
            if hasattr(w, "restyle"):
                w.restyle(fpx)
            else:
                f = w.font()
                f.setPixelSize(fpx)
                w.setFont(f)
            w.setGeometry(int(round(x)), int(round(y)),
                          int(round(larg)), int(round(alt)))
        for (w, top, left, size_fn, font_fn, height_fn,
             width_pct, height_pct) in self._items:
            if font_fn is not None:
                fpx = max(8, font_fn(cw))
                if hasattr(w, "restyle"):
                    w.restyle(fpx)
                else:
                    f = w.font()
                    f.setPixelSize(fpx)
                    w.setFont(f)
            x = cx + left / 100.0 * cw
            y = cy + top / 100.0 * ch
            hint = w.sizeHint()
            if width_pct is not None:
                width = width_pct / 100.0 * cw
            elif size_fn is not None:
                width = size_fn(cw)
            else:
                width = hint.width()
            height = hint.height()
            if height_pct is not None:
                # Painel estilo furacao: a caixa E o campo, ancorada pelo canto
                # superior-esquerdo (mesma geometria do app). Sem deslocamento.
                height = height_pct / 100.0 * ch
            elif height_fn is not None:
                # Painel estilo faceamento: a posicao foi ajustada para o TEXTO,
                # entao a area de toque cresce a partir do centro dele.
                alvo = height_fn(cw)
                if alvo > height:
                    y -= (alvo - height) / 2.0
                    height = alvo
            w.setGeometry(int(round(x)), int(round(y)),
                          int(width), int(height))
