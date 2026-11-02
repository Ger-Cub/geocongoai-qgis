"""Utilities for safe QGIS layer and canvas operations."""

from __future__ import annotations

from typing import Any, Dict, Optional


class QGISLayerTools:
    """Exposure of common QGIS operations as controlled, agent-friendly helpers."""

    def __init__(self, iface=None):
        self.iface = iface

    def list_layers(self):
        if self.iface is None:
            return []
        return [layer.name() for layer in self.iface.mapCanvas().layers()]

    def zoom_to_layer(self, layer_name: str):
        if self.iface is None:
            return {"status": "no_iface", "layer": layer_name}
        layers = self.iface.mapCanvas().layers()
        for layer in layers:
            if layer.name() == layer_name:
                self.iface.mapCanvas().zoomToFullExtent()
                return {"status": "ok", "layer": layer_name}
        return {"status": "not_found", "layer": layer_name}

    def get_canvas_extent(self):
        if self.iface is None:
            return {"status": "no_iface", "extent": "unknown"}
        return {"status": "ok", "extent": self.iface.mapCanvas().extent().toString()}
