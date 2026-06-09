import csv
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from app.core.logging import logger


class DataCleaner:
    DATE_FORMATS = [
        "%d-%m-%Y",  # 04-09-2024
        "%Y/%m/%d",  # 2024/02/05
        "%Y-%m-%d",  # 2024-07-15
        "%d/%m/%Y",  # 15/07/2024
    ]

    @classmethod
    def clean_string(cls, val: Optional[str]) -> str:
        """Strip whitespace and return cleaned string."""
        if val is None:
            return ""
        return val.strip()

    @classmethod
    def parse_date(cls, date_str: str) -> Tuple[Optional[datetime], Optional[str]]:
        """Attempt to parse dates using known patterns, returning (datetime, format_used)."""
        cleaned = cls.clean_string(date_str)
        if not cleaned:
            return None, None
            
        for fmt in cls.DATE_FORMATS:
            try:
                dt = datetime.strptime(cleaned, fmt)
                return dt, fmt
            except ValueError:
                continue
        return None, None

    @classmethod
    def clean_amount(cls, amount_str: str) -> Tuple[Optional[float], bool]:
        """Strip currency symbols, convert to float."""
        cleaned = cls.clean_string(amount_str)
        if not cleaned:
            return None, False
            
        # Remove common currency symbols and spaces
        sanitized = re.sub(r'[^\d.-]', '', cleaned)
        try:
            return float(sanitized), sanitized != amount_str
        except ValueError:
            return None, False

    @classmethod
    def clean_status(cls, status_str: str) -> str:
        """Normalize status casing (upper) and validate."""
        cleaned = cls.clean_string(status_str).upper()
        if cleaned in ["SUCCESS", "FAILED", "PENDING"]:
            return cleaned
        return "PENDING"  # Default fallback status

    @classmethod
    def clean_currency(cls, currency_str: str) -> str:
        """Normalize currency casing (upper)."""
        return cls.clean_string(currency_str).upper()

    @classmethod
    def generate_surrogate_txn_id(cls, row: Dict[str, str], row_index: int) -> str:
        """Generate a deterministic transaction ID when missing in raw data."""
        # Mix unique fields: date, account_id, merchant, amount + row_index
        mix = f"{row.get('date', '')}_{row.get('account_id', '')}_{row.get('merchant', '')}_{row.get('amount', '')}_{row_index}"
        sha = hashlib.sha256(mix.encode()).hexdigest()[:12].upper()
        return f"GEN_TXN_{sha}"

    @classmethod
    def clean_row(cls, row: Dict[str, str], row_index: int) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Cleans a single row from the transaction CSV.
        Returns:
            Tuple[CleanedDataDict, ErrorDict]
            If row is completely malformed, CleanedDataDict is None and ErrorDict has details.
        """
        errors = []
        lineage = {}
        
        # 1. Whitespace Sanitization
        raw_txn_id = cls.clean_string(row.get("txn_id"))
        raw_date = cls.clean_string(row.get("date"))
        raw_merchant = cls.clean_string(row.get("merchant"))
        raw_amount = cls.clean_string(row.get("amount"))
        raw_currency = cls.clean_string(row.get("currency"))
        raw_status = cls.clean_string(row.get("status"))
        raw_category = cls.clean_string(row.get("category"))
        raw_account_id = cls.clean_string(row.get("account_id"))
        raw_notes = cls.clean_string(row.get("notes"))

        # 2. Field validation: Account ID is critical
        if not raw_account_id:
            errors.append("Missing account_id")
            return None, {"row_index": row_index, "errors": errors, "raw_data": row}

        # 3. Handle Transaction ID
        txn_id = raw_txn_id
        if not txn_id:
            txn_id = cls.generate_surrogate_txn_id(row, row_index)
            lineage["txn_id"] = {
                "modified": True,
                "original": "",
                "cleaned": txn_id,
                "reason": "Missing txn_id; generated unique surrogate ID."
            }

        # 4. Parse Date
        dt, fmt_used = cls.parse_date(raw_date)
        if not dt:
            errors.append(f"Invalid date format: {raw_date}")
            return None, {"row_index": row_index, "errors": errors, "raw_data": row}
        
        iso_date = dt.isoformat()
        if raw_date != iso_date:
            lineage["date"] = {
                "modified": True,
                "original": raw_date,
                "cleaned": iso_date,
                "reason": f"Normalized using format {fmt_used} to ISO-8601."
            }

        # 5. Parse Amount
        amount, modified_amt = cls.clean_amount(raw_amount)
        if amount is None:
            errors.append(f"Invalid amount format: {raw_amount}")
            return None, {"row_index": row_index, "errors": errors, "raw_data": row}
        
        if modified_amt:
            lineage["amount"] = {
                "modified": True,
                "original": raw_amount,
                "cleaned": amount,
                "reason": "Stripped currency symbols/formatting characters."
            }

        # 6. Normalize Casing (Status, Currency)
        currency = cls.clean_currency(raw_currency)
        if raw_currency != currency:
            lineage["currency"] = {
                "modified": True,
                "original": raw_currency,
                "cleaned": currency,
                "reason": "Capitalized currency code."
            }

        status = cls.clean_status(raw_status)
        if raw_status != status:
            lineage["status"] = {
                "modified": True,
                "original": raw_status,
                "cleaned": status,
                "reason": "Normalized status casing."
            }

        # 7. Normalize Category (Empty categories are preserved to be classified by LLM)
        category = raw_category.title() if raw_category else None
        if raw_category and raw_category != category:
            lineage["category"] = {
                "modified": True,
                "original": raw_category,
                "cleaned": category,
                "reason": "Title-cased category name."
            }

        cleaned_data = {
            "txn_id": txn_id,
            "original_txn_id": raw_txn_id or None,
            "date": dt,
            "original_date": raw_date,
            "merchant": raw_merchant or "Unknown Merchant",
            "original_merchant": raw_merchant,
            "amount": amount,
            "original_amount": raw_amount,
            "currency": currency or "USD",
            "original_currency": raw_currency,
            "status": status,
            "original_status": raw_status,
            "category": category,
            "original_category": raw_category,
            "account_id": raw_account_id,
            "notes": raw_notes or None,
            "original_notes": raw_notes,
            "cleaning_metadata": lineage
        }
        return cleaned_data, None


def clean_csv_payload(csv_content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses a CSV string, cleans each row, and detects duplicates.
    Returns:
        Tuple[CleanedTransactionsList, ParsingErrorsList]
    """
    cleaned_rows = []
    errors = []
    seen_txn_ids = set()
    
    reader = csv.DictReader(csv_content.splitlines())
    if not reader.fieldnames:
        raise ValueError("CSV structure is empty or missing header fields.")
        
    for index, row in enumerate(reader, start=1):
        cleaned, err = DataCleaner.clean_row(row, index)
        if err:
            errors.append(err)
            continue
            
        # Check for duplicate transaction ID
        txn_id = cleaned["txn_id"]
        if txn_id in seen_txn_ids:
            # Mark duplicate and record it as a lineage event/exclude
            logger.warning(f"Row {index}: Duplicate transaction ID detected: {txn_id}")
            errors.append({
                "row_index": index,
                "errors": [f"Duplicate transaction ID detected: {txn_id}"],
                "raw_data": row
            })
            continue
            
        seen_txn_ids.add(txn_id)
        cleaned_rows.append(cleaned)
        
    return cleaned_rows, errors
