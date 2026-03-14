import os
import uuid
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from app.core.config import UPLOADS_DIR
from app.services import community_service

community_api = Blueprint("community_api", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_IMAGES = 4


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@community_api.route("/posts", methods=["GET"])
def get_posts():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    session_id = request.args.get("session_id", "")
    result = community_service.get_posts(page, per_page, session_id)
    return jsonify(result)


@community_api.route("/posts", methods=["POST"])
def create_post():
    author_name = request.form.get("author_name", "").strip()
    content = request.form.get("content", "").strip()
    location = request.form.get("location", "").strip()

    if not content:
        return jsonify({"error": "Nội dung không được để trống"}), 400
    if not author_name:
        author_name = "Người dùng ẩn danh"

    # Content moderation
    is_valid, error_msg = community_service.validate_post_content(content)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    image_urls = []
    files = request.files.getlist("images")
    for f in files[:MAX_IMAGES]:
        if f and f.filename and _allowed_file(f.filename):
            ext = f.filename.rsplit(".", 1)[1].lower()
            filename = f"img_{uuid.uuid4().hex[:12]}.{ext}"
            f.save(str(UPLOADS_DIR / filename))
            image_urls.append(f"/api/static/uploads/{filename}")

    post = community_service.create_post(author_name, content, image_urls, location)
    return jsonify(post), 201


@community_api.route("/posts/<post_id>/like", methods=["POST"])
def like_post(post_id):
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    post = community_service.toggle_like(post_id, session_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    return jsonify(post)


@community_api.route("/posts/<post_id>/dislike", methods=["POST"])
def dislike_post(post_id):
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    post = community_service.toggle_dislike(post_id, session_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404
    return jsonify(post)


@community_api.route("/posts/<post_id>/comments", methods=["POST"])
def add_comment(post_id):
    data = request.get_json(silent=True) or {}
    author_name = data.get("author_name", "").strip()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Nội dung bình luận không được để trống"}), 400
    if not author_name:
        author_name = "Người dùng ẩn danh"
    comment = community_service.add_comment(post_id, author_name, content)
    if not comment:
        return jsonify({"error": "Post not found"}), 404
    return jsonify(comment), 201


@community_api.route("/posts/<post_id>/report", methods=["POST"])
def report_post(post_id):
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    reason = data.get("reason", "")
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    post, action = community_service.report_post(post_id, session_id, reason)
    if not post:
        return jsonify({"error": action}), 404
    
    if action == "unreported":
        return jsonify({
            "message": "Đã hủy báo cáo bài viết",
            "action": "unreported",
            "hidden": post.get("hidden", False),
            "reported_by": post.get("reported_by", [])
        })
    
    return jsonify({
        "message": "Đã báo cáo bài viết",
        "action": "reported",
        "hidden": post.get("hidden", False),
        "reported_by": post.get("reported_by", [])
    })
