"""
Intersection Demo — process four traffic camera images (east/west/south/north)
and produce one JSON result file per direction.

Usage:
    python demo.py <east_img> <west_img> <south_img> <north_img> [options]

Example:
    python demo.py imgs/e.jpg imgs/w.jpg imgs/s.jpg imgs/n.jpg --output-dir results/
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import cv2

# Make video_detection importable from the project root.
# This mirrors how video_detection/main.py sets up its own path.
_VD_DIR = Path(__file__).parent / "video_detection"
sys.path.insert(0, str(_VD_DIR))

from ultralytics import YOLO  # noqa: E402
from detector.yolo_detector import YOLODetector  # noqa: E402

# Pre-trained models already in the repo — no download needed
_DEFAULT_MODEL = str(_VD_DIR / "vehicle_detection_yolov8l.pt")
_DEFAULT_ACCIDENT_MODEL = str(_VD_DIR / "accident_classification_yolov8l.pt")

DIRECTIONS = ["east", "west", "south", "north"]


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


def build_detector(cfg: dict) -> YOLODetector:
    """Build a YOLODetector from a parsed YAML config dict."""
    model_cfg = cfg.get("model", {})
    return YOLODetector(
        model_path=model_cfg.get("path", _DEFAULT_MODEL),
        device=model_cfg.get("device", "cpu"),
        conf_threshold=model_cfg.get("conf_threshold", 0.25),
        iou_threshold=model_cfg.get("iou_threshold", 0.55),
        class_conf_thresholds=model_cfg.get("class_conf_thresholds", None),
        min_box_area=model_cfg.get("min_box_area", 400),
        max_box_area=model_cfg.get("max_box_area", 500000),
        min_aspect_ratio=model_cfg.get("min_aspect_ratio", 0.3),
        max_aspect_ratio=model_cfg.get("max_aspect_ratio", 4.0),
    )


def process_image(
    detector: YOLODetector,
    accident_model: YOLO,
    image_path: str,
    direction: str,
) -> dict:
    """
    Detect vehicles and classify accidents in a single image.

    Args:
        detector:        Initialised YOLODetector (vehicle detection).
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

    # Vehicle detection
    detections = detector.detect(frame)
    vehicle_counts: Dict[str, int] = {}
    for det in detections:
        vehicle_counts[det.class_name] = vehicle_counts.get(det.class_name, 0) + 1
    total_vehicles = sum(vehicle_counts.values())

    # Ambulance: model not yet trained for this class — always False
    has_ambulance: bool = False

    # Accident classification
    has_accident, accident_confidence = classify_accident(accident_model, frame)

    logger.info(
        f"[{direction.upper():5s}] {image_path} → {total_vehicles} vehicles "
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process four intersection images and output per-direction JSON files."
    )
    parser.add_argument(
        "images",
        nargs=4,
        metavar=("EAST", "WEST", "SOUTH", "NORTH"),
        help="Paths to the four images in east → west → south → north order",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=".",
        metavar="DIR",
        help="Directory to write output JSON files (default: current directory)",
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

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load models once, reuse for all four images
    cfg = load_config(args.config)
    logger.info("Loading vehicle detection model...")
    detector = build_detector(cfg)
    logger.info("Loading accident classification model...")
    accident_model = load_accident_model()

    # Process each direction
    results = {}
    for direction, image_path in zip(DIRECTIONS, args.images):
        try:
            result = process_image(detector, accident_model, image_path, direction)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            sys.exit(1)

        results[direction] = result

    # Write combined summary (east → west → south → north order preserved)
    summary = {
        "processed_at": datetime.now().isoformat(),
        "directions": results,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved summary: {summary_path}")

    logger.info("Done. All files written to: %s", output_dir.resolve())


if __name__ == "__main__":
    main()
