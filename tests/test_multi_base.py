"""Test beberapa folder di MCP_FILE_BASE untuk mcp-file-manager.

Padanan multi_base_test.go di versi Go (0.3.0). Test tautan yang butuh symlink
atau junction dilewati bila mesin tidak mengizinkannya.
"""
import importlib
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(monkeypatch, *dirs):
    monkeypatch.setenv("MCP_FILE_BASE", os.pathsep.join(str(d) for d in dirs))
    import server  # noqa: E402
    importlib.reload(server)
    return server


@pytest.fixture()
def dirs(tmp_path):
    out = []
    for name in ("satu", "dua", "tiga"):
        d = tmp_path / name
        d.mkdir()
        out.append(d)
    return out


@pytest.fixture()
def srv2(dirs, monkeypatch):
    return _load(monkeypatch, dirs[0], dirs[1])


def test_single_folder_unchanged(dirs, monkeypatch):
    srv = _load(monkeypatch, dirs[0])
    assert srv.BASES == [srv.BASE_DIR]
    assert "Folder lain" not in srv.INSTRUCTIONS
    assert str(srv.BASE_DIR) in srv.INSTRUCTIONS


def test_multiple_folders_loaded(srv2, dirs):
    assert [str(b) for b in srv2.BASES] == [str(dirs[0].resolve()), str(dirs[1].resolve())]
    assert srv2.BASE_DIR == srv2.BASES[0]


def test_overlap_rejected(dirs, monkeypatch):
    (dirs[0] / "anak").mkdir()
    with pytest.raises(ValueError, match="tumpang tindih"):
        _load(monkeypatch, dirs[0], dirs[0] / "anak")
    with pytest.raises(ValueError, match="tumpang tindih"):
        _load(monkeypatch, dirs[0], dirs[0])


def test_unavailable_folder_skipped(dirs, tmp_path, monkeypatch):
    srv = _load(monkeypatch, tmp_path / "tidak-ada", dirs[1])
    assert srv.BASES == [dirs[1].resolve()]
    with pytest.raises(ValueError, match="tidak ada folder"):
        _load(monkeypatch, tmp_path / "tidak-ada", tmp_path / "juga-tidak-ada")


def test_safe_accepts_any_base_and_rejects_outside(srv2, dirs, tmp_path):
    assert srv2._safe(str(dirs[1] / "x.txt")) == (dirs[1] / "x.txt").resolve()
    assert srv2._safe("a.txt") == (dirs[0] / "a.txt").resolve()  # relatif dari folder pertama
    with pytest.raises(srv2.PathError):
        srv2._safe(str(dirs[2] / "x.txt"))
    with pytest.raises(srv2.PathError):
        srv2._safe(os.path.join("..", "luar.txt"))


def test_tools_work_in_second_base(srv2, dirs):
    f = dirs[1] / "sub" / "catatan.txt"
    assert "error" not in srv2.write_file(str(f), "isi kedua\n")
    assert f.read_text(encoding="utf-8") == "isi kedua\n"
    assert "".join(srv2.read_file(str(f))["lines"]) == "isi kedua\n"
    assert "error" not in srv2.list_directory(str(dirs[1]), depth=2)


def test_outside_all_bases_rejected_by_tools(srv2, dirs):
    assert "error" in srv2.write_file(str(dirs[2] / "x.txt"), "x")
    assert not (dirs[2] / "x.txt").exists()


def test_delete_dir_refuses_every_base(srv2, dirs):
    for d in dirs[:2]:
        (d / "jangan-hilang.txt").write_text("x", encoding="utf-8")
        assert "error" in srv2.delete_dir(str(d), recursive=True)
        assert (d / "jangan-hilang.txt").exists()
    (dirs[1] / "boleh").mkdir()
    assert srv2.delete_dir(str(dirs[1] / "boleh")) == {
        "path": str(dirs[1] / "boleh"), "deleted": True, "recursive": False}


def test_dry_run_in_second_base(srv2, dirs):
    sub = dirs[1] / "pratinjau"
    sub.mkdir()
    (sub / "a.txt").write_text("abc", encoding="utf-8")
    r = srv2.delete_dir(str(sub), recursive=True, dry_run=True)
    assert r["deleted"] is False and r["files"] == 1
    assert (sub / "a.txt").exists()


def test_move_between_bases(srv2, dirs):
    src = dirs[0] / "a.txt"
    dst = dirs[1] / "b.txt"
    src.write_text("pindah", encoding="utf-8")
    assert "error" not in srv2.move_file(str(src), str(dst))
    assert dst.read_text(encoding="utf-8") == "pindah"
    assert not src.exists()


def test_link_in_second_base_checked(srv2, dirs, tmp_path):
    luar = tmp_path / "luar"
    luar.mkdir()
    (luar / "rahasia.txt").write_text("rahasia", encoding="utf-8")
    link = dirs[1] / "tautan"
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(luar)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            pytest.skip(f"junction tidak bisa dibuat: {r.stderr.strip()}")
    else:
        os.symlink(luar, link, target_is_directory=True)
    assert "error" in srv2.read_file(str(link / "rahasia.txt"))
    assert (luar / "rahasia.txt").read_text(encoding="utf-8") == "rahasia"


def test_instructions_list_folders_only_when_multiple(srv2, dirs):
    assert "Folder lain" in srv2.INSTRUCTIONS
    assert str(dirs[1].resolve()) in srv2.INSTRUCTIONS
    assert "folder pertama" in srv2.INSTRUCTIONS
