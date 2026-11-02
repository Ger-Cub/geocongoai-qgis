"""Remote sensing workflow tools for Mtumishi."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class RemoteSensingTools:
    """A lightweight integration point for STAC and geobotanical routines."""

    def __init__(self, connector=None):
        self.connector = connector

    def search_and_analyze(self, bbox=None, dates=None, indices=None):
        if self.connector is not None:
            return self.connector.search_scenes(bbox=bbox, date_range=dates, cloud_cover=None)
        return {
            "status": "mocked",
            "bbox": bbox,
            "dates": dates,
            "indices": indices or ["NDVI", "MSV_COMPOSITE"],
            "message": "Analyse télédétection préparée avec le moteur de données STAC.",
        }
