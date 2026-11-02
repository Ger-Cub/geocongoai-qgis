"""Mining exploration workflows for Mtumishi."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MiningExplorationWorkflow:
    """Higher-level workflow to orchestrate mineral exploration tasks."""

    def __init__(self, iface=None):
        self.iface = iface

    def prepare_drillhole_dataset(self, layers: Optional[List[Any]] = None):
        return {
            "status": "ready",
            "layers": [layer.name() for layer in (layers or []) if hasattr(layer, "name")],
            "workflow": "prepare_drillhole_dataset",
            "message": "Préparation du jeu de forages démarrée dans le moteur d’exploration minière.",
        }

    def estimate_resources(self, cutoff: float = 0.5, method: str = "IDW"):
        return {
            "status": "mocked",
            "method": method,
            "cutoff": cutoff,
            "message": "Estimation de ressources préparée pour exécution avec le moteur Chimbua.",
        }
