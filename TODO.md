# TODO

- [x] Tambah tool `move_file` / `rename_file`.
- [x] Tambah tool `list_files` opsional: include subdirektori (rekursif).
- [x] Dukungan glob/pola filter pada `list_files`.
- [x] Tambahkan unit test (pytest) untuk path traversal dan roundtrip file.
- [x] Pastikan path handling konsisten di Windows & Linux (pakai `pathlib.resolve()`).
- [x] Validasi nama file/path (tolak karakter ilegal, null byte).
- [x] Optional: dukungan `.env` via `python-dotenv`.
- [x] CI (GitHub Actions) untuk menjalankan `pytest` otomatis di setiap push.

- [x] `list_files(recursive=True)` exclude direktori berat (`.git`, `.venv`, `node_modules`, dll.) + cap `MAX_RECURSIVE_ENTRIES` agar hasil tidak melebihi batas ukuran tool. Ditemukan langsung saat listing repo nyata (papan-tugas, mcp-file-manager sendiri) — hasil sebelumnya gagal total ("Tool result too large").

## Masih terbuka
- [ ] Tool `delete_dir` sudah ada — pertimbangkan dry-run/preview sebelum hapus rekursif.
- [ ] Batas ukuran file untuk `write_file`/`append_file` agar tidak menulis file raksasa tanpa sengaja.
- [ ] `read_file` memuat seluruh file ke memori (`f.readlines()`) sebelum dipotong ke `limit` — untuk file sangat besar ini boros memori/lambat. Pertimbangkan baca baris secara streaming (mis. `itertools.islice`) supaya berhenti begitu `limit` tercapai.
- [ ] `DEFAULT_EXCLUDE_DIRS`/`MAX_RECURSIVE_ENTRIES` saat ini hardcoded — pertimbangkan jadikan parameter opsional di `list_files` (mis. `exclude`, `max_entries`) supaya caller bisa override sesuai kebutuhan.
