/**
 * Simple one-shot task for runqy-worker (Node.js version).
 *
 * Test:
 *   echo '{"task_id":"t1","payload":{"operation":"echo","data":"hello"}}' | npx ts-node main.ts
 *   echo '{"task_id":"t2","payload":{"operation":"uppercase","data":"hello"}}' | npx ts-node main.ts
 *   echo '{"task_id":"t3","payload":{"operation":"double","data":21}}' | npx ts-node main.ts
 */

import { task, runOnce, Payload } from "runqy-task";

// Simple task that processes once and exits
task((payload: Payload) => {
  const operation = (payload.operation as string) || "echo";
  const data = payload.data;

  switch (operation) {
    case "echo":
      return { result: data };

    case "uppercase":
      if (typeof data === "string") {
        return { result: data.toUpperCase() };
      }
      return { result: data };

    case "double":
      if (typeof data === "number") {
        return { result: data * 2 };
      }
      return { result: data };

    default:
      return { error: `Unknown operation: ${operation}` };
  }
});

runOnce();
