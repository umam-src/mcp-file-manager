# TODO

- [x] Tambah tool `move_file` / `rename_file`.
- [x] Tambah tool `list_files` opsional: include subdirektori (rekursif).
- [x] Dukungan glob/pola filter pada `list_files`.
- [x] Tambahkan unit test (pytest) untuk path traversal dan roundtrip file.
- [x] Pastikan path handling konsisten di Windows & Linux (pakai `pathlib.resolve()`).
- [x] Validasi nama file/path (tolak karakter ilegal, null byte).
- [x] Optional: dukungan `.env` via `python-dotenv`.
- [x] CI (GitHub Actions) untuk menjalankan `pytest` otomatis di setiap push.

## Masih terbuka
- [ ] Tool `delete_dir` sudah ada — pertimbangkan dry-run/preview sebelum hapus rekursif.
- [ ] Batas ukuran file untuk `write_file`/`append_file` agar tidak menulis file raksasa tanpa sengaja.
