#!/usr/bin/env python3
import sys
import json
from model.model import Model


def main():
    # Load model (this can take minutes for large models)
    model_instance = Model().load()

    # Signal ready to Go worker
    print(json.dumps({"status": "ready"}))
    sys.stdout.flush()

    # Process tasks from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            task = json.loads(line)
            task_id = task["task_id"]
            payload = task.get("payload", {})

            # Call existing predict method
            result = model_instance.predict(payload)

            # Send success response
            response = {"task_id": task_id, "result": result}
            print(json.dumps(response))
            sys.stdout.flush()

        except Exception as e:
            # Send error response
            response = {
                "task_id": task.get("task_id", "unknown"),
                "error": str(e),
                "retry": False  # Model errors are usually permanent
            }
            print(json.dumps(response))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
