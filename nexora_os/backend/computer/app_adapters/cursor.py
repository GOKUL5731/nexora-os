from .process_adapter import ProcessBackedAdapter


class CursorAdapter(ProcessBackedAdapter):
    executable_names = ("cursor", "Cursor.exe")
    process_tokens = ("cursor",)
