"""Jendela utama. Semua pekerjaan berat dijalankan di worker thread."""
from __future__ import annotations
import csv, logging, os, sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QListWidget, QStackedWidget, QHBoxLayout,
    QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QTableView,
    QTabWidget, QPlainTextEdit, QLineEdit, QProgressBar, QComboBox, QHeaderView)
from ..core import file_manager as FM, binary_analyzer as BA, rider_parser as RP, demo as DEMO
from ..core.backup_manager import BackupManager, atomic_write
from ..core.hex_editor import HexDocument
from ..core.patch_engine import Patch, PatchError
from ..core.text_modder import TextReplacement, apply_replacements, preview_replacements, scan_ascii_strings
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
    NAV = ["Beranda", "Editor Nama", "Cari Teks", "File & Backup", "Lanjutan"]
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MotoGP06 PSP Modding Studio"); self.resize(1320, 820); self.setAcceptDrops(True)
        self.info = None; self.doc = None; self.schema = None; self.demo = False; self._workers = []
        self.string_candidates = []
        self.backups = BackupManager(DATA_DIR / "backups")
        self.nav = QListWidget(); self.nav.setObjectName("nav"); self.nav.addItems(self.NAV)
        self.stack = QStackedWidget()
        self.pages = [self.pg_dashboard(), self.pg_names(), self.pg_text_browser(), self.pg_files(), self.pg_advanced()]
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
        if self.doc is None:
            QMessageBox.information(self, "Belum ada file", "Buka file data game atau jalankan mode demo dahulu.")
            return False
        return True
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        u = e.mimeData().urls()
        if u: self.load_file(u[0].toLocalFile())
    def closeEvent(self, event):
        if not self.doc or not self.doc.dirty:
            event.accept(); return
        answer = QMessageBox.question(
            self, "Perubahan belum disimpan",
            "Perubahan belum disimpan sebagai file baru. Tetap keluar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        event.accept() if answer == QMessageBox.Yes else event.ignore()

    # ---------- pembukaan file ----------
    def confirm_discard_changes(self):
        if not self.doc or not self.doc.dirty: return True
        answer = QMessageBox.question(
            self, "Perubahan belum disimpan",
            "File memiliki perubahan yang belum disimpan. Buka file lain dan buang perubahan di memori?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return answer == QMessageBox.Yes

    def reset_name_plan(self):
        self.name_table.setRowCount(0)
        self.add_name_row()
        self.name_status.setText("File aktif berubah. Masukkan nama lama dan nama baru, lalu periksa kecocokan.")

    def open_dialog(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Buka file data game (mis. MOTOGP.DAT)", "",
            "File data game (*.DAT *.dat *.BIN *.bin);;Semua file (*)")
        if p: self.load_file(p)
    def load_file(self, path):
        if not self.confirm_discard_changes(): return
        def job(prog):
            if Path(path).stat().st_size > 1 << 30:
                raise MemoryError("File lebih dari 1 GiB belum didukung. Pilih file data hasil ekstrak, bukan ISO penuh.")
            info = FM.open_file(path, prog)
            return info, Path(path).read_bytes()
        def ok(r):
            self.info, data = r; self.doc = HexDocument(data); self.schema = None; self.demo = False
            self.reset_name_plan(); self.string_candidates = []; self.string_table.setRowCount(0)
            self.hexmodel.set_doc(self.doc); self.refresh_all(); self.nav.setCurrentRow(1)
        self.run_bg(job, ok, f"Membuka {path}...")
    def start_demo(self):
        if not self.confirm_discard_changes(): return
        self.info = None; self.doc = HexDocument(DEMO.make_demo_file()); self.schema = DEMO.demo_schema(); self.demo = True
        self.reset_name_plan(); self.string_candidates = []; self.string_table.setRowCount(0)
        self.hexmodel.set_doc(self.doc); self.refresh_all(); self.nav.setCurrentRow(1)

    # ---------- Beranda ----------
    def pg_dashboard(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("MotoGP06 PSP Modding Studio", "h1"))
        l.addWidget(label("Alur cepat: buka file data hasil ekstrak → cari teks → ganti nama → simpan sebagai file baru.\n"
                          "Gunakan salinan game/ISO, bukan satu-satunya file asli.", "muted"))
        self.dash = label(""); self.dash.setObjectName("card"); l.addWidget(self.dash)
        b = QHBoxLayout(); o = QPushButton("Buka file game..."); o.setObjectName("primary"); o.clicked.connect(self.open_dialog)
        d = QPushButton("Coba data demo"); d.clicked.connect(self.start_demo)
        n = QPushButton("Ke Editor Nama"); n.clicked.connect(lambda: self.nav.setCurrentRow(1))
        b.addWidget(o); b.addWidget(d); b.addWidget(n); b.addStretch(); l.addLayout(b); l.addStretch()
        return w
    def refresh_dash(self):
        if self.doc is None:
            self.dash.setText("Belum ada file dibuka.\n\n"
                              "1. Ekstrak file data MotoGP dari salinan game/ISO PSP.\n"
                              "2. Buka file data tersebut, lalu masuk ke Editor Nama.\n"
                              "3. Periksa jumlah kecocokan sebelum menerapkan perubahan.\n"
                              "4. Simpan hasil sebagai file baru dan uji di emulator.\n\n"
                              "Demo hanya untuk mencoba antarmuka; bukan data game asli."); return
        t = []
        if self.demo: t.append("⚠ MODE DEMO — file sintetis, bukan file MotoGP.")
        if self.info:
            i = self.info; t += [f"File aktif : {i.path.name} ({i.size:,} byte)", f"SHA-256   : {i.sha256}"]
            t += [f"Format    : {x.name} (identifikasi belum memetakan struktur game)" for x in i.identifications]
            t += [f"Peringatan: {x}" for x in i.warnings]
        if self.schema:
            try: RP.validate_schema(self.schema, len(self.doc)); v = "batas data valid"
            except Exception as e: v = f"GAGAL: {e}"
            t.append(f"Skema tambahan: {self.schema.name} — {self.schema.count} record; {v}")
        t.append(f"Perubahan belum disimpan: {'ya' if self.doc.dirty else 'tidak'}")
        self.dash.setText("\n".join(t))

    # ---------- Editor nama cepat ----------
    def pg_names(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(label("Editor Nama & Label", "h1"))
        l.addWidget(label(
            "Untuk nama pembalap, tim, motor, atau teks lain yang tersimpan berurutan di file. "
            "Panjang nama baru wajib sama dalam byte; semua kecocokan persis akan diganti.", "muted"))
        self.name_file = label("Belum ada file dibuka.", "card")
        l.addWidget(self.name_file)
        self.name_status = label("Buka file game, lalu tambahkan pasangan nama lama → nama baru.", "muted")
        l.addWidget(self.name_status)

        actions = QHBoxLayout()
        open_btn = QPushButton("Buka file game..."); open_btn.clicked.connect(self.open_dialog)
        save_btn = QPushButton("Simpan sebagai file baru..."); save_btn.setObjectName("primary"); save_btn.clicked.connect(self.do_save_as)
        actions.addWidget(open_btn); actions.addWidget(save_btn); actions.addStretch(); l.addLayout(actions)

        enc_row = QHBoxLayout(); enc_row.addWidget(label("Encoding teks:"))
        self.name_encoding = QComboBox()
        self.name_encoding.addItem("ASCII (standar)", "ascii")
        self.name_encoding.addItem("Windows-1252", "cp1252")
        self.name_encoding.addItem("UTF-16 Little Endian", "utf-16le")
        self.name_encoding.setToolTip("Gunakan ASCII kecuali Anda tahu file memakai encoding lain.")
        enc_row.addWidget(self.name_encoding); enc_row.addStretch()
        l.addLayout(enc_row)

        self.name_table = QTableWidget(0, 5)
        self.name_table.setHorizontalHeaderLabels(["Jenis", "Nama lama di file", "Nama baru", "Byte", "Kecocokan / status"])
        self.name_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.name_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.name_table.setAlternatingRowColors(True)
        self.name_table.verticalHeader().setVisible(False)
        header = self.name_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        l.addWidget(self.name_table, 1)

        controls = QHBoxLayout()
        for text, fn in [
            ("Tambah nama", lambda: self.add_name_row()), ("Hapus baris", self.remove_name_rows),
            ("Periksa kecocokan", self.check_name_plan), ("Terapkan semua", self.apply_name_plan),
            ("Impor CSV...", self.import_name_list), ("Ekspor CSV...", self.export_name_list),
            ("Undo", lambda: self.hex_undo(True)), ("Redo", lambda: self.hex_undo(False)),
        ]:
            button = QPushButton(text)
            if text == "Terapkan semua": button.setObjectName("primary")
            button.clicked.connect(lambda _checked=False, callback=fn: callback()); controls.addWidget(button)
        controls.addStretch(); l.addLayout(controls)

        self.name_help = label(
            "Catatan: editor ini hanya mengubah teks literal yang ditemukan persis. "
            "Jika nama tidak ditemukan, kemungkinan nama terkompresi/terpecah atau tersimpan di aset lain. "
            "File asli tidak ditimpa; selalu uji hasil di emulator menggunakan salinan.", "warn")
        l.addWidget(self.name_help)
        self.name_table.setRowCount(0); self.add_name_row()
        return w

    def add_name_row(self, category="Pembalap", old="", new=""):
        row = self.name_table.rowCount(); self.name_table.insertRow(row)
        kind = QComboBox(); kind.addItems(["Pembalap", "Tim", "Motor", "Lainnya"])
        idx = kind.findText(category)
        if idx >= 0: kind.setCurrentIndex(idx)
        self.name_table.setCellWidget(row, 0, kind)
        for column, value in ((1, old), (2, new), (3, "—"), (4, "Belum diperiksa")):
            item = QTableWidgetItem(str(value))
            if column >= 3: item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.name_table.setItem(row, column, item)
        return row

    def remove_name_rows(self):
        selected = sorted({index.row() for index in self.name_table.selectionModel().selectedRows()}, reverse=True)
        if not selected and self.name_table.currentRow() >= 0: selected = [self.name_table.currentRow()]
        for row in selected: self.name_table.removeRow(row)
        if self.name_table.rowCount() == 0: self.add_name_row()
        self.name_status.setText("Baris dihapus. Klik ‘Periksa kecocokan’ sebelum menerapkan.")

    def _name_encoding(self):
        return self.name_encoding.currentData() or "ascii"

    def _set_name_result(self, row, bytes_text, status):
        for column, text in ((3, bytes_text), (4, status)):
            item = self.name_table.item(row, column)
            if item is None:
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.name_table.setItem(row, column, item)
            item.setText(text)

    def check_name_plan(self):
        if not self.doc:
            self.name_status.setText("Buka file game atau jalankan Demo Mode dahulu.")
            return None

        row_rules = []
        errors = []
        has_input = False
        for row in range(self.name_table.rowCount()):
            old_item, new_item = self.name_table.item(row, 1), self.name_table.item(row, 2)
            old = old_item.text() if old_item else ""
            new = new_item.text() if new_item else ""
            if not old and not new:
                self._set_name_result(row, "—", "Isi nama lama dan baru")
                continue
            has_input = True
            if not old or not new:
                self._set_name_result(row, "—", "Lengkapi kedua nama")
                errors.append(f"Baris {row + 1}: nama lama dan nama baru wajib diisi.")
                continue
            category_widget = self.name_table.cellWidget(row, 0)
            category = category_widget.currentText() if category_widget else "Lainnya"
            rule = TextReplacement(old, new, category, self._name_encoding())
            try:
                single = preview_replacements(self.doc.data, [rule])[0]
            except Exception as exc:
                self._set_name_result(row, "—", str(exc))
                errors.append(f"Baris {row + 1}: {exc}")
                continue
            size = f"{len(single.old_bytes)} → {len(single.new_bytes)} B"
            if single.offsets:
                positions = ", ".join(f"0x{x:X}" for x in single.offsets[:3])
                if len(single.offsets) > 3: positions += ", …"
                status = f"{len(single.offsets)} kecocokan: {positions}"
            else:
                status = "Tidak ditemukan di file aktif"
            self._set_name_result(row, size, status)
            row_rules.append((row, rule, single))
            if not single.offsets:
                errors.append(f"Baris {row + 1}: nama lama '{old}' tidak ditemukan.")

        if not has_input:
            self.name_status.setText("Tambahkan nama lama dan nama baru, lalu periksa kecocokannya.")
            return None
        if not row_rules:
            self.name_status.setText("Ada data yang belum valid. Perbaiki baris bertanda, lalu periksa lagi.")
            return None

        try:
            combined = preview_replacements(self.doc.data, [rule for _row, rule, _preview in row_rules])
        except Exception as exc:
            for row, _rule, _preview in row_rules:
                self._set_name_result(row, "—", "Aturan bertabrakan; lihat pesan di atas")
            errors.append(str(exc))
            combined = []

        if errors:
            summary = errors[0]
            if len(errors) > 1: summary += f" (+{len(errors) - 1} masalah lain; periksa kolom status tiap baris)"
            self.name_status.setText("Belum siap diterapkan: " + summary)
            return None
        total = sum(len(preview.offsets) for preview in combined)
        self.name_status.setText(f"Siap: {len(combined)} aturan akan mengubah {total} lokasi. Periksa offset sebelum menerapkan.")
        return combined

    def apply_name_plan(self):
        previews = self.check_name_plan()
        if not previews: return
        total = sum(len(preview.offsets) for preview in previews)
        summary = "\n".join(
            f"• {preview.replacement.category}: {preview.replacement.old} → {preview.replacement.new} "
            f"({len(preview.offsets)} lokasi)" for preview in previews
        )
        choice = QMessageBox.question(
            self, "Konfirmasi penggantian",
            f"Ganti seluruh {total} kecocokan berikut?\n\n{summary}\n\n"
            "Perubahan bisa di-Undo. File asli belum disimpan/ditimpa.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if choice != QMessageBox.Yes: return
        try:
            count = apply_replacements(self.doc, [preview.replacement for preview in previews])
            self.refresh_all()
            self.name_status.setText(
                f"Berhasil: {count} lokasi diubah dalam satu langkah Undo. "
                "Klik ‘Simpan sebagai file baru’ untuk membuat salinan mod."
            )
        except Exception as exc:
            self.err(f"Penggantian dibatalkan; tidak ada perubahan parsial.\n{exc}")

    def import_name_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Impor daftar perubahan nama", "", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source)
                required = {"kategori", "nama_lama", "nama_baru"}
                if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                    raise ValueError("Kolom CSV wajib: kategori,nama_lama,nama_baru")
                rows = list(reader)
            self.name_table.setRowCount(0)
            for record in rows:
                self.add_name_row(record.get("kategori") or "Lainnya", record.get("nama_lama") or "", record.get("nama_baru") or "")
            if not rows: self.add_name_row()
            self.name_status.setText(f"Daftar dimuat: {len(rows)} baris. Pilih encoding lalu periksa kecocokan.")
        except Exception as exc:
            self.err(f"CSV tidak dapat dimuat: {exc}")

    def export_name_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Ekspor daftar perubahan nama", "daftar_nama.csv", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as target:
                writer = csv.writer(target)
                writer.writerow(["kategori", "nama_lama", "nama_baru"])
                for row in range(self.name_table.rowCount()):
                    category = self.name_table.cellWidget(row, 0)
                    old = self.name_table.item(row, 1)
                    new = self.name_table.item(row, 2)
                    if old and new and (old.text() or new.text()):
                        writer.writerow([category.currentText() if category else "Lainnya", old.text(), new.text()])
            self.name_status.setText(f"Daftar disimpan: {path}")
        except Exception as exc:
            self.err(f"CSV tidak dapat disimpan: {exc}")

    # ---------- Penjelajah Teks ----------
    def pg_text_browser(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(label("Penjelajah Teks", "h1"))
        l.addWidget(label(
            "Pindai potongan ASCII tercetak yang mungkin berisi nama rider, tim, atau motor. "
            "Hasil ini hanya petunjuk; teks di dalam kompresi bisa terpotong atau tidak terbaca.", "warn"))
        bar = QHBoxLayout(); self.string_filter = QLineEdit()
        self.string_filter.setPlaceholderText("Filter hasil, mis. Rossi, Yamaha, YZR...")
        self.string_filter.textChanged.connect(self.filter_strings)
        self.string_scan_btn = QPushButton("Pindai file aktif"); self.string_scan_btn.setObjectName("primary")
        self.string_scan_btn.clicked.connect(self.do_scan_strings)
        bar.addWidget(self.string_filter, 1); bar.addWidget(self.string_scan_btn); l.addLayout(bar)
        self.string_info = label("Belum dipindai. Klik dua kali pada sebuah teks untuk menyalinnya ke Editor Nama.", "muted")
        l.addWidget(self.string_info)
        self.string_table = QTableWidget(0, 2); self.string_table.setHorizontalHeaderLabels(["Offset", "Teks ASCII"])
        self.string_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.string_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.string_table.verticalHeader().setVisible(False)
        self.string_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.string_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.string_table.cellDoubleClicked.connect(self.use_string_candidate)
        l.addWidget(self.string_table, 1)
        return w

    def do_scan_strings(self):
        if not self.need_doc(): return
        data = bytes(self.doc.data)
        def job(progress):
            progress(5)
            result = scan_ascii_strings(data, min_length=3, limit=20_000)
            progress(100)
            return result
        def done(result):
            self.string_candidates, truncated = result
            self.string_table.setRowCount(len(self.string_candidates))
            for row, candidate in enumerate(self.string_candidates):
                self.string_table.setItem(row, 0, QTableWidgetItem(f"0x{candidate.offset:X}"))
                self.string_table.setItem(row, 1, QTableWidgetItem(candidate.text))
            suffix = " (daftar dibatasi 20.000 hasil; gunakan filter)" if truncated else ""
            self.string_info.setText(f"Ditemukan {len(self.string_candidates):,} potongan teks ASCII.{suffix} "
                                     "Klik dua kali untuk mengisi nama lama di Editor Nama.")
            self.filter_strings()
        self.run_bg(job, done, "Memindai teks yang terbaca...")

    def filter_strings(self, _text=None):
        query = self.string_filter.text().casefold()
        for row in range(self.string_table.rowCount()):
            item = self.string_table.item(row, 1)
            self.string_table.setRowHidden(row, bool(query) and (item is None or query not in item.text().casefold()))

    def use_string_candidate(self, row, _column):
        item = self.string_table.item(row, 1)
        if item is None: return
        self.nav.setCurrentRow(1)
        target = self.name_table.currentRow()
        old_item = self.name_table.item(target, 1) if target >= 0 else None
        if target < 0 or (old_item and old_item.text()): target = self.add_name_row()
        self.name_table.item(target, 1).setText(item.text())
        self.name_table.setCurrentCell(target, 1)
        self.name_status.setText(f"Nama lama diisi dari potongan teks pada {self.string_table.item(row, 0).text()}. Isi nama baru, lalu periksa.")

    # ---------- File dan backup ----------
    def pg_files(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("File & Backup", "h1"))
        self.finfo = QPlainTextEdit(); self.finfo.setReadOnly(True); l.addWidget(self.finfo)
        b = QHBoxLayout()
        for txt, fn in [("Buka file", self.open_dialog), ("Buat backup", self.do_backup), ("Pulihkan backup...", self.do_restore),
                        ("Simpan sebagai file baru...", self.do_save_as)]:
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
        if self.demo:
            return QMessageBox.information(
                self, "Mode demo", "Data demo bersifat sintetis dan tidak bisa dipakai untuk memodifikasi game. Buka file data game asli terlebih dahulu.")
        base = self.info.path if self.info else Path("demo.dat")
        d, _ = QFileDialog.getSaveFileName(
            self, "Simpan hasil sebagai file BARU",
            str(base.with_name(base.stem + "_mod" + base.suffix)),
            "File data (*.DAT *.dat *.BIN *.bin);;Semua file (*)")
        if not d: return
        if self.info and Path(d).resolve() == self.info.path.resolve():
            return self.err("Menimpa file asli diblokir. Pilih nama lain.")
        if Path(d).exists():
            answer = QMessageBox.question(
                self, "File sudah ada", f"File ini sudah ada:\n{d}\n\nTimpa file tersebut?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes: return
        try:
            if self.info: self.backups.create(self.info.path)
            out = self.doc.export(); atomic_write(d, out)
            diffs = self.doc.changed_ranges()
            QMessageBox.information(self, "Tersimpan", f"File baru: {d}\nRentang berubah: {len(diffs)}\nByte berubah: {sum(x[1] for x in diffs)}\n"
                "Peringatan: berhasil disimpan ≠ kompatibel dengan game. Uji di emulator dengan salinan.")
        except Exception as e: self.err(str(e))

    # ---------- Alat lanjutan (dikelompokkan agar navigasi utama sederhana) ----------
    def pg_advanced(self):
        self.advanced_tabs = QTabWidget()
        for page, title in [
            (self.pg_analyzer(), "Analisis Biner"),
            (self.pg_riders(), "Editor Rider / Skema"),
            (self.pg_bike(), "Model 3D Motor"),
            (self.pg_hex(), "Hex Editor"),
            (self.pg_patch(), "Patch"),
            (self.pg_settings(), "Pengaturan"),
            (self.pg_about(), "Tentang"),
        ]:
            self.advanced_tabs.addTab(page, title)
        return self.advanced_tabs

    # ---------- Binary Analyzer ----------
    def pg_analyzer(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Analisis Biner (Lanjutan)", "h1"))
        l.addWidget(label("Semua hasil adalah kandidat heuristik, bukan fakta. Verifikasi manual sebelum mengedit byte.", "warn"))
        b = QHBoxLayout(); r = QPushButton("Jalankan analisis"); r.setObjectName("primary"); r.clicked.connect(self.do_analyze)
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

    # ---------- Editor tabel dengan skema ----------
    def pg_riders(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Editor Rider Berbasis Skema (Lanjutan)", "h1"))
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
    def filter_riders(self, _text=None):
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

    # ---------- Aset motor ----------
    def pg_bike(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Model 3D Motor", "h1"))
        l.addWidget(label("Belum tersedia. Editor Nama dapat mengganti teks nama motor jika teks itu ditemukan di file data. "
            "Mengganti bentuk/tekstur motor membutuhkan format aset model, material, skeleton, dan referensi yang belum dipetakan. "
            "Jangan mengubah ID model secara acak karena dapat membuat game gagal memuat aset.", "warn"))
        l.addStretch(); return w

    # ---------- Hex ----------
    def pg_hex(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Hex Editor (Lanjutan)", "h1"))
        b = QHBoxLayout(); self.goto = QLineEdit(); self.goto.setPlaceholderText("Offset hex, mis. 1F0"); self.goto.returnPressed.connect(self.do_goto)
        self.smode = QComboBox(); self.smode.addItems(["Byte hex", "Teks ASCII", "Teks UTF-16LE", "Int32 LE", "Int32 BE", "Int16 LE", "Int16 BE"])
        self.sq = QLineEdit(); self.sq.setPlaceholderText("Cari nilai..."); self.sq.returnPressed.connect(self.do_search)
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
        if not self.doc: return
        change = (self.doc.undo if undo else self.doc.redo)()
        self.refresh_all()
        if hasattr(self, "name_status"):
            action = "Undo" if undo else "Redo"
            self.name_status.setText(f"{action} berhasil." if change else f"Tidak ada perubahan untuk {action}.")
    def refresh_hexlog(self):
        self.hexlog.setPlainText("\n".join(f"0x{c.offset:08X}: {c.old.hex(' ')} -> {c.new.hex(' ')}  {c.note}" for c in (self.doc.log[-200:] if self.doc else [])))

    # ---------- Patch ----------
    def pg_patch(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Patch (Lanjutan)", "h1"))
        self.pinfo = label(""); l.addWidget(self.pinfo)
        b = QHBoxLayout()
        for txt, fn in [("Simpan perubahan sebagai patch (.json)...", self.patch_save), ("Terapkan patch ke file...", self.patch_apply), ("Urungkan patch pada file...", self.patch_revert)]:
            x = QPushButton(txt); x.clicked.connect(fn); b.addWidget(x)
        b.addStretch(); l.addLayout(b); l.addStretch(); return w
    def patch_save(self):
        if not self.need_doc(): return
        try: p = Patch.from_document(self.doc)
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
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("Pengaturan", "h1"))
        l.addWidget(label(f"Mode portable: {'aktif' if PORTABLE else 'nonaktif (buat file kosong portable.flag di samping run.py untuk mengaktifkan)'}\n"
                          f"Folder data/log: {DATA_DIR}\nFolder backup: {DATA_DIR / 'backups'}")); l.addStretch(); return w
    def pg_about(self):
        w = QWidget(); l = QVBoxLayout(w); l.addWidget(label("MotoGP06 PSP Modding Studio", "h1"))
        l.addWidget(label("Versi 0.2. Editor Nama mendukung penggantian teks literal dengan panjang byte tetap, "
                          "pemeriksaan semua offset, CSV untuk daftar perubahan, backup, Undo/Redo, dan simpan sebagai file baru. "
                          "Format kompresi kustom MotoGP.DAT serta aset model 3D belum dipetakan; lihat README.md dan docs/FORMAT_NOTES.md.")); l.addStretch(); return w

    def refresh_names_header(self):
        if not self.doc:
            self.name_file.setText("Belum ada file dibuka. Buka file data game atau coba mode demo.")
        elif self.demo:
            self.name_file.setText("MODE DEMO — data sintetis; perubahan tidak akan memodifikasi game.")
        else:
            self.name_file.setText(f"File aktif: {self.info.path.name}  •  {len(self.doc):,} byte  •  panjang file tidak akan berubah")

    def refresh_all(self):
        self.refresh_dash(); self.refresh_files(); self.refresh_names_header(); self.refresh_riders(); self.hexmodel.refresh(); self.refresh_hexlog()
        n = len(self.doc.changed_ranges()) if self.doc else 0
        self.pinfo.setText("Belum ada file." if not self.doc else f"Perubahan saat ini: {n} rentang. Patch menyimpan offset, byte lama/baru, dan hash file sumber.")
        self.setWindowTitle("MotoGP06 PSP Modding Studio" + (" • perubahan belum disimpan" if n else ""))

def main():
    app = QApplication(sys.argv); app.setStyleSheet(QSS)
    w = MainWindow(); w.show(); return app.exec()
