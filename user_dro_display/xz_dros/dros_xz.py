import os
import linuxcnc

from qtpy import uic
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QWidget

from qtpyvcp.plugins import getPlugin
from qtpyvcp.utilities import logger

LOG = logger.getLogger(__name__)

STATUS = getPlugin('status')
TOOL_TABLE = getPlugin('tooltable')

INI_FILE = linuxcnc.ini(os.getenv('INI_FILE_NAME'))


class UserDRO(QWidget):
    def __init__(self, parent=None):
        super(UserDRO, self).__init__(parent)
        ui_file = os.path.splitext(os.path.basename(__file__))[0] + ".ui"
        uic.loadUi(os.path.join(os.path.dirname(__file__), ui_file), self)

        # Workaround: motion nao aplica G54 automaticamente do P5220
        # mesmo com G54 no STARTUP_CODE. Precisa de outro WCS primeiro.
        # Issue G55 -> G54 apos motion estar pronto.
        QTimer.singleShot(3000, self._init_wcs)

    def _init_wcs(self):
        try:
            c = linuxcnc.command()
            s = linuxcnc.stat()
            s.poll()
            if s.task_state != linuxcnc.STATE_ON:
                # Tenta de novo em 2s
                QTimer.singleShot(2000, self._init_wcs)
                return
            prev_mode = s.task_mode
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete(2)
            c.mdi("G55")
            c.wait_complete(2)
            c.mdi("G54")
            c.wait_complete(2)
            # Volta pro modo anterior
            if prev_mode != linuxcnc.MODE_MDI:
                c.mode(prev_mode)
                c.wait_complete(2)
            LOG.info("WCS inicializado em G54")
        except Exception as e:
            LOG.error("Erro inicializando G54: %s", e)
