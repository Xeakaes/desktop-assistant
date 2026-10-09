import importlib
import sys


def test_sdk_importable_from_vendor():
    mod = importlib.import_module("vendor.sc_server.sdk")
    assert hasattr(mod, "ScreenControl")


def test_vendor_packages_renamed():
    sc_core_backends = importlib.import_module("vendor.sc_server.sc_core.backends")
    assert sc_core_backends.__name__ == "vendor.sc_server.sc_core.backends"
    import core

    assert not hasattr(core, "backends")


def test_server_module_importable():
    pytest_importorskip = __import__("pytest").importorskip
    pytest_importorskip("flask")
    mod = importlib.import_module("vendor.sc_server.server")
    assert hasattr(mod, "main")


def test_server_token_dir_uses_env(monkeypatch, tmp_path):
    __import__("pytest").importorskip("flask")
    monkeypatch.setenv("SCREEN_CONTROL_DATA_DIR", str(tmp_path))
    # force fresh module so env is read at import time
    for name in [m for m in list(sys.modules) if m.startswith("vendor.sc_server.server")]:
        del sys.modules[name]
    mod = importlib.import_module("vendor.sc_server.server")
    assert str(tmp_path) in mod.SESSION_TOKEN_FILE
    assert str(tmp_path) in mod.APIKEYS_FILE


def test_default_client_factory_uses_vendor(monkeypatch):
    import core.bootstrap as b

    src = __import__("pathlib").Path(b.__file__).read_text()
    assert "/home/xeakaes/screen-control" not in src
    assert "vendor.sc_server.sdk" in src
