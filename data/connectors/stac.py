"""STAC connector for remote sensing and geobotanical analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class StacConnector:
    """Simplified STAC connector for GeoCongo AI workflows."""

    def __init__(self, catalog_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"):
        self.catalog_url = catalog_url

    def search_scenes(self, bbox=None, date_range=None, cloud_cover=None):
        return {
            "catalog_url": self.catalog_url,
            "bbox": bbox,
            "date_range": date_range,
            "cloud_cover": cloud_cover,
            "items": [],
            "status": "mocked",
            "message": "Connecteur STAC initialisé. À brancher sur le catalogue réel selon l’installation finale.",
        }

    def compute_indices(self, dataset_name: str, indices: Optional[List[str]] = None):
        return {
            "dataset_name": dataset_name,
            "indices": indices or ["NDVI", "NDMI", "MSV_COMPOSITE"],
            "status": "mocked",
        }
