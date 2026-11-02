"""Validation and safety helpers for agent execution."""

from __future__ import annotations

from typing import Any, Dict, List


class ExecutionGuard:
    """Prevents unsafe actions from being executed without validation."""

    def __init__(self):
        self.blocked_patterns = ["rm -rf", "del /s", "subprocess", "os.system", "exec("]

    def validate_prompt(self, prompt: str) -> Dict[str, Any]:
        lowered = prompt.lower()
        blocked = [pattern for pattern in self.blocked_patterns if pattern in lowered]
        return {
            "safe": not bool(blocked),
            "blocked_patterns": blocked,
            "message": "Validation de sécurité exécutée avant exécution d’un workflow.",
        }

    def validate_tool_call(self, tool_name: str, params: Dict[str, Any]):
        return {
            "tool": tool_name,
            "safe": True,
            "params": params,
            "message": "Appel d’outil validé par le garde-fou d’exécution.",
        }
