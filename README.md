# MotoGP06 PSP Modding Studio (v0.1, Tahap 1)

## Instalasi (Windows 10/11)
1. Pasang Python 3.10+ dari python.org (centang "Add to PATH").
2. Di folder proyek:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
## Menjalankan
`python run.py`  (Mode portable: buat file kosong `portable.flag` di folder yang sama.)
## Test (tanpa GUI/PySide6)
`python -m unittest discover -s tests -t .`

## Status fitur
| Fitur | Status |
|---|---|
| Buka file, hash, identifikasi signature, drag & drop | Berfungsi (worker thread) |
| Backup/restore (verifikasi hash), simpan sebagai file baru, tulis atomik | Berfungsi |
| Binary Analyzer: string, tabel pointer, stride, entropi, bandingkan | Berfungsi (hasil = kandidat) |
| Hex Editor: edit panjang-tetap, undo/redo, cari byte/string/int, change log | Berfungsi |
| Rider Editor | Berfungsi berbasis skema JSON terverifikasi / Demo Mode; TIDAK ada skema MotoGP.DAT asli |
| Patch Manager (hash sumber, verifikasi byte, rollback) | Berfungsi |
| Bike Model Editor, preview 3D | BELUM (butuh sampel + analisis format) |

## Batasan
- GUI ditulis tapi belum diuji menjalankan di lingkungan pengembangan (PySide6 tidak tersedia); logika inti diuji 19 unit test.
- File dimuat penuh ke RAM (batas 1 GiB). Edit hanya panjang-tetap; nama lebih panjang dari field ditolak.
- Format MotoGP.DAT belum dipetakan (lihat docs/FORMAT_NOTES.md). Berhasil disimpan ≠ kompatibel dengan game.
