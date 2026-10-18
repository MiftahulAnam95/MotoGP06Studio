"""File SINTETIS untuk demo/test. BUKAN format MotoGP.DAT asli."""
import struct
from .rider_parser import TableSchema, FieldDef

DEMO_NAMES = ["DEMO RIDER ONE", "DEMO RIDER TWO", "DEMO RIDER THREE", "DEMO RIDER FOUR"]
BASE, STRIDE = 0x100, 32

def make_demo_file():
    buf = bytearray(b"\xAA" * 0x400)
    buf[0:8] = b"SYNTHDAT"
    for i, n in enumerate(DEMO_NAMES):
        o = BASE + i * STRIDE
        buf[o:o + 20] = n.encode().ljust(20, b"\0")
        buf[o + 20:o + 22] = struct.pack("<H", 10 + i)   # nomor
        buf[o + 22:o + 24] = struct.pack("<H", i)        # id model
        buf[o + 24:o + 32] = b"\0" * 8
    return bytes(buf)

def demo_schema():
    return TableSchema("demo_riders", BASE, STRIDE, len(DEMO_NAMES), "<", [
        FieldDef("name", 0, "str", 20), FieldDef("number", 20, "u16"), FieldDef("model_id", 22, "u16")], verified=True)
