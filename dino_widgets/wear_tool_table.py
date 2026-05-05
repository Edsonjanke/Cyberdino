"""WearToolTable - tool table widget with Fanuc-style geometry/wear split.

Adds two virtual columns ('XW', 'ZW') alongside X/Z. The tool.tbl on disk
keeps storing the TOTAL offset (so LinuxCNC sees geom+wear directly), while
the wear sidecar 'tool_wear.json' (in CONFIG_DIR) stores the wear part.
The X / Z columns shown in the UI are computed as total - wear (= geometry).
"""

import json
import os

from qtpy.QtCore import Qt, Slot, QLocale, QSortFilterProxyModel
from qtpy.QtGui import QBrush, QColor
from qtpy.QtWidgets import QTableView, QDoubleSpinBox

from qtpyvcp.utilities.logger import getLogger
from qtpyvcp.widgets.input_widgets.tool_table import (
    ToolTable, ToolModel, ItemDelegate,
)

LOG = getLogger(__name__)

WEAR_FILE_NAME = 'tool_wear.json'
EXTRA_LABELS = {'XW': 'X Desg', 'ZW': 'Z Desg'}
WEAR_COLOR = QColor('#FFD000')  # amarelo


def _wear_file_path(tt):
    base = os.environ.get('CONFIG_DIR') \
        or os.path.dirname(getattr(tt, 'tool_table_file', '') or '') \
        or '.'
    return os.path.join(base, WEAR_FILE_NAME)


class WearToolModel(ToolModel):

    def __init__(self, parent=None):
        super().__init__(parent)

        # Insert XW and ZW side-by-side, right after whichever of X/Z
        # appears later in the column list.
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
        self._column_labels = dict(self._column_labels)
        self._column_labels.update(EXTRA_LABELS)
        self.setColumnCount(len(self._columns))

        self._wear = self._load_wear()

    def _load_wear(self):
        path = _wear_file_path(self.tt)
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
                out[int(k)] = {'x': float(v.get('x', 0.0)),
                               'z': float(v.get('z', 0.0))}
            except (TypeError, ValueError):
                continue
        return out

    def _save_wear(self):
        path = _wear_file_path(self.tt)
        # Drop entries where both x and z are zero to keep the file clean
        clean = {str(k): {'x': v['x'], 'z': v['z']}
                 for k, v in self._wear.items()
                 if abs(v.get('x', 0.0)) > 1e-9 or abs(v.get('z', 0.0)) > 1e-9}
        try:
            with open(path, 'w') as fh:
                json.dump(clean, fh, indent=2, sort_keys=True)
        except OSError as e:
            LOG.error("Could not write wear file %s: %s", path, e)

    def _wear_value(self, tnum, axis):
        return self._wear.get(int(tnum), {}).get(axis, 0.0)

    def _set_wear_value(self, tnum, axis, value):
        tnum = int(tnum)
        if tnum not in self._wear:
            self._wear[tnum] = {'x': 0.0, 'z': 0.0}
        self._wear[tnum][axis] = float(value)

    def _row_to_tnum(self, row):
        try:
            return sorted(self._tool_table)[row + self.row_offset]
        except IndexError:
            return None

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.EditRole):
            key = self._columns[index.column()]
            if key in ('X', 'Z', 'XW', 'ZW'):
                tnum = self._row_to_tnum(index.row())
                if tnum is None:
                    return None
                if key == 'XW':
                    return self._wear_value(tnum, 'x')
                if key == 'ZW':
                    return self._wear_value(tnum, 'z')
                if key == 'X':
                    return self._tool_table[tnum]['X'] - self._wear_value(tnum, 'x')
                if key == 'Z':
                    return self._tool_table[tnum]['Z'] - self._wear_value(tnum, 'z')
        elif role == Qt.TextColorRole:
            if self._columns[index.column()] in ('XW', 'ZW'):
                return QBrush(WEAR_COLOR)
        return super().data(index, role)

    def setData(self, index, value, role):
        col = index.column()
        key = self._columns[col]
        tnum = self._row_to_tnum(index.row())
        if tnum is None:
            return False

        if key in ('XW', 'ZW'):
            axis = 'x' if key == 'XW' else 'z'
            tbl_key = 'X' if axis == 'x' else 'Z'
            old_wear = self._wear_value(tnum, axis)
            new_wear = float(value)
            self._set_wear_value(tnum, axis, new_wear)
            # Keep displayed geom constant: total += (new_wear - old_wear)
            self._tool_table[tnum][tbl_key] = \
                self._tool_table[tnum][tbl_key] - old_wear + new_wear
            self.dataChanged.emit(index, index)
            geom_idx = self.index(index.row(), self._columns.index(tbl_key))
            self.dataChanged.emit(geom_idx, geom_idx)
            return True

        if key in ('X', 'Z'):
            new_geom = float(value)
            axis = 'x' if key == 'X' else 'z'
            self._tool_table[tnum][key] = new_geom + self._wear_value(tnum, axis)
            self.dataChanged.emit(index, index)
            return True

        # All other columns: default behaviour
        self._tool_table[tnum][key] = value
        self.dataChanged.emit(index, index)
        return True

    def saveToolTable(self):
        # Persist wear sidecar; tool.tbl writing is handled by the plugin
        # which already holds the TOTAL (geom + wear) in self._tool_table.
        self._save_wear()
        return super().saveToolTable()

    def removeTool(self, row):
        tnum = self._row_to_tnum(row)
        result = super().removeTool(row)
        if tnum is not None and int(tnum) in self._wear:
            del self._wear[int(tnum)]
        return result

    def clearWearForTool(self, tnum):
        tnum = int(tnum)
        if tnum not in self._wear:
            return False
        old = self._wear.pop(tnum)
        if tnum in self._tool_table:
            self._tool_table[tnum]['X'] -= old.get('x', 0.0)
            self._tool_table[tnum]['Z'] -= old.get('z', 0.0)
        self.beginResetModel()
        self.endResetModel()
        return True


class WearItemDelegate(ItemDelegate):

    # Locale C: aceita "." como separador decimal (teclado virtual envia ".";
    # locale pt_BR padrao do sistema usa "," e o QDoubleSpinBox rejeita ".")
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


class WearToolTable(ToolTable):

    def __init__(self, parent=None):
        # Bypass ToolTable.__init__ so we can install our model/delegate;
        # replicate the QTableView-level setup it does.
        QTableView.__init__(self, parent)

        self.clicked.connect(self.onClick)

        self.tool_model = WearToolModel(self)

        self.item_delegate = WearItemDelegate(columns=self.tool_model._columns)
        self.setItemDelegate(self.item_delegate)

        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(0)
        self.proxy_model.setSourceModel(self.tool_model)
        self.setModel(self.proxy_model)

        self._columns = self.tool_model._columns
        self._confirm_actions = False
        self._current_tool_color = QColor('sage')
        self._current_tool_bg = None

        self.setSortingEnabled(True)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.SingleSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSortIndicator(0, Qt.AscendingOrder)

    @Slot()
    def clearWear(self):
        row = self.selectedRow()
        if row < 0:
            return
        try:
            tnum = self.tool_model.toolDataFromRow(row)['T']
        except (KeyError, IndexError):
            return
        self.tool_model.clearWearForTool(tnum)
