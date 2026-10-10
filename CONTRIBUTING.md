# Berkontribusi

Terima kasih sudah ingin membantu. Proyek ini kecil dan sengaja dijaga ringan.

## Sebelum mengirim perubahan

Jalankan dari folder ini; semuanya harus lulus:

```
pip install -e ".[dev]"
pytest
```

## Aturan singkat

- Kontrak tool (nama, parameter, bentuk hasil) harus sama dengan versi Go di `../mcp-file-manager-go`. Bila berubah, kedua sisi diubah bersama.
- Semua akses file dari input pemanggil wajib lewat `_safe()` di `server.py` (atau `_safe_leaf()` untuk hapus dan pindah, agar tautan tidak diikuti). Jangan membuka file langsung dari input pemanggil.
- Jangan `print()` ke stdout karena dipakai protokol; log ke stderr.
- Tambah dependensi hanya bila benar-benar perlu. Server harus tetap berjalan penuh tanpa jaringan.
- Setiap perbaikan atau tool baru disertai test, termasuk kasus gagal (di luar `BASE_DIR`, tidak ditemukan, null byte, symlink atau junction keluar).
- Hemat token: deskripsi tool maksimal dua kalimat, hasil tool satu blok JSON ringkas, dan ukuran `tools/list` tidak naik tanpa alasan tertulis.
- Perubahan yang terlihat oleh pemanggil perlu naik versi di `pyproject.toml` dan entri `CHANGELOG.md` dalam satu commit (format [Keep a Changelog](https://keepachangelog.com/), [SemVer](https://semver.org/)). Judul versi bernomor teratas di `CHANGELOG.md` harus sama dengan versi di `pyproject.toml`.
- Jangan memasukkan kredensial, token, atau data pribadi ke kode, catatan, maupun commit.
