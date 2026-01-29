"""Google Veo video generation task for runqy-worker.

Supports models:
- veo-3.1-generate-preview: Standard video generation
- veo-3.1-fast-generate-preview: Faster video generation

Environment variables:
- GOOGLE_API_KEY: API key for authentication
"""

import os
import sys
import time
import base64
import requests
from typing import Optional, Dict, Any

from runqy_python import task, load, run


BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Model configurations
MODELS = {
    "veo-3.1-generate-preview": {},
    "veo-3.1-fast-generate-preview": {},
}

VALID_ASPECT_RATIOS = {"16:9", "9:16"}
VALID_RESOLUTIONS = {"720p", "1080p"}
VALID_DURATIONS = {4, 6, 8}
VALID_PERSON_GENERATION = {"allow_all", "allow_adult"}

TIMEOUT = 120
DEFAULT_POLL_INTERVAL = 10
DEFAULT_MAX_WAIT = 600


@load
def setup():
    """Load credentials from environment variables."""
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    print("Google Veo video task initialized", file=sys.stderr)

    return {
        "api_key": api_key,
    }


def download_video(video_uri: str, api_key: str) -> str:
    """Download video from URI and return as base64."""
    response = requests.get(
        video_uri,
        headers={"x-goog-api-key": api_key},
        timeout=TIMEOUT
    )
    if response.status_code != 200:
        raise Exception(f"Failed to download video: {response.status_code}")
    return base64.b64encode(response.content).decode("utf-8")


def poll_operation(
    operation_name: str,
    api_key: str,
    poll_interval: int,
    max_wait: int,
) -> Dict[str, Any]:
    """Poll for operation completion."""
    poll_url = f"{BASE_URL}/{operation_name}"
    headers = {
        "x-goog-api-key": api_key,
    }

    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        print(f"Polling operation... ({elapsed}s elapsed)", file=sys.stderr)

        response = requests.get(poll_url, headers=headers, timeout=TIMEOUT)
        data = response.json()

        if "error" in data:
            error_msg = data["error"].get("message", "Unknown error")
            error_status = data["error"].get("status", "unknown")
            raise Exception(f"Google Veo API error [{error_status}]: {error_msg}")

        if data.get("done"):
            return data

    raise Exception(f"Video generation timed out after {max_wait} seconds")


@task
def process(payload: dict, ctx: dict) -> dict:
    """Generate videos using Google Veo.

    Payload:
        model (str): Required. Model name (veo-3.1-generate-preview, veo-3.1-fast-generate-preview)
        prompt (str): Required. Video description
        negative_prompt (str): Optional. What to avoid
        aspect_ratio (str): Optional. Aspect ratio (16:9, 9:16)
        resolution (str): Optional. Resolution (720p, 1080p)
        duration_seconds (int): Optional. Duration (4, 6, 8)
        person_generation (str): Optional. Person generation setting
        seed (int): Optional. For reproducibility
        poll_interval (int): Optional. Seconds between status checks (default: 10)
        max_wait (int): Optional. Maximum seconds to wait (default: 600)

    Returns:
        videos (list): Array of base64-encoded videos
        model (str): Model used
        provider (str): "google"
        mime_type (str): Video MIME type
        operation_name (str): Operation name
    """
    api_key = ctx["api_key"]

    # Validate required fields
    model_name = payload.get("model")
    if not model_name:
        raise ValueError("Missing required field: model")
    if model_name not in MODELS:
        raise ValueError(f"Unsupported model: {model_name}. Supported: {list(MODELS.keys())}")

    prompt = payload.get("prompt")
    if not prompt:
        raise ValueError("Missing required field: prompt")

    # Extract optional parameters
    negative_prompt = payload.get("negative_prompt")
    aspect_ratio = payload.get("aspect_ratio")
    resolution = payload.get("resolution")
    duration_seconds = payload.get("duration_seconds")
    person_generation = payload.get("person_generation")
    seed = payload.get("seed")
    poll_interval = payload.get("poll_interval", DEFAULT_POLL_INTERVAL)
    max_wait = payload.get("max_wait", DEFAULT_MAX_WAIT)

    url = f"{BASE_URL}/models/{model_name}:predictLongRunning"

    # Build request
    request_body: Dict[str, Any] = {
        "instances": [{"prompt": prompt}],
    }

    parameters: Dict[str, Any] = {}
    if negative_prompt:
        parameters["negativePrompt"] = negative_prompt
    if aspect_ratio and aspect_ratio in VALID_ASPECT_RATIOS:
        parameters["aspectRatio"] = aspect_ratio
    if resolution and resolution in VALID_RESOLUTIONS:
        parameters["resolution"] = resolution
    if duration_seconds and duration_seconds in VALID_DURATIONS:
        parameters["durationSeconds"] = duration_seconds
    if person_generation and person_generation in VALID_PERSON_GENERATION:
        parameters["personGeneration"] = person_generation
    if seed is not None:
        parameters["seed"] = seed

    if parameters:
        request_body["parameters"] = parameters

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    print(f"Starting video generation with {model_name}: {prompt[:50]}...", file=sys.stderr)

    # Start generation
    response = requests.post(url, json=request_body, headers=headers, timeout=TIMEOUT)
    data = response.json()

    if "error" in data:
        error_msg = data["error"].get("message", "Unknown error")
        error_status = data["error"].get("status", "unknown")
        raise Exception(f"Google Veo API error [{error_status}]: {error_msg}")

    if response.status_code != 200:
        raise Exception(f"Google Veo API returned status {response.status_code}: {response.text}")

    operation_name = data.get("name")
    if not operation_name:
        raise Exception("No operation name in response")

    print(f"Operation started: {operation_name}", file=sys.stderr)

    # If already done (unlikely)
    if not data.get("done"):
        data = poll_operation(operation_name, api_key, poll_interval, max_wait)

    # Parse response and download videos
    videos = []
    response_data = data.get("response", {}).get("generateVideoResponse", {})

    for sample in response_data.get("generatedSamples", []):
        video_uri = sample.get("video", {}).get("uri")
        if video_uri:
            print(f"Downloading video from {video_uri[:50]}...", file=sys.stderr)
            video_base64 = download_video(video_uri, api_key)
            videos.append(video_base64)

    if not videos:
        raise Exception("No videos generated in response")

    print(f"Generated {len(videos)} video(s)", file=sys.stderr)

    return {
        "videos": videos,
        "model": model_name,
        "provider": "google",
        "mime_type": "video/mp4",
        "operation_name": operation_name,
    }


if __name__ == "__main__":
    run()
