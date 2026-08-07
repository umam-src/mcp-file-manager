# mcp-file-manager

MCP server untuk mengelola file lokal (read/write/list/edit) di server Hermes.

## Tools
- `list_files(path)` — daftar isi direktori
- `read_file(path, limit)` — baca isi file teks
- `write_file(path, content)` — tulis/overwrite file
- `append_file(path, content)` — tambah isi di akhir file
- `edit_file(path, old, new)` — ganti teks dalam file
- `delete_file(path)` — hapus file
- `mkdir(path)` — buat direktori

## Keamanan
Semua akses dibatasi ke `BASE_DIR` (default `/root`). Path traversal keluar
dari base directory ditolak.

## Menjalankan
```bash
pip install -e .
python3 server.py   # stdio MCP server
```

Atau set base dir berbeda:
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
