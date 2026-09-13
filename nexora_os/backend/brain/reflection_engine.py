from __future__ import annotations

from typing import Any


class ReflectionEngine:
    """
    Evaluates task outcomes and creates structured memory chunks for future learning.
    """
    def __init__(self, memory_engine: Any) -> None:
        self.memory = memory_engine

    def reflect(self, goal: str, verification_result: dict[str, Any], plan: list[dict[str, Any]], execution_results: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Synthesizes experience into a structured format to store in memory.
        """
        status = verification_result.get("status", "UNKNOWN")

        # Analyze which strategy worked and which failed
        failed_steps = [res for res in execution_results if not res.get("ok")]
        success_steps = [res for res in execution_results if res.get("ok")]
        meaningful_steps = [res for res in success_steps if res.get("action") != "verify_result"] or success_steps

        reflection_data = {
            "type": "experience",
            "goal": goal,
            "status": status,
            "failed_steps_count": len(failed_steps),
            "success_steps_count": len(success_steps),
            "tags": ["brain", "experience", status.lower()]
        }

        # Create a text summary for embedding and user response
        import json
        if meaningful_steps and "message" in meaningful_steps[-1].get("result", {}):
            summary = meaningful_steps[-1]["result"]["message"]
        elif meaningful_steps and "text" in meaningful_steps[-1].get("result", {}):
            summary = meaningful_steps[-1]["result"]["text"]
        elif meaningful_steps:
            # Drop noisy fields before serializing
            res_clean = {k: v for k, v in meaningful_steps[-1].get("result", {}).items() if k not in ["ok", "path", "image"]}
            summary = json.dumps(res_clean) if res_clean else "Action completed successfully."
        elif failed_steps:
            summary = f"Failed on action: {failed_steps[0].get('action')} - Error: {failed_steps[0].get('error')}"
        else:
            summary = "Action completed."

        reflection_data["summary"] = summary

        # Store in memory
        if self.memory:
            self.memory.store(summary, "episodic", reflection_data["tags"])

        return reflection_data
