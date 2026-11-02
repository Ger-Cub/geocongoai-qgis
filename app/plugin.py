"""Modular plugin facade for the GeoCongo AI architecture."""

from __future__ import annotations

from qgis.PyQt.QtWidgets import QAction, QMessageBox

from ..ai.agent import MtumishiAgent
from ..app.bootstrap import safe_startup
from ..core.settings import GeoCongoSettings


class GeoCongoAIModularPlugin:
    """Thin facade exposing the new modular architecture while preserving the old plugin entry points."""

    def __init__(self, iface):
        self.iface = iface
        self.settings = GeoCongoSettings()
        self.agent = MtumishiAgent(iface=iface, settings=self.settings)

    def initialize(self):
        result = safe_startup(self.iface)
        if not result["ok"]:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "GeoCongo AI - Compatibilité",
                "Dépendances ou version QGIS/SDK incompatibles.\n\n"
                + "\n".join(result["diagnostics"].errors or ["Erreur inconnue"]),
            )
        return result

    def create_actions(self):
        actions = []
        action = QAction("Mtumishi - Agent", self.iface.mainWindow())
        action.triggered.connect(self.run_agent)
        actions.append(action)
        return actions

    def run_agent(self):
        response = self.agent.process("Analyse le projet QGIS courant et prépare les workflows géoscientifiques.")
        QMessageBox.information(
            self.iface.mainWindow(),
            "Mtumishi",
            response["message"],
        )
