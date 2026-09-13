from __future__ import annotations

from typing import Any


class Verifier:
    """
    Independent verification module that checks if an action truly succeeded.
    """
    def verify(self, goal: str, execution_results: list[dict[str, Any]], observations: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Determines whether the executed steps successfully achieved the goal based on observations.
        """
        if not execution_results:
            return {"verified": False, "reason": "No execution results"}

        all_ok = all(res.get("ok", False) for res in execution_results)
        goal_lower = goal.lower()

        if "file" in goal_lower and any(word in goal_lower for word in ("create", "write", "read", "delete", "remove")):
            tool_results = [res.get("result", {}) for res in execution_results if res.get("action") != "verify_result"]
            if not tool_results:
                return {"verified": False, "status": "FAILED", "reason": "No filesystem execution result"}
            verified_tool = False
            for result in tool_results:
                verification = result.get("verification") if isinstance(result, dict) else None
                if isinstance(verification, dict):
                    if any(word in goal_lower for word in ("create", "write")):
                        verified_tool = bool(result.get("ok") and verification.get("exists") and verification.get("is_file") and verification.get("content_matches"))
                    elif "read" in goal_lower:
                        verified_tool = bool(result.get("ok") and verification.get("exists") and verification.get("is_file") and "content" in result)
                    elif any(word in goal_lower for word in ("delete", "remove")):
                        verified_tool = bool(result.get("ok") and verification.get("exists") is False)
                if verified_tool:
                    break
            if not verified_tool:
                return {"verified": False, "status": "FAILED", "reason": "Filesystem side effect was not verified"}

        # In a deep learning/LLM system, this would ask an LLM to evaluate the observations
        # against the original goal.

        status = "SUCCESS" if all_ok else "FAILED"

        return {
            "verified": all_ok,
            "status": status,
            "reason": "All steps executed successfully" if all_ok else "One or more steps failed"
        }
