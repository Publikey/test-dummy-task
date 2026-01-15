"""Dummy test task for runqy-worker."""

import sys
from runqy_task import task, load, run


class DummyModel:
    """Simulates a heavy ML model."""

    def predict(self, data):
        return f"Predicted: {data}"


@load
def setup():
    """Load the model (runs once before ready signal)."""
    print("Loading dummy model...", file=sys.stderr)
    model = DummyModel()
    print("Model loaded!", file=sys.stderr)
    return {"model": model}


@task
def process(payload: dict, ctx: dict) -> dict:
    """Process a task using the loaded model."""
    model = ctx["model"]
    prediction = model.predict(payload.get("input", ""))
    return {
        "message": "Hello from dummy task!",
        "prediction": prediction,
        "received_payload": payload
    }


if __name__ == "__main__":
    run()
