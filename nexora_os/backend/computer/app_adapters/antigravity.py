from .process_adapter import ProcessBackedAdapter


class AntigravityAdapter(ProcessBackedAdapter):
    executable_names = ("antigravity", "antigravity.exe")
    process_tokens = ("antigravity",)
