# mcp-file-manager

MCP server untuk mengelola file lokal (list/read/write/edit/move/delete).

## Tools
- `list_directory(path=".", depth=2)` - daftar isi folder sampai kedalaman tertentu (folder berat seperti `.git`, `.venv`, `node_modules` dicantumkan tetapi tidak dimasuki; maks 1000 entri)
- `read_file(path, offset=0, length=2000)` - baca file teks per baris; `offset` negatif membaca ekor file; lanjutkan file besar dari `next_offset`. Hasil: `lines`, `offset`, `total_lines`, `truncated`, `line_ending`
- `read_multiple_files(paths)` - baca sampai 20 file sekali panggil
- `write_file(path, content, mode="rewrite")` - tulis ulang (`rewrite`) atau tambah di akhir (`append`); folder induk dibuat bila perlu
- `edit_block(file_path, old_string, new_string, expected_replacements=1)` - ganti teks; gagal bila jumlah kemunculan berbeda dari `expected_replacements`
- `create_directory(path)` - buat folder (rekursif)
- `move_file(source, destination, overwrite=False)` - pindah atau ganti nama file atau folder
- `get_file_info(path)` - tipe, ukuran, waktu ubah (UTC), dan jumlah baris
- `start_search(pattern, path=".", searchType="files", filePattern="", ignoreCase=True, maxResults=100)` - cari nama file/folder (teks biasa atau wildcard `*` `?`) atau teks di dalam file (`searchType="content"`)
- `delete_file(path)` - hapus file
- `delete_dir(path, recursive=False)` - hapus folder; pada symlink atau junction hanya tautannya yang dihapus (hasil memuat `link: true`)

## Keamanan
Semua akses dibatasi ke `BASE_DIR` (default `/root`, diatur via env `MCP_FILE_BASE`).
Path di-resolve dengan `pathlib.Path.resolve()` sebelum divalidasi, sehingga:
- traversal via `..` ditolak,
- symlink dan junction yang mengarah keluar `BASE_DIR` ditolak, dan tautan tidak ditelusuri oleh `list_directory` maupun `start_search`,
- separator Windows (`\`) dan Linux (`/`) ditangani konsisten,
- path yang mengandung null byte ditolak.

## Perilaku untuk Claude Desktop
- **Instructions:** server mengirim petunjuk saat inisialisasi (berisi `BASE_DIR` dan cara pakai tool), jadi model tahu batas akses sejak awal.
- **Annotations:** tiap tool ditandai `readOnlyHint` / `destructiveHint` / `idempotentHint`. `list_directory`, `read_file`, `read_multiple_files`, `get_file_info`, dan `start_search` read-only; `write_file`, `edit_block`, `delete_file`, `delete_dir`, dan `move_file` ditandai destruktif.
- **Hasil dibatasi:** `read_file` maks 100.000 karakter per panggilan (`MAX_READ_CHARS`) dan `list_directory` dan `start_search` maks 1000 entri, supaya hasil tool tidak melebihi batas ukuran di client.
- **Batas tulis:** satu operasi `write_file`/`edit_block` maks 5 MiB; ubah dengan env `MCP_FILE_MAX_WRITE_BYTES`.
- **Line ending dipertahankan:** file yang sudah memakai CRLF tetap CRLF setelah ditulis/diedit, dan file LF tetap LF (tidak diubah menjadi CRLF oleh Windows). File baru ditulis dengan LF. `read_file` selalu mengembalikan `\n` pada `lines` dan melaporkan aslinya di `line_ending`.

## Instalasi & menjalankan
```bash
pip install -e .
python3 server.py   # stdio MCP server
```

Untuk pengembangan (termasuk test):
```bash
pip install -e ".[dev]"
pytest
```

Untuk dukungan file `.env` (opsional):
```bash
pip install -e ".[dotenv]"
```

Atau set base dir berbeda tanpa `.env`:
```bash
MCP_FILE_BASE=/home python3 server.py
```

## Integrasi ke Claude Desktop (Windows)
Edit `%APPDATA%\Claude\claude_desktop_config.json`, tambahkan server di bawah `mcpServers`, lalu tutup Claude Desktop sepenuhnya (termasuk dari system tray) dan buka lagi. Pakai Python dari `.venv` proyek supaya paket `mcp` tersedia. Contoh lengkap ada di `claude_desktop_config.json.example`.
```json
{
  "mcpServers": {
    "file-manager": {
      "command": "C:/path/ke/mcp-file-manager/.venv/Scripts/python.exe",
      "args": ["C:/path/ke/mcp-file-manager/server.py"],
      "env": {
        "MCP_FILE_BASE": "C:/path/ke/folder-yang-boleh-diakses"
      }
    }
  }
}
```
Log server ada di `%APPDATA%\Claude\logs\mcp-server-file-manager.log`.

## Integrasi ke Hermes
Tambahkan ke config MCP client sebagai server stdio:
```json
{
  "mcpServers": {
    "file-manager": {
      "command": "python3",
      "args": ["/root/mcp-file-manager/server.py"]
    }
  }
}
```

## Testing
Test unit mencakup: baca dan tulis, penolakan path di luar `BASE_DIR` dan null byte, `list_directory` dan `start_search`, edit dan pindah file, hapus folder, symlink dan junction (termasuk yang keluar `BASE_DIR`), pelestarian line ending CRLF/LF, batas ukuran, serta annotations dan `instructions` server.
```bash
pytest -v
```
