import pytest
from app.pipelines.cleaner import DataCleaner, clean_csv_payload


def test_clean_amount():
    amount, modified = DataCleaner.clean_amount("$1000.50")
    assert amount == 1000.50
    assert modified is True

    amount, modified = DataCleaner.clean_amount("250.75")
    assert amount == 250.75
    assert modified is False

    amount, modified = DataCleaner.clean_amount("not-a-number")
    assert amount is None


def test_parse_dates():
    dt, fmt = DataCleaner.parse_date("04-09-2024")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 9
    assert dt.day == 4

    dt, fmt = DataCleaner.parse_date("2024/02/05")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 2
    assert dt.day == 5

    dt, fmt = DataCleaner.parse_date("invalid-date")
    assert dt is None


def test_clean_row_valid():
    row = {
        "txn_id": "TX100",
        "date": "2024/02/05",
        "merchant": "Swiggy",
        "amount": "$125.50",
        "currency": "inr",
        "status": "success",
        "category": "Food",
        "account_id": "ACC01",
        "notes": "Dinner"
    }
    
    cleaned, err = DataCleaner.clean_row(row, 1)
    assert err is None
    assert cleaned["txn_id"] == "TX100"
    assert cleaned["amount"] == 125.50
    assert cleaned["currency"] == "INR"
    assert cleaned["status"] == "SUCCESS"
    assert cleaned["category"] == "Food"


def test_clean_row_missing_txn_id():
    row = {
        "txn_id": "",
        "date": "17-02-2024",
        "merchant": "Zomato",
        "amount": "25.00",
        "currency": "USD",
        "status": "success",
        "category": "",
        "account_id": "ACC01",
        "notes": ""
    }
    
    cleaned, err = DataCleaner.clean_row(row, 2)
    assert err is None
    assert cleaned["txn_id"].startswith("GEN_TXN_")
    assert cleaned["cleaning_metadata"]["txn_id"]["modified"] is True


def test_clean_row_invalid_missing_account():
    row = {
        "txn_id": "TX101",
        "date": "17-02-2024",
        "merchant": "Zomato",
        "amount": "25.00",
        "currency": "USD",
        "status": "success",
        "account_id": ""  # Missing critical field
    }
    
    cleaned, err = DataCleaner.clean_row(row, 3)
    assert cleaned is None
    assert "Missing account_id" in err["errors"]


def test_clean_csv_payload_duplicates():
    csv_data = (
        "txn_id,date,merchant,amount,currency,status,category,account_id,notes\n"
        "TX1,04-09-2024,Flipkart,100,INR,SUCCESS,Shopping,ACC3,None\n"
        "TX1,04-09-2024,Flipkart,100,INR,SUCCESS,Shopping,ACC3,None\n"  # Duplicate txn_id
        "TX2,04-09-2024,Flipkart,200,INR,SUCCESS,Shopping,ACC3,None\n"
    )
    
    cleaned, errors = clean_csv_payload(csv_data)
    assert len(cleaned) == 2
    assert len(errors) == 1
    assert "Duplicate transaction ID" in errors[0]["errors"][0]
