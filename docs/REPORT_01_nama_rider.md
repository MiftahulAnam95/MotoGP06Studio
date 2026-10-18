# Laporan 01 — Analisis kemunculan nama rider (MOTOGP.DAT, sha256 5ff77a24...e9d34)
Sumber bukti: `reports/names_occurrences.txt` (dibuat ulang oleh `experiments/names_occurrences.py`).

## A. Audit proyek
- 543 baris kode inti, 19 unit test lolos. Tidak ada dekompresor; `compression_handler.py` hanya zlib standar (tidak cocok untuk file ini).
- Tidak ada hasil ekstraksi/sampel lain. Sampel: `MOTOGP.DAT` (dan arsip 7z yang sama).

## B. Fakta terverifikasi (bukti byte)
1. "Valentino ROSSI" dan "Nicky HAYDEN" masing-masing 10x. "Colin EDWARDS", "Max BIAGGI", "Loris CAPIROSSI" 0x sebagai string utuh:
   nama tersebut terpotong token (mis. `Co` `60 18 29 FF` ` EDWARDS`; `Loris CAPI` `C3 10 15 FF` `DUC`).
2. Sepuluh kemunculan terbagi DUA kelompok isi 5:
   - Grup A: 0x94432, 0x956F3, 0x969AC, 0x97C73, 0x98F36 (jarak 4801, 4793, 4807, 4803).
   - Grup B: 0x9CE30, 0x9DA11, 0x9E5F3, 0x9F1D8, 0x9FDB8 (jarak 3041, 3042, 3045, 3040). Jarak A→B: 16122.
3. Grup A dan B BUKAN tabel identik: setelah nama, A berisi `GAU`, B berisi `CAM06`; B memuat rider yang tidak ada di A
   (`Dani PED..`, `Casey STONER`, `y DE PUNIET`, `VERMEUL..`); `Honda` tidak ditemukan setelah nama pada grup B (ada pada A, +743).
   24 byte sebelum nama identik di semua 10 kemunculan kecuali satu byte: `...28 2B 21 FF` (A) vs `...28 2B 23 FF` (B).
4. Dalam satu grup, kelima salinan nyaris identik (kemiripan 0,983 pada blok 0x400 byte). Perbedaan hanya pada singkatan negara:
   `USA`/`E-U`/`E.E.U.U`, `SPA`/`ESP`, `JPN`/`JAP`, `GER`/`ALL`/`ALE`/`DEU`, `BRA`/`BRE`.
5. Byte sebelum nama identik antar-salinan sepanjang 316 byte (dalam grup), bahkan 1765/1332/2428 byte untuk pasangan tertentu:
   penyandian teks sama tidak bergantung pada posisinya dalam file.
6. Header daftar field (`strID`, `nEntrant`...) ada di 0x94327, 0x955E8, 0x968A1, 0x97B68, 0x98E2B (grup A) dan 0x9CD25, 0x9D906, 0x9E4E8, 0x9F0CD, 0x9FCAD (grup B):
   tiap salinan diawali header field ±267 byte sebelum nama pertama. Offset ini TIDAK selaras sektor 2048.
7. Nama disimpan sebagai literal ASCII (bukan terenkripsi), tetapi aliran data bukan teks utuh: tersisip urutan berpenutup `FF`.

## C. Hipotesis (BELUM terbukti)
- H1: lima salinan per grup = varian bahasa (singkatan negara berbeda). Belum ada bukti hubungan dengan pengaturan bahasa game.
- H2: Grup A dan B = dua musim/rooster berbeda (B memuat `CAM06`, rider baru). Hanya dugaan dari isi teks.
- H3: urutan `xx yy zz FF` menggantikan substring berulang (panjang pengganti terinferensi 3, 6, 3 byte dari nama yang dikenal:
  `lin`, `ROSSI\0`, ` BA`). Ini inferensi dari teks, bukan hasil dekode; arti byte `yy zz` (jarak? indeks kamus?) belum diketahui.
- H4: kompresi per-blok tanpa referensi lintas-salinan (butir B5 konsisten dengan ini, tidak membuktikannya).

## D. Belum diketahui
Aturan token, arti byte `FF`, batas blok sebenarnya, direktori/pointer ke blok, checksum, hubungan nBike/nHelmetModel dengan aset.

## E. Rencana (belum dikerjakan)
Langkah 3: cari direktori blok dengan menguji integer di sekitar 0x933FB–0x9FDB8 dan area sebelum PNG pertama; Langkah 4 menunggu hasil itu.
