"""DinoGcodeTextEdit - editor de G-code com seta na linha em execução.

Igual ao GcodeTextEdit do qtpyvcp, mas a margem dos números de linha ganha
uma seta à esquerda do número da linha que a máquina está executando
(STATUS.motion_line). A seta só aparece com programa rodando em AUTO:
verde executando, teal em pausa. Com o programa parado ela some.

A seta segue a linha da máquina, não o cursor: se o operador rolar ou clicar
em outra linha durante a usinagem, a seta continua na linha que está cortando.

As cores do G-code são as mesmas do PROGRAMA da aba GERAR PGM (RealceGcode):
G0 vermelho, corte verde, demais G teal, T/M amarelo, comentário cinza. O
realce do qtpyvcp (YAML apontado pelo INI) fica de fora para não haver dois
realces no mesmo documento. DinoGcodeTextEditCores é só a parte das cores
(editor da aba ARQUIVO); DinoGcodeTextEdit soma a seta (aba PRINCIPAL).
"""

import linuxcnc

from qtpy.QtCore import Qt, QPointF, QEvent
from qtpy.QtGui import QColor, QPainter, QPen, QPolygonF
from qtpy.QtWidgets import QPlainTextEdit

from qtpyvcp.plugins import getPlugin
from qtpyvcp.widgets.input_widgets.gcode_text_edit import (
    GcodeTextEdit, NumberMargin,
)

from torno_cam_ui.realce_gcode import RealceGcode

STATUS = getPlugin('status')

ARROW_RUN_COLOR = QColor('#3DDC84')    # verde, executando
ARROW_PAUSE_COLOR = QColor('#00838F')  # teal, pausa (paleta teal: sem ambar)
ARROW_BORDER_COLOR = QColor('#000000')


class ArrowNumberMargin(NumberMargin):

    def arrowWidth(self):
        return int(self.parent.fontMetrics().height() * 0.8) + 4

    def getWidth(self):
        return super().getWidth() + self.arrowWidth()

    def paintEvent(self, event):
        # números de linha como no original, a seta vai por cima
        super().paintEvent(event)

        line = self.parent.runningLine()
        if line < 1:
            return

        block = self.parent.document().findBlockByNumber(line - 1)
        if not block.isValid() or not block.isVisible():
            return

        top = self.parent.blockBoundingGeometry(block).translated(
            self.parent.contentOffset()).top()
        h = self.parent.fontMetrics().height()
        if top + h < 0 or top > self.height():
            return

        x0 = 2.0
        x1 = x0 + self.arrowWidth() - 4
        y0 = top + 2
        y1 = top + h - 2
        arrow = QPolygonF([QPointF(x0, y0),
                           QPointF(x1, (y0 + y1) / 2.0),
                           QPointF(x0, y1)])

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(ARROW_BORDER_COLOR, 1.5))
        painter.setBrush(ARROW_PAUSE_COLOR if self.parent.isPaused()
                         else ARROW_RUN_COLOR)
        painter.drawPolygon(arrow)
        painter.end()


class DinoGcodeTextEditCores(GcodeTextEdit):
    """GcodeTextEdit com as cores do PROGRAMA do GERAR PGM (sem a seta)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # guardar a referência do realce (senão o GC leva)
        self._realce = RealceGcode(self.document())

    def setPlainText(self, p_str):
        # o GcodeTextEdit cria um documento novo a cada programa carregado;
        # o realce do qtpyvcp fica desligado e o documento novo ganha o nosso
        ligado = self.syntax_highlighting
        self.syntax_highlighting = False
        try:
            super().setPlainText(p_str)
        finally:
            self.syntax_highlighting = ligado
        self._realce = RealceGcode(self.document())

    def changeEvent(self, event):
        # o GcodeTextEdit recria o realce do qtpyvcp a cada troca de fonte;
        # aqui o evento vai direto para o QPlainTextEdit (o nosso realce não
        # depende da fonte)
        if event.type() == QEvent.FontChange:
            QPlainTextEdit.changeEvent(self, event)
            return
        super().changeEvent(event)


class DinoGcodeTextEdit(DinoGcodeTextEditCores):

    def __init__(self, parent=None):
        super().__init__(parent)

        # troca a margem padrão pela que desenha a seta
        old = self.margin
        try:
            self.blockCountChanged.disconnect(old.updateWidth)
            self.updateRequest.disconnect(old.updateContents)
        except (TypeError, RuntimeError):
            pass
        old.hide()
        old.deleteLater()
        self.margin = ArrowNumberMargin(self)
        self.margin.updateWidth()

        self._running_line = 0

        STATUS.motion_line.onValueChanged(self._onMotionLine)
        STATUS.interp_state.notify(self._onRunStateChanged)
        STATUS.task_mode.notify(self._onRunStateChanged)

    def runningLine(self):
        stat = STATUS.stat
        if stat.task_mode != linuxcnc.MODE_AUTO \
                or stat.interp_state == linuxcnc.INTERP_IDLE:
            return 0
        return self._running_line

    def isPaused(self):
        stat = STATUS.stat
        return stat.interp_state == linuxcnc.INTERP_PAUSED or bool(stat.paused)

    def _onMotionLine(self, line):
        self._running_line = int(line or 0)
        self.margin.update()

    def _onRunStateChanged(self, *args):
        self.margin.update()
