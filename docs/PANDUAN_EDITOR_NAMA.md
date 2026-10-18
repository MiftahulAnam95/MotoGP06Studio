# Panduan singkat — mengganti nama rider, tim, dan motor

## Alur paling mudah

1. Ekstrak `MOTOGP.DAT` dari salinan game/ISO, kemudian buka file itu di Studio.
2. Buka tab **Cari Teks** → **Pindai file aktif**.
3. Ketik bagian nama pada kotak filter, misalnya `Rossi`, `Yamaha`, atau `YZR`.
4. Klik dua kali teks yang tepat. Studio mengirimkannya ke kolom nama lama di **Editor Nama**.
5. Isi nama baru dengan jumlah **byte yang sama**, klik **Periksa kecocokan**, periksa jumlah dan offset, lalu **Terapkan semua**.
6. Simpan sebagai file baru. Uji file hasil pada salinan game.

## Contoh panjang teks

Contoh berikut hanya untuk menjelaskan aturan panjang; tidak menjamin semua string ada pada setiap versi game:

| Teks lama | Teks baru contoh | Panjang ASCII |
|---|---|---:|
| `Valentino ROSSI` | `Rider Custom 01` | 15 byte |
| `Yamaha Factory Team` | `Garuda Factory Team` | 19 byte |
| `YZR-M1` | `XZR-M2` | 6 byte |

Nama lama harus sama persis—termasuk huruf besar/kecil—dengan teks pada file. Jika nama lama muncul beberapa kali, Studio menampilkan jumlah dan beberapa offset pertama; **Terapkan semua** mengganti seluruh kecocokan untuk aturan tersebut.

## Jika nama tidak ditemukan

- Pastikan file yang dibuka memang file data game, bukan ISO atau arsip.
- Pastikan ejaan, spasi, dan kapitalisasi sama.
- Coba encoding yang sesuai jika teks memakai karakter non-ASCII.
- Jika tetap nol kecocokan, string mungkin terpecah oleh token kompresi kustom atau tersimpan sebagai tekstur/di file lain. Studio tidak mengubahnya secara spekulatif; diperlukan sampel data dan pemetaan format terlebih dahulu.

Jangan menyimpan menimpa `MOTOGP.DAT` asli. Simpan file baru, simpan backup, dan uji satu perubahan terlebih dahulu.
