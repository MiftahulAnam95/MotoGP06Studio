import hashlib, os, struct, tempfile, unittest, zlib
from pathlib import Path
from motogp06_studio.core import file_manager as FM, backup_manager as BM, binary_analyzer as BA
from motogp06_studio.core import validation as V, rider_parser as RP, demo
from motogp06_studio.core.hex_editor import HexDocument
from motogp06_studio.core.patch_engine import Patch, PatchError
from motogp06_studio.core.compression_handler import scan_zlib, try_decompress

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
        self.data = demo.make_demo_file()
        self.f = self.dir / "SYNTH.DAT"; self.f.write_bytes(self.data)
    def tearDown(self): self.tmp.cleanup()

class TestFile(Base):
    def test_open_and_hash(self):
        i = FM.open_file(self.f)
        self.assertEqual(i.size, len(self.data)); self.assertEqual(i.sha256, hashlib.sha256(self.data).hexdigest())
        self.assertTrue(any("belum dikenal" in w for w in i.warnings))
    def test_identify_7z_and_zero_size(self):
        self.assertEqual(FM.identify(b"7z\xbc\xaf\x27\x1c" + b"\0" * 10, 16)[0].name, "7-Zip archive")
        e = self.dir / "e.dat"; e.write_bytes(b"")
        self.assertTrue(FM.open_file(e).warnings)
    def test_missing(self):
        with self.assertRaises(FileNotFoundError): FM.open_file(self.dir / "nope")
    def test_truncated_detected_by_bounds(self):
        with self.assertRaises(ValueError): V.check_record_bounds(100, 0x80, 32, 4)

class TestBackup(Base):
    def test_backup_restore(self):
        bm = BM.BackupManager(self.dir / "bk"); b = bm.create(self.f)
        self.assertTrue(bm.verify(b)); self.f.write_bytes(b"corrupt")
        with self.assertRaises(FileExistsError): bm.restore(b, self.f)
        bm.restore(b, self.f, overwrite=True); self.assertEqual(self.f.read_bytes(), self.data)
    def test_corrupt_backup_rejected(self):
        bm = BM.BackupManager(self.dir / "bk"); b = bm.create(self.f)
        b.write_bytes(b"x")
        with self.assertRaises(ValueError): bm.restore(b, self.dir / "o.dat")
    def test_atomic_write(self):
        BM.atomic_write(self.dir / "a.bin", b"abc"); self.assertEqual((self.dir / "a.bin").read_bytes(), b"abc")
        self.assertFalse(list(self.dir.glob(".tmp_*")))

class TestHex(Base):
    def test_write_undo_redo_log(self):
        d = HexDocument(self.data); d.write(0x10, b"\x01\x02")
        self.assertTrue(d.dirty); d.undo(); self.assertFalse(d.dirty)
        d.redo(); self.assertEqual(d.data[0x10:0x12], b"\x01\x02"); self.assertEqual(len(d.log), 3)
    def test_bounds_and_protect(self):
        d = HexDocument(self.data)
        with self.assertRaises(ValueError): d.write(len(d) - 1, b"\0\0")
        d.protect(0, 8, "header")
        with self.assertRaises(PermissionError): d.write(4, b"\0")
    def test_length_constant_and_search(self):
        d = HexDocument(self.data); d.write(0x300, struct.pack("<I", 0xDEADBEEF))
        self.assertEqual(len(d.export()), len(self.data))
        self.assertIn(0x300, d.find_int(0xDEADBEEF)); self.assertIn(0x100, d.find_string("DEMO RIDER ONE"))
        self.assertEqual(d.find_int(0xDEADBEEF, endian=">"), [])

class TestParser(Base):
    def test_read_write_roundtrip_untouched_bytes(self):
        d, s = HexDocument(self.data), demo.demo_schema()
        rows = RP.read_records(d, s); self.assertEqual(rows[1]["name"], "DEMO RIDER TWO"); self.assertEqual(rows[2]["number"], 12)
        RP.write_field(d, s, 1, "name", "NEW NAME"); RP.write_field(d, s, 1, "number", 46)
        out = d.export(); r = RP.read_records(HexDocument(out), s)[1]
        self.assertEqual((r["name"], r["number"]), ("NEW NAME", 46))
        allowed = set(range(0x100 + 32, 0x100 + 32 + 22))
        diff = [o for o, *_ in BA.compare(self.data, out)]
        for off, ln, *_ in BA.compare(self.data, out):
            self.assertTrue(all(x in allowed for x in range(off, off + ln)))
    def test_name_too_long_and_range(self):
        d, s = HexDocument(self.data), demo.demo_schema()
        with self.assertRaises(ValueError): RP.write_field(d, s, 0, "name", "X" * 21)
        with self.assertRaises(ValueError): RP.write_field(d, s, 0, "number", 70000)
        with self.assertRaises(UnicodeEncodeError): RP.write_field(d, s, 0, "name", "Ñandú€")
    def test_schema_bounds(self):
        s = demo.demo_schema(); s.fields[0].size = 40
        with self.assertRaises(ValueError): RP.validate_schema(s, len(self.data))
    def test_schema_json(self):
        s = demo.demo_schema(); self.assertEqual(RP.TableSchema.from_json(s.to_json()).stride, 32)

class TestPatch(Base):
    def test_create_apply_revert_reject(self):
        mod = bytearray(self.data); mod[0x100:0x104] = b"ABCD"; mod[0x200] = 1
        p = Patch.from_diff(self.data, bytes(mod)); self.assertEqual(len(p.entries), 2)
        p2 = Patch.from_json(p.to_json())
        patched = p2.apply(self.data); self.assertEqual(patched, bytes(mod)); self.assertEqual(p2.revert(patched), self.data)
        with self.assertRaises(PatchError): p2.apply(self.data[:-1])
        other = bytearray(self.data); other[0] ^= 1
        with self.assertRaises(PatchError): p2.apply(bytes(other))
    def test_length_change_rejected(self):
        with self.assertRaises(PatchError): Patch.from_diff(b"ab", b"abc")

class TestAnalyzer(Base):
    def test_strings_pointers_strides(self):
        self.assertTrue(any("DEMO RIDER" in c.detail for c in BA.find_strings(self.data)))
        tbl = b"".join(struct.pack("<I", 0x40 + i * 0x10) for i in range(20)) + b"\0" * 512
        ptr = BA.find_pointer_tables(tbl); self.assertTrue(ptr and ptr[0].kind == "pointer_table" and not ptr[0].verified)
        self.assertTrue(BA.find_record_strides(self.data, 0x100, 0x80 * 1) is not None)
    def test_compare_and_entropy(self):
        m = bytearray(self.data); m[5] = 0
        self.assertEqual(BA.compare(self.data, bytes(m))[0][0], 5)
        self.assertLess(BA.entropy(b"\0" * 100), 0.1); self.assertGreater(BA.entropy(bytes(range(256))), 7.9)
    def test_zlib_scan(self):
        blob = b"junk" * 5 + zlib.compress(b"hello world" * 20) + b"tail"
        r = scan_zlib(blob); self.assertTrue(r); self.assertEqual(try_decompress(blob, r[0][0]), b"hello world" * 20)

if __name__ == "__main__": unittest.main()
