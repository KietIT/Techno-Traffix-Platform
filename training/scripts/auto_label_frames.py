"""
Auto-Labeling Script using Pre-trained YOLO Model.

This script uses a pre-trained YOLO model to generate initial labels for your frames.
You should then REVIEW and CORRECT these labels using a labeling tool.

This significantly speeds up the labeling process:
1. Pre-trained model generates ~80% accurate labels
2. You only need to fix errors and add missing labels
3. Reduces labeling time by 60-80%

Usage:
    python auto_label_frames.py --frames_dir ./frames --output_dir ./auto_labels --model yolov8l.pt

Classes generated:
    0: car
    1: truck
    2: motorcycle
    3: bus
    4: ambulance
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from ultralytics import YOLO
    import cv2
    import numpy as np
except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("Install with: pip install ultralytics opencv-python")
    sys.exit(1)


# COCO class IDs to our custom class mapping
COCO_TO_CUSTOM = {
    2: 0,   # car -> car (0)
    7: 1,   # truck -> truck (1)
    3: 2,   # motorcycle -> motorcycle (2)
    5: 3,   # bus -> bus (3)
    # ambulance (4) - not in COCO, will need manual labeling
}

CUSTOM_CLASS_NAMES = {
    0: 'car',
    1: 'truck',
    2: 'motorcycle',
    3: 'bus',
    4: 'ambulance',
}


def convert_to_yolo_format(
    bbox: Tuple[float, float, float, float],
    img_width: int,
    img_height: int
) -> Tuple[float, float, float, float]:
    """
    Convert bbox from (x1, y1, x2, y2) to YOLO format (x_center, y_center, width, height).
    All values normalized to [0, 1].
    """
    x1, y1, x2, y2 = bbox

    x_center = ((x1 + x2) / 2) / img_width
    y_center = ((y1 + y2) / 2) / img_height
    width = (x2 - x1) / img_width
    height = (y2 - y1) / img_height

    # Clamp to [0, 1]
    x_center = max(0, min(1, x_center))
    y_center = max(0, min(1, y_center))
    width = max(0, min(1, width))
    height = max(0, min(1, height))

    return x_center, y_center, width, height


def auto_label_image(
    model: YOLO,
    image_path: str,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
) -> Tuple[List[str], Dict]:
    """
    Generate YOLO format labels for a single image.

    Returns:
        Tuple of (label_lines, stats)
    """
    # Load image to get dimensions
    img = cv2.imread(image_path)
    if img is None:
        return [], {"error": f"Cannot read image: {image_path}"}

    img_height, img_width = img.shape[:2]

    # Run inference
    results = model(image_path, conf=confidence_threshold, iou=iou_threshold, verbose=False)

    label_lines = []
    stats = {
        "total_detections": 0,
        "car": 0,
        "truck": 0,
        "motorcycle": 0,
        "bus": 0,
        "ambulance": 0,
        "skipped": 0,
    }

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        for box in boxes:
            coco_class_id = int(box.cls[0])

            # Map COCO class to our custom class
            if coco_class_id not in COCO_TO_CUSTOM:
                stats["skipped"] += 1
                continue

            custom_class_id = COCO_TO_CUSTOM[coco_class_id]
            class_name = CUSTOM_CLASS_NAMES[custom_class_id]

            # Get bounding box
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0])

            # Convert to YOLO format
            x_center, y_center, width, height = convert_to_yolo_format(
                (x1, y1, x2, y2), img_width, img_height
            )

            # Create label line
            label_line = f"{custom_class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
            label_lines.append(label_line)

            stats["total_detections"] += 1
            stats[class_name] += 1

    return label_lines, stats


def process_directory(
    model: YOLO,
    frames_dir: str,
    output_dir: str,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    save_visualizations: bool = False,
    viz_dir: str = None,
) -> Dict:
    """
    Process all images in a directory and generate labels.
    """
    frames_path = Path(frames_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if save_visualizations:
        viz_path = Path(viz_dir) if viz_dir else output_path / 'visualizations'
        viz_path.mkdir(parents=True, exist_ok=True)

    # Find all images
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    image_files = []
    for ext in image_extensions:
        image_files.extend(frames_path.glob(f'*{ext}'))
        image_files.extend(frames_path.glob(f'*{ext.upper()}'))

    image_files = sorted(set(image_files))

    print(f"Found {len(image_files)} images to process")

    total_stats = {
        "total_images": len(image_files),
        "images_with_detections": 0,
        "total_detections": 0,
        "car": 0,
        "truck": 0,
        "motorcycle": 0,
        "bus": 0,
        "ambulance": 0,
        "errors": 0,
    }

    for i, image_path in enumerate(image_files):
        if (i + 1) % 50 == 0:
            print(f"Processing {i + 1}/{len(image_files)}...")

        # Generate labels
        label_lines, stats = auto_label_image(
            model, str(image_path), confidence_threshold, iou_threshold
        )

        if "error" in stats:
            total_stats["errors"] += 1
            continue

        # Save label file
        label_filename = image_path.stem + '.txt'
        label_path = output_path / label_filename

        with open(label_path, 'w') as f:
            f.write('\n'.join(label_lines))

        # Update total stats
        if stats["total_detections"] > 0:
            total_stats["images_with_detections"] += 1

        for key in ["total_detections", "car", "truck", "motorcycle", "bus", "ambulance"]:
            total_stats[key] += stats[key]

        # Save visualization if requested
        if save_visualizations and label_lines:
            results = model(str(image_path), conf=confidence_threshold, verbose=False)
            annotated = results[0].plot()
            viz_save_path = viz_path / f"viz_{image_path.name}"
            cv2.imwrite(str(viz_save_path), annotated)

    return total_stats


def main():
    parser = argparse.ArgumentParser(description="Auto-label frames using pre-trained YOLO")
    parser.add_argument("--frames_dir", type=str, required=True,
                        help="Directory containing extracted frames")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Output directory for label files")
    parser.add_argument("--model", type=str, default="yolov8l.pt",
                        help="YOLO model path (default: yolov8l.pt)")
    parser.add_argument("--confidence", type=float, default=0.25,
                        help="Confidence threshold (default: 0.25)")
    parser.add_argument("--iou", type=float, default=0.45,
                        help="IOU threshold for NMS (default: 0.45)")
    parser.add_argument("--visualize", action="store_true",
                        help="Save visualizations of detections")
    parser.add_argument("--viz_dir", type=str, default=None,
                        help="Directory for visualizations")

    args = parser.parse_args()

    print("="*60)
    print("AUTO-LABELING SCRIPT FOR VIETNAM TRAFFIC DATASET")
    print("="*60)
    print(f"\nFrames directory: {args.frames_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Model: {args.model}")
    print(f"Confidence threshold: {args.confidence}")
    print(f"IOU threshold: {args.iou}")

    # Load model
    print(f"\nLoading model...")
    model = YOLO(args.model)
    print(f"Model loaded successfully")

    # Process images
    print(f"\nProcessing images...")
    stats = process_directory(
        model,
        args.frames_dir,
        args.output_dir,
        confidence_threshold=args.confidence,
        iou_threshold=args.iou,
        save_visualizations=args.visualize,
        viz_dir=args.viz_dir,
    )

    # Print summary
    print("\n" + "="*60)
    print("AUTO-LABELING COMPLETE")
    print("="*60)
    print(f"\nStatistics:")
    print(f"  Total images processed: {stats['total_images']}")
    print(f"  Images with detections: {stats['images_with_detections']}")
    print(f"  Total detections: {stats['total_detections']}")
    print(f"\nDetections by class:")
    print(f"  car:        {stats['car']}")
    print(f"  truck:      {stats['truck']}")
    print(f"  motorcycle: {stats['motorcycle']}")
    print(f"  bus:        {stats['bus']}")
    print(f"  ambulance:  {stats['ambulance']} (requires manual labeling)")

    if stats['errors'] > 0:
        print(f"\nErrors: {stats['errors']}")

    print(f"\nLabels saved to: {args.output_dir}")
    print(f"\n*** IMPORTANT ***")
    print(f"These labels are AUTO-GENERATED and need MANUAL REVIEW!")
    print(f"Please use a labeling tool (CVAT, Roboflow, Label Studio) to:")
    print(f"  1. Review and correct bounding boxes")
    print(f"  2. Add missing detections (especially ambulances)")
    print(f"  3. Remove false positives")

    # Save stats
    stats_path = Path(args.output_dir) / 'auto_label_stats.json'
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\nStats saved to: {stats_path}")


if __name__ == "__main__":
    main()
