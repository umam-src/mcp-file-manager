"""Test list_directory exclude dan max_entries untuk mcp-file-manager.

Padanan list_options_test.go di versi Go (0.4.0).
"""
import asyncio
import importlib
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def srv(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_FILE_BASE", str(tmp_path))
    import server  # noqa: E402
    return importlib.reload(server)


def _raw(srv, rel, text="x"):
    p = srv.BASE_DIR / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_exclude(srv):
    for rel in ("a.txt", "b.log", "keep/c.txt", "skip/d.txt", "tmp1/e.txt"):
        _raw(srv, rel)
    r = srv.list_directory(exclude=["skip", "*.log", "tmp?"])
    assert "error" not in r, r
    assert r["entries"] == ["[FILE] a.txt", "[DIR] keep", "[FILE] keep/c.txt"]


def test_exclude_name_is_exact(srv):
    _raw(srv, "log.txt")
    _raw(srv, "logs/a.txt")
    r = srv.list_directory(exclude=["log"])
    assert len(r["entries"]) == 3, r  # tanpa wildcard: cocok nama persis, bukan sebagian


def test_exclude_empty_list_changes_nothing(srv):
    _raw(srv, "a.txt")
    assert srv.list_directory(exclude=[]) == srv.list_directory()


def test_max_entries(srv):
    for n in "abcd":
        _raw(srv, f"{n}.txt")
    r = srv.list_directory(max_entries=2)
    assert len(r["entries"]) == 2 and r["truncated"] is True

    # Di atas batas server: dipotong ke batas server, bukan gagal.
    srv.MAX_LIST_ENTRIES = 3
    r = srv.list_directory(max_entries=100)
    assert len(r["entries"]) == 3 and r["truncated"] is True


@pytest.mark.parametrize("bad", [0, -1])
def test_max_entries_invalid(srv, bad):
    assert "error" in srv.list_directory(max_entries=bad)


def test_default_result_unchanged_without_options(srv):
    _raw(srv, "a.txt")
    r = srv.list_directory()
    assert r == {"path": ".", "entries": ["[FILE] a.txt"]}


def test_options_through_protocol_and_null_is_unset(srv):
    for n in "abc":
        _raw(srv, f"{n}.txt")

    def call(args):
        out = asyncio.run(srv.mcp.call_tool("list_directory", args))
        content = out[0] if isinstance(out, tuple) else out
        return json.loads(content[0].text)

    assert call({"exclude": ["a.txt"], "max_entries": 1})["entries"] == ["[FILE] b.txt"]
    assert len(call({"exclude": None, "max_entries": None})["entries"]) == 3


def test_schemas_have_no_null_union(srv):
    tools = asyncio.run(srv.mcp.list_tools())

    def has_null(node):
        if isinstance(node, dict):
            return node.get("type") == "null" or any(has_null(v) for v in node.values())
        if isinstance(node, list):
            return any(has_null(v) for v in node)
        return False

    for t in tools:
        assert not has_null(t.inputSchema), t.name
