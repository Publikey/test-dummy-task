// Simple one-shot task for runqy-worker (Go version).
//
// Build:
//
//	go build -o simple-task .
//
// Test:
//
//	echo '{"task_id":"t1","payload":{"operation":"echo","data":"hello"}}' | ./simple-task
//	echo '{"task_id":"t2","payload":{"operation":"uppercase","data":"hello"}}' | ./simple-task
//	echo '{"task_id":"t3","payload":{"operation":"double","data":21}}' | ./simple-task
package main

import (
	"fmt"
	"os"
	"strings"

	"github.com/Publikey/runqy-golang/task"
)

func main() {
	// Simple task that processes once and exits
	task.Register(func(payload task.Payload, ctx task.Context) (task.Result, error) {
		operation := "echo"
		if v, ok := payload["operation"].(string); ok {
			operation = v
		}

		data := payload["data"]

		switch operation {
		case "echo":
			return task.Result{"result": data}, nil

		case "uppercase":
			if s, ok := data.(string); ok {
				return task.Result{"result": strings.ToUpper(s)}, nil
			}
			return task.Result{"result": data}, nil

		case "double":
			if n, ok := data.(float64); ok { // JSON numbers are float64
				return task.Result{"result": n * 2}, nil
			}
			return task.Result{"result": data}, nil

		default:
			return task.Result{"error": fmt.Sprintf("Unknown operation: %s", operation)}, nil
		}
	})

	if err := task.RunOnce(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %s\n", err)
		os.Exit(1)
	}
}
