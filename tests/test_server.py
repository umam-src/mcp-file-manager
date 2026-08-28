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
