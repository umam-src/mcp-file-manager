#!/usr/bin/env python3
"""MCP server untuk mengelola file lokal di server Hermes.

Tools:
  - list_files(path, recursive, pattern) -> daftar isi direktori
  - read_file(path, limit)               -> baca isi file (text)
  - write_file(path, content)            -> tulis/overwrite file
  - append_file(path, content)           -> tambah isi di akhir file
  - edit_file(path, old, new, count)     -> ganti teks dalam file
  - delete_file(path)                    -> hapus file
  - delete_dir(path, recursive)          -> hapus direktori
  - move_file(src, dst, overwrite)       -> pindah/ganti nama file atau direktori
  - mkdir(path)                          -> buat direktori

Semua akses dibatasi ke BASE_DIR (default /root) untuk keamanan.
Path di-resolve dengan pathlib (menangani symlink & separator Windows/Linux)
sebelum divalidasi berada di dalam BASE_DIR.

Jalankan:
  python3 server.py   (stdio MCP)
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv opsional; jika tidak terpasang, lanjut pakai env yang ada.
    pass

from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

# PENTING: MCP stdio memakai stdout untuk protokol JSON-RPC.
# Semua log HARUS ke stderr, jangan pernah print() ke stdout.
logging.basicConfig(
    level=os.environ.get("MCP_FILE_LOG_LEVEL", "INFO"),
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mcp-file-manager")

BASE_DIR = Path(os.environ.get("MCP_FILE_BASE", "/root")).resolve()

mcp = FastMCP("mcp-file-manager")


class PathError(ValueError):
    """Error validasi atau akses path di luar BASE_DIR."""


# --------------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------------

def _validate_raw(path: str) -> None:
    if not path:
        raise PathError("path tidak boleh kosong")
    if "\x00" in path:
        raise PathError("path mengandung null byte")


def _safe(path: str) -> Path:
    """Resolve path relatif terhadap BASE_DIR, tolak akses di luar BASE_DIR.

    Menggunakan Path.resolve() sehingga:
      - separator Windows (\\) dan Linux (/) sama-sama ditangani dengan benar,
      - traversal via '..' diselesaikan sebelum dicek,
      - symlink yang mengarah keluar BASE_DIR ikut tertangkap.
    """
    _validate_raw(path)
    candidate = (BASE_DIR / path).resolve()
    try:
        candidate.relative_to(BASE_DIR)
    except ValueError:
        raise PathError(f"Akses ditolak: '{path}' berada di luar {BASE_DIR}")
    return candidate


def _entry_info(fp: Path, name: str) -> dict:
    return {
        "name": name,
        "type": "dir" if fp.is_dir() else "file",
        "size": fp.stat().st_size if fp.is_file() else 0,
    }


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

# Direktori besar/tidak relevan yang otomatis dilewati saat recursive=True,
# supaya hasil list_files tidak meledak ukurannya (mis. .git punya ribuan
# object file, .venv/node_modules bisa berisi puluhan ribu file paket).
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".egg-info", "dist", "build", ".mypy_cache", ".pytest_cache",
}

# Batas jumlah entri yang dikembalikan untuk recursive=True, agar tidak
# melebihi batas ukuran hasil tool meski exclude di atas tidak cukup.
MAX_RECURSIVE_ENTRIES = 1000


def _is_excluded(fp: Path, root: Path) -> bool:
    return any(part in DEFAULT_EXCLUDE_DIRS or part.endswith(".egg-info")
               for part in fp.relative_to(root).parts[:-1])


@mcp.tool()
def list_files(path: str = ".", recursive: bool = False, pattern: str = "*") -> dict:
    """Daftar isi direktori (file & folder).

    Args:
        path: path relatif terhadap BASE_DIR.
        recursive: jika True, telusuri seluruh subdirektori juga. Direktori
            besar/tidak relevan (.git, .venv, node_modules, __pycache__, dll.)
            otomatis dilewati, dan hasil dibatasi maks MAX_RECURSIVE_ENTRIES
            entri (ditandai lewat field 'truncated').
        pattern: glob pattern untuk memfilter nama (mis. '*.py', '*.txt').
    """
    try:
        full = _safe(path)
        if not full.exists():
            return {"error": f"Path tidak ditemukan: {path}"}
        if not full.is_dir():
            return {"error": f"Path bukan direktori: {path}"}

        iterator = full.rglob(pattern) if recursive else full.glob(pattern)
        entries = []
        truncated = False
        for fp in sorted(iterator):
            if recursive and _is_excluded(fp, full):
                continue
            if recursive and len(entries) >= MAX_RECURSIVE_ENTRIES:
                truncated = True
                break
            name = str(fp.relative_to(full)) if recursive else fp.name
            entries.append(_entry_info(fp, name))

        result = {
            "path": path,
            "entries": entries,
            "count": len(entries),
            "recursive": recursive,
            "pattern": pattern,
        }
        if recursive:
            result["excluded_dirs"] = sorted(DEFAULT_EXCLUDE_DIRS)
            result["truncated"] = truncated
        return result
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("list_files gagal")
        return {"error": str(e)}


@mcp.tool()
def read_file(path: str, limit: int = 2000) -> dict:
    """Baca isi file teks (maks `limit` baris)."""
    try:
        if limit <= 0:
            return {"error": "limit harus lebih besar dari 0"}
        full = _safe(path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {path}"}
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}
        with full.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return {
            "path": path,
            "lines": lines[:limit],
            "total_lines": len(lines),
            "truncated": len(lines) > limit,
        }
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("read_file gagal")
        return {"error": str(e)}


@mcp.tool()
def write_file(path: str, content: str) -> dict:
    """Tulis/overwrite isi file sepenuhnya (membuat direktori induk bila perlu)."""
    try:
        full = _safe(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return {"path": path, "written": len(content), "ok": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("write_file gagal")
        return {"error": str(e)}


@mcp.tool()
def append_file(path: str, content: str) -> dict:
    """Tambah isi di akhir file (membuat file/direktori induk bila belum ada)."""
    try:
        full = _safe(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with full.open("a", encoding="utf-8") as f:
            f.write(content)
        return {"path": path, "appended": len(content), "ok": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("append_file gagal")
        return {"error": str(e)}


@mcp.tool()
def edit_file(path: str, old_string: str, new_string: str, count: int = -1) -> dict:
    """Ganti kemunculan old_string -> new_string dalam file.

    Args:
        count: jumlah maksimum penggantian. -1 (default) berarti semua kemunculan.
    """
    try:
        full = _safe(path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {path}"}
        text = full.read_text(encoding="utf-8")
        if old_string not in text:
            return {"path": path, "ok": False, "error": "old_string tidak ditemukan"}
        available = text.count(old_string)
        replacements = available if count < 0 else min(count, available)
        text = text.replace(old_string, new_string, replacements)
        full.write_text(text, encoding="utf-8")
        return {"path": path, "replacements": replacements, "ok": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("edit_file gagal")
        return {"error": str(e)}


@mcp.tool()
def delete_file(path: str) -> dict:
    """Hapus file (bukan direktori — gunakan delete_dir untuk itu)."""
    try:
        full = _safe(path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {path}"}
        if full.is_dir():
            return {"error": "path adalah direktori, gunakan tool delete_dir"}
        full.unlink()
        return {"path": path, "deleted": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("delete_file gagal")
        return {"error": str(e)}


@mcp.tool()
def delete_dir(path: str, recursive: bool = False) -> dict:
    """Hapus direktori.

    Args:
        recursive: jika False (default), hanya berhasil bila direktori kosong.
                   Jika True, hapus direktori beserta seluruh isinya.
    """
    try:
        full = _safe(path)
        if full == BASE_DIR:
            return {"error": "tidak boleh menghapus BASE_DIR itu sendiri"}
        if not full.exists():
            return {"error": f"Direktori tidak ditemukan: {path}"}
        if not full.is_dir():
            return {"error": "path bukan direktori, gunakan tool delete_file"}
        if recursive:
            shutil.rmtree(full)
        else:
            full.rmdir()  # gagal otomatis jika direktori tidak kosong
        return {"path": path, "deleted": True, "recursive": recursive}
    except OSError as e:
        return {"error": f"Direktori tidak kosong atau gagal dihapus: {e}"}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("delete_dir gagal")
        return {"error": str(e)}


@mcp.tool()
def move_file(src: str, dst: str, overwrite: bool = False) -> dict:
    """Pindah atau ganti nama file/direktori dari src ke dst.

    Args:
        overwrite: jika True, timpa dst jika sudah ada.
    """
    try:
        full_src = _safe(src)
        full_dst = _safe(dst)
        if not full_src.exists():
            return {"error": f"Sumber tidak ditemukan: {src}"}
        if full_dst.exists():
            if not overwrite:
                return {"error": f"Tujuan sudah ada: {dst} (gunakan overwrite=True untuk menimpa)"}
            if full_dst.is_dir():
                shutil.rmtree(full_dst)
            else:
                full_dst.unlink()
        full_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(full_src), str(full_dst))
        return {"src": src, "dst": dst, "moved": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("move_file gagal")
        return {"error": str(e)}


@mcp.tool()
def mkdir(path: str) -> dict:
    """Buat direktori (rekursif, tidak error jika sudah ada)."""
    try:
        full = _safe(path)
        full.mkdir(parents=True, exist_ok=True)
        return {"path": path, "created": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("mkdir gagal")
        return {"error": str(e)}


def main() -> None:
    logger.info("mcp-file-manager start, BASE_DIR=%s", BASE_DIR)
    mcp.run()


if __name__ == "__main__":
    main()
