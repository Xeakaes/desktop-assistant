import threading
from core.agent.cancellation import CancellationToken, TaskCancelled
import pytest

def test_initial_not_cancelled():
    assert CancellationToken().cancelled is False

def test_cancel_sets_flag():
    t = CancellationToken(); t.cancel(); assert t.cancelled is True

def test_raise_if_cancelled():
    t = CancellationToken(); t.cancel()
    with pytest.raises(TaskCancelled): t.raise_if_cancelled()

def test_wait_returns_false_on_timeout():
    assert CancellationToken().wait(0.05) is False

def test_wait_returns_true_when_cancelled_from_thread():
    t = CancellationToken()
    threading.Timer(0.05, t.cancel).start()
    assert t.wait(1.0) is True
