"""
YOLO Detector module - OPTIMIZED FOR VIETNAM TRAFFIC.

Provides:
- YOLODetector: Wrapper class for YOLOv8 object detection
- Supports easy model swapping (v8, v9, v10, etc.)
- Class-specific confidence thresholds for better motorcycle detection
- Size filtering to reduce false positives
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass

import numpy as np

from .model_loader import load_model


logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Container for a single detection result."""

    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    class_id: int
    class_name: str
    confidence: float
    track_id: Optional[int] = None  # Assigned by tracker

    @property
    def centroid(self) -> Tuple[float, float]:
        """Calculate center point of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def area(self) -> float:
        """Calculate area of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return max(0, x2 - x1) * max(0, y2 - y1)

    @property
    def width(self) -> int:
        """Get bounding box width."""
        return self.bbox[2] - self.bbox[0]

    @property
    def height(self) -> int:
        """Get bounding box height."""
        return self.bbox[3] - self.bbox[1]

    @property
    def aspect_ratio(self) -> float:
        """Calculate width/height ratio."""
        h = self.height
        if h == 0:
            return 0.0
        return self.width / h


class YOLODetector:
    """
    YOLO-based object detector - OPTIMIZED FOR VIETNAM TRAFFIC.

    Wraps ultralytics YOLO for vehicle detection.
    Designed to be model-agnostic (can swap YOLOv8 with v9, v10, etc.).

    Optimizations:
    - Class-specific confidence thresholds (lower for motorcycles)
    - Size filtering to reduce false positives
    - Aspect ratio filtering
    """

    # Default class mapping for COCO-based models
    DEFAULT_VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    # Custom class mapping for traffic models
    TRAFFIC_CLASS_MAPPING = {
        "car": "car",
        "xe_oto": "car",
        "truck": "truck",
        "xe_tai": "truck",
        "bus": "truck",
        "motorcycle": "motorcycle",
        "moto": "motorcycle",
        "xe_may": "motorcycle",
        "motorbike": "motorcycle",
        "bicycle": "motorcycle",  # Treat bicycles as motorcycles for tracking
        "ambulance": "ambulance",
        "xe_cap_cuu": "ambulance",
    }

    # Default class-specific confidence thresholds
    DEFAULT_CLASS_CONF_THRESHOLDS = {
        "motorcycle": 0.20,  # Lower threshold for small objects
        "car": 0.30,
        "truck": 0.35,
        "bus": 0.35,
        "ambulance": 0.30,
    }

    def __init__(
        self,
        model_path: str = "yolov8l.pt",
        device: str = "cuda",
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.55,
        target_classes: Optional[List[str]] = None,
        # NEW: Class-specific thresholds
        class_conf_thresholds: Optional[Dict[str, float]] = None,
        # NEW: Size filtering
        min_box_area: int = 400,
        max_box_area: int = 500000,
        min_aspect_ratio: float = 0.3,
        max_aspect_ratio: float = 4.0,
    ):
        """
        Initialize YOLO detector with optimizations.

        Args:
            model_path: Path to YOLO model weights
            device: Device for inference ('cuda', 'cpu')
            conf_threshold: Base confidence threshold (used if class-specific not set)
            iou_threshold: IOU threshold for NMS
            target_classes: List of class names to detect (None = all vehicles)
            class_conf_thresholds: Dict of class_name -> confidence threshold
            min_box_area: Minimum detection area in pixels
            max_box_area: Maximum detection area in pixels
            min_aspect_ratio: Minimum width/height ratio
            max_aspect_ratio: Maximum width/height ratio
        """
        self.model_path = model_path
        self.device = device
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.target_classes = target_classes or ["car", "truck", "motorcycle", "ambulance"]

        # Class-specific confidence thresholds
        self.class_conf_thresholds = class_conf_thresholds or self.DEFAULT_CLASS_CONF_THRESHOLDS

        # Size filtering parameters
        self.min_box_area = min_box_area
        self.max_box_area = max_box_area
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio

        # Load model
        self.model = load_model(model_path, device)

        # Build class ID to name mapping
        self._class_names = self.model.names
        self._build_class_filter()

        # Statistics tracking
        self._detection_stats = {
            "total_raw": 0,
            "filtered_conf": 0,
            "filtered_size": 0,
            "filtered_aspect": 0,
            "passed": 0,
        }

        logger.info(f"YOLODetector initialized (OPTIMIZED)")
        logger.info(f"  Base conf_threshold: {conf_threshold}")
        logger.info(f"  Class-specific thresholds: {self.class_conf_thresholds}")
        logger.info(
            f"  Size filter: area [{min_box_area}, {max_box_area}], aspect [{min_aspect_ratio}, {max_aspect_ratio}]"
        )
        logger.info(f"  Target classes: {self.target_classes}")

    def _build_class_filter(self) -> None:
        """Build filter for target classes based on model's class names."""
        self._target_class_ids = []
        self._class_id_to_normalized = {}

        for class_id, class_name in self._class_names.items():
            # Normalize class name
            normalized = self.TRAFFIC_CLASS_MAPPING.get(class_name.lower(), class_name.lower())

            if normalized in self.target_classes:
                self._target_class_ids.append(class_id)
                self._class_id_to_normalized[class_id] = normalized

        logger.debug(f"Target class IDs: {self._target_class_ids}")

    def _get_conf_threshold_for_class(self, class_name: str) -> float:
        """Get confidence threshold for a specific class."""
        return self.class_conf_thresholds.get(class_name, self.conf_threshold)

    def _passes_size_filter(self, bbox: Tuple[int, int, int, int]) -> Tuple[bool, str]:
        """
        Check if detection passes size and aspect ratio filters.

        Returns:
            Tuple of (passes, reason_if_failed)
        """
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        area = width * height

        # Check area bounds
        if area < self.min_box_area:
            return False, "area_too_small"
        if area > self.max_box_area:
            return False, "area_too_large"

        # Check aspect ratio
        if height > 0:
            aspect_ratio = width / height
            if aspect_ratio < self.min_aspect_ratio:
                return False, "aspect_too_narrow"
            if aspect_ratio > self.max_aspect_ratio:
                return False, "aspect_too_wide"

        return True, ""

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Run detection on a single frame with optimized filtering.

        Args:
            frame: Input image (BGR format, numpy array)

        Returns:
            List of Detection objects (filtered by confidence and size)
        """
        detections = []

        # Run YOLO inference with LOW base threshold to catch all candidates
        # We'll apply class-specific thresholds later
        min_conf = min(self.class_conf_thresholds.values()) if self.class_conf_thresholds else self.conf_threshold
        min_conf = min(min_conf, self.conf_threshold) * 0.8  # 20% lower to not miss edge cases

        results = self.model(frame, conf=min_conf, iou=self.iou_threshold, verbose=False)

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                self._detection_stats["total_raw"] += 1

                class_id = int(box.cls[0])

                # Skip if not in target classes
                if self._target_class_ids and class_id not in self._target_class_ids:
                    continue

                # Extract bounding box
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])

                # Get class name and normalize
                class_name = self._class_names.get(class_id, "unknown")
                normalized_name = self.TRAFFIC_CLASS_MAPPING.get(class_name.lower(), class_name.lower())

                # Apply class-specific confidence threshold
                class_threshold = self._get_conf_threshold_for_class(normalized_name)
                if confidence < class_threshold:
                    self._detection_stats["filtered_conf"] += 1
                    continue

                bbox = (x1, y1, x2, y2)

                # Apply size filter
                passes_size, filter_reason = self._passes_size_filter(bbox)
                if not passes_size:
                    if "aspect" in filter_reason:
                        self._detection_stats["filtered_aspect"] += 1
                    else:
                        self._detection_stats["filtered_size"] += 1
                    continue

                detection = Detection(bbox=bbox, class_id=class_id, class_name=normalized_name, confidence=confidence)
                detections.append(detection)
                self._detection_stats["passed"] += 1

        return detections

    def detect_with_details(self, frame: np.ndarray) -> Tuple[List[Detection], Dict[str, int]]:
        """
        Run detection and return both results and filtering statistics.

        Useful for debugging and tuning parameters.

        Args:
            frame: Input image (BGR format, numpy array)

        Returns:
            Tuple of (detections, stats_dict)
        """
        # Reset stats for this frame
        frame_stats = {"total_raw": 0, "filtered_conf": 0, "filtered_size": 0, "filtered_aspect": 0, "passed": 0}

        # Store current stats
        old_stats = self._detection_stats.copy()
        self._detection_stats = frame_stats

        # Run detection
        detections = self.detect(frame)

        # Get frame stats
        result_stats = self._detection_stats.copy()

        # Restore cumulative stats
        for key in old_stats:
            self._detection_stats[key] = old_stats[key] + result_stats[key]

        return detections, result_stats

    def get_class_names(self) -> Dict[int, str]:
        """Get model's class names mapping."""
        return self._class_names.copy()

    def get_detection_stats(self) -> Dict[str, int]:
        """Get cumulative detection statistics."""
        return self._detection_stats.copy()

    def reset_stats(self) -> None:
        """Reset detection statistics."""
        self._detection_stats = {
            "total_raw": 0,
            "filtered_conf": 0,
            "filtered_size": 0,
            "filtered_aspect": 0,
            "passed": 0,
        }

    def update_thresholds(
        self,
        conf_threshold: Optional[float] = None,
        iou_threshold: Optional[float] = None,
        class_conf_thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Update detection thresholds.

        Args:
            conf_threshold: New base confidence threshold
            iou_threshold: New IOU threshold for NMS
            class_conf_thresholds: New class-specific confidence thresholds
        """
        if conf_threshold is not None:
            self.conf_threshold = conf_threshold
        if iou_threshold is not None:
            self.iou_threshold = iou_threshold
        if class_conf_thresholds is not None:
            self.class_conf_thresholds.update(class_conf_thresholds)

        logger.info(f"Thresholds updated: base_conf={self.conf_threshold}, iou={self.iou_threshold}")
        logger.info(f"  Class thresholds: {self.class_conf_thresholds}")

    def update_size_filters(
        self,
        min_box_area: Optional[int] = None,
        max_box_area: Optional[int] = None,
        min_aspect_ratio: Optional[float] = None,
        max_aspect_ratio: Optional[float] = None,
    ) -> None:
        """
        Update size filtering parameters.

        Args:
            min_box_area: Minimum detection area
            max_box_area: Maximum detection area
            min_aspect_ratio: Minimum width/height ratio
            max_aspect_ratio: Maximum width/height ratio
        """
        if min_box_area is not None:
            self.min_box_area = min_box_area
        if max_box_area is not None:
            self.max_box_area = max_box_area
        if min_aspect_ratio is not None:
            self.min_aspect_ratio = min_aspect_ratio
        if max_aspect_ratio is not None:
            self.max_aspect_ratio = max_aspect_ratio

        logger.info(
            f"Size filters updated: area=[{self.min_box_area}, {self.max_box_area}], "
            f"aspect=[{self.min_aspect_ratio}, {self.max_aspect_ratio}]"
        )
