/**
 * Dummy test task for runqy-worker (Node.js version).
 *
 * Test:
 *   echo '{"task_id":"t1","payload":{"input":"hello"}}' | npx ts-node main.ts
 */

import { task, load, run } from "runqy-task";

/**
 * Simulates a heavy ML model.
 */
class DummyModel {
  predict(data: string): string {
    return `Predicted: ${data}`;
  }
}

// Load the model (runs once before ready signal)
load(() => {
  console.error("Loading dummy model...");
  const model = new DummyModel();
  console.error("Model loaded!");
  return { model };
});

// Process a task using the loaded model
task((payload, ctx) => {
  const model = ctx.model as DummyModel;
  const input = (payload.input as string) || "";
  const prediction = model.predict(input);

  return {
    message: "Hello from dummy task!",
    prediction: prediction,
    received_payload: payload,
  };
});

run();
