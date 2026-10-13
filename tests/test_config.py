"""Test config terpusat (berkas JSON) untuk mcp-file-manager.

Padanan config_file_test.go di versi Go (0.5.0): folder dasar rw/ro, batas
hasil, muat ulang tanpa restart, dan cadangan MCP_FILE_BASE.
"""
import asyncio
import importlib
import itertools
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_tick = itertools.count(1)


def _load(monkeypatch, *, config=None, base=None, **env):
    """Import ulang server.py dengan env tertentu (hanya yang diberikan)."""
    # Nilai kosong (bukan dihapus) agar load_dotenv() tidak mengisinya dari .env.
    monkeypatch.setenv("MCP_FILE_CONFIG", "")
    monkeypatch.setenv("MCP_FILE_BASE", "")
    if config is not None:
        monkeypatch.setenv("MCP_FILE_CONFIG", str(config))
    if base is not None:
        monkeypatch.setenv("MCP_FILE_BASE", str(base))
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    import server  # noqa: E402
    return importlib.reload(server)


def _write_cfg(path, data):
    """Tulis config dan pastikan tanda berkas (waktu ubah) berbeda dari sebelumnya."""
    text = data if isinstance(data, str) else json.dumps(data)
    path.write_text(text, encoding="utf-8")
    t = 2_000_000_000_000_000_000 + next(_tick) * 1_000_000_000
    os.utime(path, ns=(t, t))


@pytest.fixture()
def dirs(tmp_path):
    out = {}
    for name in ("a", "b", "c"):
        d = tmp_path / name
        d.mkdir()
        out[name] = d
    out["cfg"] = tmp_path / "config" / "config.json"
    out["cfg"].parent.mkdir()
    return out


def _bases(*pairs):
    return {"bases": [{"path": str(p), "mode": m} for p, m in pairs]}


def test_config_file_basic(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], {**_bases((dirs["a"], "rw"), (dirs["b"], "ro")),
                             "max_write_bytes": 1234, "max_read_chars": 500, "max_entries": 7})
    srv = _load(monkeypatch, config=dirs["cfg"])
    assert srv.BASES == [dirs["a"].resolve(), dirs["b"].resolve()]
    assert srv.BASE_DIR == dirs["a"].resolve()
    assert srv.RO_BASES == [dirs["b"].resolve()]
    assert (srv.MAX_WRITE_BYTES, srv.MAX_READ_CHARS, srv.MAX_LIST_ENTRIES) == (1234, 500, 7)


def test_config_file_mode_default_is_read_only(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], {"bases": [{"path": str(dirs["a"])}, {"path": str(dirs["b"]), "mode": "rw"}]})
    srv = _load(monkeypatch, config=dirs["cfg"])
    assert srv.RO_BASES == [dirs["a"].resolve()]


def test_config_file_default_limits(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "rw")))
    srv = _load(monkeypatch, config=dirs["cfg"], MCP_FILE_MAX_WRITE_BYTES=999)
    assert srv.MAX_WRITE_BYTES == 999
    assert srv.MAX_READ_CHARS == srv.DEFAULT_MAX_READ_CHARS
    assert srv.MAX_LIST_ENTRIES == srv.DEFAULT_MAX_ENTRIES


@pytest.mark.parametrize("content", [
    "bukan json",
    '{"bases": [{"path": "X"}]} sisa',
    '[]',
    '{"bases": [{"path": "X"}], "tak_dikenal": 1}',
    '{"bases": []}',
    '{}',
    '{"bases": [{"path": "X", "mode": "rwx"}]}',
    '{"bases": [{"path": "X", "ekstra": 1}]}',
    '{"bases": [{"path": ""}]}',
    '{"bases": [{"path": "X"}], "max_entries": -1}',
    '{"bases": [{"path": "X"}], "max_read_chars": "10"}',
    '{"bases": [{"path": "X"}], "max_write_bytes": true}',
])
def test_config_file_invalid_without_fallback_fails(dirs, monkeypatch, content):
    _write_cfg(dirs["cfg"], content.replace("X", str(dirs["a"]).replace("\\", "/")))
    with pytest.raises(ValueError, match="MCP_FILE_BASE"):
        _load(monkeypatch, config=dirs["cfg"])


def test_config_file_missing_folder_fails(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], _bases((dirs["a"] / "tidak-ada", "rw")))
    with pytest.raises(ValueError):
        _load(monkeypatch, config=dirs["cfg"])


def test_config_file_overlapping_bases_rejected(dirs, monkeypatch):
    sub = dirs["a"] / "sub"
    sub.mkdir()
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "rw"), (sub, "ro")))
    with pytest.raises(ValueError):
        _load(monkeypatch, config=dirs["cfg"])


def test_config_file_inside_base_rejected(dirs, monkeypatch):
    inside = dirs["a"] / "config.json"
    _write_cfg(inside, _bases((dirs["a"], "rw")))
    with pytest.raises(ValueError, match="di dalam folder dasar"):
        _load(monkeypatch, config=inside)


def test_no_base_and_no_config_fails(monkeypatch):
    with pytest.raises(ValueError, match="MCP_FILE_BASE belum diisi"):
        _load(monkeypatch)


def test_config_file_fallback_to_env(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], "rusak")
    srv = _load(monkeypatch, config=dirs["cfg"], base=dirs["b"])
    assert srv.BASES == [dirs["b"].resolve()]
    assert srv.RO_BASES == []


def test_config_file_fallback_then_reload(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], "rusak")
    srv = _load(monkeypatch, config=dirs["cfg"], base=dirs["b"])
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "ro")))
    srv._refresh_config()
    assert srv.BASES == [dirs["a"].resolve()]
    assert srv.RO_BASES == [dirs["a"].resolve()]


def test_default_config_path(tmp_path, monkeypatch):
    srv = _load(monkeypatch, base=tmp_path)
    expected = tmp_path / "mcp-file-manager" / "config.json"
    if os.name == "nt":
        assert srv._default_config_path({"APPDATA": str(tmp_path)}) == expected
    else:
        assert srv._default_config_path({"XDG_CONFIG_HOME": str(tmp_path)}) == expected
        assert srv._default_config_path({"HOME": str(tmp_path)}) == tmp_path / ".config" / "mcp-file-manager" / "config.json"
    assert srv._default_config_path({}) is None


def test_default_config_file_is_used_when_present(tmp_path, monkeypatch):
    home = tmp_path / "home"
    work = tmp_path / "kerja"
    work.mkdir()
    cfg = home / "mcp-file-manager" / "config.json" if os.name == "nt" else home / ".config" / "mcp-file-manager" / "config.json"
    cfg.parent.mkdir(parents=True)
    _write_cfg(cfg, _bases((work, "rw")))
    monkeypatch.setenv("APPDATA", str(home))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    srv = _load(monkeypatch)
    assert srv.BASES == [work.resolve()]


def test_read_only_blocks_writes(dirs, monkeypatch):
    (dirs["b"] / "x.txt").write_text("isi", encoding="utf-8")
    (dirs["b"] / "sub").mkdir()
    (dirs["a"] / "y.txt").write_text("isi", encoding="utf-8")
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "rw"), (dirs["b"], "ro")))
    srv = _load(monkeypatch, config=dirs["cfg"])
    ro = str(dirs["b"])

    def blocked(result):
        assert "hanya baca" in result.get("error", ""), result

    blocked(srv.write_file(os.path.join(ro, "baru.txt"), "x"))
    blocked(srv.edit_block(os.path.join(ro, "x.txt"), "isi", "ubah"))
    blocked(srv.create_directory(os.path.join(ro, "dir-baru")))
    blocked(srv.delete_file(os.path.join(ro, "x.txt")))
    blocked(srv.delete_dir(os.path.join(ro, "sub")))
    blocked(srv.move_file(os.path.join(ro, "x.txt"), os.path.join(str(dirs["a"]), "z.txt")))
    blocked(srv.move_file(os.path.join(str(dirs["a"]), "y.txt"), os.path.join(ro, "y.txt")))
    assert (dirs["b"] / "x.txt").read_text(encoding="utf-8") == "isi"
    assert not (dirs["b"] / "baru.txt").exists()
    # membaca dan menulis di folder rw tetap boleh
    assert "error" not in srv.read_file(os.path.join(ro, "x.txt"))
    assert "error" not in srv.write_file(os.path.join(str(dirs["a"]), "ok.txt"), "x")


def test_reload_applies_changes(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "ro")))
    srv = _load(monkeypatch, config=dirs["cfg"])
    assert "hanya baca" in srv.write_file("f.txt", "1").get("error", "")
    _write_cfg(dirs["cfg"], {**_bases((dirs["a"], "rw"), (dirs["b"], "rw")), "max_entries": 3})
    srv._refresh_config()
    assert srv.RO_BASES == []
    assert srv.BASES == [dirs["a"].resolve(), dirs["b"].resolve()]
    assert srv.MAX_LIST_ENTRIES == 3
    assert "error" not in srv.write_file("f.txt", "1")
    assert (dirs["a"] / "f.txt").read_text(encoding="utf-8") == "1"


def test_reload_keeps_last_valid_on_broken_file(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "rw")))
    srv = _load(monkeypatch, config=dirs["cfg"])
    _write_cfg(dirs["cfg"], "{rusak")
    srv._refresh_config()
    assert srv.BASES == [dirs["a"].resolve()]
    assert srv.RO_BASES == []
    dirs["cfg"].unlink()
    srv._refresh_config()
    assert srv.BASES == [dirs["a"].resolve()]


def test_reload_rejects_config_inside_new_base(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "rw")))
    srv = _load(monkeypatch, config=dirs["cfg"])
    _write_cfg(dirs["cfg"], _bases((dirs["cfg"].parent, "rw")))
    srv._refresh_config()
    assert srv.BASES == [dirs["a"].resolve()]


def test_env_only_has_no_reload(dirs, monkeypatch):
    srv = _load(monkeypatch, base=dirs["a"])
    assert srv._CFG_PATH is None
    srv._refresh_config()
    assert srv.BASES == [dirs["a"].resolve()]


def _call(srv, name, args):
    out = asyncio.run(srv.mcp.call_tool(name, args))
    content = out[0] if isinstance(out, tuple) else out
    return json.loads(content[0].text)


def test_reload_through_protocol(dirs, monkeypatch):
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "ro")))
    srv = _load(monkeypatch, config=dirs["cfg"])
    assert "hanya baca" in _call(srv, "write_file", {"path": "x.txt", "content": "1"}).get("error", "")
    _write_cfg(dirs["cfg"], _bases((dirs["a"], "rw")))
    assert "error" not in _call(srv, "write_file", {"path": "x.txt", "content": "1"})
    assert (dirs["a"] / "x.txt").read_text(encoding="utf-8") == "1"
