"""WearOffsetTable - work coordinate offsets with Fanuc-style geom/wear split.

Adds two virtual columns ('XW', 'ZW') alongside X/Z. The offset values sent
to LinuxCNC via G10 L2 keep storing the TOTAL (geom + wear), so the machine
behaves exactly as before; the wear sidecar 'offset_wear.json' (in CONFIG_DIR)
stores only the wear portion. The X / Z columns shown in the UI are computed
as total - wear (= geometry).

The wear is keyed by the row label (G54, G55, ..., G59.3).
"""

import json
import os

from qtpy.QtCore import Qt, Slot, QLocale, QSortFilterProxyModel
from qtpy.QtGui import QBrush, QColor
from qtpy.QtWidgets import QTableView, QDoubleSpinBox, QHeaderView

from qtpyvcp.utilities.logger import getLogger
from qtpyvcp.actions.machine_actions import issue_mdi
from qtpyvcp.widgets.input_widgets.offset_table import (
    OffsetTable, OffsetModel, ItemDelegate,
)

LOG = getLogger(__name__)

WEAR_FILE_NAME = 'offset_wear.json'
EXTRA_LABELS = {'XW': 'X Offset', 'ZW': 'Z Offset'}
WEAR_COLOR = QColor('#FFD000')  # amarelo


def _wear_file_path():
    base = os.environ.get('CONFIG_DIR') or '.'
    return os.path.join(base, WEAR_FILE_NAME)


class WearOffsetModel(OffsetModel):

    def __init__(self, parent=None):
        super().__init__(parent)

        # Plugin columns (e.g. ['X','Z']) — these address self._offset_table.
        # Keep a snapshot before we extend self._columns with XW/ZW.
        self._plugin_columns = list(self._columns)

        # Build UI columns: insert XW and ZW right after the last X/Z column.
        cols = list(self._columns)
        last_xz = -1
        for i, c in enumerate(cols):
            if c in ('X', 'Z'):
                last_xz = i
        new_cols = []
        for i, c in enumerate(cols):
            new_cols.append(c)
            if i == last_xz:
                new_cols.append('XW')
                new_cols.append('ZW')
        self._columns = new_cols
        self.setColumnCount(len(self._columns))

        self._wear = self._load_wear()

    def _load_wear(self):
        path = _wear_file_path()
        if not os.path.exists(path):
            return {}
        try:
            with open(path, 'r') as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as e:
            LOG.warning("Could not read wear file %s: %s", path, e)
            return {}
        out = {}
        for k, v in raw.items():
            try:
                out[str(k)] = {'x': float(v.get('x', 0.0)),
                               'z': float(v.get('z', 0.0))}
            except (TypeError, AttributeError, ValueError):
                continue
        return out

    def _save_wear(self):
        path = _wear_file_path()
        clean = {k: {'x': v['x'], 'z': v['z']}
                 for k, v in self._wear.items()
                 if abs(v.get('x', 0.0)) > 1e-9 or abs(v.get('z', 0.0)) > 1e-9}
        try:
            with open(path, 'w') as fh:
                json.dump(clean, fh, indent=2, sort_keys=True)
        except OSError as e:
            LOG.error("Could not write wear file %s: %s", path, e)

    def _row_label(self, row):
        try:
            return str(self._row_labels[row])
        except IndexError:
            return None

    def _wear_value(self, row_label, axis):
        return self._wear.get(row_label, {}).get(axis, 0.0)

    def _set_wear_value(self, row_label, axis, value):
        if row_label not in self._wear:
            self._wear[row_label] = {'x': 0.0, 'z': 0.0}
        self._wear[row_label][axis] = float(value)

    def _plugin_col_for(self, key):
        # key is 'X' or 'Z' — return its index in self._offset_table.
        try:
            return self._plugin_columns.index(key)
        except ValueError:
            return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            key = self._columns[section]
            return EXTRA_LABELS.get(key, key)
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.EditRole):
            key = self._columns[index.column()]
            row = index.row()
            label = self._row_label(row)
            if label is None:
                return None
            if key == 'XW':
                return self._wear_value(label, 'x')
            if key == 'ZW':
                return self._wear_value(label, 'z')
            if key == 'X':
                col = self._plugin_col_for('X')
                if col is None:
                    return None
                return self._offset_table[row][col] - self._wear_value(label, 'x')
            if key == 'Z':
                col = self._plugin_col_for('Z')
                if col is None:
                    return None
                return self._offset_table[row][col] - self._wear_value(label, 'z')
            # Any other column passes through to the plugin table.
            col = self._plugin_col_for(key)
            if col is None:
                return None
            return self._offset_table[row][col]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignVCenter | Qt.AlignRight
        if role == Qt.TextColorRole:
            if self._columns[index.column()] in ('XW', 'ZW'):
                return QBrush(WEAR_COLOR)
            offset = index.row() + 1
            if self.ot.current_index == offset:
                return QBrush(self.current_row_color)
            return None
        if role == Qt.BackgroundRole and self.current_row_bg is not None:
            offset = index.row() + 1
            if self.ot.current_index == offset:
                return QBrush(self.current_row_bg)
            return None
        return None

    def setData(self, index, value, role):
        key = self._columns[index.column()]
        row = index.row()
        label = self._row_label(row)
        if label is None:
            return False

        try:
            value = float(value)
        except (TypeError, ValueError):
            return False

        if key in ('XW', 'ZW'):
            axis = 'x' if key == 'XW' else 'z'
            tbl_key = 'X' if axis == 'x' else 'Z'
            col = self._plugin_col_for(tbl_key)
            if col is None:
                return False
            old_wear = self._wear_value(label, axis)
            new_wear = value
            self._set_wear_value(label, axis, new_wear)
            # Keep geom constant: total += (new_wear - old_wear)
            self._offset_table[row][col] = (
                self._offset_table[row][col] - old_wear + new_wear
            )
            self.dataChanged.emit(index, index)
            geom_idx = self.index(row, self._columns.index(tbl_key))
            self.dataChanged.emit(geom_idx, geom_idx)
            return True

        if key in ('X', 'Z'):
            axis = 'x' if key == 'X' else 'z'
            col = self._plugin_col_for(key)
            if col is None:
                return False
            new_geom = value
            self._offset_table[row][col] = new_geom + self._wear_value(label, axis)
            self.dataChanged.emit(index, index)
            return True

        col = self._plugin_col_for(key)
        if col is None:
            return False
        self._offset_table[row][col] = value
        self.dataChanged.emit(index, index)
        return True

    def clearRow(self, row):
        label = self._row_label(row)
        if label and label in self._wear:
            del self._wear[label]
        for col in range(len(self._plugin_columns)):
            self._offset_table[row][col] = 0.0
        self.refreshModel()

    def clearRows(self):
        self._wear.clear()
        for row in range(len(self._rows)):
            for col in range(len(self._plugin_columns)):
                self._offset_table[row][col] = 0.0
        self.refreshModel()

    def saveOffsetTable(self):
        self._save_wear()
        # BUG FIX (X drift em G7): o plugin do qtpyvcp emite "G10 L2 P# X<v>"
        # sem forcar modo raio. Como a maquina roda sempre em G7 (diametro),
        # o interpretador le o X do G10 L2 como DIAMETRO e grava METADE no
        # parametro (que e raio) -> o X encolhe pela metade a cada SAVE.
        # (Z nao e eixo de diametro, por isso so o X driftava.)
        #
        # Solucao: espelhar o que o touch_off_x.ngc ja faz (linha 16) -> M70
        # salva os modos, G8 forca raio, grava os G10 L2, M72 restaura os modos.
        # Tudo numa unica transacao MDI (issue_mdi aceita comandos separados por
        # ';' e os executa em sequencia), entao nao ha race com o reload do
        # QFileSystemWatcher. Funciona identico em G7 e G8.
        cols = self._plugin_columns
        cmds = ["M70", "G8"]
        for index in range(len(self.ot.rows)):
            parts = ["G10 L2", "P{}".format(index + 1)]
            for char in cols:
                col = self.ot.columns.index(char)
                parts.append("{}{}".format(char, self._offset_table[index][col]))
            cmds.append(" ".join(parts))
        cmds.append("M72")
        # Mantem o plugin em sincronia com a tabela em memoria (ele faz isso no
        # seu proprio saveOffsetTable; aqui replicamos sem o G10 cru sem-guarda).
        self.ot.g5x_offset_table = self._offset_table
        issue_mdi(";".join(cmds))
        return True

    def clearWearForRow(self, row):
        label = self._row_label(row)
        if not label or label not in self._wear:
            return False
        old = self._wear.pop(label)
        for axis, tbl_key in (('x', 'X'), ('z', 'Z')):
            col = self._plugin_col_for(tbl_key)
            if col is not None:
                self._offset_table[row][col] -= old.get(axis, 0.0)
        self.beginResetModel()
        self.endResetModel()
        return True


class WearOffsetDelegate(ItemDelegate):

    _C_LOCALE = QLocale(QLocale.C)

    def createEditor(self, parent, option, index):
        col = self._columns[index.column()]
        if col in ('XW', 'ZW'):
            editor = QDoubleSpinBox(parent)
            editor.setFrame(False)
            editor.setAlignment(Qt.AlignCenter)
            editor.setDecimals(4)
            editor.setProperty('stepType', 1)
            editor.setRange(-100, 100)
            editor.setLocale(self._C_LOCALE)
            return editor
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QDoubleSpinBox):
            editor.setLocale(self._C_LOCALE)
        return editor


class WearOffsetTable(OffsetTable):

    def __init__(self, parent=None):
        # Bypass OffsetTable.__init__ so we can install our model/delegate;
        # replicate its QTableView-level setup.
        QTableView.__init__(self, parent)

        self.setEnabled(False)

        self.offset_model = WearOffsetModel(self)

        self._columns = self.offset_model._columns
        self._confirm_actions = False
        self._current_row_color = QColor('sage')
        self._current_row_bg = None

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setSourceModel(self.offset_model)

        self.item_delegate = WearOffsetDelegate(columns=self._columns)
        self.setItemDelegate(self.item_delegate)

        self.setModel(self.proxy_model)

        self.setSortingEnabled(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        from qtpyvcp.plugins import getPlugin
        STATUS = getPlugin('status')
        STATUS.all_axes_homed.notify(self.handle_home_signal)

    @Slot()
    def clearWear(self):
        row = self.selectedRow()
        if row < 0:
            return
        self.offset_model.clearWearForRow(row)
