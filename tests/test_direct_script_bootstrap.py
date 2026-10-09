"""Direct-script bootstrap tests.

Regression: running an entry module as a plain script (python ui/app.py)
set sys.path[0] to the module's directory, so sibling packages (core, ui)
were not importable -> ModuleNotFoundError. The entry files now insert the
repo root into sys.path before any core/ui imports.

GUI entry points launch a window and do not exit, so those tests start the
process, give it a moment, and assert it did not die with ModuleNotFoundError.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}


def _run_to_completion(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO / script), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        env=ENV,
        timeout=60,
    )


def _launch_and_check(script: str) -> subprocess.CompletedProcess:
    """Start a GUI entry point, let it run briefly, then kill it.

    Success = process is still alive after the grace period (GUI launched)
    and stderr has no ModuleNotFoundError.
    """
    proc = subprocess.Popen(
        [sys.executable, str(REPO / script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO),
        env=ENV,
        text=True,
    )
    try:
        time.sleep(4)
        # Still running => it got past imports and is in the GUI loop.
        alive = proc.poll() is None
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        _, stderr = proc.communicate(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    if not alive:
        raise AssertionError(f"{script} exited early:\n{stderr}")
    assert "No module named 'core'" not in stderr
    return proc


def test_entry_direct_script_version():
    """python app_entry/entry.py --version must not fail with No module named 'core'."""
    proc = _run_to_completion("app_entry/entry.py", "--version")
    assert "No module named 'core'" not in proc.stderr
    assert proc.returncode == 0
    assert proc.stdout.strip()  # prints a version string


def test_ui_app_direct_script_imports_core():
    """python ui/app.py must get past the core import and launch."""
    _launch_and_check("ui/app.py")


def test_avatar_app_direct_script_imports_core():
    """python ui/avatar_app.py must get past the core import and launch."""
    _launch_and_check("ui/avatar_app.py")
