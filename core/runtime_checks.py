"""Runtime validation helpers for Python, QGIS and SDK compatibility."""

from __future__ import annotations

import importlib
import sys
from typing import List


class RuntimeCheckResult:
    """Result of compatibility checks."""

    def __init__(self, ok: bool = True, messages: List[str] = None):
        self.ok = ok
        self.messages = messages or []

    def __bool__(self):
        return self.ok


def validate_runtime_environment():
    """Checks the QGIS runtime and the SDK installation in the current Python env."""
    messages: List[str] = []

    if sys.version_info < (3, 9):
        messages.append("Python version too old. Use Python 3.9+.")

    try:
        import qgis  # noqa: F401
    except Exception:
        messages.append("QGIS Python runtime is not available in this environment.")

    try:
        import geocongoai  # noqa: F401
    except Exception:
        messages.append("SDK geocongoai is not installed in the QGIS Python environment.")

    return RuntimeCheckResult(ok=not messages, messages=messages)
