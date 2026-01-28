"""Azure OpenAI image generation task for runqy-worker.

Supports models:
- gpt-image-1.5: quality, output_compression, output_format
- gpt-image-1: quality, output_compression, output_format
- flux.2-pro: requires model field in body
- flux-1.1-pro: output_format only

Environment variables:
- AZURE_OPENAI_API_KEY: API key for authentication
- AZURE_OPENAI_ENDPOINT: Base endpoint URL (e.g., https://your-resource.cognitiveservices.azure.com)
"""

import os
import sys
import requests
from typing import Optional, Dict, Any

from runqy_task import task, load, run


# Model configurations
MODELS = {
    "gpt-image-1.5": {
        "deployment": "gpt-image-1.5",
        "api_version": "2024-02-01",
        "url_pattern": "openai",
        "base_domain": "cognitiveservices",
        "supports_quality": True,
        "supports_output_compression": True,
        "supports_output_format": True,
    },
    "gpt-image-1": {
        "deployment": "gpt-image-1",
        "api_version": "2025-04-01-preview",
        "url_pattern": "openai",
        "base_domain": "cognitiveservices",
        "supports_quality": True,
        "supports_output_compression": True,
        "supports_output_format": True,
    },
    "flux.2-pro": {
        "deployment": "",
        "api_version": "preview",
        "url_pattern": "blackforest",
        "base_domain": "services.ai",
        "requires_model_field": True,
    },
    "flux-1.1-pro": {
        "deployment": "FLUX-1.1-pro",
        "api_version": "2025-04-01-preview",
        "url_pattern": "openai",
        "base_domain": "services.ai",
        "supports_output_format": True,
    },
}

TIMEOUT = 120


def build_url(endpoint: str, model_name: str) -> str:
    """Build the API URL based on model configuration."""
    config = MODELS[model_name]
    base = endpoint

    # Transform domain if needed
    if config.get("base_domain") == "services.ai":
        base = base.replace(".cognitiveservices.azure.com", ".services.ai.azure.com")

    if config["url_pattern"] == "blackforest":
        return f"{base}/providers/blackforestlabs/v1/flux-2-pro?api-version={config['api_version']}"
    else:  # openai
        return f"{base}/openai/deployments/{config['deployment']}/images/generations?api-version={config['api_version']}"


def build_request(
    model_name: str,
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    n: int = 1,
    quality: Optional[str] = None,
    output_compression: Optional[int] = None,
    output_format: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the request body based on model capabilities."""
    config = MODELS[model_name]

    request = {
        "prompt": prompt,
        "size": f"{width}x{height}",
        "n": n,
    }

    # Add fields based on model support
    if config.get("supports_quality") and quality:
        # Map quality values
        quality_map = {
            "hd": "high",
            "high": "high",
            "low": "low",
            "medium": "medium",
            "standard": "medium",
        }
        request["quality"] = quality_map.get(quality, quality)

    if config.get("supports_output_compression") and output_compression is not None:
        request["output_compression"] = output_compression

    if config.get("supports_output_format") and output_format:
        request["output_format"] = output_format

    if config.get("requires_model_field"):
        request["model"] = "flux.2-pro"

    return request


@load
def setup():
    """Load credentials from environment variables."""
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")

    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable not set")
    if not endpoint:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable not set")

    print(f"Azure OpenAI image task initialized with endpoint: {endpoint}", file=sys.stderr)

    return {
        "api_key": api_key,
        "endpoint": endpoint,
    }


@task
def process(payload: dict, ctx: dict) -> dict:
    """Generate images using Azure OpenAI.

    Payload:
        model (str): Required. Model name (gpt-image-1.5, gpt-image-1, flux.2-pro, flux-1.1-pro)
        prompt (str): Required. Image description
        width (int): Optional. Image width (default: 1024)
        height (int): Optional. Image height (default: 1024)
        n (int): Optional. Number of images (default: 1)
        quality (str): Optional. Quality level (low, medium, high)
        output_compression (int): Optional. Compression 0-100
        output_format (str): Optional. Format (png, jpeg)

    Returns:
        images (list): Array of base64-encoded images
        revised_prompt (str): Revised prompt if available
        model (str): Model used
        provider (str): "azure"
    """
    api_key = ctx["api_key"]
    endpoint = ctx["endpoint"]

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
    width = payload.get("width", 1024)
    height = payload.get("height", 1024)
    n = payload.get("n", 1)
    quality = payload.get("quality")
    output_compression = payload.get("output_compression")
    output_format = payload.get("output_format")

    # Build URL and request
    url = build_url(endpoint, model_name)
    body = build_request(
        model_name, prompt, width, height, n,
        quality, output_compression, output_format
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    print(f"Generating image with {model_name}: {prompt[:50]}...", file=sys.stderr)

    response = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
    data = response.json()

    # Check for error
    if "error" in data and data["error"]:
        error_msg = data["error"].get("message", "Unknown error")
        error_code = data["error"].get("code", "unknown")
        raise Exception(f"Azure API error [{error_code}]: {error_msg}")

    if response.status_code != 200:
        raise Exception(f"Azure API returned status {response.status_code}: {response.text}")

    # Parse response
    images = []
    revised_prompt = None

    for item in data.get("data", []):
        if item.get("b64_json"):
            images.append(item["b64_json"])
        if item.get("revised_prompt"):
            revised_prompt = item["revised_prompt"]

    if not images:
        raise Exception("No images generated in response")

    print(f"Generated {len(images)} image(s)", file=sys.stderr)

    return {
        "images": images,
        "revised_prompt": revised_prompt,
        "model": model_name,
        "provider": "azure",
    }


if __name__ == "__main__":
    run()
