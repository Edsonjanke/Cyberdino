import os
import linuxcnc

from qtpy import uic
from qtpy.QtCore import Qt, QSettings
from qtpy.QtWidgets import QWidget, QPushButton, QSizePolicy

from qtpyvcp.plugins import getPlugin
from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

STATUS = getPlugin('status')
TOOL_TABLE = getPlugin('tooltable')

INI_FILE = linuxcnc.ini(os.getenv('INI_FILE_NAME'))

# Estilo dos DROs grandes: fonte parametrizada pelo modo (44pt junto da
# tabela; 64pt quando em tela cheia do painel).
_BIG_DRO_SS = """DROLabel {{
    border: 1px solid #3A3F43;
    border-radius: 6px;
    color: #00E676;
    background: #0D0F0E;
    padding-right: 10px;
    font: {size} "Bebas Kai";
}}

DROLabel[style="unhomed"] {{
    color: red;
}}

DROLabel[style="homing"] {{
    color: rgb(196, 160, 0);
}}"""

_CAPTION_SS = """QLabel {{
    font: {size} "Bebas Kai";
    color: white;
}}"""


class UserDRO(QWidget):
    """DRO custom XZ com dois modos alternaveis (botao AMPLIAR/TABELA):
       - TABELA: header + linhas X/Z detalhadas (WORK/MACHINE/DTG/REF).
       - AMPLIADO: so os DROs gigantes do zero-peca atual (le de longe).
       Modo persiste entre sessoes (QSettings DinoEvo/DroView)."""

    def __init__(self, parent=None):
        super(UserDRO, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        self._view_settings = QSettings("DinoEvo", "DroView")
        big = self._view_settings.value("big", False, type=bool)

        # Botao de alternancia no rodape (junto de ZERO ALL / HOMED).
        self._toggle_btn = QPushButton(self)
        self._toggle_btn.setMinimumHeight(40)
        self._toggle_btn.setMinimumWidth(110)
        self._toggle_btn.setFocusPolicy(Qt.NoFocus)
        try:
            self.horizontalLayout.addWidget(self._toggle_btn)
        except AttributeError:
            LOG.warning("dros_xz: layout do rodape nao encontrado p/ botao")
        self._toggle_btn.clicked.connect(self._toggle_view)

        # DROs grandes esticam verticalmente no modo ampliado.
        for lbl in (self.big_dro_x, self.big_dro_z):
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._apply_view(big)

    def _toggle_view(self):
        big = not self._view_settings.value("big", False, type=bool)
        self._view_settings.setValue("big", big)
        self._view_settings.sync()
        self._apply_view(big)

    def _apply_view(self, big):
        # TABELA: header (widget_87) + linha X (widget_88) + linha Z (widget_89)
        for w in (self.widget_87, self.widget_88, self.widget_89):
            w.setVisible(not big)
        self.widget_big_dro.setVisible(bool(big))
        size = '64pt' if big else '44pt'
        cap = '44pt' if big else '30pt'
        for lbl in (self.big_dro_x, self.big_dro_z):
            lbl.setStyleSheet(_BIG_DRO_SS.format(size=size))
        for lbl in (self.big_x_caption, self.big_z_caption):
            lbl.setStyleSheet(_CAPTION_SS.format(size=cap))
        self._toggle_btn.setText(u"TABELA" if big else u"AMPLIAR")
