from pathlib import Path


def test_core_has_no_qt_imports():
    core = Path(__file__).resolve().parents[2] / "core"
    for f in core.rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert "PySide6" not in src and "PyQt" not in src, f"Qt leaked into {f}"
