import pytest
from src.database import init_db
from tests.helpers import insert_row
from src.web_verification import get_cached_verification, cache_verification_result, verify_scholarship_record
from src.ai_agent import process_chat_message

def test_cache_and_get_verification(isolated_database):
    init_db()
    insert_row(name="Test Award", provider="Test Provider", source_url="https://example.com")
    sch_id = 1
    cache_verification_result(
        sch_id, "Test Award", "Test Provider", "https://example.com", "verified_primary",
        ["Claim 1"], ["Discrepancy 1"], "Raw test evidence"
    )

    cached = get_cached_verification(sch_id)
    assert cached is not None
    assert cached["scholarship_id"] == sch_id
    assert cached["status"] == "verified_primary"
    assert "Claim 1" in cached["verified_claims"]
    assert "Discrepancy 1" in cached["discrepancies"]

def test_process_chat_message_off_topic():
    res = process_chat_message("Write a python script to parse json")
    assert res["intent"] == "off_topic"
    assert "PathFinder AI Scholarship Assistant" in res["response"]

def test_process_chat_message_fallback(isolated_database):
    res = process_chat_message("Find scholarships for BS Computer Science in Punjab")
    assert res["intent"] == "scholarship_chat"
    assert res["updated_profile"]["province"] == "Punjab"
    assert isinstance(res["scholarships"], list)

def test_process_chat_message_conversation_history(isolated_database):
    history = [
        {"role": "user", "content": "I am looking for undergraduate scholarships"},
        {"role": "assistant", "content": "Sure, what is your province?"},
    ]
    res = process_chat_message("Punjab", conversation_history=history)
    assert res["intent"] == "scholarship_chat"
    assert res["updated_profile"]["province"] == "Punjab"
