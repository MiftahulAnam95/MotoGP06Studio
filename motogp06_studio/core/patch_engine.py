"""Patch berbasis offset dengan pemeriksaan hash sumber, verifikasi byte lama, dan rollback."""
from __future__ import annotations
import hashlib, json, time
from dataclasses import dataclass, asdict

@dataclass
class PatchEntry:
    offset: int
    old: str   # hex
    new: str   # hex
    note: str = ""

class PatchError(Exception): pass

class Patch:
    def __init__(self, source_sha256: str, source_size: int, entries=None, meta=None):
        self.source_sha256, self.source_size = source_sha256, source_size
        self.entries: list[PatchEntry] = entries or []
        self.meta = meta or {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "tool": "MotoGP06 PSP Modding Studio"}

    @classmethod
    def from_diff(cls, original: bytes, modified: bytes, note=""):
        if len(original) != len(modified):
            raise PatchError("Panjang berbeda: patch offset-murni hanya untuk file berukuran sama.")
        p = cls(hashlib.sha256(original).hexdigest(), len(original))
        start = None
        for i in range(len(original) + 1):
            diff = i < len(original) and original[i] != modified[i]
            if diff and start is None: start = i
            elif not diff and start is not None:
                p.entries.append(PatchEntry(start, original[start:i].hex(), modified[start:i].hex(), note)); start = None
        return p

    @classmethod
    def from_document(cls, document, note=""):
        """Buat patch dari rentang yang sudah dilacak dokumen, tanpa memindai seluruh file."""
        original = document.original
        if len(original) != len(document.data):
            raise PatchError("Panjang berbeda: patch offset-murni hanya untuk file berukuran sama.")
        p = cls(hashlib.sha256(original).hexdigest(), len(original))
        for offset, length in document.changed_ranges():
            end = offset + length
            p.entries.append(PatchEntry(
                offset, original[offset:end].hex(), bytes(document.data[offset:end]).hex(), note))
        return p

    def check_target(self, data: bytes):
        if len(data) != self.source_size:
            raise PatchError(f"Ukuran target {len(data)} != ukuran sumber {self.source_size}")
        if hashlib.sha256(data).hexdigest() != self.source_sha256:
            raise PatchError("Hash target tidak cocok dengan file sumber patch. Patch ditolak.")

    def apply(self, data: bytes) -> bytes:
        self.check_target(data)
        out = bytearray(data)
        for e in self.entries:
            old, new = bytes.fromhex(e.old), bytes.fromhex(e.new)
            if out[e.offset:e.offset + len(old)] != old:
                raise PatchError(f"Byte lama di 0x{e.offset:X} tidak cocok")
            if len(old) != len(new): raise PatchError("Entri mengubah panjang data")
            out[e.offset:e.offset + len(new)] = new
        return bytes(out)

    def revert(self, patched: bytes) -> bytes:
        if len(patched) != self.source_size: raise PatchError("Ukuran tidak cocok untuk rollback")
        out = bytearray(patched)
        for e in reversed(self.entries):
            old, new = bytes.fromhex(e.old), bytes.fromhex(e.new)
            if out[e.offset:e.offset + len(new)] != new:
                raise PatchError(f"Rollback gagal: byte di 0x{e.offset:X} bukan hasil patch")
            out[e.offset:e.offset + len(old)] = old
        return bytes(out)

    def to_json(self) -> str:
        return json.dumps({"source_sha256": self.source_sha256, "source_size": self.source_size,
                           "meta": self.meta, "entries": [asdict(e) for e in self.entries]}, indent=2)

    @classmethod
    def from_json(cls, text: str):
        d = json.loads(text)
        return cls(d["source_sha256"], d["source_size"], [PatchEntry(**e) for e in d["entries"]], d.get("meta"))
