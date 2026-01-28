"""Google Gemini image generation task for runqy-worker.

Supports models:
- gemini-2.5-flash-image: Fast image generation (no imageSize support)
- gemini-3-pro-image-preview: Higher quality, supports imageSize

Environment variables:
- GOOGLE_API_KEY: API key for authentication
"""

import os
import sys
import requests
from typing import Optional, Dict, Any

from runqy_task import task, load, run


BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Model configurations
MODELS = {
    "gemini-2.5-flash-image": {"supports_image_size": False},
    "gemini-3-pro-image-preview": {"supports_image_size": True},
}

VALID_ASPECT_RATIOS = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
VALID_IMAGE_SIZES = {"1K", "2K", "4K"}

TIMEOUT = 120


@load
def setup():
    """Load credentials from environment variables."""
    api_key = os.environ.get("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set")

    print("Google Gemini image task initialized", file=sys.stderr)

    return {
        "api_key": api_key,
    }


@task
def process(payload: dict, ctx: dict) -> dict:
    """Generate images using Google Gemini.

    Payload:
        model (str): Required. Model name (gemini-2.5-flash-image, gemini-3-pro-image-preview)
        prompt (str): Required. Image description
        aspect_ratio (str): Optional. Aspect ratio (1:1, 16:9, 9:16, etc.)
        image_size (str): Optional. Image size (1K, 2K, 4K) - Pro model only

    Returns:
        images (list): Array of base64-encoded images
        revised_prompt (str): Text response from model
        model (str): Model used
        provider (str): "google"
        mime_type (str): Image MIME type
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
    aspect_ratio = payload.get("aspect_ratio")
    image_size = payload.get("image_size")

    config = MODELS[model_name]
    url = f"{BASE_URL}/models/{model_name}:generateContent"

    # Build request
    request_body: Dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    # Add image config if needed
    image_config: Dict[str, Any] = {}
    if aspect_ratio and aspect_ratio in VALID_ASPECT_RATIOS:
        image_config["aspectRatio"] = aspect_ratio
    if config.get("supports_image_size") and image_size and image_size in VALID_IMAGE_SIZES:
        image_config["imageSize"] = image_size

    if image_config:
        request_body["generationConfig"]["imageConfig"] = image_config

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    print(f"Generating image with {model_name}: {prompt[:50]}...", file=sys.stderr)

    response = requests.post(url, json=request_body, headers=headers, timeout=TIMEOUT)
    data = response.json()

    # Check for errors
    if "error" in data:
        error_msg = data["error"].get("message", "Unknown error")
        error_status = data["error"].get("status", "unknown")
        raise Exception(f"Google API error [{error_status}]: {error_msg}")

    if data.get("promptFeedback", {}).get("blockReason"):
        raise Exception(f"Prompt blocked: {data['promptFeedback']['blockReason']}")

    if response.status_code != 200:
        raise Exception(f"Google API returned status {response.status_code}: {response.text}")

    # Parse response
    images = []
    revised_prompt = None
    mime_type = "image/png"

    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                revised_prompt = part["text"]
            if part.get("inlineData", {}).get("data"):
                images.append(part["inlineData"]["data"])
                if part["inlineData"].get("mimeType"):
                    mime_type = part["inlineData"]["mimeType"]

    if not images:
        raise Exception("No images generated in response")

    print(f"Generated {len(images)} image(s)", file=sys.stderr)

    return {
        "images": images,
        "revised_prompt": revised_prompt,
        "model": model_name,
        "provider": "google",
        "mime_type": mime_type,
    }


if __name__ == "__main__":
    run()
