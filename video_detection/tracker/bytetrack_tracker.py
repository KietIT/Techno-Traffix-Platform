"""
ByteTrack Tracker module.

Provides:
- ByteTrackTracker: Wrapper for object tracking using YOLO's built-in ByteTrack
- Track management and ID assignment
"""

import logging
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np

from detector.yolo_detector import Detection
from detector.model_loader import load_model


logger = logging.getLogger(__name__)


@dataclass
class TrackedObject:
    """Container for a tracked object with history."""
    track_id: int
    bbox: Tuple[int, int, int, int]
    class_id: int
    class_name: str
    confidence: float
    centroid: Tuple[float, float]
    frame_id: int
    
    # History for speed calculation
    centroid_history: List[Tuple[float, float]] = field(default_factory=list)
    frame_history: List[int] = field(default_factory=list)
    
    def update_history(self, max_history: int = 30) -> None:
        """Add current position to history and trim if needed."""
        self.centroid_history.append(self.centroid)
        self.frame_history.append(self.frame_id)
        
        # Keep only recent history
        if len(self.centroid_history) > max_history:
            self.centroid_history = self.centroid_history[-max_history:]
            self.frame_history = self.frame_history[-max_history:]


class ByteTrackTracker:
    """
    Object tracker using YOLO's built-in ByteTrack implementation.
    
    Uses ultralytics YOLO.track() which internally uses ByteTrack.
    This provides consistent tracking IDs across frames.
    """
    
    def __init__(
        self,
        model_path: str = "yolov8l.pt",
        device: str = "cuda",
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        track_thresh: float = 0.5,
        track_buffer: int = 30,
        match_thresh: float = 0.8,
        target_classes: Optional[List[str]] = None,
        history_length: int = 30
    ):
        """
        Initialize ByteTrack tracker.
        
        Args:
            model_path: Path to YOLO model weights
            device: Device for inference
            conf_threshold: Detection confidence threshold
            iou_threshold: NMS IOU threshold
            track_thresh: Tracking confidence threshold
            track_buffer: Frames to keep lost tracks
            match_thresh: Matching threshold for track association
            target_classes: List of class names to track
            history_length: Number of frames to keep in position history
        """
        self.model_path = model_path
        self.device = device
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.track_thresh = track_thresh
        self.track_buffer = track_buffer
        self.match_thresh = match_thresh
        self.history_length = history_length
        
        # Target classes
        self.target_classes = target_classes or ["car", "truck", "motorcycle", "ambulance"]
        
        # Class name normalization
        self.CLASS_MAPPING = {
            "car": "car",
            "xe_oto": "car",
            "truck": "truck",
            "xe_tai": "truck",
            "bus": "truck",
            "motorcycle": "motorcycle",
            "moto": "motorcycle",
            "xe_may": "motorcycle",
            "ambulance": "ambulance",
            "xe_cap_cuu": "ambulance"
        }
        
        # Load model
        self.model = load_model(model_path, device)
        self._class_names = self.model.names
        self._build_class_filter()
        
        # Track history storage
        self._track_histories: Dict[int, TrackedObject] = {}
        self._current_frame_id = 0
        
        logger.info(f"ByteTrackTracker initialized")
        logger.info(f"  Track buffer: {track_buffer} frames")
        logger.info(f"  History length: {history_length} frames")
    
    def _build_class_filter(self) -> None:
        """Build filter for target classes."""
        self._target_class_ids = []
        
        for class_id, class_name in self._class_names.items():
            normalized = self.CLASS_MAPPING.get(class_name.lower(), class_name.lower())
            if normalized in self.target_classes:
                self._target_class_ids.append(class_id)
    
    def track(self, frame: np.ndarray, frame_id: int) -> List[TrackedObject]:
        """
        Run tracking on a frame.
        
        Args:
            frame: Input image (BGR format)
            frame_id: Sequential frame ID for history tracking
            
        Returns:
            List of TrackedObject with assigned track IDs
        """
        self._current_frame_id = frame_id
        tracked_objects = []
        
        # Run YOLO tracking (ByteTrack is default)
        results = self.model.track(
            frame,
            persist=True,  # Maintain tracks across frames
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            tracker="bytetrack.yaml",  # Explicitly use ByteTrack
            verbose=False
        )
        
        active_track_ids = set()
        
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            
            for box in boxes:
                class_id = int(box.cls[0])
                
                # Skip non-target classes
                if self._target_class_ids and class_id not in self._target_class_ids:
                    continue
                
                # Get track ID (may be None if tracking failed)
                track_id = None
                if box.id is not None:
                    track_id = int(box.id[0])
                
                if track_id is None:
                    continue  # Skip detections without track ID
                
                active_track_ids.add(track_id)
                
                # Extract detection info
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_name = self._class_names.get(class_id, "unknown")
                normalized_name = self.CLASS_MAPPING.get(class_name.lower(), class_name.lower())
                
                centroid = ((x1 + x2) / 2, (y1 + y2) / 2)
                
                # Create or update tracked object
                if track_id in self._track_histories:
                    # Update existing track
                    tracked_obj = self._track_histories[track_id]
                    tracked_obj.bbox = (x1, y1, x2, y2)
                    tracked_obj.confidence = confidence
                    tracked_obj.centroid = centroid
                    tracked_obj.frame_id = frame_id
                    tracked_obj.update_history(self.history_length)
                else:
                    # Create new track
                    tracked_obj = TrackedObject(
                        track_id=track_id,
                        bbox=(x1, y1, x2, y2),
                        class_id=class_id,
                        class_name=normalized_name,
                        confidence=confidence,
                        centroid=centroid,
                        frame_id=frame_id,
                        centroid_history=[centroid],
                        frame_history=[frame_id]
                    )
                    self._track_histories[track_id] = tracked_obj
                
                tracked_objects.append(tracked_obj)
        
        # Clean up old tracks (not seen for track_buffer frames)
        stale_ids = []
        for track_id, obj in self._track_histories.items():
            if track_id not in active_track_ids:
                if frame_id - obj.frame_id > self.track_buffer:
                    stale_ids.append(track_id)
        
        for track_id in stale_ids:
            del self._track_histories[track_id]
        
        return tracked_objects
    
    def get_track_history(self, track_id: int) -> Optional[TrackedObject]:
        """Get history for a specific track ID."""
        return self._track_histories.get(track_id)
    
    def get_all_tracks(self) -> Dict[int, TrackedObject]:
        """Get all current track histories."""
        return self._track_histories.copy()
    
    def reset(self) -> None:
        """Reset tracker state."""
        self._track_histories.clear()
        self._current_frame_id = 0
        logger.info("Tracker reset")
