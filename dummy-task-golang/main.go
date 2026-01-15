// Dummy test task for runqy-worker (Go version).
//
// Build:
//
//	go build -o dummy-task .
//
// Test:
//
//	echo '{"task_id":"t1","payload":{"input":"hello"}}' | ./dummy-task
package main

import (
	"fmt"
	"os"

	"github.com/Publikey/runqy-golang/task"
)

// DummyModel simulates a heavy ML model.
type DummyModel struct{}

// Predict returns a prediction string.
func (m *DummyModel) Predict(data string) string {
	return fmt.Sprintf("Predicted: %s", data)
}

func main() {
	// Load the model (runs once before ready signal)
	task.Load(func() (task.Context, error) {
		fmt.Fprintln(os.Stderr, "Loading dummy model...")
		model := &DummyModel{}
		fmt.Fprintln(os.Stderr, "Model loaded!")
		return task.Context{"model": model}, nil
	})

	// Process a task using the loaded model
	task.Register(func(payload task.Payload, ctx task.Context) (task.Result, error) {
		model := ctx["model"].(*DummyModel)

		input := ""
		if v, ok := payload["input"].(string); ok {
			input = v
		}

		prediction := model.Predict(input)

		return task.Result{
			"message":          "Hello from dummy task!",
			"prediction":       prediction,
			"received_payload": payload,
		}, nil
	})

	if err := task.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %s\n", err)
		os.Exit(1)
	}
}
