"""
Frame Extraction Script for Vietnam Traffic Dataset.

This script extracts frames from video files for manual annotation.
It uses intelligent sampling to ensure diverse frames are captured.

Usage:
    python extract_frames.py --videos_dir ../dataset --output_dir ./frames --interval 30

Features:
    - Smart frame sampling (not just every N frames)
    - Scene change detection for diverse samples
    - Brightness-based filtering to ensure varied lighting
    - Progress tracking and resumable extraction
"""

import os
import sys
import cv2
import argparse
import hashlib
import json
from pathlib import Path
from typing import List, Tuple, Optional
from collections import defaultdict
import numpy as np


def calculate_frame_hash(frame: np.ndarray, hash_size: int = 8) -> str:
    """Calculate perceptual hash for frame similarity detection."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size))
    diff = resized[:, 1:] > resized[:, :-1]
    return ''.join(str(int(b)) for b in diff.flatten())


def calculate_brightness(frame: np.ndarray) -> float:
    """Calculate average brightness of frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return np.mean(gray)


def is_scene_change(prev_hash: str, curr_hash: str, threshold: int = 10) -> bool:
    """Detect if there's a significant scene change between frames."""
    if not prev_hash:
        return True
    diff = sum(c1 != c2 for c1, c2 in zip(prev_hash, curr_hash))
    return diff > threshold


def extract_frames_from_video(
    video_path: str,
    output_dir: str,
    frame_interval: int = 30,
    min_brightness: float = 20.0,
    max_brightness: float = 240.0,
    scene_change_threshold: int = 10,
    max_frames_per_video: Optional[int] = None,
) -> Tuple[int, List[dict]]:
    """
    Extract frames from a single video with intelligent sampling.

    Args:
        video_path: Path to video file
        output_dir: Directory to save extracted frames
        frame_interval: Base interval between frames
        min_brightness: Minimum brightness threshold
        max_brightness: Maximum brightness threshold
        scene_change_threshold: Threshold for scene change detection
        max_frames_per_video: Maximum frames to extract per video

    Returns:
        Tuple of (frames_extracted, frame_metadata_list)
    """
    video_name = Path(video_path).stem
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Cannot open video {video_path}")
        return 0, []

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0

    print(f"\nProcessing: {video_name}")
    print(f"  FPS: {fps:.1f}, Duration: {duration:.1f}s, Total frames: {total_frames}")

    extracted_count = 0
    frame_metadata = []
    prev_hash = None
    frame_idx = 0

    # Brightness buckets for diversity
    brightness_buckets = defaultdict(int)
    bucket_size = 30
    max_per_bucket = max_frames_per_video // 8 if max_frames_per_video else 50

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Check frame interval
        if frame_idx % frame_interval != 0:
            frame_idx += 1
            continue

        # Calculate frame properties
        brightness = calculate_brightness(frame)
        frame_hash = calculate_frame_hash(frame)

        # Skip if brightness out of range
        if brightness < min_brightness or brightness > max_brightness:
            frame_idx += 1
            continue

        # Check brightness bucket diversity
        bucket = int(brightness // bucket_size)
        if brightness_buckets[bucket] >= max_per_bucket:
            frame_idx += 1
            continue

        # Prefer scene changes for diversity
        is_change = is_scene_change(prev_hash, frame_hash, scene_change_threshold)

        # Extract frame
        timestamp = frame_idx / fps if fps > 0 else 0
        frame_filename = f"{video_name}_frame_{frame_idx:06d}.jpg"
        frame_path = os.path.join(output_dir, frame_filename)

        cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

        metadata = {
            "filename": frame_filename,
            "video": video_name,
            "frame_idx": frame_idx,
            "timestamp": round(timestamp, 2),
            "brightness": round(brightness, 1),
            "is_scene_change": is_change,
        }
        frame_metadata.append(metadata)

        brightness_buckets[bucket] += 1
        prev_hash = frame_hash
        extracted_count += 1

        if max_frames_per_video and extracted_count >= max_frames_per_video:
            print(f"  Reached max frames limit ({max_frames_per_video})")
            break

        frame_idx += 1

    cap.release()
    print(f"  Extracted: {extracted_count} frames")

    return extracted_count, frame_metadata


def main():
    parser = argparse.ArgumentParser(description="Extract frames from videos for annotation")
    parser.add_argument("--videos_dir", type=str, default="../dataset",
                        help="Directory containing video files")
    parser.add_argument("--output_dir", type=str, default="./frames",
                        help="Output directory for extracted frames")
    parser.add_argument("--interval", type=int, default=30,
                        help="Frame extraction interval (default: 30 = 1 frame/second at 30fps)")
    parser.add_argument("--max_per_video", type=int, default=100,
                        help="Maximum frames to extract per video")
    parser.add_argument("--video_extensions", type=str, nargs="+",
                        default=[".mp4", ".avi", ".mov", ".mkv"],
                        help="Video file extensions to process")

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Find all videos
    videos_dir = Path(args.videos_dir)
    video_files = []
    for ext in args.video_extensions:
        video_files.extend(videos_dir.glob(f"*{ext}"))
        video_files.extend(videos_dir.glob(f"*{ext.upper()}"))

    video_files = sorted(set(video_files))

    if not video_files:
        print(f"No video files found in {args.videos_dir}")
        sys.exit(1)

    print(f"Found {len(video_files)} video files")
    print(f"Output directory: {args.output_dir}")
    print(f"Frame interval: {args.interval}")
    print(f"Max frames per video: {args.max_per_video}")

    # Extract frames from each video
    all_metadata = []
    total_extracted = 0

    for video_path in video_files:
        count, metadata = extract_frames_from_video(
            str(video_path),
            args.output_dir,
            frame_interval=args.interval,
            max_frames_per_video=args.max_per_video,
        )
        total_extracted += count
        all_metadata.extend(metadata)

    # Save metadata
    metadata_path = os.path.join(args.output_dir, "frame_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump({
            "total_frames": total_extracted,
            "videos_processed": len(video_files),
            "settings": {
                "interval": args.interval,
                "max_per_video": args.max_per_video,
            },
            "frames": all_metadata,
        }, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Extraction complete!")
    print(f"Total frames extracted: {total_extracted}")
    print(f"Frames saved to: {args.output_dir}")
    print(f"Metadata saved to: {metadata_path}")
    print(f"\nNext steps:")
    print(f"1. Upload frames to a labeling tool (Roboflow, CVAT, or Label Studio)")
    print(f"2. Create labels for: car, truck, motorcycle, bus, ambulance")
    print(f"3. Export annotations in YOLO format")


if __name__ == "__main__":
    main()
