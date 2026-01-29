# Wan Video Generation Task

Generate videos using Wan2.1 FusionX GGUF models (Image-to-Video and Text-to-Video).

## Supported Models

| Model | Type | Description |
|-------|------|-------------|
| `wan21-fusionx-i2v` | Image-to-Video | Generates video from an input image |
| `wan21-fusionx-t2v` | Text-to-Video | Generates video from text prompt only |

## Requirements

- NVIDIA GPU with CUDA support
- ~24GB+ VRAM recommended for 14B models
- Models are loaded from local paths or downloaded from Hugging Face

**Model paths (optional, will download if missing):**
- I2V: `/root/data/Wan2.1_I2V_14B_FusionX-Q8_0.gguf`
- T2V: `/root/data/Wan2.1_T2V_14B_FusionX-Q8_0.gguf`

## Payload Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model_name` | string | No | `wan21-fusionx-i2v` | Model to use |
| `prompt` | string | Yes | - | Video description |
| `negative_prompt` | string | No | (Chinese defaults) | What to avoid |
| `img_url` | string | I2V only | - | Input image URL (required for I2V) |
| `width` | int | T2V only | 1024 | Video width |
| `height` | int | T2V only | 1024 | Video height |
| `num_frames` | int | No | 121 | Number of frames |
| `fps` | int | No | 18 | Frames per second |
| `quality` | string | No | `standard` | `standard` (6 steps) or `high` (10 steps) |
| `id` | string | No | `xyz` | Task identifier for webhook |
| `webhook_url` | string | No | - | URL to POST results to |

**Note:** Dimensions are automatically adjusted to be divisible by 32 and under 399,360 total pixels.

## Response Schema

```json
{
  "uuid": "task-123",
  "data": [
    {
      "result": "base64-encoded-mp4...",
      "seed": 12345678
    }
  ],
  "errors": []
}
```

---

## Usage

### 1. Local Development (No Server Required)

Test the task directly by piping JSON to the Python script:

```bash
# Install dependencies
pip install -r requirements.txt

# Run I2V task
echo '{"task_id":"t1","payload":{"model_name":"wan21-fusionx-i2v","prompt":"A cat walking gracefully","img_url":"https://example.com/cat.jpg"}}' | python main.py

# Run T2V task
echo '{"task_id":"t2","payload":{"model_name":"wan21-fusionx-t2v","prompt":"A dog running in a field","width":832,"height":480}}' | python main.py
```

**Expected output:**
```json
{"status": "ready"}
{"task_id": "t1", "result": {"uuid": "xyz", "data": [{"result": "AAAAIGZ0eXBpc29t...", "seed": 12345678}], "errors": []}, "error": null, "retry": false}
```

**More examples:**
```bash
# High quality I2V
echo '{"task_id":"t3","payload":{"model_name":"wan21-fusionx-i2v","prompt":"Gentle camera zoom on a landscape","img_url":"https://example.com/landscape.jpg","quality":"high","num_frames":81}}' | python main.py

# T2V with custom dimensions
echo '{"task_id":"t4","payload":{"model_name":"wan21-fusionx-t2v","prompt":"Ocean waves crashing on rocks","width":1280,"height":720,"fps":24}}' | python main.py

# With webhook callback
echo '{"task_id":"t5","payload":{"id":"my-task-123","model_name":"wan21-fusionx-t2v","prompt":"A sunset timelapse","webhook_url":"https://your-server.com/webhook"}}' | python main.py
```

---

### 2. Using runqy CLI (Server Required)

First, ensure you're logged in and the queue is created on the server.

**Linux/macOS (bash):**
```bash
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue I2V task
runqy task enqueue -q wan-video -p '{"model_name":"wan21-fusionx-i2v","prompt":"A person smiling","img_url":"https://example.com/portrait.jpg"}'

# Enqueue T2V task
runqy task enqueue -q wan-video -p '{"model_name":"wan21-fusionx-t2v","prompt":"Fireworks exploding in the night sky"}'
```

**Windows (PowerShell) - use `cmd /c`:**
```powershell
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue I2V task
cmd /c 'runqy task enqueue -q wan-video -p "{\"model_name\":\"wan21-fusionx-i2v\",\"prompt\":\"A flower blooming\",\"img_url\":\"https://example.com/flower.jpg\"}"'

# Enqueue T2V task
cmd /c 'runqy task enqueue -q wan-video -p "{\"model_name\":\"wan21-fusionx-t2v\",\"prompt\":\"Clouds moving across the sky\"}"'
```

**Check task status:**
```bash
# List tasks in queue
runqy task list wan-video

# Get specific task details
runqy task get wan-video <task-id>

# List completed tasks
runqy task list wan-video --state completed
```

---

### 3. Using REST API (Server Required)

**Endpoint:** `POST /queue/add`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <your-api-key>
```

**cURL examples:**

```bash
# I2V request
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "wan-video",
    "timeout": 600000,
    "data": {
      "model_name": "wan21-fusionx-i2v",
      "prompt": "A bird taking flight",
      "img_url": "https://example.com/bird.jpg",
      "num_frames": 81,
      "fps": 24
    }
  }'

# T2V request
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "wan-video",
    "timeout": 600000,
    "data": {
      "model_name": "wan21-fusionx-t2v",
      "prompt": "A waterfall in a forest",
      "width": 832,
      "height": 480,
      "quality": "high"
    }
  }'

# With webhook
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "wan-video",
    "timeout": 600000,
    "data": {
      "id": "my-custom-id",
      "model_name": "wan21-fusionx-t2v",
      "prompt": "Northern lights dancing",
      "webhook_url": "https://your-callback.com/results"
    }
  }'
```

**Get task result:**
```bash
curl -X GET https://your-server:3000/queue/<task-id> \
  -H "Authorization: Bearer your-api-key"
```

**Python example:**

```python
import requests

# Enqueue I2V task
response = requests.post(
    "https://your-server:3000/queue/add",
    headers={
        "Authorization": "Bearer your-api-key",
        "Content-Type": "application/json"
    },
    json={
        "queue": "wan-video",
        "timeout": 600000,
        "data": {
            "model_name": "wan21-fusionx-i2v",
            "prompt": "Gentle movement and camera pan",
            "img_url": "https://example.com/scene.jpg",
            "num_frames": 121,
            "fps": 18,
            "quality": "high"
        }
    }
)
task_info = response.json()
task_id = task_info["info"]["id"]
print(f"Task ID: {task_id}")

# Get result
result = requests.get(
    f"https://your-server:3000/queue/{task_id}",
    headers={"Authorization": "Bearer your-api-key"}
)
print(result.json())
```

---

## Notes

- Both models are loaded to CPU at startup, then swapped to GPU on demand
- Model swapping between I2V and T2V happens automatically based on `model_name`
- Video output is saved to `./output/{uuid}.mp4` and returned as base64
- Timeout should be set higher (e.g., 600000ms) for video generation tasks
