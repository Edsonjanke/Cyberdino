"""Widgets customizados para painel CyberDino.

MpgButton        - indicador MPG controlado por HAL pin
ReadOnlyAction   - indicador de modo (MAN/AUTO/MDI) que nao aceita click
SafeCycleStart   - cycle start que exige modo AUTO, senao mostra mensagem
GearButton       - botao toggle de marcha (alta/reduzida) com QSettings persistente
"""
import linuxcnc
from qtpy.QtCore import Qt, Property, QSettings
from qtpy.QtWidgets import QPushButton, QMessageBox
from qtpyvcp import hal
from qtpyvcp.widgets import HALWidget, VCPWidget
from qtpyvcp.actions import bindWidget, InvalidAction
from qtpyvcp.widgets.button_widgets.action_button import ActionButton


class MpgButton(QPushButton, HALWidget, VCPWidget):
    """Indicador MPG controlado por HAL pin .in (somente leitura)."""

    def __init__(self, parent=None):
        super(MpgButton, self).__init__(parent)
        self.setText("MPG")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._in_pin = None

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def initialize(self):
        comp = hal.getComponent()
        obj_name = self.getPinBaseName()
        self._in_pin = comp.addPin(obj_name + ".in", "bit", "in")
        self._in_pin.valueChanged.connect(self.setChecked)


class ReadOnlyAction(QPushButton, VCPWidget):
    """Indicador de modo que acompanha a action mas nao aceita click."""

    def __init__(self, parent=None):
        super(ReadOnlyAction, self).__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._action_name = ''

    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    @Property(str)
    def actionName(self):
        return self._action_name

    @actionName.setter
    def actionName(self, action_name):
        self._action_name = action_name
        try:
            bindWidget(self, action_name)
        except InvalidAction:
            pass


class SafeCycleStart(ActionButton):
    """Cycle Start que verifica modo AUTO antes de executar.

    Mantem toda funcionalidade original (bindWidget, rules, run-from-line).
    Bloqueia click se nao estiver em modo AUTO.
    Tambem monitora HAL pin .blocked para mostrar aviso do botao fisico.
    """

    def __init__(self, parent=None):
        super(SafeCycleStart, self).__init__(parent)
        self._stat = linuxcnc.stat()
        self._blocked_pin = None

    def initialize(self):
        comp = hal.getComponent()
        obj_name = str(self.objectName()).replace('_', '-')
        self._blocked_pin = comp.addPin(obj_name + ".blocked", "bit", "in")
        self._blocked_pin.valueChanged.connect(self._on_blocked)

    def _on_blocked(self, value):
        if value:
            self._show_warning()

    def _show_warning(self):
        msg = QMessageBox(self.window())
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Modo Incorreto")
        msg.setText(u"Máquina não está em modo AUTO!\n\n"
                    u"Selecione AUTO no seletor de modo\n"
                    u"para executar o programa.")
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowStaysOnTopHint)
        msg.exec_()

    def mousePressEvent(self, event):
        try:
            self._stat.poll()
            if self._stat.task_mode != linuxcnc.MODE_AUTO:
                self._show_warning()
                event.ignore()
                return
        except Exception:
            pass
        super(SafeCycleStart, self).mousePressEvent(event)


class GearButton(QPushButton, HALWidget, VCPWidget):
    """Botao toggle de marcha (alta/reduzida) com persistencia QSettings.

    HAL pins:
      .checked  (bit out)  - estado da marcha (TRUE = reduzida)
      .spinning (bit in)   - desabilita botao quando spindle ligado
    Estado salvo entre sessoes em QSettings(DinoEvo/Gearbox).
    Texto/cor mudam conforme estado.
    """

    def __init__(self, parent=None):
        super(GearButton, self).__init__(parent)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self._checked_pin = None
        self._spinning_pin = None
        self._settings = QSettings("DinoEvo", "Gearbox")
        saved = self._settings.value("gear_low", False, type=bool)
        self.setChecked(saved)
        self._update_label()
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        self._update_label()
        self._settings.setValue("gear_low", checked)
        self._settings.sync()
        if self._checked_pin is not None:
            self._checked_pin.value = checked

    def _update_label(self):
        if self.isChecked():
            self.setText("REDUZIDA 600")
        else:
            self.setText("ALTA 2360")

    def _on_spinning_changed(self, spinning):
        self.setEnabled(not spinning)

    def initialize(self):
        comp = hal.getComponent()
        obj_name = self.getPinBaseName()
        self._checked_pin = comp.addPin(obj_name + ".checked", "bit", "out")
        self._checked_pin.value = self.isChecked()
        self._spinning_pin = comp.addPin(obj_name + ".spinning", "bit", "in")
        self._spinning_pin.valueChanged.connect(self._on_spinning_changed)
