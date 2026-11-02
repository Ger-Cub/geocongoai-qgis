"""Centralized settings and compatibility helpers for GeoCongo AI QGIS."""

import json
import os
import sys

from qgis.PyQt.QtCore import QSettings


class GeoCongoSettings:
    """Thin wrapper around QGIS settings with safe defaults."""

    def __init__(self, organization="GeoCongoAI", app_name="GeoCongoAIPlugin"):
        self.organization = organization
        self.app_name = app_name
        self.settings = QSettings(self.organization, self.app_name)

    def get(self, key, default=None):
        value = self.settings.value(key, default)
        if isinstance(value, str):
            return value.strip()
        return value

    def set(self, key, value):
        self.settings.setValue(key, value)

    def remove(self, key):
        self.settings.remove(key)

    def get_json(self, key, default=None):
        raw = self.get(key, default)
        if raw in (None, ""):
            return default if default is not None else {}
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return default if default is not None else {}

    def set_json(self, key, value):
        self.settings.setValue(key, json.dumps(value))


class CompatStatus:
    """Lightweight compatibility report for Python / QGIS / SDK."""

    def __init__(self, python_version=None, qgis_version=None, sdk_installed=False, sdk_version=None, errors=None):
        self.python_version = python_version or sys.version.split()[0]
        self.qgis_version = qgis_version or "unknown"
        self.sdk_installed = sdk_installed
        self.sdk_version = sdk_version
        self.errors = errors or []

    def to_dict(self):
        return {
            "python_version": self.python_version,
            "qgis_version": self.qgis_version,
            "sdk_installed": self.sdk_installed,
            "sdk_version": self.sdk_version,
            "errors": self.errors,
        }


def check_runtime_compatibility():
    """Basic compatibility checker used for safe startup."""
    errors = []

    try:
        import qgis
        qgis_version = getattr(qgis, "QGIS_VERSION", "unknown")
    except Exception:
        qgis_version = "unknown"
        errors.append("QGIS runtime unavailable.")

    try:
        import geocongoai  # noqa: F401
        sdk_installed = True
        try:
            from importlib import metadata
            sdk_version = metadata.version("geocongoai")
        except Exception:
            sdk_version = "unknown"
    except Exception:
        sdk_installed = False
        sdk_version = None
        errors.append("geocongoai SDK not installed in current QGIS Python environment.")

    if sys.version_info < (3, 9):
        errors.append("Python version too old for the plugin.")

    return CompatStatus(
        python_version=sys.version.split()[0],
        qgis_version=qgis_version,
        sdk_installed=sdk_installed,
        sdk_version=sdk_version,
        errors=errors,
    )
