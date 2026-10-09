"""Cooperative cancellation for agent tasks and tools.

Contract (spec §3.5): the token is a flag, not a thread killer. Tools and
the runtime must poll it between steps. Setting the token does not stop
non-cancellable in-flight work (e.g. a blocked HTTP call); HTTP timeouts
bound the hang, and the runtime discards late results after cancellation.
"""

from __future__ import annotations

import threading


class TaskCancelled(Exception):
    """Raised when an operation observes a cancelled token."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise TaskCancelled()

    def wait(self, timeout: float) -> bool:
        """Block up to timeout seconds; True if cancelled in that window."""
        return self._event.wait(timeout)
