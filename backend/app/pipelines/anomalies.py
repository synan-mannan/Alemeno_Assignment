import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.logging import logger


class AnomalyDetector:
    SUSPICIOUS_KEYWORDS = [
        "suspicious",
        "unauthorized",
        "chargeback",
        "unrecognized",
        "dispute",
        "fraud",
        "stolen",
        "hack",
        "duplicate",
    ]

    @classmethod
    def calculate_median(cls, values: List[float]) -> float:
        """Helper to calculate median of a list of floats."""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        return sorted_vals[mid]

    @classmethod
    def calculate_stats(cls, values: List[float]) -> tuple[float, float]:
        """Helper to calculate mean and standard deviation of a list of floats."""
        if not values:
            return 0.0, 0.0
        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        std_dev = math.sqrt(variance)
        return mean, std_dev

    @classmethod
    def process_anomalies(
        cls, 
        current_txns: List[Dict[str, Any]], 
        historical_txns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Processes a list of transaction dictionaries, evaluates anomaly rules,
        and annotates each transaction dict with is_anomaly and anomalies list.
        """
        # Combine current and historical transactions to calculate per-account stats
        all_txns_by_account: Dict[str, List[Dict[str, Any]]] = {}
        for txn in historical_txns + current_txns:
            acc = txn.get("account_id")
            if acc:
                all_txns_by_account.setdefault(acc, []).append(txn)

        # Precompute statistics per account
        account_stats: Dict[str, Dict[str, Any]] = {}
        for acc, txns in all_txns_by_account.items():
            amounts = [t["amount"] for t in txns if t["amount"] is not None]
            if amounts:
                median = cls.calculate_median(amounts)
                mean, std_dev = cls.calculate_stats(amounts)
                account_stats[acc] = {
                    "median": median,
                    "mean": mean,
                    "std_dev": std_dev,
                    "amounts": amounts,
                    "all_txns_sorted": sorted(txns, key=lambda t: t["date"])
                }

        # Domestic brand list from settings (lowercase)
        domestic_brands = settings.DOMESTIC_BRANDS

        # Check each transaction in the current batch
        for txn in current_txns:
            txn_anomalies = []
            acc_id = txn.get("account_id")
            amount = txn.get("amount")
            currency = txn.get("currency", "USD").upper()
            merchant = txn.get("merchant", "").lower()
            date = txn.get("date")
            notes = txn.get("notes", "") or ""

            # Skip checking transactions without critical components
            if not acc_id or amount is None or not date:
                txn["is_anomaly"] = False
                txn["anomalies"] = []
                continue

            stats = account_stats.get(acc_id, {})
            median = stats.get("median", 0.0)
            mean = stats.get("mean", 0.0)
            std_dev = stats.get("std_dev", 0.0)

            # Rule 1: Amount > 3x Median for the account
            median_threshold = median * settings.ANOMALY_MEDIAN_MULTIPLIER
            if median > 0 and amount > median_threshold:
                multiplier = amount / median
                txn_anomalies.append({
                    "rule": "HIGH_AMOUNT_3X_MEDIAN",
                    "severity": "MEDIUM",
                    "confidence": min(0.95, 0.6 + (multiplier - 3.0) * 0.05),
                    "reason": f"Transaction amount {amount:.2f} is {multiplier:.1f}x the median account spend ({median:.2f})"
                })

            # Rule 2: Domestic brands using USD
            # Check if merchant matches a domestic brand
            is_domestic = any(brand in merchant for brand in domestic_brands)
            if is_domestic and currency == "USD":
                txn_anomalies.append({
                    "rule": "DOMESTIC_USD",
                    "severity": "HIGH",
                    "confidence": 0.90,
                    "reason": f"Domestic merchant '{txn['merchant']}' charged in USD"
                })

            # Rule 3: Z-Score detection (statistical)
            if std_dev > 0.01:
                z_score = abs(amount - mean) / std_dev
                if z_score > settings.ANOMALY_Z_SCORE_THRESHOLD:
                    txn_anomalies.append({
                        "rule": "Z_SCORE_ANOMALY",
                        "severity": "HIGH",
                        "confidence": min(0.99, 0.8 + (z_score - settings.ANOMALY_Z_SCORE_THRESHOLD) * 0.05),
                        "reason": f"Transaction amount {amount:.2f} is statistically anomalous with a Z-score of {z_score:.2f} (mean: {mean:.2f}, std_dev: {std_dev:.2f})"
                    })

            # Rule 4: Suspicious keywords in notes
            notes_lower = notes.lower()
            matching_keywords = [word for word in cls.SUSPICIOUS_KEYWORDS if word in notes_lower]
            if matching_keywords:
                txn_anomalies.append({
                    "rule": "SUSPICIOUS_KEYWORD",
                    "severity": "LOW",
                    "confidence": 0.70,
                    "reason": f"Notes contain suspicious keyword(s): {', '.join(matching_keywords)}"
                })

            # Rule 5: Repeated rapid transactions detection
            # Same account, same merchant, within 10 minutes
            if stats:
                sorted_txns = stats.get("all_txns_sorted", [])
                rapid_count = 0
                window = timedelta(minutes=settings.RAPID_TRANSACTION_WINDOW_MINUTES)
                
                for other_txn in sorted_txns:
                    other_id = other_txn.get("txn_id")
                    # Do not compare the transaction with itself
                    if other_id == txn.get("txn_id"):
                        continue
                    
                    # Same merchant
                    if other_txn.get("merchant", "").lower() == merchant:
                        other_date = other_txn.get("date")
                        if other_date:
                            time_diff = abs(date - other_date)
                            if time_diff <= window:
                                rapid_count += 1

                if rapid_count > 0:
                    txn_anomalies.append({
                        "rule": "REPEATED_RAPID",
                        "severity": "MEDIUM",
                        "confidence": min(0.95, 0.5 + rapid_count * 0.15),
                        "reason": f"Detected {rapid_count} other transaction(s) for merchant '{txn['merchant']}' within {settings.RAPID_TRANSACTION_WINDOW_MINUTES} minutes"
                    })

            txn["is_anomaly"] = len(txn_anomalies) > 0
            txn["anomalies"] = txn_anomalies

        return current_txns
