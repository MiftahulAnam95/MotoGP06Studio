# Catatan Format MOTOGP.DAT (hasil analisis sampel)

Status: SEBAGIAN TERIDENTIFIKASI. Parser/dekompresor BELUM ada. Semua poin berlabel [FAKTA] atau [HIPOTESIS].

## Fakta terukur
- [FAKTA] Ukuran 137.224.192 byte = 67.004 x 2048 (kelipatan sektor). SHA-256 5ff77a24...e9d34.
- [FAKTA] Tidak ada magic/header: 0x000-0x56D semuanya 0x00; data pertama di 0x56E.
- [FAKTA] 0x56E: `40 FF` lalu teks skrip `//version=1.10 //output time 2006/03/10 ... (Nus_Prog.xls ...` (konfigurasi SPU/suara).
- [FAKTA] Teks di 0x56E-0xA2D terputus oleh urutan seperti `C4 07 05 FF`, `E0 05 08 FF`: teks asli tidak utuh, sebagian byte diganti token.
- [FAKTA] Tabel rider terlihat di 0x94300-0x94C00+: nama field (`strID, nEntrant, nTeam, nBike, nHelmetModel, nMaxSpeed...`) dan isi
  (`Valentino ROSSI`, `Nicky HAYDEN`, `Colin EDWARDS`, `Max BIAGGI`, `Loris CAPIROSSI`, `Honda`, `Yamaha`, `Ducati` ...), juga disisipi token ber-0xFF.
- [KOREKSI] 10 kemunculan = 2 kelompok x 5 varian, bukan 10 salinan identik; lihat docs/REPORT_01_nama_rider.md.
- [FAKTA] "Valentino ROSSI" muncul 10x (0x94432, 0x956F3, 0x969AC, 0x97C73, 0x98F36, 0x9CE30, 0x9DA11, 0x9E5F3, 0x9F1D8, 0x9FDB8): kemungkinan beberapa salinan tabel.
- [FAKTA] 212 PNG valid (480x272 = layar PSP, juga 144x80), 211 di antaranya selaras sektor 2048; contoh 0x2FDD000, 0x2FEA800, 0x3F50600.
- [FAKTA] Byte 0xFF ~7-11% dari data, jarak antar-0xFF 5-40 byte, tersebar rata di seluruh file. Rasio ASCII tercetak ~27-32% per 4 MiB.

## Kesimpulan
- [HIPOTESIS KUAT] Data skrip/tabel disimpan dalam kompresi kustom mirip LZ (literal tetap terbaca, referensi balik ditandai 0xFF + byte parameter). Nama rider TIDAK bisa diganti dengan menimpa byte: panjang, token, dan referensi akan rusak.
- [FAKTA] Bukan zlib/gzip standar. [BELUM DIKETAHUI] aturan token, tabel offset/direktori file, checksum.

## Langkah berikut
1. Rekayasa balik format token: bandingkan salinan teks identik (mis. 10 salinan "Valentino ROSSI") untuk menurunkan aturan (jarak, panjang).
2. Tulis dekompresor, uji round-trip kompresor (hasil kompres ulang harus identik byte-per-byte pada data asli).
3. Cari tabel direktori (offset+ukuran) agar blok bisa diganti tanpa menggeser file; PNG selaras 2048 menunjukkan arsip berbasis sektor.
4. Baru isi `TableSchema` rider dari data hasil dekompresi.

## Pembaruan (Laporan 02)
- Lihat docs/REPORT_02_directory_analysis.md: 212 PNG valid, blok 0x2FDD000 dipadatkan sektor; tidak ada direktori terbukti; tabel offset suara kandidat di 0x52484FA/0x672C886.
