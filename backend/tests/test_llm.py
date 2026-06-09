import pytest
from unittest.mock import MagicMock
from app.llm.client import MockLLMClient, ResilientLLMClient


def test_mock_llm_classification():
    client = MockLLMClient()
    txns = [
        {"index": 0, "merchant": "Swiggy", "notes": "dinner"},
        {"index": 1, "merchant": "Amazon UK", "notes": "books"},
        {"index": 2, "merchant": "Netflix", "notes": ""},
        {"index": 3, "merchant": "Unknown Corp", "notes": "misc"},
    ]
    
    res = client.classify_transactions(txns)
    classifications = res["classifications"]
    
    assert classifications[0]["category"] == "Food"
    assert classifications[1]["category"] == "Shopping"
    assert classifications[2]["category"] == "Entertainment"
    assert classifications[3]["category"] == "Other"
    assert res["token_usage"]["fallback_triggered"] is True


def test_mock_llm_summary():
    client = MockLLMClient()
    txns = [
        {"amount": 100.0, "currency": "INR", "merchant": "Flipkart"},
        {"amount": 150.0, "currency": "INR", "merchant": "Flipkart"},
        {"amount": 20.0, "currency": "USD", "merchant": "AWS"},
    ]
    anomalies = [{"rule": "test"}]
    
    res = client.generate_summary(txns, anomalies)
    
    assert res["total_spend"]["INR"] == 250.0
    assert res["total_spend"]["USD"] == 20.0
    assert len(res["top_merchants"]) > 0
    assert res["risk_level"] == "MEDIUM"  # 1 anomaly
    assert "financial_narrative" in res


def test_resilient_client_circuit_breaker():
    resilient_client = ResilientLLMClient()
    # Stub Gemini to throw exceptions constantly
    resilient_client.gemini._initialized = True
    resilient_client.gemini.classify_transactions = MagicMock(side_effect=RuntimeError("API Error"))
    
    txns = [{"index": 0, "merchant": "Swiggy", "notes": ""}]
    
    # 1st fail
    resilient_client.classify_transactions(txns)
    assert resilient_client.consecutive_failures == 1
    assert resilient_client.circuit_broken is False
    
    # 2nd fail
    resilient_client.classify_transactions(txns)
    assert resilient_client.consecutive_failures == 2
    assert resilient_client.circuit_broken is False
    
    # 3rd fail (triggers circuit break)
    res = resilient_client.classify_transactions(txns)
    assert resilient_client.circuit_broken is True
    # Verify result came from Mock
    assert res["token_usage"]["fallback_triggered"] is True
