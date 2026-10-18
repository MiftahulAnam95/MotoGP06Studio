"""Analisis eksploratori. SEMUA hasil adalah KANDIDAT (verified=False) sampai dikonfirmasi manual."""
from __future__ import annotations
import math, re, struct
from collections import Counter
from dataclasses import dataclass

@dataclass
class Candidate:
    kind: str          # "string", "pointer_table", "record_table", "entropy", ...
    offset: int
    length: int
    confidence: float  # 0..1 heuristik, BUKAN bukti
    detail: str = ""
    verified: bool = False

def entropy(block: bytes) -> float:
    if not block: return 0.0
    n = len(block)
    return -sum(c / n * math.log2(c / n) for c in Counter(block).values())

def entropy_map(data: bytes, block=0x10000):
    """Entropi per blok. >7.5 bit/byte biasanya terkompresi/terenkripsi."""
    return [(o, entropy(data[o:o + block])) for o in range(0, len(data), block)]

def find_strings(data: bytes, min_len=4, limit=5000):
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, data):
        out.append(Candidate("string_ascii", m.start(), len(m.group()), 0.6, m.group().decode("ascii")))
        if len(out) >= limit: return out
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % min_len, data):
        out.append(Candidate("string_utf16le", m.start(), len(m.group()), 0.6, m.group().decode("utf-16le")))
        if len(out) >= limit * 2: break
    return sorted(out, key=lambda c: c.offset)

def find_pointer_tables(data: bytes, min_run=8, limit=200):
    """Deret uint32 LE naik-monoton dan semuanya < ukuran file (kandidat tabel offset)."""
    size, res, i = len(data), [], 0
    n = len(data) // 4 * 4
    while i + 4 * min_run <= n and len(res) < limit:
        prev = struct.unpack_from("<I", data, i)[0]
        if not 0 < prev < size: i += 4; continue
        j = i + 4
        while j + 4 <= n:
            v = struct.unpack_from("<I", data, j)[0]
            if not prev < v < size: break
            prev = v; j += 4
        run = (j - i) // 4
        if run >= min_run:
            conf = min(0.9, 0.3 + run / 100)
            res.append(Candidate("pointer_table", i, run * 4, conf, f"{run} entri uint32 LE menaik"))
            i = j
        else:
            i += 4
    return res

def find_record_strides(data: bytes, start=0, window=0x4000, strides=range(8, 257, 4)):
    """Kandidat panjang record: stride dengan banyak kolom byte konstan pada window."""
    chunk = data[start:start + window]
    scored = []
    for s in strides:
        rows = len(chunk) // s
        if rows < 8: continue
        const = 0
        for col in range(s):
            if len({chunk[r * s + col] for r in range(rows)}) == 1: const += 1
        scored.append((const / s, s))
    scored.sort(reverse=True)
    return [Candidate("record_stride", start, s, round(min(sc, 0.8), 2), f"stride={s}, {sc:.0%} kolom konstan")
            for sc, s in scored[:5] if sc > 0.2]

def analyze(data: bytes, progress=None):
    res = {"entropy": entropy_map(data)}
    if progress: progress(25)
    res["strings"] = find_strings(data); 
    if progress: progress(60)
    res["pointer_tables"] = find_pointer_tables(data)
    if progress: progress(85)
    res["strides"] = find_record_strides(data)
    if progress: progress(100)
    return res

def compare(a: bytes, b: bytes, max_ranges=10000):
    """Bandingkan dua buffer. Return daftar (offset, len_a, len_b, bytes_a, bytes_b); mendukung beda panjang."""
    out, n, start = [], min(len(a), len(b)), None
    for i in range(n):
        if a[i] != b[i]:
            if start is None: start = i
        elif start is not None:
            out.append((start, i - start, a[start:i], b[start:i])); start = None
            if len(out) >= max_ranges: return out
    if start is not None: out.append((start, n - start, a[start:n], b[start:n]))
    if len(a) != len(b):
        out.append((n, abs(len(a) - len(b)), a[n:], b[n:]))
    return out
