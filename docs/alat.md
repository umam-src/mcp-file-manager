# Daftar tool dan konfigurasi

Kontrak sama dengan `mcp-file-manager-go`. Nama dan parameter tool mengikuti Desktop Commander (khusus file) dan berbahasa Inggris; deskripsi dan pesan error berbahasa Indonesia. Parameter bertanda `*` wajib. Path boleh relatif terhadap folder dasar pertama atau absolut selama hasil akhirnya masih di dalam salah satu folder dasar. Kegagalan dikembalikan sebagai `{"error": "..."}`.

## Tool

| Tool | Parameter | Keterangan |
|---|---|---|
| `list_directory` | `path` (`.`), `depth` (2), `exclude`, `max_entries` | Daftar isi folder sampai kedalaman tertentu. `exclude` (daftar nama; persis atau pola `*` `?`) melewati entri sepenuhnya; `max_entries` menurunkan batas server (nilai lebih besar dipotong, kurang dari 1 ditolak). Folder berat (`.git`, `.venv`, `node_modules`, dll.) dicantumkan tetapi tidak dimasuki. Maksimal 1000 entri (`truncated`). Hanya baca. |
| `read_file` | `path*`, `offset` (0), `length` (2000) | Baca per baris. `offset` negatif membaca ekor file. Hasil: `lines`, `offset`, `next_offset` (bila masih ada baris), `total_lines`, `line_ending`, `truncated`. Maksimal 100.000 karakter. Hanya baca. |
| `read_multiple_files` | `paths*` | Baca sampai 20 file sekali panggil. File yang gagal memuat `error` tanpa menggagalkan yang lain. Hanya baca. |
| `write_file` | `path*`, `content*`, `mode` (`rewrite`) | `rewrite` menulis ulang, `append` menambah di akhir; folder induk dibuat bila perlu. Line ending file lama dipertahankan, file baru memakai LF. |
| `edit_block` | `file_path*`, `old_string*`, `new_string*`, `expected_replacements` (1) | Ganti teks; gagal bila jumlah kemunculan berbeda dari `expected_replacements`. |
| `create_directory` | `path*` | Buat folder (rekursif). |
| `move_file` | `source*`, `destination*`, `overwrite` (false) | Pindah atau ganti nama file atau folder. Tautan dipindah sebagai tautan. |
| `get_file_info` | `path*` | Tipe, ukuran, waktu ubah (UTC), dan jumlah baris. Hanya baca. |
| `start_search` | `pattern*`, `path`, `searchType` (`files`), `filePattern`, `ignoreCase` (true), `maxResults` (100) | `files` mencari nama file/folder (teks biasa atau wildcard `*` `?`); `content` mencari teks di dalam file. Tautan tidak ditelusuri. Hanya baca. |
| `delete_file` | `path*` | Hapus file. Pada tautan, yang dihapus tautannya. |
| `delete_dir` | `path*`, `recursive` (false), `dry_run` (false) | Hapus folder; bawaannya hanya bila kosong. Pada symlink atau junction hanya tautannya yang dilepas (`link: true`). Dengan `dry_run=true` tidak ada yang dihapus; hasil rekursif melaporkan `files`, `dirs`, `bytes` (hitungan sebagian bila lebih dari 100.000 entri). |

Annotations: `list_directory`, `read_file`, `read_multiple_files`, `get_file_info`, dan `start_search` bertanda hanya baca; `write_file`, `edit_block`, `move_file`, `delete_file`, dan `delete_dir` bertanda destruktif.

## Konfigurasi (variabel lingkungan)

| Variabel | Bawaan | Keterangan |
|---|---|---|
| `MCP_FILE_CONFIG` | berkas bawaan bila ada | Berkas config JSON (lihat di bawah). Bila kosong dipakai `%APPDATA%\mcp-file-manager\config.json` (Windows) atau `$XDG_CONFIG_HOME`/`~/.config/mcp-file-manager/config.json` (Linux) jika ada. |
| `MCP_FILE_BASE` | wajib bila tanpa config | Folder yang boleh diakses; menjadi cadangan bila berkas config tidak bisa dipakai (semua `rw`). Beberapa folder dipisah `;` (Windows) atau `:` (Linux); path relatif dihitung dari folder pertama. Folder yang bertumpang tindih ditolak saat mulai. Folder jarak jauh (UNC atau mount) boleh sebagai path yang dipasang sistem operasi. |
| `MCP_FILE_MAX_WRITE_BYTES` | 5 MiB | Batas ukuran tulis per operasi `write_file`/`edit_block`. |
| `MCP_FILE_LOG_LEVEL` | `INFO` | Level log ke stderr. |

### Berkas config

Berkas JSON di luar semua folder dasar (ditolak bila berada di dalamnya, agar server tidak bisa mengubah pengaturannya sendiri). Contoh:

```json
{
  "bases": [
    {"path": "C:/Proyek", "mode": "rw"},
    {"path": "//server/share", "mode": "ro"}
  ],
  "max_write_bytes": 5242880,
  "max_read_chars": 100000,
  "max_entries": 1000
}
```

- `mode`: `rw` atau `ro`; bawaan `ro` (aman). Tulis, hapus, dan pindah dari atau ke folder `ro` ditolak dengan pesan galat.
- Batas yang dihilangkan memakai bawaan. Field yang tidak dikenal menolak seluruh berkas. Gunakan garis miring (`//server/share`) agar JSON tidak rusak oleh `\`.
- Dimuat ulang tanpa restart: waktu ubah berkas diperiksa tiap panggilan tool. Berkas rusak atau tidak valid: config valid terakhir tetap dipakai dan peringatan ditulis ke stderr. `instructions` dikirim saat mulai, jadi daftar folder di dalamnya baru berubah setelah restart.
- Bila berkas tidak bisa dipakai saat mulai, `MCP_FILE_BASE` menjadi cadangan (semua `rw`) dan berkas tetap dipantau.

Dukungan berkas `.env` bersifat opsional (`pip install -e ".[dotenv]"`); tanpa itu pakai pengaturan client MCP.

## Keamanan path

Path di-resolve (`pathlib.Path.resolve()`) sebelum divalidasi, sehingga: traversal `..` ditolak; symlink dan junction yang mengarah keluar semua folder dasar ditolak dan tidak ditelusuri `list_directory` maupun `start_search`; pemisah Windows (`\`) dan Linux (`/`) ditangani konsisten; path dengan null byte ditolak.

## Perilaku untuk Claude Desktop

- Server mengirim petunjuk saat inisialisasi (folder dasar dan cara pakai tool).
- Hasil dibatasi supaya tidak melebihi batas ukuran client: `read_file` maksimal 100.000 karakter, daftar dan pencarian maksimal 1000 entri.
- Line ending dipertahankan: file CRLF tetap CRLF, file LF tetap LF. `read_file` selalu mengembalikan `\n` pada `lines` dan melaporkan aslinya di `line_ending`.

## Test

```bash
pip install -e ".[dev]"
pytest -v
```

Mencakup baca dan tulis, penolakan path di luar folder dasar dan null byte, pencarian, edit dan pindah, hapus (termasuk `dry_run`), symlink dan junction, line ending CRLF/LF, batas ukuran, serta annotations dan petunjuk server.
