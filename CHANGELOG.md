# Changelog

Semua perubahan penting dicatat di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/), versi mengikuti [SemVer](https://semver.org/).

## [Unreleased]

## [0.3.1] - 2026-10-10

### Changed
- Hemat token: `tools/list` turun dari 5.625 menjadi 4.445 karakter. Deskripsi tool dipangkas dari 2.145 menjadi 1.004 karakter (maksimal dua kalimat per tool) dan disamakan dengan versi Go. Kontrak tool dan bentuk hasil tidak berubah.

## [0.3.0] - 2026-10-09

Optimasi untuk pemakaian di Claude Desktop (Windows).

### Added
- `instructions` server (memuat `BASE_DIR` dan cara pakai tool) dan annotations pada semua tool (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`), agar Claude Desktop membedakan tool baca saja dari tool yang menimpa, menghapus, atau memindah.
- `read_file(path, limit, offset)`: parameter `offset` (0-based) untuk membaca file besar bertahap. Hasil menambah `offset`, `next_offset` (bila masih ada baris), dan `line_ending` (`LF`, `CRLF`, `CR`, `mixed`).
- Batas hasil `read_file` (`MAX_READ_CHARS`, 100.000 karakter) dan batas tulis `MAX_WRITE_BYTES` (default 5 MiB, env `MCP_FILE_MAX_WRITE_BYTES`) untuk `write_file`, `append_file`, dan `edit_file`.

### Changed
- `read_file` membaca streaming (tidak memuat seluruh file ke memori); `total_lines` tetap akurat.
- `write_file`/`append_file`/`edit_file` mempertahankan line ending file yang ada. File baru ditulis dengan LF (sebelumnya di Windows menjadi CRLF); yang butuh CRLF pada file baru perlu menulis `\r\n` sendiri.
- `edit_file` menolak `old_string` kosong.
- Dependensi minimum `mcp` menjadi `>=1.8.0` (annotations tool).

### Fixed
- Di Windows, `write_file`/`append_file`/`edit_file` mengubah semua `\n` menjadi CRLF, sehingga mengedit file LF (mis. repo Git) menimbulkan diff besar. Line ending kini dipertahankan.
- `edit_file` pada file CRLF kini mencocokkan `old_string` multibaris yang ditulis dengan `\n`.
- `write_file`/`append_file`/`edit_file` pada path direktori mengembalikan pesan error yang jelas.

## [0.2.1] - 2026-10-09

### Fixed
- `list_files(recursive=True)` bisa menghasilkan output melebihi batas ukuran hasil tool pada direktori berisi `.git`, `.venv`, `node_modules`, dll., sehingga tool gagal total. Direktori berat kini dilewati (`DEFAULT_EXCLUDE_DIRS`, termasuk entri direktorinya sendiri) dan hasil dibatasi maks 1000 entri (`MAX_RECURSIVE_ENTRIES`), dengan field baru `excluded_dirs` dan `truncated`.

### Added
- CI `tests.yml` (GitHub Actions): `pytest` otomatis di setiap push/PR pada Python 3.10 sampai 3.12.

## [0.2.0] - 2026-08-07

### Fixed
- Import `FastMCP` diperbaiki (`from mcp.server.fastmcp import FastMCP`); sebelumnya memakai kelas yang tidak ada di SDK resmi sehingga server tidak bisa berjalan.
- `_safe()` memakai `pathlib.Path.resolve()` sehingga traversal `..`, symlink escape, dan perbedaan separator Windows/Linux tertangani konsisten.

### Added
- Tool `move_file(src, dst, overwrite)` dan `delete_dir(path, recursive)` (tidak bisa menghapus `BASE_DIR`).
- `list_files`: parameter `recursive` dan `pattern` (glob). `edit_file`: parameter `count`.
- Validasi path: null byte dan path kosong ditolak.
- Dukungan `.env` opsional (`python-dotenv`, `pip install -e ".[dotenv]"`), logging ke stderr, unit test `pytest`, dan entry point `mcp-file-manager = "server:main"`.

## [0.1.0]

### Added
- Inisialisasi project `mcp-file-manager`: tool `list_files`, `read_file`, `write_file`, `append_file`, `edit_file`, `delete_file`, dan `mkdir`.
- Akses dibatasi ke `BASE_DIR` (env `MCP_FILE_BASE`, default `/root`), README, dan `.env.example`.