# Laporan 02 — Analisis direktori / pointer / container (MOTOGP.DAT)
File: 137.224.192 byte, sha256 `5ff77a24...e9d34` (diverifikasi tidak berubah sesudah eksperimen; file hanya dibuka read-only/memmap).
Reproduksi: `python experiments/directory_analysis.py MOTOGP.DAT > reports/directory_analysis.txt` (butuh numpy). Bukti lengkap per-PNG ada di `reports/directory_analysis.txt`.
Tidak ada dekompresor/kompresor dibuat; Rider Editor dan aplikasi utama tidak diubah. Tes: 19 test lama lolos (tidak ada test baru ditambahkan).

## A. Reproduksibilitas
- Skrip eksperimen 1 dijalankan ulang dari dalam skrip baru: keluaran **identik byte-per-byte** dengan `reports/names_occurrences.txt`. Tidak ada ketidaksesuaian dengan Laporan 01.

## B. Area di sekitar tabel rider (strID)
Fakta:
- 14 kemunculan `strID` (daftar field): 0x933FB, 0x94327, 0x955E8, 0x968A1, 0x97B68, 0x98E2B, 0x9BF0A, 0x9C3CF, 0x9CD25, 0x9D906, 0x9E4E8, 0x9F0CD, 0x9FCAD, 0xA2F21. Jarak: 3884, 4801, 4793, 4807, 4803, 12511, 1221, 2390, 3041, 3042, 3045, 3040, 12916.
- Ada paling sedikit empat jenis tabel (daftar field berbeda): `nCourse/nLap/...` (0x933FB, 0x9C3CF; berisi nama sirkuit, mis. "Jerez"), `nTeam/First/Second/Third/...` (0x9BF0A, 0xA2F21; nama tim: Yamaha Factory, Telefonica Movistar, Repsol, Ducati, Kawasaki Racing...), dan `nEntrant/nTeam/nBike/...` (grup A dan B yang berisi rider).
- 48 byte sebelum `strID` identik pada kelima salinan grup A (`01 C0 22 00 FF 77 E1 EF 00 FF 29 ED 23 01 FF 29 11 C2 20 04 FF F8 6C ED 05 F7 60 00 00 FF F1 60 00 00 FF F2 60 00 00 FF F5 60 00 F9 23 0E FF 70`) dan berbeda pada grup B (`... 00 E5 0B 00 FF 95 60 01 00 FF 1D F8 0B 0E FF 70` untuk 16 byte terakhir). Byte `70` ('p') tepat sebelum "strID" pada semua.
- Dalam 32 byte sebelum tiap `strID`, **tidak ada** nilai u16/u32 (LE atau BE) yang berada dalam ±16 dari jarak ke `strID` berikutnya (kandidat "panjang blok"). Tidak ditemukan field panjang/jumlah entri/ukuran terkompresi di sana.
- Tidak ada u32 (LE/BE) di seluruh file yang bernilai tepat sama dengan offset salah satu `strID` yang bukan kebetulan: LE ada 8 hit, 7 di antaranya = 0x9FCAD pada alamat 0x690589 + k·0x480000 (k=0..6) — pola periodik (jarak tetap 2304 sektor), bukan pointer; 1 hit (nilai 0x56E di 0x79541CD) tidak selaras 4 byte. BE: 0 hit. Status: **ditolak**.
- Penutup blok tidak terlihat sebagai penanda tersendiri: area setelah blok terakhir grup A langsung melanjutkan aliran token (`FF 87 E2 03 03 FF ...`); setelah grup B melanjutkan data tabel lain (`... Season FreeMugell ... Jerez ... Valencia`).
Hasil: **tidak ada bukti** field jumlah entri / ukuran terkompresi / ukuran hasil ekstraksi di dekat tabel rider.

## C. PNG dan sektor (verifikasi chunk-walk + CRC)
- 222 signature PNG; **212 valid penuh** (semua chunk CRC benar, berakhir IEND); 10 palsu (kebetulan byte, mis. 0x199869, 0x1B1094, 0x3B8E863).
- Dimensi: 211 × 480×272 dan 1 × 144×80.
- 211/212 awal PNG selaras 2048; satu tidak selaras: **0x3F50600** (480×272), didahului 32 byte 0xFF.
- Akhir PNG (offset setelah IEND+CRC) **tidak pernah** selaras 2048 (0/212): panjang file PNG bukan kelipatan sektor.
- 209 dari 211 pasangan PNG berurutan: PNG berikutnya tepat di `align_up(akhir, 2048)`; bytes di antaranya nol (tidak ada byte non-nol di celah ≤64 KiB). Dua pengecualian: celah 3318 sektor dan celah 47 sektor.
- Blok kontigu: 210 PNG dari 0x2FDD000 (4542 sektor) + 144×80 di 0x3F37000 + 0x3F50600.
- Ukuran dan posisi tidak memuat angka panjang di depan PNG (8 byte sebelum PNG = nol pada 209/214).
Status:
- "PNG tersimpan sebagai aset yang dipadatkan ke batas sektor": **terverifikasi untuk blok 0x2FDD000** (209/211).
- "Seluruh file adalah arsip berbasis sektor": **tidak didukung**. Tabel rider mulai di sembarang offset sektor (mod 2048 = 807, 1512, 161, 872, 1579 ...), dan aliran token melintasi batas sektor (sektor tepat sebelum PNG pertama berisi token `FF`). Hanya blok PNG yang terbukti dipadatkan sektor.
- Peta sektor: 67.004 sektor = 20 nol, 4.593 mengandung PNG, 62.391 data lain. Run terpanjang non-PNG: 24.506 sektor pertama (0x0), 27.745 sektor dari 0x4CAD800, 6.672 dari 0x3F68000, 3.318 dari 0x38BC000.

## D. Pencarian direktori/indeks (metode independen)
1. **Nilai jangkar** (offset byte dan nomor sektor 211 PNG) dicari sebagai u32/u16 LE/BE di semua fase byte: tidak ada klaster ≥4 hit berdekatan untuk offset byte (LE/BE). Hit LE 398 (>6,7 acak) berasal dari hanya 49 nilai berbeda, didominasi 0x3022000 (114×), tersebar tanpa klaster/urutan: dijelaskan oleh pola 4 byte yang sering muncul pada data, bukan tabel (status **ditolak**).
2. **Nomor sektor** u32 LE: 5 klaster (0x814579C, 0x819AF9C, 0x81F3F9C, 0x824FF9C, 0x82A479C), masing-masing 7 hit. Pasangan (u32 ≈ 26146–26152, float32 ≈ −6,09): blok **identik** diulang lima kali; nilai pertama adalah bilangan bulat kecil yang kebetulan berada di rentang nomor sektor PNG (24506–29048), bukan pointer. Status: **ditolak** (bantahan: pasangan dengan float, nilai berubah ±1–5, blok berulang).
3. **Run u32 menaik ≥8 entri** (semua fase/endian): 12.368 run; 482 deret aritmetika (selisih konstan); terpanjang adalah rampa 0x10001 (data), bukan pointer. Hanya 2 run dengan ≥3 target PNG; keduanya salinan dari satu tabel (lihat E4) dan ditolak sebagai pointer PNG.
4. **Pasangan (offset,panjang)** menaik ≥6 entri: **tidak ada** kandidat.
5. **Perbandingan grup A vs B**: header field identik antar-grup (16 byte pertama sama) tetapi isi dan konteks sebelum header berbeda; tidak ada field penghubung terlihat.

## E. Kandidat terkuat: tabel offset menaik di dalam aliran bertoken (bukan tabel rider)
Bukti: urutan literal u32 LE `80 15 03 00 | A0 1C 03 00 | 30 26 03 00 | 90 2E 03 00 | F0 36 03 00 | E0 3F 03 00` (= 0x31580, 0x31CA0, 0x32630, 0x32E90, 0x336F0, 0x33FE0) ditemukan di **0x52484FA** dan **0x672C886** (konteks 64 byte identik), disusul entri terpotong token (0x34840...) lalu u32 utuh 0x36160, 0x36A50, 0x372B0, 0x37B10, 0x38370, 0x38BD0, 0x394C0, 0x39D20.
- 14 nilai terbaca utuh: menaik, < ukuran file, **semuanya kelipatan 16** (peluang acak 16^-14 = 1,4e-17).
- Target berada di area data berpola bingkai 16 byte dengan byte[1]=0x02 (run ≥512 bingkai, mis. 0x30F00, 0x33AC0, 0x37290). Dugaan: tabel awal sampel suara (cocok dengan skrip "Nus_Prog.xls ... SPU ... BGM" di 0x56E). **Ini kandidat; jenis data belum terbukti** (uji bingkai tidak membedakan target dari posisi 16-byte lain di area itu).
- Tafsir alternatif "nilai × 256 = offset PNG": 3 dari 8 nilai tepat di awal PNG, 5 tidak (head byte acak) → **ditolak**.
- Implikasi penting: **tabel offset ini disimpan di dalam aliran bertoken (`FF` tersisip di antara bytes)**, sehingga pemindaian u32 berurutan seperti D1/D3 secara prinsip gagal mendeteksi tabel yang tertanam dalam aliran terkompresi. Absennya klaster pointer di D bukan bukti bahwa direktori tidak ada.

## F. Tabel status hipotesis
| Hipotesis | Status | Bukti utama | Bantahan/ketidakpastian |
|---|---|---|---|
| Blok PNG 0x2FDD000 dipadatkan sektor, kontigu | Terverifikasi | 209/211 awal = align_up(akhir sebelumnya), padding nol | 2 celah besar, 0x3F50600 tidak selaras |
| Seluruh file arsip sektor | Ditolak/tidak didukung | offset tabel sembarang, token melintasi sektor | — |
| Direktori u32 offset PNG di area datar | Ditolak | 0 klaster, hit didominasi satu nilai | tabel bisa tertanam di aliran bertoken |
| Pointer = nomor sektor 24506–29048 (klaster 0x814579C) | Ditolak | pasangan int+float identik ×5 | — |
| Pasangan (offset,panjang) menaik | Ditolak | 0 kandidat | — |
| Ukuran blok tabel rider tertulis di dekat strID | Ditolak | tidak ada nilai ±16 dari jarak | field bisa di dalam aliran terkompresi |
| Tabel offset suara menaik (0x31580…0x39D20), tertanam di aliran bertoken | Kandidat kuat (sifat tabel), jenis data = hipotesis | 14 nilai kelipatan 16, 2 salinan identik | target belum diparse, jenis data tak terbukti |
| Direktori/indeks global untuk MOTOGP.DAT | **Belum konklusif** | — | mungkin di berkas lain (EBOOT/ISO) atau di dalam aliran terkompresi |

## G. Jawaban tiga pertanyaan
1. **Bukti kuat direktori/pointer blok?** Belum. Satu-satunya struktur pointer-like yang meyakinkan adalah tabel offset menaik kelipatan 16 (E), yang tampak terkait suara dan tertanam di aliran bertoken, bukan direktori blok/rider/PNG. Direktori global belum ditemukan; hasilnya belum konklusif.
2. **Hubungan tabel rider ↔ PNG terbukti?** Tidak. Tidak ada nilai di blok rider yang terbukti menunjuk ke PNG, tidak ada nama berkas (.png dll.; 0 hit) dan satu-satunya kandidat ×256 ditolak. Kolom seperti nTex/nName/nProfile belum dapat ditafsirkan tanpa dekompresi.
3. **Bukti tambahan sebelum melanjutkan RE kompresi?** (a) Berkas lain dari UMD yang sama (EBOOT.BIN, file modul, dan daftar file/ISO) untuk mencari rutin dekompresi dan tabel file; (b) sampel versi lain game/dump ISO tempat MOTOGP.DAT dibaca (untuk melihat siapa membaca offset berapa); (c) idealnya salinan data hasil dekompresi (dump memori emulator saat tabel rider dimuat) sebagai referensi independen; (d) bila tidak ada, lanjut RE murni dengan memakai dua salinan identik (mis. tabel offset di 0x52484FA/0x672C886) dan lima varian bahasa grup A/B sebagai pasangan uji, tetapi tanpa jaminan.

Berhenti di sini; dekompresor tidak dibuat dan menunggu persetujuan.
