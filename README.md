# mcp-file-manager

MCP server untuk mengelola file lokal (list/read/write/edit/move/delete) di server Hermes.

## Tools
- `list_files(path=".", recursive=False, pattern="*")` — daftar isi direktori, opsional rekursif & filter glob
- `read_file(path, limit=2000)` — baca isi file teks
- `write_file(path, content)` — tulis/overwrite file (membuat folder induk bila perlu)
- `append_file(path, content)` — tambah isi di akhir file
- `edit_file(path, old, new, count=-1)` — ganti teks dalam file (count=-1 artinya semua kemunculan)
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
penolakan null byte, listing rekursif + pola glob, pindah/rename file, edit file
(termasuk kasus tidak ditemukan), dan hapus direktori (kosong vs rekursif).
```bash
pytest -v
```
