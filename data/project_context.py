"""Project context model for Mtumishi agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ProjectContext:
    project_name: str = "unknown"
    canvas_extent: str = "unknown"
    layer_count: int = 0
    layers: List[Dict[str, Any]] = field(default_factory=list)
