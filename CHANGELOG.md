# Changelog

Semua perubahan penting dicatat di file ini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/), versi mengikuti [SemVer](https://semver.org/).

## [Unreleased]

### Added
- `delete_dir`: parameter opsional `dry_run`; pratinjau hapus rekursif tanpa menghapus (`files`, `dirs`, `bytes`, `truncated`; tidak rekursif: `empty`, `would_delete`), kontrak sama dengan Go. `tools/list` 5.192 menjadi 5.291 karakter. Belum diberi nomor versi (G-7, roadmap 0.4.0).

## [0.4.3] - 2026-10-11

### Changed
- Parameter tak dikenal (salah ketik, mis. `recursve`) kini ditolak di server dan operasinya tidak berjalan, sama dengan Go 0.2.7. Sebelumnya diabaikan diam-diam sehingga `delete_dir` dengan `recursve` tetap berjalan tanpa `recursive`. Skema di `tools/list` tidak berubah (tanpa `additionalProperties`, 5.192 karakter); penolakan dilakukan oleh validasi argumen sisi server.

## [0.4.2] - 2026-10-11

### Fixed
- Pasang baru gagal: dependensi `mcp` kini dibatasi `<2` karena `mcp` 2.x menghapus `FastMCP` (`mcp.server.fastmcp`) sehingga server tidak dapat diimpor dan workflow `Tests` gagal di GitHub. Kode tidak berubah; migrasi ke `MCPServer` (mcp 2) dicatat di `TODO.md`.

## [0.4.1] - 2026-10-11

### Changed
- Hemat token tahap 2: field `title` otomatis FastMCP (`"title": "Path"`, `read_fileArguments`, dan sejenisnya) dibuang dari skema input di `tools/list`; `tools/list` turun dari 6.074 menjadi 5.226 karakter (38 field `title` menjadi 0). Nama parameter, tipe, nilai bawaan, `required`, dan hasil tool tidak berubah; nama tampilan tool tetap ada di annotations.

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
- `instructions` server dan annotations pada semua tool; `read_file` dengan `offset` dan `line_ending`; batas hasil baca (100.000 karakter) dan batas tulis (5 MiB, env `MCP_FILE_MAX_WRITE_BYTES`).

### Changed
- Baca streaming; line ending file lama dipertahankan, file baru memakai LF; `old_string` kosong ditolak.

### Fixed
- Di Windows, menulis atau mengedit file LF tidak lagi mengubah semua baris menjadi CRLF; edit multibaris pada file CRLF kini cocok.

## [0.2.1] - 2026-10-09

### Fixed
- Listing rekursif pada folder berat (`.git`, `.venv`, `node_modules`) tidak lagi menghasilkan output raksasa: folder berat dilewati dan hasil dibatasi 1000 entri.

### Added
- CI `tests.yml`: `pytest` di setiap push dan PR (Python 3.10 sampai 3.12).

## [0.2.0] - 2026-08-07

### Fixed
- Import `FastMCP` diperbaiki; `_safe()` memakai `Path.resolve()` (traversal, symlink keluar, dan separator Windows/Linux).

### Added
- `move_file`, `delete_dir`, validasi path, `.env` opsional, logging ke stderr, unit test, dan entry point.

## [0.1.0]

### Added
- Inisialisasi: tool dasar baca, tulis, edit, hapus, dan daftar isi; akses dibatasi ke `BASE_DIR`.
