"""Bootstrapping utilities for GeoCongo AI applications."""

from __future__ import annotations

import traceback

from qgis.PyQt.QtWidgets import QMessageBox

from ..core.settings import GeoCongoSettings, check_runtime_compatibility


class BootstrapError(RuntimeError):
    """Raised when safe startup is impossible."""


def safe_startup(iface, plugin_name="GeoCongo AI"):
    """Run startup checks before creating the plugin UI."""
    diagnostics = check_runtime_compatibility()
    settings = GeoCongoSettings()

    if diagnostics.errors:
        settings.set("runtime/compatibility_report", diagnostics.to_dict())
        return {
            "ok": False,
            "diagnostics": diagnostics,
            "message": "L'environnement QGIS/Python/SDK est incompatible ou incomplet.",
        }

    settings.set("runtime/compatibility_report", diagnostics.to_dict())
    return {"ok": True, "diagnostics": diagnostics}


def show_bootstrap_error(iface, exc):
    if iface is not None and getattr(iface, "mainWindow", None):
        QMessageBox.critical(
            iface.mainWindow(),
            "GeoCongo AI - erreur de démarrage",
            "Une erreur de démarrage a été détectée.\n\n"
            f"{exc}\n\n"
            f"Trace:\n{traceback.format_exc()}",
        )
