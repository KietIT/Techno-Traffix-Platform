import json
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import DATA_DIR

POSTS_FILE = DATA_DIR / "posts.json"
_lock = threading.Lock()

# ==================== CONTENT MODERATION ====================

SENSITIVE_KEYWORDS = [
    # Profanity / vulgar
    "địt", "đụ", "đéo", "đĩ", "điếm", "lồn", "buồi", "cặc", "dái",
    "đm", "đcm", "vcl", "vl", "clgt", "dmm", "vkl", "cc",
    "ngu", "khốn nạn", "mất dạy", "đồ chó", "con chó", "thằng chó",
    "óc chó", "ngu như chó", "đồ ngu", "thằng ngu", "con ngu",
    # Hate speech
    "giết", "chém", "đâm chết", "bắn chết", "thiêu sống",
    "diệt chủng", "kỳ thị", "phân biệt chủng tộc",
    # Sexually explicit
    "sex", "khiêu dâm", "porn", "nude", "xxx",
    "quan hệ tình dục", "làm tình",
    # Politically sensitive
    "lật đổ", "phản động", "chống phá nhà nước",
    "biểu tình", "bạo loạn",
]

TRAFFIC_COMMUNITY_KEYWORDS = [
    # Vehicles
    "xe", "ô tô", "xe máy", "xe tải", "xe buýt", "xe khách", "xe đạp",
    "xe ba gác", "xe cứu thương", "xe cứu hỏa", "xe cộ", "xe hơi",
    "mô tô", "xe container", "xe bồn", "xe ben", "xe đầu kéo",
    # Traffic concepts
    "giao thông", "đường", "ngã tư", "ngã ba", "ngã năm",
    "đèn đỏ", "đèn xanh", "đèn vàng", "đèn giao thông", "đèn tín hiệu",
    "vạch kẻ đường", "biển báo", "biển cấm", "tín hiệu",
    "tắc đường", "kẹt xe", "ùn tắc", "tắc nghẽn", "ách tắc",
    "tai nạn", "va chạm", "đâm", "lật xe", "cháy xe",
    "vi phạm", "phạt", "lỗi", "nồng độ cồn", "tốc độ",
    "vượt đèn đỏ", "lấn làn", "đi ngược chiều", "quá tốc độ",
    # Infrastructure
    "cầu", "hầm", "cao tốc", "quốc lộ", "tỉnh lộ", "đường cao tốc",
    "đường phố", "đường nội thành", "làn đường", "vỉa hè",
    "bùng binh", "vòng xuyến", "nút giao", "cầu vượt", "hầm chui",
    "trạm thu phí", "BOT", "đường sắt", "ga tàu",
    # Locations (common Vietnamese roads/cities)
    "quốc lộ 1", "quốc lộ 14", "đại lộ", "TP.HCM", "Hà Nội",
    "Đà Nẵng", "Buôn Ma Thuột", "Sài Gòn", "đường Nguyễn",
    "đường Lê", "đường Trần", "đường Phạm", "đường Võ",
    # Driving / commute
    "lái xe", "tài xế", "lái", "chạy xe", "đi xe", "dừng xe",
    "đỗ xe", "bãi đỗ", "bến xe", "ga", "sân bay",
    "GPLX", "giấy phép lái xe", "bằng lái", "đăng kiểm", "đăng ký xe",
    "bảo hiểm xe", "CSGT", "cảnh sát giao thông", "thanh tra",
    # Weather-traffic
    "mưa", "ngập", "lũ", "sạt lở", "sụt lún",
    "trơn trượt", "sương mù", "tầm nhìn",
    # Road conditions
    "ổ gà", "ổ voi", "đường xấu", "đường hỏng", "đường sửa",
    "công trình", "rào chắn", "phân luồng",
]

# Pre-compile regex for sensitive keywords (word boundary matching)
_sensitive_pattern = re.compile(
    r'(?:' + '|'.join(re.escape(kw) for kw in SENSITIVE_KEYWORDS) + r')',
    re.IGNORECASE
)


def validate_post_content(content):
    """Validate post content for moderation.

    Returns (is_valid, error_message).
    """
    text = content.lower().strip()

    # Check sensitive content
    if _sensitive_pattern.search(text):
        return False, "Nội dung chứa từ ngữ không phù hợp. Vui lòng chỉnh sửa và thử lại."

    # Check traffic relevance
    has_traffic_keyword = any(kw in text for kw in TRAFFIC_COMMUNITY_KEYWORDS)
    if not has_traffic_keyword:
        return False, "Nội dung không liên quan đến giao thông. Cộng đồng này chỉ dành cho các chủ đề về giao thông, đường xá và phương tiện."

    return True, ""


REPORT_THRESHOLD = 3


def _read_posts():
    """Read posts from JSON file (must hold _lock)."""
    if not POSTS_FILE.exists():
        return {"posts": []}
    with open(POSTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_posts(data):
    """Write posts to JSON file (must hold _lock)."""
    POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_posts(page=1, per_page=20, session_id=None):
    """Return paginated posts, newest first. Hidden posts are excluded."""
    with _lock:
        data = _read_posts()
    posts = [p for p in data["posts"] if not p.get("hidden", False)]
    posts = sorted(posts, key=lambda p: p["created_at"], reverse=True)
    total = len(posts)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "posts": posts[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_more": end < total,
    }


def create_post(author_name, content, images=None, location=None):
    """Create a new post and return it."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    post = {
        "id": f"post_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "author_name": author_name,
        "author_avatar_color": _random_color(),
        "content": content,
        "images": images or [],
        "location": location or "",
        "created_at": now,
        "likes": 0,
        "dislikes": 0,
        "liked_by": [],
        "disliked_by": [],
        "comments": [],
        "reports": 0,
        "reported_by": [],
        "hidden": False,
    }
    with _lock:
        data = _read_posts()
        data["posts"].append(post)
        _write_posts(data)
    return post


def toggle_like(post_id, session_id):
    """Toggle like for a session. Removes dislike if present."""
    with _lock:
        data = _read_posts()
        post = _find_post(data, post_id)
        if not post:
            return None

        if session_id in post["liked_by"]:
            post["liked_by"].remove(session_id)
            post["likes"] = max(0, post["likes"] - 1)
        else:
            post["liked_by"].append(session_id)
            post["likes"] += 1
            if session_id in post["disliked_by"]:
                post["disliked_by"].remove(session_id)
                post["dislikes"] = max(0, post["dislikes"] - 1)

        _write_posts(data)
        return post


def toggle_dislike(post_id, session_id):
    """Toggle dislike for a session. Removes like if present."""
    with _lock:
        data = _read_posts()
        post = _find_post(data, post_id)
        if not post:
            return None

        if session_id in post["disliked_by"]:
            post["disliked_by"].remove(session_id)
            post["dislikes"] = max(0, post["dislikes"] - 1)
        else:
            post["disliked_by"].append(session_id)
            post["dislikes"] += 1
            if session_id in post["liked_by"]:
                post["liked_by"].remove(session_id)
                post["likes"] = max(0, post["likes"] - 1)

        _write_posts(data)
        return post


def add_comment(post_id, author_name, content):
    """Add a comment to a post."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    comment = {
        "id": f"cmt_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}",
        "author_name": author_name,
        "author_avatar_color": _random_color(),
        "content": content,
        "created_at": now,
    }
    with _lock:
        data = _read_posts()
        post = _find_post(data, post_id)
        if not post:
            return None
        post["comments"].append(comment)
        _write_posts(data)
    return comment


def report_post(post_id, session_id, reason=""):
    """Toggle report for a post. Returns (post, action) tuple.
    
    action is "reported", "unreported", or an error message.
    """
    with _lock:
        data = _read_posts()
        post = _find_post(data, post_id)
        if not post:
            return None, "Bài viết không tồn tại"

        reported_by = post.get("reported_by", [])
        
        if session_id in reported_by:
            # Toggle off - unreport
            reported_by.remove(session_id)
            post["reported_by"] = reported_by
            post["reports"] = max(0, post.get("reports", 0) - 1)
            _write_posts(data)
            return post, "unreported"

        # Toggle on - report
        reported_by.append(session_id)
        post["reported_by"] = reported_by
        post["reports"] = post.get("reports", 0) + 1

        if post["reports"] >= REPORT_THRESHOLD:
            post["hidden"] = True

        _write_posts(data)
        return post, "reported"


def _find_post(data, post_id):
    for post in data["posts"]:
        if post["id"] == post_id:
            return post
    return None


_COLORS = [
    "#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6",
    "#ec4899", "#06b6d4", "#14b8a6", "#f97316", "#6366f1",
]


def _random_color():
    import random
    return random.choice(_COLORS)
