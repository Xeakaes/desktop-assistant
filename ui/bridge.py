"""EventBus → Qt signal bridge (thread-safe queued delivery to the GUI thread)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.events import Event, EventBus


class QtBridge(QObject):
    sig = Signal(object)

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        bus.subscribe("*", self._on_event)

    def _on_event(self, event: Event) -> None:
        self.sig.emit(event)
