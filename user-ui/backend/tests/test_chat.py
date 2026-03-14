"""
Tests for chat functionality - Topic Validator and Chat Service
"""

import sys
import io
from pathlib import Path

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validators.topic_validator import TopicValidator, TopicCategory
from app.models.chat_models import ChatRequest, ChatResponse
from app.services.chat_service import ChatService


def test_topic_validator():
    """Test TopicValidator with various inputs."""
    validator = TopicValidator()

    print("=" * 60)
    print("TESTING TOPIC VALIDATOR")
    print("=" * 60)

    # Test cases: (message, expected_valid, expected_category)
    test_cases = [
        # Greetings - should be valid
        ("Xin chào", True, TopicCategory.GREETING),
        ("Hello", True, TopicCategory.GREETING),
        ("Chào bạn", True, TopicCategory.GREETING),
        ("Cảm ơn bạn", True, TopicCategory.GREETING),
        ("Tạm biệt", True, TopicCategory.GREETING),
        # Traffic-related - should be valid
        ("Phạt vượt đèn đỏ bao nhiêu?", True, None),  # Should detect as traffic
        ("Vượt đèn đỏ bị phạt bao nhiêu tiền?", True, None),
        ("Tốc độ tối đa trong đô thị là bao nhiêu?", True, None),
        ("Uống rượu lái xe bị phạt như thế nào?", True, None),
        ("Bằng lái xe hạng B2 được lái xe gì?", True, None),
        ("Xe máy chạy quá tốc độ bị phạt bao nhiêu?", True, None),
        ("Không đội mũ bảo hiểm phạt bao nhiêu?", True, None),
        ("Nghị định 168 quy định gì?", True, None),
        ("Hệ thống trừ điểm GPLX hoạt động thế nào?", True, None),
        ("Nồng độ cồn cho phép là bao nhiêu?", True, None),
        # Off-topic - should be invalid
        ("Hôm nay thời tiết thế nào?", False, TopicCategory.OFF_TOPIC),
        ("Cách nấu phở ngon?", False, TopicCategory.OFF_TOPIC),
        ("Bitcoin giá bao nhiêu?", False, TopicCategory.OFF_TOPIC),
        ("Viết code Python cho tôi", False, TopicCategory.OFF_TOPIC),
        ("Đội bóng nào vô địch World Cup?", False, TopicCategory.OFF_TOPIC),
        ("Phim hay nào đang chiếu?", False, TopicCategory.OFF_TOPIC),
        ("Làm sao để tán gái?", False, TopicCategory.OFF_TOPIC),
        ("Tôi bị đau đầu phải làm sao?", False, TopicCategory.OFF_TOPIC),
        # Edge cases
        ("", False, TopicCategory.OFF_TOPIC),  # Empty
        ("   ", False, TopicCategory.OFF_TOPIC),  # Whitespace only
        ("Có", True, None),  # Very short, might be follow-up
    ]

    passed = 0
    failed = 0

    for message, expected_valid, expected_category in test_cases:
        result = validator.validate(message)

        # Check validity
        valid_match = result.is_valid == expected_valid

        # Check category (if specified)
        category_match = True
        if expected_category is not None:
            category_match = result.category == expected_category

        status = "PASS" if (valid_match and category_match) else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(
            f"\n[{status}] Message: '{message[:40]}...' " if len(message) > 40 else f"\n[{status}] Message: '{message}'"
        )
        print(f"  Expected: valid={expected_valid}, category={expected_category}")
        print(f"  Got:      valid={result.is_valid}, category={result.category}, confidence={result.confidence:.2f}")
        print(f"  Reason:   {result.reason}")

        if not result.is_valid and result.suggested_response:
            print(f"  Response: {result.suggested_response[:80]}...")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 60)

    return failed == 0


def test_chat_service():
    """Test ChatService with mock LLM."""
    print("\n" + "=" * 60)
    print("TESTING CHAT SERVICE")
    print("=" * 60)

    # Use mock provider (no API key needed)
    service = ChatService(llm_provider="mock")

    test_cases = [
        # Valid traffic questions - now uses RAG directly (is_ai_generated = False)
        {
            "message": "Phạt vượt đèn đỏ bao nhiêu?",
            "expected_valid": True,
            "expected_ai": False,  # RAG has high-quality match, no LLM needed
        },
        {
            "message": "Xin chào",
            "expected_valid": True,
            "expected_ai": False,  # Greeting handled without LLM
        },
        # Off-topic
        {
            "message": "Cách nấu phở ngon?",
            "expected_valid": False,
            "expected_ai": False,
        },
    ]

    passed = 0
    failed = 0

    for case in test_cases:
        request = ChatRequest(message=case["message"])
        response = service.process_message_sync(request)

        valid_match = response.topic_valid == case["expected_valid"]
        ai_match = response.is_ai_generated == case["expected_ai"]

        status = "PASS" if (valid_match and ai_match) else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        print(f"\n[{status}] Message: '{case['message']}'")
        print(f"  Expected: topic_valid={case['expected_valid']}, is_ai={case['expected_ai']}")
        print(f"  Got:      topic_valid={response.topic_valid}, is_ai={response.is_ai_generated}")
        print(f"  Category: {response.category}")
        print(f"  Response: {response.content[:100]}...")
        if response.sources:
            print(f"  Sources:  {len(response.sources)} found")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 60)

    return failed == 0


def test_knowledge_base_search():
    """Test knowledge base search functionality."""
    print("\n" + "=" * 60)
    print("TESTING KNOWLEDGE BASE SEARCH")
    print("=" * 60)

    from app.knowledge.traffic_law_kb import traffic_law_kb

    queries = [
        "vượt đèn đỏ",
        "nồng độ cồn",
        "tốc độ trong đô thị",
        "bằng lái xe hạng B2",
        "không đội mũ bảo hiểm",
    ]

    for query in queries:
        print(f"\nQuery: '{query}'")
        results = traffic_law_kb.search(query)

        print(f"  Violations found: {len(results.get('violations', []))}")
        print(f"  FAQ found: {len(results.get('faq', []))}")
        print(f"  GPLX found: {len(results.get('gplx', []))}")
        print(f"  Has results: {results.get('has_results', False)}")

        if results.get("violations"):
            v = results["violations"][0]
            print(f"  Top violation: {v.get('content', '')[:60]}...")
            print(f"  Fine: {v.get('fine', 'N/A')}")


def test_rag_priority():
    """Test RAG priority - should use RAG without LLM for high-quality matches."""
    print("\n" + "=" * 60)
    print("TESTING RAG PRIORITY (RAG vs LLM)")
    print("=" * 60)

    # Use mock provider
    service = ChatService(llm_provider="mock")

    test_cases = [
        # FAQ question - should use RAG only (is_ai_generated = False, topic_valid = True)
        {
            "message": "Vượt đèn vàng có bị phạt không?",
            "expected_rag_only": True,
            "expected_topic_valid": True,
            "description": "FAQ question - exact match",
        },
        # Violation query with clear keywords - should use RAG only
        {
            "message": "vượt đèn đỏ ô tô",
            "expected_rag_only": True,
            "expected_topic_valid": True,
            "description": "Violation query - clear match",
        },
        # Speed limit question - should use RAG only (speed_limits always sufficient)
        {
            "message": "tốc độ tối đa trong đô thị",
            "expected_rag_only": True,
            "expected_topic_valid": True,
            "description": "Speed limit query",
        },
        # GPLX question - should use RAG only
        {
            "message": "bằng A1 lái xe gì",
            "expected_rag_only": True,
            "expected_topic_valid": True,
            "description": "GPLX query",
        },
        # Greeting - handled separately (is_ai_generated = False but different handler)
        {
            "message": "Xin chào",
            "expected_rag_only": False,
            "expected_topic_valid": True,
            "description": "Greeting - handled by greeting handler",
        },
        # Off-topic - rejected (is_ai_generated = False, topic_valid = False)
        {
            "message": "Cách nấu phở ngon?",
            "expected_rag_only": False,
            "expected_topic_valid": False,
            "description": "Off-topic - rejected by validator",
        },
    ]

    passed = 0
    failed = 0

    for case in test_cases:
        request = ChatRequest(message=case["message"])
        response = service.process_message_sync(request)

        # Check if topic validation matches
        topic_match = response.topic_valid == case["expected_topic_valid"]

        # For on-topic questions, check if RAG-only behavior matches expectation
        # is_ai_generated = False AND topic_valid = True means RAG-only
        is_rag_only = (not response.is_ai_generated) and response.topic_valid and response.category != "greeting"
        rag_match = (is_rag_only == case["expected_rag_only"]) or not case["expected_topic_valid"]

        status = "PASS" if (topic_match and rag_match) else "FAIL"

        if status == "PASS":
            passed += 1
        else:
            failed += 1

        source_info = ""
        if response.sources:
            top_source = response.sources[0]
            source_info = f"Top source: {top_source.category} (score: {top_source.relevance_score:.1f})"

        print(f"\n[{status}] {case['description']}")
        print(f"  Message: '{case['message']}'")
        print(f"  Expected: RAG-only={case['expected_rag_only']}, topic_valid={case['expected_topic_valid']}")
        print(f"  Got: is_ai_generated={response.is_ai_generated}, topic_valid={response.topic_valid}, category={response.category}")
        if source_info:
            print(f"  {source_info}")
        print(f"  Response preview: {response.content[:80]}...")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CHAT MODULE TESTS")
    print("=" * 60)

    # Run tests
    validator_ok = test_topic_validator()
    service_ok = test_chat_service()
    test_knowledge_base_search()
    rag_priority_ok = test_rag_priority()

    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Topic Validator: {'PASS' if validator_ok else 'FAIL'}")
    print(f"Chat Service: {'PASS' if service_ok else 'FAIL'}")
    print(f"RAG Priority: {'PASS' if rag_priority_ok else 'FAIL'}")
    print("=" * 60)
