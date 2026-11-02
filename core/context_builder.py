"""Builds a structured context payload for QGIS project and layer analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ProjectContextBuilder:
    """Collect project information and layer metadata for the agent."""

    def __init__(self, iface=None):
        self.iface = iface

    def build_context(self, project=None, layers=None, canvas=None):
        layer_snapshot = []
        if layers:
            for layer in layers:
                try:
                    layer_snapshot.append({
                        "name": layer.name(),
                        "type": layer.type(),
                        "provider": getattr(layer, "providerType", lambda: "unknown")(),
                        "feature_count": getattr(layer, "featureCount", lambda: 0)(),
                    })
                except Exception:
                    layer_snapshot.append({"name": "unknown", "type": "unknown"})

        return {
            "project": project.name() if project and hasattr(project, "name") else "unknown",
            "canvas_extent": canvas.extent().toString() if canvas else "unknown",
            "layers": layer_snapshot,
            "layer_count": len(layer_snapshot),
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
