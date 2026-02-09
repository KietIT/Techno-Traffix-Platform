#!/usr/bin/env python3
"""
================================================================================
VIETNAM TRAFFIC DETECTION - COMPLETE TRAINING WORKFLOW
================================================================================

This file documents the complete workflow for training a custom YOLO model
on your Vietnam traffic dataset and deploying it to Kaggle.

DATASET CHARACTERISTICS (from your description):
- 17 videos, longest is 1 minute 2 seconds
- Diverse lighting (bright to dark)
- Diverse traffic levels (no congestion to heavy)
- Vehicle types: car, truck, motorcycle, bus, ambulance
- Camera angles: 360 cameras and fixed traffic pole cameras

ESTIMATED TIMELINE:
- Frame extraction: 5-10 minutes
- Auto-labeling: 10-15 minutes
- Manual label review: 2-4 hours (most time-consuming)
- Upload to Kaggle: 10-20 minutes
- Training on Kaggle: 2-4 hours
- Integration: 5 minutes

================================================================================
"""

WORKFLOW = """
================================================================================
STEP 1: EXTRACT FRAMES FROM VIDEOS
================================================================================

Run this command from the training/scripts directory:

    cd training/scripts
    python extract_frames.py \\
        --videos_dir ../../dataset \\
        --output_dir ../frames \\
        --interval 15 \\
        --max_per_video 100

Parameters explained:
    --interval 15      : Extract every 15th frame (~2 frames/second at 30fps)
    --max_per_video 100: Max 100 frames per video (17 videos × 100 = 1700 frames)

This will create:
    training/frames/
    ├── 01_frame_000000.jpg
    ├── 01_frame_000015.jpg
    ├── ...
    └── frame_metadata.json

Expected output: ~1000-1700 frames total

================================================================================
STEP 2: AUTO-LABEL FRAMES (SAVES TIME!)
================================================================================

The pre-trained YOLO model can automatically label most vehicles.
This reduces manual labeling work by 60-80%.

    cd training/scripts
    python auto_label_frames.py \\
        --frames_dir ../frames \\
        --output_dir ../auto_labels \\
        --model ../../video_detection/yolov8l.pt \\
        --confidence 0.25 \\
        --visualize

This creates:
    training/auto_labels/
    ├── 01_frame_000000.txt    (YOLO format labels)
    ├── 01_frame_000015.txt
    ├── ...
    ├── visualizations/         (if --visualize)
    │   ├── viz_01_frame_000000.jpg
    │   └── ...
    └── auto_label_stats.json

IMPORTANT: These are AUTO-GENERATED labels that need MANUAL REVIEW!

================================================================================
STEP 3: MANUAL LABEL REVIEW & CORRECTION
================================================================================

You MUST review and correct the auto-generated labels. Here are your options:

OPTION A: ROBOFLOW (Recommended - Easiest)
------------------------------------------
1. Go to https://roboflow.com (free tier: 10,000 images)
2. Create new project: "Vietnam Traffic Detection"
3. Upload frames from training/frames/
4. Upload labels from training/auto_labels/
5. Review and correct labels in the web UI
6. Add missing ambulance labels (not auto-detected)
7. Export as "YOLO v8" format
8. Download the exported dataset

OPTION B: CVAT (Free, Open Source)
----------------------------------
1. Go to https://app.cvat.ai or install locally
2. Create new task with your frames
3. Import labels (CVAT supports YOLO format)
4. Review and correct in the annotation UI
5. Export as "YOLO 1.1" format

OPTION C: LABEL STUDIO (Free, Self-hosted)
------------------------------------------
1. Install: pip install label-studio
2. Run: label-studio start
3. Create project, import images
4. Configure labeling interface for object detection
5. Import pre-labels, review and correct
6. Export as YOLO format

LABELING TIPS:
- Focus on correcting obvious errors first
- Add ALL ambulances (not detected by COCO model)
- Remove false positives (signs, shadows mistaken for vehicles)
- Ensure bounding boxes are tight around vehicles
- Label partially visible vehicles at frame edges

================================================================================
STEP 4: PREPARE DATASET FOR TRAINING
================================================================================

After exporting corrected labels from your labeling tool:

    cd training/scripts
    python prepare_dataset.py \\
        --input_dir ../labeled_data \\
        --output_dir ../yolo_dataset \\
        --split 0.7 0.2 0.1 \\
        --validate

This creates the final dataset structure:
    training/yolo_dataset/
    ├── images/
    │   ├── train/  (70% of data)
    │   ├── val/    (20% of data)
    │   └── test/   (10% of data)
    ├── labels/
    │   ├── train/
    │   ├── val/
    │   └── test/
    └── dataset.yaml

================================================================================
STEP 5: UPLOAD DATASET TO KAGGLE
================================================================================

1. Go to https://www.kaggle.com/datasets/new

2. Click "New Dataset"

3. Dataset settings:
   - Title: "Vietnam Traffic Detection Dataset"
   - Visibility: Private (recommended)
   - License: Your choice

4. Upload files:
   - Drag and drop the entire training/yolo_dataset/ folder
   - Or zip it first:

     cd training
     zip -r vietnam_traffic_dataset.zip yolo_dataset/

5. Click "Create" and wait for upload to complete

6. Note your dataset path (e.g., "your-username/vietnam-traffic-detection-dataset")

================================================================================
STEP 6: RUN TRAINING ON KAGGLE
================================================================================

1. Go to https://www.kaggle.com/code/new

2. Settings:
   - Enable GPU: Settings → Accelerator → GPU P100 or T4
   - Enable Internet: Settings → Internet → On

3. Add your dataset:
   - Click "+ Add Data"
   - Search for your uploaded dataset
   - Add it to the notebook

4. Upload the training notebook:
   - Upload: training/notebooks/kaggle_yolo_training.ipynb
   - Or copy/paste the cells

5. IMPORTANT: Update the dataset path in the notebook:

   DATASET_PATH = '/kaggle/input/vietnam-traffic-detection-dataset'

   (Replace with your actual dataset path)

6. Run all cells and wait for training to complete (2-4 hours)

7. Download the trained model from the Output tab:
   - vietnam_traffic_model.zip

================================================================================
STEP 7: INTEGRATE TRAINED MODEL
================================================================================

After downloading the trained model from Kaggle:

1. Extract vietnam_traffic_model.zip

2. Run the integration script:

    cd training/scripts
    python integrate_trained_model.py \\
        --model /path/to/vietnam_traffic_yolov8l_best.pt \\
        --test

This will:
- Copy model to video_detection/
- Update config.yaml
- Update class mappings
- Run a test inference

3. Test the model manually:

    cd video_detection
    python main.py --video ../dataset/01.mp4 --model vietnam_traffic_yolov8l_best.pt

================================================================================
EXPECTED RESULTS
================================================================================

With your dataset characteristics, you should expect:

mAP50 Performance (approximate):
- car:        85-95%  (common, easy to detect)
- truck:      80-90%  (less common, larger)
- motorcycle: 75-85%  (common in Vietnam, smaller)
- bus:        80-90%  (larger, distinctive)
- ambulance:  70-85%  (rare, depends on training samples)

Overall mAP50: 80-90% (with good labeling)

Tips to improve accuracy:
1. More training data (especially for rare classes like ambulance)
2. More epochs (up to 200)
3. Larger model (yolov8x instead of yolov8l)
4. Better labeling quality

================================================================================
TROUBLESHOOTING
================================================================================

Problem: Training loss not decreasing
Solution: Check label quality, reduce learning rate

Problem: Out of memory on Kaggle
Solution: Reduce batch size (8 or 4), reduce image size (512)

Problem: Poor performance on dark images
Solution: Add more dark images to training, increase HSV augmentation

Problem: Motorcycle detection poor
Solution: Lower confidence threshold for motorcycles in config

Problem: False positives from signs/shadows
Solution: Better labeling, higher confidence thresholds

================================================================================
FILE STRUCTURE AFTER SETUP
================================================================================

Traffic-Platform/
├── dataset/                    # Your 17 videos
│   ├── 01.mp4
│   ├── 02.mp4
│   └── ...
├── training/                   # Training files (NEW)
│   ├── scripts/
│   │   ├── extract_frames.py
│   │   ├── auto_label_frames.py
│   │   ├── prepare_dataset.py
│   │   └── integrate_trained_model.py
│   ├── notebooks/
│   │   └── kaggle_yolo_training.ipynb
│   ├── configs/
│   │   └── dataset.yaml
│   ├── frames/                 # Extracted frames (created)
│   ├── auto_labels/            # Auto-generated labels (created)
│   ├── labeled_data/           # Corrected labels (from labeling tool)
│   ├── yolo_dataset/           # Final training dataset (created)
│   └── TRAINING_WORKFLOW.py    # This file
└── video_detection/            # Existing detection code
    ├── vietnam_traffic_yolov8l_best.pt  # Your trained model (after integration)
    └── ...

================================================================================
"""


def print_workflow():
    """Print the complete workflow."""
    print(WORKFLOW)


def print_quick_start():
    """Print a quick start guide."""
    quick_start = """
================================================================================
QUICK START - MINIMUM COMMANDS
================================================================================

# 1. Extract frames
cd training/scripts
python extract_frames.py --videos_dir ../../dataset --output_dir ../frames

# 2. Auto-label (optional but saves time)
python auto_label_frames.py --frames_dir ../frames --output_dir ../auto_labels --model ../../video_detection/yolov8l.pt

# 3. Label with Roboflow (web interface)
# Upload frames/ and auto_labels/ to roboflow.com
# Review, correct, export as YOLO v8

# 4. Prepare dataset
python prepare_dataset.py --input_dir ../labeled_data --output_dir ../yolo_dataset

# 5. Upload yolo_dataset/ to Kaggle

# 6. Run kaggle_yolo_training.ipynb on Kaggle with GPU

# 7. Download trained model and integrate
python integrate_trained_model.py --model /path/to/vietnam_traffic_yolov8l_best.pt --test

Done! Your custom model is ready.
================================================================================
"""
    print(quick_start)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        print_quick_start()
    else:
        print_workflow()
        print("\nTip: Run with --quick for a condensed version")
