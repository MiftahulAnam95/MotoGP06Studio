from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QColor, QFont

class HexModel(QAbstractTableModel):
    """Model lazy: hanya baris yang terlihat yang dibaca dari HexDocument."""
    W = 16
    def __init__(self, doc, on_error=None, on_change=None):
        super().__init__(); self.doc, self.on_error, self.on_change = doc, on_error, on_change
    def set_doc(self, doc):
        self.beginResetModel(); self.doc = doc; self.endResetModel()
    def refresh(self):
        self.beginResetModel(); self.endResetModel()
    def rowCount(self, p=QModelIndex()): return 0 if p.isValid() or not self.doc else (len(self.doc) + self.W - 1) // self.W
    def columnCount(self, p=QModelIndex()): return self.W + 1
    def headerData(self, s, o, role=Qt.DisplayRole):
        if role != Qt.DisplayRole: return None
        if o == Qt.Horizontal: return f"{s:02X}" if s < self.W else "ASCII"
        return f"{s * self.W:08X}"
    def data(self, idx, role=Qt.DisplayRole):
        if not self.doc: return None
        r, c = idx.row(), idx.column(); base = r * self.W
        if c == self.W:
            if role == Qt.DisplayRole:
                return "".join(chr(b) if 32 <= b < 127 else "." for b in self.doc.data[base:base + self.W])
            if role == Qt.FontRole: return QFont("Consolas", 10)
            return None
        o = base + c
        if o >= len(self.doc): return None
        if role == Qt.DisplayRole: return f"{self.doc.data[o]:02X}"
        if role == Qt.BackgroundRole and self.doc.data[o] != self.doc.original[o]: return QColor("#7a1f2b")
        if role == Qt.TextAlignmentRole: return Qt.AlignCenter
        if role == Qt.FontRole: return QFont("Consolas", 10)
        return None
    def flags(self, idx):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if idx.column() < self.W and idx.row() * self.W + idx.column() < len(self.doc): f |= Qt.ItemIsEditable
        return f
    def setData(self, idx, value, role=Qt.EditRole):
        try:
            v = int(str(value).strip(), 16)
            if not 0 <= v <= 255: raise ValueError("Nilai harus 00-FF")
            self.doc.write(idx.row() * self.W + idx.column(), bytes([v]), "edit hex manual")
        except Exception as e:
            if self.on_error: self.on_error(str(e))
            return False
        self.dataChanged.emit(idx, idx); self.dataChanged.emit(self.index(idx.row(), self.W), self.index(idx.row(), self.W))
        if self.on_change: self.on_change()
        return True
