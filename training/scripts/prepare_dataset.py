"""
Dataset Preparation Script for YOLO Training.

This script organizes labeled data into the YOLO training format:
    dataset/
    ├── images/
    │   ├── train/
    │   ├── val/
    │   └── test/
    └── labels/
        ├── train/
        ├── val/
        └── test/

Usage:
    python prepare_dataset.py --input_dir ./labeled_data --output_dir ./yolo_dataset --split 0.7 0.2 0.1

Supports input from:
    - Roboflow export (YOLO format)
    - CVAT export (YOLO 1.1 format)
    - Label Studio export (YOLO format)
"""

import os
import sys
import shutil
import random
import argparse
from pathlib import Path
from typing import List, Tuple
import json


def find_image_files(directory: Path) -> List[Path]:
    """Find all image files in directory."""
    extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
    images = []
    for ext in extensions:
        images.extend(directory.rglob(f'*{ext}'))
        images.extend(directory.rglob(f'*{ext.upper()}'))
    return sorted(set(images))


def find_label_file(image_path: Path, labels_dirs: List[Path]) -> Path:
    """Find corresponding label file for an image."""
    label_name = image_path.stem + '.txt'

    # Check in same directory
    same_dir_label = image_path.parent / label_name
    if same_dir_label.exists():
        return same_dir_label

    # Check in labels directories
    for labels_dir in labels_dirs:
        label_path = labels_dir / label_name
        if label_path.exists():
            return label_path

    return None


def validate_label_file(label_path: Path, num_classes: int = 5) -> Tuple[bool, str]:
    """Validate YOLO format label file."""
    if not label_path or not label_path.exists():
        return False, "Label file not found"

    try:
        with open(label_path, 'r') as f:
            lines = f.readlines()

        if not lines:
            return True, "Empty (no objects)"  # Valid but empty

        for i, line in enumerate(lines):
            parts = line.strip().split()
            if len(parts) != 5:
                return False, f"Line {i+1}: Expected 5 values, got {len(parts)}"

            class_id = int(parts[0])
            if class_id < 0 or class_id >= num_classes:
                return False, f"Line {i+1}: Invalid class_id {class_id}"

            coords = [float(x) for x in parts[1:]]
            for j, coord in enumerate(coords):
                if coord < 0 or coord > 1:
                    return False, f"Line {i+1}: Coordinate {j} out of range: {coord}"

        return True, f"Valid ({len(lines)} objects)"

    except Exception as e:
        return False, f"Parse error: {str(e)}"


def split_dataset(
    image_paths: List[Path],
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    seed: int = 42
) -> Tuple[List[Path], List[Path], List[Path]]:
    """Split dataset into train/val/test sets."""
    random.seed(seed)
    shuffled = image_paths.copy()
    random.shuffle(shuffled)

    n = len(shuffled)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train = shuffled[:train_end]
    val = shuffled[train_end:val_end]
    test = shuffled[val_end:]

    return train, val, test


def copy_pair(image_path: Path, label_path: Path, output_dir: Path, split: str):
    """Copy image and label to output directory."""
    images_dir = output_dir / 'images' / split
    labels_dir = output_dir / 'labels' / split

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    # Copy image
    dst_image = images_dir / image_path.name
    shutil.copy2(image_path, dst_image)

    # Copy label
    if label_path and label_path.exists():
        dst_label = labels_dir / label_path.name
        shutil.copy2(label_path, dst_label)
    else:
        # Create empty label file if no objects
        dst_label = labels_dir / (image_path.stem + '.txt')
        dst_label.touch()


def create_dataset_yaml(output_dir: Path, num_classes: int = 5):
    """Create dataset.yaml for training."""
    yaml_content = f"""# Vietnam Traffic Dataset - Auto-generated
path: {output_dir.absolute()}
train: images/train
val: images/val
test: images/test

nc: {num_classes}

names:
  0: car
  1: truck
  2: motorcycle
  3: bus
  4: ambulance
"""

    yaml_path = output_dir / 'dataset.yaml'
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)

    return yaml_path


def main():
    parser = argparse.ArgumentParser(description="Prepare dataset for YOLO training")
    parser.add_argument("--input_dir", type=str, required=True,
                        help="Directory containing labeled images and labels")
    parser.add_argument("--output_dir", type=str, default="./yolo_dataset",
                        help="Output directory for organized dataset")
    parser.add_argument("--split", type=float, nargs=3, default=[0.7, 0.2, 0.1],
                        help="Train/val/test split ratios (default: 0.7 0.2 0.1)")
    parser.add_argument("--num_classes", type=int, default=5,
                        help="Number of classes")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--validate", action="store_true",
                        help="Validate label files before processing")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    train_ratio, val_ratio, test_ratio = args.split

    # Normalize ratios
    total = train_ratio + val_ratio + test_ratio
    train_ratio, val_ratio, test_ratio = train_ratio/total, val_ratio/total, test_ratio/total

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Split ratios: train={train_ratio:.1%}, val={val_ratio:.1%}, test={test_ratio:.1%}")

    # Find images
    images = find_image_files(input_dir)
    print(f"\nFound {len(images)} images")

    if not images:
        print("Error: No images found!")
        sys.exit(1)

    # Find possible label directories
    labels_dirs = [
        input_dir / 'labels',
        input_dir / 'annotations',
        input_dir / 'Labels',
        input_dir,
    ]
    labels_dirs = [d for d in labels_dirs if d.exists()]

    # Pair images with labels
    pairs = []
    missing_labels = []
    invalid_labels = []

    for img_path in images:
        label_path = find_label_file(img_path, labels_dirs)

        if args.validate:
            is_valid, msg = validate_label_file(label_path, args.num_classes)
            if not is_valid:
                invalid_labels.append((img_path, msg))
                continue

        if label_path:
            pairs.append((img_path, label_path))
        else:
            missing_labels.append(img_path)

    print(f"Valid image-label pairs: {len(pairs)}")
    if missing_labels:
        print(f"Images without labels: {len(missing_labels)}")
    if invalid_labels:
        print(f"Invalid labels: {len(invalid_labels)}")
        for path, msg in invalid_labels[:5]:
            print(f"  - {path.name}: {msg}")

    if not pairs:
        print("Error: No valid image-label pairs found!")
        sys.exit(1)

    # Split dataset
    image_paths = [p[0] for p in pairs]
    train_imgs, val_imgs, test_imgs = split_dataset(
        image_paths, train_ratio, val_ratio, test_ratio, args.seed
    )

    print(f"\nSplit: train={len(train_imgs)}, val={len(val_imgs)}, test={len(test_imgs)}")

    # Create output directory structure
    if output_dir.exists():
        print(f"Warning: Output directory exists, will be overwritten")
        shutil.rmtree(output_dir)

    # Create pairs mapping
    img_to_label = {p[0]: p[1] for p in pairs}

    # Copy files
    print("\nCopying files...")
    for img in train_imgs:
        copy_pair(img, img_to_label.get(img), output_dir, 'train')
    for img in val_imgs:
        copy_pair(img, img_to_label.get(img), output_dir, 'val')
    for img in test_imgs:
        copy_pair(img, img_to_label.get(img), output_dir, 'test')

    # Create dataset.yaml
    yaml_path = create_dataset_yaml(output_dir, args.num_classes)

    # Save split info
    split_info = {
        "train": [str(p.name) for p in train_imgs],
        "val": [str(p.name) for p in val_imgs],
        "test": [str(p.name) for p in test_imgs],
        "settings": {
            "train_ratio": train_ratio,
            "val_ratio": val_ratio,
            "test_ratio": test_ratio,
            "seed": args.seed,
        }
    }
    with open(output_dir / 'split_info.json', 'w') as f:
        json.dump(split_info, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Dataset preparation complete!")
    print(f"Output: {output_dir}")
    print(f"Dataset YAML: {yaml_path}")
    print(f"\nDirectory structure:")
    print(f"  {output_dir}/")
    print(f"  ├── images/")
    print(f"  │   ├── train/ ({len(train_imgs)} images)")
    print(f"  │   ├── val/ ({len(val_imgs)} images)")
    print(f"  │   └── test/ ({len(test_imgs)} images)")
    print(f"  ├── labels/")
    print(f"  │   ├── train/")
    print(f"  │   ├── val/")
    print(f"  │   └── test/")
    print(f"  └── dataset.yaml")


if __name__ == "__main__":
    main()
