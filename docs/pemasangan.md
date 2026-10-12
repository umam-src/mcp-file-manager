# Pemasangan

Panduan lengkap memasang `mcp-file-manager` (Python). Butuh Python 3.10 atau lebih baru.

## 1. Siapkan program

```bash
pip install -e .
```

Disarankan memakai lingkungan virtual (`.venv`) di folder proyek supaya paket `mcp` tersedia. Untuk pengembangan dan test: `pip install -e ".[dev]"`; untuk dukungan berkas `.env`: `pip install -e ".[dotenv]"`.

## 2. Pilih folder yang boleh diakses

Isi `MCP_FILE_BASE` dengan satu atau beberapa folder (dipisah `;` di Windows, `:` di Linux). Makin sempit makin aman. Folder harus sudah ada. Bila kosong, bawaannya `/root` (di Windows isi sendiri).

## 3. Daftarkan di Claude Desktop (Windows)

Edit `%APPDATA%\Claude\claude_desktop_config.json`, tambahkan di bawah `mcpServers` (contoh lengkap: `claude_desktop_config.json.example`). Tulis alamat dengan garis miring biasa (`/`).

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

Lalu keluar sepenuhnya dari Claude Desktop (lewat ikon di pojok kanan bawah, bukan hanya menutup jendela) dan buka lagi. Coba minta Claude, "tampilkan isi folder saya".

Uji manual tanpa klien: `MCP_FILE_BASE=/home python3 server.py` (server stdio).

## Bila tidak berjalan

Penyebab paling umum: alamat Python atau `server.py` salah, paket belum terpasang di Python yang dipakai, atau folder di `MCP_FILE_BASE` belum ada. Log Claude Desktop ada di `%APPDATA%\Claude\logs\mcp-server-file-manager.log`.
