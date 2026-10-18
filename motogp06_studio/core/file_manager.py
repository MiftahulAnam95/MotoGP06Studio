"""Pembukaan file, metadata, hash, dan identifikasi format (kandidat, bukan kepastian)."""
from __future__ import annotations
import hashlib, os, zlib, logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

# (magic, offset, nama, catatan). Hanya signature publik yang dikenal.
SIGNATURES = [
    (b"7z\xbc\xaf\x27\x1c", 0, "7-Zip archive", "Arsip, bukan DAT game. Ekstrak dulu."),
    (b"PK\x03\x04", 0, "ZIP archive", "Arsip, bukan DAT game. Ekstrak dulu."),
    (b"\x1f\x8b", 0, "GZIP stream", "Data terkompresi gzip."),
    (b"CISO", 0, "PSP CSO (compressed ISO)", "Image UMD terkompresi."),
    (b"\x00PBP", 0, "PSP EBOOT.PBP", "Container PBP."),
    (b"~PSP", 0, "PSP encrypted module", "Modul terenkripsi."),
    (b"\x7fELF", 0, "ELF executable", "Executable."),
    (b"RIFF", 0, "RIFF container", "WAV/AVI/dll."),
    (b"\x89PNG\r\n\x1a\n", 0, "PNG image", ""),
    (b"CD001", 0x8001, "ISO9660 image", "Image disc."),
    (b"MIG.00.1PSP", 0, "PSP GIM texture", "Tekstur PSP."),
]

@dataclass
class Identification:
    name: str
    confidence: float  # 0..1
    note: str = ""
    verified: bool = False  # selalu False: signature != bukti struktur

@dataclass
class FileInfo:
    path: Path
    size: int
    sha256: str
    md5: str
    crc32: str
    identifications: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

def hash_file(path, chunk=1 << 20, progress=None):
    sha, md, crc, done = hashlib.sha256(), hashlib.md5(), 0, 0
    total = os.path.getsize(path) or 1
    with open(path, "rb") as f:
        while b := f.read(chunk):
            sha.update(b); md.update(b); crc = zlib.crc32(b, crc); done += len(b)
            if progress: progress(done * 100 // total)
    return sha.hexdigest(), md.hexdigest(), f"{crc & 0xFFFFFFFF:08X}"

def identify(head: bytes, size: int):
    out = []
    for magic, off, name, note in SIGNATURES:
        if head[off:off + len(magic)] == magic:
            out.append(Identification(name, 0.9, note))
    if not out:
        out.append(Identification("Format tidak dikenal (raw binary)", 0.0,
                   "Tidak ada signature cocok. Gunakan Binary Analyzer (mode eksploratori)."))
    return out

def open_file(path, progress=None) -> FileInfo:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"File tidak ditemukan: {p}")
    size = p.stat().st_size
    warnings = []
    if size == 0:
        warnings.append("File kosong (0 byte).")
    with open(p, "rb") as f:
        head = f.read(0x9000)
    ids = identify(head, size)
    if all(i.confidence == 0 for i in ids):
        warnings.append("Format belum dikenal: integritas tidak dapat dipastikan.")
    if p.suffix.lower() in (".7z", ".zip", ".gz"):
        warnings.append("Ini arsip, bukan MotoGP.DAT. Ekstrak lebih dulu.")
    sha, md, crc = hash_file(p, progress=progress)
    log.info("Dibuka %s (%d byte) sha256=%s", p, size, sha)
    return FileInfo(p, size, sha, md, crc, ids, warnings)
