# Azure OpenAI Image Generation Task

Generate images using Azure OpenAI models (gpt-image-1, gpt-image-1.5, flux.2-pro, flux-1.1-pro).

## Supported Models

| Model | Features |
|-------|----------|
| `gpt-image-1.5` | quality, output_compression, output_format |
| `gpt-image-1` | quality, output_compression, output_format |
| `flux.2-pro` | Basic generation |
| `flux-1.1-pro` | output_format |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_OPENAI_API_KEY` | Yes | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Yes | Base endpoint URL (e.g., `https://your-resource.cognitiveservices.azure.com`) |

## Payload Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `model` | string | Yes | - | Model name |
| `prompt` | string | Yes | - | Image description |
| `width` | int | No | 1024 | Image width in pixels |
| `height` | int | No | 1024 | Image height in pixels |
| `n` | int | No | 1 | Number of images to generate |
| `quality` | string | No | - | Quality: `low`, `medium`, `high` |
| `output_compression` | int | No | - | Compression 0-100 (gpt-image models) |
| `output_format` | string | No | - | Format: `png`, `jpeg` |

## Response Schema

```json
{
  "images": ["base64..."],
  "revised_prompt": "...",
  "model": "gpt-image-1.5",
  "provider": "azure"
}
```

---

## Usage

### 1. Local Development (No Server Required)

Test the task directly by piping JSON to the Python script:

```bash
# Set environment variables
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.cognitiveservices.azure.com"

# Install dependencies
pip install -r requirements.txt

# Run task
echo '{"task_id":"t1","payload":{"model":"gpt-image-1.5","prompt":"A blue whale swimming in the ocean"}}' | python main.py
```

**Expected output:**
```json
{"status": "ready"}
{"task_id": "t1", "result": {"images": ["iVBORw0KGgo..."], "revised_prompt": "...", "model": "gpt-image-1.5", "provider": "azure"}, "error": null, "retry": false}
```

**More examples:**
```bash
# With size and quality
echo '{"task_id":"t2","payload":{"model":"gpt-image-1.5","prompt":"A sunset over mountains","width":1280,"height":720,"quality":"high"}}' | python main.py

# Multiple images
echo '{"task_id":"t3","payload":{"model":"gpt-image-1","prompt":"Abstract art","n":2,"output_format":"jpeg"}}' | python main.py

# Flux model
echo '{"task_id":"t4","payload":{"model":"flux-1.1-pro","prompt":"A futuristic city"}}' | python main.py
```

---

### 2. Using runqy CLI (Server Required)

First, ensure you're logged in and the queue is created on the server.

**Linux/macOS (bash):**
```bash
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue a task
runqy task enqueue -q azure-image -p '{"model":"gpt-image-1.5","prompt":"A blue whale swimming in the ocean"}'
```

**Windows (PowerShell) - use `cmd /c`:**
```powershell
# Login (if not already)
runqy login -s https://your-server:3000 -k your-api-key

# Enqueue a task
cmd /c 'runqy task enqueue -q azure-image -p "{\"model\":\"gpt-image-1.5\",\"prompt\":\"A blue whale swimming in the ocean\"}"'
```

**More examples (Windows PowerShell):**
```powershell
# With all options
cmd /c 'runqy task enqueue -q azure-image -p "{\"model\":\"gpt-image-1.5\",\"prompt\":\"A majestic mountain landscape\",\"width\":1280,\"height\":720,\"quality\":\"high\",\"output_format\":\"png\"}"'

# Multiple images
cmd /c 'runqy task enqueue -q azure-image -p "{\"model\":\"gpt-image-1\",\"prompt\":\"Abstract colorful patterns\",\"n\":3}"'

# Flux model
cmd /c 'runqy task enqueue -q azure-image -p "{\"model\":\"flux-1.1-pro\",\"prompt\":\"A cyberpunk street scene\",\"output_format\":\"jpeg\"}"'
```

**Check task status:**
```bash
# List tasks in queue
runqy task list azure-image

# Get specific task details
runqy task get azure-image <task-id>

# List completed tasks
runqy task list azure-image --state completed
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
    "queue": "azure-image",
    "timeout": 120000,
    "data": {
      "model": "gpt-image-1.5",
      "prompt": "A blue whale swimming in the ocean"
    }
  }'

# With all options
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "azure-image",
    "timeout": 120000,
    "data": {
      "model": "gpt-image-1.5",
      "prompt": "A serene Japanese garden",
      "width": 1280,
      "height": 720,
      "quality": "high",
      "output_format": "png"
    }
  }'
```

**Flat format (alternative):**
```bash
curl -X POST https://your-server:3000/queue/add \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "queue": "azure-image",
    "timeout": 120000,
    "model": "gpt-image-1.5",
    "prompt": "A blue whale swimming in the ocean"
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
    queue = "azure-image"
    timeout = 120000
    data = @{
        model = "gpt-image-1.5"
        prompt = "A blue whale swimming in the ocean"
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
        "queue": "azure-image",
        "timeout": 120000,
        "data": {
            "model": "gpt-image-1.5",
            "prompt": "A blue whale swimming in the ocean",
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
