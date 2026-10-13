"""Isolasi config untuk semua test: tanpa berkas config bawaan milik pengguna."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_config_env(tmp_path_factory, monkeypatch):
    empty = tmp_path_factory.mktemp("home-kosong")
    for name in ("APPDATA", "XDG_CONFIG_HOME", "HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(empty))
    # Kosong, bukan dihapus: load_dotenv() tidak menimpa variabel yang sudah ada.
    monkeypatch.setenv("MCP_FILE_CONFIG", "")
