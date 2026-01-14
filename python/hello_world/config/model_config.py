"""
Model configuration loader for YAML-based model definitions.
Supports on-demand model downloading from Azure or HuggingFace.
"""
import os
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

import yaml

logger = logging.getLogger(__name__)

# Default local storage path for downloaded models
DEFAULT_MODEL_DIR = "/root/data"


@dataclass
class ModelSource:
    """Represents a single source location for a model."""
    type: str  # 'local', 'azure', or 'huggingface'
    path: Optional[str] = None  # For local type
    url: Optional[str] = None   # For azure or huggingface type


@dataclass
class ModelConfig:
    """Configuration for a single model."""
    name: str
    filename: str
    pipeline: str
    sources: List[ModelSource]


def download_model_from_url(url: str, local_path: str, use_azcopy: bool = False) -> bool:
    """
    Download a model file from URL to local path.

    Args:
        url: The URL to download from (Azure blob or HuggingFace)
        local_path: The local path to save the file
        use_azcopy: If True, use azcopy for download (recommended for Azure)

    Returns:
        True if download succeeded, False otherwise
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    try:
        if use_azcopy:
            # Use azcopy for Azure blob storage (faster, supports resume)
            logger.info(f"Downloading with azcopy: {url} -> {local_path}")
            result = subprocess.run(
                ["azcopy", "copy", url, local_path, "--check-md5=FailIfDifferent"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                logger.error(f"azcopy failed: {result.stderr}")
                return False
            logger.info(f"Downloaded successfully: {local_path}")
            return True
        else:
            # Use wget/curl for HuggingFace or fallback
            logger.info(f"Downloading with wget: {url} -> {local_path}")
            result = subprocess.run(
                ["wget", "-q", "--show-progress", "-O", local_path, url],
                capture_output=False
            )
            if result.returncode != 0:
                logger.error(f"wget failed with code {result.returncode}")
                return False
            logger.info(f"Downloaded successfully: {local_path}")
            return True

    except FileNotFoundError as e:
        logger.error(f"Download tool not found: {e}")
        return False
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return False


class ModelConfigLoader:
    """Loads and validates model configurations from YAML file."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Default to models.yml in the same directory as this file
            config_path = Path(__file__).parent / "models.yml"

        self.config_path = Path(config_path)
        self._models: Dict[str, ModelConfig] = {}
        self._loaded = False

    def load(self) -> Dict[str, ModelConfig]:
        """Load and parse the YAML configuration file."""
        if self._loaded:
            return self._models

        if not self.config_path.exists():
            raise FileNotFoundError(f"Model config file not found: {self.config_path}")

        logger.info(f"Loading model configuration from {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        if not config_data or 'models' not in config_data:
            raise ValueError("Invalid config file: missing 'models' section")

        for model_name, model_data in config_data['models'].items():
            self._validate_model_config(model_name, model_data)

            sources = []
            for source_data in model_data['sources']:
                source = ModelSource(
                    type=source_data['type'],
                    path=source_data.get('path'),
                    url=source_data.get('url')
                )
                sources.append(source)

            self._models[model_name] = ModelConfig(
                name=model_name,
                filename=model_data['filename'],
                pipeline=model_data['pipeline'],
                sources=sources
            )

        self._loaded = True
        logger.info(f"Loaded {len(self._models)} model configurations")
        return self._models

    def _validate_model_config(self, model_name: str, model_data: dict):
        """Validate required fields for a model configuration."""
        required_fields = ['filename', 'pipeline', 'sources']
        for field in required_fields:
            if field not in model_data:
                raise ValueError(f"Model '{model_name}' missing required field: {field}")

        if not model_data['sources']:
            raise ValueError(f"Model '{model_name}' must have at least one source")

        for i, source in enumerate(model_data['sources']):
            if 'type' not in source:
                raise ValueError(f"Model '{model_name}' source {i} missing 'type' field")

            source_type = source['type']
            if source_type == 'local' and 'path' not in source:
                raise ValueError(f"Model '{model_name}' local source {i} missing 'path' field")
            elif source_type in ('azure', 'huggingface') and 'url' not in source:
                raise ValueError(f"Model '{model_name}' {source_type} source {i} missing 'url' field")

    def get_model_config(self, model_name: str) -> ModelConfig:
        """Get configuration for a specific model."""
        if not self._loaded:
            self.load()

        if model_name not in self._models:
            available = list(self._models.keys())
            raise ValueError(f"Unknown model: {model_name}. Available models: {available}")

        return self._models[model_name]

    def get_all_model_names(self) -> List[str]:
        """Get list of all available model names."""
        if not self._loaded:
            self.load()
        return list(self._models.keys())

    def resolve_model_path(self, model_name: str) -> str:
        """
        Resolve the path for a model, downloading if necessary.

        Priority order:
        1. Local path (if file exists)
        2. Azure URL (download to local, then use local path)
        3. HuggingFace URL (download to local or use directly)

        Returns:
            The local path to use for loading the model.
        """
        config = self.get_model_config(model_name)
        local_path = None

        # First pass: find local path and check if exists
        for source in config.sources:
            if source.type == 'local':
                local_path = source.path
                if os.path.exists(source.path):
                    logger.info(f"Using local model: {source.path}")
                    return source.path
                else:
                    logger.debug(f"Local path not found: {source.path}")
                break

        # If no local path defined, create one
        if local_path is None:
            local_path = os.path.join(DEFAULT_MODEL_DIR, config.filename)

        # Second pass: try to download from Azure or HuggingFace
        for source in config.sources:
            if source.type == 'azure':
                logger.info(f"Attempting Azure download for {model_name}...")
                if download_model_from_url(source.url, local_path, use_azcopy=True):
                    logger.info(f"Successfully downloaded from Azure: {local_path}")
                    return local_path
                else:
                    logger.warning(f"Azure download failed, trying next source...")

            elif source.type == 'huggingface':
                # Try downloading to local first
                logger.info(f"Attempting HuggingFace download for {model_name}...")
                if download_model_from_url(source.url, local_path, use_azcopy=False):
                    logger.info(f"Successfully downloaded from HuggingFace: {local_path}")
                    return local_path
                else:
                    # Fallback: return HuggingFace URL directly (diffusers can load from URL)
                    logger.warning(f"Download failed, using HuggingFace URL directly")
                    return source.url

        raise FileNotFoundError(
            f"No available source found for model '{model_name}'. "
            f"Checked {len(config.sources)} sources."
        )

    def download_all_models(self) -> Dict[str, bool]:
        """
        Download all models from their remote sources.

        Returns:
            Dict mapping model name to download success status
        """
        if not self._loaded:
            self.load()

        results = {}
        for model_name in self._models:
            logger.info(f"Pre-downloading model: {model_name}")
            try:
                path = self.resolve_model_path(model_name)
                results[model_name] = os.path.exists(path)
                logger.info(f"Model {model_name}: {'OK' if results[model_name] else 'FAILED'}")
            except Exception as e:
                logger.error(f"Failed to download {model_name}: {e}")
                results[model_name] = False

        return results


# Global singleton instance
_config_loader: Optional[ModelConfigLoader] = None


def get_config_loader() -> ModelConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ModelConfigLoader()
    return _config_loader


def get_model_config(model_name: str) -> ModelConfig:
    """Convenience function to get a model config."""
    return get_config_loader().get_model_config(model_name)


def get_all_model_names() -> List[str]:
    """Convenience function to get all model names."""
    return get_config_loader().get_all_model_names()


def resolve_model_path(model_name: str) -> str:
    """Convenience function to resolve a model path (downloads if needed)."""
    return get_config_loader().resolve_model_path(model_name)


def download_all_models() -> Dict[str, bool]:
    """Convenience function to download all models."""
    return get_config_loader().download_all_models()
