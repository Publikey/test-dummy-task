import base64
from io import BytesIO
import random
from typing import Dict
import os
import logging, sys, json
import warnings
from collections import OrderedDict
import time
import requests
import torch
import numpy as np
from PIL import Image
import gc
from uploaders import ImageUploader, AzureProvider, UploadError
from diffusers import (
    StableDiffusionXLPipeline,
    StableDiffusionXLImg2ImgPipeline,
    DPMSolverMultistepScheduler,
    EulerAncestralDiscreteScheduler
)
from diffusers.utils import load_image

from sd_embed.embedding_funcs import get_weighted_text_embeddings_sdxl
from config import get_all_model_names, resolve_model_path, get_model_config, download_all_models
from runqy_python import task, load, run

MAX_SEED = np.iinfo(np.int32).max

# === Configuration (from environment variables) ===
MAX_CPU_MODELS = int(os.getenv("MAX_CPU_MODELS", "3"))
DOWNLOAD_ALL_AT_STARTUP = os.getenv("DOWNLOAD_ALL_AT_STARTUP", "false").lower() == "true"
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_STORAGE_CONTAINER = os.getenv("AZURE_STORAGE_CONTAINER", "ephemeral")

logging.basicConfig(stream=sys.stderr, level=logging.INFO)


def load_source_image(img_url: str = None, img_base64: str = None) -> Image.Image:
    """
    Load source image from either URL or Base64 string.
    Returns PIL Image or None if no valid source.
    """
    if img_url and img_url.strip():
        return load_image(img_url)
    elif img_base64 and img_base64.strip():
        image_data = base64.b64decode(img_base64)
        return Image.open(BytesIO(image_data)).convert("RGB")
    return None



def resize_image_to_dimensions(image: Image.Image, width: int, height: int) -> Image.Image:
    """
    Resize image to match target dimensions, maintaining aspect ratio with center crop.
    SDXL requires dimensions divisible by 8.
    """
    # Ensure dimensions are divisible by 8
    width = width - (width % 8)
    height = height - (height % 8)

    # Calculate resize to cover target dimensions
    img_ratio = image.width / image.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        # Image is wider - resize by height, crop width
        new_height = height
        new_width = int(height * img_ratio)
    else:
        # Image is taller - resize by width, crop height
        new_width = width
        new_height = int(width / img_ratio)

    # Resize with high-quality resampling
    resized = image.resize((new_width, new_height), Image.LANCZOS)

    # Center crop to target dimensions
    left = (new_width - width) // 2
    top = (new_height - height) // 2
    cropped = resized.crop((left, top, left + width, top + height))

    return cropped

class ModelManager:
    def __init__(self, model_cache_dir="../workspace/models_cache", hf_access_token=None):
        self.models = {}  # Currently loaded models in CPU/GPU memory
        self.model_cache_dir = model_cache_dir
        self.current_model_on_gpu_name = None  # Track the name of the current model on GPU
        os.makedirs(self.model_cache_dir, exist_ok=True)
        self.hf_access_token = hf_access_token

        # LRU tracking: OrderedDict maintains insertion order, we move to end on access
        self.model_load_times = OrderedDict()

        self.max_cpu_models = MAX_CPU_MODELS
        logging.info(f"Max CPU models set to: {self.max_cpu_models}")

        # Load available models from YAML config
        self.available_models = get_all_model_names()
        logging.info(f"Loaded {len(self.available_models)} models from config")

    def gc_collect(self):
        gc.collect()
        torch.cuda.empty_cache()
        
    def swap_model_to_cpu(self, model):
        # Suppress diffusers logger warning about float16 on CPU
        diffusers_logger = logging.getLogger("diffusers")
        original_level = diffusers_logger.level
        diffusers_logger.setLevel(logging.ERROR)
        model.to('cpu')
        diffusers_logger.setLevel(original_level)
        self.gc_collect()

    def swap_model_to_gpu(self, model, model_name: str = None):
        model.to('cuda')
        self.gc_collect()
        if model_name:
            self.current_model_on_gpu_name = model_name

    def get_current_model_on_gpu(self):
        # Verify if current_model_on_gpu_name's primary components are on GPU
        model = self.models.get(self.current_model_on_gpu_name)
        if model is not None and model.unet.device.type == 'cuda':
            return model
        return None

    def create_img2img_pipeline(self, t2i_pipe: StableDiffusionXLPipeline) -> StableDiffusionXLImg2ImgPipeline:
        """
        Create an img2img pipeline from an existing t2i pipeline.
        Shares all model components (no additional memory).
        """
        img2img_pipe = StableDiffusionXLImg2ImgPipeline(
            vae=t2i_pipe.vae,
            text_encoder=t2i_pipe.text_encoder,
            text_encoder_2=t2i_pipe.text_encoder_2,
            tokenizer=t2i_pipe.tokenizer,
            tokenizer_2=t2i_pipe.tokenizer_2,
            unet=t2i_pipe.unet,
            scheduler=t2i_pipe.scheduler,
        )
        return img2img_pipe

    def update_lru(self, model_name: str):
        """Update LRU tracking - move model to end (most recently used)."""
        if model_name in self.model_load_times:
            self.model_load_times.move_to_end(model_name)
        else:
            self.model_load_times[model_name] = time.time()

    def evict_lru_model(self):
        """Evict the least recently used model from CPU memory (skip GPU model)."""
        for model_name in self.model_load_times:
            # Skip the model currently on GPU
            if model_name == self.current_model_on_gpu_name:
                continue

            # Found the LRU model to evict
            logging.info(f"Evicting LRU model from CPU: {model_name}")
            del self.models[model_name]
            del self.model_load_times[model_name]
            self.gc_collect()
            return True

        logging.warning("No model available for eviction (all models are on GPU or protected)")
        return False

    def get_or_load_model(self, model_name: str):
        """
        Get a model from cache or load it on first request.
        Implements lazy loading with LRU eviction.
        """
        # Check if model is already loaded
        if model_name in self.models:
            logging.info(f"Model {model_name} already in CPU memory, updating LRU")
            self.update_lru(model_name)
            return self.models[model_name]

        # Model not loaded - need to load it
        logging.info(f"Model {model_name} not in memory, loading...")

        # Check if we need to evict a model first
        if len(self.models) >= self.max_cpu_models:
            logging.info(f"CPU memory full ({len(self.models)}/{self.max_cpu_models} models), evicting LRU model")
            self.evict_lru_model()

        # Load the model from config
        if model_name not in self.available_models:
            raise ValueError(f"Unknown model: {model_name}. Available models: {self.available_models}")

        model = self.load_model_from_config(model_name)
        # Suppress diffusers logger warning about float16 on CPU
        # (Models are only cached on CPU, inference runs on GPU)
        diffusers_logger = logging.getLogger("diffusers")
        original_level = diffusers_logger.level
        diffusers_logger.setLevel(logging.ERROR)
        model.to('cpu')  # Ensure model is on CPU after loading
        diffusers_logger.setLevel(original_level)

        # Add to cache and update LRU
        self.models[model_name] = model
        self.update_lru(model_name)

        logging.info(f"Model {model_name} loaded to CPU. Total models in memory: {len(self.models)}")
        return model

    def load_model_from_config(self, model_name: str):
        """
        Load a model using configuration from YAML file.
        Resolves the best available source (local first, then remote).
        """
        config = get_model_config(model_name)
        path = resolve_model_path(model_name)

        logging.info(f"Loading model '{model_name}' from {path}...")

        # Currently all models use StableDiffusionXLPipeline
        # This can be extended to support other pipeline types based on config.pipeline
        if config.pipeline == "StableDiffusionXLPipeline":
            pipeline = StableDiffusionXLPipeline.from_single_file(
                path,
                torch_dtype=torch.float16,
                use_safetensors=True,
            )
        else:
            raise ValueError(f"Unsupported pipeline type: {config.pipeline}")

        return pipeline

    def setup_model_registry(self):
        """
        Initialize the model registry for lazy loading.
        Models are NOT preloaded - they will be loaded on first request.

        If DOWNLOAD_ALL_AT_STARTUP=true, downloads all model files at startup.
        """
        logging.info(f"Lazy loading enabled. Max CPU models: {self.max_cpu_models}")
        logging.info(f"Available models: {self.available_models}")

        if DOWNLOAD_ALL_AT_STARTUP:
            logging.info("DOWNLOAD_ALL_AT_STARTUP=true, downloading all models...")
            results = download_all_models()
            success_count = sum(1 for v in results.values() if v)
            logging.info(f"Downloaded {success_count}/{len(results)} models successfully")
        else:
            logging.info("DOWNLOAD_ALL_AT_STARTUP=false, models will be downloaded on-demand")


class Model:
    def __init__(self, **kwargs):
        # self.hf_access_token = os.getenv("HF_ACCESS_TOKEN")
        # if not self.hf_access_token:
        #     raise ValueError("Missing Hugging Face access token. Please set 'HF_ACCESS_TOKEN' as an environment variable.")
        self.pipe = None
        # self.model_manager = ModelManager(hf_access_token=self.hf_access_token)
        self.model_manager = ModelManager()
        self.current_model_on_gpu = self.model_manager.get_current_model_on_gpu()

        # Image upload chain
        self.uploader = ImageUploader()
        if AZURE_STORAGE_CONNECTION_STRING:
            self.uploader.add_provider(AzureProvider(AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_CONTAINER))
        # Add more providers here: S3, GCS, etc.
        if not self.uploader.providers:
            raise RuntimeError("No upload provider configured. Set AZURE_STORAGE_CONNECTION_STRING (or another provider).")

    def load(self):
        self.model_manager.setup_model_registry()
        self.model_manager.gc_collect()
        return self

    def predict(self, model_input: Dict) -> Dict:
        url = model_input.get("webhook_url")
        uuid = model_input.get("id")

        seed = model_input.get("seed")
        prompt = model_input.get("prompt")
        negative_prompt = model_input.get("negative_prompt")
        width = model_input.get("width")
        height = model_input.get("height")
        num_steps = model_input.get("num_steps", 28)
        guidance_scale = model_input.get("guidance_scale", 6)
        clip_skip= model_input.get("clip_skip", 0)
        scheduler = model_input.get("scheduler", None)
        batch_nbr = model_input.get("batch_nbr", 1)
        model_name = model_input.get("model_name")

        # img2img parameters
        img_url = model_input.get("img_url", "")
        img_base64 = model_input.get("img_base64", "")
        strength = model_input.get("strength", 0.75)

        # Validate and clamp strength
        strength = max(0.1, min(1.0, strength))

        # Detect if this is an img2img request
        is_img2img = bool(img_url or img_base64)

        logging.info(f"Received request with UUID: {uuid}")
        logging.info(f"url: {url}") 
        logging.info(f"Prompt: {prompt}")
        logging.info(f"Seed: {seed}")
        logging.info(f"Negative Prompt: {negative_prompt}")
        logging.info(f"Width: {width}")
        logging.info(f"Height: {height}")
        logging.info(f"Num Steps: {num_steps}")
        logging.info(f"Guidance Scale: {guidance_scale}")
        logging.info(f"Clip Skip: {clip_skip}")
        logging.info(f"Scheduler: {scheduler}")
        logging.info(f"Batch Number: {batch_nbr}")
        logging.info(f"Model Name: {model_name}")
        logging.info(f"Is img2img: {is_img2img}")
        if is_img2img:
            logging.info(f"Strength: {strength}")
            logging.info(f"Image source: {'URL' if img_url else 'Base64'}")

        # Get model from cache or load it (lazy loading with LRU eviction)
        model = self.model_manager.get_or_load_model(model_name)

        # Check if model is already on GPU
        if self.current_model_on_gpu == model_name:
            logging.info(f"Using cached model {self.current_model_on_gpu} on GPU.")
            self.pipe = model
        else:
            if self.current_model_on_gpu is not None:
                logging.info(f"Swapping current model {self.current_model_on_gpu} to CPU.")
                current_model = self.model_manager.models.get(self.current_model_on_gpu)
                if current_model is not None:
                    self.model_manager.swap_model_to_cpu(current_model)
                gc.collect()
                torch.cuda.empty_cache()

            logging.info(f"Swapping requested model {model_name} to GPU.")
            self.model_manager.swap_model_to_gpu(model, model_name)
            gc.collect()
            torch.cuda.empty_cache()
            self.pipe = model
            self.current_model_on_gpu = model_name
            self.model_manager.update_lru(model_name)  # Update LRU after GPU access
        
        
            
        # embed the prompt and negative prompt to override limitation token length
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=".*Token indices sequence length.*")
            (
                prompt_embeds
                , prompt_neg_embeds
                , pooled_prompt_embeds
                , negative_pooled_prompt_embeds
            ) = get_weighted_text_embeddings_sdxl(
                self.pipe
                , prompt = prompt
                , neg_prompt = negative_prompt
            )
        
        # set scheduler (to change)
        if scheduler == "DPMSolverMultistepScheduler":
            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self.pipe.scheduler.config, use_karras_sigmas=True
            )
        if scheduler == "EulerAncestralDiscreteScheduler":
            self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
                self.pipe.scheduler.config
            )
        else:
            self.pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
                self.pipe.scheduler.config, use_karras_sigmas=True
            )

        # Load and preprocess source image for img2img
        source_image = None
        if is_img2img:
            try:
                source_image = load_source_image(img_url=img_url, img_base64=img_base64)
                if source_image is None:
                    raise ValueError("No valid source image provided")

                # Resize to target dimensions
                source_image = resize_image_to_dimensions(source_image, width, height)
                logging.info(f"Source image processed: {source_image.size}")

            except Exception as e:
                logging.error(f"Failed to load source image: {e}")
                # Return error in webhook payload
                payload = {
                    "uuid": uuid,
                    "data": [],
                    "errors": [{"error": f"Failed to load source image: {str(e)}", "batch_index": -1, "seed": None}],
                }
                try:
                    requests.post(url, json=payload, timeout=30)
                except:
                    pass
                return payload

        result_array = [] # accumulate all results across the batch
        errors_all = []  # accumulate all errors across the batch

        for i in range(batch_nbr):
            if not seed:
                random_seed = random.randint(0, MAX_SEED)
                logging.info(f"Generated Seed: {random_seed}")
                generator = torch.Generator().manual_seed(random_seed)
            else:
                # if seed is provided, use the seed and increment by i at each iteration
                random_seed = seed+i
                generator = torch.Generator().manual_seed(random_seed)
            
            try:
                if is_img2img and source_image is not None:
                    # Create img2img pipeline from current t2i pipeline
                    img2img_pipe = self.model_manager.create_img2img_pipeline(self.pipe)
                    img2img_pipe.scheduler = self.pipe.scheduler  # Use same scheduler

                    # Upcast VAE to float32 to avoid deprecated upcast_vae warning
                    # Store original dtype to restore after inference
                    vae_original_dtype = img2img_pipe.vae.dtype
                    img2img_pipe.vae.to(torch.float32)

                    output_image = img2img_pipe(
                        image=source_image,
                        prompt_embeds=prompt_embeds,
                        pooled_prompt_embeds=pooled_prompt_embeds,
                        negative_prompt_embeds=prompt_neg_embeds,
                        negative_pooled_prompt_embeds=negative_pooled_prompt_embeds,
                        strength=strength,
                        guidance_scale=guidance_scale,
                        num_inference_steps=num_steps,
                        generator=generator,
                        clip_skip=clip_skip
                    ).images[0]

                    # Restore VAE to original dtype to save memory
                    img2img_pipe.vae.to(vae_original_dtype)
                else:
                    # Text-to-image path
                    output_image = self.pipe(
                        prompt_embeds=prompt_embeds,
                        pooled_prompt_embeds=pooled_prompt_embeds,
                        negative_prompt_embeds=prompt_neg_embeds,
                        negative_pooled_prompt_embeds=negative_pooled_prompt_embeds,
                        width=width,
                        height=height,
                        guidance_scale=guidance_scale,
                        num_inference_steps=num_steps,
                        generator=generator,
                        clip_skip=clip_skip
                    ).images[0]

                image_url = self.uploader.upload(output_image, uuid, i)
                result_array.append({"url": image_url, "seed": random_seed})
            except Exception as e:
                errors_all.append({
                    "error": str(e),
                    "batch_index": i,
                    "seed": random_seed,
                })
                result_array.append({
                    "url": None,
                    "seed": random_seed,
                })
        payload = {
            "uuid": uuid,
            "data": result_array,
            "errors": errors_all,
        }

        # Only send webhook if URL is provided
        if url and url.strip():
            try:
                res = requests.post(url, json=payload, timeout=30)
                if res.status_code != 200:
                    logging.info(f"Error sending result to {url}: {res.text}")
                else:
                    logging.info(f"Result successfully sent to {url}")
            except requests.exceptions.RequestException as e:
                logging.info(f"Request failed: {e}")
        else:
            logging.info("No webhook URL provided, skipping callback")

        return payload


@load
def setup():
    """Load the SDXL model manager (runs once before ready signal)."""
    logging.info("Initializing SDXL Multi-Model...")
    model = Model()
    model.load()
    logging.info("SDXL Multi-Model ready!")
    return {"model": model}


@task
def process(payload: dict, ctx: dict) -> dict:
    """Process an image generation task."""
    model = ctx["model"]
    # Extract model_input and merge with top-level fields (id, webhook_url)
    model_input = payload.get("model_input", {})
    model_input["id"] = payload.get("id")
    model_input["webhook_url"] = payload.get("webhook_url")
    return model.predict(model_input)


if __name__ == "__main__":
    run()
