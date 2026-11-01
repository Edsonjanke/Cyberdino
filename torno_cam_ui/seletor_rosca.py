# -*- coding: utf-8 -*-
"""Seletor de rosca (artboard "LinuxCNC, seletor de rosca" do canvas Painel
CNC, 2026-11-01).

A celula ROSCA da faixa inferior abre, por cima do desenho, um painel em dois
passos: o diametro nominal e depois o passo. Ao lado fica a rosca escolhida,
com o perfil e as medidas da externa e da interna pelas mesmas regras do
gerador (roscas.altura_filete e o D1 da tabela). APLICAR ROSCA troca a rosca
do combo; passo, X e RPM seguem pelo _aplicar_rosca do thread_panel, como
antes.

Por dentro a celula continua sendo o ComboRoscas: o estado salvo, o agente e
o GERAR PGM leem e escrevem a rosca pelo nome da tabela, sem saber do painel.
"""

import math
from collections import OrderedDict

from qtpy.QtCore import Qt, Signal, QPointF, QRectF
from qtpy.QtGui import (QColor, QFont, QFontMetricsF, QIcon, QPainter,
                        QPainterPath, QPen, QPixmap, QPolygonF)
from qtpy.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout,
                            QLabel, QPushButton, QVBoxLayout, QWidget)

from torno_cam.engine import roscas

from .ciclo_panel import (FONTE_CICLO, PAINEL, BORDA, VISOR, BOTAO, ATIVO,
                          TEXTO, TEXTO_2, espacamento)
from .widgets import ComboRoscas

# tokens do artboard que as telas de ciclo ainda nao tinham
AMARELO = "#F2C14E"        # cotas
TRACO = "#E7EAEE"          # contorno da peca
HACHURA = "#4A515B"
TEXTO_3 = "#6F7884"        # nota apagada ("M5 TEM 2 PASSOS")
LEGENDA = "#D5D9DC"        # legenda do botao de passo nao marcado
LINHA_CARTAO = "#1F242B"
VEU = QColor(11, 13, 16, 209)      # rgba(11,13,16,0.82) sobre o desenho

NOME_TABELA = {roscas.TAB_METRICA: u"MÉTRICA ISO",
               roscas.TAB_POLEGADA: u"POLEGADA UNC/UNF",
               roscas.TAB_NPT: u"NPT (CÔNICA)"}


# ── nomes e medidas ─────────────────────────────────────────────────────────
def diametro(it):
    """Rotulo do diametro nominal: M5, 1/2", #10."""
    if it["tabela"] == roscas.TAB_METRICA:
        return u"M%g" % it["bitola"]
    nome = it["nome"].split(u" - ")[0]
    return nome[4:] if nome.startswith(u"NPT ") else nome


def rotulo_passo(it):
    """(valor grande, legenda) do botao de passo: 0.8 NORMAL, 13 UNC."""
    if it["tabela"] == roscas.TAB_METRICA:
        return (u"%g" % it["passo"],
                u"NORMAL" if it["tipo"] == roscas.PADRAO else u"FINA")
    if it["tabela"] == roscas.TAB_NPT:
        return u"%g" % it["tpi"], u"NPT"
    return u"%g" % it["tpi"], (it.get("comentario") or u"")


def nome_curto(it):
    """('M5 × 0.5', 'FINA'): o que a celula e o painel mostram."""
    valor, legenda = rotulo_passo(it)
    if it["tabela"] == roscas.TAB_NPT:
        return u"NPT %s × %s" % (diametro(it), valor), u"CÔNICA"
    return u"%s × %s" % (diametro(it), valor), legenda


def medidas(it):
    """Medidas do painel, com as mesmas alturas de filete do gerador."""
    passo = 25.4 / it["tpi"] if it.get("tpi") else it["passo"]
    tab = it["tabela"]
    h_ext = roscas.altura_filete(tab, False) * passo
    h_int = roscas.altura_filete(tab, True) * passo
    # flanco: ISO/unificada D - 0.6495P; na NPT a tabela parte de E0 + 0.8P
    flanco = it["bitola"] - (0.8 if tab == roscas.TAB_NPT else 0.6495) * passo
    return dict(passo=passo, flanco=flanco, angulo=60,
                maior=it["bitola"], menor_ext=it["bitola"] - 2.0 * h_ext,
                prof_ext=h_ext, menor_int=it["menor"], broca=it["broca"],
                prof_int=h_int)


def _fonte(px, espaco=0.0):
    f = QFont(FONTE_CICLO)
    f.setPixelSize(int(px))
    if espaco:
        f.setLetterSpacing(QFont.AbsoluteSpacing, float(espaco))
    return f


def _largura(fonte, texto):
    fm = QFontMetricsF(fonte)
    medir = getattr(fm, "horizontalAdvance", None) or fm.width   # Qt5 antigo
    return medir(texto)


def _texto_centrado(p, x, y, texto):
    """Texto com a linha de base em y e centrado em x (como o SVG)."""
    p.drawText(QPointF(x - _largura(p.font(), texto) / 2.0, y), texto)


def _seta(p, cx, cy, para_cima, cor, lado=12.0):
    """Chevron 12 px do artboard (path M6 9l6 6 6-6, traco 3 no 24)."""
    k = lado / 24.0
    p.save()
    p.setPen(QPen(QColor(cor), 3 * k, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    dy = -1 if para_cima else 1
    pts = [QPointF(cx - 6 * k, cy - 3 * k * dy), QPointF(cx, cy + 3 * k * dy),
           QPointF(cx + 6 * k, cy - 3 * k * dy)]
    p.drawPolyline(QPolygonF(pts))
    p.restore()


def _icone_fechar():
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    k = 20 / 24.0
    p.setPen(QPen(QColor(TEXTO), 3 * k, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(5 * k, 5 * k), QPointF(19 * k, 19 * k))
    p.drawLine(QPointF(19 * k, 5 * k), QPointF(5 * k, 19 * k))
    p.end()
    return QIcon(pm)


# ── pecas do painel ─────────────────────────────────────────────────────────
class _PerfilRosca(QWidget):
    """Perfil de 60 graus com a cota do passo e da altura (SVG 236 x 122 do
    artboard, desenhado a 200 x 103)."""

    PERFIL = [(6, 95), (26, 95), (54, 46), (62, 46), (90, 95), (106, 95),
              (134, 46), (142, 46), (170, 95), (186, 95), (214, 46), (222, 46),
              (230, 60)]

    def __init__(self, parent=None):
        super(_PerfilRosca, self).__init__(parent)
        self.setFixedSize(200, 103)
        self._passo = u""
        self._angulo = 60

    def set_rosca(self, passo, angulo=60):
        self._passo = u"P %g" % round(passo, 3)
        self._angulo = angulo
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width() / 236.0, self.height() / 122.0)
        pts = [QPointF(x, y) for x, y in self.PERFIL]
        area = QPainterPath(pts[0])
        for pt in pts[1:]:
            area.lineTo(pt)
        area.lineTo(230, 116)
        area.lineTo(6, 116)
        area.closeSubpath()
        p.save()
        p.setClipPath(area)
        p.setPen(QPen(QColor(HACHURA), 1.6))
        for x in range(-130, 240, 9):
            p.drawLine(QPointF(x, 122), QPointF(x + 122, 0))
        p.restore()
        p.setPen(QPen(QColor(TRACO), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF(pts))

        amarelo = QColor(AMARELO)
        p.setPen(QPen(amarelo, 1.5))
        for a, b in (((58, 40), (58, 18)), ((138, 40), (138, 18)),
                     ((64, 22), (132, 22)), ((146, 46), (196, 46)),
                     ((174, 95), (196, 95)), ((190, 52), (190, 89))):
            p.drawLine(QPointF(*a), QPointF(*b))
        p.setPen(Qt.NoPen)
        p.setBrush(amarelo)
        for tri in (((58, 22), (68, 18), (68, 26)), ((138, 22), (128, 18), (128, 26)),
                    ((190, 46), (186, 56), (194, 56)), ((190, 95), (186, 85), (194, 85))):
            p.drawPolygon(QPolygonF([QPointF(*v) for v in tri]))
        p.setPen(amarelo)
        p.setFont(_fonte(16, 1))
        _texto_centrado(p, 98, 15, self._passo)

        # arco do angulo (A22 entre 85,86 e 111,86, por cima)
        cinza = QColor(TEXTO_2)
        p.setPen(QPen(cinza, 1.2))
        p.setBrush(Qt.NoBrush)
        cy = 86 + math.sqrt(22 ** 2 - 13 ** 2)
        a0 = math.degrees(math.atan2(cy - 86, 13))
        p.drawArc(QRectF(98 - 22, cy - 22, 44, 44), int(a0 * 16),
                  int((180 - 2 * a0) * 16))
        p.setPen(cinza)
        p.setFont(_fonte(15))
        _texto_centrado(p, 98, 78, u"%d°" % self._angulo)
        p.end()


class _BotaoPasso(QPushButton):
    """Botao alto do passo: o valor grande e a legenda embaixo."""

    def __init__(self, valor, legenda, largura=168, parent=None):
        super(_BotaoPasso, self).__init__(parent)
        self.setCheckable(True)
        self.setProperty("sel", "botao")
        self.setFixedSize(largura, 76)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 6, 0, 6)
        v.setSpacing(2)
        self._valor = QLabel(valor)
        self._valor.setProperty("sel", "passoValor")
        self._legenda = QLabel(legenda)
        self._legenda.setProperty("sel", "passoLegenda")
        espacamento(self._legenda, 2)
        for lab in (self._valor, self._legenda):
            lab.setAlignment(Qt.AlignCenter)
            lab.setAttribute(Qt.WA_TransparentForMouseEvents)
            v.addWidget(lab)
        self.toggled.connect(self._pintar)
        self._pintar(False)

    def _pintar(self, marcado):
        self._legenda.setProperty("marcado", bool(marcado))
        self._legenda.style().unpolish(self._legenda)
        self._legenda.style().polish(self._legenda)


class _Cartao(QFrame):
    """EXTERNA · EIXO / INTERNA · FURO: tres medidas, a do lado atual com a
    borda teal e a marca LADO ATUAL."""

    def __init__(self, titulo, onde, rotulos, parent=None):
        super(_Cartao, self).__init__(parent)
        self.setProperty("sel", "cartao")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 4)
        v.setSpacing(0)
        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 6)
        t = QLabel(u'%s <span style="color:%s">· %s</span>' % (titulo, TEXTO_2, onde))
        t.setProperty("sel", "cartaoTitulo")
        espacamento(t, 1.5)
        topo.addWidget(t)
        topo.addStretch(1)
        self._atual = QLabel(u"LADO ATUAL")
        self._atual.setProperty("sel", "ladoAtual")
        espacamento(self._atual, 1.5)
        topo.addWidget(self._atual)
        v.addLayout(topo)
        self._valores = []
        for rotulo in rotulos:
            linha = QFrame()
            linha.setProperty("sel", "linhaCartao")
            h = QHBoxLayout(linha)
            h.setContentsMargins(0, 3, 0, 3)
            r = QLabel(rotulo)
            r.setProperty("sel", "cartaoRotulo")
            espacamento(r, 1.5)
            val = QLabel()
            val.setProperty("sel", "cartaoValor")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(r)
            h.addStretch(1)
            h.addWidget(val)
            v.addWidget(linha)
            self._valores.append((r, val))

    def set_atual(self, atual):
        self.setProperty("atual", bool(atual))
        self.style().unpolish(self)
        self.style().polish(self)
        self._atual.setVisible(bool(atual))

    def set_linha(self, i, rotulo, valor, casas=3):
        r, val = self._valores[i]
        r.setText(rotulo)
        val.setText(u'%.*f <span style="font-size:12px; color:%s">MM</span>'
                    % (casas, valor, TEXTO_2))


_QSS = """
QWidget {{ background: transparent; }}
QLabel {{ background: transparent; border: none; color: {texto}; font-family: "{f}"; }}
QFrame#seletorDialogo {{ background: {painel}; border: 1px solid {borda}; border-radius: 10px; }}
QLabel[sel="titulo"] {{ font-size: 30px; }}
QLabel[sel="subtitulo"] {{ font-size: 15px; color: {texto2}; }}
QLabel[sel="etapaNumero"] {{ background: {visor}; border: 1px solid {botao}; border-radius: 13px; font-size: 16px; }}
QLabel[sel="etapa"] {{ font-size: 17px; color: {texto2}; }}
QLabel[sel="etapaNota"] {{ font-size: 15px; color: {texto3}; }}
QPushButton[sel="botao"] {{ background: {botao}; border: 2px solid {borda}; border-radius: 5px; color: {texto}; font-family: "{f}"; font-size: 24px; padding: 0px; }}
QPushButton[sel="botao"]:checked {{ background: {ativo}; border-color: {ativo}; }}
QPushButton[sel="acao"] {{ background: {botao}; border: 2px solid {borda}; border-radius: 5px; color: {texto}; font-family: "{f}"; font-size: 22px; }}
QPushButton[sel="aplicar"] {{ background: {ativo}; border: 2px solid {ativo}; border-radius: 5px; color: {texto}; font-family: "{f}"; font-size: 22px; }}
QPushButton[sel="fechar"] {{ background: {botao}; border: 2px solid {borda}; border-radius: 5px; }}
QLabel[sel="passoValor"] {{ font-size: 32px; }}
QLabel[sel="passoLegenda"] {{ font-size: 14px; color: {legenda}; }}
QLabel[sel="passoLegenda"][marcado="true"] {{ color: {texto}; }}
QFrame[sel="escolhida"] {{ background: {visor}; border: 1px solid {borda}; border-radius: 8px; }}
QLabel[sel="rotuloPequeno"] {{ font-size: 13px; color: {texto2}; }}
QLabel[sel="nome"] {{ font-size: 46px; }}
QLabel[sel="etiqueta"] {{ font-size: 16px; color: {texto2}; border: 1px solid {botao}; border-radius: 4px; padding: 1px 7px; }}
QLabel[sel="dado"] {{ font-size: 15px; color: {texto2}; }}
QFrame[sel="cartao"] {{ background: transparent; border: 1px solid {borda}; border-radius: 6px; }}
QFrame[sel="cartao"][atual="true"] {{ border: 2px solid {ativo}; }}
QLabel[sel="cartaoTitulo"] {{ font-size: 18px; }}
QLabel[sel="ladoAtual"] {{ font-size: 12px; background: {ativo}; border-radius: 4px; padding: 2px 7px; }}
QFrame[sel="linhaCartao"] {{ background: transparent; border: none; border-top: 1px solid {linha}; }}
QLabel[sel="cartaoRotulo"] {{ font-size: 15px; color: {texto2}; }}
QLabel[sel="cartaoValor"] {{ font-size: 26px; }}
QLabel[sel="dica"] {{ font-size: 16px; color: {texto2}; }}
""".format(texto=TEXTO, texto2=TEXTO_2, texto3=TEXTO_3, painel=PAINEL, borda=BORDA,
           visor=VISOR, botao=BOTAO, ativo=ATIVO, legenda=LEGENDA,
           linha=LINHA_CARTAO, f=FONTE_CICLO)


def _limpar(layout):
    """Tira os botoes do layout ja escondidos: o deleteLater so apaga na volta
    ao loop de eventos e, ate la, o botao velho ficaria desenhado por cima."""
    while layout.count():
        w = layout.takeAt(0).widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()


# ── o painel ────────────────────────────────────────────────────────────────
class SeletorRosca(QWidget):
    """Veu sobre o desenho + painel SELECIONAR ROSCA.

    Filho do formulario da rosca, posicionado sobre o desenho (`abrir` recebe
    o retangulo) com a seta apontando para a celula ROSCA."""

    escolhida = Signal(object)      # dict da rosca da tabela
    fechado = Signal()

    MARGEM = 14                     # do desenho ate o painel
    ESPACO_SETA = 22                # embaixo, onde a seta desce

    def __init__(self, parent):
        super(SeletorRosca, self).__init__(parent)
        self.setObjectName("seletorRosca")
        self.setStyleSheet(_QSS)
        self.setFocusPolicy(Qt.StrongFocus)
        self._itens = []
        self._grupos = OrderedDict()    # diametro -> [itens]
        self._diametro = None
        self._item = None
        self._passos = []               # [(botao, item)] do diametro marcado
        self._interna = False
        self._seta_x = None

        self._dialogo = QFrame(self)
        self._dialogo.setObjectName("seletorDialogo")
        raiz = QVBoxLayout(self._dialogo)
        raiz.setContentsMargins(20, 20, 20, 20)
        raiz.setSpacing(16)
        raiz.addLayout(self._montar_topo())
        corpo = QHBoxLayout()
        corpo.setSpacing(24)
        corpo.addWidget(self._montar_escolha(), 0)
        corpo.addWidget(self._montar_escolhida(), 1)
        raiz.addLayout(corpo, 1)
        raiz.addLayout(self._montar_rodape())
        self.hide()

    # ── construcao ─────────────────────────────────────────────────────────
    def _montar_topo(self):
        h = QHBoxLayout()
        v = QVBoxLayout()
        v.setSpacing(4)
        titulo = QLabel(u"SELECIONAR ROSCA")
        titulo.setProperty("sel", "titulo")
        espacamento(titulo, 2)
        self._subtitulo = QLabel()
        self._subtitulo.setProperty("sel", "subtitulo")
        espacamento(self._subtitulo, 1.5)
        v.addWidget(titulo)
        v.addWidget(self._subtitulo)
        h.addLayout(v)
        h.addStretch(1)
        fechar = QPushButton()
        fechar.setProperty("sel", "fechar")
        fechar.setFixedSize(52, 52)
        fechar.setIcon(_icone_fechar())
        fechar.setAccessibleName(u"Fechar")
        fechar.clicked.connect(self.fechar)
        h.addWidget(fechar, 0, Qt.AlignTop)
        return h

    @staticmethod
    def _etapa(numero, texto):
        h = QHBoxLayout()
        h.setSpacing(10)
        n = QLabel(str(numero))
        n.setProperty("sel", "etapaNumero")
        n.setFixedSize(26, 26)
        n.setAlignment(Qt.AlignCenter)
        t = QLabel(texto)
        t.setProperty("sel", "etapa")
        espacamento(t, 2)
        h.addWidget(n)
        h.addWidget(t)
        return h, t

    def _montar_escolha(self):
        col = QWidget()
        col.setFixedWidth(544)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        etapa1, _t = self._etapa(1, u"DIÂMETRO NOMINAL")
        etapa1.addStretch(1)
        v.addLayout(etapa1)
        self._grade = QGridLayout()
        self._grade.setSpacing(8)
        v.addLayout(self._grade)
        v.addSpacing(2)
        etapa2, self._etapa_passo = self._etapa(2, u"PASSO")
        self._nota_passo = QLabel()
        self._nota_passo.setProperty("sel", "etapaNota")
        espacamento(self._nota_passo, 1.5)
        etapa2.addWidget(self._nota_passo)
        etapa2.addStretch(1)
        v.addLayout(etapa2)
        self._linha_passos = QHBoxLayout()
        self._linha_passos.setSpacing(8)
        v.addLayout(self._linha_passos)
        v.addStretch(1)
        self._botoes_diam = QButtonGroup(self)
        self._botoes_diam.setExclusive(True)
        self._botoes_passo = QButtonGroup(self)
        self._botoes_passo.setExclusive(True)
        return col

    def _montar_escolhida(self):
        card = QFrame()
        card.setProperty("sel", "escolhida")
        v = QVBoxLayout(card)
        v.setContentsMargins(18, 14, 18, 14)
        v.setSpacing(8)
        r = QLabel(u"ROSCA ESCOLHIDA")
        r.setProperty("sel", "rotuloPequeno")
        espacamento(r, 2)
        v.addWidget(r)
        nome = QHBoxLayout()
        nome.setSpacing(12)
        self._nome = QLabel()
        self._nome.setProperty("sel", "nome")
        self._etiqueta = QLabel()
        self._etiqueta.setProperty("sel", "etiqueta")
        espacamento(self._etiqueta, 1.5)
        nome.addWidget(self._nome)
        nome.addWidget(self._etiqueta, 0, Qt.AlignVCenter)
        nome.addStretch(1)
        v.addLayout(nome)
        perfil = QHBoxLayout()
        perfil.setSpacing(18)
        self._perfil = _PerfilRosca()
        perfil.addWidget(self._perfil)
        dados = QVBoxLayout()
        dados.setSpacing(6)
        self._dados = []
        for _i in range(3):
            d = QLabel()
            d.setProperty("sel", "dado")
            espacamento(d, 1.5)
            dados.addWidget(d)
            self._dados.append(d)
        perfil.addLayout(dados)
        perfil.addStretch(1)
        v.addLayout(perfil)
        cartoes = QHBoxLayout()
        cartoes.setSpacing(12)
        self._externa = _Cartao(u"EXTERNA", u"EIXO", (u"Ø MAIOR", u"Ø MENOR", u"PROFUNDIDADE"))
        self._interna_c = _Cartao(u"INTERNA", u"FURO", (u"Ø MENOR", u"BROCA (D − P)", u"PROFUNDIDADE"))
        cartoes.addWidget(self._externa, 1)
        cartoes.addWidget(self._interna_c, 1)
        v.addLayout(cartoes)
        v.addStretch(1)
        return card

    def _montar_rodape(self):
        h = QHBoxLayout()
        h.setSpacing(24)
        dica = QLabel(u"TOQUE NO DIÂMETRO E DEPOIS NO PASSO. AO TROCAR O DIÂMETRO,\n"
                      u"O PASSO NORMAL JÁ VEM MARCADO.")
        dica.setProperty("sel", "dica")
        espacamento(dica, 1)
        h.addWidget(dica, 1)
        botoes = QHBoxLayout()
        botoes.setSpacing(10)
        cancelar = QPushButton(u"CANCELAR")
        cancelar.setProperty("sel", "acao")
        cancelar.setFixedSize(180, 56)
        cancelar.clicked.connect(self.fechar)
        aplicar = QPushButton(u"APLICAR ROSCA")
        aplicar.setProperty("sel", "aplicar")
        aplicar.setFixedSize(250, 56)
        aplicar.clicked.connect(self._aplicar)
        for b in (cancelar, aplicar):
            espacamento(b, 1.5)
            botoes.addWidget(b)
        h.addLayout(botoes)
        return h

    # ── uso ────────────────────────────────────────────────────────────────
    def abrir(self, itens, atual, interna, area, seta_x=None):
        """Mostra o painel sobre `area` (retangulo do desenho no pai)."""
        self._itens = list(itens)
        self._interna = bool(interna)
        self._seta_x = seta_x
        self._grupos = OrderedDict()
        for it in self._itens:
            self._grupos.setdefault(diametro(it), []).append(it)
        tab = self._itens[0]["tabela"] if self._itens else roscas.TAB_METRICA
        self._subtitulo.setText(u"TABELA %s · LADO %s" % (
            NOME_TABELA.get(tab, tab), u"INTERNA" if interna else u"EXTERNA"))
        self._etapa_passo.setText(u"PASSO" if tab == roscas.TAB_METRICA
                                  else u"FIOS POR POLEGADA")
        self._interna_c.set_linha(1, u"BROCA" if tab == roscas.TAB_NPT
                                  else u"BROCA (D − P)", 0.0)
        self._externa.set_atual(not interna)
        self._interna_c.set_atual(interna)
        self._montar_diametros()
        atual = atual or (self._itens[0] if self._itens else None)
        if atual is not None:
            self._escolher_diametro(diametro(atual), atual)
        self.posicionar(area, seta_x)
        self.show()
        self.raise_()
        self.setFocus()

    def posicionar(self, area, seta_x=None):
        if seta_x is not None:
            self._seta_x = seta_x
        self.setGeometry(area)
        self._dialogo.setGeometry(self.MARGEM, self.MARGEM,
                                  self.width() - 2 * self.MARGEM,
                                  self.height() - self.MARGEM - self.ESPACO_SETA)
        self.update()

    def fechar(self):
        if self.isVisible():
            self.hide()
            self.fechado.emit()

    def _aplicar(self):
        it = self._item
        self.fechar()
        if it is not None:
            self.escolhida.emit(it)

    def _montar_diametros(self):
        _limpar(self._grade)
        for b in self._botoes_diam.buttons():
            self._botoes_diam.removeButton(b)
        n = len(self._grupos)
        # 6 colunas como no artboard; a metrica inteira (28 bitolas, ate M50)
        # cabe nas mesmas 4 linhas com 7
        colunas = 6 if n <= 24 else 7
        for i, nome in enumerate(self._grupos):
            b = QPushButton(nome)
            b.setCheckable(True)
            b.setProperty("sel", "botao")
            b.setFixedHeight(50)
            espacamento(b, 1)
            b.clicked.connect(lambda _c=False, d=nome: self._escolher_diametro(d))
            self._botoes_diam.addButton(b)
            self._grade.addWidget(b, i // colunas, i % colunas)

    def _escolher_diametro(self, nome, item=None):
        """Marca o diametro e monta os passos dele. Sem `item` (toque do
        operador) o passo NORMAL, o primeiro da tabela, ja vem marcado."""
        self._diametro = nome
        for b in self._botoes_diam.buttons():
            b.setChecked(b.text() == nome)
        itens = self._grupos.get(nome, [])
        _limpar(self._linha_passos)
        for b in self._botoes_passo.buttons():
            self._botoes_passo.removeButton(b)
        self._passos = []
        # 168 px como no artboard; com 4 ou 5 passos (M10, M30 a M50) eles
        # dividem a coluna de 544
        largura = min(168, (544 - 8 * (len(itens) - 1)) // max(1, len(itens)))
        for it in itens:
            valor, legenda = rotulo_passo(it)
            b = _BotaoPasso(valor, legenda, largura)
            b.clicked.connect(lambda _c=False, x=it: self._escolher_item(x))
            self._botoes_passo.addButton(b)
            self._linha_passos.addWidget(b)
            self._passos.append((b, it))
        self._linha_passos.addStretch(1)
        n = len(itens)
        self._nota_passo.setText(u"· %s TEM %d %s" % (
            nome, n, u"PASSO" if n == 1 else u"PASSOS"))
        if itens:
            self._escolher_item(item if item in itens else itens[0])

    def _escolher_item(self, it):
        self._item = it
        for b, x in self._passos:
            b.setChecked(x is it)
        nome, etiqueta = nome_curto(it)
        self._nome.setText(nome)
        self._etiqueta.setText(etiqueta)
        self._etiqueta.setVisible(bool(etiqueta))
        m = medidas(it)
        self._perfil.set_rosca(m["passo"], m["angulo"])
        grande = u'<span style="color:%s; font-size:22px">%s</span>' % (TEXTO, u"%s")
        self._dados[0].setText(u"PASSO " + grande % (u"%.3f" % m["passo"]) + u" MM")
        self._dados[1].setText(u"Ø FLANCO " + grande % (u"%.3f" % m["flanco"]) + u" MM")
        self._dados[2].setText(u"ÂNGULO " + grande % (u"%d°" % m["angulo"]))
        self._externa.set_linha(0, u"Ø MAIOR", m["maior"])
        self._externa.set_linha(1, u"Ø MENOR", m["menor_ext"])
        self._externa.set_linha(2, u"PROFUNDIDADE", m["prof_ext"])
        self._interna_c.set_linha(0, u"Ø MENOR", m["menor_int"])
        broca = u"BROCA" if it["tabela"] == roscas.TAB_NPT else u"BROCA (D − P)"
        self._interna_c.set_linha(1, broca, m["broca"], 2)
        self._interna_c.set_linha(2, u"PROFUNDIDADE", m["prof_int"])

    # ── eventos ────────────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        # toque no veu, fora do painel: cancela
        if not self._dialogo.geometry().contains(ev.pos()):
            self.fechar()
        ev.accept()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.fechar()
            return
        super(SeletorRosca, self).keyPressEvent(ev)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(VEU)
        p.drawRoundedRect(QRectF(self.rect()), 8, 8)
        if self._seta_x is None:
            return
        # seta do painel ate a celula ROSCA (30 x 17 no artboard)
        g = self._dialogo.geometry()
        x = min(max(self._seta_x - self.x(), g.left() + 30), g.right() - 30)
        y = g.bottom()
        tri = QPolygonF([QPointF(x - 15, y), QPointF(x + 15, y), QPointF(x, y + 17)])
        p.setBrush(QColor(PAINEL))
        p.drawPolygon(tri)
        p.setPen(QPen(QColor(BORDA), 1))
        p.drawPolyline(QPolygonF([QPointF(x - 15, y + 0.5), QPointF(x, y + 17),
                                  QPointF(x + 15, y + 0.5)]))
        p.end()


# ── a celula ────────────────────────────────────────────────────────────────
class ComboSeletorRosca(ComboRoscas):
    """A celula ROSCA da faixa: por dentro o mesmo ComboRoscas (estado, agente
    e _aplicar_rosca nao mudam); por fora 'M5 × 0.5' com a etiqueta FINA e a
    seta, e o toque abre o SeletorRosca em vez da lista."""

    def __init__(self, itens, abrir, parent=None):
        self._abrir = abrir
        self.aberto = False
        super(ComboSeletorRosca, self).__init__(itens, parent)

    def itens(self):
        return list(self._itens)

    def showPopup(self):
        if self._abrir is not None:
            self._abrir()
        else:
            super(ComboSeletorRosca, self).showPopup()

    def usar_estilo_celula(self):
        self._celula = True
        self.setStyleSheet("QComboBox { background: transparent; border: none;"
                           " padding: 0px; min-height: 0px; }"
                           " QComboBox::drop-down { border: none; width: 0px; }")

    def _pintar_fechado(self, indice):
        if getattr(self, "_celula", False):
            self.update()
            return
        super(ComboSeletorRosca, self)._pintar_fechado(indice)

    def set_aberto(self, aberto):
        """Celula com a borda teal e a seta para cima enquanto o painel esta
        aberto (o QSS da faixa le a propriedade celulaAberta)."""
        self.aberto = bool(aberto)
        cel = self.parentWidget()
        if cel is not None and cel.property("celulaFaixa"):
            cel.setProperty("celulaAberta", self.aberto)
            cel.style().unpolish(cel)
            cel.style().polish(cel)
        self.update()

    def paintEvent(self, ev):
        if not getattr(self, "_celula", False):
            return super(ComboSeletorRosca, self).paintEvent(ev)
        it = self.item_atual()
        if it is None:
            return
        nome, etiqueta = nome_curto(it)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        f = _fonte(22)
        p.setFont(f)
        p.setPen(QColor(TEXTO))
        fm = QFontMetricsF(f)
        base = r.center().y() + (fm.ascent() - fm.descent()) / 2.0
        p.drawText(QPointF(0, base), nome)
        if etiqueta:
            fe = _fonte(12, 1.5)
            alt = QFontMetricsF(fe).height()
            caixa = QRectF(_largura(f, nome) + 8, r.center().y() - alt / 2.0 - 1,
                           _largura(fe, etiqueta) + 14, alt + 2)
            p.setPen(QPen(QColor(BOTAO), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(caixa, 4, 4)
            p.setFont(fe)
            p.setPen(QColor(TEXTO_2))
            p.drawText(caixa, Qt.AlignCenter, etiqueta)
        _seta(p, r.right() - 8, r.center().y(), self.aberto,
              TEXTO if self.aberto else TEXTO_2)
        p.end()
