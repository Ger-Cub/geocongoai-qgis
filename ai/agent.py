"""Mtumishi agent orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentStep:
    name: str
    status: str
    detail: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)


class MtumishiAgent:
    """Generic AI layer for QGIS tasks and geoscience workflows."""

    def __init__(self, iface=None, settings=None):
        self.iface = iface
        self.settings = settings
        self.steps: List[AgentStep] = []

    def add_step(self, name, status, detail="", payload=None):
        self.steps.append(AgentStep(name=name, status=status, detail=detail, payload=payload or {}))
        return self.steps[-1]

    def reset(self):
        self.steps = []

    def describe_context(self, project=None, layers=None, canvas=None):
        context = {
            "project": project.name if project else "unknown",
            "layers": len(layers or []),
            "canvas": canvas.extent().toString() if canvas else "unknown",
        }
        return context

    def process(self, prompt: str, context: Optional[Dict[str, Any]] = None):
        context = context or {}
        self.add_step("context", "ok", "Contexte construit pour l’agent Mtumishi", context)
        self.add_step("analysis", "pending", f"Traitement du prompt : {prompt[:120]}...")
        return {
            "status": "ready",
            "prompt": prompt,
            "context": context,
            "steps": [step.__dict__ for step in self.steps],
            "message": "Mtumishi est initialisé et prêt à exécuter les workflows QGIS et géoscientifiques.",
        }
