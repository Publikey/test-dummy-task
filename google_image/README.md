# Google Gemini Image Generation Task

Generate images using Google Gemini models.

## Supported Models

| Model | Features |
|-------|----------|
| `gemini-2.5-flash-image` | Fast image generation |
| `gemini-3-pro-image-preview` | Higher quality, supports `image_size` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | Google API key |

## Payload Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model name |
| `prompt` | string | Yes | - | Image description |
| `aspect_ratio` | string | No | - | Aspect ratio (see below) |
| `image_size` | string | No | - | Size: `1K`, `2K`, `4K` (Pro model only) |

**Valid aspect ratios:** `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`

## Response Schema

```json
{
  "images": ["base64..."],
  "revised_prompt": "...",
  "model": "gemini-2.5-flash-image",
  "provider": "google",
  "mime_type": "image/png"
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
echo '{"task_id":"t1","payload":{"model":"gemini-2.5-flash-image","prompt":"A beautiful sunset over the ocean"}}' | python main.py
```

**Expected output:**
```json
{"status": "ready"}
{"task_id": "t1", "result": {"images": ["iVBORw0KGgo..."], "revised_prompt": "...", "model": "gemini-2.5-flash-image", "provider": "google", "mime_type": "image/png"}, "error": null, "retry": false}
```

**More examples:**
```bash
# With aspect ratio
echo '{"task_id":"t2","payload":{"model":"gemini-2.5-flash-image","prompt":"A mountain landscape","aspect_ratio":"16:9"}}' | python main.py

# Pro model with image size
echo '{"task_id":"t3","payload":{"model":"gemini-3-pro-image-preview","prompt":"A detailed portrait","aspect_ratio":"3:4","image_size":"2K"}}' | python main.py

# Square image
echo '{"task_id":"t4","payload":{"model":"gemini-2.5-flash-image","prompt":"An app icon design","aspect_ratio":"1:1"}}' | python main.py
```

---

### 2. Using runqy CLI (Server Required)

First, ensure you're logged in and the queue is created on the server.

**Linux/macOS (bash):**
```bash
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue a task
runqy task enqueue -q google-image -p '{"model":"gemini-2.5-flash-image","prompt":"A beautiful sunset over the ocean"}'
```

**Windows (PowerShell) - use `cmd /c`:**
```powershell
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue a task
cmd /c 'runqy task enqueue -q google-image -p "{\"model\":\"gemini-2.5-flash-image\",\"prompt\":\"A beautiful sunset over the ocean\"}"'
```

**More examples (Windows PowerShell):**
```powershell
# With aspect ratio
cmd /c 'runqy task enqueue -q google-image -p "{\"model\":\"gemini-2.5-flash-image\",\"prompt\":\"A panoramic mountain view\",\"aspect_ratio\":\"21:9\"}"'

# Pro model with size
cmd /c 'runqy task enqueue -q google-image -p "{\"model\":\"gemini-3-pro-image-preview\",\"prompt\":\"A detailed fantasy landscape\",\"aspect_ratio\":\"16:9\",\"image_size\":\"4K\"}"'

# Portrait orientation
cmd /c 'runqy task enqueue -q google-image -p "{\"model\":\"gemini-2.5-flash-image\",\"prompt\":\"A person standing in a forest\",\"aspect_ratio\":\"9:16\"}"'
```

**Check task status:**
```bash
# List tasks in queue
runqy task list google-image

# Get specific task details
runqy task get google-image <task-id>

# List completed tasks
runqy task list google-image --state completed
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
    "queue": "google-image",
    "timeout": 120000,
    "data": {
      "model": "gemini-2.5-flash-image",
      "prompt": "A beautiful sunset over the ocean"
    }
  }'

# With aspect ratio
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-image",
    "timeout": 120000,
    "data": {
      "model": "gemini-2.5-flash-image",
      "prompt": "A cinematic landscape shot",
      "aspect_ratio": "21:9"
    }
  }'

# Pro model with image size
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-image",
    "timeout": 120000,
    "data": {
      "model": "gemini-3-pro-image-preview",
      "prompt": "A highly detailed architectural rendering",
      "aspect_ratio": "16:9",
      "image_size": "4K"
    }
  }'
```

**Flat format (alternative):**
```bash
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "google-image",
    "timeout": 120000,
    "model": "gemini-2.5-flash-image",
    "prompt": "A beautiful sunset over the ocean",
    "aspect_ratio": "16:9"
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
    queue = "google-image"
    timeout = 120000
    data = @{
        model = "gemini-2.5-flash-image"
        prompt = "A beautiful sunset over the ocean"
        aspect_ratio = "16:9"
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

# Enqueue task
response = requests.post(
    "https://your-server:3000/queue/add",
    headers={
        "Authorization": "Bearer your-api-key",
        "Content-Type": "application/json"
    },
    json={
        "queue": "google-image",
        "timeout": 120000,
        "data": {
            "model": "gemini-2.5-flash-image",
            "prompt": "A beautiful sunset over the ocean",
            "aspect_ratio": "16:9"
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
