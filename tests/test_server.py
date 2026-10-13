"""Unit test untuk mcp-file-manager.

Jalankan:
    pip install -e ".[dev]"
    pytest
"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    """Import ulang server.py dengan BASE_DIR diarahkan ke direktori sementara."""
    monkeypatch.setenv("MCP_FILE_BASE", str(tmp_path))
    import server  # noqa: E402
    importlib.reload(server)
    yield server


# --------------------------------------------------------------------------
# Dasar: tulis, baca, keamanan path
# --------------------------------------------------------------------------

def test_write_and_read_roundtrip(srv):
    result = srv.write_file("hello.txt", "halo dunia")
    assert result == {"path": "hello.txt", "written": 10}

    read = srv.read_file("hello.txt")
    assert "".join(read["lines"]) == "halo dunia"
    assert read["total_lines"] == 1


def test_write_file_append_mode(srv):
    srv.write_file("log.txt", "baris1\n")
    result = srv.write_file("log.txt", "baris2\n", mode="append")
    assert "error" not in result
    assert srv.read_file("log.txt")["lines"] == ["baris1\n", "baris2\n"]


def test_write_file_append_creates_missing_file(srv):
    srv.write_file("sub/baru.txt", "x", mode="append")
    assert srv.read_file("sub/baru.txt")["lines"] == ["x"]


def test_write_file_rejects_unknown_mode(srv):
    assert "error" in srv.write_file("a.txt", "x", mode="timpa")


def test_path_traversal_blocked(srv):
    assert "error" in srv.read_file("../secret.txt")


def test_absolute_path_escape_blocked(srv, tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("rahasia")
    assert "error" in srv.read_file(str(outside))


def test_null_byte_rejected(srv):
    assert "error" in srv.read_file("bad\x00name.txt")


# --------------------------------------------------------------------------
# list_directory
# --------------------------------------------------------------------------

def test_list_directory_depth(srv):
    srv.create_directory("sub/dalam")
    srv.write_file("sub/a.py", "print(1)")
    srv.write_file("sub/dalam/b.txt", "text")
    srv.write_file("top.txt", "x")

    d1 = srv.list_directory(".", depth=1)
    assert d1["entries"] == ["[DIR] sub", "[FILE] top.txt"]

    d2 = srv.list_directory(".", depth=2)
    assert d2["entries"] == ["[DIR] sub", "[FILE] sub/a.py", "[DIR] sub/dalam", "[FILE] top.txt"]

    d3 = srv.list_directory(".", depth=3)
    assert "[FILE] sub/dalam/b.txt" in d3["entries"]
    assert "truncated" not in d3


def test_list_directory_does_not_enter_heavy_dirs(srv):
    srv.create_directory(".git")
    srv.write_file(".git/config", "junk")
    srv.create_directory(".venv/lib")
    srv.write_file(".venv/lib/pkg.py", "junk")
    srv.write_file("real.py", "print('ok')")

    entries = srv.list_directory(".", depth=5)["entries"]
    assert "[FILE] real.py" in entries
    assert "[DIR] .git" in entries and "[DIR] .venv" in entries
    assert not any(e.startswith(("[FILE] .git/", "[DIR] .git/", "[DIR] .venv/", "[FILE] .venv/"))
                   for e in entries)


def test_list_directory_caps_entry_count(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_LIST_ENTRIES", 3)
    for i in range(6):
        srv.write_file(f"f{i}.txt", "x")

    result = srv.list_directory(".")
    assert len(result["entries"]) == 3
    assert result["truncated"] is True


def test_list_directory_errors(srv):
    assert "error" in srv.list_directory("tidak-ada")
    srv.write_file("f.txt", "x")
    assert "error" in srv.list_directory("f.txt")
    assert "error" in srv.list_directory(".", depth=0)


# --------------------------------------------------------------------------
# read_file, read_multiple_files
# --------------------------------------------------------------------------

def test_read_file_offset_and_length(srv):
    srv.write_file("n.txt", "".join(f"baris{i}\n" for i in range(10)))
    r = srv.read_file("n.txt", offset=2, length=3)
    assert r["lines"] == ["baris2\n", "baris3\n", "baris4\n"]
    assert r["offset"] == 2
    assert r["total_lines"] == 10
    assert r["truncated"] is True
    assert r["next_offset"] == 5

    last = srv.read_file("n.txt", offset=r["next_offset"], length=100)
    assert last["lines"][0] == "baris5\n"
    assert last["truncated"] is False
    assert "next_offset" not in last


def test_read_file_negative_offset_reads_tail(srv):
    srv.write_file("n.txt", "".join(f"baris{i}\n" for i in range(10)))
    r = srv.read_file("n.txt", offset=-3)
    assert r["lines"] == ["baris7\n", "baris8\n", "baris9\n"]
    assert r["offset"] == 7
    assert r["total_lines"] == 10
    assert r["truncated"] is False

    short = srv.read_file("n.txt", offset=-50)
    assert len(short["lines"]) == 10
    assert short["offset"] == 0


def test_read_file_tail_ignores_length(srv):
    srv.write_file("n.txt", "a\nb\nc\n")
    assert srv.read_file("n.txt", offset=-2, length=1)["lines"] == ["b\n", "c\n"]


def test_read_file_rejects_bad_length(srv):
    srv.write_file("n.txt", "a\n")
    assert "error" in srv.read_file("n.txt", length=0)


def test_read_file_char_cap(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_READ_CHARS", 10)
    srv.write_file("big.txt", "aaaaaa\nbbbbbb\ncccccc\n")
    r = srv.read_file("big.txt")
    assert "".join(r["lines"]) == "aaaaaa\nbbb"
    assert r["truncated"] is True
    assert r["total_lines"] == 3


def test_read_file_reports_line_ending(srv, tmp_path):
    (tmp_path / "crlf.txt").write_bytes(b"a\r\nb\r\n")
    (tmp_path / "lf.txt").write_bytes(b"a\nb\n")
    crlf = srv.read_file("crlf.txt")
    assert crlf["line_ending"] == "CRLF"
    assert crlf["lines"] == ["a\n", "b\n"]
    assert srv.read_file("lf.txt")["line_ending"] == "LF"


def test_read_multiple_files(srv):
    srv.write_file("a.txt", "A\n")
    srv.write_file("b.txt", "B1\nB2\n")
    r = srv.read_multiple_files(["a.txt", "b.txt"])
    assert [f["path"] for f in r["files"]] == ["a.txt", "b.txt"]
    assert r["files"][0]["lines"] == ["A\n"]
    assert r["files"][1]["total_lines"] == 2


def test_read_multiple_files_reports_error_per_file(srv):
    srv.write_file("a.txt", "A")
    r = srv.read_multiple_files(["a.txt", "tidak-ada.txt", "../luar.txt"])
    assert "error" not in r["files"][0]
    assert r["files"][1]["path"] == "tidak-ada.txt" and "error" in r["files"][1]
    assert r["files"][2]["path"] == "../luar.txt" and "error" in r["files"][2]


def test_read_multiple_files_shares_char_budget(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_READ_CHARS", 6)
    srv.write_file("a.txt", "aaaa\nbbbb\n")
    srv.write_file("b.txt", "cc\n")
    srv.write_file("c.txt", "dd\n")
    r = srv.read_multiple_files(["a.txt", "b.txt", "c.txt"])
    assert "".join(r["files"][0]["lines"]) == "aaaa\nb"
    assert r["files"][0]["truncated"] is True
    assert "error" in r["files"][1] or "error" in r["files"][2]


def test_read_multiple_files_validates_input(srv):
    assert "error" in srv.read_multiple_files([])
    assert "error" in srv.read_multiple_files(["x.txt"] * (srv.MAX_READ_FILES + 1))


# --------------------------------------------------------------------------
# move_file, delete
# --------------------------------------------------------------------------

def test_move_file(srv):
    srv.write_file("old.txt", "isi")
    result = srv.move_file("old.txt", "new.txt")
    assert result["moved"] is True
    assert srv.read_file("new.txt")["lines"] == ["isi"]
    assert srv.read_file("old.txt").get("error")


def test_move_file_no_overwrite_fails(srv):
    srv.write_file("a.txt", "A")
    srv.write_file("b.txt", "B")
    assert "error" in srv.move_file("a.txt", "b.txt")
    assert srv.read_file("a.txt")["lines"] == ["A"]


def test_move_file_overwrite(srv):
    srv.write_file("a.txt", "A")
    srv.write_file("b.txt", "B")
    assert srv.move_file("a.txt", "b.txt", overwrite=True)["moved"] is True
    assert srv.read_file("b.txt")["lines"] == ["A"]


def test_move_file_guards_protect_source(srv):
    srv.write_file("d/x.txt", "isi")
    assert "error" in srv.move_file("d", "d", overwrite=True)
    assert "error" in srv.move_file("d", "d/dalam", overwrite=True)
    assert "error" in srv.move_file("d/x.txt", "d", overwrite=True)
    assert srv.read_file("d/x.txt")["lines"] == ["isi"]


def test_delete_dir_requires_recursive_for_nonempty(srv):
    srv.create_directory("d")
    srv.write_file("d/x.txt", "x")
    assert "error" in srv.delete_dir("d")
    assert srv.delete_dir("d", recursive=True)["deleted"] is True


def test_delete_base_dir_blocked(srv):
    assert "error" in srv.delete_dir(".", recursive=True)


def test_delete_file(srv):
    srv.write_file("x.txt", "x")
    assert srv.delete_file("x.txt")["deleted"] is True
    assert "error" in srv.delete_file("x.txt")


def test_create_directory(srv, tmp_path):
    assert srv.create_directory("a/b/c")["created"] is True
    assert (tmp_path / "a" / "b" / "c").is_dir()
    assert srv.create_directory("a/b/c")["created"] is True


# --------------------------------------------------------------------------
# edit_block
# --------------------------------------------------------------------------

def test_edit_block_single_replacement(srv):
    srv.write_file("f.txt", "satu dua tiga")
    r = srv.edit_block("f.txt", "dua", "2")
    assert r == {"path": "f.txt", "replacements": 1}
    assert srv.read_file("f.txt")["lines"] == ["satu 2 tiga"]


def test_edit_block_no_match(srv):
    srv.write_file("f.txt", "abc")
    r = srv.edit_block("f.txt", "xyz", "123")
    assert "error" in r
    assert srv.read_file("f.txt")["lines"] == ["abc"]


def test_edit_block_requires_expected_count(srv):
    srv.write_file("f.txt", "aa aa aa")
    r = srv.edit_block("f.txt", "aa", "bb")
    assert "error" in r and "3" in r["error"]
    assert srv.read_file("f.txt")["lines"] == ["aa aa aa"]

    ok = srv.edit_block("f.txt", "aa", "bb", expected_replacements=3)
    assert ok["replacements"] == 3
    assert srv.read_file("f.txt")["lines"] == ["bb bb bb"]


def test_edit_block_rejects_bad_arguments(srv):
    srv.write_file("e.txt", "abc")
    assert "error" in srv.edit_block("e.txt", "", "x")
    assert "error" in srv.edit_block("e.txt", "a", "x", expected_replacements=0)
    assert srv.read_file("e.txt")["lines"] == ["abc"]


def test_edit_block_preserves_crlf_with_multiline_match(srv, tmp_path):
    (tmp_path / "e.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    r = srv.edit_block("e.txt", "one\ntwo", "uno\ndos")
    assert r["replacements"] == 1
    assert (tmp_path / "e.txt").read_bytes() == b"uno\r\ndos\r\nthree\r\n"


def test_edit_block_preserves_lf_file(srv, tmp_path):
    (tmp_path / "e.txt").write_bytes(b"one\ntwo\n")
    assert srv.edit_block("e.txt", "two", "dua")["replacements"] == 1
    assert (tmp_path / "e.txt").read_bytes() == b"one\ndua\n"


def test_edit_block_size_limit(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_WRITE_BYTES", 10)
    srv.write_file("e.txt", "abc")
    assert "error" in srv.edit_block("e.txt", "abc", "x" * 11)
    assert srv.read_file("e.txt")["lines"] == ["abc"]


# --------------------------------------------------------------------------
# Line ending dan batas tulis
# --------------------------------------------------------------------------

def test_write_new_file_uses_lf(srv, tmp_path):
    srv.write_file("new.txt", "x\ny\n")
    assert (tmp_path / "new.txt").read_bytes() == b"x\ny\n"


def test_write_preserves_crlf_of_existing_file(srv, tmp_path):
    (tmp_path / "w.txt").write_bytes(b"a\r\nb\r\n")
    srv.write_file("w.txt", "x\ny\n")
    assert (tmp_path / "w.txt").read_bytes() == b"x\r\ny\r\n"


def test_append_preserves_crlf(srv, tmp_path):
    (tmp_path / "a.txt").write_bytes(b"a\r\n")
    srv.write_file("a.txt", "b\n", mode="append")
    assert (tmp_path / "a.txt").read_bytes() == b"a\r\nb\r\n"


def test_write_file_on_directory_rejected(srv):
    srv.create_directory("d")
    assert "error" in srv.write_file("d", "x")


def test_write_size_limit(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_WRITE_BYTES", 10)
    assert "error" in srv.write_file("big.txt", "x" * 11)
    assert "error" not in srv.write_file("ok.txt", "x" * 10)


def test_append_size_limit_counts_existing_content(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_WRITE_BYTES", 10)
    srv.write_file("a.txt", "x" * 8)
    assert "error" in srv.write_file("a.txt", "yyy", mode="append")
    assert srv.read_file("a.txt")["lines"] == ["x" * 8]


# --------------------------------------------------------------------------
# get_file_info
# --------------------------------------------------------------------------

def test_get_file_info_text_file(srv):
    srv.write_file("t.txt", "a\nb\nc\n")
    info = srv.get_file_info("t.txt")
    assert info["type"] == "file"
    assert info["size"] == 6
    assert info["lines"] == 3
    assert info["modified"].endswith("Z") and len(info["modified"]) == 20


def test_get_file_info_binary_has_no_line_count(srv, tmp_path):
    (tmp_path / "b.bin").write_bytes(b"\x00\x01\x02\n\x03")
    info = srv.get_file_info("b.bin")
    assert info["size"] == 5
    assert "lines" not in info


def test_get_file_info_directory_and_errors(srv):
    srv.create_directory("d")
    info = srv.get_file_info("d")
    assert info["type"] == "dir"
    assert "size" not in info
    assert "error" in srv.get_file_info("tidak-ada")
    assert "error" in srv.get_file_info("../luar")


# --------------------------------------------------------------------------
# start_search
# --------------------------------------------------------------------------

def test_search_files_by_name(srv):
    srv.write_file("a/Kode.py", "x")
    srv.write_file("a/data.txt", "x")
    srv.create_directory("kode-baru")

    sub = srv.start_search("kode")["matches"]
    assert sub == ["a/Kode.py", "kode-baru/"]

    wild = srv.start_search("*.py")["matches"]
    assert wild == ["a/Kode.py"]
    assert srv.start_search("d?ta.txt")["matches"] == ["a/data.txt"]


def test_search_files_case_sensitive_option(srv):
    srv.write_file("Kode.py", "x")
    assert srv.start_search("kode", ignoreCase=False)["matches"] == []
    assert srv.start_search("Kode", ignoreCase=False)["matches"] == ["Kode.py"]


def test_search_content(srv):
    srv.write_file("a.py", "satu\nCari Ini\ntiga\n")
    srv.write_file("b.txt", "tidak ada\n")
    srv.write_file("c.py", "cari ini lagi\r\n")

    m = srv.start_search("cari ini", searchType="content")["matches"]
    assert m == ["a.py:2: Cari Ini", "c.py:1: cari ini lagi"]

    only_py_exact = srv.start_search("cari ini", searchType="content",
                                     ignoreCase=False)["matches"]
    assert only_py_exact == ["c.py:1: cari ini lagi"]

    filtered = srv.start_search("ada", searchType="content", filePattern="*.txt")["matches"]
    assert filtered == ["b.txt:1: tidak ada"]


def test_search_content_skips_binary_and_heavy_dirs(srv, tmp_path):
    (tmp_path / "b.bin").write_bytes(b"\x00cari")
    srv.write_file(".git/config", "cari")
    srv.write_file("ok.txt", "cari")
    m = srv.start_search("cari", searchType="content")["matches"]
    assert m == ["ok.txt:1: cari"]


def test_search_caps_results(srv):
    for i in range(5):
        srv.write_file(f"f{i}.txt", "x")
    r = srv.start_search("f", maxResults=2)
    assert len(r["matches"]) == 2
    assert r["truncated"] is True
    assert "truncated" not in srv.start_search("f", maxResults=5)


def test_search_validates_input(srv):
    assert "error" in srv.start_search("")
    assert "error" in srv.start_search("x", searchType="regex")
    assert "error" in srv.start_search("x", maxResults=0)
    assert "error" in srv.start_search("x", path="tidak-ada")
    assert "error" in srv.start_search("x", path="../luar")


# --------------------------------------------------------------------------
# Annotations dan instructions
# --------------------------------------------------------------------------

def test_tools_have_annotations(srv):
    import asyncio

    tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
    assert set(tools) == {
        "list_directory", "read_file", "read_multiple_files", "write_file",
        "edit_block", "create_directory", "move_file", "get_file_info",
        "start_search", "delete_file", "delete_dir",
    }
    for t in tools.values():
        assert t.annotations is not None
        assert t.annotations.openWorldHint is False

    for name in ("list_directory", "read_file", "read_multiple_files",
                 "get_file_info", "start_search"):
        assert tools[name].annotations.readOnlyHint is True
    for name in ("write_file", "edit_block", "delete_file", "delete_dir", "move_file"):
        assert tools[name].annotations.readOnlyHint is False
        assert tools[name].annotations.destructiveHint is True


def test_old_tool_names_are_gone(srv):
    for old in ("list_files", "append_file", "edit_file", "mkdir"):
        assert not hasattr(srv, old)


def test_tool_result_is_one_compact_json_block(srv):
    """Hasil lewat MCP: satu blok teks JSON ringkas, tanpa indentasi, isi sama dengan dict."""
    import asyncio
    import json

    (srv.BASE_DIR / "kompak.txt").write_text("a\nb\n", encoding="utf-8")
    blocks = asyncio.run(srv.mcp.call_tool("get_file_info", {"path": "kompak.txt"}))
    if isinstance(blocks, tuple):  # versi SDK yang mengembalikan (konten, terstruktur)
        blocks, structured = blocks
        assert structured is None
    assert len(blocks) == 1
    text = blocks[0].text
    assert "\n" not in text and ": " not in text and ", " not in text
    assert json.loads(text) == srv.get_file_info("kompak.txt")


def test_tool_function_still_returns_dict(srv):
    assert isinstance(srv.list_directory("."), dict)


def test_tool_result_keeps_unicode(srv):
    import asyncio
    import json

    (srv.BASE_DIR / "naïve.txt").write_text("x", encoding="utf-8")
    blocks = asyncio.run(srv.mcp.call_tool("list_directory", {"path": "."}))
    if isinstance(blocks, tuple):
        blocks = blocks[0]
    assert "naïve.txt" in blocks[0].text  # tidak di-escape menjadi \u00ef
    assert "[FILE] naïve.txt" in json.loads(blocks[0].text)["entries"]


def test_instructions_mention_base_dir(srv):
    assert str(srv.BASE_DIR) in srv.INSTRUCTIONS
    assert srv.mcp.instructions == srv.INSTRUCTIONS


def test_input_schemas_have_no_title_fields(srv):
    """Hemat token: FastMCP menambah "title" otomatis (nama tool dan tiap
    parameter) ke skema input; dibuang, sedangkan kontraknya tetap."""
    import asyncio

    def titles(node):
        if isinstance(node, dict):
            own = sum(1 for k, v in node.items() if k == "title" and isinstance(v, str))
            return own + sum(titles(v) for v in node.values())
        if isinstance(node, list):
            return sum(titles(v) for v in node)
        return 0

    tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
    assert sum(titles(t.inputSchema) for t in tools.values()) == 0

    ls = tools["list_directory"].inputSchema
    assert ls["properties"] == {
        "path": {"default": ".", "type": "string"},
        "depth": {"default": 2, "type": "integer"},
        "exclude": {"items": {"type": "string"}, "type": "array"},
        "max_entries": {"type": "integer"},
    }
    assert "required" not in ls
    ss = tools["start_search"].inputSchema
    assert ss["required"] == ["pattern"]
    assert ss["properties"]["ignoreCase"] == {"default": True, "type": "boolean"}
    assert tools["read_multiple_files"].inputSchema["properties"]["paths"]["items"] == {"type": "string"}
    # Judul di annotations (dipakai client untuk menampilkan nama tool) tetap ada.
    assert tools["list_directory"].annotations.title == "Daftar folder"

def test_unknown_arguments_are_rejected_without_running(srv):
    """Parameter tak dikenal (salah ketik, mis. "recursve") ditolak di server dan
    operasi tidak berjalan, setara dengan Go 0.2.7. Skema terkirim tidak berubah."""
    import asyncio

    base = srv.BASE_DIR
    (base / "a.txt").write_text("satu\n", encoding="utf-8")
    (base / "d").mkdir()
    (base / "d" / "dalam.txt").write_text("isi", encoding="utf-8")

    args = {
        "list_directory": {"path": "."},
        "read_file": {"path": "a.txt"},
        "read_multiple_files": {"paths": ["a.txt"]},
        "write_file": {"path": "baru.txt", "content": "x"},
        "edit_block": {"file_path": "a.txt", "old_string": "satu", "new_string": "SATU"},
        "create_directory": {"path": "dir-baru"},
        "move_file": {"source": "a.txt", "destination": "b.txt"},
        "delete_file": {"path": "a.txt"},
        "delete_dir": {"path": "d", "recursive": True},
        "get_file_info": {"path": "a.txt"},
        "start_search": {"pattern": "satu"},
    }
    tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
    assert set(args) == set(tools)

    for name, valid in args.items():
        with pytest.raises(Exception, match="salah_ketik"):
            asyncio.run(srv.mcp.call_tool(name, {**valid, "salah_ketik": True}))

    # Tidak ada operasi yang berjalan.
    assert (base / "a.txt").read_text(encoding="utf-8") == "satu\n"
    assert (base / "d" / "dalam.txt").exists()
    for nama in ("baru.txt", "b.txt", "dir-baru"):
        assert not (base / nama).exists()

    # Panggilan yang benar tetap berjalan, dan skema tidak memuat additionalProperties.
    blocks = asyncio.run(srv.mcp.call_tool("get_file_info", args["get_file_info"]))
    if isinstance(blocks, tuple):
        blocks = blocks[0]
    assert '"type":"file"' in blocks[0].text
    assert "additionalProperties" not in str([t.inputSchema for t in tools.values()])


def test_delete_dir_dry_run_recursive_reports_without_deleting(srv):
    base = srv.BASE_DIR
    (base / "d" / "sub" / "dalam").mkdir(parents=True)
    (base / "d" / "a.txt").write_text("abc", encoding="utf-8")
    (base / "d" / "sub" / "b.txt").write_text("de", encoding="utf-8")
    (base / "d" / "sub" / "dalam" / "c.txt").write_text("f", encoding="utf-8")

    r = srv.delete_dir("d", recursive=True, dry_run=True)
    assert "error" not in r, r
    assert r["dry_run"] is True and r["deleted"] is False and r["recursive"] is True
    assert (r["files"], r["dirs"], r["bytes"]) == (3, 2, 6)
    assert r["would_delete"] is True and "truncated" not in r
    for rel in ("d/a.txt", "d/sub/b.txt", "d/sub/dalam/c.txt"):
        assert (base / rel).exists(), rel


def test_delete_dir_dry_run_non_recursive(srv):
    base = srv.BASE_DIR
    (base / "penuh").mkdir()
    (base / "penuh" / "x.txt").write_text("x", encoding="utf-8")
    (base / "kosong").mkdir()

    r = srv.delete_dir("penuh", dry_run=True)
    assert "error" not in r
    assert (r["dry_run"], r["deleted"], r["empty"], r["would_delete"]) == (True, False, False, False)
    r = srv.delete_dir("kosong", dry_run=True)
    assert (r["dry_run"], r["deleted"], r["empty"], r["would_delete"]) == (True, False, True, True)
    assert (base / "penuh" / "x.txt").exists() and (base / "kosong").is_dir()


def test_delete_dir_dry_run_keeps_guards(srv):
    (srv.BASE_DIR / "f.txt").write_text("x", encoding="utf-8")
    for path, recursive in ((".", True), ("tidak-ada", False), ("f.txt", False), ("../luar", True)):
        assert "error" in srv.delete_dir(path, recursive=recursive, dry_run=True), path


def test_delete_dir_dry_run_caps_count(srv, monkeypatch):
    base = srv.BASE_DIR
    (base / "besar").mkdir()
    for i in range(9):
        (base / "besar" / f"f{i}.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(srv, "MAX_DRY_RUN_ENTRIES", 5)

    r = srv.delete_dir("besar", recursive=True, dry_run=True)
    assert "error" not in r and r["truncated"] is True and r["deleted"] is False
    assert len(list((base / "besar").iterdir())) == 9


def test_delete_dir_dry_run_schema_and_rejects_typo(srv):
    import asyncio

    tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
    props = tools["delete_dir"].inputSchema["properties"]
    assert props["dry_run"] == {"default": False, "type": "boolean"}
    with pytest.raises(Exception, match="dryrun"):
        asyncio.run(srv.mcp.call_tool("delete_dir", {"path": "d", "dryrun": True}))
