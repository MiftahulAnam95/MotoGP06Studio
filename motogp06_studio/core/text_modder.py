"""Penggantian teks literal berukuran tetap pada file game.

Modul ini sengaja tidak mencoba menebak atau membongkar kompresi kustom MotoGP.DAT.
Ia hanya mengubah urutan byte teks yang ditemukan persis seperti yang diketik pengguna.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TextReplacement:
    """Satu aturan penggantian teks; semua kecocokan persis akan dipilih."""

    old: str
    new: str
    category: str = "Lainnya"
    encoding: str = "ascii"


@dataclass(frozen=True)
class ReplacementPreview:
    """Hasil pemeriksaan aturan sebelum byte diubah."""

    replacement: TextReplacement
    old_bytes: bytes
    new_bytes: bytes
    offsets: tuple[int, ...]


@dataclass(frozen=True)
class StringCandidate:
    """Potongan ASCII tercetak yang ditemukan oleh pemindai heuristik."""

    offset: int
    text: str


_ASCII_RUN = re.compile(rb"[\x20-\x7E]{3,}")


def _encode_name(text: str, encoding: str, role: str) -> bytes:
    if not isinstance(text, str) or not text:
        raise ValueError(f"{role} tidak boleh kosong.")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in text):
        raise ValueError(f"{role} tidak boleh berisi karakter kontrol/baris baru.")
    try:
        raw = text.encode(encoding, errors="strict")
    except (LookupError, UnicodeEncodeError) as exc:
        raise ValueError(f"{role} tidak cocok dengan encoding {encoding}: {exc}") from exc
    if not raw:
        raise ValueError(f"{role} tidak boleh kosong.")
    return raw


def find_byte_occurrences(data: bytes | bytearray, needle: bytes) -> tuple[int, ...]:
    """Temukan semua offset persis, termasuk kecocokan yang saling tumpang tindih."""
    if not needle:
        raise ValueError("Teks pencarian tidak boleh kosong.")
    offsets: list[int] = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return tuple(offsets)
        offsets.append(offset)
        start = offset + 1


def find_text_occurrences(
    data: bytes | bytearray,
    text: str,
    encoding: str = "ascii",
) -> tuple[int, ...]:
    """Cari teks dengan encoding eksplisit dan hasil berupa offset byte."""
    needle = _encode_name(text, encoding, "Teks pencarian")
    return find_byte_occurrences(data, needle)


def preview_replacements(
    data: bytes | bytearray,
    replacements: Iterable[TextReplacement],
) -> list[ReplacementPreview]:
    """Validasi semua aturan dan hitung lokasi sebelum perubahan dilakukan.

    Nama baru wajib memiliki panjang byte yang sama. Aturan yang duplikat atau
    mengenai rentang byte yang bertumpang-tindih ditolak agar hasilnya tidak
    bergantung pada urutan penerapan.
    """
    rules = list(replacements)
    if not rules:
        raise ValueError("Tambahkan setidaknya satu perubahan nama.")

    previews: list[ReplacementPreview] = []
    seen: set[bytes] = set()
    occupied: list[tuple[int, int, str]] = []

    for rule in rules:
        old = _encode_name(rule.old, rule.encoding, "Nama lama")
        new = _encode_name(rule.new, rule.encoding, "Nama baru")
        if len(old) != len(new):
            raise ValueError(
                f"Panjang byte harus sama untuk '{rule.old}' → '{rule.new}' "
                f"({len(old)} → {len(new)} byte)."
            )
        if old == new:
            raise ValueError(f"Nama lama dan baru sama: '{rule.old}'.")
        if old in seen:
            raise ValueError(f"Aturan nama lama '{rule.old}' dimasukkan lebih dari sekali.")
        seen.add(old)

        offsets = find_byte_occurrences(data, old)
        occupied.extend((offset, offset + len(old), rule.old) for offset in offsets)
        previews.append(ReplacementPreview(rule, old, new, offsets))

    occupied.sort()
    for previous, current in zip(occupied, occupied[1:]):
        if current[0] < previous[1]:
            raise ValueError(
                f"Aturan '{current[2]}' bertumpang-tindih dengan '{previous[2]}' "
                f"di offset 0x{current[0]:X}. Hapus salah satu aturan."
            )
    return previews


def apply_replacements(document, replacements: Iterable[TextReplacement]) -> int:
    """Terapkan semua aturan ke HexDocument sebagai satu transaksi Undo.

    Mengembalikan jumlah lokasi yang diubah. Seluruh aturan diperiksa dahulu;
    bila ada satu nama yang tidak ditemukan, tidak ada byte yang disentuh.
    """
    previews = preview_replacements(document.data, replacements)
    missing = [preview.replacement.old for preview in previews if not preview.offsets]
    if missing:
        raise ValueError("Nama lama tidak ditemukan: " + ", ".join(repr(x) for x in missing))

    writes: list[tuple[int, bytes, str]] = []
    for preview in previews:
        rule = preview.replacement
        note = f"{rule.category}: {rule.old} → {rule.new}"
        writes.extend((offset, preview.new_bytes, note) for offset in preview.offsets)

    document.write_many(writes)
    return len(writes)


def scan_ascii_strings(
    data: bytes | bytearray,
    *,
    min_length: int = 3,
    limit: int = 20_000,
) -> tuple[list[StringCandidate], bool]:
    """Cari run ASCII tercetak sebagai petunjuk, bukan hasil dekode terverifikasi.

    Mengembalikan (kandidat, terpotong). Batas hasil melindungi GUI dari tabel
    yang terlalu besar saat file biner berisi banyak potongan teks.
    """
    if min_length < 1:
        raise ValueError("min_length harus lebih besar dari nol.")
    if limit < 1:
        raise ValueError("limit harus lebih besar dari nol.")

    if min_length == 3:
        pattern = _ASCII_RUN
    else:
        pattern = re.compile(rb"[\x20-\x7E]{" + str(min_length).encode("ascii") + rb",}")

    candidates: list[StringCandidate] = []
    iterator = pattern.finditer(data)
    for match in iterator:
        if len(candidates) == limit:
            return candidates, True
        candidates.append(StringCandidate(match.start(), match.group().decode("ascii")))
    return candidates, False
