# -*- coding: utf-8 -*-
"""Widgets touch-friendly para a aba GERAR PGM (fonte grande, sem setinhas,
locale C para o ponto decimal, commit do texto antes de ler)."""

from qtpy.QtWidgets import (QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit,
                            QStyledItemDelegate)
from qtpy.QtCore import QLocale, Qt, QTimer


_SPIN_QSS = """
QAbstractSpinBox, QComboBox, QLineEdit {
    background: #1E2224;
    color: #E6E6E6;
    border: 1px solid #3A3F43;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 36px;
    font: 15pt "Bebas Kai";
}
QComboBox::drop-down { width: 26px; }
"""


class TouchDoubleSpin(QDoubleSpinBox):
    def __init__(self, decimals=3, minimum=-99999.0, maximum=99999.0,
                 step=0.1, suffix="", parent=None):
        super(TouchDoubleSpin, self).__init__(parent)
        self.setLocale(QLocale.c())          # exibe sempre com ponto decimal
        self.setDecimals(decimals)
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        if suffix:
            self.setSuffix(" " + suffix)
        self.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setStyleSheet(_SPIN_QSS)

    # Aceita VIRGULA como separador decimal (teclado BR e habito do operador).
    # Sem isso a virgula era recusada e "0,2" virava "02" = 2.0 — o campo so
    # aceitava inteiros na pratica.
    def validate(self, text, pos):
        return super(TouchDoubleSpin, self).validate(text.replace(",", "."), pos)

    def valueFromText(self, text):
        return super(TouchDoubleSpin, self).valueFromText(text.replace(",", "."))

    def focusInEvent(self, event):
        # No touch o toque poe o cursor depois do sufixo (" mm/v"); selecionar
        # tudo faz o que for digitado substituir o valor.
        super(TouchDoubleSpin, self).focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def committed_value(self):
        self.interpretText()   # garante que o texto digitado foi lido
        return self.value()


class TouchIntSpin(QSpinBox):
    def __init__(self, minimum=0, maximum=999999, step=1, suffix="", parent=None):
        super(TouchIntSpin, self).__init__(parent)
        self.setLocale(QLocale.c())
        self.setRange(minimum, maximum)
        self.setSingleStep(step)
        if suffix:
            self.setSuffix(" " + suffix)
        self.setButtonSymbols(QSpinBox.NoButtons)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setStyleSheet(_SPIN_QSS)

    def focusInEvent(self, event):
        super(TouchIntSpin, self).focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def committed_value(self):
        self.interpretText()
        return self.value()


class TouchCombo(QComboBox):
    """Combo cujos itens carregam (label, valor). value()/set_value operam no
    valor, nao no indice."""

    def __init__(self, options, parent=None):
        super(TouchCombo, self).__init__(parent)
        self._values = []
        for label, value in options:
            self.addItem(label)
            self._values.append(value)
        self.setStyleSheet(_SPIN_QSS)

    def committed_value(self):
        i = self.currentIndex()
        return self._values[i] if 0 <= i < len(self._values) else None

    def set_value(self, value):
        for i, v in enumerate(self._values):
            if v == value:
                self.setCurrentIndex(i)
                return
        self.setCurrentIndex(0)


class TouchLine(QLineEdit):
    def __init__(self, parent=None):
        super(TouchLine, self).__init__(parent)
        self.setStyleSheet(_SPIN_QSS)

    def committed_value(self):
        return self.text()

    def set_value(self, value):
        self.setText(str(value))


class _DelegadoCorItem(QStyledItemDelegate):
    """Pinta o texto de cada item na cor dele.

    Necessario porque tanto o tema (`QComboBox { color: white }`) quanto o
    estilo local definem `color`, e folha de estilo VENCE o ForegroundRole do
    item — as cores simplesmente nao apareciam. Desenhando o texto aqui, a
    folha de estilo nao tem como sobrepor."""

    def __init__(self, cores, parent=None):
        super(_DelegadoCorItem, self).__init__(parent)
        self._cores = list(cores)

    def paint(self, painter, option, index):
        from qtpy.QtWidgets import QStyleOptionViewItem, QStyle, QApplication
        from qtpy.QtGui import QColor
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        texto = opt.text
        opt.text = ""                      # fundo/selecao pelo estilo normal
        widget = opt.widget
        estilo = widget.style() if widget is not None else QApplication.style()
        estilo.drawControl(QStyle.CE_ItemViewItem, opt, painter, widget)
        linha = index.row()
        cor = self._cores[linha] if 0 <= linha < len(self._cores) else "#E6E6E6"
        painter.save()
        painter.setPen(QColor(cor))
        rect = estilo.subElementRect(QStyle.SE_ItemViewItemText, opt, widget)
        painter.drawText(rect.adjusted(6, 0, 0, 0),
                         Qt.AlignVCenter | Qt.AlignLeft, texto)
        painter.restore()


class ComboRoscas(QComboBox):
    """Combo da tabela de roscas: passo PADRAO em verde, passos FINOS em
    amarelo (pedido do operador — da para escolher no toque sem consultar
    tabela). O item guarda o dict completo da rosca."""

    def __init__(self, itens, parent=None):
        super(ComboRoscas, self).__init__(parent)
        from qtpy.QtGui import QBrush, QColor
        self._itens = list(itens)
        self.setStyleSheet(_SPIN_QSS)
        cores = [it.get("cor", "#E6E6E6") for it in self._itens]
        for i, it in enumerate(self._itens):
            self.addItem(it["nome"])
            self.setItemData(i, QBrush(QColor(cores[i])), Qt.ForegroundRole)
        self.setMaxVisibleItems(20)
        # o delegate e' quem realmente faz a cor aparecer (ver _DelegadoCorItem)
        self._delegado = _DelegadoCorItem(cores, self)
        self.setItemDelegate(self._delegado)
        self.currentIndexChanged.connect(self._pintar_fechado)
        self._pintar_fechado(self.currentIndex())

    def _pintar_fechado(self, indice):
        """A caixa fechada tambem mostra a cor da rosca escolhida."""
        cor = "#E6E6E6"
        if 0 <= indice < len(self._itens):
            cor = self._itens[indice].get("cor", cor)
        self.setStyleSheet(_SPIN_QSS + "\nQComboBox { color: %s; }" % cor)

    def committed_value(self):
        i = self.currentIndex()
        return self._itens[i]["nome"] if 0 <= i < len(self._itens) else None

    def item_atual(self):
        i = self.currentIndex()
        return self._itens[i] if 0 <= i < len(self._itens) else None

    def set_value(self, nome):
        for i, it in enumerate(self._itens):
            if it["nome"] == nome:
                self.setCurrentIndex(i)
                return
        self.setCurrentIndex(0)
