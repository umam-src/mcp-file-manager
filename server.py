#!/usr/bin/env python3
"""MCP server untuk mengelola file lokal di server Hermes.

Tools:
  - list_files(path)        -> daftar isi direktori
  - read_file(path, limit)  -> baca isi file (text)
  - write_file(path, content) -> tulis/overwrite file
  - append_file(path, content) -> tambah isi di akhir file
  - edit_file(path, old, new) -> ganti teks dalam file
  - delete_file(path)       -> hapus file
  - mkdir(path)             -> buat direktori

Semua akses dibatasi ke BASE_DIR (default /root) untuk keamanan.

Jalankan:
  python3 server.py   (stdio MCP)
"""
import os
import sys
from mcp.server import MCPServer

BASE_DIR = os.environ.get("MCP_FILE_BASE", "/root")

mcp = MCPServer(name="mcp-file-manager", version="0.1.0")


def _safe(path: str) -> str:
    """Resolve path dalam BASE_DIR, tolak traversal keluar."""
    full = os.path.normpath(os.path.join(BASE_DIR, path))
    if not (full == BASE_DIR or full.startswith(BASE_DIR + os.sep)):
        raise ValueError(f"Akses ditolak: {path} di luar {BASE_DIR}")
    return full


@mcp.tool()
def list_files(path: str = ".") -> dict:
    """Daftar isi direktori (file & folder)."""
    try:
        full = _safe(path)
        entries = []
        for name in sorted(os.listdir(full)):
            fp = os.path.join(full, name)
            entries.append({
                "name": name,
                "type": "dir" if os.path.isdir(fp) else "file",
                "size": os.path.getsize(fp) if os.path.isfile(fp) else 0,
            })
        return {"path": path, "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def read_file(path: str, limit: int = 2000) -> dict:
    """Baca isi file teks (maks limit baris)."""
    try:
        full = _safe(path)
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return {"path": path, "lines": lines[:limit], "total_lines": len(lines), "truncated": len(lines) > limit}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def write_file(path: str, content: str) -> dict:
    """Tulis/overwrite isi file sepenuhnya."""
    try:
        full = _safe(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "written": len(content), "ok": True}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def append_file(path: str, content: str) -> dict:
    """Tambah isi di akhir file."""
    try:
        full = _safe(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "a", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "appended": len(content), "ok": True}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def edit_file(path: str, old_string: str, new_string: str) -> dict:
    """Ganti semua kemunculan old_string -> new_string dalam file."""
    try:
        full = _safe(path)
        with open(full, "r", encoding="utf-8") as f:
            text = f.read()
        if old_string not in text:
            return {"path": path, "ok": False, "error": "old_string tidak ditemukan"}
        count = text.count(old_string)
        text = text.replace(old_string, new_string)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
        return {"path": path, "replacements": count, "ok": True}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def delete_file(path: str) -> dict:
    """Hapus file (bukan direktori)."""
    try:
        full = _safe(path)
        if os.path.isdir(full):
            return {"error": "path adalah direktori, gunakan delete via os tidak didukung"}
        os.remove(full)
        return {"path": path, "deleted": True}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def mkdir(path: str) -> dict:
    """Buat direktori (rekursif)."""
    try:
        full = _safe(path)
        os.makedirs(full, exist_ok=True)
        return {"path": path, "created": True}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    mcp.run()
