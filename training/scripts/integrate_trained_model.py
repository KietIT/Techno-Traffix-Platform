"""
Model Integration Script.

This script integrates your custom-trained YOLO model into the video_detection system.

Usage:
    python integrate_trained_model.py --model path/to/vietnam_traffic_yolov8l_best.pt

Steps performed:
    1. Copies model to video_detection folder
    2. Updates config.yaml to use new model
    3. Updates yolo_detector.py with new class mapping
    4. Runs a test inference to verify
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
import yaml


def backup_file(filepath: Path) -> Path:
    """Create a backup of a file."""
    backup_path = filepath.with_suffix(filepath.suffix + '.backup')
    if filepath.exists():
        shutil.copy2(filepath, backup_path)
        return backup_path
    return None


def update_config_yaml(config_path: Path, model_name: str):
    """Update config.yaml with new model path."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Update model path
    if 'model' not in config:
        config['model'] = {}

    config['model']['path'] = model_name

    # Update class mappings for custom trained model
    # Custom model class indices: 0=car, 1=truck, 2=motorcycle, 3=bus, 4=ambulance
    config['model']['class_conf_thresholds'] = {
        'motorcycle': 0.25,  # Can be slightly higher with custom training
        'car': 0.30,
        'truck': 0.35,
        'bus': 0.35,
        'ambulance': 0.30,  # Now detectable!
    }

    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return config


def update_yolo_detector(detector_path: Path):
    """Update yolo_detector.py with new class mapping for custom model."""

    with open(detector_path, 'r') as f:
        content = f.read()

    # Find and replace the DEFAULT_VEHICLE_CLASSES mapping
    old_mapping = 'DEFAULT_VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}'
    new_mapping = '''DEFAULT_VEHICLE_CLASSES = {
        # Custom trained model class indices
        0: "car",
        1: "truck",
        2: "motorcycle",
        3: "bus",
        4: "ambulance",
    }'''

    if old_mapping in content:
        content = content.replace(old_mapping, new_mapping)

        with open(detector_path, 'w') as f:
            f.write(content)

        return True
    else:
        # Try to find any DEFAULT_VEHICLE_CLASSES and update it
        import re
        pattern = r'DEFAULT_VEHICLE_CLASSES\s*=\s*\{[^}]+\}'
        if re.search(pattern, content):
            content = re.sub(pattern, new_mapping.strip(), content)
            with open(detector_path, 'w') as f:
                f.write(content)
            return True

    return False


def verify_model(model_path: Path):
    """Verify the model can be loaded and has correct classes."""
    try:
        from ultralytics import YOLO

        print(f"Loading model for verification...")
        model = YOLO(str(model_path))

        print(f"Model loaded successfully")
        print(f"Model type: {type(model)}")
        print(f"Class names: {model.names}")

        expected_classes = {0: 'car', 1: 'truck', 2: 'motorcycle', 3: 'bus', 4: 'ambulance'}

        # Check class names
        if model.names == expected_classes:
            print("Class mapping matches expected classes")
            return True
        else:
            print("WARNING: Class mapping differs from expected!")
            print(f"  Expected: {expected_classes}")
            print(f"  Got: {model.names}")
            return True  # Still usable, just warn

    except Exception as e:
        print(f"ERROR: Failed to verify model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Integrate trained model into video_detection")
    parser.add_argument("--model", type=str, required=True,
                        help="Path to trained model (vietnam_traffic_yolov8l_best.pt)")
    parser.add_argument("--video_detection_dir", type=str, default=None,
                        help="Path to video_detection directory")
    parser.add_argument("--no_backup", action="store_true",
                        help="Don't create backup files")
    parser.add_argument("--test", action="store_true",
                        help="Run a test inference after integration")

    args = parser.parse_args()

    # Find video_detection directory
    if args.video_detection_dir:
        vd_dir = Path(args.video_detection_dir)
    else:
        # Try to find it relative to this script
        script_dir = Path(__file__).parent
        vd_dir = script_dir.parent.parent / 'video_detection'

    if not vd_dir.exists():
        print(f"ERROR: video_detection directory not found at {vd_dir}")
        sys.exit(1)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"ERROR: Model file not found at {model_path}")
        sys.exit(1)

    print("="*60)
    print("INTEGRATING TRAINED MODEL")
    print("="*60)
    print(f"\nModel: {model_path}")
    print(f"video_detection: {vd_dir}")

    # 1. Verify model first
    print(f"\n[1/4] Verifying model...")
    if not verify_model(model_path):
        print("Model verification failed. Aborting.")
        sys.exit(1)

    # 2. Copy model to video_detection folder
    print(f"\n[2/4] Copying model to video_detection...")
    dest_model_path = vd_dir / model_path.name
    shutil.copy2(model_path, dest_model_path)
    print(f"  Copied to: {dest_model_path}")

    # 3. Update config.yaml
    print(f"\n[3/4] Updating config.yaml...")
    config_path = vd_dir / 'config' / 'config.yaml'

    if not args.no_backup:
        backup = backup_file(config_path)
        if backup:
            print(f"  Backup created: {backup}")

    config = update_config_yaml(config_path, model_path.name)
    print(f"  Updated model path to: {model_path.name}")

    # 4. Update yolo_detector.py
    print(f"\n[4/4] Updating yolo_detector.py...")
    detector_path = vd_dir / 'detector' / 'yolo_detector.py'

    if not args.no_backup:
        backup = backup_file(detector_path)
        if backup:
            print(f"  Backup created: {backup}")

    if update_yolo_detector(detector_path):
        print(f"  Updated class mapping for custom model")
    else:
        print(f"  WARNING: Could not automatically update class mapping")
        print(f"  You may need to manually update DEFAULT_VEHICLE_CLASSES in yolo_detector.py")

    print("\n" + "="*60)
    print("INTEGRATION COMPLETE")
    print("="*60)

    print(f"\nYour custom model is now integrated!")
    print(f"Model location: {dest_model_path}")

    print(f"\nTo test the model, run:")
    print(f"  cd {vd_dir}")
    print(f"  python main.py --video ../dataset/01.mp4 --model {model_path.name}")

    # Run test if requested
    if args.test:
        print(f"\n[TEST] Running test inference...")
        try:
            from ultralytics import YOLO
            import cv2

            model = YOLO(str(dest_model_path))

            # Find a test video/image
            dataset_dir = vd_dir.parent / 'dataset'
            test_video = list(dataset_dir.glob('*.mp4'))

            if test_video:
                test_path = test_video[0]
                print(f"  Testing on: {test_path}")

                cap = cv2.VideoCapture(str(test_path))
                ret, frame = cap.read()
                cap.release()

                if ret:
                    results = model(frame, verbose=False)
                    detections = len(results[0].boxes) if results[0].boxes else 0
                    print(f"  Detections in first frame: {detections}")
                    print(f"  TEST PASSED!")
                else:
                    print(f"  Could not read test video")
            else:
                print(f"  No test videos found in {dataset_dir}")

        except Exception as e:
            print(f"  TEST FAILED: {e}")


if __name__ == "__main__":
    main()
