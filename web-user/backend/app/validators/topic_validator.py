"""
Topic Validator - Validates if user message is related to Vietnamese traffic law.
Filters out off-topic questions BEFORE sending to LLM to save costs and maintain focus.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum


class TopicCategory(Enum):
    """Categories of valid traffic-related topics."""

    TRAFFIC_VIOLATION = "traffic_violation"
    DRIVER_LICENSE = "driver_license"
    SPEED_LIMIT = "speed_limit"
    ALCOHOL_REGULATION = "alcohol_regulation"
    TRAFFIC_RULES = "traffic_rules"
    TRAFFIC_SIGNS = "traffic_signs"
    VEHICLE_REGISTRATION = "vehicle_registration"
    INSURANCE = "insurance"
    ACCIDENT = "accident"
    TRAFFIC_STATUS = "traffic_status"
    GREETING = "greeting"
    OFF_TOPIC = "off_topic"


@dataclass
class ValidationResult:
    """Result of topic validation."""

    is_valid: bool
    confidence: float  # 0.0 to 1.0
    category: TopicCategory
    reason: str
    suggested_response: Optional[str] = None


class TopicValidator:
    """
    Multi-layer topic validator for Vietnamese traffic law chatbot.

    Validation Strategy:
    1. Check for greetings (always valid, but handled differently)
    2. Check blacklist keywords (definitely off-topic)
    3. Check whitelist keywords (definitely on-topic)
    4. Calculate relevance score for edge cases
    """

    # Greeting patterns - always valid but handled separately
    GREETING_PATTERNS = [
        r"^(xin\s*)?chào",
        r"^hello",
        r"^hi\b",
        r"^hey\b",
        r"^chào\s*bạn",
        r"^chào\s*bot",
        r"^bạn\s*(là\s*)?ai",
        r"^giới\s*thiệu",
        r"^cảm\s*ơn",
        r"^thank",
        r"^tạm\s*biệt",
        r"^bye",
    ]

    # Whitelist: Traffic-related keywords (Vietnamese)
    TRAFFIC_KEYWORDS = [
        # Violations & Penalties
        "vi phạm",
        "phạt",
        "xử phạt",
        "mức phạt",
        "tiền phạt",
        "bị phạt",
        "nghị định",
        "nđ 168",
        "nd 168",
        "168/2024",
        # Vehicles
        "xe máy",
        "xe may",
        "ô tô",
        "oto",
        "xe hơi",
        "xe con",
        "mô tô",
        "moto",
        "xe tải",
        "xe khách",
        "xe buýt",
        "xe bus",
        "xe đạp",
        "xe điện",
        "phương tiện",
        "xe cơ giới",
        # Driver's License
        "bằng lái",
        "bang lai",
        "gplx",
        "giấy phép lái xe",
        "giay phep lai xe",
        "hạng a1",
        "hạng a2",
        "hạng b1",
        "hạng b2",
        "hạng c",
        "hạng d",
        "hạng e",
        "thi bằng",
        "đổi bằng",
        "cấp bằng",
        "gia hạn bằng",
        # Points System
        "điểm",
        "trừ điểm",
        "hệ thống điểm",
        "12 điểm",
        "tước bằng",
        "tước gplx",
        # Speed
        "tốc độ",
        "giới hạn tốc độ",
        "km/h",
        "kmh",
        "chạy nhanh",
        "quá tốc độ",
        "vượt tốc độ",
        # Alcohol
        "nồng độ cồn",
        "nong do con",
        "cồn",
        "độ cồn",
        "rượu bia",
        "uống rượu",
        "say rượu",
        "đo nồng độ",
        "thổi nồng độ",
        "mg/l",
        "đã uống",
        # Traffic Rules
        "giao thông",
        "luật giao thông",
        "luật gtđb",
        "an toàn giao thông",
        "atgt",
        "quy tắc",
        "quy định",
        # Traffic Signs & Signals
        "đèn đỏ",
        "đèn xanh",
        "đèn vàng",
        "đèn giao thông",
        "biển báo",
        "biển cấm",
        "biển hiệu",
        "vạch kẻ đường",
        # Road Types
        "đường cao tốc",
        "cao tốc",
        "đường quốc lộ",
        "quốc lộ",
        "đường tỉnh",
        "đường nội thành",
        "đô thị",
        "ngoài đô thị",
        # Actions
        "vượt đèn đỏ",
        "chạy ngược chiều",
        "lấn làn",
        "không đội mũ",
        "mũ bảo hiểm",
        "không thắt dây",
        "dây an toàn",
        "đi sai làn",
        "chở quá số người",
        "quá tải",
        "không có bằng",
        "hết hạn bằng",
        "đậu xe",
        "đỗ xe",
        "dừng xe",
        "quay đầu",
        # Documents
        "giấy tờ xe",
        "đăng ký xe",
        "đăng kiểm",
        "bảo hiểm xe",
        "cavet",
        "cà vẹt",
        # Accident
        "tai nạn",
        "va chạm",
        "đâm xe",
        "tông xe",
        # Questions about traffic
        "lái xe",
        "điều khiển xe",
        "chở người",
        "chở hàng",
        # Traffic status / congestion queries
        "ùn tắc",
        "tắc đường",
        "kẹt xe",
        "đông xe",
        "tình hình giao thông",
        "đường nào tắc",
        "tắc nghẽn",
        "mật độ giao thông",
        "đường đông",
        "đang tắc",
        "bị tắc",
        "đang kẹt",
        "bị kẹt",
        "đang đông",
        "chỗ nào tắc",
        "nào đang tắc",
        # Location-based queries
        "vị trí của tôi",
        "chỗ tôi",
        "nơi tôi",
        "khu vực của tôi",
        "gần tôi",
        "quanh tôi",
        "xung quanh tôi",
        "vị trí hiện tại",
    ]

    # Blacklist: Definitely off-topic keywords
    OFF_TOPIC_KEYWORDS = [
        # Technology (not traffic)
        "lập trình",
        "code",
        "coding",
        "python",
        "javascript",
        "java",
        "website",
        "app",
        "ứng dụng",
        "phần mềm",
        "software",
        "máy tính",
        "computer",
        "laptop",
        "điện thoại",
        "iphone",
        "android",
        "ai",
        "machine learning",
        "chatgpt",
        "gpt",
        # Entertainment
        "phim",
        "movie",
        "game",
        "trò chơi",
        "nhạc",
        "music",
        "ca sĩ",
        "diễn viên",
        "youtube",
        "tiktok",
        "facebook",
        "instagram",
        # Food
        "nấu ăn",
        "món ăn",
        "thức ăn",
        "nhà hàng",
        "quán ăn",
        "đồ ăn",
        "recipe",
        "công thức nấu",
        "phở",
        "bún",
        "cơm",
        "nấu",
        # Relationships
        "tình yêu",
        "người yêu",
        "bạn gái",
        "bạn trai",
        "hẹn hò",
        "kết hôn",
        "ly hôn",
        "gia đình",
        "tán gái",
        "tán trai",
        "crush",
        # Sports (not traffic)
        "bóng đá",
        "bóng rổ",
        "tennis",
        "cầu lông",
        "thể thao",
        "world cup",
        "euro",
        "olympic",
        # Finance (not traffic-related)
        "crypto",
        "bitcoin",
        "chứng khoán",
        "cổ phiếu",
        "đầu tư",
        "forex",
        "ngân hàng",
        "vay tiền",
        # Health (general)
        "bệnh",
        "thuốc",
        "bác sĩ",
        "bệnh viện",
        "sức khỏe",
        "covid",
        "vaccine",
        "tiêm",
        # Weather
        "thời tiết",
        "mưa",
        "nắng",
        "bão",
        "nhiệt độ",
        # Politics (sensitive)
        "chính trị",
        "bầu cử",
        "đảng",
        "chính phủ",
        # Other
        "học tiếng anh",
        "du lịch",
        "khách sạn",
        "vé máy bay",
        "mua sắm",
        "shopping",
        "quần áo",
        "giày dép",
        "làm đẹp",
        "trang điểm",
        "skincare",
    ]

    # Rejection response templates
    REJECTION_RESPONSES = {
        "default": """Xin lỗi, tôi là **TECHNO TRAFFIX** — trợ lý chuyên về Luật An toàn giao thông đường bộ Việt Nam.

Tôi chỉ có thể hỗ trợ các câu hỏi về:
- 🚗 Mức phạt vi phạm giao thông (Nghị định 168/2024)
- 📋 Quy định về Giấy phép lái xe (GPLX)
- 🚦 Quy tắc giao thông đường bộ
- 🍺 Quy định về nồng độ cồn
- ⚡ Tốc độ và biển báo giao thông

Bạn có câu hỏi gì về giao thông không? **TECHNO TRAFFIX** luôn sẵn sàng hỗ trợ!""",
        "greeting": """Xin chào! 👋

Tôi là **TECHNO TRAFFIX** — Trợ lý Luật An toàn giao thông đường bộ Việt Nam.

**TECHNO TRAFFIX** có thể giúp bạn:
- 📖 Tra cứu mức phạt vi phạm giao thông (theo NĐ 168/2024)
- 🪪 Thông tin về GPLX và hệ thống trừ điểm (từ 01/01/2025)
- 🚗 Quy định tốc độ, nồng độ cồn
- 🚦 Các quy tắc giao thông đường bộ khác

Hãy hỏi **TECHNO TRAFFIX** bất cứ điều gì về luật giao thông!""",
        "thanks": """Không có chi! 😊

**TECHNO TRAFFIX** luôn sẵn sàng hỗ trợ bạn. Nếu có thêm câu hỏi về luật giao thông, đừng ngại hỏi nhé!""",
        "goodbye": """Tạm biệt! 👋

**TECHNO TRAFFIX** chúc bạn lái xe an toàn! Nhớ tuân thủ luật giao thông nhé! 🚗✨""",
    }

    def __init__(self):
        """Initialize the validator with compiled patterns."""
        # Pre-compile greeting patterns for performance
        self._greeting_patterns = [
            re.compile(pattern, re.IGNORECASE | re.UNICODE) for pattern in self.GREETING_PATTERNS
        ]

        # Normalize keywords for faster lookup
        self._traffic_keywords = set(kw.lower() for kw in self.TRAFFIC_KEYWORDS)
        self._off_topic_keywords = set(kw.lower() for kw in self.OFF_TOPIC_KEYWORDS)

    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text for matching."""
        text = text.lower().strip()
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def _check_greeting(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if message is a greeting or common interaction.
        Returns (is_greeting, response_key)
        """
        text_lower = text.lower().strip()

        for pattern in self._greeting_patterns:
            if pattern.search(text_lower):
                # Determine response type
                if any(word in text_lower for word in ["cảm ơn", "thank", "cám ơn"]):
                    return True, "thanks"
                elif any(word in text_lower for word in ["tạm biệt", "bye", "goodbye"]):
                    return True, "goodbye"
                else:
                    return True, "greeting"

        return False, None

    def _count_keyword_matches(self, text: str, keywords: set) -> Tuple[int, List[str]]:
        """Count how many keywords from a set appear in the text."""
        text_normalized = self._normalize_text(text)
        matches = []

        for keyword in keywords:
            if keyword in text_normalized:
                matches.append(keyword)

        return len(matches), matches

    def _calculate_traffic_score(self, text: str) -> Tuple[float, List[str]]:
        """
        Calculate relevance score for traffic-related content.
        Returns (score 0-1, matched_keywords)
        """
        traffic_count, traffic_matches = self._count_keyword_matches(text, self._traffic_keywords)
        off_topic_count, _ = self._count_keyword_matches(text, self._off_topic_keywords)

        # If off-topic keywords dominate, lower the score
        if off_topic_count > 0 and traffic_count == 0:
            return 0.0, []

        # Calculate score based on keyword density
        if traffic_count == 0:
            return 0.0, []

        # More traffic keywords = higher confidence
        # Penalize if off-topic keywords present
        base_score = min(traffic_count * 0.25, 1.0)
        penalty = off_topic_count * 0.15

        final_score = max(0.0, min(1.0, base_score - penalty))

        return final_score, traffic_matches

    def _detect_category(self, text: str, matched_keywords: List[str]) -> TopicCategory:
        """Detect the specific traffic category based on keywords."""
        text_lower = text.lower()

        # Traffic status / congestion queries (check early – takes priority)
        if any(kw in text_lower for kw in [
            "ùn tắc", "tắc đường", "kẹt xe", "đông xe", "tình hình giao thông",
            "đường nào tắc", "tắc nghẽn", "mật độ giao thông", "đường đông",
            "đang tắc", "bị tắc", "đang kẹt", "bị kẹt", "đang đông",
            "chỗ nào tắc", "nào đang tắc",
            "vị trí của tôi", "chỗ tôi", "nơi tôi", "khu vực của tôi",
            "gần tôi", "quanh tôi", "xung quanh tôi", "vị trí hiện tại",
        ]):
            return TopicCategory.TRAFFIC_STATUS

        # Check specific categories
        if any(kw in text_lower for kw in ["nồng độ cồn", "rượu bia", "uống rượu", "say"]):
            return TopicCategory.ALCOHOL_REGULATION

        if any(kw in text_lower for kw in ["bằng lái", "gplx", "giấy phép lái", "hạng a", "hạng b", "hạng c"]):
            return TopicCategory.DRIVER_LICENSE

        if any(kw in text_lower for kw in ["tốc độ", "km/h", "chạy nhanh", "quá tốc"]):
            return TopicCategory.SPEED_LIMIT

        if any(kw in text_lower for kw in ["đèn đỏ", "biển báo", "vạch kẻ"]):
            return TopicCategory.TRAFFIC_SIGNS

        if any(kw in text_lower for kw in ["tai nạn", "va chạm", "đâm", "tông"]):
            return TopicCategory.ACCIDENT

        if any(kw in text_lower for kw in ["phạt", "vi phạm", "xử phạt", "mức phạt"]):
            return TopicCategory.TRAFFIC_VIOLATION

        if any(kw in text_lower for kw in ["đăng ký", "đăng kiểm", "bảo hiểm"]):
            return TopicCategory.VEHICLE_REGISTRATION

        # Default to general traffic rules
        return TopicCategory.TRAFFIC_RULES

    def validate(self, message: str) -> ValidationResult:
        """
        Validate if a message is related to Vietnamese traffic law.

        Args:
            message: User's input message

        Returns:
            ValidationResult with validation status and details
        """
        if not message or not message.strip():
            return ValidationResult(
                is_valid=False,
                confidence=1.0,
                category=TopicCategory.OFF_TOPIC,
                reason="Empty message",
                suggested_response="Bạn chưa nhập nội dung. Hãy hỏi tôi về luật giao thông nhé!",
            )

        text = message.strip()

        # Step 1: Check for greetings
        is_greeting, greeting_type = self._check_greeting(text)
        if is_greeting:
            return ValidationResult(
                is_valid=True,
                confidence=1.0,
                category=TopicCategory.GREETING,
                reason="Greeting detected",
                suggested_response=self.REJECTION_RESPONSES[greeting_type]
                if greeting_type
                else self.REJECTION_RESPONSES["greeting"],
            )

        # Step 2: Check for off-topic keywords first (blacklist)
        off_topic_count, off_topic_matches = self._count_keyword_matches(text, self._off_topic_keywords)
        traffic_score, traffic_matches = self._calculate_traffic_score(text)

        # If clearly off-topic (blacklist matches and no traffic keywords)
        if off_topic_count > 0 and traffic_score < 0.3:
            return ValidationResult(
                is_valid=False,
                confidence=min(off_topic_count * 0.3, 1.0),
                category=TopicCategory.OFF_TOPIC,
                reason=f"Off-topic keywords detected: {off_topic_matches[:3]}",
                suggested_response=self.REJECTION_RESPONSES["default"],
            )

        # Step 3: Check for traffic keywords (whitelist)
        if traffic_score >= 0.3:
            category = self._detect_category(text, traffic_matches)
            return ValidationResult(
                is_valid=True,
                confidence=traffic_score,
                category=category,
                reason=f"Traffic-related keywords found: {traffic_matches[:5]}",
            )

        # Step 4: Edge case - no clear indicators
        # For short messages without keywords, assume it might be a follow-up question
        # Let it through with low confidence (LLM will handle context)
        if len(text.split()) <= 5:
            return ValidationResult(
                is_valid=True,
                confidence=0.3,
                category=TopicCategory.TRAFFIC_RULES,
                reason="Short message, might be follow-up question",
            )

        # Default: Reject unclear long messages
        return ValidationResult(
            is_valid=False,
            confidence=0.5,
            category=TopicCategory.OFF_TOPIC,
            reason="No traffic-related content detected",
            suggested_response=self.REJECTION_RESPONSES["default"],
        )

    def get_intent(self, validation_result: ValidationResult) -> Optional[str]:
        """
        Convert validation category to intent string for RAG search.
        """
        category_to_intent = {
            TopicCategory.TRAFFIC_VIOLATION: "traffic_violation",
            TopicCategory.DRIVER_LICENSE: "license_query",
            TopicCategory.SPEED_LIMIT: "speed_limit",
            TopicCategory.ALCOHOL_REGULATION: "alcohol_regulation",
            TopicCategory.TRAFFIC_STATUS: "traffic_status",
            TopicCategory.TRAFFIC_RULES: None,  # General search
            TopicCategory.TRAFFIC_SIGNS: None,
            TopicCategory.VEHICLE_REGISTRATION: None,
            TopicCategory.INSURANCE: None,
            TopicCategory.ACCIDENT: None,
        }
        return category_to_intent.get(validation_result.category)
