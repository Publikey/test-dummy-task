# Google Veo Video Generation Task

Generate videos using Google Veo models.

## Supported Models

| Model | Description |
|-------|-------------|
| `veo-3.1-generate-preview` | Standard video generation |
| `veo-3.1-fast-generate-preview` | Faster video generation |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google API key |

## Payload Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model name |
| `prompt` | string | Yes | - | Video description |
| `negative_prompt` | string | No | - | What to avoid |
| `aspect_ratio` | string | No | - | `16:9` or `9:16` |
| `resolution` | string | No | - | `720p` or `1080p` |
| `duration_seconds` | int | No | - | `4`, `6`, or `8` |
| `person_generation` | string | No | - | `allow_all` or `allow_adult` |
| `seed` | int | No | - | For reproducibility |
| `poll_interval` | int | No | 10 | Seconds between status checks |
| `max_wait` | int | No | 600 | Maximum wait time in seconds |

## Response Schema

```json
{
  "videos": ["base64..."],
  "model": "veo-3.1-generate-preview",
  "provider": "google",
  "mime_type": "video/mp4",
  "operation_name": "operations/..."
}
```

---

## Usage

### 1. Local Development (No Server Required)

Test the task directly by piping JSON to the Python script:

```bash
# Set environment variables
export GOOGLE_API_KEY="your-api-key"

# Install dependencies
pip install -r requirements.txt

# Run task
echo '{"task_id":"t1","payload":{"model":"veo-3.1-generate-preview","prompt":"Ocean waves crashing on a beach"}}' | python main.py
```

**Expected output:**
```json
{"status": "ready"}
{"task_id": "t1", "result": {"videos": ["AAAAIGZ0eXBpc29t..."], "model": "veo-3.1-generate-preview", "provider": "google", "mime_type": "video/mp4", "operation_name": "operations/..."}, "error": null, "retry": false}
```

**Note:** Video generation takes time (typically 1-5 minutes). The task will poll until complete.

**More examples:**
```bash
# With all options
echo '{"task_id":"t2","payload":{"model":"veo-3.1-generate-preview","prompt":"A whale swimming gracefully in the deep ocean","negative_prompt":"blurry, low quality","aspect_ratio":"16:9","resolution":"1080p","duration_seconds":6}}' | python main.py

# Fast model
echo '{"task_id":"t3","payload":{"model":"veo-3.1-fast-generate-preview","prompt":"A time-lapse of clouds moving","aspect_ratio":"16:9"}}' | python main.py

# Vertical video (mobile)
echo '{"task_id":"t4","payload":{"model":"veo-3.1-generate-preview","prompt":"A person walking through a city street","aspect_ratio":"9:16","resolution":"1080p"}}' | python main.py

# With seed for reproducibility
echo '{"task_id":"t5","payload":{"model":"veo-3.1-generate-preview","prompt":"A serene forest scene","seed":12345}}' | python main.py
```

---

### 2. Using runqy CLI (Server Required)

First, ensure you're logged in and the queue is created on the server.

**Linux/macOS (bash):**
```bash
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue a task
runqy task enqueue -q google-video -p '{"model":"veo-3.1-generate-preview","prompt":"Ocean waves crashing on a beach"}'
```

**Windows (PowerShell) - use `cmd /c`:**
```powershell
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue a task
cmd /c 'runqy task enqueue -q google-video -p "{\"model\":\"veo-3.1-generate-preview\",\"prompt\":\"Ocean waves crashing on a beach\"}"'
```

**More examples (Windows PowerShell):**
```powershell
# With full options
cmd /c 'runqy task enqueue -q google-video -p "{\"model\":\"veo-3.1-generate-preview\",\"prompt\":\"A majestic eagle flying over mountains\",\"negative_prompt\":\"blurry\",\"aspect_ratio\":\"16:9\",\"resolution\":\"1080p\",\"duration_seconds\":8}"'

# Fast generation
cmd /c 'runqy task enqueue -q google-video -p "{\"model\":\"veo-3.1-fast-generate-preview\",\"prompt\":\"Abstract flowing colors\"}"'

# Vertical video
cmd /c 'runqy task enqueue -q google-video -p "{\"model\":\"veo-3.1-generate-preview\",\"prompt\":\"A dancer performing\",\"aspect_ratio\":\"9:16\",\"duration_seconds\":6}"'
```

**Check task status:**
```bash
# List tasks in queue
runqy task list google-video

# Get specific task details (check if still processing)
runqy task get google-video <task-id>

# List active tasks (currently processing)
runqy task list google-video --state active

# List completed tasks
runqy task list google-video --state completed
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
# Basic request
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-video",
    "timeout": 660000,
    "data": {
      "model": "veo-3.1-generate-preview",
      "prompt": "Ocean waves crashing on a beach"
    }
  }'

# With all options
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-video",
    "timeout": 660000,
    "data": {
      "model": "veo-3.1-generate-preview",
      "prompt": "A cinematic shot of a spacecraft flying through an asteroid field",
      "negative_prompt": "blurry, low quality, distorted",
      "aspect_ratio": "16:9",
      "resolution": "1080p",
      "duration_seconds": 8
    }
  }'

# Fast model
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-video",
    "timeout": 300000,
    "data": {
      "model": "veo-3.1-fast-generate-preview",
      "prompt": "Colorful smoke swirling",
      "aspect_ratio": "16:9"
    }
  }'
```

**Flat format (alternative):**
```bash
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-video",
    "timeout": 660000,
    "model": "veo-3.1-generate-preview",
    "prompt": "Ocean waves crashing on a beach",
    "aspect_ratio": "16:9",
    "resolution": "1080p"
  }'
```

**Get task result:**
```bash
curl -X GET https://your-server:3000/queue/<task-id> \
  -H "Authorization: Bearer your-api-key"
```

**PowerShell examples:**

```powershell
# Basic request
$body = @{
    queue = "google-video"
    timeout = 660000
    data = @{
        model = "veo-3.1-generate-preview"
        prompt = "Ocean waves crashing on a beach"
        aspect_ratio = "16:9"
        resolution = "1080p"
        duration_seconds = 6
    }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Uri "https://your-server:3000/queue/add" `
    -Method Post `
    -Headers @{ "Authorization" = "Bearer your-api-key" } `
    -ContentType "application/json" `
    -Body $body

# Get task result
Invoke-RestMethod -Uri "https://your-server:3000/queue/<task-id>" `
    -Headers @{ "Authorization" = "Bearer your-api-key" }
```

**Python example:**

```python
import requests
import time

# Enqueue task
response = requests.post(
    "https://your-server:3000/queue/add",
    headers={
        "Authorization": "Bearer your-api-key",
        "Content-Type": "application/json"
    },
    json={
        "queue": "google-video",
        "timeout": 660000,  # 11 minutes (video generation is slow)
        "data": {
            "model": "veo-3.1-generate-preview",
            "prompt": "A whale swimming gracefully in the deep ocean",
            "aspect_ratio": "16:9",
            "resolution": "1080p",
            "duration_seconds": 6
        }
    }
)
task_info = response.json()
task_id = task_info["info"]["id"]
print(f"Task ID: {task_id}")

# Poll for result (video generation takes time)
while True:
    result = requests.get(
        f"https://your-server:3000/queue/{task_id}",
        headers={"Authorization": "Bearer your-api-key"}
    )
    data = result.json()
    state = data.get("info", {}).get("state")
    print(f"State: {state}")

    if state == "completed":
        print("Video generated!")
        print(data)
        break
    elif state in ["archived", "failed"]:
        print(f"Task failed: {data}")
        break

    time.sleep(10)  # Poll every 10 seconds
```

---

## Notes

- Video generation is a **long-running operation** and can take 1-5 minutes
- Set appropriate `timeout` values (recommend 600000-660000 ms for standard, 300000 ms for fast)
- The task internally polls Google's API every 10 seconds by default
- Maximum wait time is 600 seconds (10 minutes) by default
- Use `veo-3.1-fast-generate-preview` for faster (but potentially lower quality) results
