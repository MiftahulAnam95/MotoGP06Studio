# MotoGP06 PSP Modding Studio

Aplikasi desktop Python untuk membantu memodifikasi file data MotoGP 06 PSP dengan aman. Alur utamanya sekarang berfokus pada penggantian nama pembalap, nama tim, nama motor, dan teks lain yang tersimpan sebagai teks literal di dalam file.

## Fitur

- **Editor Nama**: daftar banyak penggantian sekaligus (`nama lama → nama baru`), kategori Pembalap/Tim/Motor/Lainnya, pemeriksaan jumlah kecocokan dan offset, konfirmasi sebelum edit, Undo/Redo sebagai satu tindakan, serta impor/ekspor CSV.
- **Penjelajah Teks**: memindai potongan ASCII yang terbaca dan mengirim pilihan ke Editor Nama dengan klik ganda.
- **Simpan aman**: hasil disimpan sebagai file baru; file sumber tidak ditimpa. Backup, pemulihan, dan patch JSON tersedia.
- **Tools lanjutan**: Hex Editor, Binary Analyzer, dan editor tabel berbasis skema JSON.
- **Mode demo**: data sintetis untuk mencoba alur aplikasi; bukan data game.

## Instalasi Windows 10/11

1. Pasang Python 3.10 atau lebih baru dari [python.org](https://www.python.org/) dan aktifkan opsi **Add Python to PATH**.
2. Buka Command Prompt/PowerShell di folder proyek:

   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Jalankan aplikasi:

   ```bat
   python run.py
   ```

## Cara memakai Editor Nama

1. Ekstrak file data game—biasanya `MOTOGP.DAT`—dari salinan UMD/ISO milik Anda. Buka file data hasil ekstrak, **bukan ISO penuh**.
2. Buka tab **Cari Teks** (judul halaman: Penjelajah Teks), klik **Pindai file aktif**, lalu filter misalnya `Rossi`, `Yamaha`, `Honda`, atau `YZR`. Hasil pemindaian hanya kandidat teks yang terbaca.
3. Klik dua kali teks yang ingin diganti. Aplikasi mengisi kolom **Nama lama di file** di Editor Nama.
4. Isi **Nama baru**, pilih kategori, lalu klik **Periksa kecocokan**. Periksa jumlah kecocokan dan offset—satu teks bisa muncul beberapa kali karena salinan/varian bahasa.
5. Ulangi untuk nama lain. Daftar dapat disimpan/dimuat sebagai CSV (kolom `kategori,nama_lama,nama_baru`) agar mudah disunting di spreadsheet.
6. Klik **Terapkan semua**, konfirmasi, lalu **Simpan sebagai file baru**. Jangan menimpa file sumber. Uji hasil pada salinan game di emulator/PSP.

## Batasan format yang perlu diketahui

Format internal `MOTOGP.DAT` belum sepenuhnya dipetakan. Analisis sampel menunjukkan ada aliran data bertoken/terkompresi kustom; belum tersedia dekompresor dan belum ada skema roster terverifikasi (lihat `docs/FORMAT_NOTES.md`). Karena itu:

- Editor Nama **hanya mengganti urutan byte teks yang ditemukan persis dan berurutan**. Teks yang dipecah oleh token kompresi tidak dapat diubah oleh fitur ini.
- Untuk menjaga offset dan struktur file, nama pengganti harus memiliki **panjang byte yang sama** dengan nama lama. Misalnya perubahan pada `Valentino ROSSI` harus tetap 15 byte pada encoding yang dipilih. Perbedaan jumlah huruf saja belum tentu sama dengan jumlah byte.
- Semua kecocokan persis dari nama lama akan diganti. Selalu periksa jumlah dan offset sebelum menerapkan; istilah umum seperti `Honda` bisa muncul di lebih dari satu konteks.
- Penggantian teks nama tim/motor tidak sama dengan mengganti model 3D atau tekstur. Editor model 3D belum tersedia.
- Berhasil menyimpan file **tidak menjamin** game menerima perubahan. Bila nama tidak ditemukan, jangan memaksa edit byte secara acak—formatnya mungkin terkompresi atau teksnya berada pada file/aset lain.

## Tes

```bash
python -m unittest discover -s tests -t .
```

Tes inti tidak memerlukan PySide6. GUI membutuhkan dependensi di `requirements.txt`.
