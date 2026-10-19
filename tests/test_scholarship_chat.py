import pytest
from src.scholarship_chat import is_scholarship_related, classify_user_intent, OFF_TOPIC_REDIRECT_MESSAGE

def test_is_scholarship_related_valid():
    valid_queries = [
        "Find me scholarships for BS Computer Science in Pakistan",
        "Am I eligible for Fulbright scholarship with 3.5 CGPA?",
        "What are the required documents for Ehsaas scholarship?",
        "Help me write an SOP for Turkiye Burslari",
        "Hi, I am 20 years old from Punjab with 85% marks in FSC",
    ]
    for q in valid_queries:
        related, _ = is_scholarship_related(q)
        assert related is True, f"Failed on query: {q}"

def test_is_scholarship_related_off_topic():
    off_topic_queries = [
        "Write a python script to solve Fibonacci series",
        "Who is the president of United States?",
        "Tell me a joke about cats",
        "What is the weather in Lahore today?",
        "How to invest in bitcoin crypto?",
        "write python code for this",
        "hi write python script",
    ]
    for q in off_topic_queries:
        related, _ = is_scholarship_related(q)
        assert related is False, f"Failed to reject off-topic query: {q}"


def test_guardrail_word_boundary():
    # "this" contains "hi" as substring, but shouldn't match \bhi\b
    related, reason = is_scholarship_related("this")
    assert "greeting" not in reason

    # Exact greeting match "hi"
    related, reason = is_scholarship_related("hi")
    assert related is True
    assert "greeting" in reason

def test_classify_user_intent():
    assert classify_user_intent("Write a python code for fibonacci") == "off_topic"
    assert classify_user_intent("Find scholarships for my profile") == "search_request"
    assert classify_user_intent("Help me draft an SOP for Fulbright") == "sop_assistance"
    assert classify_user_intent("My age is 22 and CGPA is 3.6 from Punjab") == "profile_update"
