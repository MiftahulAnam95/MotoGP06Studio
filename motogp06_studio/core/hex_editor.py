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
        # Satu transaksi dapat berisi banyak rentang terpisah (mis. semua
        # kemunculan satu nama). Undo/redo tetap membatalkan seluruh tindakan.
        self._undo: list[tuple[Change, ...]] = []
        self._redo: list[tuple[Change, ...]] = []
        self._touched: list[tuple[int, int]] = []
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
        return self.write_many([(offset, new, note)])[0]

    def write_many(self, writes) -> list[Change]:
        """Tulis beberapa rentang secara atomik sebagai satu langkah Undo.

        Semua batas, area terproteksi, dan tumpang-tindih divalidasi sebelum
        byte pertama diubah. Panjang file tidak pernah berubah.
        """
        prepared = [(int(offset), bytes(new), str(note)) for offset, new, note in writes]
        if not prepared:
            return []

        ranges = []
        for offset, new, _note in prepared:
            self._check(offset, len(new))
            if new:
                ranges.append((offset, offset + len(new)))
        ranges.sort()
        for previous, current in zip(ranges, ranges[1:]):
            if current[0] < previous[1]:
                raise ValueError(f"Rentang tulis bertumpang-tindih di 0x{current[0]:X}")

        now = time.time()
        changes = tuple(
            Change(offset, bytes(self.data[offset:offset + len(new)]), new, note, now)
            for offset, new, note in prepared
        )
        for ch in changes:
            self.data[ch.offset:ch.offset + len(ch.new)] = ch.new
            self.log.append(ch)
            if ch.new: self._touched.append((ch.offset, ch.offset + len(ch.new)))
        self._undo.append(changes)
        self._redo.clear()
        return list(changes)

    def undo(self):
        if not self._undo: return None
        changes = self._undo.pop()
        now = time.time()
        for ch in reversed(changes):
            self.data[ch.offset:ch.offset + len(ch.old)] = ch.old
            self.log.append(Change(ch.offset, ch.new, ch.old, "UNDO", now))
            if ch.old: self._touched.append((ch.offset, ch.offset + len(ch.old)))
        self._redo.append(changes)
        return changes[0] if len(changes) == 1 else changes

    def redo(self):
        if not self._redo: return None
        changes = self._redo.pop()
        now = time.time()
        for ch in changes:
            self.data[ch.offset:ch.offset + len(ch.new)] = ch.new
            self.log.append(Change(ch.offset, ch.old, ch.new, "REDO", now))
            if ch.new: self._touched.append((ch.offset, ch.offset + len(ch.new)))
        self._undo.append(changes)
        return changes[0] if len(changes) == 1 else changes

    @property
    def dirty(self): return self.data != self.original

    def changed_ranges(self):
        """Rentang byte berbeda dari sumber; pemindaian dibatasi ke area yang diedit."""
        if not self._touched:
            # Fallback untuk kode pemanggil lama yang mengubah `data` langsung.
            if self.data == self.original: return []
            ranges = [(0, len(self.data))]
        else:
            ranges = sorted(self._touched)

        merged = []
        for start, end in ranges:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))

        out = []
        for start, end in merged:
            run = None
            for offset in range(start, end):
                if self.original[offset] != self.data[offset]:
                    if run is None: run = offset
                elif run is not None:
                    out.append((run, offset - run)); run = None
            if run is not None: out.append((run, end - run))
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
