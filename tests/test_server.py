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


def test_write_and_read_roundtrip(srv):
    result = srv.write_file("hello.txt", "halo dunia")
    assert result["ok"] is True

    read = srv.read_file("hello.txt")
    assert "".join(read["lines"]) == "halo dunia"
    assert read["total_lines"] == 1


def test_append_file(srv):
    srv.write_file("log.txt", "baris1\n")
    result = srv.append_file("log.txt", "baris2\n")
    assert result["ok"] is True
    read = srv.read_file("log.txt")
    assert read["lines"] == ["baris1\n", "baris2\n"]


def test_path_traversal_blocked(srv):
    result = srv.read_file("../secret.txt")
    assert "error" in result


def test_absolute_path_escape_blocked(srv, tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("rahasia")
    result = srv.read_file(str(outside))
    assert "error" in result


def test_null_byte_rejected(srv):
    result = srv.read_file("bad\x00name.txt")
    assert "error" in result


def test_list_files_recursive_and_pattern(srv):
    srv.mkdir("sub")
    srv.write_file("sub/a.py", "print(1)")
    srv.write_file("sub/b.txt", "text")

    result = srv.list_files(".", recursive=True, pattern="*.py")
    names = [e["name"] for e in result["entries"]]
    assert any(n.endswith("a.py") for n in names)
    assert not any(n.endswith("b.txt") for n in names)


def test_list_files_recursive_excludes_heavy_dirs(srv):
    srv.mkdir(".git")
    srv.write_file(".git/config", "junk")
    srv.mkdir(".venv/lib")
    srv.write_file(".venv/lib/pkg.py", "junk")
    srv.write_file("real.py", "print('ok')")

    result = srv.list_files(".", recursive=True, pattern="*")
    names = [e["name"] for e in result["entries"]]
    assert "real.py" in names
    assert not any(n.startswith(".git") for n in names)
    assert not any(n.startswith(".venv") for n in names)
    assert result["truncated"] is False


def test_list_files_recursive_caps_entry_count(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_RECURSIVE_ENTRIES", 3)
    for i in range(6):
        srv.write_file(f"f{i}.txt", "x")

    result = srv.list_files(".", recursive=True, pattern="*")
    assert result["count"] == 3
    assert result["truncated"] is True


def test_move_file(srv):
    srv.write_file("old.txt", "isi")
    result = srv.move_file("old.txt", "new.txt")
    assert result["moved"] is True
    assert srv.read_file("new.txt")["lines"] == ["isi"]
    assert srv.read_file("old.txt").get("error")


def test_move_file_no_overwrite_fails(srv):
    srv.write_file("a.txt", "A")
    srv.write_file("b.txt", "B")
    result = srv.move_file("a.txt", "b.txt")
    assert "error" in result


def test_edit_file_no_match(srv):
    srv.write_file("f.txt", "abc")
    result = srv.edit_file("f.txt", "xyz", "123")
    assert result["ok"] is False


def test_edit_file_replace_all(srv):
    srv.write_file("f.txt", "aa aa aa")
    result = srv.edit_file("f.txt", "aa", "bb")
    assert result["ok"] is True
    assert result["replacements"] == 3
    assert srv.read_file("f.txt")["lines"] == ["bb bb bb"]


def test_delete_dir_requires_recursive_for_nonempty(srv):
    srv.mkdir("d")
    srv.write_file("d/x.txt", "x")
    result = srv.delete_dir("d")
    assert "error" in result

    result = srv.delete_dir("d", recursive=True)
    assert result["deleted"] is True


def test_delete_base_dir_blocked(srv):
    result = srv.delete_dir(".", recursive=True)
    assert "error" in result



# --------------------------------------------------------------------------
# Optimasi untuk Claude Desktop (0.3.0)
# --------------------------------------------------------------------------

def test_read_file_offset_and_limit(srv):
    srv.write_file("n.txt", "".join(f"baris{i}\n" for i in range(10)))
    r = srv.read_file("n.txt", limit=3, offset=2)
    assert r["lines"] == ["baris2\n", "baris3\n", "baris4\n"]
    assert r["offset"] == 2
    assert r["total_lines"] == 10
    assert r["truncated"] is True
    assert r["next_offset"] == 5

    last = srv.read_file("n.txt", limit=100, offset=r["next_offset"])
    assert last["lines"][0] == "baris5\n"
    assert last["truncated"] is False
    assert "next_offset" not in last


def test_read_file_rejects_negative_offset(srv):
    assert "error" in srv.read_file("x.txt", offset=-1)


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


def test_write_new_file_uses_lf(srv, tmp_path):
    srv.write_file("new.txt", "x\ny\n")
    assert (tmp_path / "new.txt").read_bytes() == b"x\ny\n"


def test_write_preserves_crlf_of_existing_file(srv, tmp_path):
    (tmp_path / "w.txt").write_bytes(b"a\r\nb\r\n")
    srv.write_file("w.txt", "x\ny\n")
    assert (tmp_path / "w.txt").read_bytes() == b"x\r\ny\r\n"


def test_write_file_on_directory_rejected(srv):
    srv.mkdir("d")
    assert "error" in srv.write_file("d", "x")


def test_append_preserves_crlf(srv, tmp_path):
    (tmp_path / "a.txt").write_bytes(b"a\r\n")
    srv.append_file("a.txt", "b\n")
    assert (tmp_path / "a.txt").read_bytes() == b"a\r\nb\r\n"


def test_edit_preserves_crlf_with_multiline_match(srv, tmp_path):
    (tmp_path / "e.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    r = srv.edit_file("e.txt", "one\ntwo", "uno\ndos")
    assert r["ok"] is True
    assert (tmp_path / "e.txt").read_bytes() == b"uno\r\ndos\r\nthree\r\n"


def test_edit_preserves_lf_file(srv, tmp_path):
    (tmp_path / "e.txt").write_bytes(b"one\ntwo\n")
    r = srv.edit_file("e.txt", "two", "dua")
    assert r["ok"] is True
    assert (tmp_path / "e.txt").read_bytes() == b"one\ndua\n"


def test_edit_rejects_empty_old_string(srv):
    srv.write_file("e.txt", "abc")
    assert "error" in srv.edit_file("e.txt", "", "x")
    assert srv.read_file("e.txt")["lines"] == ["abc"]


def test_write_size_limit(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_WRITE_BYTES", 10)
    assert "error" in srv.write_file("big.txt", "x" * 11)
    assert srv.write_file("ok.txt", "x" * 10)["ok"] is True


def test_append_size_limit_counts_existing_content(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_WRITE_BYTES", 10)
    srv.write_file("a.txt", "x" * 8)
    assert "error" in srv.append_file("a.txt", "yyy")
    assert srv.read_file("a.txt")["lines"] == ["x" * 8]


def test_edit_size_limit(srv, monkeypatch):
    monkeypatch.setattr(srv, "MAX_WRITE_BYTES", 10)
    srv.write_file("e.txt", "abc")
    assert "error" in srv.edit_file("e.txt", "abc", "x" * 11)
    assert srv.read_file("e.txt")["lines"] == ["abc"]


def test_tools_have_annotations(srv):
    import asyncio

    tools = {t.name: t for t in asyncio.run(srv.mcp.list_tools())}
    assert set(tools) == {
        "list_files", "read_file", "write_file", "append_file", "edit_file",
        "delete_file", "delete_dir", "move_file", "mkdir",
    }
    for t in tools.values():
        assert t.annotations is not None
        assert t.annotations.openWorldHint is False

    assert tools["read_file"].annotations.readOnlyHint is True
    assert tools["list_files"].annotations.readOnlyHint is True
    for name in ("write_file", "edit_file", "delete_file", "delete_dir", "move_file"):
        assert tools[name].annotations.readOnlyHint is False
        assert tools[name].annotations.destructiveHint is True


def test_instructions_mention_base_dir(srv):
    assert str(srv.BASE_DIR) in srv.INSTRUCTIONS
    assert srv.mcp.instructions == srv.INSTRUCTIONS
