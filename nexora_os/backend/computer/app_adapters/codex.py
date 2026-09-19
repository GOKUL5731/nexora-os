from .process_adapter import ProcessBackedAdapter


class CodexAdapter(ProcessBackedAdapter):
    executable_names = ("codex", "codex.exe")
    # The installed Windows Codex desktop shell currently identifies its
    # process as ChatGPT.exe. This detects presence only; it does not imply a
    # supported prompt transport.
    process_tokens = ("codex", "chatgpt")
