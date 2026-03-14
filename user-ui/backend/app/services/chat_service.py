"""
Chat Service - Orchestrates the chatbot logic with topic validation, RAG, and LLM.
"""

import os
import logging
from typing import Optional, List, Dict, Any

from app.validators.topic_validator import TopicValidator, ValidationResult, TopicCategory
from app.models.chat_models import (
    ChatRequest,
    ChatResponse,
    SourceReference,
)
from app.knowledge.traffic_law_kb import traffic_law_kb, TrafficLawKB
from app.services.traffic_service import traffic_service
from app.prompts.traffic_law_prompt import build_chat_prompt, format_chat_history
from app.core.config import RAG_FAQ_THRESHOLD, RAG_VIOLATION_THRESHOLD, RAG_GPLX_THRESHOLD

# Configure logging
logger = logging.getLogger(__name__)


class ChatService:
    """
    Main chat service that orchestrates:
    1. Topic validation (filter off-topic)
    2. RAG search (retrieve relevant context)
    3. LLM call (generate response)
    """

    def __init__(
        self,
        knowledge_base: Optional[TrafficLawKB] = None,
        llm_provider: str = "anthropic",
    ):
        """
        Initialize chat service.

        Args:
            knowledge_base: TrafficLawKB instance (uses singleton if not provided)
            llm_provider: LLM provider to use ("openai", "anthropic", or "mock")
        """
        self.topic_validator = TopicValidator()
        self.knowledge_base = knowledge_base or traffic_law_kb
        self.llm_provider = llm_provider
        self._llm_client = None

    def _get_llm_client(self):
        """Lazy initialization of LLM client."""
        if self._llm_client is not None:
            return self._llm_client

        if self.llm_provider == "openai":
            try:
                from openai import OpenAI

                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self._llm_client = OpenAI(api_key=api_key)
                else:
                    logger.warning("OPENAI_API_KEY not set, using mock responses")
                    self._llm_client = None
            except ImportError:
                logger.warning("OpenAI package not installed, using mock responses")
                self._llm_client = None

        elif self.llm_provider == "anthropic":
            try:
                from anthropic import Anthropic

                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    self._llm_client = Anthropic(api_key=api_key)
                else:
                    logger.warning("ANTHROPIC_API_KEY not set, using mock responses")
                    self._llm_client = None
            except ImportError:
                logger.warning("Anthropic package not installed, using mock responses")
                self._llm_client = None

        return self._llm_client

    async def _call_llm(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Call LLM with the given prompt.

        Args:
            prompt: The complete prompt to send
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLM response text
        """
        client = self._get_llm_client()

        if client is None:
            # Return a mock response when no LLM is configured
            return self._generate_mock_response(prompt)

        try:
            if self.llm_provider == "openai":
                response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""

            elif self.llm_provider == "anthropic":
                response = client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"),
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text if response.content else ""

            else:
                # Unknown provider, use mock response
                return self._generate_mock_response(prompt)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return self._generate_fallback_response()

        # Fallback (should not reach here)
        return self._generate_fallback_response()

    def _generate_mock_response(self, prompt: str) -> str:
        """Generate a mock response when LLM is not available."""
        # Extract some context from RAG if present in prompt
        if "THÔNG TIN VI PHẠM" in prompt:
            return """Dựa trên thông tin từ cơ sở dữ liệu, **TECHNO TRAFFIX** sẽ trả lời câu hỏi của bạn.

⚠️ **Lưu ý**: Đây là chế độ demo (không có kết nối LLM).
Để có câu trả lời chính xác và đầy đủ, vui lòng cấu hình API key cho OpenAI hoặc Anthropic.

Bạn có thể tham khảo thông tin chi tiết tại: thuvienphapluat.vn"""

        return """Cảm ơn bạn đã hỏi **TECHNO TRAFFIX** về luật giao thông!

⚠️ **Chế độ Demo**: Hiện tại **TECHNO TRAFFIX** đang chạy ở chế độ demo (không có LLM API).
Để được hỗ trợ đầy đủ, vui lòng cấu hình biến môi trường:
- `OPENAI_API_KEY` cho OpenAI
- `ANTHROPIC_API_KEY` cho Anthropic

Bạn vẫn có thể xem thông tin từ cơ sở dữ liệu trong phần nguồn tham khảo."""

    def _generate_fallback_response(self) -> str:
        """Generate fallback response when LLM fails."""
        return """**TECHNO TRAFFIX** xin lỗi, hiện tại đang gặp sự cố kỹ thuật và không thể trả lời chi tiết.

Bạn có thể:
1. Thử lại sau vài phút
2. Tra cứu trực tiếp tại: thuvienphapluat.vn
3. Liên hệ cơ quan chức năng để được tư vấn chính xác

**TECHNO TRAFFIX** xin cảm ơn sự thông cảm của bạn!"""

    def _convert_search_results_to_sources(self, search_results: Dict[str, Any]) -> List[SourceReference]:
        """Convert RAG search results to SourceReference objects."""
        sources = []

        # Convert violations
        for v in search_results.get("violations", [])[:3]:
            sources.append(
                SourceReference(
                    id=v.get("id", ""),
                    content=v.get("content", ""),
                    source=v.get("source", "Nghị định 168/2024"),
                    category=v.get("category", "Vi phạm"),
                    relevance_score=v.get("score", 0.0),
                    metadata={
                        "fine": v.get("fine"),
                        "license_suspension": v.get("license_suspension"),
                        "points_deducted": v.get("points_deducted"),
                        "vehicle_type": v.get("vehicle_type"),
                    },
                )
            )

        # Convert FAQ
        for f in search_results.get("faq", [])[:2]:
            sources.append(
                SourceReference(
                    id=f.get("id", ""),
                    content=f.get("answer", ""),
                    source="FAQ - Câu hỏi thường gặp",
                    category="FAQ",
                    relevance_score=f.get("score", 0.0),
                    metadata={"question": f.get("question")},
                )
            )

        # Convert GPLX
        for g in search_results.get("gplx", [])[:2]:
            sources.append(
                SourceReference(
                    id=g.get("id", ""),
                    content=g.get("content", ""),
                    source="Quy định GPLX",
                    category="Giấy phép lái xe",
                    relevance_score=g.get("score", 0.0),
                    metadata={"class": g.get("class")},
                )
            )

        return sources

    def _check_rag_sufficiency(self, search_results: Dict[str, Any]) -> bool:
        """
        Check if RAG results are sufficient to answer without LLM.

        Returns True if we have high-confidence results from the knowledge base.
        Uses configurable thresholds from config.py (can be set via environment variables).
        """
        # Check FAQ - highest priority as they're complete Q&A pairs
        faq_results = search_results.get("faq", [])
        if faq_results and faq_results[0].get("score", 0) >= RAG_FAQ_THRESHOLD:
            logger.info(f"High-quality FAQ match found (score: {faq_results[0].get('score')}, threshold: {RAG_FAQ_THRESHOLD})")
            return True

        # Check violations - good for specific violation queries
        violation_results = search_results.get("violations", [])
        if violation_results and violation_results[0].get("score", 0) >= RAG_VIOLATION_THRESHOLD:
            logger.info(f"High-quality violation match found (score: {violation_results[0].get('score')}, threshold: {RAG_VIOLATION_THRESHOLD})")
            return True

        # Check GPLX info
        gplx_results = search_results.get("gplx", [])
        if gplx_results and gplx_results[0].get("score", 0) >= RAG_GPLX_THRESHOLD:
            logger.info(f"High-quality GPLX match found (score: {gplx_results[0].get('score')}, threshold: {RAG_GPLX_THRESHOLD})")
            return True

        # Check if we have speed limits or point system info (always sufficient if present)
        if search_results.get("speed_limits") or search_results.get("point_system"):
            logger.info("Speed limits or point system info found")
            return True

        logger.info("RAG results insufficient, will use LLM for response generation")
        return False

    def _format_rag_only_response(self, search_results: Dict[str, Any]) -> str:
        """
        Format RAG results into a complete user response without LLM.
        Used when RAG has high-confidence results.
        """
        response_parts = []

        # Format FAQ answers (highest priority)
        faq_results = search_results.get("faq", [])
        if faq_results:
            top_faq = faq_results[0]
            response_parts.append(f"**{top_faq.get('question', '')}**\n")
            response_parts.append(top_faq.get("answer", ""))
            response_parts.append("")

            # Add additional FAQs if relevant
            if len(faq_results) > 1 and faq_results[1].get("score", 0) >= 2.0:
                response_parts.append("**Xem thêm:**")
                for faq in faq_results[1:3]:
                    response_parts.append(f"- {faq.get('question', '')}")
                response_parts.append("")

        # Format violations
        violation_results = search_results.get("violations", [])
        if violation_results and not faq_results:  # Only if FAQ didn't answer
            response_parts.append("**Thông tin vi phạm:**\n")
            for i, v in enumerate(violation_results[:3], 1):
                response_parts.append(f"{i}. **{v.get('category', '')}** ({v.get('vehicle_type', '')})")
                response_parts.append(f"   - Vi phạm: {v.get('content', '')}")
                response_parts.append(f"   - Mức phạt: {v.get('fine', '')}")
                if v.get("license_suspension"):
                    response_parts.append(f"   - {v.get('license_suspension')}")
                if v.get("points_deducted"):
                    response_parts.append(f"   - {v.get('points_deducted')}")
                response_parts.append("")

        # Format GPLX info
        gplx_results = search_results.get("gplx", [])
        if gplx_results and not faq_results:  # Only if FAQ didn't answer
            response_parts.append("**Thông tin giấy phép lái xe:**\n")
            for g in gplx_results[:2]:
                response_parts.append(f"- {g.get('content', '')}")
            response_parts.append("")

        # Format speed limits
        if search_results.get("speed_limits"):
            sl = search_results["speed_limits"]
            response_parts.append("**Quy định tốc độ (Luật GTĐB 2024):**\n")
            response_parts.append("*Trong đô thị:*")
            if sl.get("urban"):
                for vehicle, speed in sl["urban"].items():
                    vehicle_vn = {
                        "xe_may": "Xe máy",
                        "oto_con": "Ô tô con",
                        "oto_tai": "Xe tải",
                        "xe_khach": "Xe khách",
                    }.get(vehicle, vehicle)
                    response_parts.append(f"- {vehicle_vn}: {speed} km/h")
            response_parts.append("\n*Ngoài đô thị:*")
            if sl.get("rural"):
                for vehicle, speed in sl["rural"].items():
                    vehicle_vn = {
                        "xe_may": "Xe máy",
                        "oto_con": "Ô tô con",
                        "oto_tai": "Xe tải",
                        "xe_khach": "Xe khách",
                    }.get(vehicle, vehicle)
                    response_parts.append(f"- {vehicle_vn}: {speed} km/h")
            response_parts.append("")

        # Format point system
        if search_results.get("point_system"):
            ps = search_results["point_system"]
            response_parts.append("**Hệ thống trừ điểm GPLX (từ 01/01/2025):**")
            response_parts.append(f"- Tổng điểm: {ps.get('total_points', 12)} điểm/năm")
            for rule in ps.get("rules", [])[:5]:
                response_parts.append(f"- {rule.get('rule', '')}")
            response_parts.append("")

        # Add footer note
        response_parts.append("---")
        response_parts.append("*Thông tin được **TECHNO TRAFFIX** trích xuất trực tiếp từ cơ sở dữ liệu luật giao thông Việt Nam.*")

        return "\n".join(response_parts)

    async def process_message(
        self,
        request: ChatRequest,
    ) -> ChatResponse:
        """
        Process a chat message through the full pipeline.

        Pipeline:
        1. Validate request
        2. Check topic validity
        3. Handle greetings (no LLM needed)
        4. Search knowledge base (RAG)
        5. Build prompt with context
        6. Call LLM
        7. Return response

        Args:
            request: ChatRequest with message and optional history

        Returns:
            ChatResponse with answer and metadata
        """
        # Step 1: Validate request
        is_valid, error = request.validate()
        if not is_valid:
            return ChatResponse.error_response(error or "Invalid request")

        message = request.message.strip()

        # Step 2: Validate topic
        validation = self.topic_validator.validate(message)

        # Step 3: Handle greetings (no LLM call needed)
        if validation.category == TopicCategory.GREETING:
            return ChatResponse(
                content=validation.suggested_response or "",
                is_ai_generated=False,
                topic_valid=True,
                session_id=request.session_id,
                category=validation.category.value,
                confidence=validation.confidence,
            )

        # Step 4: Reject off-topic messages
        if not validation.is_valid:
            return ChatResponse(
                content=validation.suggested_response or "",
                is_ai_generated=False,
                topic_valid=False,
                session_id=request.session_id,
                category=validation.category.value,
                confidence=validation.confidence,
            )

        # Step 4b: Handle traffic status queries (real-time data, no LLM needed)
        #          Always include both GPS location data and fixed zone data.
        if validation.category == TopicCategory.TRAFFIC_STATUS:
            lat = request.location["lat"] if request.location else None
            lng = request.location["lng"] if request.location else None
            summary = traffic_service.get_combined_traffic_summary(
                lat=lat, lng=lng, message=message
            )
            if summary:
                return ChatResponse(
                    content=summary,
                    is_ai_generated=False,
                    topic_valid=True,
                    session_id=request.session_id,
                    category=validation.category.value,
                    confidence=validation.confidence,
                )

        # Step 5: Search knowledge base (RAG)
        intent = self.topic_validator.get_intent(validation)
        search_results = self.knowledge_base.search(message, intent=intent)
        rag_context = self.knowledge_base.format_rag_context(search_results)

        # Convert to source references
        sources = self._convert_search_results_to_sources(search_results)

        # Step 6: Check if RAG results are sufficient (PRIORITIZE RAG)
        if self._check_rag_sufficiency(search_results):
            # RAG has high-quality results - return directly without LLM call
            logger.info("Using RAG-only response (no LLM call)")
            rag_response = self._format_rag_only_response(search_results)
            return ChatResponse(
                content=rag_response,
                is_ai_generated=False,  # Direct from knowledge base
                topic_valid=True,
                session_id=request.session_id,
                sources=sources,
                category=validation.category.value,
                confidence=validation.confidence,
            )

        # Step 7: RAG insufficient - use LLM with context
        logger.info("RAG results insufficient, calling LLM with context")

        # Inject traffic status context if this is a traffic status question
        traffic_context = ""
        if validation.category == TopicCategory.TRAFFIC_STATUS:
            lat = request.location["lat"] if request.location else None
            lng = request.location["lng"] if request.location else None
            traffic_context = traffic_service.get_combined_traffic_summary(
                lat=lat, lng=lng, message=message
            ) or ""

        chat_history_str = format_chat_history(request.chat_history)
        prompt = build_chat_prompt(
            user_message=message,
            rag_context=rag_context,
            chat_history=chat_history_str,
            traffic_context=traffic_context,
        )

        # Step 8: Call LLM
        try:
            llm_response = await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            llm_response = self._generate_fallback_response()

        # Step 9: Return response
        return ChatResponse(
            content=llm_response,
            is_ai_generated=True,
            topic_valid=True,
            session_id=request.session_id,
            sources=sources,
            category=validation.category.value,
            confidence=validation.confidence,
        )

    def process_message_sync(self, request: ChatRequest) -> ChatResponse:
        """
        Synchronous wrapper for process_message.
        Use this for non-async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.process_message(request))


# Singleton instance for easy import
chat_service = ChatService()
