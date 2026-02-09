# API Routes Blueprint
from flask import Blueprint, request, jsonify, send_from_directory, Response
from pathlib import Path
import os
import asyncio
import logging

from app.core.config import PROCESSED_DIR, STATIC_DIR, HOST, PORT
from app.services.ai_service import ai_service
from app.services.traffic_service import traffic_service
from app.services.chat_service import chat_service
from app.services.air_quality_service import air_quality_service
from app.models.chat_models import ChatRequest
from app.utils.file_utils import generate_unique_filename, cleanup_file, get_file_size_mb, get_file_size_kb

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


@api.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "message": "Techno Traffix Backend is running"})


@api.route("/analyze/image", methods=["POST"])
def analyze_image():
    """
    API endpoint to analyze uploaded image for traffic and accidents.
    """
    try:
        if "image" not in request.files:
            return jsonify({"success": False, "error": "No image file provided"}), 400

        image_file = request.files["image"]
        if image_file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Generate unique filenames
        filename = image_file.filename or "upload.jpg"
        file_ext = os.path.splitext(filename)[1] or ".jpg"
        input_filename = generate_unique_filename("input", file_ext)
        output_filename = generate_unique_filename("output", file_ext)

        input_path = STATIC_DIR / input_filename
        output_path = PROCESSED_DIR / output_filename

        print(f"Saving image to: {input_path}")
        image_file.save(str(input_path))

        # Process image
        result = ai_service.process_image(input_path, output_path)

        # Cleanup input
        cleanup_file(input_path)

        # Build response URL - use relative path for same-origin requests
        media_url = f"/api/static/processed/{output_filename}"

        return jsonify(
            {
                "success": True,
                "traffic_status": result["traffic_status"],
                "is_traffic_jam": result.get("is_traffic_jam", False),
                "accident_warning": result["accident_detected"],
                "media_url": media_url,
                "media_type": "image",
            }
        )

    except Exception as e:
        print(f"Error processing image: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/analyze/video", methods=["POST"])
def analyze_video():
    """
    API endpoint to analyze uploaded video for traffic and accidents.
    """
    try:
        if "video" not in request.files:
            return jsonify({"success": False, "error": "No video file provided"}), 400

        video_file = request.files["video"]
        if video_file.filename == "":
            return jsonify({"success": False, "error": "No file selected"}), 400

        # Generate unique filenames
        input_filename = generate_unique_filename("input", ".mp4")
        output_filename = generate_unique_filename("output", ".mp4")

        input_path = STATIC_DIR / input_filename
        output_path = PROCESSED_DIR / output_filename

        print(f"Saving video to: {input_path}")
        video_file.save(str(input_path))

        # Process video
        result = ai_service.process_video(input_path, output_path)

        # Cleanup input
        cleanup_file(input_path)

        # Build response URL - use relative path for same-origin requests
        actual_filename = result.get("output_filename", output_filename)
        media_url = f"/api/static/processed/{actual_filename}"

        print(f"Sending response - media_url: {media_url}")
        print(
            f"Traffic: {result['traffic_status']}, Jam: {result.get('is_traffic_jam')}, Accident: {result['accident_detected']}"
        )

        return jsonify(
            {
                "success": True,
                "traffic_status": result["traffic_status"],
                "is_traffic_jam": result.get("is_traffic_jam", False),
                "accident_warning": result["accident_detected"],
                "media_url": media_url,
                "video_url": media_url,  # Backward compatibility
                "media_type": "video",
            }
        )

    except Exception as e:
        print(f"Error processing video: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@api.route("/traffic/data", methods=["GET"])
def get_traffic_data():
    """
    Generate traffic simulation data with OSRM routing.

    Query params (priority order):
      zone_id   – use a predefined zone
      lat & lng – use browser geolocation (dynamic)
      radius_km – radius in km (default 10 for geolocation, zone value for zones)
      (none)    – fall back to first predefined zone
    """
    try:
        zone_id = request.args.get("zone_id")
        lat = request.args.get("lat", type=float)
        lng = request.args.get("lng", type=float)
        radius_km = request.args.get("radius_km", type=float)

        data = traffic_service.get_traffic_data(
            zone_id=zone_id, lat=lat, lng=lng, radius_km=radius_km
        )
        return jsonify(data)

    except Exception as e:
        print(f"Error getting traffic data: {e}")
        return jsonify({"error": str(e), "zone": None, "routes": []}), 500


@api.route("/air-quality", methods=["GET"])
def get_air_quality():
    """
    Fetch real-time AQI data from WAQI API.

    Query params:
      lat       – latitude (required)
      lng       – longitude (required)
      radius_km – search radius in km (default 50)
    """
    try:
        lat = request.args.get("lat", type=float)
        lng = request.args.get("lng", type=float)
        radius_km = request.args.get("radius_km", 50, type=float)

        if lat is None or lng is None:
            return jsonify({"error": "lat and lng are required"}), 400

        data = air_quality_service.get_aqi_data(lat, lng, radius_km)
        return jsonify(data)

    except Exception as e:
        print(f"Error getting air quality data: {e}")
        return jsonify({"error": str(e), "nearest": None, "stations": []}), 500


@api.route("/traffic/zones", methods=["GET"])
def get_traffic_zones():
    """List all available traffic monitoring zones."""
    try:
        zones = traffic_service.get_all_zones()
        return jsonify({"zones": zones})
    except Exception as e:
        print(f"Error getting traffic zones: {e}")
        return jsonify({"error": str(e), "zones": []}), 500


@api.route("/static/processed/<path:filename>")
def serve_processed_media(filename):
    """Serve processed media files with proper headers for browser playback."""
    file_path = PROCESSED_DIR / filename

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return jsonify({"error": "File not found"}), 404

    # Determine content type based on extension
    ext = file_path.suffix.lower()
    content_types = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }

    content_type = content_types.get(ext, "application/octet-stream")

    print(f"Serving file: {file_path} with type: {content_type}")

    response = send_from_directory(str(PROCESSED_DIR), filename, mimetype=content_type)

    # Add headers for better video streaming support
    if ext in [".mp4", ".webm", ".avi", ".mov"]:
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Cache-Control"] = "public, max-age=3600"
        response.headers["Access-Control-Allow-Origin"] = "*"

    return response


# ==================== CHAT ENDPOINTS ====================


@api.route("/chat", methods=["POST"])
def chat():
    """
    Chat endpoint for traffic law Q&A.

    Request body:
    {
        "message": "Phạt vượt đèn đỏ bao nhiêu?",
        "session_id": "optional-session-id",
        "chat_history": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }

    Response:
    {
        "success": true,
        "data": {
            "content": "Theo Nghị định 168/2024...",
            "is_ai_generated": true,
            "topic_valid": true,
            "sources": [...],
            "category": "traffic_violation",
            "confidence": 0.85
        }
    }
    """
    try:
        # Parse request body
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        # Create ChatRequest from data
        chat_request = ChatRequest.from_dict(data)

        # Validate request
        is_valid, error = chat_request.validate()
        if not is_valid:
            return jsonify({"success": False, "error": error}), 400

        # Process message through chat service
        response = chat_service.process_message_sync(chat_request)

        return jsonify({"success": True, "data": response.to_dict()})

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api.route("/chat/validate", methods=["POST"])
def validate_topic():
    """
    Validate if a message is traffic-related (without calling LLM).
    Useful for frontend to show immediate feedback.

    Request body:
    {
        "message": "Hôm nay thời tiết thế nào?"
    }

    Response:
    {
        "success": true,
        "data": {
            "is_valid": false,
            "category": "off_topic",
            "confidence": 0.8,
            "reason": "Off-topic keywords detected"
        }
    }
    """
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"success": False, "error": "Message is required"}), 400

        message = data.get("message", "").strip()
        if not message:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400

        # Validate topic
        from app.validators.topic_validator import TopicValidator

        validator = TopicValidator()
        result = validator.validate(message)

        return jsonify(
            {
                "success": True,
                "data": {
                    "is_valid": result.is_valid,
                    "category": result.category.value,
                    "confidence": result.confidence,
                    "reason": result.reason,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error in validate endpoint: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500


@api.route("/chat/search", methods=["POST"])
def search_knowledge():
    """
    Search the traffic law knowledge base directly.

    Request body:
    {
        "query": "vượt đèn đỏ",
        "intent": "traffic_violation" (optional)
    }

    Response:
    {
        "success": true,
        "data": {
            "violations": [...],
            "faq": [...],
            "gplx": [...],
            "has_results": true
        }
    }
    """
    try:
        data = request.get_json()
        if not data or "query" not in data:
            return jsonify({"success": False, "error": "Query is required"}), 400

        query = data.get("query", "").strip()
        intent = data.get("intent")

        if not query:
            return jsonify({"success": False, "error": "Query cannot be empty"}), 400

        # Search knowledge base
        from app.knowledge.traffic_law_kb import traffic_law_kb

        results = traffic_law_kb.search(query, intent=intent)

        return jsonify({"success": True, "data": results})

    except Exception as e:
        logger.error(f"Error in search endpoint: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500
