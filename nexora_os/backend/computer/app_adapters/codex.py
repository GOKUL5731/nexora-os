from .process_adapter import ProcessBackedAdapter


class CodexAdapter(ProcessBackedAdapter):
    executable_names = ("codex", "codex.exe")
    process_tokens = ("codex",)
