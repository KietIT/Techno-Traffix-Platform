# AI Detection Service - Using Custom Trained Models
# Uses 3 YOLOv8 models: vehicle detection, accident classification, traffic jam classification

import sys
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.core.config import (
    VIDEO_DETECTION_DIR,
    VEHICLE_DETECTION_MODEL,
    ACCIDENT_CLASSIFICATION_MODEL,
    TRAFFIC_CLASSIFICATION_MODEL,
    PROCESSED_DIR,
)

# Add video_detection to path
if str(VIDEO_DETECTION_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_DETECTION_DIR))

from ultralytics import YOLO


class AIService:
    """Service using custom trained YOLOv8 models for traffic analysis."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_models()
        return cls._instance

    def _initialize_models(self):
        """Initialize all three trained models."""
        print("Initializing AI Models...")

        # Load Vehicle Detection Model (Object Detection)
        if VEHICLE_DETECTION_MODEL.exists():
            print(f"Loading vehicle detection model: {VEHICLE_DETECTION_MODEL}")
            self.vehicle_model = YOLO(str(VEHICLE_DETECTION_MODEL))
        else:
            print(f"WARNING: Vehicle detection model not found, using default yolov8l.pt")
            self.vehicle_model = YOLO("yolov8l.pt")

        # Load Accident Classification Model
        if ACCIDENT_CLASSIFICATION_MODEL.exists():
            print(f"Loading accident classification model: {ACCIDENT_CLASSIFICATION_MODEL}")
            self.accident_model = YOLO(str(ACCIDENT_CLASSIFICATION_MODEL))
        else:
            print(f"WARNING: Accident classification model not found at {ACCIDENT_CLASSIFICATION_MODEL}")
            self.accident_model = None

        # Load Traffic Jam Classification Model
        if TRAFFIC_CLASSIFICATION_MODEL.exists():
            print(f"Loading traffic classification model: {TRAFFIC_CLASSIFICATION_MODEL}")
            self.traffic_model = YOLO(str(TRAFFIC_CLASSIFICATION_MODEL))
        else:
            print(f"WARNING: Traffic classification model not found at {TRAFFIC_CLASSIFICATION_MODEL}")
            self.traffic_model = None

        print("AI Models initialized successfully!")

    def _classify_accident(self, frame: np.ndarray) -> Tuple[bool, float]:
        """
        Classify if frame contains an accident.
        Returns: (is_accident, confidence)
        """
        if self.accident_model is None:
            return False, 0.0

        results = self.accident_model(frame, verbose=False)
        if results and len(results) > 0:
            probs = results[0].probs
            if probs is not None:
                # Class 0 = accident, Class 1 = no_accident
                top1_idx = probs.top1
                confidence = float(probs.top1conf)
                is_accident = top1_idx == 0  # 0 = accident class
                return is_accident, confidence
        return False, 0.0

    def _classify_traffic(self, frame: np.ndarray) -> Tuple[bool, float, str]:
        """
        Classify if frame shows traffic jam.
        Returns: (is_jam, confidence, status_text)
        """
        if self.traffic_model is None:
            return False, 0.0, "Khong xac dinh"

        results = self.traffic_model(frame, verbose=False)
        if results and len(results) > 0:
            probs = results[0].probs
            if probs is not None:
                # Class 0 = jam, Class 1 = no_jam
                top1_idx = probs.top1
                confidence = float(probs.top1conf)
                is_jam = top1_idx == 0  # 0 = jam class

                if is_jam:
                    status_text = "Tac nghen"  # Traffic jam
                else:
                    status_text = "Thong thoang"  # Free flow

                return is_jam, confidence, status_text
        return False, 0.0, "Khong xac dinh"

    def _detect_vehicles(self, frame: np.ndarray) -> Tuple[np.ndarray, int]:
        """
        Detect vehicles in frame and draw bounding boxes.
        Returns: (annotated_frame, vehicle_count)
        """
        results = self.vehicle_model(frame, verbose=False, conf=0.25)

        annotated_frame = frame.copy()
        vehicle_count = 0

        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None:
                vehicle_count = len(boxes)
                # Draw annotations
                annotated_frame = results[0].plot()

        return annotated_frame, vehicle_count

    def process_image(self, input_path: Path, output_path: Path) -> Dict[str, Any]:
        """Process a single image for traffic and accident detection."""
        frame = cv2.imread(str(input_path))
        if frame is None:
            raise RuntimeError("Failed to read image")

        print(f"Processing image: {input_path}")

        # 1. Detect vehicles and annotate
        annotated_frame, vehicle_count = self._detect_vehicles(frame)

        # 2. Classify accident
        is_accident, accident_conf = self._classify_accident(frame)

        # 3. Classify traffic jam
        is_jam, traffic_conf, traffic_status = self._classify_traffic(frame)

        # Save output image (no overlay - results shown on website only)
        cv2.imwrite(str(output_path), annotated_frame)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Failed to save output image")

        print(f"Results: Traffic={traffic_status}, Accident={is_accident}, Jam={is_jam}")

        return {
            "traffic_status": traffic_status,
            "is_traffic_jam": is_jam,
            "traffic_confidence": traffic_conf,
            "accident_detected": is_accident,
            "accident_confidence": accident_conf,
        }

    def process_video(self, input_path: Path, output_path: Path) -> Dict[str, Any]:
        """Process a video for traffic and accident detection."""
        cap = cv2.VideoCapture(str(input_path))

        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {input_path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"Input video: {width}x{height} @ {fps}fps, {total_frames} frames")

        # Output path with .mp4 extension
        final_output_path = output_path.with_suffix(".mp4")

        # Try codecs
        codecs_to_try = [
            ("avc1", "H.264"),
            ("mp4v", "MPEG-4"),
            ("XVID", "Xvid"),
            ("MJPG", "Motion JPEG"),
        ]

        out = None
        for codec, desc in codecs_to_try:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                test_out = cv2.VideoWriter(str(final_output_path), fourcc, fps, (width, height))
                if test_out.isOpened():
                    out = test_out
                    print(f"Using codec: {codec}")
                    break
                test_out.release()
            except Exception as e:
                print(f"Codec {codec} failed: {e}")

        if out is None:
            cap.release()
            raise RuntimeError("No suitable video codec found")

        # Processing variables
        frame_count = 0
        accident_frames = 0
        jam_frames = 0
        sample_interval = max(1, fps // 2)  # Sample classification every 0.5 seconds

        # For final decision
        accident_detected_overall = False
        jam_detected_overall = False
        traffic_status_final = "Thong thoang"

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # Detect vehicles and annotate every frame
                annotated_frame, _ = self._detect_vehicles(frame)

                # Run classification at sample intervals (to save processing time)
                if frame_count % sample_interval == 0:
                    is_accident, _ = self._classify_accident(frame)
                    is_jam, _, status = self._classify_traffic(frame)

                    if is_accident:
                        accident_frames += 1
                    if is_jam:
                        jam_frames += 1

                # Write frame (no overlay - results shown on website only)
                out.write(annotated_frame)

                if frame_count % 100 == 0:
                    progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                    print(f"Progress: {frame_count}/{total_frames} ({progress:.1f}%)")

        finally:
            cap.release()
            out.release()

        # Determine final results
        total_samples = frame_count // sample_interval if sample_interval > 0 else 1

        # If more than 30% of sampled frames show jam, consider it jammed
        jam_detected_overall = jam_frames > total_samples * 0.3
        # If any frame shows accident, flag it
        accident_detected_overall = accident_frames > 0

        traffic_status_final = "Tac nghen" if jam_detected_overall else "Thong thoang"

        # Validate output
        if not final_output_path.exists() or final_output_path.stat().st_size == 0:
            raise RuntimeError("Output video file was not created")

        file_size = final_output_path.stat().st_size
        print(f"Output video: {final_output_path} ({file_size / 1024 / 1024:.2f} MB)")

        print(f"Results: Traffic={traffic_status_final}, Accident={accident_detected_overall}, "
              f"Jam frames={jam_frames}/{total_samples}, Accident frames={accident_frames}")

        return {
            "traffic_status": traffic_status_final,
            "is_traffic_jam": jam_detected_overall,
            "accident_detected": accident_detected_overall,
            "output_filename": final_output_path.name,
        }


# Singleton instance
ai_service = AIService()
