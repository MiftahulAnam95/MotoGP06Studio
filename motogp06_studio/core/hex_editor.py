"""Dokumen biner dengan edit panjang-tetap, undo/redo, change log, area terproteksi, dan pencarian."""
from __future__ import annotations
import struct, time
from dataclasses import dataclass

@dataclass
class Change:
    offset: int
    old: bytes
    new: bytes
    note: str = ""
    ts: float = 0.0

class HexDocument:
    def __init__(self, data: bytes):
        self.original = bytes(data)
        self.data = bytearray(data)
        self.log: list[Change] = []
        self._undo: list[Change] = []
        self._redo: list[Change] = []
        self.protected: list[tuple[int, int, str]] = []

    def __len__(self): return len(self.data)

    def protect(self, start, end, label=""):
        self.protected.append((start, end, label))

    def _check(self, offset, length):
        if offset < 0 or length < 0 or offset + length > len(self.data):
            raise ValueError(f"Di luar batas file: offset 0x{offset:X}, panjang {length}, ukuran {len(self.data)}")
        for s, e, lab in self.protected:
            if offset < e and offset + length > s:
                raise PermissionError(f"Area terproteksi '{lab}' (0x{s:X}-0x{e:X})")

    def write(self, offset: int, new: bytes, note: str = "") -> Change:
        """Timpa byte pada offset. Panjang file selalu tetap; tidak ada insert/delete."""
        new = bytes(new)
        self._check(offset, len(new))
        ch = Change(offset, bytes(self.data[offset:offset + len(new)]), new, note, time.time())
        self.data[offset:offset + len(new)] = new
        self.log.append(ch); self._undo.append(ch); self._redo.clear()
        return ch

    def undo(self):
        if not self._undo: return None
        ch = self._undo.pop()
        self.data[ch.offset:ch.offset + len(ch.old)] = ch.old
        self._redo.append(ch)
        self.log.append(Change(ch.offset, ch.new, ch.old, "UNDO", time.time()))
        return ch

    def redo(self):
        if not self._redo: return None
        ch = self._redo.pop()
        self.data[ch.offset:ch.offset + len(ch.new)] = ch.new
        self._undo.append(ch)
        self.log.append(Change(ch.offset, ch.old, ch.new, "REDO", time.time()))
        return ch

    @property
    def dirty(self): return bytes(self.data) != self.original

    def changed_ranges(self):
        out, start = [], None
        a, b = self.original, self.data
        for i in range(len(a)):
            if a[i] != b[i]:
                if start is None: start = i
            elif start is not None:
                out.append((start, i - start)); start = None
        if start is not None: out.append((start, len(a) - start))
        return out

    def dump_line(self, offset, width=16):
        chunk = self.data[offset:offset + width]
        hx = " ".join(f"{c:02X}" for c in chunk).ljust(width * 3 - 1)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        return f"{offset:08X}  {offset:>10d}  {hx}  |{asc}|"

    def find_bytes(self, pat: bytes, start=0, limit=1000):
        res, i = [], start
        while len(res) < limit and (i := self.data.find(pat, i)) != -1:
            res.append(i); i += 1
        return res

    def find_string(self, text: str, encoding="ascii", **kw):
        return self.find_bytes(text.encode(encoding), **kw)

    def find_int(self, value: int, size=4, endian="<", signed=False, **kw):
        fmt = endian + {1: "b", 2: "h", 4: "i", 8: "q"}[size]
        if not signed: fmt = fmt.upper()
        return self.find_bytes(struct.pack(fmt, value), **kw)

    def export(self) -> bytes:
        if len(self.data) != len(self.original):
            raise RuntimeError("Panjang file berubah (tidak diizinkan)")
        return bytes(self.data)
