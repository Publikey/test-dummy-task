"""Wan Video generation task for runqy-worker."""

import base64
import random
import gc
import os
import sys
import logging
from typing import Dict

import requests
import torch
import numpy as np
from diffusers import (
    AutoencoderKLWan,
    WanImageToVideoPipeline,
    WanPipeline,
    WanTransformer3DModel,
    GGUFQuantizationConfig,
)
from diffusers.utils import load_image, export_to_video
from transformers import (
    CLIPVisionModel,
    CLIPImageProcessor,
    UMT5EncoderModel,
    T5TokenizerFast,
)
from runqy_python import task, load, run

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

MAX_SEED = np.iinfo(np.int32).max
MAX_PIXELS = 399_360


def round_to_nearest_resolution_acceptable_by_vae(height: int, width: int) -> tuple[int, int]:
    """Adjust dimensions to be acceptable by VAE (divisible by 32, under max pixels)."""
    print(f"Original dimensions: {height}x{width}, total pixels: {height * width}.", file=sys.stderr)
    while height * width > MAX_PIXELS:
        height = height / 1.05
        width = width / 1.05
    height = height - (height % 32)
    width = width - (width % 32)
    total_pixels = height * width
    print(f"Adjusted dimensions to {height}x{width}, total pixels: {total_pixels}.", file=sys.stderr)
    return int(height), int(width)


def video_to_base64(video_path: str) -> str:
    """Convert an MP4 video file to a Base64 string."""
    with open(video_path, "rb") as video_file:
        encoded = base64.b64encode(video_file.read())
        return encoded.decode("utf-8")


def gc_collect():
    """Clean up GPU memory."""
    gc.collect()
    torch.cuda.empty_cache()


def load_i2v_pipeline():
    """Load Wan2.1 Image-to-Video FusionX GGUF model."""
    remote_path = "https://huggingface.co/QuantStack/Wan2.1_I2V_14B_FusionX-GGUF/blob/main/Wan2.1_I2V_14B_FusionX-Q8_0.gguf"
    local_path = "/root/data/Wan2.1_I2V_14B_FusionX-Q8_0.gguf"

    if os.path.exists(local_path):
        path = local_path
        logging.info(f"Loading local I2V model from {path}...")
    else:
        path = remote_path
        logging.info(f"Local I2V model not found. Loading from Hugging Face: {path}...")

    model_id = "Wan-AI/Wan2.1-I2V-14B-720P-Diffusers"
    image_encoder = CLIPVisionModel.from_pretrained(model_id, subfolder="image_encoder", torch_dtype=torch.bfloat16)
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.bfloat16)
    image_processor = CLIPImageProcessor.from_pretrained(model_id, subfolder="image_processor", torch_dtype=torch.bfloat16)
    text_encoder = UMT5EncoderModel.from_pretrained(model_id, subfolder="text_encoder", torch_dtype=torch.bfloat16)
    tokenizer = T5TokenizerFast.from_pretrained(model_id, subfolder="tokenizer")
    transformer = WanTransformer3DModel.from_single_file(
        path,
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16
    )
    pipeline = WanImageToVideoPipeline.from_pretrained(
        model_id,
        image_processor=image_processor,
        image_encoder=image_encoder,
        vae=vae,
        transformer=transformer,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        torch_dtype=torch.bfloat16
    )
    return pipeline


def load_t2v_pipeline():
    """Load Wan2.1 Text-to-Video FusionX GGUF model."""
    remote_path = "https://huggingface.co/QuantStack/Wan2.1_T2V_14B_FusionX-GGUF/blob/main/Wan2.1_T2V_14B_FusionX-Q8_0.gguf"
    local_path = "/root/data/Wan2.1_T2V_14B_FusionX-Q8_0.gguf"

    if os.path.exists(local_path):
        path = local_path
        logging.info(f"Loading local T2V model from {path}...")
    else:
        path = remote_path
        logging.info(f"Local T2V model not found. Loading from Hugging Face: {path}...")

    model_id = "Wan-AI/Wan2.1-T2V-14B-Diffusers"
    vae = AutoencoderKLWan.from_pretrained(model_id, subfolder="vae", torch_dtype=torch.bfloat16)
    text_encoder = UMT5EncoderModel.from_pretrained(model_id, subfolder="text_encoder", torch_dtype=torch.bfloat16)
    tokenizer = T5TokenizerFast.from_pretrained(model_id, subfolder="tokenizer", torch_dtype=torch.bfloat16)
    transformer = WanTransformer3DModel.from_single_file(
        path,
        quantization_config=GGUFQuantizationConfig(compute_dtype=torch.bfloat16),
        torch_dtype=torch.bfloat16
    )
    pipeline = WanPipeline.from_pretrained(
        model_id,
        transformer=transformer,
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        torch_dtype=torch.bfloat16
    )
    return pipeline


@load
def setup() -> dict:
    """Load video generation models (runs once before ready signal)."""
    logging.info("Loading Wan video models...")

    models = {}
    current_model_on_gpu = None

    # Load I2V model
    logging.info("Loading wan21-fusionx-i2v model...")
    try:
        models["wan21-fusionx-i2v"] = load_i2v_pipeline()
        models["wan21-fusionx-i2v"].to("cpu")
        logging.info("wan21-fusionx-i2v loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading wan21-fusionx-i2v: {e}")

    # Load T2V model
    logging.info("Loading wan21-fusionx-t2v model...")
    try:
        models["wan21-fusionx-t2v"] = load_t2v_pipeline()
        models["wan21-fusionx-t2v"].to("cpu")
        logging.info("wan21-fusionx-t2v loaded successfully.")
    except Exception as e:
        logging.error(f"Error loading wan21-fusionx-t2v: {e}")

    gc_collect()
    logging.info("All models loaded and moved to CPU.")

    return {
        "models": models,
        "current_model_on_gpu": current_model_on_gpu,
    }


@task
def process(payload: dict, ctx: dict) -> dict:
    """Process a video generation task."""
    models = ctx["models"]
    current_model_on_gpu = ctx.get("current_model_on_gpu")

    # Extract parameters from payload
    uuid = payload.get("id", "xyz")
    webhook_url = payload.get("webhook_url", "")
    prompt = payload.get("prompt", "")
    negative_prompt = payload.get(
        "negative_prompt",
        "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, 整体发灰, 最差质量, 低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, 画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, 形态畸形的肢体, 手指融合, 静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走."
    )
    model_name = payload.get("model_name", "wan21-fusionx-i2v")
    img_url = payload.get("img_url", "")
    quality = payload.get("quality", "standard")
    width = payload.get("width", 1024)
    height = payload.get("height", 1024)
    num_frames = payload.get("num_frames", 121)
    fps = payload.get("fps", 18)

    logging.info(f"uuid: {uuid}")
    logging.info(f"webhook_url: {webhook_url}")
    logging.info(f"Model Name: {model_name}")
    logging.info(f"Prompt: {prompt}")
    logging.info(f"Image URL: {img_url}")
    logging.info(f"Quality: {quality}")
    logging.info(f"Dimensions: {width}x{height}")
    logging.info(f"num_frames: {num_frames}, fps: {fps}")

    # Handle model swapping
    if model_name not in models:
        return {"error": f"Model {model_name} not found"}

    pipe = models[model_name]

    if current_model_on_gpu != model_name:
        if current_model_on_gpu is not None and current_model_on_gpu in models:
            logging.info(f"Swapping {current_model_on_gpu} to CPU...")
            models[current_model_on_gpu].to("cpu")
            gc_collect()

        logging.info(f"Moving {model_name} to GPU...")
        pipe.to("cuda")
        gc_collect()
        ctx["current_model_on_gpu"] = model_name

    # Set inference steps based on quality
    num_inference_steps = 10 if quality == "high" else 6

    # Generate random seed
    random_seed = random.randint(0, MAX_SEED)
    generator = torch.Generator().manual_seed(random_seed)

    result_data = []
    errors = []

    try:
        if model_name == "wan21-fusionx-i2v":
            # Image-to-Video
            image_raw = load_image(img_url)
            im_init_width, im_init_height = image_raw.size

            downscaled_height, downscaled_width = round_to_nearest_resolution_acceptable_by_vae(
                im_init_height, im_init_width
            )
            image_downscaled = image_raw.resize((downscaled_width, downscaled_height))

            logging.info(f"Original image size: {im_init_width}x{im_init_height}")
            logging.info(f"Image resized to: {downscaled_width}x{downscaled_height}")

            output = pipe(
                image=image_downscaled,
                prompt=prompt,
                negative_prompt=negative_prompt,
                height=downscaled_height,
                width=downscaled_width,
                num_frames=int(num_frames),
                guidance_scale=1.0,
                generator=generator,
                num_inference_steps=num_inference_steps
            ).frames[0]
        else:
            # Text-to-Video
            downscaled_height, downscaled_width = round_to_nearest_resolution_acceptable_by_vae(
                int(height), int(width)
            )
            output = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                height=downscaled_height,
                width=downscaled_width,
                num_frames=int(num_frames),
                guidance_scale=1.0,
                generator=generator,
                num_inference_steps=num_inference_steps
            ).frames[0]

        # Export video
        os.makedirs("./output", exist_ok=True)
        output_path = f"./output/{uuid}.mp4"
        export_to_video(output, output_path, fps=int(fps))

        output_base64 = video_to_base64(output_path)

        result_data.append({
            "result": output_base64,
            "seed": random_seed,
        })

    except Exception as e:
        logging.error(f"Generation error: {e}")
        errors.append({
            "error": str(e),
            "seed": random_seed,
        })
        gc_collect()

    result_payload = {
        "uuid": uuid,
        "data": result_data,
        "errors": errors,
    }

    # Send webhook if URL provided
    if webhook_url:
        try:
            res = requests.post(webhook_url, json=result_payload, timeout=30)
            if res.status_code != 200:
                logging.error(f"Error sending result to {webhook_url}: {res.text}")
            else:
                logging.info(f"Result successfully sent to {webhook_url}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Webhook request failed: {e}")

    gc_collect()
    return result_payload


if __name__ == "__main__":
    run()
