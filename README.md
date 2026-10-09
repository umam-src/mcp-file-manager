# mcp-file-manager

MCP server untuk mengelola file lokal (list/read/write/edit/move/delete).

## Tools
- `list_files(path=".", recursive=False, pattern="*")` — daftar isi direktori, opsional rekursif & filter glob (direktori berat seperti `.git`, `.venv`, `node_modules` dilewati; maks 1000 entri)
- `read_file(path, limit=2000, offset=0)` — baca file teks per baris; lanjutkan file besar dari `next_offset`. Hasil: `lines`, `offset`, `total_lines`, `truncated`, `line_ending`
- `write_file(path, content)` — tulis/overwrite file (membuat folder induk bila perlu)
- `append_file(path, content)` — tambah isi di akhir file
- `edit_file(path, old_string, new_string, count=-1)` — ganti teks dalam file (count=-1 artinya semua kemunculan; `old_string` tidak boleh kosong)
- `delete_file(path)` — hapus file
- `delete_dir(path, recursive=False)` — hapus direktori (recursive=True untuk hapus beserta isinya)
- `move_file(src, dst, overwrite=False)` — pindah/ganti nama file atau direktori
- `mkdir(path)` — buat direktori rekursif

## Keamanan
Semua akses dibatasi ke `BASE_DIR` (default `/root`, diatur via env `MCP_FILE_BASE`).
Path di-resolve dengan `pathlib.Path.resolve()` sebelum divalidasi, sehingga:
- traversal via `..` ditolak,
- symlink yang mengarah keluar `BASE_DIR` ikut tertangkap,
- separator Windows (`\`) dan Linux (`/`) ditangani konsisten,
- path yang mengandung null byte ditolak.

## Perilaku untuk Claude Desktop
- **Instructions:** server mengirim petunjuk saat inisialisasi (berisi `BASE_DIR` dan cara pakai tool), jadi model tahu batas akses sejak awal.
- **Annotations:** tiap tool ditandai `readOnlyHint` / `destructiveHint` / `idempotentHint`. `list_files` dan `read_file` read-only; `write_file`, `edit_file`, `delete_file`, `delete_dir`, dan `move_file` ditandai destruktif.
- **Hasil dibatasi:** `read_file` maks 100.000 karakter per panggilan (`MAX_READ_CHARS`) dan `list_files` rekursif maks 1000 entri, supaya hasil tool tidak melebihi batas ukuran di client.
- **Batas tulis:** satu operasi `write_file`/`append_file`/`edit_file` maks 5 MiB; ubah dengan env `MCP_FILE_MAX_WRITE_BYTES`.
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
Test unit mencakup: roundtrip baca/tulis, penolakan path traversal (relatif & absolut),
penolakan null byte, listing rekursif + pola glob + pengecualian direktori berat, pindah/rename file,
edit file (termasuk kasus tidak ditemukan dan `old_string` kosong), hapus direktori (kosong vs rekursif),
`read_file` dengan `offset`/`limit`/batas karakter, pelestarian line ending CRLF/LF,
batas ukuran tulis, serta annotations dan `instructions` server.
```bash
pytest -v
```
