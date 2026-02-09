# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Techno Traffix - Vietnamese traffic monitoring system using YOLOv8 for vehicle detection, ByteTrack for object tracking, and a rule-based 4-stage accident detection algorithm. Includes a Flask web backend with Anthropic Claude integration for traffic law Q&A.

## Common Commands

### Video Detection CLI
```bash
cd video_detection
python main.py --video <path_or_rtsp_url> [--show] [--config config/config.yaml]
python main.py --video video.mp4 --model yolov8l.pt --device cuda --conf 0.5
python main.py --video 0  # Use webcam
```

### Web Backend
```bash
cd web-user/backend
python main.py  # Runs on http://0.0.0.0:5000
```

### Running Tests
```bash
cd video_detection
pytest tests/test_pipeline.py -v
pytest tests/test_pipeline.py::test_pipeline_config_defaults -v  # Single test
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

## Architecture

### Video Detection Pipeline (`video_detection/`)
```
InferencePipeline (pipeline/inference_pipeline.py)
├── VideoReader (video_io/) → OpenCV video/RTSP capture
├── YOLODetector (detector/) → YOLOv8 detection with class-specific thresholds
├── ByteTrackTracker (tracker/) → Object tracking with ID persistence
├── SpeedEstimator (speed_estimation/) → Velocity, heading, acceleration
└── AccidentDetector (accident_detection/rule_based.py) → 4-stage detection
```

**4-Stage Accident Detection Logic:**
1. **Proximity** - Vehicles within IOU threshold 0.05
2. **Collision Candidate** - IOU 0.15+ sustained for min 5 frames
3. **Post-Collision** - Analyze behavior over 90 frame window (stops, direction changes)
4. **Confirmation** - Vote on 5 indicators, require ≥3 for accident confirmation

### Web Backend (`web-user/backend/`)
```
Flask App (main.py)
├── API Routes (app/api/routes.py) → /api/health, /api/analyze/*, /api/chat
├── AIService (app/services/ai_service.py) → 3-model YOLO ensemble
├── ChatService (app/services/chat_service.py) → Claude integration
└── Knowledge Bases (app/knowledge/) → FAQ, traffic laws, license info
```

### Key Configuration

**Pipeline Config:** `video_detection/config/config.yaml`
- Detection: conf_threshold=0.25, iou_threshold=0.55
- Tracker: ByteTrack with 50-frame buffer for occlusion handling
- Class-specific thresholds: motorcycle=0.20, car=0.30
- Size filtering: 400-500000 pixel area, 0.3-4.0 aspect ratio

**Environment:** `web-user/backend/.env`
- `ANTHROPIC_API_KEY` - Required for chat service
- `ANTHROPIC_MODEL` - Default: claude-3-haiku-20240307
- `PORT` - Default: 5000

### Models

Three trained YOLOv8L models stored in `vietnam_traffic_models/`:
- `vehicle_detection_yolov8l.pt` - 5 classes: car, truck, motorcycle, bus, ambulance
- `accident_classification_yolov8l.pt` - Binary accident classifier
- `traffic_classification_yolov8l.pt` - Traffic jam classifier

Falls back to default `yolov8l.pt` if custom models unavailable.

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/analyze/image` | POST | Analyze image for accidents |
| `/api/analyze/video` | POST | Analyze video file |
| `/api/chat` | POST | Traffic law Q&A with Claude |

## Deployment

Configured for Render.com via `render.yaml`:
- Python 3.11, Singapore region
- Build: `pip install -r requirements.txt`
- Start: `cd web-user/backend && python main.py`
