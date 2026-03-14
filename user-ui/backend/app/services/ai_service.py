# AI Detection Service - Using Custom Trained Models
# Uses 3 YOLOv8 models: vehicle detection, accident classification, traffic jam classification

import gc
import sys
import subprocess
import threading
import cv2
import numpy as np
import torch
from pathlib import Path
from typing import Callable, Dict, Any, List, Optional, Tuple

from app.core.config import (
    VIDEO_DETECTION_DIR,
    VEHICLE_DETECTION_MODEL,
    AMBULANCE_DETECTION_MODEL,
    ACCIDENT_CLASSIFICATION_MODEL,
    TRAFFIC_CLASSIFICATION_MODEL,
    PROCESSED_DIR,
)

# Add video_detection to path so pipeline sub-modules resolve correctly
if str(VIDEO_DETECTION_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_DETECTION_DIR))

from ultralytics import YOLO
from pipeline.vehicle_counter import VehicleCounter
from tracker.bytetrack_tracker import TrackedObject


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
        # Inference lock — YOLO models are not thread-safe.  Serializes all
        # calls to process_image / process_video even if something bypasses
        # the TaskManager's single-worker constraint.
        self._inference_lock = threading.Lock()

        print("Initializing AI Models...")

        # Load Vehicle Detection Model (Object Detection)
        if VEHICLE_DETECTION_MODEL.exists():
            print(f"Loading vehicle detection model: {VEHICLE_DETECTION_MODEL}")
            self.vehicle_model = YOLO(str(VEHICLE_DETECTION_MODEL))
        else:
            print(f"WARNING: Vehicle detection model not found, using default yolov8l.pt")
            self.vehicle_model = YOLO("yolov8l.pt")

        # Load Ambulance Detection Model (dedicated fine-tuned model)
        if AMBULANCE_DETECTION_MODEL.exists():
            print(f"Loading ambulance detection model: {AMBULANCE_DETECTION_MODEL}")
            self.ambulance_model = YOLO(str(AMBULANCE_DETECTION_MODEL))
        else:
            print(f"WARNING: Ambulance detection model not found at {AMBULANCE_DETECTION_MODEL}")
            self.ambulance_model = None

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

    def _get_ffmpeg_exe(self) -> str:
        """Return absolute path to an FFmpeg executable."""
        print(f"FFmpeg: server Python = {sys.executable}")

        # 1. imageio_ffmpeg bundled binary (works when installed in server env)
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if Path(exe).exists():
                print(f"FFmpeg: using imageio_ffmpeg binary at {exe}")
                return exe
        except Exception as e:
            print(f"FFmpeg: imageio_ffmpeg lookup failed: {e}")

        # 2. Search site-packages relative to the running Python (handles venvs)
        python_exe = Path(sys.executable)
        sp_roots = [
            python_exe.parent / "Lib" / "site-packages",          # conda env / venv Scripts/
            python_exe.parent.parent / "Lib" / "site-packages",   # venv root
        ]
        for sp in sp_roots:
            binaries_dir = sp / "imageio_ffmpeg" / "binaries"
            if binaries_dir.exists():
                matches = list(binaries_dir.glob("ffmpeg*.exe"))
                if matches:
                    print(f"FFmpeg: found in site-packages at {matches[0]}")
                    return str(matches[0])

        # 3. Check known fixed Anaconda/conda locations across drives
        fixed_roots = [
            r"D:\Anaconda", r"D:\Anaconda3", r"C:\Anaconda", r"C:\Anaconda3",
            r"C:\ProgramData\Anaconda3", r"C:\ProgramData\Anaconda",
        ]
        for root in fixed_roots:
            binaries_dir = Path(root) / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries"
            if binaries_dir.exists():
                matches = list(binaries_dir.glob("ffmpeg*.exe"))
                if matches:
                    print(f"FFmpeg: found in {root} at {matches[0]}")
                    return str(matches[0])

        print("FFmpeg: WARNING - no bundled ffmpeg found, falling back to system PATH")
        return 'ffmpeg'

    def _transcode_for_browser(self, video_path: Path) -> bool:
        """
        Re-encode video to H.264 + yuv420p so every browser can play it.
        Uses bundled FFmpeg from imageio-ffmpeg (no system install required).
        Returns True on success, False on failure (original kept).
        """
        temp_path = video_path.with_suffix('.tmp.mp4')
        try:
            ffmpeg_exe = self._get_ffmpeg_exe()
            subprocess.run(
                [
                    ffmpeg_exe, '-y',
                    '-i', str(video_path),
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart',
                    str(temp_path),
                ],
                check=True,
                capture_output=True,
                timeout=600,
            )
            video_path.unlink()
            temp_path.rename(video_path)
            print(f"Transcoded to browser-compatible H.264: {video_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg transcode failed (exit {e.returncode}): {e.stderr.decode(errors='replace')[-500:]}")
            if temp_path.exists():
                temp_path.unlink()
            return False
        except Exception as e:
            print(f"FFmpeg transcode failed (original kept): {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

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
            return False, 0.0, "Không xác định"

        results = self.traffic_model(frame, verbose=False)
        if results and len(results) > 0:
            probs = results[0].probs
            if probs is not None:
                # Class 0 = jam, Class 1 = no_jam
                top1_idx = probs.top1
                confidence = float(probs.top1conf)
                is_jam = top1_idx == 0  # 0 = jam class

                if is_jam:
                    status_text = "Tắc nghẽn"  # Traffic jam
                else:
                    status_text = "Thông thoáng"  # Free flow

                return is_jam, confidence, status_text
        return False, 0.0, "Không xác định"

    def _detect_vehicles(self, frame: np.ndarray) -> Tuple[np.ndarray, int, bool]:
        """
        Detect vehicles in frame using dual-model approach and draw bounding boxes.
        - vehicle_model: car, truck, motorcycle, bus (skip ambulance)
        - ambulance_model: ambulance only
        Returns: (annotated_frame, vehicle_count, ambulance_detected)
        """
        results = self.vehicle_model(frame, verbose=False, conf=0.25)

        annotated_frame = frame.copy()
        vehicle_count = 0
        ambulance_detected = False

        if results and len(results) > 0:
            boxes = results[0].boxes
            if boxes is not None:
                # Count only non-ambulance detections from general model
                for box in boxes:
                    class_name = self.vehicle_model.names[int(box.cls[0])]
                    if class_name != "ambulance":
                        vehicle_count += 1
                # Draw annotations from general model
                annotated_frame = results[0].plot()

        # Ambulance detection using dedicated fine-tuned model (threshold: 0.4)
        if self.ambulance_model is not None:
            amb_results = self.ambulance_model(frame, verbose=False, conf=0.4)
            if amb_results and len(amb_results) > 0:
                amb_boxes = amb_results[0].boxes
                if amb_boxes is not None:
                    for box in amb_boxes:
                        class_name = self.ambulance_model.names[int(box.cls[0])]
                        if class_name == "ambulance":
                            vehicle_count += 1
                            ambulance_detected = True
                            # Draw ambulance boxes on annotated frame
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
                            conf = float(box.conf[0])
                            cv2.putText(annotated_frame, f"ambulance {conf:.2f}",
                                        (x1, max(y1 - 8, 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        return annotated_frame, vehicle_count, ambulance_detected

    def process_image(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Process a single image for traffic and accident detection."""
        frame = cv2.imread(str(input_path))
        if frame is None:
            raise RuntimeError("Failed to read image")

        print(f"Processing image: {input_path}")
        if progress_callback:
            progress_callback(30, "Đang phát hiện phương tiện...")

        with self._inference_lock, torch.no_grad():
            # 1. Detect vehicles and annotate
            annotated_frame, vehicle_count, ambulance_detected = self._detect_vehicles(frame)
            if progress_callback:
                progress_callback(60, "Đang phân loại tai nạn...")

            # 2. Classify accident
            is_accident, accident_conf = self._classify_accident(frame)
            if progress_callback:
                progress_callback(80, "Đang phân loại giao thông...")

            # 3. Classify traffic jam
            is_jam, traffic_conf, traffic_status = self._classify_traffic(frame)

        # Override: when ambulance detected, hardcode clear traffic & no accident
        if ambulance_detected:
            traffic_status = "Thông thoáng"
            is_jam = False
            is_accident = False
            accident_conf = 0.0

        # Save output image (no overlay - results shown on website only)
        cv2.imwrite(str(output_path), annotated_frame)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Failed to save output image")

        if progress_callback:
            progress_callback(95, "Đang lưu kết quả...")

        print(f"Results: Traffic={traffic_status}, Accident={is_accident}, Jam={is_jam}, Ambulance={ambulance_detected}")

        return {
            "traffic_status": traffic_status,
            "is_traffic_jam": is_jam,
            "traffic_confidence": traffic_conf,
            "accident_detected": is_accident,
            "accident_confidence": accident_conf,
        }

    def process_video(
        self,
        input_path: Path,
        output_path: Path,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Process a video with ByteTrack vehicle tracking + VehicleCounter.

        Reuses the already-loaded self.vehicle_model (no duplicate YOLO load).
        Produces an annotated output video showing bounding boxes, track IDs,
        a virtual counting line, and live per-class counts.
        """
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            raise RuntimeError(f"Failed to open video: {input_path}")

        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        print(f"Input video: {width}x{height} @ {fps}fps, {total_frames} frames")

        final_output_path = output_path.with_suffix(".mp4")

        # --- Setup VideoWriter ---
        # avc1/H264/X264 require openh264 DLL which may not be available;
        # mp4v always works. FFmpeg (imageio-ffmpeg) handles H.264 transcoding.
        out = None
        for codec in ["mp4v", "XVID", "MJPG"]:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                test = cv2.VideoWriter(str(final_output_path), fourcc, fps, (width, height))
                if test.isOpened():
                    out = test
                    print(f"Using codec: {codec}")
                    break
                test.release()
            except Exception as e:
                print(f"Codec {codec} failed: {e}")

        if out is None:
            raise RuntimeError("No suitable video codec found")

        # --- Vehicle counter ---
        counter = VehicleCounter(
            frame_height=height,
            line_position=0.5,
            min_track_length=2,
            dedup_distance=40.0,
            dedup_time_window=1.5,
            fps=fps,
        )

        # Track history for building TrackedObject with centroid history
        track_histories: Dict[int, TrackedObject] = {}
        CLASS_MAP = {
            "car": "car", "xe_oto": "car",
            "truck": "truck", "xe_tai": "truck", "bus": "truck",
            "motorcycle": "motorcycle", "moto": "motorcycle", "xe_may": "motorcycle",
            "ambulance": "ambulance",
        }
        HISTORY_LEN = 30
        TRACK_BUFFER = 50       # frames before a lost track is pruned
        BBOX_COLORS = {
            "car": (0, 255, 0),
            "motorcycle": (255, 255, 0),
            "truck": (0, 165, 255),
            "ambulance": (255, 0, 0),
        }

        # Classification sample interval (~0.5 s)
        sample_interval = max(1, fps // 2)
        frame_id = 0
        accident_frames = 0
        jam_frames = 0
        ambulance_detected_in_video = False

        if progress_callback:
            progress_callback(5, "Đang khởi tạo xử lý video...")

        cap = cv2.VideoCapture(str(input_path))
        try:
          with self._inference_lock, torch.no_grad():
            # Reset ByteTrack's internal tracker state from any previous video
            self.vehicle_model.predictor = None

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # ---- ByteTrack via existing vehicle_model ----
                results = self.vehicle_model.track(
                    frame,
                    persist=True,
                    conf=0.25,
                    iou=0.55,
                    tracker="bytetrack.yaml",
                    verbose=False,
                )

                annotated = frame.copy()
                tracked_objects: List[TrackedObject] = []
                active_ids: set = set()

                boxes = results[0].boxes if results else None
                if boxes is not None:
                    for box in boxes:
                        if box.id is None:
                            continue
                        track_id = int(box.id[0])
                        class_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        raw_name = self.vehicle_model.names.get(class_id, "unknown")
                        # Skip ambulance from general model — use dedicated model
                        if raw_name.lower() == "ambulance":
                            continue
                        cls_name = CLASS_MAP.get(raw_name.lower(), raw_name.lower())
                        centroid = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                        active_ids.add(track_id)

                        # Update or create track history
                        if track_id in track_histories:
                            obj = track_histories[track_id]
                            obj.bbox = (x1, y1, x2, y2)
                            obj.confidence = conf
                            obj.centroid = centroid
                            obj.frame_id = frame_id
                            obj.centroid_history.append(centroid)
                            obj.frame_history.append(frame_id)
                            if len(obj.centroid_history) > HISTORY_LEN:
                                obj.centroid_history = obj.centroid_history[-HISTORY_LEN:]
                                obj.frame_history = obj.frame_history[-HISTORY_LEN:]
                        else:
                            obj = TrackedObject(
                                track_id=track_id,
                                bbox=(x1, y1, x2, y2),
                                class_id=class_id,
                                class_name=cls_name,
                                confidence=conf,
                                centroid=centroid,
                                frame_id=frame_id,
                                centroid_history=[centroid],
                                frame_history=[frame_id],
                            )
                            track_histories[track_id] = obj

                        tracked_objects.append(obj)

                        # Draw bounding box + label
                        color = BBOX_COLORS.get(cls_name, (0, 255, 0))
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(
                            annotated, f"{cls_name} #{track_id}",
                            (x1, max(y1 - 8, 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
                        )

                # Ambulance detection using dedicated fine-tuned model (threshold: 0.4)
                if self.ambulance_model is not None:
                    amb_results = self.ambulance_model(frame, verbose=False, conf=0.4)
                    if amb_results and len(amb_results) > 0:
                        amb_boxes = amb_results[0].boxes
                        if amb_boxes is not None:
                            for box in amb_boxes:
                                class_name = self.ambulance_model.names[int(box.cls[0])]
                                if class_name == "ambulance":
                                    ambulance_detected_in_video = True
                                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                                    conf = float(box.conf[0])
                                    # Draw ambulance box
                                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)
                                    cv2.putText(
                                        annotated, f"ambulance {conf:.2f}",
                                        (x1, max(y1 - 8, 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 0), 1,
                                    )

                # Prune stale track histories
                stale = [
                    tid for tid, obj in track_histories.items()
                    if tid not in active_ids and frame_id - obj.frame_id > TRACK_BUFFER
                ]
                for tid in stale:
                    del track_histories[tid]

                # ---- Update vehicle counter ----
                counter.update(tracked_objects, frame_id)

                # ---- Draw counting line + live counts overlay ----
                line_y = counter.line_y_coord
                cv2.line(annotated, (0, line_y), (width, line_y), (0, 255, 255), 2)
                cv2.putText(
                    annotated, "COUNT LINE", (8, line_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1,
                )
                # Use unique-track counts (all tracked vehicles, not just line-crossers)
                counts_now = counter.get_unique_counts()
                y_off = 24
                cv2.putText(
                    annotated, f"Vehicles: {counter.get_unique_total()}",
                    (8, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2,
                )
                for cls, cnt in counts_now.items():
                    y_off += 22
                    cv2.putText(
                        annotated, f"  {cls}: {cnt}",
                        (8, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1,
                    )

                # ---- Classification sampling ----
                if frame_id % sample_interval == 0:
                    is_accident, _ = self._classify_accident(frame)
                    is_jam, _, _ = self._classify_traffic(frame)
                    if is_accident:
                        accident_frames += 1
                    if is_jam:
                        jam_frames += 1

                out.write(annotated)
                frame_id += 1

                if frame_id % 100 == 0:
                    pct = (frame_id / total_frames * 100) if total_frames > 0 else 0
                    print(f"  Progress: {frame_id}/{total_frames} ({pct:.1f}%) | "
                          f"vehicles: {counts_now}")
                    if progress_callback:
                        # Map frame progress to 5-90% range
                        mapped_pct = 5 + int(pct * 0.85)
                        progress_callback(
                            min(mapped_pct, 90),
                            f"Đang xử lý frame {frame_id}/{total_frames} ({pct:.0f}%)",
                        )

        finally:
            cap.release()
            out.release()

        # Re-encode to browser-compatible H.264/yuv420p
        if progress_callback:
            progress_callback(92, "Đang chuyển đổi video cho trình duyệt...")
        print("Transcoding output video for browser compatibility...")
        self._transcode_for_browser(final_output_path)

        # ---- Final classification results ----
        total_samples = max(1, frame_id // sample_interval)
        jam_detected = jam_frames > total_samples * 0.3
        accident_detected = accident_frames > 0
        traffic_status = "Tắc nghẽn" if jam_detected else "Thông thoáng"

        # Override: when ambulance detected, hardcode clear traffic & no accident
        if ambulance_detected_in_video:
            traffic_status = "Thông thoáng"
            jam_detected = False
            accident_detected = False

        # ---- Build CountResult for JSON export ----
        count_result = counter.build_result(
            video_source=input_path.name,
            total_frames=frame_id,
            duration_seconds=round(frame_id / fps, 2),
            accidents_detected=1 if accident_detected else 0,
        )

        if not final_output_path.exists() or final_output_path.stat().st_size == 0:
            raise RuntimeError("Output video file was not created")

        # Use unique-track counts (more accurate than line-crossing only)
        unique_counts = counter.get_unique_counts()
        unique_total = counter.get_unique_total()

        # Explicit cleanup of large objects
        del track_histories
        del counter
        gc.collect()

        if progress_callback:
            progress_callback(98, "Đang hoàn tất...")

        print(f"Output: {final_output_path} "
              f"({final_output_path.stat().st_size / 1024 / 1024:.2f} MB)")
        print(f"Traffic={traffic_status}, Accident={accident_detected}, "
              f"Vehicle counts={unique_counts} (total: {unique_total})")

        return {
            "traffic_status": traffic_status,
            "is_traffic_jam": jam_detected,
            "accident_detected": accident_detected,
            "vehicle_counts": unique_counts,
            "total_vehicles": unique_total,
            "count_result": count_result,
            "output_filename": final_output_path.name,
        }


# Singleton instance
ai_service = AIService()
