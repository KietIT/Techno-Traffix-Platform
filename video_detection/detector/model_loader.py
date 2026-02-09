"""
Model Loader module for YOLOv8.

Provides:
- Factory function for loading YOLO models
- Model caching for efficiency
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from ultralytics import YOLO


logger = logging.getLogger(__name__)

# Cache for loaded models
_model_cache: Dict[str, YOLO] = {}


def load_model(
    model_path: str,
    device: str = "cuda",
    use_cache: bool = True
) -> YOLO:
    """
    Load a YOLO model.
    
    Args:
        model_path: Path to model weights (.pt file) or model name (e.g., 'yolov8l.pt')
        device: Device to load model on ('cuda', 'cpu', '0', '1', etc.)
        use_cache: Whether to cache the loaded model
        
    Returns:
        Loaded YOLO model
        
    Raises:
        FileNotFoundError: If model file doesn't exist
        RuntimeError: If model loading fails
    """
    global _model_cache
    
    # Check cache first
    cache_key = f"{model_path}_{device}"
    if use_cache and cache_key in _model_cache:
        logger.debug(f"Returning cached model: {model_path}")
        return _model_cache[cache_key]
    
    # Check if model file exists (for custom models)
    if not model_path.startswith("yolov") and not Path(model_path).exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    logger.info(f"Loading YOLO model: {model_path} on device: {device}")
    
    try:
        model = YOLO(model_path)
        
        # Move model to device
        # Note: YOLO handles device placement internally during inference
        # but we can set default device
        model.to(device)
        
        logger.info(f"Model loaded successfully: {model_path}")
        logger.info(f"  Model type: {type(model).__name__}")
        logger.info(f"  Classes: {len(model.names)} classes")
        
        # Cache the model
        if use_cache:
            _model_cache[cache_key] = model
        
        return model
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise RuntimeError(f"Failed to load model {model_path}: {e}")


def clear_cache() -> None:
    """Clear the model cache."""
    global _model_cache
    _model_cache.clear()
    logger.info("Model cache cleared")


def get_cached_models() -> list:
    """Get list of cached model keys."""
    return list(_model_cache.keys())
