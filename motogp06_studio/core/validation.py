"""Validasi string, angka, dan batas record."""
from __future__ import annotations

def encode_fixed_string(text: str, max_bytes: int, encoding="ascii", pad=b"\x00") -> bytes:
    """Encode ke field panjang tetap. Menolak teks terlalu panjang (tidak memotong diam-diam)."""
    raw = text.encode(encoding)
    if len(raw) > max_bytes:
        raise ValueError(f"String {len(raw)} byte melebihi batas field {max_bytes} byte")
    return raw + pad * (max_bytes - len(raw))

def decode_fixed_string(raw: bytes, encoding="ascii") -> str:
    return raw.split(b"\x00", 1)[0].decode(encoding, errors="replace")

def check_int_range(value: int, size: int, signed=False):
    lo, hi = (-(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1) if signed else (0, (1 << 8 * size) - 1)
    if not lo <= value <= hi:
        raise ValueError(f"Nilai {value} di luar rentang [{lo}, {hi}]")

def check_record_bounds(file_size, base, stride, count):
    if min(base, stride, count) < 0 or stride == 0:
        raise ValueError("base/stride/count tidak valid")
    end = base + stride * count
    if end > file_size:
        raise ValueError(f"Tabel melewati akhir file (akhir 0x{end:X} > 0x{file_size:X})")
