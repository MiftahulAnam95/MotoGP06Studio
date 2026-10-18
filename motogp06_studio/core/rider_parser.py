"""Parser tabel record berbasis SKEMA. Skema harus diisi/diverifikasi manusia setelah analisis.
Tidak ada skema bawaan untuk MotoGP.DAT asli karena strukturnya belum dipetakan."""
from __future__ import annotations
import json, struct
from dataclasses import dataclass, asdict
from . import validation as V
from .hex_editor import HexDocument

@dataclass
class FieldDef:
    name: str
    offset: int          # relatif ke awal record
    kind: str            # "str" | "u8" | "u16" | "u32"
    size: int = 0        # wajib untuk str
    encoding: str = "ascii"
    verified: bool = False

@dataclass
class TableSchema:
    name: str
    base: int
    stride: int
    count: int
    endian: str = "<"
    fields: list = None
    verified: bool = False

    def to_json(self): return json.dumps(asdict(self), indent=2)
    @classmethod
    def from_json(cls, t):
        d = json.loads(t); d["fields"] = [FieldDef(**f) for f in d["fields"]]; return cls(**d)

_INT = {"u8": (1, "B"), "u16": (2, "H"), "u32": (4, "I")}

def _span(f: FieldDef):
    return f.size if f.kind == "str" else _INT[f.kind][0]

def validate_schema(schema: TableSchema, file_size: int):
    V.check_record_bounds(file_size, schema.base, schema.stride, schema.count)
    for f in schema.fields:
        if f.offset < 0 or f.offset + _span(f) > schema.stride:
            raise ValueError(f"Field '{f.name}' keluar dari batas record (stride {schema.stride})")

def read_records(doc: HexDocument, schema: TableSchema):
    validate_schema(schema, len(doc))
    rows = []
    for i in range(schema.count):
        rec = schema.base + i * schema.stride
        row = {"_index": i, "_offset": rec}
        for f in schema.fields:
            o = rec + f.offset
            if f.kind == "str":
                row[f.name] = V.decode_fixed_string(bytes(doc.data[o:o + f.size]), f.encoding)
            else:
                row[f.name] = struct.unpack_from(schema.endian + _INT[f.kind][1], doc.data, o)[0]
        rows.append(row)
    return rows

def write_field(doc: HexDocument, schema: TableSchema, index: int, field_name: str, value):
    if not 0 <= index < schema.count: raise IndexError("Indeks record di luar rentang")
    f = next((x for x in schema.fields if x.name == field_name), None)
    if f is None: raise KeyError(field_name)
    o = schema.base + index * schema.stride + f.offset
    if f.kind == "str":
        raw = V.encode_fixed_string(str(value), f.size, f.encoding)
    else:
        size, code = _INT[f.kind]
        V.check_int_range(int(value), size)
        raw = struct.pack(schema.endian + code, int(value))
    return doc.write(o, raw, note=f"record {index}.{field_name} = {value!r}")
