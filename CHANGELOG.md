# Changelog

Semua perubahan penting dicatat di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/), versi mengikuti [SemVer](https://semver.org/).

## [Unreleased]

### Added
- CI `tests.yml` (GitHub Actions) — jalankan `pytest` otomatis di setiap push/PR pada Python 3.10–3.12.

## [0.2.0] - 2026-08-07

### Fixed
- Import `from mcp.server import MCPServer` diganti menjadi `from mcp.server.fastmcp import FastMCP`
  (kelas lama tidak ada di SDK resmi `mcp`, server tidak bisa berjalan sebelumnya).
- `_safe()` kini pakai `pathlib.Path.resolve()` (bukan `os.path.normpath`) sehingga
  traversal `..`, symlink escape, dan perbedaan separator Windows/Linux tertangani konsisten.

### Added
- Tool `move_file(src, dst, overwrite)` — pindah/ganti nama file atau direktori.
- Tool `delete_dir(path, recursive)` — hapus direktori (kosong atau rekursif), tidak bisa hapus BASE_DIR.
- `list_files` kini mendukung `recursive` dan `pattern` (filter glob).
- `edit_file` kini mendukung parameter `count` untuk membatasi jumlah penggantian.
- Validasi path: null byte dan path kosong ditolak sebelum operasi file dijalankan.
- Dukungan `.env` opsional via `python-dotenv` (`pip install -e ".[dotenv]"`).
- Logging ke stderr (bukan stdout, agar tidak merusak protokol stdio MCP).
- Unit test (`pytest`) untuk traversal, null byte, roundtrip, list rekursif, move, edit, delete_dir.
- `main()` sebagai entry point script (`mcp-file-manager = "server:main"`).

## [0.1.0]

### Added
- Inisialisasi project `mcp-file-manager` (v0.1.0).
- Tool `list_files` — daftar isi direktori.
- Tool `read_file` — baca isi file teks.
- Tool `write_file` — tulis/overwrite file.
- Tool `append_file` — tambah isi di akhir file.
- Tool `edit_file` — ganti teks dalam file.
- Tool `delete_file` — hapus file.
- Tool `mkdir` — buat direktori rekursif.
- Pembatasan akses ke `BASE_DIR` via env `MCP_FILE_BASE` (default `/root`).
- README dan `.env.example`.
