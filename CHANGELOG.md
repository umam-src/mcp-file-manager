# Changelog

Semua perubahan penting dicatat di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/), versi mengikuti [SemVer](https://semver.org/).

## [Unreleased]

## [0.4.0] - 2026-10-10

Tool mengikuti nama dan parameter Desktop Commander (khusus file); kontrak identik dengan Go 0.2.0.

### Added
- `read_multiple_files`: baca sampai 20 file sekali panggil; batas karakter dibagi antar file dan file yang gagal memuat `error` tanpa menggagalkan yang lain.
- `get_file_info`: tipe, ukuran, waktu ubah (UTC), dan jumlah baris untuk file teks.
- `start_search`: cari nama file/folder (teks biasa atau wildcard `*` `?`) atau teks di dalam file (`searchType=content`), dibatasi `maxResults` (`truncated`).
- `read_file`: `offset` negatif membaca ekor file.
- `write_file`: parameter `mode` (`rewrite` bawaan atau `append`).

### Changed
- **BREAKING:** `list_files` diganti `list_directory(path, depth)`; hasilnya daftar `[DIR] nama` dan `[FILE] nama` (path relatif dengan `/`), folder berat dicantumkan tetapi tidak dimasuki, dan `truncated` hanya muncul bila hasil terpotong.
- **BREAKING:** `edit_file(path, old_string, new_string, count)` diganti `edit_block(file_path, old_string, new_string, expected_replacements)`. Perubahan dibatalkan dengan `error` bila jumlah kemunculan berbeda dari `expected_replacements` (bawaan 1).
- **BREAKING:** `read_file` memakai `length` (sebelumnya `limit`); `move_file` memakai `source` dan `destination` (sebelumnya `src` dan `dst`); `mkdir` diganti `create_directory`.
- **BREAKING:** Hasil lebih ringkas: `write_file` hanya `path` dan `written`, `move_file` hanya `destination` dan `moved`, tanpa field `ok`.
- `tools/list` kini memuat 11 tool.
- Hasil tool dikirim sebagai satu blok teks JSON ringkas (tanpa indentasi dan tanpa `structuredContent`), isi dan nama field tidak berubah; `list_directory` 510 menjadi 403 karakter dan `get_file_info` 114 menjadi 93 karakter pada contoh uji.
- Dependensi minimum `mcp` naik ke 1.10.0 (parameter `structured_output`).
- CI: workflow Docker dihapus (proyek ini tidak memakai Docker) dan `release.yml` hanya membuat GitHub Release dari `CHANGELOG.md`.

### Removed
- **BREAKING:** `append_file` (pakai `write_file` dengan `mode` `append`).

### Fixed
- `delete_file`, `delete_dir`, dan `move_file` bekerja pada tautan (symlink atau junction) itu sendiri, bukan targetnya. `delete_dir` pada tautan hanya melepas tautan dan hasilnya memuat `link: true`; sebelumnya isi target ikut terhapus.
- `move_file` dengan `overwrite=true`: tujuan dipindah ke cadangan sementara (`.mfm-lama-*`) dan baru dihapus setelah pemindahan berhasil; bila gagal, tujuan dikembalikan. Sebelumnya tujuan dihapus lebih dulu.
- `move_file`: mengganti huruf besar/kecil nama file (mis. `a.txt` menjadi `A.txt`) kini diizinkan di Windows.
- `list_directory` tidak memasuki tautan folder.

### Security
- `start_search` (`searchType=content`) tidak lagi membaca symlink atau junction yang keluar dari `BASE_DIR`.

## [0.3.1] - 2026-10-10

### Changed
- Hemat token: `tools/list` turun dari 5.625 menjadi 4.445 karakter. Deskripsi tool dipangkas menjadi maksimal dua kalimat dan disamakan dengan versi Go. Kontrak tool dan bentuk hasil tidak berubah.

## [0.3.0] - 2026-10-09

Optimasi untuk pemakaian di Claude Desktop (Windows).

### Added
- `instructions` server (memuat `BASE_DIR` dan cara pakai tool) dan annotations pada semua tool (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`, `title`).
- `read_file`: parameter `offset` (0-based) untuk membaca file besar bertahap; hasil menambah `offset`, `next_offset`, dan `line_ending` (`LF`, `CRLF`, `CR`, `mixed`).
- Batas hasil `read_file` (100.000 karakter) dan batas tulis (default 5 MiB, env `MCP_FILE_MAX_WRITE_BYTES`).

### Changed
- `read_file` membaca streaming; `total_lines` tetap akurat.
- Penulisan dan pengeditan mempertahankan line ending file yang ada. File baru ditulis dengan LF (sebelumnya di Windows menjadi CRLF).
- `old_string` kosong ditolak. Dependensi minimum `mcp` menjadi `>=1.8.0`.

### Fixed
- Di Windows, menulis atau mengedit file LF mengubah semua baris menjadi CRLF dan menimbulkan diff besar; kini line ending dipertahankan.
- Edit pada file CRLF kini mencocokkan `old_string` multibaris yang ditulis dengan `\n`.
- Menulis atau mengedit path direktori mengembalikan pesan error yang jelas.

## [0.2.1] - 2026-10-09

### Fixed
- Listing rekursif pada folder berisi `.git`, `.venv`, `node_modules`, dll. menghasilkan output terlalu besar sehingga tool gagal total. Direktori berat kini dilewati dan hasil dibatasi 1000 entri (`truncated`).

### Added
- CI `tests.yml` (GitHub Actions): `pytest` otomatis di setiap push/PR pada Python 3.10 sampai 3.12.

## [0.2.0] - 2026-08-07

### Fixed
- Import `FastMCP` diperbaiki (`from mcp.server.fastmcp import FastMCP`); sebelumnya server tidak bisa berjalan.
- `_safe()` memakai `pathlib.Path.resolve()` sehingga traversal `..`, symlink keluar, dan perbedaan separator Windows/Linux tertangani konsisten.

### Added
- Tool `move_file` dan `delete_dir` (tidak bisa menghapus `BASE_DIR`); listing rekursif dengan filter pola; parameter `count` pada edit.
- Validasi path: null byte dan path kosong ditolak.
- Dukungan `.env` opsional (`python-dotenv`), logging ke stderr, unit test `pytest`, dan entry point `mcp-file-manager = "server:main"`.

## [0.1.0]

### Added
- Inisialisasi project `mcp-file-manager`: tool baca, tulis, tambah, edit, hapus file, daftar isi folder, dan buat folder. Akses dibatasi ke `BASE_DIR` (env `MCP_FILE_BASE`), dengan README dan `.env.example`.
