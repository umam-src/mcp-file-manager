#!/usr/bin/env python3
"""MCP server untuk mengelola file lokal di server Hermes.

Tools:
  - list_files(path, recursive, pattern) -> daftar isi direktori
  - read_file(path, limit, offset)       -> baca isi file (text) per baris
  - write_file(path, content)            -> tulis/overwrite file
  - append_file(path, content)           -> tambah isi di akhir file
  - edit_file(path, old_string, new_string, count) -> ganti teks dalam file
  - delete_file(path)                    -> hapus file
  - delete_dir(path, recursive)          -> hapus direktori
  - move_file(src, dst, overwrite)       -> pindah/ganti nama file atau direktori
  - mkdir(path)                          -> buat direktori

Semua akses dibatasi ke BASE_DIR (default /root) untuk keamanan.
Path di-resolve dengan pathlib (menangani symlink & separator Windows/Linux)
sebelum divalidasi berada di dalam BASE_DIR.

Jalankan:
  python3 server.py   (stdio MCP)

Environment variable:
  MCP_FILE_BASE            direktori dasar yang boleh diakses (default /root)
  MCP_FILE_MAX_WRITE_BYTES batas ukuran tulis per operasi (default 5 MiB)
  MCP_FILE_LOG_LEVEL       level log ke stderr (default INFO)
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
from mcp.types import ToolAnnotations

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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        logger.warning("%s tidak valid, memakai default %s", name, default)
        return default


# Batas karakter isi yang dikembalikan read_file per panggilan, agar hasil
# tool tidak melebihi batas ukuran di client.
MAX_READ_CHARS = 100_000

# Batas ukuran (byte) untuk satu operasi write_file/append_file/edit_file,
# agar tidak menulis file raksasa tanpa sengaja.
MAX_WRITE_BYTES = _env_int("MCP_FILE_MAX_WRITE_BYTES", 5 * 1024 * 1024)

# Petunjuk untuk model, dikirim client saat inisialisasi (Claude Desktop
# memasukkannya ke konteks), supaya model tahu batas akses dan cara pakai.
INSTRUCTIONS = (
    f"Server file manager lokal. Semua path relatif terhadap BASE_DIR = {BASE_DIR}. "
    "Path absolut di dalam BASE_DIR juga diterima; path di luarnya ditolak. "
    "Untuk melihat struktur pakai list_files(recursive=True); direktori berat "
    "(.git, .venv, node_modules, dll.) dilewati otomatis. "
    "Untuk file besar pakai read_file dengan limit dan offset (lanjutkan dari "
    "next_offset). Pakai edit_file untuk perubahan kecil; write_file hanya untuk "
    "file baru atau tulis ulang penuh. Line ending file yang sudah ada (CRLF/LF) "
    "dipertahankan. Hapus, timpa, dan pindah tidak bisa dibatalkan."
)

mcp = FastMCP("mcp-file-manager", instructions=INSTRUCTIONS)


def _ann(title: str, *, read_only: bool = False, destructive: bool = False,
         idempotent: bool = False) -> ToolAnnotations:
    """Annotations tool agar client (mis. Claude Desktop) tahu mana yang aman.

    Tool read-only bisa diizinkan tanpa konfirmasi ketat; tool destruktif
    (timpa/hapus/pindah) ditandai supaya client meminta persetujuan pengguna.
    """
    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=False,
    )


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


def _detect_eol(full: Path) -> str:
    """Line ending file yang sudah ada: CRLF bila mayoritas CRLF, selain itu LF.

    File yang belum ada (atau tanpa baris baru) dianggap LF.
    """
    if not full.is_file():
        return "\n"
    with full.open("rb") as f:
        head = f.read(65536)
    crlf = head.count(b"\r\n")
    lf = head.count(b"\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def _convert_eol(text: str, eol: str) -> str:
    """Ubah '\\n' pada text menjadi CRLF bila file tujuan memakai CRLF.

    Text yang sudah memuat '\\r' dibiarkan apa adanya (pemanggil mengatur sendiri).
    """
    if eol == "\r\n" and "\r" not in text:
        return text.replace("\n", "\r\n")
    return text


def _eol_name(newlines) -> str | None:
    """Terjemahkan TextIOWrapper.newlines menjadi nama line ending."""
    if newlines is None:
        return None
    if isinstance(newlines, tuple):
        return "mixed"
    return {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}.get(newlines)


def _size_error(data: str, existing: int = 0) -> str | None:
    """Pesan error bila ukuran hasil tulis melebihi MAX_WRITE_BYTES, else None."""
    size = existing + len(data.encode("utf-8"))
    if size > MAX_WRITE_BYTES:
        return (f"Ukuran tulis {size} byte melebihi batas {MAX_WRITE_BYTES} byte "
                "(atur MCP_FILE_MAX_WRITE_BYTES bila memang perlu)")
    return None


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
    """True bila fp berada di dalam direktori berat, atau fp sendiri direktori berat."""
    parts = fp.relative_to(root).parts
    dir_parts = parts if fp.is_dir() else parts[:-1]
    return any(part in DEFAULT_EXCLUDE_DIRS or part.endswith(".egg-info")
               for part in dir_parts)


@mcp.tool(annotations=_ann("Daftar file", read_only=True, idempotent=True))
def list_files(path: str = ".", recursive: bool = False, pattern: str = "*") -> dict:
    """Daftar isi folder. recursive=true menelusuri subfolder, melewati folder berat (.git, .venv, node_modules, dll.) dan membatasi entri ('truncated'); pattern memfilter nama (mis. *.py)."""
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


@mcp.tool(annotations=_ann("Baca file", read_only=True, idempotent=True))
def read_file(path: str, limit: int = 2000, offset: int = 0) -> dict:
    """Baca file teks (UTF-8) per baris; lanjutkan file besar dari 'next_offset'. Hasil dibatasi karakternya ('truncated'); 'line_ending' melaporkan LF, CRLF, CR, atau mixed."""
    try:
        if limit <= 0:
            return {"error": "limit harus lebih besar dari 0"}
        if offset < 0:
            return {"error": "offset tidak boleh negatif"}
        full = _safe(path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {path}"}
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}

        lines: list[str] = []
        chars = 0
        total = 0
        cut_by_chars = False
        with full.open("r", encoding="utf-8", errors="replace") as f:
            for total, line in enumerate(f, start=1):
                if total <= offset or len(lines) >= limit:
                    continue  # tetap iterasi agar total_lines akurat
                remaining = MAX_READ_CHARS - chars
                if remaining <= 0:
                    cut_by_chars = True
                    continue
                if len(line) > remaining:
                    line = line[:remaining]
                    cut_by_chars = True
                lines.append(line)
                chars += len(line)
            line_ending = _eol_name(f.newlines)

        end = offset + len(lines)
        result = {
            "path": path,
            "lines": lines,
            "offset": offset,
            "total_lines": total,
            "truncated": end < total or cut_by_chars,
            "line_ending": line_ending,
        }
        if end < total:
            result["next_offset"] = end
        return result
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("read_file gagal")
        return {"error": str(e)}


@mcp.tool(annotations=_ann("Tulis file", destructive=True, idempotent=True))
def write_file(path: str, content: str) -> dict:
    """Tulis atau timpa seluruh file (folder induk dibuat bila perlu). Line ending file lama dipertahankan, file baru memakai LF; ada batas ukuran."""
    try:
        full = _safe(path)
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}
        data = _convert_eol(content, _detect_eol(full))
        too_big = _size_error(data)
        if too_big:
            return {"error": too_big}
        full.parent.mkdir(parents=True, exist_ok=True)
        with full.open("w", encoding="utf-8", newline="") as f:
            f.write(data)
        return {"path": path, "written": len(content), "ok": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("write_file gagal")
        return {"error": str(e)}


@mcp.tool(annotations=_ann("Tambah ke file", destructive=False))
def append_file(path: str, content: str) -> dict:
    """Tambah isi di akhir file (file dan folder induk dibuat bila belum ada). Line ending mengikuti file; ada batas ukuran."""
    try:
        full = _safe(path)
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}
        data = _convert_eol(content, _detect_eol(full))
        existing = full.stat().st_size if full.is_file() else 0
        too_big = _size_error(data, existing)
        if too_big:
            return {"error": too_big}
        full.parent.mkdir(parents=True, exist_ok=True)
        with full.open("a", encoding="utf-8", newline="") as f:
            f.write(data)
        return {"path": path, "appended": len(content), "ok": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("append_file gagal")
        return {"error": str(e)}


@mcp.tool(annotations=_ann("Edit file", destructive=True))
def edit_file(path: str, old_string: str, new_string: str, count: int = -1) -> dict:
    """Ganti old_string dengan new_string (count membatasi jumlah, -1 = semua). old_string tidak boleh kosong; CRLF dicocokkan otomatis dan line ending dipertahankan."""
    try:
        if not old_string:
            return {"error": "old_string tidak boleh kosong"}
        full = _safe(path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {path}"}
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}
        with full.open("r", encoding="utf-8", newline="") as f:
            text = f.read()
        crlf = text.count("\r\n")
        eol = "\r\n" if crlf * 2 > text.count("\n") else "\n"
        old = _convert_eol(old_string, eol)
        new = _convert_eol(new_string, eol)
        available = text.count(old)
        if available == 0:
            return {"path": path, "ok": False, "error": "old_string tidak ditemukan"}
        replacements = available if count < 0 else min(count, available)
        text = text.replace(old, new, replacements)
        too_big = _size_error(text)
        if too_big:
            return {"error": too_big}
        with full.open("w", encoding="utf-8", newline="") as f:
            f.write(text)
        return {"path": path, "replacements": replacements, "ok": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("edit_file gagal")
        return {"error": str(e)}


@mcp.tool(annotations=_ann("Hapus file", destructive=True, idempotent=True))
def delete_file(path: str) -> dict:
    """Hapus file (bukan folder)."""
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


@mcp.tool(annotations=_ann("Hapus direktori", destructive=True, idempotent=True))
def delete_dir(path: str, recursive: bool = False) -> dict:
    """Hapus folder. Bawaannya hanya bila kosong; recursive=true menghapus beserta isinya."""
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


@mcp.tool(annotations=_ann("Pindah/ganti nama", destructive=True))
def move_file(src: str, dst: str, overwrite: bool = False) -> dict:
    """Pindah atau ganti nama file/folder dari src ke dst; overwrite=true menimpa dst."""
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


@mcp.tool(annotations=_ann("Buat direktori", idempotent=True))
def mkdir(path: str) -> dict:
    """Buat folder (rekursif; tidak error bila sudah ada)."""
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
