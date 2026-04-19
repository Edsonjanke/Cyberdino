#!/usr/bin/env python3
"""
CyberDino - Painel Secundario (Pi Touch)
DRO (X/Z) + Tool/Feed + Spindle Override + Rapid Override
Roda no PC, exibido na Pi via VNC
"""

import sys
import os
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout,
    QStackedWidget, QLineEdit, QListWidget, QListWidgetItem,
    QSlider, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

# linuxcnc importado sob demanda para nao interferir com ProbeBasic
linuxcnc = None
LIVE = False

def _import_linuxcnc():
    global linuxcnc, LIVE
    if linuxcnc is not None:
        return True
    try:
        import importlib
        linuxcnc = importlib.import_module('linuxcnc')
        LIVE = True
        return True
    except ImportError:
        return False

# -- Cores tema cobre (matching ProbeBasic custom) --
BG_DARK = "#1a1a1a"
BG_PANEL = "#2a2a2a"
BG_BUTTON = "#3a3a3a"
COPPER = "#da8728"
COPPER_LIGHT = "#e8a040"
COPPER_DIM = "#b86410"
TEXT_WHITE = "#e0e0e0"
TEXT_DIM = "#888888"

STYLESHEET = f"""
    QWidget {{
        background-color: {BG_DARK};
        color: {TEXT_WHITE};
    }}
    QFrame#panel {{
        background-color: {BG_PANEL};
        border: 2px solid {COPPER_DIM};
        border-radius: 10px;
    }}
    QLabel#title {{
        color: {COPPER};
        font-size: 16px;
        font-weight: bold;
    }}
    QLabel#axis-label {{
        color: {COPPER};
        font-size: 36px;
        font-weight: bold;
    }}
    QLabel#dro-value {{
        color: {TEXT_WHITE};
        font-size: 36px;
        font-weight: bold;
        font-family: "Monospace";
    }}
    QLabel#override-value {{
        color: {COPPER_LIGHT};
        font-size: 52px;
        font-weight: bold;
        font-family: "Monospace";
    }}
    QLabel#override-label {{
        color: {TEXT_DIM};
        font-size: 16px;
    }}
    QLabel#unit {{
        color: {TEXT_DIM};
        font-size: 20px;
    }}
    QLabel#info-label {{
        color: {COPPER};
        font-size: 22px;
        font-weight: bold;
    }}
    QLabel#info-value {{
        color: {TEXT_WHITE};
        font-size: 28px;
        font-weight: bold;
        font-family: "Monospace";
    }}
    QPushButton#ovr-btn {{
        background-color: {BG_BUTTON};
        color: {COPPER_LIGHT};
        border: 2px solid {COPPER_DIM};
        border-radius: 8px;
        font-size: 24px;
        font-weight: bold;
        min-width: 55px;
        min-height: 45px;
    }}
    QPushButton#ovr-btn:pressed {{
        background-color: {COPPER_DIM};
        color: black;
    }}
    QPushButton#ovr-100 {{
        background-color: {BG_BUTTON};
        color: {TEXT_DIM};
        border: 2px solid {COPPER_DIM};
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        min-width: 55px;
        min-height: 35px;
    }}
    QPushButton#ovr-100:pressed {{
        background-color: {COPPER_DIM};
        color: black;
    }}
    QPushButton#rapid-btn {{
        background-color: {BG_BUTTON};
        color: {COPPER_LIGHT};
        border: 2px solid {COPPER_DIM};
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        min-height: 42px;
    }}
    QPushButton#rapid-btn:pressed {{
        background-color: {COPPER_DIM};
        color: black;
    }}
    QPushButton#rapid-btn-active {{
        background-color: {COPPER_DIM};
        color: black;
        border: 2px solid {COPPER_LIGHT};
        border-radius: 8px;
        font-size: 18px;
        font-weight: bold;
        min-height: 42px;
    }}
    QPushButton#page-btn {{
        background-color: {COPPER_DIM};
        color: black;
        border: 2px solid {COPPER};
        border-radius: 8px;
        font-size: 16px;
        font-weight: bold;
        min-height: 38px;
    }}
    QPushButton#page-btn:pressed {{
        background-color: {COPPER};
    }}
    QLineEdit#mdi-entry {{
        background-color: #2a2a2a;
        color: {TEXT_WHITE};
        border: 2px solid #555555;
        border-radius: 4px;
        font-size: 28px;
        font-family: "Monospace";
        font-weight: bold;
        padding: 4px 8px;
    }}
    QLineEdit#mdi-entry:focus {{
        border-color: {COPPER_LIGHT};
    }}
    QListWidget#mdi-history {{
        background-color: #2a2a2a;
        color: {TEXT_WHITE};
        border: 2px solid #555555;
        border-radius: 4px;
        font-size: 44px;
        font-family: "Monospace";
        font-weight: bold;
    }}
    QListWidget#mdi-history::item {{
        padding: 2px 4px;
    }}
    QListWidget#mdi-history::item:selected {{
        background-color: #3399ff;
        color: white;
    }}
    QPushButton#kbd-letter {{
        background-color: {COPPER};
        color: black;
        border: 1px solid {COPPER_LIGHT};
        border-radius: 4px;
        font-size: 18px;
        font-weight: bold;
        min-width: 50px;
        min-height: 50px;
    }}
    QPushButton#kbd-letter:pressed {{
        background-color: {COPPER_LIGHT};
    }}
    QPushButton#kbd-number {{
        background-color: #e0e0e0;
        color: black;
        border: 1px solid #999999;
        border-radius: 4px;
        font-size: 18px;
        font-weight: bold;
        min-width: 50px;
        min-height: 50px;
    }}
    QPushButton#kbd-number:pressed {{
        background-color: #ffffff;
    }}
    QPushButton#kbd-minus {{
        background-color: #cc3333;
        color: white;
        border: 1px solid #aa2222;
        border-radius: 4px;
        font-size: 18px;
        font-weight: bold;
        min-width: 50px;
        min-height: 50px;
    }}
    QPushButton#kbd-minus:pressed {{
        background-color: #ee4444;
    }}
    QPushButton#kbd-dark {{
        background-color: #333333;
        color: {TEXT_WHITE};
        border: 1px solid #555555;
        border-radius: 4px;
        font-size: 15px;
        font-weight: bold;
        min-height: 50px;
    }}
    QPushButton#kbd-dark:pressed {{
        background-color: #555555;
    }}
    QPushButton#mdi-action {{
        background-color: #333333;
        color: {TEXT_WHITE};
        border: 1px solid #555555;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
    }}
    QPushButton#mdi-action:pressed {{
        background-color: #555555;
    }}
    QPushButton#page-active {{
        background-color: {COPPER};
        color: black;
        border: 2px solid {COPPER_LIGHT};
        border-radius: 4px;
        font-size: 14px;
        font-weight: bold;
    }}
    QPushButton#page-inactive {{
        background-color: #333333;
        color: {TEXT_WHITE};
        border: 2px solid #555555;
        border-radius: 4px;
        font-size: 14px;
        font-weight: bold;
    }}
    QPushButton#page-inactive:pressed {{
        background-color: #555555;
    }}
    QSlider#ovr-slider::groove:horizontal {{
        background: #444444;
        height: 18px;
        border: 1px solid #555555;
        border-radius: 3px;
    }}
    QSlider#ovr-slider::sub-page:horizontal {{
        background: {COPPER};
        border: 1px solid {COPPER_DIM};
        border-radius: 3px;
    }}
    QSlider#ovr-slider::handle:horizontal {{
        background: #e0e0e0;
        border: 1px solid #777777;
        width: 24px;
        margin: -4px 0;
        border-radius: 3px;
    }}
    QLabel#load-value {{
        background-color: #1a1a1a;
        color: {TEXT_WHITE};
        border: 1px solid #555555;
        border-radius: 3px;
        font-size: 14px;
        font-weight: bold;
        padding: 2px;
    }}
    QLabel#slider-value {{
        background-color: #e0e0e0;
        color: black;
        border: 1px solid #999999;
        border-radius: 3px;
        font-size: 13px;
        font-weight: bold;
        padding: 2px;
    }}
    QPushButton#slider-reset {{
        background-color: #333333;
        color: {TEXT_WHITE};
        border: 1px solid #555555;
        border-radius: 3px;
        font-size: 11px;
        font-weight: bold;
        padding: 2px;
    }}
    QPushButton#slider-reset:pressed {{
        background-color: #555555;
    }}
    QSlider#gcode-scroll::groove:vertical {{
        background: #2a2a2a;
        width: 30px;
        border: 1px solid #555555;
        border-radius: 4px;
    }}
    QSlider#gcode-scroll::handle:vertical {{
        background: {COPPER};
        border: 2px solid {COPPER_LIGHT};
        height: 80px;
        margin: 0 -20px;
        border-radius: 6px;
    }}
    QSlider#gcode-scroll::handle:vertical:pressed {{
        background: {COPPER_LIGHT};
    }}
"""


class SecondaryPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CyberDino - Painel")
        self.setFixedSize(800, 480)
        self.setStyleSheet(STYLESHEET)

        # LinuxCNC connection
        self.stat = None
        self.cmd = None
        self._reconnect_counter = 0
        self.rapid_buttons = []
        self.cycle_start_time = None
        self.cycle_elapsed = 0
        self._prev_interp_state = None
        self.mdi_history = []
        self._build_ui()

        # Update timer - 10Hz
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)
        self.timer.start(100)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        # Page 0: DRO (existing)
        dro_page = QWidget()
        self._build_dro_page(dro_page)
        self.stack.addWidget(dro_page)

        # Page 1: MDI
        mdi_page = QWidget()
        self._build_mdi_page(mdi_page)
        self.stack.addWidget(mdi_page)

        # Page 2: GCODE
        gcode_page = QWidget()
        self._build_gcode_page(gcode_page)
        self.stack.addWidget(gcode_page)

        self.stack.setCurrentIndex(0)

    def _build_dro_page(self, page):
        main = QHBoxLayout(page)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        # === LEFT: DRO + Tool/Feed ===
        left_frame = QFrame()
        left_frame.setObjectName("panel")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(15, 10, 15, 10)
        left_layout.setSpacing(6)

        title_dro = QLabel("POSICAO")
        title_dro.setObjectName("title")
        title_dro.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title_dro)

        # X axis
        x_row = QHBoxLayout()
        x_label = QLabel("X")
        x_label.setObjectName("axis-label")
        x_label.setFixedWidth(50)
        x_label.setAlignment(Qt.AlignCenter)
        self.x_value = QLabel("+000.000")
        self.x_value.setObjectName("dro-value")
        self.x_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        x_unit = QLabel("mm")
        x_unit.setObjectName("unit")
        x_unit.setFixedWidth(40)
        x_row.addWidget(x_label)
        x_row.addWidget(self.x_value, 1)
        x_row.addWidget(x_unit)
        left_layout.addLayout(x_row)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet(f"color: {COPPER_DIM};")
        left_layout.addWidget(sep1)

        # Z axis
        z_row = QHBoxLayout()
        z_label = QLabel("Z")
        z_label.setObjectName("axis-label")
        z_label.setFixedWidth(50)
        z_label.setAlignment(Qt.AlignCenter)
        self.z_value = QLabel("+000.000")
        self.z_value.setObjectName("dro-value")
        self.z_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        z_unit = QLabel("mm")
        z_unit.setObjectName("unit")
        z_unit.setFixedWidth(40)
        z_row.addWidget(z_label)
        z_row.addWidget(self.z_value, 1)
        z_row.addWidget(z_unit)
        left_layout.addLayout(z_row)

        # Separator
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color: {COPPER_DIM};")
        left_layout.addWidget(sep2)

        # Tool + Feed (centered)
        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        info_row.addStretch()
        tool_label = QLabel("FERR")
        tool_label.setObjectName("info-label")
        self.tool_value = QLabel("T0")
        self.tool_value.setObjectName("info-value")
        feed_label = QLabel("F")
        feed_label.setObjectName("info-label")
        self.feed_value = QLabel("0")
        self.feed_value.setObjectName("info-value")
        feed_unit = QLabel("mm/min")
        feed_unit.setObjectName("unit")
        cycle_label = QLabel("CICLO")
        cycle_label.setObjectName("info-label")
        self.cycle_value = QLabel("00:00")
        self.cycle_value.setObjectName("info-value")
        info_row.addWidget(tool_label)
        info_row.addWidget(self.tool_value)
        info_row.addSpacing(12)
        info_row.addWidget(feed_label)
        info_row.addWidget(self.feed_value)
        info_row.addSpacing(12)
        info_row.addWidget(cycle_label)
        info_row.addWidget(self.cycle_value)
        info_row.addStretch()
        left_layout.addLayout(info_row)

        # Separator
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"color: {COPPER_DIM};")
        left_layout.addWidget(sep3)

        # Spindle LOAD header
        load_row = QHBoxLayout()
        load_row.setSpacing(6)
        self.spindle_load_value = QLabel("0 %")
        self.spindle_load_value.setObjectName("load-value")
        self.spindle_load_value.setAlignment(Qt.AlignCenter)
        load_lbl = QLabel("SPINDLE\nLOAD")
        load_lbl.setObjectName("slider-reset")
        load_lbl.setAlignment(Qt.AlignCenter)
        load_lbl.setFixedWidth(60)
        load_row.addWidget(self.spindle_load_value, 1)
        load_row.addWidget(load_lbl)
        left_layout.addLayout(load_row)

        # 4 sliders: MVEL / FEED / RPM / RAPID
        self.override_sliders = {}
        for name, key in [("MVEL", "mvel"), ("FEED", "feed"),
                          ("RPM", "rpm"), ("RAPID", "rapid")]:
            row = QHBoxLayout()
            row.setSpacing(6)
            slider = QSlider(Qt.Horizontal)
            slider.setObjectName("ovr-slider")
            slider.setRange(0, 200)
            slider.setValue(100)
            value_lbl = QLabel("100%")
            value_lbl.setObjectName("slider-value")
            value_lbl.setAlignment(Qt.AlignCenter)
            value_lbl.setFixedWidth(55)
            btn_reset = QPushButton(f"{name}\n100%")
            btn_reset.setObjectName("slider-reset")
            btn_reset.setFixedWidth(60)
            btn_reset.clicked.connect(lambda _, s=slider: s.setValue(100))
            slider.valueChanged.connect(
                lambda v, lbl=value_lbl: lbl.setText(f"{v}%"))
            row.addWidget(slider, 1)
            row.addWidget(value_lbl)
            row.addWidget(btn_reset)
            left_layout.addLayout(row)
            self.override_sliders[key] = (slider, value_lbl)

        self._gcode_lines = []
        self._gcode_file = ""
        self._gcode_rendered_file = ""
        self._gcode_last_line = -1
        main.addWidget(left_frame, 3)

        # === RIGHT: Spindle Override + Rapid Override ===
        right_frame = QFrame()
        right_frame.setObjectName("panel")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(15, 10, 15, 10)
        right_layout.setSpacing(4)

        # -- Spindle Override --
        title_ovr = QLabel("SPINDLE")
        title_ovr.setObjectName("title")
        title_ovr.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(title_ovr)

        self.ovr_value = QLabel("100%")
        self.ovr_value.setObjectName("override-label")
        self.ovr_value.setAlignment(Qt.AlignCenter)
        self.ovr_value.setStyleSheet(f"color: {COPPER_LIGHT}; font-size: 28px; font-weight: bold;")
        right_layout.addWidget(self.ovr_value)

        # 5 buttons in 3 rows: [50%] / [75%  100%] / [150%  200%]
        self.spindle_buttons = []

        sovr_row1 = QHBoxLayout()
        sovr_row1.setSpacing(6)
        btn = QPushButton("50%")
        btn.setObjectName("rapid-btn")
        btn.clicked.connect(lambda _, p=50: self._set_override(p))
        sovr_row1.addWidget(btn)
        self.spindle_buttons.append((50, btn))
        right_layout.addLayout(sovr_row1)

        sovr_row2 = QHBoxLayout()
        sovr_row2.setSpacing(6)
        for pct in [75, 100]:
            btn = QPushButton(f"{pct}%")
            btn.setObjectName("rapid-btn")
            btn.clicked.connect(lambda _, p=pct: self._set_override(p))
            sovr_row2.addWidget(btn)
            self.spindle_buttons.append((pct, btn))
        right_layout.addLayout(sovr_row2)

        sovr_row3 = QHBoxLayout()
        sovr_row3.setSpacing(6)
        for pct in [150, 200]:
            btn = QPushButton(f"{pct}%")
            btn.setObjectName("rapid-btn")
            btn.clicked.connect(lambda _, p=pct: self._set_override(p))
            sovr_row3.addWidget(btn)
            self.spindle_buttons.append((pct, btn))
        right_layout.addLayout(sovr_row3)

        # Fine adjust: -10  -1  +1  +10
        fine_row = QHBoxLayout()
        fine_row.setSpacing(6)
        for text, delta in [("-10", -10), ("-1", -1), ("+1", 1), ("+10", 10)]:
            btn = QPushButton(text)
            btn.setObjectName("ovr-btn")
            btn.clicked.connect(lambda _, d=delta: self._adjust_override(d))
            fine_row.addWidget(btn)
        right_layout.addLayout(fine_row)

        # -- Separator --
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.HLine)
        sep3.setStyleSheet(f"color: {COPPER_DIM};")
        right_layout.addSpacing(6)
        right_layout.addWidget(sep3)
        right_layout.addSpacing(4)

        # -- Rapid Override (G0) --
        rapid_title = QLabel("G0 RAPID")
        rapid_title.setObjectName("title")
        rapid_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(rapid_title)

        self.rapid_value_label = QLabel("100%")
        self.rapid_value_label.setObjectName("override-label")
        self.rapid_value_label.setAlignment(Qt.AlignCenter)
        self.rapid_value_label.setStyleSheet(f"color: {COPPER_LIGHT}; font-size: 28px; font-weight: bold;")
        right_layout.addWidget(self.rapid_value_label)

        # 5 buttons in 3 rows: [5%] / [25%  50%] / [75%  100%]
        self.rapid_buttons = []

        rapid_row1 = QHBoxLayout()
        rapid_row1.setSpacing(6)
        btn = QPushButton("5%")
        btn.setObjectName("rapid-btn")
        btn.clicked.connect(lambda _, p=5: self._set_rapid(p))
        rapid_row1.addWidget(btn)
        self.rapid_buttons.append((5, btn))
        right_layout.addLayout(rapid_row1)

        rapid_row2 = QHBoxLayout()
        rapid_row2.setSpacing(6)
        for pct in [25, 50]:
            btn = QPushButton(f"{pct}%")
            btn.setObjectName("rapid-btn")
            btn.clicked.connect(lambda _, p=pct: self._set_rapid(p))
            rapid_row2.addWidget(btn)
            self.rapid_buttons.append((pct, btn))
        right_layout.addLayout(rapid_row2)

        rapid_row3 = QHBoxLayout()
        rapid_row3.setSpacing(6)
        for pct in [75, 100]:
            btn = QPushButton(f"{pct}%")
            btn.setObjectName("rapid-btn")
            btn.clicked.connect(lambda _, p=pct: self._set_rapid(p))
            rapid_row3.addWidget(btn)
            self.rapid_buttons.append((pct, btn))
        right_layout.addLayout(rapid_row3)

        # Botoes de navegacao (GCODE + MDI)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        btn_gcode = QPushButton("GCODE")
        btn_gcode.setObjectName("page-btn")
        btn_gcode.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        nav_row.addWidget(btn_gcode)
        btn_mdi = QPushButton("MDI")
        btn_mdi.setObjectName("page-btn")
        btn_mdi.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        nav_row.addWidget(btn_mdi)
        right_layout.addStretch()
        right_layout.addLayout(nav_row)
        main.addWidget(right_frame, 4)

    # ── GCODE Page (dedicated viewer) ────────────────────────────────

    def _build_gcode_page(self, page):
        outer = QVBoxLayout(page)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        title = QLabel("GCODE")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        outer.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(6)

        self.gcode_label = QTextEdit()
        self.gcode_label.setReadOnly(True)
        self.gcode_label.setStyleSheet(
            f"color: #cccc00; font-size: 20px; font-weight: bold; "
            f"font-family: Monospace; background-color: {BG_DARK}; "
            f"padding: 8px; border: 2px solid #555555; border-radius: 4px;"
        )
        body.addWidget(self.gcode_label, 1)

        self._scroll_syncing = False
        self.gcode_scroll = QSlider(Qt.Vertical)
        self.gcode_scroll.setObjectName("gcode-scroll")
        self.gcode_scroll.setFixedWidth(70)
        self.gcode_scroll.setInvertedAppearance(True)
        bar = self.gcode_label.verticalScrollBar()
        bar.rangeChanged.connect(
            lambda mn, mx: self.gcode_scroll.setRange(mn, mx))
        bar.valueChanged.connect(self._gcode_bar_to_slider)
        self.gcode_scroll.valueChanged.connect(self._gcode_slider_to_bar)
        body.addWidget(self.gcode_scroll)

        outer.addLayout(body, 1)

        nav = QHBoxLayout()
        nav.setSpacing(6)
        btn_dro = QPushButton("DRO")
        btn_dro.setObjectName("page-btn")
        btn_dro.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        nav.addWidget(btn_dro)
        btn_mdi = QPushButton("MDI")
        btn_mdi.setObjectName("page-btn")
        btn_mdi.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        nav.addWidget(btn_mdi)
        outer.addLayout(nav)

    # ── MDI Page (ProbeBasic style) ─────────────────────────────────

    def _build_mdi_page(self, page):
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(3)

        # Body: history (left) + keyboard (right)
        body = QHBoxLayout()
        body.setSpacing(4)

        # === LEFT: History + action buttons ===
        left = QVBoxLayout()
        left.setSpacing(4)

        self.mdi_history_list = QListWidget()
        self.mdi_history_list.setObjectName("mdi-history")
        self.mdi_history_list.itemDoubleClicked.connect(self._mdi_history_recall)
        left.addWidget(self.mdi_history_list, 1)

        body.addLayout(left, 5)

        # === RIGHT: Keyboard grid 4 cols (T M S G F X Z + numerico) ===
        kbd = QGridLayout()
        kbd.setHorizontalSpacing(3)
        kbd.setVerticalSpacing(0)

        keys = [
            (0, 0, "T", "L"), (0, 1, "M", "L"), (0, 2, "S", "L"), (0, 3, "G", "L"),
            (1, 0, "F", "L"), (1, 1, "X", "L"), (1, 2, "Z", "L"), (1, 3, "-", "M"),
            (2, 0, "7", "N"), (2, 1, "8", "N"), (2, 2, "9", "N"),
            (3, 0, "4", "N"), (3, 1, "5", "N"), (3, 2, "6", "N"),
            (4, 0, "1", "N"), (4, 1, "2", "N"), (4, 2, "3", "N"),
            (5, 0, "0", "N"), (5, 1, ".", "N"),
        ]

        for row, col, text, ktype in keys:
            btn = QPushButton(text)
            style = {"L": "kbd-letter", "N": "kbd-number", "M": "kbd-minus"}[ktype]
            btn.setObjectName(style)
            btn.clicked.connect(lambda _, ch=text: self._mdi_key(ch))
            kbd.addWidget(btn, row, col)

        # Col 3 laterais: ⌫ / ◄ / ►
        btn_bksp = QPushButton("\u232B")
        btn_bksp.setObjectName("kbd-dark")
        btn_bksp.clicked.connect(self._mdi_backspace)
        kbd.addWidget(btn_bksp, 2, 3)

        btn_left = QPushButton("\u25C4")
        btn_left.setObjectName("kbd-dark")
        btn_left.clicked.connect(self._mdi_cursor_left)
        kbd.addWidget(btn_left, 3, 3)

        btn_right = QPushButton("\u25BA")
        btn_right.setObjectName("kbd-dark")
        btn_right.clicked.connect(self._mdi_cursor_right)
        kbd.addWidget(btn_right, 4, 3)

        # SPACE e ENTER na mesma linha
        btn_space = QPushButton("SPACE")
        btn_space.setObjectName("kbd-dark")
        btn_space.clicked.connect(lambda: self._mdi_key(" "))
        kbd.addWidget(btn_space, 5, 2)

        btn_enter = QPushButton("ENTER")
        btn_enter.setObjectName("kbd-dark")
        btn_enter.clicked.connect(self._mdi_submit)
        kbd.addWidget(btn_enter, 5, 3)

        body.addLayout(kbd, 5)
        outer.addLayout(body, 1)

        # === BOTTOM BAR: MDI entry + DRO/MDI buttons ===
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        self.mdi_entry = QLineEdit()
        self.mdi_entry.setObjectName("mdi-entry")
        self.mdi_entry.setPlaceholderText("MDI")
        self.mdi_entry.setFixedHeight(68)
        self.mdi_entry.returnPressed.connect(self._mdi_submit)
        bottom.addWidget(self.mdi_entry, 1)

        btn_dro = QPushButton("DRO")
        btn_dro.setObjectName("page-inactive")
        btn_dro.setFixedHeight(68)
        btn_dro.setFixedWidth(70)
        btn_dro.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        bottom.addWidget(btn_dro)

        btn_gcode_page = QPushButton("GCODE")
        btn_gcode_page.setObjectName("page-inactive")
        btn_gcode_page.setFixedHeight(68)
        btn_gcode_page.setFixedWidth(80)
        btn_gcode_page.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        bottom.addWidget(btn_gcode_page)

        btn_mdi_page = QPushButton("MDI")
        btn_mdi_page.setObjectName("page-active")
        btn_mdi_page.setFixedHeight(68)
        btn_mdi_page.setFixedWidth(70)
        bottom.addWidget(btn_mdi_page)

        outer.addLayout(bottom)

    # ── MDI Logic ────────────────────────────────────────────────────

    def _mdi_key(self, char):
        self.mdi_entry.insert(char)
        self.mdi_entry.setFocus()

    def _mdi_backspace(self):
        self.mdi_entry.backspace()
        self.mdi_entry.setFocus()

    def _mdi_cursor_left(self):
        pos = self.mdi_entry.cursorPosition()
        self.mdi_entry.setCursorPosition(max(0, pos - 1))
        self.mdi_entry.setFocus()

    def _mdi_cursor_right(self):
        pos = self.mdi_entry.cursorPosition()
        self.mdi_entry.setCursorPosition(pos + 1)
        self.mdi_entry.setFocus()

    def _mdi_submit(self):
        cmd_text = self.mdi_entry.text().strip().upper()
        if not cmd_text:
            return
        self.mdi_history.append(cmd_text)
        self.mdi_history_list.addItem(cmd_text)
        self.mdi_history_list.scrollToBottom()
        self.mdi_entry.clear()
        self._mdi_send(cmd_text)

    def _mdi_send(self, cmd_text):
        if not self.cmd or not self.stat:
            return
        try:
            self.stat.poll()
            if self.stat.task_mode != linuxcnc.MODE_MDI:
                self.cmd.mode(linuxcnc.MODE_MDI)
                self.cmd.wait_complete(1)
            self.cmd.mdi(cmd_text)
        except Exception:
            pass

    def _mdi_history_recall(self, item):
        self.mdi_entry.setText(item.text())
        self.mdi_entry.setFocus()

    def _mdi_rerun_selected(self):
        item = self.mdi_history_list.currentItem()
        if item:
            self._mdi_send(item.text())

    def _mdi_run_from(self):
        row = self.mdi_history_list.currentRow()
        if row < 0:
            return
        for i in range(row, self.mdi_history_list.count()):
            item = self.mdi_history_list.item(i)
            if item:
                self._mdi_send(item.text())

    def _mdi_del_selected(self):
        row = self.mdi_history_list.currentRow()
        if row >= 0:
            self.mdi_history_list.takeItem(row)
            if row < len(self.mdi_history):
                self.mdi_history.pop(row)

    def _mdi_clear_history(self):
        self.mdi_history.clear()
        self.mdi_history_list.clear()

    def _mdi_history_up(self):
        row = self.mdi_history_list.currentRow()
        if row > 0:
            self.mdi_history_list.setCurrentRow(row - 1)

    def _mdi_history_down(self):
        row = self.mdi_history_list.currentRow()
        if row < self.mdi_history_list.count() - 1:
            self.mdi_history_list.setCurrentRow(row + 1)

    # ── Spindle/Rapid Override ───────────────────────────────────────

    def _adjust_override(self, delta):
        if self.stat:
            try:
                current = int(self.stat.spindle[0]['override'] * 100)
                self._set_override(max(10, min(200, current + delta)))
            except Exception:
                pass

    def _set_override(self, percent):
        self.ovr_value.setText(f"{percent}%")
        if self.cmd:
            try:
                self.cmd.spindleoverride(percent / 100.0, 0)
            except Exception:
                pass

    def _update_spindle_buttons(self, current_pct):
        for pct, btn in self.spindle_buttons:
            if abs(pct - current_pct) < 2:
                btn.setObjectName("rapid-btn-active")
            else:
                btn.setObjectName("rapid-btn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _set_rapid(self, percent):
        self.rapid_value_label.setText(f"{percent}%")
        if self.cmd:
            try:
                self.cmd.rapidrate(percent / 100.0)
            except Exception:
                pass

    def _update_rapid_buttons(self, current_pct):
        for pct, btn in self.rapid_buttons:
            if abs(pct - current_pct) < 2:
                btn.setObjectName("rapid-btn-active")
            else:
                btn.setObjectName("rapid-btn")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _linuxcnc_ready(self):
        """Verifica se milltask E probe_basic estao rodando via /proc."""
        found_milltask = False
        found_display = False
        try:
            for pid in os.listdir('/proc'):
                if not pid.isdigit():
                    continue
                try:
                    with open(f'/proc/{pid}/comm', 'r') as f:
                        comm = f.read().strip()
                    if comm == 'milltask':
                        found_milltask = True
                    if not found_display:
                        with open(f'/proc/{pid}/cmdline', 'rb') as f:
                            cmdline = f.read().decode('utf-8', errors='ignore')
                        if 'probe_basic_lathe' in cmdline:
                            found_display = True
                except (IOError, OSError):
                    continue
                if found_milltask and found_display:
                    return True
            return False
        except Exception:
            return False

    def _try_reconnect(self):
        """Tenta criar conexao com LinuxCNC. So conecta se tudo estiver pronto."""
        if not self._linuxcnc_ready():
            return
        if not _import_linuxcnc():
            return
        try:
            self.stat = linuxcnc.stat()
            self.stat.poll()
            self.cmd = linuxcnc.command()
            # Reset state ao conectar
            self.cycle_start_time = None
            self.cycle_elapsed = 0
            self._prev_interp_state = None
            self._gcode_file = ""
            self._gcode_lines = []
            self._gcode_rendered_file = ""
            self._gcode_last_line = -1
        except Exception:
            self.stat = None
            self.cmd = None

    def _update(self):
        if self.stat is None:
            # Sem conexao - tenta reconectar a cada 2s (20 ciclos de 100ms)
            self._reconnect_counter += 1
            if self._reconnect_counter >= 20:
                self._reconnect_counter = 0
                self._try_reconnect()
            return

        # Verifica se LinuxCNC ainda esta rodando a cada 2s
        self._reconnect_counter += 1
        if self._reconnect_counter >= 20:
            self._reconnect_counter = 0
            if not self._linuxcnc_ready():
                self.stat = None
                self.cmd = None
                self._reset_display()
                return

        try:
            self.stat.poll()

            # DRO - work coordinates = actual - g5x - g92 - tool
            x = self.stat.actual_position[0]
            z = self.stat.actual_position[2]
            g5x = self.stat.g5x_offset
            g92 = self.stat.g92_offset
            tool = self.stat.tool_offset
            x -= g5x[0] + g92[0] + tool[0]
            z -= g5x[2] + g92[2] + tool[2]
            # Lathe: X in diameter (x2) to match ProbeBasic
            x *= 2
            self.x_value.setText(f"{x:+09.3f}")
            self.z_value.setText(f"{z:+09.3f}")
            # Tool number
            tool_num = self.stat.tool_in_spindle
            self.tool_value.setText(f"T{tool_num}")
            # Feed rate (settings[1] = F value in mm/min)
            feed = self.stat.settings[1]
            self.feed_value.setText(f"{feed:.0f}")
            # Spindle override
            ovr = int(self.stat.spindle[0]['override'] * 100)
            self.ovr_value.setText(f"{ovr}%")
            self._update_spindle_buttons(ovr)
            # Cycle time (interp_state: 1=reading, 2=paused, 3=waiting)
            interp = self.stat.interp_state
            if interp == linuxcnc.INTERP_READING and self._prev_interp_state != linuxcnc.INTERP_READING:
                if self.cycle_start_time is None:
                    self.cycle_start_time = time.time()
                    self.cycle_elapsed = 0
            elif interp == linuxcnc.INTERP_IDLE and self._prev_interp_state != linuxcnc.INTERP_IDLE:
                if self.cycle_start_time is not None:
                    self.cycle_elapsed = time.time() - self.cycle_start_time
                    self.cycle_start_time = None
            self._prev_interp_state = interp

            if self.cycle_start_time is not None:
                elapsed = time.time() - self.cycle_start_time
            else:
                elapsed = self.cycle_elapsed
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            self.cycle_value.setText(f"{mins:02d}:{secs:02d}")

            # G-code viewer
            gcode_file = self.stat.file
            if gcode_file and gcode_file != self._gcode_file:
                try:
                    with open(gcode_file, 'r') as f:
                        self._gcode_lines = f.readlines()
                    self._gcode_file = gcode_file
                except Exception:
                    self._gcode_lines = []
            if gcode_file and self._gcode_lines:
                line = self.stat.motion_line if interp != linuxcnc.INTERP_IDLE else 0
                if gcode_file != self._gcode_rendered_file:
                    display = []
                    for i, raw in enumerate(self._gcode_lines):
                        num = i + 1
                        txt = raw.rstrip()
                        display.append(f'{num:4d}  {txt}')
                    self.gcode_label.setHtml('<pre>' + '\n'.join(display) + '</pre>')
                    self._gcode_rendered_file = gcode_file
                    self._gcode_last_line = -1
                if line != self._gcode_last_line:
                    self._highlight_gcode_line(line)
                    self._gcode_last_line = line
            else:
                if self._gcode_rendered_file:
                    self.gcode_label.setHtml("")
                    self._gcode_rendered_file = ""
                    self._gcode_last_line = -1

            # Rapid override
            rapid_pct = int(self.stat.rapidrate * 100)
            self.rapid_value_label.setText(f"{rapid_pct}%")
            self._update_rapid_buttons(rapid_pct)

            # Sliders de override (read-only por enquanto)
            feed_pct = int(self.stat.feedrate * 100)
            self._sync_slider("feed", feed_pct)
            self._sync_slider("rpm", ovr)
            self._sync_slider("rapid", rapid_pct)
            self._sync_slider("mvel", 100)

        except Exception:
            # Conexao perdida
            self.stat = None
            self.cmd = None
            self._reconnect_counter = 0
            self._reset_display()

    def _highlight_gcode_line(self, line):
        selections = []
        if line > 0:
            doc = self.gcode_label.document()
            block = doc.findBlockByLineNumber(line - 1)
            if block.isValid():
                cursor = QTextCursor(block)
                cursor.select(QTextCursor.LineUnderCursor)
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                fmt = QTextCharFormat()
                fmt.setBackground(QColor(COPPER))
                fmt.setForeground(QColor("black"))
                sel.format = fmt
                selections.append(sel)
        self.gcode_label.setExtraSelections(selections)

    def _gcode_bar_to_slider(self, value):
        if self._scroll_syncing:
            return
        self._scroll_syncing = True
        self.gcode_scroll.setValue(value)
        self._scroll_syncing = False

    def _gcode_slider_to_bar(self, value):
        if self._scroll_syncing:
            return
        self._scroll_syncing = True
        self.gcode_label.verticalScrollBar().setValue(value)
        self._scroll_syncing = False

    def _sync_slider(self, key, value):
        if key in self.override_sliders:
            slider, lbl = self.override_sliders[key]
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            lbl.setText(f"{value}%")

    def _reset_display(self):
        self.x_value.setText("+000.000")
        self.z_value.setText("+000.000")
        self.tool_value.setText("T0")
        self.feed_value.setText("0")
        self.cycle_value.setText("00:00")
        self.ovr_value.setText("--")
        self.rapid_value_label.setText("--")
        self.gcode_label.setText("")
        self.cycle_start_time = None
        self.cycle_elapsed = 0
        self._prev_interp_state = None
        self._gcode_file = ""
        self._gcode_lines = []


def main():
    app = QApplication(sys.argv)
    app.setOverrideCursor(Qt.BlankCursor)  # Hide mouse cursor (touch only)
    panel = SecondaryPanel()
    # Fullscreen apenas no display virtual (Xvfb :1 = 800x480)
    # No display principal (:0), mostra janela 800x480 sem decoracao
    screen = app.primaryScreen().size()
    if screen.width() == 800 and screen.height() == 480:
        panel.showFullScreen()
    else:
        panel.setWindowFlags(panel.windowFlags() | Qt.FramelessWindowHint)
        panel.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
