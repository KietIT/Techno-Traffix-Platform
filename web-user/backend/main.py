# Techno Traffix Backend - Main Entry Point
# Serves both API and Frontend on the same port

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file immediately
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from flask import Flask, send_from_directory
from flask_cors import CORS

from app.api.routes import api
from app.api.community_routes import community_api
from app.core.config import HOST, PORT, DEBUG, UPLOADS_DIR

# Path to frontend folder
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


def create_app():
    """Application factory."""
    app = Flask(__name__, static_folder=None)

    # Enable CORS for all routes
    CORS(
        app,
        resources={r"/*": {"origins": "*"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    # Register API blueprints
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(community_api, url_prefix="/api")

    # Serve uploaded files
    @app.route("/api/static/uploads/<path:filename>")
    def serve_upload(filename):
        return send_from_directory(str(UPLOADS_DIR), filename)

    # Serve frontend index.html at root
    @app.route("/")
    def index():
        """Serve main index.html"""
        return send_from_directory(str(FRONTEND_DIR), "index.html")

    # Serve CSS files
    @app.route("/css/<path:filename>")
    def serve_css(filename):
        """Serve CSS files"""
        return send_from_directory(str(FRONTEND_DIR / "css"), filename)

    # Serve JS files
    @app.route("/js/<path:filename>")
    def serve_js(filename):
        """Serve JavaScript files"""
        js_path = FRONTEND_DIR / "js"
        return send_from_directory(str(js_path), filename, mimetype="application/javascript")

    # Serve assets (images, fonts, etc.)
    @app.route("/assets/<path:filename>")
    def serve_assets(filename):
        """Serve asset files"""
        return send_from_directory(str(FRONTEND_DIR / "assets"), filename)

    # Catch-all for other frontend files
    @app.route("/<path:filename>")
    def serve_frontend(filename):
        """Serve other frontend static files"""
        file_path = FRONTEND_DIR / filename
        if file_path.exists() and file_path.is_file():
            # Determine mimetype
            if filename.endswith(".js"):
                return send_from_directory(str(FRONTEND_DIR), filename, mimetype="application/javascript")
            elif filename.endswith(".css"):
                return send_from_directory(str(FRONTEND_DIR), filename, mimetype="text/css")
            return send_from_directory(str(FRONTEND_DIR), filename)
        # If file not found, return index.html for SPA routing
        return send_from_directory(str(FRONTEND_DIR), "index.html")

    return app


if __name__ == "__main__":
    print("=" * 60)
    print("  TECHNO TRAFFIX - AI Traffic Monitoring System")
    print("=" * 60)

    app = create_app()

    print(f"\n  Server: http://127.0.0.1:{PORT}")
    print(f"\n  Open this URL in your browser to use the application")
    print("\n" + "=" * 60)
    print("  Press Ctrl+C to stop the server")
    print("=" * 60 + "\n")

    app.run(debug=DEBUG, host=HOST, port=PORT)
