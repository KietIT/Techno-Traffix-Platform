# Techno Traffix — AI-Powered Traffic Monitoring Platform

A Vietnamese AI traffic monitoring system using dual-model YOLOv8 detection, ByteTrack tracking, rule-based accident detection, and Claude-powered traffic law Q&A.

---

## Features

- **Dual-Model Vehicle Detection** — two specialized YOLOv8 models run in parallel: one for general vehicles (car, truck, motorcycle, bus), one for ambulances
- **Object Tracking** — ByteTrack with persistent IDs and speed/acceleration estimation
- **Accident Detection** — 4-stage rule-based algorithm (proximity → collision candidate → post-collision behavior → voting)
- **Traffic Law Q&A** — RAG knowledge base (Vietnamese traffic law) + Claude LLM fallback
- **Web Dashboard** — drag-drop image/video upload, interactive Leaflet map, air quality widget, community feed
- **Admin Desktop UI** — Tkinter dashboard for 4-camera intersection monitoring
- **CLI Demo** — standalone image and video analysis without the web server

---

## Project Structure

```
Traffic-Platform/
├── video_detection/          # Core detection pipeline
│   ├── config/config.yaml    # All detection/tracking tuning
│   ├── detector/             # YOLODetector wrapper
│   ├── tracker/              # ByteTrack integration
│   ├── pipeline/             # InferencePipeline, VehicleCounter
│   ├── speed_estimation/     # Velocity, heading, acceleration
│   ├── accident_detection/   # Rule-based 4-stage algorithm
│   └── tests/
├── user-ui/
│   ├── backend/              # Flask API (port 5000)
│   │   └── app/
│   │       ├── services/     # AIService, TaskManager, ChatService
│   │       ├── knowledge/    # Vietnamese traffic law KB
│   │       └── api/          # Route handlers
│   └── frontend/             # Vanilla JS + ES6 modules (no build step)
├── admin-ui/                 # Tkinter desktop dashboard
├── training/                 # YOLOv8 training scripts & notebooks
├── demo.py                   # Standalone CLI demo
└── requirements.txt
```

---

## Prerequisites

- Python 3.9+
- pip

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd Traffic-Platform
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download YOLO Models

The trained YOLO model weights are hosted on Google Drive. Download them from:

**[YOLO Models](https://drive.google.com/drive/folders/1QirKN04mXn7teCnd8zldtyfNF1BstSzR?usp=sharing)**

Place all downloaded `.pt` files into the `video_detection/` directory:

```
video_detection/
├── vehicle_detection_yolov8l.pt          # General vehicle detection
├── vehicle_detection_yolov8l_ambulance.pt # Ambulance detection
├── accident_classification_yolov8l.pt     # Accident classification
└── traffic_classification_yolov8l.pt      # Traffic state classification
```

You can download manually from the link above, or use `gdown`:

```bash
pip install gdown

# Download the entire folder (replace FOLDER_ID with the ID from the Drive link)
gdown --folder https://drive.google.com/drive/folders/1QirKN04mXn7teCnd8zldtyfNF1BstSzR --output video_detection/
```

### 4. Configure environment variables

Create `user-ui/backend/.env`:

```env
ANTHROPIC_API_KEY=your_api_key_here
ANTHROPIC_MODEL=claude-3-haiku-20240307
HOST=0.0.0.0
PORT=5000
RAG_FAQ_THRESHOLD=3.0
RAG_VIOLATION_THRESHOLD=4.0
RAG_GPLX_THRESHOLD=3.0
WAQI_API_TOKEN=demo
```

Get an Anthropic API key at [console.anthropic.com](https://console.anthropic.com).

---

## Usage

### Web Application

```bash
python user-ui/backend/main.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

**Tabs:**
- **Tổng Quan** — overview and hero section
- **Phân Tích AI** — drag-drop image or video for detection
- **Bản Đồ** — interactive traffic map (Buon Ma Thuot)
- **Không Khí** — real-time air quality
- **Cộng Đồng** — community posts feed

The chatbot (TECHNO TRAFFIX) answers Vietnamese traffic law questions using RAG + Claude.

---

### CLI Demo

**Image mode** — analyze up to 4 intersection images:

```bash
python demo.py --img east.jpg west.jpg south.jpg north.jpg -o results/
```

**Video mode** — analyze a video file or webcam:

```bash
python demo.py --video video.mp4 -o results/
python demo.py --video 0           # Webcam
python demo.py --video rtsp://...  # RTSP stream
```

**Options:**

| Flag | Description |
|---|---|
| `--img` | One or more image paths (east/west/south/north) |
| `--video` | Video file path, RTSP URL, or webcam index |
| `-o` | Output directory (default: `results/`) |
| `--no-region` | Disable region-of-interest filtering |

**Output files:**
- `<name>_detected.mp4` — annotated video with bounding boxes and track IDs
- `<name>_result.json` — detection summary JSON

---

### Video Detection Pipeline (direct)

```bash
cd video_detection
python main.py --video <path_or_rtsp> [--show] [--config config/config.yaml]
```

---

### Admin Desktop Dashboard

```bash
python admin-ui/dashboard.py
```

Tkinter GUI for 4-camera intersection monitoring. Upload images for each direction (east/west/south/north), view vehicle counts, and simulate traffic light control.

---

## API Reference

Base URL: `http://localhost:5000`

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/analyze/image` | POST | Submit image for analysis — returns `task_id` |
| `/api/analyze/video` | POST | Submit video for analysis — returns `task_id` |
| `/api/task/<task_id>` | GET | Poll task progress and retrieve results |
| `/api/chat` | POST | Traffic law Q&A (RAG + Claude) |
| `/api/chat/validate` | POST | Quick topic validation (no LLM call) |
| `/api/traffic/data` | GET | OSRM-based traffic simulation data |

**Example — submit image and poll result:**

```bash
# Submit
curl -X POST http://localhost:5000/api/analyze/image \
  -F "file=@intersection.jpg"
# → {"task_id": "abc123"}

# Poll
curl http://localhost:5000/api/task/abc123
# → {"status": "completed", "result": {...}}
```

---

## Architecture

### Dual-Model Detection

Two YOLO models run in parallel and results are merged:

| Model | Target | Classes |
|---|---|---|
| `vehicle_detection_yolov8l.pt` | General vehicles | car(0), truck(1), motorcycle(2), bus(3) |
| `vehicle_detection_yolov8l_ambulance.pt` | Ambulance | ambulance(4) |

Merge rule: skip ambulance detections from the general model; skip non-ambulance detections from the ambulance model.

### Accident Detection (4-Stage Algorithm)

1. **Proximity** — vehicles closer than 100 px or IoU > 0.05 for ≥2 frames
2. **Collision Candidate** — IoU > 0.15 + velocity change > 40% + heading change > 20° for ≥5 frames
3. **Post-Collision Behavior** — stopped or slow movement within a 90-frame window
4. **Voting** — alert if ≥3 of 5 indicators triggered

### Thread Safety

- `AIService` is a singleton with a `threading.Lock` — all YOLO inference is serialized
- `TaskManager` uses a single-worker `ThreadPoolExecutor` — background tasks run one at a time
- Flask reloader is disabled (`use_reloader=False`) to prevent mid-inference crashes

---

## Configuration

All detection and tracking parameters are in `video_detection/config/config.yaml`.

Key tunable parameters:

```yaml
model:
  confidence_threshold: 0.25
  class_thresholds:
    motorcycle: 0.20   # most sensitive
    car: 0.30
    ambulance: 0.30
    truck: 0.35
    bus: 0.35

tracker:
  track_thresh: 0.4
  track_buffer: 50      # frames to keep lost tracks

accident_detection:
  collision_candidate:
    velocity_change_threshold: 0.40
    heading_change_threshold: 20
  confirmation:
    min_indicators: 3   # out of 5
```

---

## Running Tests

```bash
# Video detection pipeline tests
cd video_detection && pytest tests/test_pipeline.py -v

# Backend API tests
cd user-ui/backend && python -m pytest tests/ -v

# Single test class
cd user-ui/backend && python -m pytest tests/test_chat.py::TestChatService -v
```

---

## Linting

```bash
ruff check user-ui/backend/
flake8 user-ui/backend/app/
```

---

## Training

Training scripts and Kaggle notebooks are in `training/`. The main orchestration script is `training/TRAINING_WORKFLOW.py`. Dataset annotations are in YOLO format under `training/datasets/` and COCO format under `dataset/`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8 (Ultralytics) |
| Tracking | ByteTrack (scipy + lap) |
| Web backend | Flask, Gunicorn |
| AI/Chat | Anthropic Claude (claude-3-haiku) |
| Maps | Leaflet 1.9.4 + CartoDB |
| Frontend | Vanilla JS (ES6 modules, no build step) |
| Desktop UI | Tkinter + Pillow |
| Routing | OSRM API |
| Air quality | WAQI API |
