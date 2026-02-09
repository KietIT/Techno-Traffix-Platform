# Backend Configuration
import os
import sys
from pathlib import Path

# Paths
# BASE_DIR = backend/app (where this config file's parent is)
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static"
PROCESSED_DIR = STATIC_DIR / "processed"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = STATIC_DIR / "uploads"

# Video Detection Module Path
# Path structure: TechnoTraffix/web-user/backend/app/core/config.py
# BASE_DIR = backend/app -> backend -> web-user -> TechnoTraffix (repo root)
PROJECT_ROOT = BASE_DIR.parent.parent.parent  # TechnoTraffix/
VIDEO_DETECTION_DIR = PROJECT_ROOT / "video_detection"
VIDEO_DETECTION_CONFIG = VIDEO_DETECTION_DIR / "config" / "config.yaml"

# Trained model paths
VEHICLE_DETECTION_MODEL = VIDEO_DETECTION_DIR / "vehicle_detection_yolov8l.pt"
ACCIDENT_CLASSIFICATION_MODEL = VIDEO_DETECTION_DIR / "accident_classification_yolov8l.pt"
TRAFFIC_CLASSIFICATION_MODEL = VIDEO_DETECTION_DIR / "traffic_classification_yolov8l.pt"

# Fallback to old model if new ones don't exist
VIDEO_DETECTION_MODEL = VIDEO_DETECTION_DIR / "yolov8l.pt"

# Add project root and video_detection to Python path for imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(VIDEO_DETECTION_DIR) not in sys.path:
    sys.path.insert(0, str(VIDEO_DETECTION_DIR))

# Ensure directories exist
STATIC_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# Traffic Detection Configuration
TRAFFIC_CLASSES = {
    'motorcycle': {'id': 3, 'weight': 1},
    'car': {'id': 2, 'weight': 3},
    'bus': {'id': 5, 'weight': 5},
    'truck': {'id': 7, 'weight': 5}
}

# Confidence Thresholds
TRAFFIC_CONFIDENCE = 0.25   # Low for high recall
ACCIDENT_CONFIDENCE = 0.75  # High for precision

# Congestion Scoring
SEVERE_CONGESTION_SCORE = 20
HEAVY_TRAFFIC_SCORE = 12

# Accident Detection Filters
ACCIDENT_MIN_DETECTIONS = 3
ACCIDENT_MIN_BOX_AREA = 3000

# RAG Configuration - Thresholds for using RAG without LLM
# Higher scores = more confident the RAG result is sufficient
RAG_FAQ_THRESHOLD = float(os.getenv("RAG_FAQ_THRESHOLD", "3.0"))  # FAQ answers are complete Q&A pairs
RAG_VIOLATION_THRESHOLD = float(os.getenv("RAG_VIOLATION_THRESHOLD", "4.0"))  # Violations need higher confidence
RAG_GPLX_THRESHOLD = float(os.getenv("RAG_GPLX_THRESHOLD", "3.0"))  # License info threshold

# Air Quality - WAQI API (free: https://aqicn.org/data-platform/token/)
WAQI_API_TOKEN = os.getenv("WAQI_API_TOKEN", "demo")
WAQI_CACHE_TTL = int(os.getenv("WAQI_CACHE_TTL", "600"))  # seconds

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
