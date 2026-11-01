# Realce de cores do G-code no painel PROGRAMA (padrão das telas de ciclo da EVO).
# Uso: self._realce = RealceGcode(self.programa.document())   (guardar a referência)
from qtpy.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from qtpy.QtCore import QRegularExpression


class RealceGcode(QSyntaxHighlighter):
    # A ordem importa: cada regra pinta por cima da anterior.
    # (?<![A-Z]) em vez de \b: funciona também com códigos colados, como "G18G40G80G95".
    REGRAS = [
        (r"(?<![A-Z])G\d+(?:\.\d+)?", "#5FB3BB"),                       # demais códigos G (G21, G18, G54, G96...)
        (r"(?<![A-Z])G0*0(?![.\d])", "#FF7B72"),                           # G0 / G00: rápido, vermelho
        (r"(?<![A-Z])(?:G0*[123]|G33(?:\.1)?|G76|G73|G8[1-9])(?![.\d])",
         "#3DDC84"),                                                       # movimentos de corte, verde
        (r"(?<![A-Z])[TM]\d+(?![.\d])", "#F2C14E"),                       # ferramenta e funções M, amarelo
        (r"\([^)]*\)|;.*$|^\s*%\s*$", "#6F7884"),                          # comentários e %, cinza (por último)
    ]

    def __init__(self, documento):
        super().__init__(documento)
        self._regras = []
        for padrao, cor in self.REGRAS:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(cor))
            rx = QRegularExpression(padrao, QRegularExpression.CaseInsensitiveOption)
            self._regras.append((rx, fmt))

    def highlightBlock(self, texto):
        for rx, fmt in self._regras:
            it = rx.globalMatch(texto)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
