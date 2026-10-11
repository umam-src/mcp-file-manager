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

- [x] Optimasi untuk Claude Desktop (0.3.0): `instructions` server, annotations tool, `read_file` streaming + `offset` + batas karakter, batas ukuran tulis, pelestarian line ending CRLF/LF.

## Masih terbuka
- [x] `delete_dir`: parameter `dry_run` (pratinjau hapus rekursif; belum dirilis, lihat `[Unreleased]` di CHANGELOG).
- [ ] `DEFAULT_EXCLUDE_DIRS`/`MAX_RECURSIVE_ENTRIES` saat ini hardcoded — pertimbangkan jadikan parameter opsional di `list_files` (mis. `exclude`, `max_entries`) supaya caller bisa override sesuai kebutuhan.
- [ ] Pertimbangkan tool tambahan yang sering dibutuhkan client: `search_files` (cari teks di banyak file) dan `get_file_info` (ukuran, waktu ubah).
- [ ] Default `MCP_FILE_BASE` masih `/root` (tidak bermakna di Windows) — pertimbangkan default yang lebih aman, mis. wajib diisi.
- [x] 0.3.1: hemat token tahap 1 (deskripsi tool dipangkas ke maksimal dua kalimat dan disamakan dengan Go): `tools/list` 5.625 menjadi 4.445 karakter, deskripsi tool 2.145 menjadi 1.004.
- [x] 0.4.1: hemat token tahap 2 (field `title` otomatis FastMCP dibuang dari skema input; kontrak tidak berubah): `tools/list` 6.074 menjadi 5.226 karakter, 38 field `title` menjadi 0.
- [ ] `read_file`: dukung membaca ekor file (mis. `offset` negatif) agar file besar tidak perlu dibaca dari awal. Kontrak harus sama dengan Go.

- [ ] Migrasi ke `mcp` 2.x: `FastMCP` diganti `mcp.server.mcpserver.MCPServer` dan API lain berubah; saat ini ditahan dengan `mcp<2` (0.4.2). Uji dulu pada cabang terpisah.
