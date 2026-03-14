"""
Traffic Law Knowledge Base - Vietnamese Traffic Law RAG System
Provides semantic search and retrieval for traffic violation queries
Based on Nghị định 168/2024/NĐ-CP and Luật GTĐB 2024
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Represents a search result from the knowledge base."""

    id: str
    content: str
    category: str
    relevance_score: float
    source: str
    metadata: Dict[str, Any]


class TrafficLawKB:
    """
    Knowledge Base for Vietnamese Traffic Law.
    Provides keyword-based search with relevance scoring.
    """

    def __init__(self):
        self.data_dir = Path(__file__).parent / "data"
        self.violations_data: Dict[str, Any] = {}
        self.faq_data: List[Dict] = []
        self.gplx_data: Dict[str, Any] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load all knowledge base data from JSON files."""
        # Load violations data (NĐ 168/2024)
        nd_168_path = self.data_dir / "nd_168_2024.json"
        if nd_168_path.exists():
            with open(nd_168_path, "r", encoding="utf-8") as f:
                self.violations_data = json.load(f)

        # Load FAQ data
        faq_path = self.data_dir / "faq.json"
        if faq_path.exists():
            with open(faq_path, "r", encoding="utf-8") as f:
                faq_content = json.load(f)
                self.faq_data = faq_content.get("faqs", [])

        # Load GPLX data
        gplx_path = self.data_dir / "gplx.json"
        if gplx_path.exists():
            with open(gplx_path, "r", encoding="utf-8") as f:
                self.gplx_data = json.load(f)

    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text for matching."""
        text = text.lower().strip()
        # Common Vietnamese synonyms/variations
        replacements = {
            "ô tô": "oto",
            "xe hơi": "oto",
            "xe con": "oto",
            "xe máy": "xe_may",
            "mô tô": "xe_may",
            "xe gắn máy": "xe_may",
            "gplx": "giấy phép lái xe",
            "bằng lái": "giấy phép lái xe",
            "bang lai": "giấy phép lái xe",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _calculate_relevance(self, query: str, keywords: List[str], content: str) -> float:
        """Calculate relevance score based on keyword matching."""
        query_normalized = self._normalize_text(query)
        score = 0.0

        # Check keyword matches (higher weight)
        for keyword in keywords:
            keyword_normalized = self._normalize_text(keyword)
            if keyword_normalized in query_normalized:
                score += 2.0
            elif any(word in query_normalized for word in keyword_normalized.split()):
                score += 1.0

        # Check content matches (lower weight)
        content_normalized = self._normalize_text(content)
        query_words = query_normalized.split()
        for word in query_words:
            if len(word) > 2 and word in content_normalized:
                score += 0.5

        return min(score, 10.0)  # Cap at 10.0

    def search_violations(self, query: str, vehicle_type: Optional[str] = None, top_k: int = 5) -> List[SearchResult]:
        """
        Search for traffic violations matching the query.

        Args:
            query: User's query text
            vehicle_type: Optional filter for 'oto' or 'xe_may'
            top_k: Number of top results to return

        Returns:
            List of SearchResult objects sorted by relevance
        """
        results = []

        if not self.violations_data.get("categories"):
            return results

        for category in self.violations_data["categories"]:
            for violation in category.get("violations", []):
                # Filter by vehicle type if specified
                if vehicle_type and violation.get("vehicle_type") not in [vehicle_type, "chung"]:
                    continue

                keywords = violation.get("keywords", [])
                content = violation.get("violation", "")
                relevance = self._calculate_relevance(query, keywords, content)

                if relevance > 0:
                    # Format fine amount
                    fine_min = violation.get("fine_min", 0)
                    fine_max = violation.get("fine_max", 0)
                    fine_str = f"{fine_min:,}đ - {fine_max:,}đ".replace(",", ".")

                    # Format license suspension
                    suspension = violation.get("license_suspension_months")
                    suspension_str = ""
                    if suspension:
                        suspension_str = f"Tước GPLX {suspension[0]}-{suspension[1]} tháng"

                    # Format points deducted
                    points = violation.get("points_deducted", 0)
                    points_str = f"Trừ {points} điểm GPLX" if points > 0 else ""

                    result = SearchResult(
                        id=violation.get("id", ""),
                        content=violation.get("violation", ""),
                        category=category.get("name", ""),
                        relevance_score=relevance,
                        source=f"Nghị định 168/2024, {category.get('article', '')}",
                        metadata={
                            "vehicle_type": violation.get("vehicle_type_display", ""),
                            "fine": fine_str,
                            "license_suspension": suspension_str,
                            "points_deducted": points_str,
                            "fine_min": fine_min,
                            "fine_max": fine_max,
                        },
                    )
                    results.append(result)

        # Sort by relevance and return top_k
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def search_faq(self, query: str, top_k: int = 3) -> List[SearchResult]:
        """Search FAQ database for matching questions."""
        results = []

        for faq in self.faq_data:
            keywords = faq.get("keywords", [])
            question = faq.get("question", "")
            answer = faq.get("answer", "")

            relevance = self._calculate_relevance(query, keywords, question + " " + answer)

            if relevance > 0:
                result = SearchResult(
                    id=faq.get("id", ""),
                    content=answer,
                    category="FAQ",
                    relevance_score=relevance,
                    source="Câu hỏi thường gặp về Luật ATGT",
                    metadata={
                        "question": question,
                        "category": faq.get("category", ""),
                    },
                )
                results.append(result)

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def search_gplx(self, query: str) -> List[SearchResult]:
        """Search for driver's license information."""
        results = []

        if not self.gplx_data.get("license_classes"):
            return results

        for license_class in self.gplx_data["license_classes"]:
            keywords = license_class.get("keywords", [])
            description = license_class.get("description", "")

            relevance = self._calculate_relevance(query, keywords, description)

            if relevance > 0:
                vehicles = ", ".join(license_class.get("vehicles_allowed", []))
                note = license_class.get("note", "")

                content = f"Bằng {license_class['class']}: {description}. Được phép lái: {vehicles}."
                if note:
                    content += f" Lưu ý: {note}"

                result = SearchResult(
                    id=f"gplx-{license_class['class']}",
                    content=content,
                    category="Giấy phép lái xe",
                    relevance_score=relevance,
                    source="Quy định về GPLX Việt Nam",
                    metadata={
                        "class": license_class["class"],
                        "age_requirement": license_class.get("age_requirement"),
                        "validity_years": license_class.get("validity_years"),
                    },
                )
                results.append(result)

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results

    def search_speed_limits(self, query: str) -> Optional[Dict[str, Any]]:
        """Get speed limit information if query is about speed."""
        speed_keywords = ["tốc độ", "giới hạn", "nhanh", "chạy bao nhiêu", "km/h", "kmh"]
        query_lower = query.lower()

        if not any(kw in query_lower for kw in speed_keywords):
            return None

        return self.violations_data.get("speed_limits", {})

    def get_point_system_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the license point deduction system."""
        return self.violations_data.get("license_point_system", {})

    def search(self, query: str, intent: Optional[str] = None) -> Dict[str, Any]:
        """
        Main search method - combines all knowledge sources.

        Args:
            query: User's query text
            intent: Optional intent classification to narrow search

        Returns:
            Dictionary with search results from all sources
        """
        results = {
            "violations": [],
            "faq": [],
            "gplx": [],
            "speed_limits": None,
            "point_system": None,
            "has_results": False,
        }

        # Detect vehicle type from query
        query_lower = query.lower()
        vehicle_type = None
        if any(kw in query_lower for kw in ["ô tô", "oto", "xe hơi", "xe con"]):
            vehicle_type = "oto"
        elif any(kw in query_lower for kw in ["xe máy", "xe may", "mô tô", "xe gắn máy"]):
            vehicle_type = "xe_may"

        # Search violations
        if intent in [None, "traffic_violation", "alcohol_regulation", "speed_limit"]:
            violations = self.search_violations(query, vehicle_type)
            results["violations"] = [
                {
                    "id": v.id,
                    "content": v.content,
                    "category": v.category,
                    "source": v.source,
                    "score": v.relevance_score,
                    **v.metadata,
                }
                for v in violations
            ]

        # Search FAQ
        faq_results = self.search_faq(query)
        results["faq"] = [
            {
                "id": f.id,
                "question": f.metadata.get("question", ""),
                "answer": f.content,
                "score": f.relevance_score,
            }
            for f in faq_results
        ]

        # Search GPLX if relevant
        if intent in [None, "license_query"] or any(kw in query_lower for kw in ["bằng", "gplx", "giấy phép"]):
            gplx_results = self.search_gplx(query)
            results["gplx"] = [
                {
                    "id": g.id,
                    "content": g.content,
                    "class": g.metadata.get("class"),
                    "score": g.relevance_score,
                }
                for g in gplx_results
            ]

        # Get speed limits if relevant
        speed_info = self.search_speed_limits(query)
        if speed_info:
            results["speed_limits"] = speed_info

        # Get point system if relevant
        if any(kw in query_lower for kw in ["điểm", "trừ điểm", "hệ thống điểm"]):
            results["point_system"] = self.get_point_system_info()

        # Check if any results found
        results["has_results"] = bool(
            results["violations"]
            or results["faq"]
            or results["gplx"]
            or results["speed_limits"]
            or results["point_system"]
        )

        return results

    def format_rag_context(self, search_results: Dict[str, Any]) -> str:
        """
        Format search results into context string for LLM prompt.

        Args:
            search_results: Results from search() method

        Returns:
            Formatted string for RAG context injection
        """
        context_parts = []

        # Format violations
        if search_results.get("violations"):
            context_parts.append("## THÔNG TIN VI PHẠM LIÊN QUAN (NĐ 168/2024):")
            for v in search_results["violations"][:3]:  # Top 3
                context_parts.append(f"- **{v['category']}** ({v['vehicle_type']})")
                context_parts.append(f"  Vi phạm: {v['content']}")
                context_parts.append(f"  Mức phạt: {v['fine']}")
                if v.get("license_suspension"):
                    context_parts.append(f"  {v['license_suspension']}")
                if v.get("points_deducted"):
                    context_parts.append(f"  {v['points_deducted']}")
                context_parts.append(f"  Nguồn: {v['source']}")
                context_parts.append("")

        # Format FAQ
        if search_results.get("faq"):
            context_parts.append("## CÂU HỎI THƯỜNG GẶP LIÊN QUAN:")
            for f in search_results["faq"][:2]:  # Top 2
                context_parts.append(f"- Hỏi: {f['question']}")
                context_parts.append(f"  Đáp: {f['answer']}")
                context_parts.append("")

        # Format GPLX
        if search_results.get("gplx"):
            context_parts.append("## THÔNG TIN GPLX:")
            for g in search_results["gplx"][:2]:
                context_parts.append(f"- {g['content']}")
                context_parts.append("")

        # Format speed limits
        if search_results.get("speed_limits"):
            sl = search_results["speed_limits"]
            context_parts.append("## QUY ĐỊNH TỐC ĐỘ (Luật GTĐB 2024):")
            context_parts.append("**Trong đô thị:**")
            if sl.get("urban"):
                for vehicle, speed in sl["urban"].items():
                    vehicle_vn = {
                        "xe_may": "Xe máy",
                        "oto_con": "Ô tô con",
                        "oto_tai": "Xe tải",
                        "xe_khach": "Xe khách",
                    }.get(vehicle, vehicle)
                    context_parts.append(f"  - {vehicle_vn}: {speed} km/h")
            context_parts.append("**Ngoài đô thị:**")
            if sl.get("rural"):
                for vehicle, speed in sl["rural"].items():
                    vehicle_vn = {
                        "xe_may": "Xe máy",
                        "oto_con": "Ô tô con",
                        "oto_tai": "Xe tải",
                        "xe_khach": "Xe khách",
                    }.get(vehicle, vehicle)
                    context_parts.append(f"  - {vehicle_vn}: {speed} km/h")
            context_parts.append("")

        # Format point system
        if search_results.get("point_system"):
            ps = search_results["point_system"]
            context_parts.append("## HỆ THỐNG TRỪ ĐIỂM GPLX (từ 01/01/2025):")
            context_parts.append(f"- Tổng điểm: {ps.get('total_points', 12)} điểm/năm")
            for rule in ps.get("rules", []):
                context_parts.append(f"- {rule.get('rule', '')}")
            context_parts.append("")

        return "\n".join(context_parts) if context_parts else "Không tìm thấy thông tin liên quan trong cơ sở dữ liệu."


# Singleton instance for easy import
traffic_law_kb = TrafficLawKB()
