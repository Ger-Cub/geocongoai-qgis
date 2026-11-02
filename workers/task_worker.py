"""Simple background-task wrapper for long-running QGIS workflows."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional


class TaskWorker:
    """Runs a task in a background thread with a simple callback API."""

    def __init__(self, callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.callback = callback
        self._thread = None

    def run(self, func, *args, **kwargs):
        def target():
            result = func(*args, **kwargs)
            if self.callback is not None:
                self.callback({"status": "done", "result": result})

        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()
        return {"status": "started", "thread": self._thread}
