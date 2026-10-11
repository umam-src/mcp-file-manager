"""Test tautan (symlink dan junction) dan operasi timpa untuk mcp-file-manager.

Padanan test regresi versi Go (0.2.1 sampai 0.2.4). Test yang butuh symlink
file dilewati bila mesin tidak mengizinkannya (Windows tanpa Developer Mode);
junction folder di Windows tidak butuh hak khusus.
"""
import importlib
import os
import shutil
import subprocess
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


@pytest.fixture()
def outside(tmp_path):
    """Folder di luar BASE_DIR berisi satu file yang tidak boleh tersentuh."""
    d = tmp_path.parent / (tmp_path.name + "-luar")
    d.mkdir()
    (d / "rahasia.txt").write_text("rahasia luar", encoding="utf-8")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def dir_link(link, target):
    """Buat tautan folder: junction di Windows, symlink di tempat lain."""
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            pytest.skip(f"junction tidak bisa dibuat: {r.stderr.strip()}")
    else:
        os.symlink(target, link, target_is_directory=True)


def file_link(link, target):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink file tidak diizinkan di mesin ini")


@pytest.fixture()
def asli(tmp_path):
    """Folder di dalam BASE_DIR yang menjadi target tautan."""
    d = tmp_path / "asli"
    d.mkdir()
    (d / "isi.txt").write_text("penting", encoding="utf-8")
    return d


# --------------------------------------------------------------------------
# P-1 / G-1: delete dan move bekerja pada tautan, bukan targetnya
# --------------------------------------------------------------------------

def test_delete_dir_recursive_on_link_removes_only_link(srv, tmp_path, asli):
    dir_link(tmp_path / "tautan", asli)
    result = srv.delete_dir("tautan", recursive=True)
    assert result == {"path": "tautan", "deleted": True, "link": True}
    assert not os.path.lexists(tmp_path / "tautan")
    assert (asli / "isi.txt").read_text(encoding="utf-8") == "penting"


def test_delete_dir_nonrecursive_on_link_removes_only_link(srv, tmp_path, asli):
    dir_link(tmp_path / "tautan", asli)
    result = srv.delete_dir("tautan")
    assert result == {"path": "tautan", "deleted": True, "link": True}
    assert not os.path.lexists(tmp_path / "tautan")
    assert (asli / "isi.txt").exists()


def test_delete_file_on_file_symlink_removes_only_link(srv, tmp_path):
    (tmp_path / "asli.txt").write_text("penting", encoding="utf-8")
    file_link(tmp_path / "tautan.txt", tmp_path / "asli.txt")
    assert srv.delete_file("tautan.txt") == {"path": "tautan.txt", "deleted": True}
    assert not os.path.lexists(tmp_path / "tautan.txt")
    assert (tmp_path / "asli.txt").read_text(encoding="utf-8") == "penting"


def test_delete_file_on_broken_link_works(srv, tmp_path):
    file_link(tmp_path / "rusak.txt", tmp_path / "tidak-ada.txt")
    assert srv.delete_file("rusak.txt") == {"path": "rusak.txt", "deleted": True}
    assert not os.path.lexists(tmp_path / "rusak.txt")


def test_move_file_moves_link_not_target(srv, tmp_path, asli):
    dir_link(tmp_path / "tautan", asli)
    result = srv.move_file("tautan", "pindah")
    assert result == {"destination": "pindah", "moved": True}
    assert os.path.lexists(tmp_path / "pindah")
    assert not os.path.lexists(tmp_path / "tautan")
    assert (asli / "isi.txt").read_text(encoding="utf-8") == "penting"


def test_move_overwrite_onto_link_keeps_target_content(srv, tmp_path, asli):
    (tmp_path / "baru.txt").write_text("baru", encoding="utf-8")
    dir_link(tmp_path / "tautan", asli)
    result = srv.move_file("baru.txt", "tautan", overwrite=True)
    assert result == {"destination": "tautan", "moved": True}
    assert (tmp_path / "tautan").read_text(encoding="utf-8") == "baru"
    assert (asli / "isi.txt").read_text(encoding="utf-8") == "penting"


def test_link_outside_base_still_rejected(srv, tmp_path, outside):
    dir_link(tmp_path / "keluar", outside)
    assert "error" in srv.delete_dir("keluar", recursive=True)
    assert "error" in srv.move_file("keluar", "pindah")
    assert (outside / "rahasia.txt").read_text(encoding="utf-8") == "rahasia luar"


def test_read_through_link_inside_base_still_works(srv, tmp_path, asli):
    dir_link(tmp_path / "tautan", asli)
    assert srv.read_file("tautan/isi.txt")["lines"] == ["penting"]


# --------------------------------------------------------------------------
# G-8: timpa tidak boleh menghapus tujuan sebelum pemindahan berhasil
# --------------------------------------------------------------------------

def test_move_overwrite_failure_keeps_destination(srv, tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("sumber", encoding="utf-8")
    (tmp_path / "b.txt").write_text("lama", encoding="utf-8")

    def gagal(*args, **kwargs):
        raise OSError("gagal dipindah")

    monkeypatch.setattr(srv.shutil, "move", gagal)
    assert "error" in srv.move_file("a.txt", "b.txt", overwrite=True)
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "lama"
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "sumber"
    assert not [n for n in os.listdir(tmp_path) if n.startswith(".mfm-lama-")]


def test_move_overwrite_success_leaves_no_backup(srv, tmp_path):
    (tmp_path / "a.txt").write_text("sumber", encoding="utf-8")
    (tmp_path / "b.txt").write_text("lama", encoding="utf-8")
    assert srv.move_file("a.txt", "b.txt", overwrite=True) == {"destination": "b.txt", "moved": True}
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "sumber"
    assert sorted(os.listdir(tmp_path)) == ["b.txt"]


# --------------------------------------------------------------------------
# G-9: pencarian dan daftar tidak keluar BASE_DIR lewat tautan
# --------------------------------------------------------------------------

def test_search_content_does_not_read_symlink_outside(srv, tmp_path, outside):
    file_link(tmp_path / "ln.txt", outside / "rahasia.txt")
    assert srv.start_search("rahasia", searchType="content")["matches"] == []


def test_search_and_list_do_not_enter_link_to_outside(srv, tmp_path, outside):
    dir_link(tmp_path / "keluar", outside)
    content = srv.start_search("rahasia", searchType="content")["matches"]
    assert not any("rahasia luar" in m for m in content)
    names = srv.start_search("rahasia", searchType="files")["matches"]
    assert not any(m.endswith("rahasia.txt") for m in names)
    entries = srv.list_directory(".", depth=3)["entries"]
    assert not any(e.endswith("rahasia.txt") for e in entries)


# --------------------------------------------------------------------------
# G-10: ganti huruf besar/kecil nama pada file yang sama
# --------------------------------------------------------------------------

def test_move_file_case_only_rename(srv, tmp_path):
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    assert srv.move_file("a.txt", "A.txt") == {"destination": "A.txt", "moved": True}
    assert os.listdir(tmp_path) == ["A.txt"]


def test_delete_dir_dry_run_on_link_reports_only_link(srv, tmp_path):
    asli = srv.BASE_DIR / "asli"
    asli.mkdir()
    (asli / "data.txt").write_text("penting", encoding="utf-8")
    dir_link(srv.BASE_DIR / "tautan", asli)

    r = srv.delete_dir("tautan", recursive=True, dry_run=True)
    assert "error" not in r, r
    assert r["link"] is True and r["deleted"] is False and r["dry_run"] is True
    assert "files" not in r
    assert os.path.lexists(srv.BASE_DIR / "tautan")
    assert (asli / "data.txt").read_text(encoding="utf-8") == "penting"
