
def register(config: dict) -> dict:
    def sandbox_ping(args: dict) -> dict:
        return {"pong": args.get("value", "ok")}

    return {
        "name": "Sandbox Test",
        "version": "1.0.0",
        "description": "Test plugin for sandbox validation.",
        "author": "tests",
        "tools": {"sandbox_ping": sandbox_ping},
    }
