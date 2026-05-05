"""Widgets customizados para painel CyberDino.

MpgButton        - indicador MPG controlado por HAL pin
ReadOnlyAction   - indicador de modo (MAN/AUTO/MDI) que nao aceita click
SafeCycleStart   - cycle start que exige modo AUTO, senao mostra mensagem
GearButton       - botao toggle de marcha (alta/reduzida) com QSettings persistente
GearSelector     - selecao de 6 marchas (radio group) com 3 pinos sel0/sel1/sel2 + QSettings
GearLabel        - rotulo que mostra a marcha atual lendo 3 bits sel0/sel1/sel2
"""
import linuxcnc
from qtpy.QtCore import Qt, Property, QSettings
from qtpy.QtWidgets import (QPushButton, QMessageBox, QWidget, QGridLayout,
                            QButtonGroup, QLabel)
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


class GearSelector(QWidget, HALWidget, VCPWidget):
    """Seletor de 6 marchas (mutuamente exclusivo) com saida em 3 pinos sel0..sel2.

    Cada marcha mapeia para um indice 0..5 codificado em binario (LSB = sel0)
    para alimentar diretamente os pinos sel0..sel2 de mux16 (sel3 fixo em 0).

    HAL pins:
      .sel0 / .sel1 / .sel2  (bit out) - indice da marcha em binario
      .spinning              (bit in)  - desabilita troca enquanto spindle gira
    Estado salvo entre sessoes em QSettings(DinoEvo/Gearbox6).
    """

    GEARS = [
        ("M01 2360", 2360),
        ("M02 1500", 1500),
        ("M03 950",   950),
        ("M04 600",   600),
        ("M05 375",   375),
        ("M06 236",   236),
    ]

    def __init__(self, parent=None):
        super(GearSelector, self).__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)

        self._sel0_pin = None
        self._sel1_pin = None
        self._sel2_pin = None
        self._spinning_pin = None

        self._settings = QSettings("DinoEvo", "Gearbox6")
        saved_idx = int(self._settings.value("gear_idx", 0))
        if saved_idx < 0 or saved_idx >= len(self.GEARS):
            saved_idx = 0

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(6)

        self._buttons = []
        for i, (label, _rpm) in enumerate(self.GEARS):
            btn = QPushButton(label, self)
            btn.setCheckable(True)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setMinimumHeight(50)
            self._group.addButton(btn, i)
            row = i // 3
            col = i % 3
            layout.addWidget(btn, row, col)
            self._buttons.append(btn)

        self._buttons[saved_idx].setChecked(True)
        self._group.idToggled.connect(self._on_id_toggled)

    def _on_id_toggled(self, idx, checked):
        if not checked:
            return
        self._settings.setValue("gear_idx", idx)
        self._settings.sync()
        self._publish(idx)

    def _publish(self, idx):
        if self._sel0_pin is not None:
            self._sel0_pin.value = bool(idx & 0x1)
        if self._sel1_pin is not None:
            self._sel1_pin.value = bool(idx & 0x2)
        if self._sel2_pin is not None:
            self._sel2_pin.value = bool(idx & 0x4)

    def _on_spinning_changed(self, spinning):
        self.setEnabled(not spinning)

    def initialize(self):
        comp = hal.getComponent()
        obj_name = self.getPinBaseName()
        self._sel0_pin = comp.addPin(obj_name + ".sel0", "bit", "out")
        self._sel1_pin = comp.addPin(obj_name + ".sel1", "bit", "out")
        self._sel2_pin = comp.addPin(obj_name + ".sel2", "bit", "out")
        self._spinning_pin = comp.addPin(obj_name + ".spinning", "bit", "in")
        self._spinning_pin.valueChanged.connect(self._on_spinning_changed)
        # Publica estado inicial
        self._publish(self._group.checkedId())


class GearLabel(QLabel, HALWidget, VCPWidget):
    """Rotulo que mostra a marcha atual lendo 3 pinos de input sel0/sel1/sel2.

    Indice 0..5 -> texto "M0X 9999". Mesma lista do GearSelector.

    HAL pins:
      .sel0 / .sel1 / .sel2  (bit in) - indice da marcha em binario
    """

    GEARS = [
        ("M01", 2360),
        ("M02", 1500),
        ("M03",  950),
        ("M04",  600),
        ("M05",  375),
        ("M06",  236),
    ]

    def __init__(self, parent=None):
        super(GearLabel, self).__init__(parent)
        self._sel0_pin = None
        self._sel1_pin = None
        self._sel2_pin = None
        self._idx = 0
        self._update_text()

    def _read_idx(self):
        s0 = bool(self._sel0_pin.value) if self._sel0_pin is not None else False
        s1 = bool(self._sel1_pin.value) if self._sel1_pin is not None else False
        s2 = bool(self._sel2_pin.value) if self._sel2_pin is not None else False
        return (1 if s0 else 0) | (2 if s1 else 0) | (4 if s2 else 0)

    def _update_text(self):
        idx = self._idx
        if 0 <= idx < len(self.GEARS):
            _name, rpm = self.GEARS[idx]
            self.setText("RPM {}".format(rpm))
        else:
            self.setText("--")

    def _on_pin_changed(self, _value):
        self._idx = self._read_idx()
        self._update_text()

    def initialize(self):
        comp = hal.getComponent()
        obj_name = self.getPinBaseName()
        self._sel0_pin = comp.addPin(obj_name + ".sel0", "bit", "in")
        self._sel1_pin = comp.addPin(obj_name + ".sel1", "bit", "in")
        self._sel2_pin = comp.addPin(obj_name + ".sel2", "bit", "in")
        self._sel0_pin.valueChanged.connect(self._on_pin_changed)
        self._sel1_pin.valueChanged.connect(self._on_pin_changed)
        self._sel2_pin.valueChanged.connect(self._on_pin_changed)
        self._idx = self._read_idx()
        self._update_text()
