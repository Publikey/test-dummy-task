"""Simple one-shot task for runqy-worker."""

from runqy_python import task, run_once


@task
def process(payload: dict) -> dict:
    """Simple task that processes once and exits."""
    operation = payload.get("operation", "echo")
    data = payload.get("data")

    if operation == "echo":
        return {"result": data}
    elif operation == "uppercase":
        return {"result": data.upper() if isinstance(data, str) else data}
    elif operation == "double":
        return {"result": data * 2 if isinstance(data, (int, float)) else data}
    else:
        return {"error": f"Unknown operation: {operation}"}


if __name__ == "__main__":
    run_once()
