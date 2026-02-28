from __future__ import annotations

from typing import Any

from agent_ext.subagents.base import SubagentResult


class LocalKGShapeProposer:
    name = "local_kg_shape_proposer"

    async def run(self, *, input: Any, metadata: dict[str, Any]) -> SubagentResult:
        """
        Replace with your local agent bridge.
        Input could be a list of Evidence chunks or extracted entities.
        """
        # Minimal heuristic starter:
        out = {
            "node_types": ["Person", "Org", "Location", "Document"],
            "edge_types": ["MENTIONS", "AFFILIATED_WITH", "LOCATED_IN"],
            "notes": "Starter schema — replace with local corpus-driven proposal",
        }
        return SubagentResult(ok=True, output=out, metadata={"heuristic": True})
