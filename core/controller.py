"""Controller layer between QGIS UI and Mtumishi agent stack."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..ai.agent import MtumishiAgent


@dataclass
class ControllerState:
    status: str = "idle"
    last_prompt: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class MtumishiController:
    """Orchestrates project context, workflows and agent execution."""

    def __init__(self, iface=None, settings=None):
        self.iface = iface
        self.settings = settings
        self.agent = MtumishiAgent(iface=iface, settings=settings)
        self.state = ControllerState()

    def build_project_context(self, project=None, layers=None, canvas=None):
        return self.agent.describe_context(project=project, layers=layers, canvas=canvas)

    def run(self, prompt: str, context: Optional[Dict[str, Any]] = None):
        self.state.status = "running"
        self.state.last_prompt = prompt
        self.state.errors = []

        try:
            result = self.agent.process(prompt, context or {})
            self.state.status = "ready"
            self.state.steps = result.get("steps", [])
            return result
        except Exception as exc:  # pragma: no cover - defensive
            self.state.status = "error"
            self.state.errors = [str(exc)]
            return {"status": "error", "error": str(exc)}

    def reset(self):
        self.agent.reset()
        self.state = ControllerState()
