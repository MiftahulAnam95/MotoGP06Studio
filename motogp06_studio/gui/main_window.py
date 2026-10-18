"""Jendela utama. Semua pekerjaan berat dijalankan di worker thread."""
from __future__ import annotations
import logging, os, sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QListWidget, QStackedWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QTableView,
    QTabWidget, QPlainTextEdit, QLineEdit, QProgressBar, QComboBox, QHeaderView)
from ..core import file_manager as FM, binary_analyzer as BA, rider_parser as RP, demo as DEMO
from ..core.backup_manager import BackupManager, atomic_write
from ..core.hex_editor import HexDocument
from ..core.patch_engine import Patch, PatchError
from .hex_model import HexModel
from .theme import QSS

log = logging.getLogger("motogp06")
APP_DIR = Path(sys.argv[0]).resolve().parent
PORTABLE = (APP_DIR / "portable.flag").exists()
DATA_DIR = (APP_DIR / "data") if PORTABLE else Path(os.environ.get("APPDATA", Path.home())) / "MotoGP06Studio"
DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=DATA_DIR / "studio.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

class Worker(QThread):
    progress = Signal(int); done = Signal(object); failed = Signal(str)
    def __init__(self, fn): super().__init__(); self.fn = fn
    def run(self):
        try: self.done.emit(self.fn(self.progress.emit))
        except Exception as e:
            log.exception("Worker gagal"); self.failed.emit(f"{type(e).__name__}: {e}")

def label(text, name=None, wrap=True):
    l = QLabel(text); l.setWordWrap(wrap)
    if name: l.setObjectName(name)
    return l

class MainWindow(QMainWindow):
    NAV = ["Dashboard", "File Explorer", "Binary Analyzer", "Rider Editor", "Bike Model Editor",
           "Hex Editor", "Patch Manager", "Settings", "About"]
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MotoGP06 PSP Modding Studio"); self.resize(1280, 780); self.setAcceptDrops(True)
        self.info = None; self.doc = None; self.schema = None; self.demo = False; self._workers = []
        self.backups = BackupManager(DATA_DIR / "backups")
        self.nav = QListWidget(); self.nav.setObjectName("nav"); self.nav.addItems(self.NAV)
        self.stack = QStackedWidget()
        self.pages = [self.pg_dashboard(), self.pg_files(), self.pg_analyzer(), self.pg_riders(), self.pg_bike(),
                      self.pg_hex(), self.pg_patch(), self.pg_settings(), self.pg_about()]
        for p in self.pages: self.stack.addWidget(p)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex); self.nav.setCurrentRow(0)
        c = QWidget(); h = QHBoxLayout(c); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        h.addWidget(self.nav); h.addWidget(self.stack, 1); self.setCentralWidget(c)
        self.progress = QProgressBar(); self.progress.setMaximumWidth(220); self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress); self.statusBar().showMessage("Siap. Belum ada file dibuka.")
        self.refresh_all()

    # ---------- util ----------
    def err(self, msg): log.error(msg); QMessageBox.critical(self, "Kesalahan", msg)
    def run_bg(self, fn, on_done, busy="Memproses..."):
        w = Worker(fn); self._workers.append(w)
        self.progress.setValue(0); self.progress.show(); self.statusBar().showMessage(busy)
        w.progress.connect(self.progress.setValue)
        def fin(r):
            self.progress.hide(); self.statusBar().showMessage("Selesai."); on_done(r)
        def bad(m):
            self.progress.hide(); self.statusBar().showMessage("Gagal."); self.err(m)
        w.done.connect(fin); w.failed.connect(bad); w.finished.connect(lambda: self._workers.remove(w)); w.start()
    def need_doc(self):
        if self.doc is None: QMessageBox.information(self, "Belum ada file", "Buka file atau jalankan Demo Mode dahulu."); return False
        return True
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        u = e.mimeData().urls()
        if u: self.load_file(u[0].toLocalFile())

    # ---------- pembukaan file ----------
    def open_dialog(self):
        p, _ = QFileDialog.getOpenFileName(self, "Buka MotoGP.DAT", "", "Semua file (*)")
        if p: self.load_file(p)
    def load_file(self, path):
        def job(prog):
            info = FM.open_file(path, prog)
            if info.size > 1 << 30: raise MemoryError("File > 1 GiB tidak didukung pada versi ini.")
            return info, Path(path).read_bytes()
        def ok(r):
            self.info, data = r; self.doc = HexDocument(data); self.schema = None; self.demo = False
            self.hexmodel.set_doc(self.doc); self.refresh_all(); self.nav.setCurrentRow(1)
        self.run_bg(job, ok, f"Membuka {path}...")
    def start_demo(self):
        self.info = None; self.doc = HexDocument(DEMO.make_demo_file()); self.schema = DEMO.demo_schema(); self.demo = True
        self.hexmodel.set_doc(self.doc); self.refresh_all(); self.nav.setCurrentRow(3)

    # ---------- Dashboard ----------
    def pg_dashboard(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Dashboard", "h1"))
        self.dash = label(""); l.addWidget(self.dash); l.addStretch()
        b = QHBoxLayout(); o = QPushButton("Buka MotoGP.DAT"); o.setObjectName("primary"); o.clicked.connect(self.open_dialog)
        d = QPushButton("Demo Mode (data sintetis)"); d.clicked.connect(self.start_demo); b.addWidget(o); b.addWidget(d); b.addStretch(); l.addLayout(b)
        return w
    def refresh_dash(self):
        if self.doc is None:
            self.dash.setText("Belum ada file dibuka.\nBuka MotoGP.DAT (atau seret ke jendela ini), atau coba Demo Mode.\n"
                              "Catatan: struktur MotoGP.DAT belum dipetakan; editor rider baru aktif setelah skema diverifikasi."); return
        t = []
        if self.demo: t.append("⚠ DEMO MODE: file sintetis, BUKAN MotoGP.DAT asli.")
        if self.info:
            i = self.info; t += [f"File: {i.path.name}  ({i.size:,} byte)", f"SHA-256: {i.sha256}"]
            t += [f"Identifikasi: {x.name} (keyakinan {x.confidence:.0%}, belum terverifikasi)" for x in i.identifications]
            t += [f"⚠ {x}" for x in i.warnings]
        if self.schema:
            try: RP.validate_schema(self.schema, len(self.doc)); v = "lolos validasi batas"
            except Exception as e: v = f"GAGAL: {e}"
            t += [f"Skema '{self.schema.name}': {self.schema.count} record, {len(self.schema.fields)} field, "
                  f"{'terverifikasi' if self.schema.verified else 'BELUM terverifikasi'}; {v}"]
        else: t.append("Record rider: 0 (struktur belum dipetakan). Gunakan Binary Analyzer.")
        t.append(f"Perubahan belum disimpan: {len(self.doc.changed_ranges())} rentang")
        self.dash.setText("\n".join(t))

    # ---------- File Explorer ----------
    def pg_files(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("File Explorer", "h1"))
        self.finfo = QPlainTextEdit(); self.finfo.setReadOnly(True); l.addWidget(self.finfo)
        b = QHBoxLayout()
        for txt, fn in [("Buka File", self.open_dialog), ("Buat Backup", self.do_backup), ("Restore Backup...", self.do_restore),
                        ("Simpan Sebagai File Baru...", self.do_save_as)]:
            x = QPushButton(txt); x.clicked.connect(fn); b.addWidget(x)
        b.addStretch(); l.addLayout(b); return w
    def refresh_files(self):
        if not self.doc: self.finfo.setPlainText("Belum ada file."); return
        i = self.info
        self.finfo.setPlainText("DEMO (sintetis)" if not i else
            f"Nama   : {i.path.name}\nLokasi : {i.path.parent}\nUkuran : {i.size:,} byte\nSHA-256: {i.sha256}\nMD5    : {i.md5}\nCRC32  : {i.crc32}\n\n"
            + "\n".join(f"Format  : {x.name} [{x.confidence:.0%}] {x.note}" for x in i.identifications)
            + "\n" + "\n".join(f"PERINGATAN: {x}" for x in i.warnings))
    def do_backup(self):
        if not self.info: return QMessageBox.information(self, "Backup", "Backup hanya untuk file asli yang dibuka.")
        try: b = self.backups.create(self.info.path); QMessageBox.information(self, "Backup", f"Backup dibuat:\n{b}")
        except Exception as e: self.err(str(e))
    def do_restore(self):
        p, _ = QFileDialog.getOpenFileName(self, "Pilih backup", str(self.backups.dir), "Backup (*.bak)")
        if not p: return
        d, _ = QFileDialog.getSaveFileName(self, "Restore ke (file baru)", Path(p).stem)
        if not d: return
        try: self.backups.restore(p, d, overwrite=False); QMessageBox.information(self, "Restore", f"Dipulihkan ke:\n{d}")
        except Exception as e: self.err(str(e))
    def do_save_as(self):
        if not self.need_doc(): return
        base = self.info.path if self.info else Path("demo.dat")
        d, _ = QFileDialog.getSaveFileName(self, "Simpan hasil sebagai file BARU", str(base.with_name(base.stem + "_mod" + base.suffix)))
        if not d: return
        if self.info and Path(d).resolve() == self.info.path.resolve():
            return self.err("Menimpa file asli diblokir. Pilih nama lain.")
        try:
            if self.info: self.backups.create(self.info.path)
            out = self.doc.export(); atomic_write(d, out)
            diffs = BA.compare(self.doc.original, out)
            QMessageBox.information(self, "Tersimpan", f"Disimpan: {d}\nRentang berubah: {len(diffs)}\nByte berubah: {sum(x[1] for x in diffs)}\n"
                "Peringatan: berhasil disimpan ≠ kompatibel dengan game. Uji di emulator dengan salinan.")
        except Exception as e: self.err(str(e))

    # ---------- Binary Analyzer ----------
    def pg_analyzer(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Binary Analyzer", "h1"))
        l.addWidget(label("Semua hasil adalah KANDIDAT heuristik, bukan fakta. Verifikasi manual di Hex Editor.", "warn"))
        b = QHBoxLayout(); r = QPushButton("Jalankan Analisis"); r.setObjectName("primary"); r.clicked.connect(self.do_analyze)
        c = QPushButton("Bandingkan dengan file lain..."); c.clicked.connect(self.do_compare); b.addWidget(r); b.addWidget(c); b.addStretch(); l.addLayout(b)
        self.atabs = QTabWidget(); l.addWidget(self.atabs, 1)
        self.t_str, self.t_ptr, self.t_stride, self.t_ent, self.t_cmp = (self.mk_table(h) for h in [
            ["Offset", "Panjang", "Jenis", "Yakin", "Isi"], ["Offset", "Byte", "Yakin", "Detail"],
            ["Offset", "Stride", "Yakin", "Detail"], ["Offset", "Entropi (bit/byte)", "Catatan"], ["Offset", "Panjang", "A", "B"]])
        for t, n in [(self.t_str, "String"), (self.t_ptr, "Tabel pointer"), (self.t_stride, "Panjang record"), (self.t_ent, "Entropi"), (self.t_cmp, "Perbandingan")]:
            self.atabs.addTab(t, n)
        return w
    def mk_table(self, headers):
        t = QTableWidget(0, len(headers)); t.setHorizontalHeaderLabels(headers); t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.horizontalHeader().setStretchLastSection(True); return t
    def fill(self, t, rows):
        t.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(row): t.setItem(r, c, QTableWidgetItem(str(v)))
    def do_analyze(self):
        if not self.need_doc(): return
        data = bytes(self.doc.original)
        def ok(res):
            self.fill(self.t_str, [(f"0x{c.offset:X}", c.length, c.kind, f"{c.confidence:.0%}", c.detail[:120]) for c in res["strings"]])
            self.fill(self.t_ptr, [(f"0x{c.offset:X}", c.length, f"{c.confidence:.0%}", c.detail) for c in res["pointer_tables"]])
            self.fill(self.t_stride, [(f"0x{c.offset:X}", c.length, f"{c.confidence:.0%}", c.detail) for c in res["strides"]])
            self.fill(self.t_ent, [(f"0x{o:X}", f"{e:.2f}", "kemungkinan terkompresi/terenkripsi" if e > 7.5 else "") for o, e in res["entropy"]])
        self.run_bg(lambda p: BA.analyze(data, p), ok, "Menganalisis...")
    def do_compare(self):
        if not self.need_doc(): return
        p, _ = QFileDialog.getOpenFileName(self, "File pembanding")
        if not p: return
        a, cur = bytes(self.doc.original), bytes(self.doc.data)
        def job(prog): return BA.compare(a, Path(p).read_bytes())
        self.run_bg(job, lambda r: (self.fill(self.t_cmp, [(f"0x{o:X}", n, x[:16].hex(" "), y[:16].hex(" ")) for o, n, x, y in r[:2000]]),
                                    self.atabs.setCurrentWidget(self.t_cmp)), "Membandingkan...")

    # ---------- Rider Editor ----------
    def pg_riders(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Rider Editor", "h1"))
        self.rider_banner = label("", "warn"); l.addWidget(self.rider_banner)
        b = QHBoxLayout(); self.rfilter = QLineEdit(); self.rfilter.setPlaceholderText("Cari rider..."); self.rfilter.textChanged.connect(self.filter_riders)
        sc = QPushButton("Muat skema JSON..."); sc.clicked.connect(self.load_schema)
        u = QPushButton("Undo"); u.clicked.connect(lambda: self.hex_undo(True)); rd = QPushButton("Redo"); rd.clicked.connect(lambda: self.hex_undo(False))
        for x in (self.rfilter, sc, u, rd): b.addWidget(x)
        l.addLayout(b); self.rtable = QTableWidget(); l.addWidget(self.rtable, 1)
        self.rtable.itemChanged.connect(self.rider_edited); self._rider_busy = False; return w
    def load_schema(self):
        p, _ = QFileDialog.getOpenFileName(self, "Skema JSON", "", "JSON (*.json)")
        if not p or not self.need_doc(): return
        try:
            s = RP.TableSchema.from_json(Path(p).read_text()); RP.validate_schema(s, len(self.doc)); self.schema = s; self.refresh_all()
        except Exception as e: self.err(f"Skema ditolak: {e}")
    def refresh_riders(self):
        self._rider_busy = True
        if not self.schema or not self.doc:
            self.rider_banner.setText("Struktur rider belum dipetakan, jadi editor tidak ditampilkan (tidak ada data palsu). "
                "Gunakan Binary Analyzer, lalu muat skema JSON yang sudah Anda verifikasi, atau coba Demo Mode.")
            self.rtable.setRowCount(0); self.rtable.setColumnCount(0); self._rider_busy = False; return
        self.rider_banner.setText(("DEMO MODE: data sintetis. " if self.demo else "") +
            ("Skema terverifikasi." if self.schema.verified else "Skema BELUM terverifikasi: edit berisiko."))
        rows = RP.read_records(self.doc, self.schema); cols = ["#", "Offset"] + [f.name for f in self.schema.fields]
        self.rtable.setColumnCount(len(cols)); self.rtable.setHorizontalHeaderLabels(cols); self.rtable.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["_index"], f"0x{row['_offset']:X}"] + [row[f.name] for f in self.schema.fields]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if c < 2: it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.rtable.setItem(r, c, it)
        self._rider_busy = False; self.filter_riders()
    def filter_riders(self):
        q = self.rfilter.text().lower()
        for r in range(self.rtable.rowCount()):
            txt = " ".join((self.rtable.item(r, c).text() if self.rtable.item(r, c) else "") for c in range(self.rtable.columnCount())).lower()
            self.rtable.setRowHidden(r, q not in txt)
    def rider_edited(self, item):
        if self._rider_busy or item.column() < 2: return
        idx = int(self.rtable.item(item.row(), 0).text()); name = self.schema.fields[item.column() - 2].name
        try: RP.write_field(self.doc, self.schema, idx, name, item.text())
        except Exception as e: self.err(f"Perubahan ditolak: {e}")
        self.refresh_all()

    # ---------- Bike ----------
    def pg_bike(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Bike Model Editor", "h1"))
        l.addWidget(label("Belum tersedia. Format aset model motor belum dianalisis, dan MotoGP.DAT belum tentu memuat geometri 3D. "
            "Mengganti model hanya dengan mengubah ID tanpa memahami mesh, material, tekstur, skeleton, dan referensi dapat merusak game. "
            "Langkah berikutnya (Tahap 4): petakan hubungan rider→model dari sampel nyata, lalu identifikasi file aset terkait.", "warn"))
        l.addStretch(); return w

    # ---------- Hex ----------
    def pg_hex(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Hex Editor", "h1"))
        b = QHBoxLayout(); self.goto = QLineEdit(); self.goto.setPlaceholderText("Offset (hex, mis. 1F0)"); self.goto.returnPressed.connect(self.do_goto)
        self.smode = QComboBox(); self.smode.addItems(["Byte (hex)", "String ASCII", "String UTF-16LE", "Int32 LE", "Int32 BE", "Int16 LE", "Int16 BE"])
        self.sq = QLineEdit(); self.sq.setPlaceholderText("Cari..."); self.sq.returnPressed.connect(self.do_search)
        u = QPushButton("Undo"); u.clicked.connect(lambda: self.hex_undo(True)); r = QPushButton("Redo"); r.clicked.connect(lambda: self.hex_undo(False))
        for x in (self.goto, self.smode, self.sq, u, r): b.addWidget(x)
        l.addLayout(b)
        self.hexmodel = HexModel(None, on_error=self.err, on_change=self.refresh_all)
        self.hexview = QTableView(); self.hexview.setModel(self.hexmodel)
        for c in range(16): self.hexview.setColumnWidth(c, 30)
        self.hexview.setColumnWidth(16, 150); self.hexview.verticalHeader().setDefaultSectionSize(20); l.addWidget(self.hexview, 1)
        self.hexlog = QPlainTextEdit(); self.hexlog.setReadOnly(True); self.hexlog.setMaximumHeight(130); l.addWidget(self.hexlog)
        return w
    def do_goto(self):
        if not self.need_doc(): return
        try:
            o = int(self.goto.text(), 16)
            if not 0 <= o < len(self.doc): raise ValueError("Offset di luar file")
            self.hexview.selectRow(o // 16); self.hexview.scrollTo(self.hexmodel.index(o // 16, o % 16))
        except Exception as e: self.err(str(e))
    def do_search(self):
        if not self.need_doc(): return
        m, q = self.smode.currentIndex(), self.sq.text().strip()
        try:
            if m == 0: hits = self.doc.find_bytes(bytes.fromhex(q))
            elif m == 1: hits = self.doc.find_string(q)
            elif m == 2: hits = self.doc.find_string(q, "utf-16le")
            else: hits = self.doc.find_int(int(q, 0), 4 if m < 5 else 2, "<" if m in (3, 5) else ">")
        except Exception as e: return self.err(str(e))
        self.statusBar().showMessage(f"{len(hits)} hasil" + (f"; pertama di 0x{hits[0]:X}" if hits else ""))
        if hits: self.goto.setText(f"{hits[0]:X}"); self.do_goto()
    def hex_undo(self, undo):
        if self.doc: (self.doc.undo if undo else self.doc.redo)(); self.refresh_all()
    def refresh_hexlog(self):
        self.hexlog.setPlainText("\n".join(f"0x{c.offset:08X}: {c.old.hex(' ')} -> {c.new.hex(' ')}  {c.note}" for c in (self.doc.log[-200:] if self.doc else [])))

    # ---------- Patch ----------
    def pg_patch(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Patch Manager", "h1"))
        self.pinfo = label(""); l.addWidget(self.pinfo)
        b = QHBoxLayout()
        for txt, fn in [("Simpan perubahan sebagai patch (.json)...", self.patch_save), ("Terapkan patch ke file...", self.patch_apply), ("Rollback patch pada file...", self.patch_revert)]:
            x = QPushButton(txt); x.clicked.connect(fn); b.addWidget(x)
        b.addStretch(); l.addLayout(b); l.addStretch(); return w
    def patch_save(self):
        if not self.need_doc(): return
        try: p = Patch.from_diff(self.doc.original, self.doc.export())
        except PatchError as e: return self.err(str(e))
        if not p.entries: return QMessageBox.information(self, "Patch", "Tidak ada perubahan.")
        d, _ = QFileDialog.getSaveFileName(self, "Simpan patch", "mod.patch.json", "JSON (*.json)")
        if d: atomic_write(d, p.to_json().encode())
    def _patch_op(self, rev):
        pp, _ = QFileDialog.getOpenFileName(self, "Pilih patch", "", "JSON (*.json)")
        if not pp: return
        tp, _ = QFileDialog.getOpenFileName(self, "Pilih file target")
        if not tp: return
        op, _ = QFileDialog.getSaveFileName(self, "Simpan hasil sebagai file baru")
        if not op or Path(op).resolve() == Path(tp).resolve(): return self.err("Pilih file keluaran baru (bukan file target).")
        try:
            p = Patch.from_json(Path(pp).read_text()); d = Path(tp).read_bytes()
            atomic_write(op, p.revert(d) if rev else p.apply(d)); QMessageBox.information(self, "Patch", f"Selesai: {op}")
        except Exception as e: self.err(str(e))
    def patch_apply(self): self._patch_op(False)
    def patch_revert(self): self._patch_op(True)

    # ---------- Settings / About ----------
    def pg_settings(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Settings", "h1"))
        l.addWidget(label(f"Mode portable: {'AKTIF' if PORTABLE else 'nonaktif (buat file kosong portable.flag di samping run.py untuk mengaktifkan)'}\n"
                          f"Folder data/log: {DATA_DIR}\nFolder backup: {DATA_DIR / 'backups'}")); l.addStretch(); return w
    def pg_about(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("MotoGP06 PSP Modding Studio", "h1"))
        l.addWidget(label("Versi 0.1 (Tahap 1: fondasi). Format MotoGP.DAT belum dipetakan. Fitur edit rider bekerja berdasarkan skema "
                          "yang diverifikasi pengguna; Bike Model Editor belum diimplementasikan. Lihat docs/FORMAT_NOTES.md.")); l.addStretch(); return w

    def refresh_all(self):
        self.refresh_dash(); self.refresh_files(); self.refresh_riders(); self.hexmodel.refresh(); self.refresh_hexlog()
        n = len(self.doc.changed_ranges()) if self.doc else 0
        self.pinfo.setText("Belum ada file." if not self.doc else f"Perubahan saat ini: {n} rentang. Patch menyimpan offset, byte lama/baru, dan hash file sumber.")
        self.setWindowTitle("MotoGP06 PSP Modding Studio" + (" • perubahan belum disimpan" if n else ""))

def main():
    app = QApplication(sys.argv); app.setStyleSheet(QSS)
    w = MainWindow(); w.show(); return app.exec()
