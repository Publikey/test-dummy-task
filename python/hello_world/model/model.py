import sys


class Model:
    def __init__(self):
        pass

    def load(self):
        print("Dummy model loaded", file=sys.stderr)
        return self

    def predict(self, model_input: dict) -> dict:
        """Dummy predict that echoes input with hello world response."""
        return {
            "uuid": model_input.get("id", "test-uuid"),
            "data": [
                {
                    "result": "Hello World! This is a dummy response.",
                    "seed": 12345
                }
            ],
            "errors": [],
            "received_input": model_input
        }
