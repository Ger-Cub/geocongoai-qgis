"""Cloud API connector for GeoCongo services and supplementary entries."""

from __future__ import annotations

from typing import Any, Dict, Optional


class GeoCongoCloudConnector:
    """Minimal connector used to abstract GeoCongo AI API access."""

    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url
        self.api_key = api_key

    def fetch_catalog(self, query: str = ""):
        return {
            "status": "mocked",
            "base_url": self.base_url,
            "query": query,
            "items": [],
            "message": "Connecteur cloud initialisé. À relier au service GeoCongo AI final.",
        }

    def get_account_state(self):
        return {
            "status": "mocked",
            "authenticated": bool(self.api_key),
            "service": "geocongo-ai",
        }
