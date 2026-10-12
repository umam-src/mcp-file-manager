# mcp-file-manager

Alat bantu agar asisten AI (misalnya Claude) dapat melihat, membaca, dan mengelola file di **folder yang Anda tentukan**. Tidak memakai internet.

## Yang bisa dilakukan

- Melihat isi folder, mencari file, dan membaca file teks, bahkan yang besar.
- Membuat, mengubah, menambah, memindah, dan menghapus file atau folder.
- Menjaga format baris file tetap sama, sehingga file yang diubah tidak terlihat berubah seluruhnya.

## Aman karena dibatasi

Asisten hanya bisa bekerja di dalam folder yang Anda pilih. Semua upaya keluar dari folder itu ditolak, termasuk lewat jalan pintas folder.

## Pasang di Claude Desktop (Windows)

Ringkasnya empat langkah; panduan lengkapnya ada di [docs/pemasangan.md](docs/pemasangan.md).

1. **Siapkan program.** Butuh Python 3.10 atau lebih baru; paketnya dipasang dari folder ini.
2. **Pilih folder** yang boleh dilihat dan diubah asisten. Makin sempit makin aman, dan folder itu harus sudah ada.
3. **Daftarkan di Claude Desktop** dengan menambahkan isi contoh di [claude_desktop_config.json.example](claude_desktop_config.json.example) ke berkas pengaturan Claude Desktop, lalu ganti alamat di dalamnya.
4. **Mulai ulang Claude Desktop sepenuhnya.** Coba minta Claude, "tampilkan isi folder saya".

## Untuk yang ingin tahu lebih dalam

Daftar perintah, isian, batas, dan pengaturan ada di [docs/alat.md](docs/alat.md). Riwayat perubahan ada di [CHANGELOG.md](CHANGELOG.md), dan cara ikut berkontribusi di [CONTRIBUTING.md](CONTRIBUTING.md). Versi yang berupa satu file `.exe` tanpa Python ada di proyek `mcp-file-manager-go`.

## Lisensi

MIT. Hak cipta 2026 endsho.
