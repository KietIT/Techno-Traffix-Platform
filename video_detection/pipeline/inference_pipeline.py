"""
Inference Pipeline module.

Provides:
- InferencePipeline: Orchestrates the complete detection workflow
- Connects video input -> detection -> tracking -> speed -> accident detection
"""

import logging
import time
import cv2
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass, field
from pathlib import Path

import yaml
import numpy as np

from video_io.video_reader import VideoReader, FrameInfo
from tracker.bytetrack_tracker import ByteTrackTracker, TrackedObject
from speed_estimation.speed_estimator import SpeedEstimator, SpeedInfo
from accident_detection.rule_based import AccidentDetector, AccidentEvent


logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the inference pipeline - OPTIMIZED FOR VIETNAM TRAFFIC."""

    # Model settings
    model_path: str = "yolov8l.pt"
    device: str = "cuda"
    conf_threshold: float = 0.25  # Lowered for better detection
    iou_threshold: float = 0.55  # Increased to keep close vehicles

    # Class-specific confidence thresholds
    class_conf_thresholds: Optional[Dict[str, float]] = None

    # Size filtering
    min_box_area: int = 400
    max_box_area: int = 500000
    min_aspect_ratio: float = 0.3
    max_aspect_ratio: float = 4.0

    # Tracker settings
    track_buffer: int = 50  # Increased for better occlusion handling
    track_thresh: float = 0.4
    match_thresh: float = 0.85

    # Speed estimation
    pixels_per_meter: float = 50.0
    speed_history_length: int = 20
    acceleration_window: int = 5
    smooth_window: int = 3

    # Accident detection - 4-stage parameters
    proximity_iou_threshold: float = 0.05
    proximity_distance_threshold: float = 100.0
    collision_iou_threshold: float = 0.15
    collision_min_frames: int = 5
    velocity_change_threshold: float = 0.4
    post_collision_window: int = 90
    min_indicators_for_accident: int = 3

    # Video settings
    resize_width: Optional[int] = 1920  # Increased for better detection
    resize_height: Optional[int] = 1080
    target_fps: Optional[float] = None

    # Output settings
    draw_bboxes: bool = True
    draw_tracks: bool = True
    draw_accidents: bool = True

    @classmethod
    def from_yaml(cls, config_path: str) -> "PipelineConfig":
        """Load configuration from YAML file."""
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)

        config = cls()

        # Model
        if "model" in data:
            config.model_path = data["model"].get("path", config.model_path)
            config.device = data["model"].get("device", config.device)
            config.conf_threshold = data["model"].get("conf_threshold", config.conf_threshold)
            config.iou_threshold = data["model"].get("iou_threshold", config.iou_threshold)

            # Class-specific thresholds
            config.class_conf_thresholds = data["model"].get("class_conf_thresholds", None)

            # Size filtering
            config.min_box_area = data["model"].get("min_box_area", config.min_box_area)
            config.max_box_area = data["model"].get("max_box_area", config.max_box_area)
            config.min_aspect_ratio = data["model"].get("min_aspect_ratio", config.min_aspect_ratio)
            config.max_aspect_ratio = data["model"].get("max_aspect_ratio", config.max_aspect_ratio)

        # Tracker
        if "tracker" in data:
            config.track_buffer = data["tracker"].get("track_buffer", config.track_buffer)
            config.track_thresh = data["tracker"].get("track_thresh", config.track_thresh)
            config.match_thresh = data["tracker"].get("match_thresh", config.match_thresh)

        # Speed estimation
        if "speed_estimation" in data:
            config.pixels_per_meter = data["speed_estimation"].get("pixels_per_meter", config.pixels_per_meter)
            config.speed_history_length = data["speed_estimation"].get("history_length", config.speed_history_length)
            config.acceleration_window = data["speed_estimation"].get("acceleration_window", config.acceleration_window)
            config.smooth_window = data["speed_estimation"].get("smooth_window", config.smooth_window)

        # Accident detection - 4-stage
        if "accident_detection" in data:
            ad = data["accident_detection"]

            # Proximity stage
            if "proximity" in ad:
                config.proximity_iou_threshold = ad["proximity"].get("iou_threshold", config.proximity_iou_threshold)
                config.proximity_distance_threshold = ad["proximity"].get(
                    "distance_threshold", config.proximity_distance_threshold
                )

            # Collision stage
            if "collision" in ad:
                config.collision_iou_threshold = ad["collision"].get("iou_threshold", config.collision_iou_threshold)
                config.collision_min_frames = ad["collision"].get("min_frames", config.collision_min_frames)
                config.velocity_change_threshold = ad["collision"].get(
                    "velocity_change_threshold", config.velocity_change_threshold
                )

            # Post-collision stage
            if "post_collision" in ad:
                config.post_collision_window = ad["post_collision"].get("analysis_window", config.post_collision_window)

            # Confirmation stage
            if "confirmation" in ad:
                config.min_indicators_for_accident = ad["confirmation"].get(
                    "min_indicators", config.min_indicators_for_accident
                )

        # Video IO
        if "video_io" in data:
            config.resize_width = data["video_io"].get("resize_width", config.resize_width)
            config.resize_height = data["video_io"].get("resize_height", config.resize_height)

        return config


@dataclass
class FrameResult:
    """Result for a single frame processing."""

    frame_id: int
    timestamp: float
    tracked_objects: List[TrackedObject]
    speed_infos: Dict[int, SpeedInfo]
    accident_events: List[AccidentEvent]
    processing_time: float
    annotated_frame: Optional[np.ndarray] = None


class InferencePipeline:
    """
    Complete inference pipeline for video-based traffic detection.

    Flow:
    1. Read frame from video
    2. Run tracking (detection + ByteTrack)
    3. Estimate speeds
    4. Detect accidents
    5. Annotate frame (optional)
    6. Yield results
    """

    def __init__(self, config: Optional[PipelineConfig] = None, config_path: Optional[str] = None):
        """
        Initialize pipeline.

        Args:
            config: PipelineConfig object
            config_path: Path to YAML config (alternative to config object)
        """
        if config_path:
            self.config = PipelineConfig.from_yaml(config_path)
        elif config:
            self.config = config
        else:
            self.config = PipelineConfig()

        self.tracker: Optional[ByteTrackTracker] = None
        self.speed_estimator: Optional[SpeedEstimator] = None
        self.accident_detector: Optional[AccidentDetector] = None

        self._initialized = False

        logger.info("InferencePipeline created")

    def initialize(self, fps: float = 30.0) -> None:
        """
        Initialize all components.

        Args:
            fps: Video FPS for time-based calculations
        """
        logger.info("Initializing pipeline components...")

        # Initialize tracker with optimized parameters
        self.tracker = ByteTrackTracker(
            model_path=self.config.model_path,
            device=self.config.device,
            conf_threshold=self.config.conf_threshold,
            iou_threshold=self.config.iou_threshold,
            track_thresh=self.config.track_thresh,
            track_buffer=self.config.track_buffer,
            match_thresh=self.config.match_thresh,
            history_length=self.config.speed_history_length,
        )

        # Initialize speed estimator with acceleration support
        self.speed_estimator = SpeedEstimator(
            fps=fps,
            pixels_per_meter=self.config.pixels_per_meter,
            heading_history_length=self.config.speed_history_length,
            acceleration_window=self.config.acceleration_window,
            smooth_window=self.config.smooth_window,
        )

        # Initialize speed estimator
        self.speed_estimator = SpeedEstimator(fps=fps, pixels_per_meter=self.config.pixels_per_meter)

        # Initialize accident detector with 4-stage parameters
        self.accident_detector = AccidentDetector(
            proximity_iou_threshold=self.config.proximity_iou_threshold,
            proximity_distance_threshold=self.config.proximity_distance_threshold,
            collision_iou_threshold=self.config.collision_iou_threshold,
            collision_min_frames=self.config.collision_min_frames,
            velocity_change_threshold=self.config.velocity_change_threshold,
            post_collision_window=self.config.post_collision_window,
            min_indicators_for_accident=self.config.min_indicators_for_accident,
            fps=fps,
        )

        self._initialized = True
        logger.info("Pipeline components initialized")

    def process_frame(
        self, frame: np.ndarray, frame_id: int, timestamp: float = 0.0, annotate: bool = True
    ) -> FrameResult:
        """
        Process a single frame.

        Args:
            frame: Input frame (BGR)
            frame_id: Frame sequence number
            timestamp: Frame timestamp in seconds
            annotate: Whether to annotate the output frame

        Returns:
            FrameResult with all detection info
        """
        if not self._initialized:
            self.initialize()

        # Type assertions for type checker
        assert self.tracker is not None
        assert self.speed_estimator is not None
        assert self.accident_detector is not None

        start_time = time.time()

        # Step 1: Run tracking
        tracked_objects = self.tracker.track(frame, frame_id)

        # Step 2: Estimate speeds
        speed_infos = self.speed_estimator.estimate_speeds(tracked_objects)

        # Step 3: Detect accidents
        accident_events = self.accident_detector.detect(tracked_objects, speed_infos, frame_id, timestamp)

        processing_time = time.time() - start_time

        # Step 4: Annotate frame if requested
        annotated_frame = None
        if annotate:
            annotated_frame = self._annotate_frame(frame.copy(), tracked_objects, speed_infos, accident_events)

        return FrameResult(
            frame_id=frame_id,
            timestamp=timestamp,
            tracked_objects=tracked_objects,
            speed_infos=speed_infos,
            accident_events=accident_events,
            processing_time=processing_time,
            annotated_frame=annotated_frame,
        )

    def _annotate_frame(
        self,
        frame: np.ndarray,
        tracked_objects: List[TrackedObject],
        speed_infos: Dict[int, SpeedInfo],
        accident_events: List[AccidentEvent],
    ) -> np.ndarray:
        """Draw annotations on frame."""

        # Draw tracked objects
        if self.config.draw_bboxes:
            for obj in tracked_objects:
                x1, y1, x2, y2 = obj.bbox

                # Choose color based on class
                color = (0, 255, 0)  # Default green
                if obj.class_name == "ambulance":
                    color = (255, 0, 0)  # Blue for ambulance
                elif obj.class_name == "truck":
                    color = (0, 165, 255)  # Orange for truck
                elif obj.class_name == "motorcycle":
                    color = (255, 255, 0)  # Cyan for motorcycle

                # Draw box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                # Draw label with track ID
                label = f"{obj.class_name} ID:{obj.track_id}"

                # Add speed if available
                if obj.track_id in speed_infos:
                    speed = speed_infos[obj.track_id].current_speed
                    label += f" {speed:.1f}px/f"

                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw track trails
        if self.config.draw_tracks:
            for obj in tracked_objects:
                if len(obj.centroid_history) > 1:
                    points = np.array(obj.centroid_history, dtype=np.int32)
                    cv2.polylines(frame, [points], False, (255, 0, 255), 2)

        # Draw accident markers
        if self.config.draw_accidents:
            for event in accident_events:
                # Flash red rectangles for accident locations
                for bbox in event.bboxes:
                    x1, y1, x2, y2 = bbox
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 4)

                # Draw accident text
                cx, cy = int(event.location[0]), int(event.location[1])
                cv2.putText(
                    frame,
                    f"ACCIDENT: {event.event_type.value}",
                    (cx - 100, cy - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2,
                )

        return frame

    def run(
        self,
        video_source: str,
        callback: Optional[Callable[[FrameResult], bool]] = None,
        show_preview: bool = False,
        max_frames: Optional[int] = None,
    ) -> List[AccidentEvent]:
        """
        Run pipeline on a video source.

        Args:
            video_source: Path to video file or RTSP URL
            callback: Optional callback for each frame (return False to stop)
            show_preview: Show preview window
            max_frames: Maximum frames to process (None = all)

        Returns:
            List of all detected accident events
        """
        logger.info(f"Starting pipeline on: {video_source}")

        # Create video reader
        reader = VideoReader(
            source=video_source,
            resize_width=self.config.resize_width,
            resize_height=self.config.resize_height,
            target_fps=self.config.target_fps,
        )

        if not reader.open():
            logger.error(f"Failed to open video source: {video_source}")
            return []

        # Initialize with video FPS
        self.initialize(fps=reader.fps)

        all_accidents = []
        frame_count = 0

        try:
            for frame_info in reader.frames():
                # Process frame
                result = self.process_frame(
                    frame_info.frame,
                    frame_info.frame_id,
                    frame_info.timestamp,
                    annotate=show_preview or callback is not None,
                )

                # Collect accidents
                all_accidents.extend(result.accident_events)

                # Call callback if provided
                if callback:
                    if not callback(result):
                        logger.info("Pipeline stopped by callback")
                        break

                # Show preview
                if show_preview and result.annotated_frame is not None:
                    cv2.imshow("Video Detection", result.annotated_frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        logger.info("Pipeline stopped by user (q pressed)")
                        break

                frame_count += 1

                # Log progress periodically
                if frame_count % 100 == 0:
                    logger.info(f"Processed {frame_count} frames, {len(all_accidents)} accidents detected")

                # Check max frames
                if max_frames and frame_count >= max_frames:
                    logger.info(f"Reached max frames: {max_frames}")
                    break

        finally:
            reader.close()
            if show_preview:
                cv2.destroyAllWindows()

        logger.info(f"Pipeline complete: {frame_count} frames, {len(all_accidents)} accidents")
        return all_accidents

    def reset(self) -> None:
        """Reset pipeline state."""
        if self.tracker:
            self.tracker.reset()
        if self.accident_detector:
            self.accident_detector.reset()
        logger.info("Pipeline reset")
