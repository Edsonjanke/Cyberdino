# -*- coding: utf-8 -*-
"""Telas de ciclo no padrao novo (handoff "telas de ciclo", 2026-11-01).

Componentes compartilhados pelas 13 telas da aba GERAR PGM:

- CicloPanel  : desenha o fundo da tela (desenho + rotulos + notas, ja
                recolorido) e posiciona os widgets nas coordenadas do JSON
                da tela, no viewBox 160 -30 1460 747 do desenho.
- CampoCiclo  : caixa de valor visivel (fundo #1A1E24, borda #5A6268, foco
                teal). Mesma logica do OverlayEdit (virgula, commit, minimo).
- OpcaoCiclo  : caixa de opcao (QCheckBox) da faixa padrao.
- FaixaPadrao : as 4 opcoes + o AFASTAMENTO FINAL, iguais nas 13 telas
                ("essa parte sempre manter igual nas operacoes").
- FaixaInferior: linhas CONFIG. / CORTE em celulas (rotulo pequeno em cima,
                valor embaixo), reaproveitando os widgets Touch* de cada tela.

Os textos dos rotulos e notas vem desenhados no fundo (fundos/com-rotulos);
aqui so ficam os widgets.
"""

import json
import os

from qtpy.QtWidgets import (QWidget, QCheckBox, QFrame, QLabel, QHBoxLayout,
                            QVBoxLayout, QGridLayout, QSizePolicy,
                            QGraphicsOpacityEffect, QAbstractSpinBox, QLineEdit)
from qtpy.QtCore import Qt, QRectF, QObject, QEvent
from qtpy.QtGui import QPainter, QPixmap, QColor, QPen, QFont

from .image_panel import OverlayEdit

_AQUI = os.path.dirname(os.path.abspath(__file__))
CICLOS_DIR = os.path.join(_AQUI, "ciclos")
FUNDOS_DIR = os.path.join(_AQUI, "images", "ciclos")
ICONES_DIR = os.path.join(_AQUI, "icones")

# viewBox do desenho: x, y, largura, altura
VB_X, VB_Y, VB_W, VB_H = 160.0, -30.0, 1460.0, 747.0

FONTE_CICLO = "Bebas Neue"

# cores (tokens da secao 3 do handoff)
FUNDO = "#101215"
PAINEL = "#1A1E24"
BORDA = "#2E343C"
VISOR = "#0B0D10"
BOTAO = "#5A6268"
ATIVO = "#00838F"
TEXTO = "#FFFFFF"
TEXTO_2 = "#A9B0B5"
NUMERO = "#3DDC84"

OPACIDADE_DESABILITADO = 0.6


def carregar_tela(nome):
    """JSON de uma tela (ex.: '03-desbaste-int')."""
    with open(os.path.join(CICLOS_DIR, nome + ".json"), encoding="utf-8") as f:
        return json.load(f)


def caixas_por_id(tela):
    """{id do campo: (x, y, w, h, fonte_valor)} no viewBox."""
    out = {}
    for c in tela.get("campos", []):
        cx = c["caixa"]
        out[c["id"]] = (cx["x"], cx["y"], cx["w"], cx["h"], c.get("fonte_valor", 38.0))
    return out


def opacidade(widget, habilitado):
    """Desabilitado = opacidade 0,6 (o QSS nao tem opacidade)."""
    if habilitado:
        widget.setGraphicsEffect(None)
    else:
        ef = QGraphicsOpacityEffect(widget)
        ef.setOpacity(OPACIDADE_DESABILITADO)
        widget.setGraphicsEffect(ef)


def espacamento(widget, valor_px):
    """Espacamento entre letras (o QSS nao aceita letter-spacing)."""
    f = widget.font()
    f.setLetterSpacing(QFont.AbsoluteSpacing, float(valor_px))
    widget.setFont(f)


class CampoCiclo(OverlayEdit):
    """Caixa de valor da tela de ciclo, visivel (secao 5.2 do handoff)."""

    def __init__(self, decimals=2, minimum=None, integer=False, parent=None):
        super(CampoCiclo, self).__init__(decimals=decimals, minimum=minimum,
                                         integer=integer, parent=parent)
        self._borda_px = 2
        self.restyle(24)

    def set_borda(self, px):
        self._borda_px = max(1, int(round(px)))

    def setEnabled(self, ligado):
        super(CampoCiclo, self).setEnabled(ligado)
        opacidade(self, ligado)

    def restyle(self, font_px):
        f = self.font()
        f.setFamily(FONTE_CICLO)
        f.setBold(False)
        f.setPixelSize(int(font_px))
        self.setFont(f)
        # A folha do proprio widget vence a do tema (ver OverlayEdit.restyle)
        self.setStyleSheet(
            'QLineEdit { background: %s; border: %dpx solid %s; border-radius: 4px;'
            ' color: %s; padding: 0px; selection-background-color: %s;'
            ' font-family: "%s"; font-size: %dpx; font-weight: normal; }'
            ' QLineEdit:focus { border-color: %s; }'
            % (PAINEL, self._borda_px, BOTAO, TEXTO, ATIVO, FONTE_CICLO,
               int(font_px), ATIVO))


class CampoOpcional(CampoCiclo):
    """Caixa que pode ficar vazia: vazio = None (nao usa), 0 e' valor valido.
    Usada no AFASTAMENTO FINAL, onde o valor e' uma posicao absoluta."""

    def __init__(self, decimals=2, parent=None):
        super(CampoOpcional, self).__init__(decimals=decimals, parent=parent)
        self._value = None
        self.setText(u"")

    def set_value(self, v):
        if v is None or v == "":
            self._value = None
            self.setText(u"")
        else:
            super(CampoOpcional, self).set_value(v)

    def _parse(self, emit):
        if not self.text().strip():
            changed = self._value is not None
            self._value = None
            if emit and changed:
                self.committed.emit()
            return None
        return super(CampoOpcional, self)._parse(emit)

    def _fmt(self, v):
        return u"" if v is None else super(CampoOpcional, self)._fmt(v)


class OpcaoCiclo(QCheckBox):
    """Caixa de opcao da faixa padrao (secao 5.4)."""

    def __init__(self, texto, parent=None):
        super(OpcaoCiclo, self).__init__(texto, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.restyle(1.0)

    def setEnabled(self, ligado):
        super(OpcaoCiclo, self).setEnabled(ligado)
        opacidade(self, ligado)

    def restyle(self, s):
        """`s` = escala do desenho (px por unidade do viewBox)."""
        fonte = max(10, int(round(24 * s)))
        ind = max(12, int(round(20 * s)))
        pad = max(6, int(round(14 * s)))
        esp = max(6, int(round(12 * s)))
        check = os.path.join(ICONES_DIR, "check-teal.svg").replace("\\", "/")
        self.setStyleSheet("""
QCheckBox {{
    background: {painel}; border: 2px solid {botao}; border-radius: 5px;
    color: {texto}; font-family: "{fonte_f}"; font-size: {fonte}px;
    padding-left: {pad}px; spacing: {esp}px;
}}
QCheckBox:checked {{ background: {ativo}; border-color: {ativo}; }}
QCheckBox::indicator {{
    width: {ind}px; height: {ind}px; border-radius: 3px;
    border: 2px solid {texto2}; background: {visor};
}}
QCheckBox::indicator:checked {{
    background: {texto}; border-color: {texto}; image: url({check});
}}
""".format(painel=PAINEL, botao=BOTAO, texto=TEXTO, fonte_f=FONTE_CICLO,
           fonte=fonte, pad=pad, esp=esp, ativo=ATIVO, ind=ind, texto2=TEXTO_2,
           visor=VISOR, check=check))
        espacamento(self, 1.0 * s)


class CicloPanel(QWidget):
    """Fundo da tela + widgets posicionados pelo viewBox do desenho.

    Formula da secao 5.1: s = min(W/1460, H/747), desenho centrado; um item
    em (x, y, w, h) do viewBox vai para (ox + (x-160)*s, oy + (y+30)*s) com
    w*s x h*s, e a fonte do valor e' fonte_valor*s."""

    def __init__(self, tela, parent=None):
        super(CicloPanel, self).__init__(parent)
        self._itens = []                  # (widget, (x, y, w, h), fonte_vb)
        self._extras = []                 # widgets fixos (faixa padrao)
        self._pix = QPixmap()
        self.setMinimumSize(520, 280)
        self.set_tela(tela, [])

    def set_tela(self, tela, itens):
        """Troca o fundo e o conjunto de campos. `itens` = [(widget, caixa,
        fonte_valor)]. Widgets que saem sao escondidos, mas guardam o valor."""
        self._tela = tela
        nome = os.path.basename(tela.get("fundo_com_rotulos", ""))
        self._pix = QPixmap(os.path.join(FUNDOS_DIR, nome))
        anteriores = [w for (w, _c, _f) in self._itens]
        self._itens = list(itens)
        atuais = set(id(w) for (w, _c, _f) in self._itens)
        for w in anteriores:
            if id(w) not in atuais:
                w.hide()
        for (w, _c, _f) in self._itens:
            w.setParent(self)
            w.show()
        self.update()
        self.relayout()

    def add_fixo(self, widget, caixa, fonte_vb=None):
        """Widget que fica em todas as telas (faixa padrao)."""
        widget.setParent(self)
        self._extras.append((widget, tuple(caixa), fonte_vb))
        widget.show()

    # -- geometria ---------------------------------------------------------
    def escala(self):
        w, h = float(self.width()), float(self.height())
        s = min(w / VB_W, h / VB_H)
        ox = (w - VB_W * s) / 2.0
        oy = (h - VB_H * s) / 2.0
        return s, ox, oy

    def _posiciona(self, widget, caixa, fonte_vb, s, ox, oy):
        x, y, cw, ch = caixa
        if fonte_vb is not None and hasattr(widget, "restyle"):
            if isinstance(widget, CampoCiclo):
                widget.set_borda(2.5 * s)
                widget.restyle(fonte_vb * s)
            else:
                widget.restyle(s)
        widget.setGeometry(int(round(ox + (x - VB_X) * s)),
                           int(round(oy + (y - VB_Y) * s)),
                           int(round(cw * s)), int(round(ch * s)))

    def relayout(self):
        s, ox, oy = self.escala()
        if s <= 0:
            return
        for (w, caixa, fonte) in self._itens:
            self._posiciona(w, caixa[:4], fonte, s, ox, oy)
        for (w, caixa, fonte) in self._extras:
            self._posiciona(w, caixa, fonte, s, ox, oy)

    def resizeEvent(self, event):
        super(CicloPanel, self).resizeEvent(event)
        self.relayout()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(BORDA), 1))
        p.setBrush(QColor(VISOR))
        p.drawRoundedRect(r, 8, 8)
        if not self._pix.isNull():
            s, ox, oy = self.escala()
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.drawPixmap(QRectF(ox, oy, VB_W * s, VB_H * s), self._pix,
                         QRectF(self._pix.rect()))
        p.end()

    def diagnostico(self):
        pass


# ── faixa padrao: 4 opcoes + AFASTAMENTO FINAL ───────────────────────────────
# (chave interna, texto, x, y) no viewBox; caixas de 316 x 44 (secao 5.4)
OPCOES_PADRAO = [
    ("finishOnly",     u"SOMENTE ACABAMENTO",         172.0, 605.0),
    ("useCannedCycle", u"GERAR CICLO",                498.0, 605.0),
    ("pausaNoFinal",   u"USAR PAUSA NO FINAL",        172.0, 661.0),
    ("ferramentaFinal", u"CHAMAR FERRAMENTA NO FINAL", 498.0, 661.0),
]
AFASTAMENTO_FINAL = [
    ("afastamentoFinalZAbs", (1293.0, 657.0, 120.0, 50.0)),
    ("afastamentoFinalXAbs", (1488.0, 657.0, 120.0, 50.0)),
]


class FaixaPadrao(object):
    """As 4 opcoes + o AFASTAMENTO FINAL, na mesma posicao nas 13 telas.

    Cada tela liga so' o que tem logica no engine (ver `ligar`); o resto fica
    visivel e desabilitado (secao 5.4 do handoff) e e' listado no relatorio."""

    def __init__(self, panel, ao_mudar):
        self.opcoes = {}
        self.campos = {}
        self._ligadas = set()
        for chave, texto, x, y in OPCOES_PADRAO:
            o = OpcaoCiclo(texto)
            o.toggled.connect(ao_mudar)
            self.opcoes[chave] = o
            panel.add_fixo(o, (x, y, 316.0, 44.0), fonte_vb=1.0)
        for chave, caixa in AFASTAMENTO_FINAL:
            e = CampoOpcional()
            e.committed.connect(ao_mudar)
            self.campos[chave] = e
            panel.add_fixo(e, caixa, fonte_vb=38.0)
        for w in list(self.opcoes.values()) + list(self.campos.values()):
            w.setEnabled(False)
            w.setToolTip(u"Sem efeito nesta operação.")

    def ligar(self, chave, dica=u""):
        """Habilita uma opcao que tem logica nesta operacao."""
        w = self.opcoes.get(chave) or self.campos.get(chave)
        if w is None:
            return
        w.setEnabled(True)
        w.setToolTip(dica)
        self._ligadas.add(chave)

    def travar(self, chave, dica):
        """Opcao com logica, mas bloqueada (ex.: ciclo fixo invalido no 2.9)."""
        w = self.opcoes.get(chave) or self.campos.get(chave)
        if w is None:
            return
        w.setEnabled(False)
        w.setToolTip(dica)
        self._ligadas.add(chave)

    def desligar(self, chave, dica):
        """Opcao sem efeito no modo atual da tela (ex.: ciclo no Desbaste Int
        AVANCADO): desmarca e desabilita; o collect grava False."""
        o = self.opcoes.get(chave)
        if o is None:
            return
        o.blockSignals(True)
        o.setChecked(False)
        o.blockSignals(False)
        o.setEnabled(False)
        o.setToolTip(dica)
        self._ligadas.add(chave)

    def chaves(self):
        """Chaves que a tela le/grava nos params (as que tem logica)."""
        return [k for k in self.opcoes if k in self._ligadas]

    def load(self, params):
        for k in self.chaves():
            o = self.opcoes[k]
            o.blockSignals(True)
            o.setChecked(bool(params.get(k, False)))
            o.blockSignals(False)
        for k, e in self.campos.items():
            if k in self._ligadas:
                e.blockSignals(True)
                e.set_value(params.get(k))
                e.blockSignals(False)

    def collect(self, params):
        for k in self.chaves():
            params[k] = bool(self.opcoes[k].isChecked())
        for k, e in self.campos.items():
            if k in self._ligadas and e.isEnabled():
                params[k] = e.commit()        # le o que estiver digitado


# ── faixa inferior: CONFIG. / CORTE em celulas ───────────────────────────────
_FAIXA_QSS = """
QFrame#faixaInferior {{ background: {painel}; border: 1px solid {borda}; border-radius: 8px; }}
QLabel[faixaLinha="true"] {{ color: {texto2}; font-family: "{f}"; font-size: 15px; background: transparent; border: none; }}
QWidget[celulaFaixa="true"] {{ background: {visor}; border-radius: 6px; }}
QLabel[celulaRotulo="true"] {{ color: {texto2}; font-family: "{f}"; font-size: 12px; background: transparent; border: none; }}
QLabel[celulaUnidade="true"] {{ color: {texto2}; font-family: "{f}"; font-size: 13px; background: transparent; border: none; }}
QComboBox[celulaValor="true"] {{ background: transparent; border: none; color: {texto}; font-family: "{f}"; font-size: 22px; padding: 0px; min-height: 0px; }}
QComboBox[celulaValor="true"]::drop-down {{ border: none; width: 16px; background: transparent; }}
QComboBox[celulaValor="true"]::down-arrow {{ image: url({seta}); width: 12px; height: 12px; }}
QComboBox[celulaValor="true"] QAbstractItemView {{ background: {painel}; color: {texto}; font-family: "{f}"; font-size: 20px; selection-background-color: {ativo}; }}
QLineEdit[celulaTexto="true"] {{ background: transparent; border: none; color: {texto}; font-family: "{f}"; font-size: 22px; padding: 0px; }}
QAbstractSpinBox[celulaNumero="true"] {{ background: transparent; border: none; color: {numero}; font-family: "{f}"; font-size: 26px; padding: 0px; }}
"""


class FaixaInferior(QFrame):
    """Linhas com titulo a esquerda e celulas (secao 6.1 do handoff).

    `linhas` = [(titulo, [(rotulo, widget, unidade), ...]), ...]. Os widgets
    sao os Touch* que cada tela ja usa; aqui eles so ganham o visual de
    celula."""

    def __init__(self, linhas, parent=None):
        super(FaixaInferior, self).__init__(parent)
        self.setObjectName("faixaInferior")
        seta = os.path.join(ICONES_DIR, "seta-baixo.svg").replace("\\", "/")
        self.setStyleSheet(_FAIXA_QSS.format(
            painel=PAINEL, borda=BORDA, texto2=TEXTO_2, visor=VISOR, texto=TEXTO,
            ativo=ATIVO, numero=NUMERO, seta=seta, f=FONTE_CICLO))
        grid = QGridLayout(self)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        ncol = max(len(c) for _t, c in linhas) if linhas else 0
        for r, (titulo, celulas) in enumerate(linhas):
            t = QLabel(titulo)
            t.setProperty("faixaLinha", True)
            t.setFixedWidth(92)
            espacamento(t, 2.0)
            grid.addWidget(t, r, 0)
            # linha com menos celulas: o campo de texto (TITULO) ocupa as
            # colunas que sobram, como na referencia; sem ele, ficam vazias
            sobra = ncol - len(celulas)
            texto = [i for i, (_r, w, _u) in enumerate(celulas)
                     if isinstance(w, QLineEdit)]
            col = 1
            for c, (rotulo, widget, unidade) in enumerate(celulas):
                span = 1 + sobra if (texto and c == texto[0]) else 1
                grid.addWidget(self._celula(rotulo, widget, unidade),
                               r, col, 1, span)
                col += span
            grid.setRowMinimumHeight(r, 58)
        for c in range(ncol):
            grid.setColumnStretch(c + 1, 1)

    @staticmethod
    def _celula(rotulo, widget, unidade):
        cel = QWidget()
        cel.setProperty("celulaFaixa", True)
        cel.setAttribute(Qt.WA_StyledBackground, True)
        cel.setMinimumHeight(58)
        v = QVBoxLayout(cel)
        v.setContentsMargins(12, 6, 10, 4)
        v.setSpacing(0)
        lab = QLabel(rotulo)
        lab.setProperty("celulaRotulo", True)
        espacamento(lab, 1.5)
        v.addWidget(lab)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        nome = type(widget).__name__
        # os Touch* trazem folha propria (fundo cinza, 48 px); ela venceria a
        # da celula, entao sai
        widget.setStyleSheet("")
        if isinstance(widget, QAbstractSpinBox):
            widget.setProperty("celulaNumero", True)
            widget.setButtonSymbols(QAbstractSpinBox.NoButtons)
            widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if hasattr(widget, "setSuffix"):
                widget.setSuffix("")
        elif "Combo" in nome:
            widget.setProperty("celulaValor", True)
            if hasattr(widget, "usar_estilo_celula"):
                widget.usar_estilo_celula()     # ComboRoscas pinta a cor da rosca
        else:
            widget.setProperty("celulaTexto", True)
        if unidade and isinstance(widget, QAbstractSpinBox):
            # unidade logo depois do numero (como na referencia): o campo
            # fica da largura do texto e o resto da celula e espaco vazio
            widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            _LarguraDoTexto(widget)
            h.addWidget(widget, 0, Qt.AlignBottom)
            u = QLabel(unidade)
            u.setProperty("celulaUnidade", True)
            u.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
            u.setContentsMargins(0, 0, 0, 7)     # na linha de base do numero
            h.addWidget(u, 0, Qt.AlignBottom)
            h.addStretch(1)
        else:
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            widget.setMinimumWidth(40)
            h.addWidget(widget, 1)
            if unidade:
                u = QLabel(unidade)
                u.setProperty("celulaUnidade", True)
                h.addWidget(u, 0)
        v.addLayout(h)
        return cel


class _LarguraDoTexto(QObject):
    """Mantem um spinbox da largura do numero que ele mostra (a fonte so e
    conhecida depois do polish, por isso recalcula na troca de fonte)."""

    def __init__(self, spin):
        super(_LarguraDoTexto, self).__init__(spin)
        self._spin = spin
        spin.installEventFilter(self)
        spin.lineEdit().textChanged.connect(self._ajustar)
        self._ajustar()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Polish, QEvent.FontChange, QEvent.StyleChange,
                         QEvent.Show):
            self._ajustar()
        return False

    def _ajustar(self, *_a):
        sp = self._spin
        fm = sp.fontMetrics()
        txt = sp.lineEdit().text() or "0"
        try:
            w = fm.horizontalAdvance(txt)
        except AttributeError:
            w = fm.width(txt)
        sp.setFixedWidth(max(24, w + 4))
