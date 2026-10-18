"""Deteksi/dekompresi aman untuk kandidat zlib. Tidak memodifikasi apa pun."""
from __future__ import annotations
import zlib

ZLIB_HEADERS = (b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")

def scan_zlib(data: bytes, limit=200):
    """Cari kandidat stream zlib yang valid penuh. Return [(offset, compressed_len, out_len)]."""
    res = []
    for hdr in ZLIB_HEADERS:
        i = 0
        while len(res) < limit and (i := data.find(hdr, i)) != -1:
            try:
                d = zlib.decompressobj()
                out = d.decompress(data[i:i + (1 << 24)])
                if d.eof and len(out) > 0:
                    clen = len(data[i:i + (1 << 24)]) - len(d.unused_data)
                    res.append((i, clen, len(out)))
            except zlib.error:
                pass
            i += 1
    return sorted(res)

def try_decompress(data: bytes, offset: int) -> bytes:
    d = zlib.decompressobj()
    out = d.decompress(data[offset:])
    if not d.eof:
        raise ValueError("Stream zlib tidak lengkap")
    return out
