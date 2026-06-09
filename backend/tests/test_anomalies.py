import pytest
from datetime import datetime, timedelta
from app.pipelines.anomalies import AnomalyDetector


def test_calculate_median():
    assert AnomalyDetector.calculate_median([10, 20, 30]) == 20.0
    assert AnomalyDetector.calculate_median([10, 20, 30, 40]) == 25.0
    assert AnomalyDetector.calculate_median([]) == 0.0


def test_anomaly_3x_median():
    # Account has historical median of 100. Current txn is 400 (4x).
    history = [
        {"account_id": "ACC1", "amount": 100.0, "date": datetime(2024, 1, 1), "txn_id": "TXH1"},
        {"account_id": "ACC1", "amount": 100.0, "date": datetime(2024, 1, 2), "txn_id": "TXH2"},
        {"account_id": "ACC1", "amount": 100.0, "date": datetime(2024, 1, 3), "txn_id": "TXH3"},
    ]
    current = [
        {
            "account_id": "ACC1",
            "amount": 400.0,
            "currency": "INR",
            "merchant": "Uber",
            "date": datetime(2024, 1, 4),
            "notes": "Work travel",
            "txn_id": "TXC1"
        }
    ]
    
    res = AnomalyDetector.process_anomalies(current, history)
    assert res[0]["is_anomaly"] is True
    rules = [a["rule"] for a in res[0]["anomalies"]]
    assert "HIGH_AMOUNT_3X_MEDIAN" in rules


def test_anomaly_domestic_usd():
    current = [
        {
            "account_id": "ACC1",
            "amount": 50.0,
            "currency": "USD",
            "merchant": "Swiggy",
            "date": datetime(2024, 1, 1),
            "notes": "Food order",
            "txn_id": "TXC1"
        }
    ]
    
    res = AnomalyDetector.process_anomalies(current, [])
    assert res[0]["is_anomaly"] is True
    rules = [a["rule"] for a in res[0]["anomalies"]]
    assert "DOMESTIC_USD" in rules


def test_anomaly_suspicious_keyword():
    current = [
        {
            "account_id": "ACC1",
            "amount": 50.0,
            "currency": "INR",
            "merchant": "Walmart",
            "date": datetime(2024, 1, 1),
            "notes": "This is SUSPICIOUS!",
            "txn_id": "TXC1"
        }
    ]
    
    res = AnomalyDetector.process_anomalies(current, [])
    assert res[0]["is_anomaly"] is True
    rules = [a["rule"] for a in res[0]["anomalies"]]
    assert "SUSPICIOUS_KEYWORD" in rules


def test_anomaly_repeated_rapid():
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    # 2 transactions for ACC1 at merchant Uber within 5 mins
    current = [
        {
            "account_id": "ACC1",
            "amount": 100.0,
            "currency": "INR",
            "merchant": "Uber",
            "date": base_time,
            "txn_id": "TXC1"
        },
        {
            "account_id": "ACC1",
            "amount": 105.0,
            "currency": "INR",
            "merchant": "Uber",
            "date": base_time + timedelta(minutes=5),
            "txn_id": "TXC2"
        }
    ]
    
    res = AnomalyDetector.process_anomalies(current, [])
    
    # Both should detect the rapid repetition anomaly
    assert res[0]["is_anomaly"] is True
    assert res[1]["is_anomaly"] is True
    assert "REPEATED_RAPID" in [a["rule"] for a in res[0]["anomalies"]]
    assert "REPEATED_RAPID" in [a["rule"] for a in res[1]["anomalies"]]
