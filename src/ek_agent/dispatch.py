"""Deliver background events without calling a GUI API from a worker thread."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class MainThreadDispatcher:
    def __init__(self) -> None:
        self._owner = threading.get_ident()
        self._pending: queue.SimpleQueue[tuple[Callable[..., Any], tuple[Any, ...]]] = (
            queue.SimpleQueue()
        )

    def submit(self, callback: Callable[..., Any], *args: Any) -> None:
        self._pending.put((callback, args))

    def drain(self) -> None:
        if threading.get_ident() != self._owner:
            raise RuntimeError("GUI callbacks must run on the main thread")
        # Bound each batch so a busy worker cannot starve the GUI event loop.
        for _ in range(100):
            try:
                callback, args = self._pending.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args)
            except Exception:
                logger.exception("GUI callback failed")
