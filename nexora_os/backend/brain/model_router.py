from __future__ import annotations

from typing import Any, Callable

# Maps task types to model name substrings (in priority order)
TASK_TO_MODEL_HINTS: dict[str, list[str]] = {
    "reasoning":  ["llama", "mistral", "gemma", "phi", "qwen"],
    "coding":     ["codellama", "deepseek-coder", "qwen2.5-coder", "starcoder", "llama"],
    "vision":     ["llava", "moondream", "bakllava", "minicpm"],
    "embedding":  ["nomic", "mxbai", "all-minilm"],
    "math":       ["mathstral", "wizard-math", "llama"],
}


class ModelRouter:
    """
    Local-first model router using Ollama.
    Discovers installed models and selects the best match for each task type.
    """

    def __init__(self, model_status_provider: Callable[[], dict[str, Any]]) -> None:
        self.model_status_provider = model_status_provider

    def discover_models(self) -> dict[str, Any]:
        """Returns the full model status from Ollama."""
        return self.model_status_provider()

    def categorize_models(self, models: list[str]) -> dict[str, list[str]]:
        """Categorizes available models by task type by matching name substrings."""
        categories: dict[str, list[str]] = {task: [] for task in TASK_TO_MODEL_HINTS}
        for model in models:
            model_lower = model.lower()
            for task, hints in TASK_TO_MODEL_HINTS.items():
                if any(hint in model_lower for hint in hints):
                    categories[task].append(model)
        return categories

    def route(self, task_type: str, requirements: dict[str, Any]) -> dict[str, Any]:
        """
        Selects the best available model for the given task type.
        Falls back to any available model if no task-specific match is found.
        """
        status = self.model_status_provider()

        if not status.get("ready"):
            return {
                "ok": False,
                "error": "Ollama is not available or no models are installed.",
                "selected_model": None,
                "all_models": [],
            }

        all_models: list[str] = status.get("models", [])
        categories = self.categorize_models(all_models)

        # Try to find a task-specific model
        hints = TASK_TO_MODEL_HINTS.get(task_type, [])
        matched: list[str] = []
        for hint in hints:
            for m in all_models:
                if hint in m.lower() and m not in matched:
                    matched.append(m)

        selected = matched[0] if matched else (all_models[0] if all_models else None)

        return {
            "ok": bool(selected),
            "selected_model": selected,
            "provider": "ollama",
            "type": task_type,
            "all_models": all_models,
            "categories": categories,
            "fallback_used": bool(selected and not matched),
        }
