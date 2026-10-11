#!/usr/bin/env python3
"""MCP server untuk mengelola file lokal di server Hermes.

Nama dan parameter tool mengikuti Desktop Commander (khusus file):
  - list_directory(path, depth)                 -> daftar isi folder
  - read_file(path, offset, length)             -> baca file teks per baris
  - read_multiple_files(paths)                  -> baca beberapa file sekaligus
  - write_file(path, content, mode)             -> tulis ulang atau tambah di akhir
  - edit_block(file_path, old_string, new_string, expected_replacements)
  - create_directory(path)                      -> buat folder
  - move_file(source, destination, overwrite)   -> pindah/ganti nama
  - get_file_info(path)                         -> tipe, ukuran, waktu ubah, jumlah baris
  - start_search(pattern, path, searchType, filePattern, ignoreCase, maxResults)
  - delete_file(path)                           -> hapus file
  - delete_dir(path, recursive)                 -> hapus direktori

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

import functools
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
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
# tool tidak melebihi batas ukuran di client. read_multiple_files membagi
# batas yang sama untuk semua file.
MAX_READ_CHARS = 100_000

# Batas ukuran (byte) untuk satu operasi write_file/edit_block, agar tidak
# menulis file raksasa tanpa sengaja.
MAX_WRITE_BYTES = _env_int("MCP_FILE_MAX_WRITE_BYTES", 5 * 1024 * 1024)

# Jumlah file maksimal untuk read_multiple_files.
MAX_READ_FILES = 20

# Batas entri list_directory dan hasil start_search.
MAX_LIST_ENTRIES = 1000
MAX_SEARCH_RESULTS = 1000

# File lebih besar dari ini dilewati pencarian isi; get_file_info tidak
# menghitung baris untuk file yang lebih besar dari MAX_INFO_LINES_BYTES.
MAX_SEARCH_FILE_BYTES = 5 * 1024 * 1024
MAX_INFO_LINES_BYTES = 10 * 1024 * 1024

# Panjang maksimal teks baris pada hasil pencarian isi.
MAX_MATCH_CHARS = 200

# Petunjuk untuk model, dikirim client saat inisialisasi (Claude Desktop
# memasukkannya ke konteks), supaya model tahu batas akses dan cara pakai.
INSTRUCTIONS = (
    f"Server file manager lokal. Semua path relatif terhadap BASE_DIR = {BASE_DIR}. "
    "Path absolut di dalam BASE_DIR juga diterima; path di luarnya ditolak. "
    "Untuk melihat struktur pakai list_directory(depth); folder berat "
    "(.git, .venv, node_modules, dll.) tidak dimasuki. "
    "Untuk file besar pakai read_file dengan length dan offset (lanjutkan dari "
    "next_offset; offset negatif membaca ekor file). Pakai edit_block untuk "
    "perubahan kecil; write_file hanya untuk file baru, tulis ulang penuh, atau "
    "mode append. Line ending file yang sudah ada (CRLF/LF) dipertahankan. "
    "Hapus, timpa, dan pindah tidak bisa dibatalkan."
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


def _strip_titles(node) -> None:
    """Buang field "title" (string) dari skema JSON, langsung pada objeknya."""
    if isinstance(node, dict):
        if isinstance(node.get("title"), str):
            del node["title"]
        for value in node.values():
            _strip_titles(value)
    elif isinstance(node, list):
        for value in node:
            _strip_titles(value)


def _tool(title: str, **hints):
    """Daftarkan fungsi sebagai tool MCP dengan hasil JSON ringkas.

    FastMCP mencetak hasil dict dengan indent=2. Di sini hasilnya dikirim
    sebagai satu blok teks JSON ringkas (tanpa spasi indentasi dan tanpa
    structuredContent), isinya sama. Fungsi aslinya tetap mengembalikan dict
    sehingga dapat dipanggil langsung (mis. dari test).

    Skema input juga dirampingkan: "title" otomatis FastMCP (nama tool dan
    tiap parameter) dibuang karena hanya menambah token di tools/list.
    Nama tampilan tool tetap ada di annotations.
    """
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs) -> str:
            return json.dumps(fn(*args, **kwargs), ensure_ascii=False,
                              separators=(",", ":"))

        mcp.tool(annotations=_ann(title, **hints), structured_output=False)(wrapper)
        try:
            _strip_titles(mcp._tool_manager.get_tool(fn.__name__).parameters)
        except AttributeError:
            # API internal SDK berubah: skema dibiarkan apa adanya (hanya lebih
            # panjang); test_input_schemas_have_no_title_fields akan memberi tahu.
            pass
        return fn

    return deco


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


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# Awalan nama cadangan sementara tujuan yang akan ditimpa move_file; cadangan
# dihapus (atau dikembalikan) sebelum tool selesai.
BACKUP_PREFIX = ".mfm-lama-"


def _is_link(path) -> bool:
    """True bila path sendiri symlink atau junction (tanpa mengikutinya).

    os.readlink membaca symlink dan junction Windows (Python 3.8+) dan gagal
    pada file atau folder biasa, jadi tidak bergantung pada versi Python
    (os.path.isjunction baru ada di 3.12).
    """
    try:
        os.readlink(path)
        return True
    except (OSError, ValueError):
        return False


def _remove_link(path: Path) -> None:
    """Hapus tautan itu sendiri; isi folder targetnya tidak disentuh."""
    if os.name == "nt" and path.is_dir():  # junction atau symlink folder
        os.rmdir(path)
    else:
        os.unlink(path)


def _safe_leaf(path: str) -> tuple[Path, bool]:
    """Seperti _safe, tetapi komponen terakhir yang berupa tautan tidak diikuti.

    Hasilnya (path, is_link). Bila komponen terakhir symlink atau junction,
    path adalah tautan itu sendiri; dipakai delete_file, delete_dir, dan
    move_file agar yang dihapus atau dipindah adalah tautannya, bukan isi
    targetnya. Semua penolakan _safe tetap berlaku, termasuk tautan yang
    mengarah keluar BASE_DIR.
    """
    resolved = _safe(path)
    if resolved == BASE_DIR:
        return resolved, False
    raw = path.rstrip("/\\")
    if raw in (".", "..") or raw.endswith(("/.", "\\.", "/..", "\\..")):
        return resolved, False  # "tautan/." berarti foldernya sendiri
    cand = BASE_DIR / path
    if cand.name in ("", ".", ".."):
        return resolved, False
    link = _safe(str(cand.parent)) / cand.name
    if _is_link(link):
        return link, True
    return resolved, False


def _case_only_target(src: Path, dst: Path, typed: str) -> Path | None:
    """Nama tujuan bila rename hanya mengubah huruf besar/kecil pada file yang sama.

    Di Windows _safe menormalkan huruf ke nama di disk, sehingga a.txt ke
    A.txt tampak sebagai sumber dan tujuan yang sama. Hasilnya path dengan
    huruf seperti yang diketik pemanggil, atau None. Di sistem yang
    membedakan huruf (Linux) A.txt bukan file yang sama, jadi fungsi ini tidak
    aktif dan rename berjalan seperti biasa.
    """
    leaf = Path(typed.rstrip("/\\")).name
    if leaf in ("", ".", "..") or leaf == src.name or leaf.lower() != src.name.lower():
        return None
    if _fold(str(src.parent)) != _fold(str(dst.parent)):
        return None
    cand = src.parent / leaf
    try:
        if os.path.samestat(os.lstat(src), os.lstat(cand)):
            return cand
    except OSError:
        pass
    return None


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


def _fold(name: str) -> str:
    """Urutan nama: huruf besar/kecil disamakan di Windows (nama file tidak membedakannya)."""
    return name.lower() if os.name == "nt" else name


# Direktori besar/tidak relevan yang tidak dimasuki list_directory dan
# start_search, supaya hasil tidak meledak ukurannya (mis. .git punya ribuan
# object file, .venv/node_modules bisa berisi puluhan ribu file paket).
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".egg-info", "dist", "build", ".mypy_cache", ".pytest_cache",
}


def _is_heavy(name: str) -> bool:
    return name in DEFAULT_EXCLUDE_DIRS or name.endswith(".egg-info")


def _walk(root: Path, max_depth: int):
    """Telusuri root secara depth-first dengan urutan nama.

    Menghasilkan (path relatif dengan '/', is_dir, DirEntry). Folder berat dan
    symlink ke folder dicantumkan tetapi tidak dimasuki; folder yang tidak
    terbaca dilewati.
    """
    def rec(directory: str, rel: str, depth: int):
        try:
            with os.scandir(directory) as it:
                entries = sorted(it, key=lambda e: _fold(e.name))
        except OSError:
            return
        for e in entries:
            name = f"{rel}/{e.name}" if rel else e.name
            try:
                is_dir = e.is_dir()
                real_dir = e.is_dir(follow_symlinks=False) and not _is_link(e.path)
            except OSError:
                is_dir = real_dir = False
            yield name, is_dir, e
            if real_dir and depth < max_depth and not _is_heavy(e.name):
                yield from rec(e.path, name, depth + 1)

    yield from rec(str(root), "", 1)


def _wild(pattern: str, text: str) -> bool:
    """Cocokkan text dengan pattern berwildcard: '*' = urutan apa saja, '?' = satu karakter."""
    p = t = 0
    star = -1
    mark = 0
    while t < len(text):
        if p < len(pattern) and (pattern[p] == "?" or pattern[p] == text[t]):
            p += 1
            t += 1
        elif p < len(pattern) and pattern[p] == "*":
            star = p
            mark = t
            p += 1
        elif star != -1:
            p = star + 1
            mark += 1
            t = mark
        else:
            return False
    while p < len(pattern) and pattern[p] == "*":
        p += 1
    return p == len(pattern)


def _name_matches(pattern: str, name: str, ignore_case: bool) -> bool:
    """Nama cocok bila memuat pattern, atau cocok penuh bila pattern memuat '*' atau '?'."""
    if ignore_case:
        pattern, name = pattern.lower(), name.lower()
    if "*" in pattern or "?" in pattern:
        return _wild(pattern, name)
    return pattern in name


def _read_lines(full: Path, offset: int, length: int, max_chars: int) -> dict:
    """Baca baris [offset, offset+length) dari full secara streaming.

    offset negatif membaca |offset| baris terakhir (length diabaikan).
    """
    if offset < 0:
        with full.open("r", encoding="utf-8", errors="replace") as f:
            total = sum(1 for _ in f)
        length = -offset
        offset = max(0, total + offset)

    lines: list[str] = []
    chars = 0
    total = 0
    cut_by_chars = False
    with full.open("r", encoding="utf-8", errors="replace") as f:
        for total, line in enumerate(f, start=1):
            if total <= offset or len(lines) >= length:
                continue  # tetap iterasi agar total_lines akurat
            remaining = max_chars - chars
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
        "lines": lines,
        "offset": offset,
        "total_lines": total,
        "truncated": end < total or cut_by_chars,
        "line_ending": line_ending,
    }
    if end < total:
        result["next_offset"] = end
    return result


def _read_path(path: str, offset: int, length: int, max_chars: int) -> dict:
    """Validasi path lalu baca; kegagalan dikembalikan sebagai {'error': ...}."""
    try:
        if offset >= 0 and length <= 0:
            return {"error": "length harus lebih besar dari 0"}
        full = _safe(path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {path}"}
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}
        return {"path": path, **_read_lines(full, offset, length, max_chars)}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("read_file gagal")
        return {"error": str(e)}


def _count_lines(full: Path) -> int | None:
    """Jumlah baris file teks, atau None bila file tampak biner."""
    with full.open("rb") as f:
        if b"\x00" in f.read(8192):
            return None
    with full.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

@_tool("Daftar folder", read_only=True, idempotent=True)
def list_directory(path: str = ".", depth: int = 2) -> dict:
    """Daftar isi folder sampai kedalaman depth, diberi awalan [DIR] atau [FILE]. Folder berat (.git, .venv, node_modules, dll.) tidak dimasuki dan hasil dibatasi 1000 entri ('truncated')."""
    try:
        if depth < 1:
            return {"error": "depth harus lebih besar dari 0"}
        full = _safe(path)
        if not full.exists():
            return {"error": f"Path tidak ditemukan: {path}"}
        if not full.is_dir():
            return {"error": f"Path bukan direktori: {path}"}

        entries: list[str] = []
        truncated = False
        for name, is_dir, _ in _walk(full, depth):
            if len(entries) >= MAX_LIST_ENTRIES:
                truncated = True
                break
            entries.append(("[DIR] " if is_dir else "[FILE] ") + name)

        result: dict = {"path": path, "entries": entries}
        if truncated:
            result["truncated"] = True
        return result
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("list_directory gagal")
        return {"error": str(e)}


@_tool("Baca file", read_only=True, idempotent=True)
def read_file(path: str, offset: int = 0, length: int = 2000) -> dict:
    """Baca file teks (UTF-8) per baris; offset negatif membaca baris dari akhir file, dan file besar dilanjutkan dari 'next_offset'. Hasil dibatasi karakternya ('truncated'); 'line_ending' melaporkan LF, CRLF, CR, atau mixed."""
    return _read_path(path, offset, length, MAX_READ_CHARS)


@_tool("Baca banyak file", read_only=True, idempotent=True)
def read_multiple_files(paths: list[str]) -> dict:
    """Baca beberapa file (maks 20) sekaligus dengan aturan read_file; batas karakter dibagi untuk semua file. File yang gagal dibaca memuat 'error' tanpa menggagalkan yang lain."""
    if not paths:
        return {"error": "paths tidak boleh kosong"}
    if len(paths) > MAX_READ_FILES:
        return {"error": f"Maksimal {MAX_READ_FILES} file per panggilan"}
    budget = MAX_READ_CHARS
    files = []
    for p in paths:
        if budget <= 0:
            files.append({"path": p, "error": "batas karakter tercapai; baca file ini terpisah"})
            continue
        r = _read_path(p, 0, 2000, budget)
        if "error" in r:
            r = {"path": p, "error": r["error"]}
        else:
            budget -= sum(len(line) for line in r["lines"])
        files.append(r)
    return {"files": files}


@_tool("Tulis file", destructive=True)
def write_file(path: str, content: str, mode: str = "rewrite") -> dict:
    """Tulis seluruh file (mode rewrite, bawaan) atau tambah di akhir (mode append); folder induk dibuat bila perlu. Line ending file lama dipertahankan, file baru memakai LF; ada batas ukuran."""
    try:
        if mode not in ("rewrite", "append"):
            return {"error": "mode harus 'rewrite' atau 'append'"}
        full = _safe(path)
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {path}"}
        data = _convert_eol(content, _detect_eol(full))
        existing = full.stat().st_size if mode == "append" and full.is_file() else 0
        too_big = _size_error(data, existing)
        if too_big:
            return {"error": too_big}
        full.parent.mkdir(parents=True, exist_ok=True)
        with full.open("a" if mode == "append" else "w", encoding="utf-8", newline="") as f:
            f.write(data)
        return {"path": path, "written": len(content)}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("write_file gagal")
        return {"error": str(e)}


@_tool("Edit file", destructive=True)
def edit_block(file_path: str, old_string: str, new_string: str,
               expected_replacements: int = 1) -> dict:
    """Ganti old_string dengan new_string; gagal bila jumlah kemunculannya berbeda dari expected_replacements (bawaan 1). old_string tidak boleh kosong; CRLF dicocokkan otomatis dan line ending dipertahankan."""
    try:
        if not old_string:
            return {"error": "old_string tidak boleh kosong"}
        if expected_replacements < 1:
            return {"error": "expected_replacements harus lebih besar dari 0"}
        full = _safe(file_path)
        if not full.exists():
            return {"error": f"File tidak ditemukan: {file_path}"}
        if full.is_dir():
            return {"error": f"Path adalah direktori, bukan file: {file_path}"}
        with full.open("r", encoding="utf-8", newline="") as f:
            text = f.read()
        crlf = text.count("\r\n")
        eol = "\r\n" if crlf * 2 > text.count("\n") else "\n"
        old = _convert_eol(old_string, eol)
        new = _convert_eol(new_string, eol)
        found = text.count(old)
        if found == 0:
            return {"error": "old_string tidak ditemukan"}
        if found != expected_replacements:
            return {"error": (f"old_string ditemukan {found} kali, bukan {expected_replacements}; "
                              "sesuaikan expected_replacements atau perluas old_string")}
        text = text.replace(old, new)
        too_big = _size_error(text)
        if too_big:
            return {"error": too_big}
        with full.open("w", encoding="utf-8", newline="") as f:
            f.write(text)
        return {"path": file_path, "replacements": found}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("edit_block gagal")
        return {"error": str(e)}


@_tool("Buat direktori", idempotent=True)
def create_directory(path: str) -> dict:
    """Buat folder (rekursif; tidak error bila sudah ada)."""
    try:
        full = _safe(path)
        full.mkdir(parents=True, exist_ok=True)
        return {"path": path, "created": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("create_directory gagal")
        return {"error": str(e)}


@_tool("Pindah/ganti nama", destructive=True)
def move_file(source: str, destination: str, overwrite: bool = False) -> dict:
    """Pindah atau ganti nama file/folder dari source ke destination; overwrite=true menimpa destination."""
    try:
        src, src_link = _safe_leaf(source)
        dst, dst_link = _safe_leaf(destination)
        if not src_link and not src.exists():  # tautan rusak tetap bisa dipindah
            return {"error": f"Sumber tidak ditemukan: {source}"}
        # Ganti huruf besar/kecil nama pada file yang sama (Windows: a.txt ke
        # A.txt): _safe menormalkan huruf ke nama di disk sehingga sumber dan
        # tujuan tampak sama; rename dilakukan ke nama yang diketik.
        cased = _case_only_target(src, dst, destination)
        if cased is not None:
            os.rename(src, cased)
            return {"destination": destination, "moved": True}
        # Penjaga: tanpa ini overwrite=true bisa menghapus sumber sendiri bila
        # tujuan sama dengan, berada di dalam, atau induk dari sumber.
        if dst == src:
            return {"error": f"Sumber dan tujuan sama: {source}"}
        if _is_within(dst, src):
            return {"error": f"Tujuan berada di dalam sumber: {destination}"}
        if _is_within(src, dst):
            return {"error": ("Tujuan adalah folder induk dari sumber, memindahkannya "
                              f"akan menghapus sumber: {destination}")}
        backup = None
        dst_is_dir = dst.is_dir()
        if dst_link or dst.exists():
            if not overwrite:
                return {"error": f"Tujuan sudah ada: {destination} (gunakan overwrite=True untuk menimpa)"}
            # Tujuan yang akan ditimpa dipindah dulu ke cadangan sementara dan
            # baru dihapus setelah pemindahan berhasil; bila gagal, cadangan
            # dikembalikan sehingga tujuan tidak hilang.
            backup = dst.with_name(f"{BACKUP_PREFIX}{time.time_ns():x}")
            os.rename(dst, backup)

        def restore() -> None:
            if backup is None:
                return
            try:
                os.rename(backup, dst)
            except OSError:
                logger.error("gagal mengembalikan tujuan dari cadangan %s", backup)

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except BaseException:
            restore()
            raise
        if backup is not None:
            try:
                if dst_link:  # tautan cukup dilepas, isi targetnya jangan dihapus
                    _remove_link(backup)
                elif dst_is_dir:
                    shutil.rmtree(backup)
                else:
                    os.unlink(backup)
            except OSError:
                logger.error("move berhasil, tetapi cadangan %s gagal dihapus", backup)
        return {"destination": destination, "moved": True}
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("move_file gagal")
        return {"error": str(e)}


@_tool("Info file", read_only=True, idempotent=True)
def get_file_info(path: str) -> dict:
    """Info file atau folder: tipe, ukuran, waktu ubah (UTC), dan jumlah baris untuk file teks."""
    try:
        full = _safe(path)
        if not full.exists():
            return {"error": f"Path tidak ditemukan: {path}"}
        st = full.stat()
        info: dict = {
            "path": path,
            "type": "dir" if full.is_dir() else "file",
            "modified": _iso(st.st_mtime),
        }
        if full.is_file():
            info["size"] = st.st_size
            if st.st_size <= MAX_INFO_LINES_BYTES:
                lines = _count_lines(full)
                if lines is not None:
                    info["lines"] = lines
        return info
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("get_file_info gagal")
        return {"error": str(e)}


@_tool("Cari", read_only=True, idempotent=True)
def start_search(pattern: str, path: str = ".", searchType: str = "files",
                 filePattern: str = "", ignoreCase: bool = True,
                 maxResults: int = 100) -> dict:
    """Cari nama file/folder (searchType=files, bawaan; pattern teks biasa atau wildcard * ?) atau teks di dalam file (searchType=content, teks biasa). Hasil langsung dikembalikan dan dibatasi maxResults ('truncated'); filePattern membatasi nama file pada pencarian isi."""
    try:
        if searchType not in ("files", "content"):
            return {"error": "searchType harus 'files' atau 'content'"}
        if not pattern:
            return {"error": "pattern tidak boleh kosong"}
        if maxResults < 1:
            return {"error": "maxResults harus lebih besar dari 0"}
        limit = min(maxResults, MAX_SEARCH_RESULTS)
        full = _safe(path)
        if not full.exists():
            return {"error": f"Path tidak ditemukan: {path}"}
        if not full.is_dir():
            return {"error": f"Path bukan direktori: {path}"}

        needle = pattern.lower() if ignoreCase else pattern
        matches: list[str] = []
        truncated = False

        def add(item: str) -> bool:
            """Tambah hasil; False bila batas sudah terlampaui."""
            nonlocal truncated
            if len(matches) >= limit:
                truncated = True
                return False
            matches.append(item)
            return True

        for rel, is_dir, entry in _walk(full, 1_000_000):
            if searchType == "files":
                if _name_matches(pattern, entry.name, ignoreCase):
                    if not add(rel + "/" if is_dir else rel):
                        break
                continue
            if is_dir or not entry.is_file():
                continue
            if filePattern and not _name_matches(filePattern, entry.name, ignoreCase):
                continue
            if entry.is_symlink():
                # Tautan file dibaca hanya bila targetnya masih di dalam BASE_DIR.
                try:
                    _safe(entry.path)
                except PathError:
                    continue
            try:
                if entry.stat().st_size > MAX_SEARCH_FILE_BYTES:
                    continue
                data = Path(entry.path).read_bytes()
            except OSError:
                continue
            if b"\x00" in data[:8192]:
                continue
            stop = False
            for number, raw in enumerate(data.split(b"\n"), start=1):
                text = raw.decode("utf-8", errors="replace").rstrip("\r")
                hay = text.lower() if ignoreCase else text
                if needle in hay:
                    if not add(f"{rel}:{number}: {text[:MAX_MATCH_CHARS]}"):
                        stop = True
                        break
            if stop:
                break

        result: dict = {"path": path, "matches": matches}
        if truncated:
            result["truncated"] = True
        return result
    except PathError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("start_search gagal")
        return {"error": str(e)}


@_tool("Hapus file", destructive=True, idempotent=True)
def delete_file(path: str) -> dict:
    """Hapus file (bukan folder)."""
    try:
        full, is_link = _safe_leaf(path)
        if not is_link and not full.exists():  # tautan rusak tetap bisa dihapus
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


@_tool("Hapus direktori", destructive=True, idempotent=True)
def delete_dir(path: str, recursive: bool = False) -> dict:
    """Hapus folder. Bawaannya hanya bila kosong; recursive=true menghapus beserta isinya."""
    try:
        full, is_link = _safe_leaf(path)
        if full == BASE_DIR:
            return {"error": "tidak boleh menghapus BASE_DIR itu sendiri"}
        if not full.exists():
            return {"error": f"Direktori tidak ditemukan: {path}"}
        if not full.is_dir():
            return {"error": "path bukan direktori, gunakan tool delete_file"}
        if is_link:
            # Hanya tautannya yang dihapus; isi folder targetnya tidak disentuh.
            _remove_link(full)
            return {"path": path, "deleted": True, "link": True}
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


def main() -> None:
    logger.info("mcp-file-manager start, BASE_DIR=%s", BASE_DIR)
    mcp.run()


if __name__ == "__main__":
    main()
