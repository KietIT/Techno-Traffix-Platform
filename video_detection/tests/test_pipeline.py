"""Tests for inference pipeline configuration - UPDATED FOR 4-STAGE LOGIC."""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.inference_pipeline import PipelineConfig


def test_pipeline_config_defaults():
    """Test default pipeline configuration with optimized values."""
    config = PipelineConfig()
    assert config.model_path == "yolov8l.pt"
    assert config.device == "cuda"
    # Updated defaults for Vietnam traffic optimization
    assert config.conf_threshold == 0.25  # Lowered for better detection
    assert config.iou_threshold == 0.55  # Increased to keep close vehicles
    assert config.draw_bboxes is True
    assert config.draw_tracks is True
    assert config.draw_accidents is True


def test_pipeline_config_custom():
    """Test custom pipeline configuration."""
    config = PipelineConfig(model_path="custom.pt", device="cpu", conf_threshold=0.6, iou_threshold=0.5)
    assert config.model_path == "custom.pt"
    assert config.device == "cpu"
    assert config.conf_threshold == 0.6
    assert config.iou_threshold == 0.5


def test_pipeline_config_tracker_settings():
    """Test tracker settings in configuration."""
    config = PipelineConfig(track_buffer=60, track_thresh=0.5, match_thresh=0.9)
    assert config.track_buffer == 60
    assert config.track_thresh == 0.5
    assert config.match_thresh == 0.9


def test_pipeline_config_video_settings():
    """Test video settings in configuration."""
    config = PipelineConfig(resize_width=1920, resize_height=1080, target_fps=30.0)
    assert config.resize_width == 1920
    assert config.resize_height == 1080
    assert config.target_fps == 30.0


def test_pipeline_config_accident_settings():
    """Test 4-stage accident detection settings."""
    config = PipelineConfig(
        proximity_iou_threshold=0.1,
        proximity_distance_threshold=120.0,
        collision_iou_threshold=0.2,
        collision_min_frames=6,
        velocity_change_threshold=0.5,
        post_collision_window=100,
        min_indicators_for_accident=4,
    )
    assert config.proximity_iou_threshold == 0.1
    assert config.proximity_distance_threshold == 120.0
    assert config.collision_iou_threshold == 0.2
    assert config.collision_min_frames == 6
    assert config.velocity_change_threshold == 0.5
    assert config.post_collision_window == 100
    assert config.min_indicators_for_accident == 4


def test_pipeline_config_size_filtering():
    """Test size filtering settings."""
    config = PipelineConfig(min_box_area=500, max_box_area=400000, min_aspect_ratio=0.4, max_aspect_ratio=3.5)
    assert config.min_box_area == 500
    assert config.max_box_area == 400000
    assert config.min_aspect_ratio == 0.4
    assert config.max_aspect_ratio == 3.5


def test_pipeline_config_speed_estimation():
    """Test speed estimation settings."""
    config = PipelineConfig(speed_history_length=25, acceleration_window=6, smooth_window=4)
    assert config.speed_history_length == 25
    assert config.acceleration_window == 6
    assert config.smooth_window == 4
