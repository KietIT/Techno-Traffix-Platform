"""
Intersection Demo — two modes:

  --img   : process four traffic camera images (east/west/south/north)
             and produce one JSON result file per direction.
  --video : process a video file with YOLO detection + ByteTrack tracking,
             draw bounding boxes, and save the annotated video.

Usage:
    python demo.py --img <east> <west> <south> <north> [options]
    python demo.py --video <video_path> [options]

Examples:
    python demo.py --img imgs/e.jpg imgs/w.jpg imgs/s.jpg imgs/n.jpg -o results/
    python demo.py --video videos/traffic.mp4 -o results/
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

_VD_DIR = Path(__file__).parent / "video_detection"

# Add video_detection to path so pipeline sub-modules resolve correctly
if str(_VD_DIR) not in sys.path:
    sys.path.insert(0, str(_VD_DIR))

# Pre-trained models already in the repo — no download needed
_VEHICLE_MODEL = str(_VD_DIR / "vehicle_detection_yolov8l.pt")
_AMBULANCE_MODEL = str(_VD_DIR / "vehicle_detection_yolov8l_ambulance.pt")
_DEFAULT_ACCIDENT_MODEL = str(_VD_DIR / "accident_classification_yolov8l.pt")

DIRECTIONS = ["east", "west", "south", "north"]

CLASS_MAP = {
    "car": "car", "xe_oto": "car",
    "truck": "truck", "xe_tai": "truck", "bus": "truck",
    "motorcycle": "motorcycle", "moto": "motorcycle", "xe_may": "motorcycle",
    "ambulance": "ambulance",
}

BBOX_COLORS = {
    "car": (0, 255, 0),
    "motorcycle": (255, 255, 0),
    "truck": (0, 165, 255),
    "ambulance": (255, 0, 0),
}

HISTORY_LEN = 30
TRACK_BUFFER = 50  # frames before a lost track is pruned


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config(config_path: Optional[str]) -> dict:
    """Load YAML config and return the model section, or empty dict."""
    if not config_path:
        return {}
    import yaml
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_accident_model() -> YOLO:
    """Load the accident classification model from the repo."""
    return YOLO(_DEFAULT_ACCIDENT_MODEL)


def classify_accident(model: YOLO, frame) -> tuple[bool, float]:
    """
    Run the binary accident classifier on a single frame.

    Returns:
        (has_accident, confidence)  — class 0 = accident, class 1 = no_accident
    """
    results = model(frame, verbose=False)
    if results and results[0].probs is not None:
        probs = results[0].probs
        is_accident = probs.top1 == 0
        confidence = round(float(probs.top1conf), 4)
        return is_accident, confidence
    return False, 0.0


# ---------------------------------------------------------------------------
# Image mode
# ---------------------------------------------------------------------------

def process_image(
    vehicle_model: YOLO,
    ambulance_model: YOLO,
    accident_model: YOLO,
    image_path: str,
    direction: str,
) -> dict:
    """
    Detect vehicles and classify accidents in a single image.

    Uses two models:
      - vehicle_model:   detects car, truck, motorcycle, bus
      - ambulance_model: detects ambulance

    Args:
        vehicle_model:   Loaded YOLO model for general vehicles.
        ambulance_model: Loaded YOLO model fine-tuned for ambulances.
        accident_model:  Loaded YOLO accident classifier.
        image_path:      Path to the input image.
        direction:       One of east / west / south / north.

    Returns:
        Result dict ready for JSON serialisation.
    """
    logger = logging.getLogger(__name__)

    frame = cv2.imread(image_path)
    if frame is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    vehicle_counts: Dict[str, int] = {}

    #=====================================Vehicle counting=====================================
    # General vehicle detection (car, truck, motorcycle, bus)
    veh_results = vehicle_model(frame, conf=0.25, verbose=False)
    if veh_results and veh_results[0].boxes is not None:
        for box in veh_results[0].boxes:
            class_name = vehicle_model.names[int(box.cls[0])]
            if class_name == "ambulance":
                continue  # skip ambulance from this model — use dedicated model instead
            vehicle_counts[class_name] = vehicle_counts.get(class_name, 0) + 1

    # Ambulance detection (dedicated fine-tuned model)
    amb_results = ambulance_model(frame, conf=0.25, verbose=False)
    if amb_results and amb_results[0].boxes is not None:
        for box in amb_results[0].boxes:
            class_name = ambulance_model.names[int(box.cls[0])]
            if class_name == "ambulance":
                vehicle_counts["ambulance"] = vehicle_counts.get("ambulance", 0) + 1
    #==========================================================================================

    total_vehicles = sum(vehicle_counts.values())

    # Ambulance detection
    has_ambulance: bool = "ambulance" in vehicle_counts

    # Accident classification — suppressed when an ambulance is present
    has_accident, accident_confidence = classify_accident(accident_model, frame)

    if has_ambulance:
        has_accident = False
        accident_confidence = 0.0

    logger.info(
        f"[{direction.upper():5s}] {image_path} -> {total_vehicles} vehicles "
        f"{vehicle_counts} | has_accident={has_accident} ({accident_confidence:.2%}) "
        f"| has_ambulance={has_ambulance}"
    )

    return {
        "direction": direction,
        "image_source": image_path,
        "processed_at": datetime.now().isoformat(),
        "total_vehicles": total_vehicles,
        "vehicle_counts": vehicle_counts,
        "has_ambulance": has_ambulance,
        "has_accident": has_accident,
        "accident_confidence": accident_confidence,
    }


def run_image_mode(args, vehicle_model: YOLO, ambulance_model: YOLO, accident_model: YOLO) -> None:
    """Run image analysis mode on four intersection images."""
    logger = logging.getLogger(__name__)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for direction, image_path in zip(DIRECTIONS, args.images):
        try:
            result = process_image(vehicle_model, ambulance_model, accident_model, image_path, direction)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            sys.exit(1)
        results[direction] = result

    # Write combined summary
    summary = {
        "processed_at": datetime.now().isoformat(),
        "directions": results,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved summary: {summary_path}")
    logger.info("Done. All files written to: %s", output_dir.resolve())


# ---------------------------------------------------------------------------
# Video mode
# ---------------------------------------------------------------------------

def process_video(
    vehicle_model: YOLO,
    ambulance_model: YOLO,
    accident_model: YOLO,
    video_path: str,
    output_dir: Path,
) -> dict:
    """
    Process a video with ByteTrack vehicle tracking.

    Draws bounding boxes with track IDs, a counting line, and live per-class
    counts on every frame. Saves the annotated video to output_dir.

    Returns:
        Result dict with vehicle counts and output file path.
    """
    from pipeline.vehicle_counter import VehicleCounter
    from tracker.bytetrack_tracker import TrackedObject

    logger = logging.getLogger(__name__)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open video: {video_path}")

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"Input video: {width}x{height} @ {fps}fps, {total_frames} frames")

    # Output path
    output_dir.mkdir(parents=True, exist_ok=True)
    video_name = Path(video_path).stem
    output_path = output_dir / f"{video_name}_detected.mp4"

    # Setup VideoWriter
    out = None
    for codec in ["mp4v", "XVID", "MJPG"]:
        try:
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            if test.isOpened():
                out = test
                logger.info(f"Using codec: {codec}")
                break
            test.release()
        except Exception as e:
            logger.warning(f"Codec {codec} failed: {e}")

    if out is None:
        cap.release()
        raise RuntimeError("No suitable video codec found")

    # Vehicle counter
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

    # Classification sample interval (~0.5 s)
    sample_interval = max(1, fps // 2)
    frame_id = 0
    accident_frames = 0
    ambulance_detected_in_video = False

    # Reset ByteTrack's internal tracker state from any previous run
    vehicle_model.predictor = None

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # ---- ByteTrack via vehicle_model ----
            results = vehicle_model.track(
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
                    raw_name = vehicle_model.names.get(class_id, "unknown")
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

            # Ambulance detection using dedicated fine-tuned model
            amb_results = ambulance_model(frame, verbose=False, conf=0.4)
            if amb_results and amb_results[0].boxes is not None:
                for box in amb_results[0].boxes:
                    class_name = ambulance_model.names[int(box.cls[0])]
                    if class_name == "ambulance":
                        ambulance_detected_in_video = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0])
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

            # ---- Draw live counts overlay (top-right corner) ----
            counts_now = counter.get_unique_counts()
            x_off = width - 200
            y_off = 24
            cv2.putText(
                annotated, f"Vehicles: {counter.get_unique_total()}",
                (x_off, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2,
            )
            for cls, cnt in counts_now.items():
                y_off += 22
                cv2.putText(
                    annotated, f"  {cls}: {cnt}",
                    (x_off, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 1,
                )

            # ---- Classification sampling ----
            if frame_id % sample_interval == 0:
                is_accident, _ = classify_accident(accident_model, frame)
                if is_accident:
                    accident_frames += 1

            out.write(annotated)
            frame_id += 1

            if frame_id % 100 == 0:
                pct = (frame_id / total_frames * 100) if total_frames > 0 else 0
                logger.info(
                    f"Progress: {frame_id}/{total_frames} ({pct:.1f}%) | "
                    f"vehicles: {counts_now}"
                )

    finally:
        cap.release()
        out.release()

    # ---- Final results ----
    total_samples = max(1, frame_id // sample_interval)
    accident_detected = accident_frames > 0

    if ambulance_detected_in_video:
        accident_detected = False

    unique_counts = counter.get_unique_counts()
    unique_total = counter.get_unique_total()

    logger.info(f"Output: {output_path} ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")
    logger.info(
        f"Accident={accident_detected}, Ambulance={ambulance_detected_in_video}, "
        f"Vehicle counts={unique_counts} (total: {unique_total})"
    )

    result = {
        "video_source": video_path,
        "output_video": str(output_path),
        "processed_at": datetime.now().isoformat(),
        "total_frames": frame_id,
        "fps": fps,
        "duration_seconds": round(frame_id / fps, 2),
        "total_vehicles": unique_total,
        "vehicle_counts": unique_counts,
        "has_ambulance": ambulance_detected_in_video,
        "has_accident": accident_detected,
    }

    # Save result JSON alongside the video
    json_path = output_dir / f"{video_name}_result.json"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved result: {json_path}")

    return result


def run_video_mode(args, vehicle_model: YOLO, ambulance_model: YOLO, accident_model: YOLO) -> None:
    """Run video analysis mode."""
    logger = logging.getLogger(__name__)
    output_dir = Path(args.output_dir)

    process_video(vehicle_model, ambulance_model, accident_model, args.video, output_dir)
    logger.info("Done. Output written to: %s", output_dir.resolve())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Traffic analysis demo — image or video mode."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--img",
        nargs=4,
        dest="images",
        metavar=("EAST", "WEST", "SOUTH", "NORTH"),
        help="Image mode: paths to the four images in east/west/south/north order",
    )
    mode.add_argument(
        "--video",
        type=str,
        metavar="VIDEO",
        help="Video mode: path to a video file",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="results",
        metavar="DIR",
        help="Directory to write output files (default: results/)",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to YAML config file (default: built-in defaults)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Load models once, reuse across processing
    logger.info("Loading vehicle detection model...")
    vehicle_model = YOLO(_VEHICLE_MODEL)
    logger.info(f"Vehicle model classes: {vehicle_model.names}")
    logger.info("Loading ambulance detection model...")
    ambulance_model = YOLO(_AMBULANCE_MODEL)
    logger.info("Loading accident classification model...")
    accident_model = load_accident_model()

    if args.images:
        run_image_mode(args, vehicle_model, ambulance_model, accident_model)
    else:
        run_video_mode(args, vehicle_model, ambulance_model, accident_model)


if __name__ == "__main__":
    main()
