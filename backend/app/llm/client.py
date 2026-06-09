import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import logger
from app.llm.prompts import CLASSIFICATION_PROMPT_TEMPLATE, SUMMARY_PROMPT_TEMPLATE


class BaseLLMClient(ABC):
    @abstractmethod
    def classify_transactions(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Classifies list of transactions.
        Returns:
            Dict containing {"classifications": [{"index": int, "category": str}], "token_usage": dict}
        """
        pass

    @abstractmethod
    def generate_summary(self, transactions: List[Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates financial narrative and metric summaries.
        Returns:
            Dict containing total spend, top merchants, narrative, risk level, token_usage.
        """
        pass


class MockLLMClient(BaseLLMClient):
    """
    Deterministic rule-based fallback client for classification and summary.
    Allows testing/running the entire system offline or when GEMINI_API_KEY is not set.
    """
    
    def classify_transactions(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info("MockLLMClient: Performing local rule-based transaction classification.")
        classifications = []
        
        for txn in transactions:
            idx = txn.get("index")
            merchant = txn.get("merchant", "").lower()
            notes = txn.get("notes", "").lower()
            
            # Simple keyword matching logic
            category = "Other"
            if any(k in merchant for k in ["swiggy", "zomato", "restaurant", "cafe", "food"]):
                category = "Food"
            elif any(k in merchant for k in ["amazon", "flipkart", "ebay", "walmart", "store", "shopping"]):
                category = "Shopping"
            elif any(k in merchant for k in ["makemytrip", "irctc", "flight", "hotel", "travel"]):
                category = "Travel"
            elif any(k in merchant for k in ["ola", "uber", "cab", "taxi", "transport"]):
                category = "Transport"
            elif any(k in merchant for k in ["jio", "recharge", "electricity", "water", "utilities", "bill"]):
                category = "Utilities"
            elif any(k in merchant for k in ["atm", "cash", "withdrawal", "hdfc atm"]):
                category = "Cash Withdrawal"
            elif any(k in merchant for k in ["bookmyshow", "netflix", "cinema", "entertainment", "movie"]):
                category = "Entertainment"
                
            classifications.append({"index": idx, "category": category})
            
        return {
            "classifications": classifications,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "fallback_triggered": True
            }
        }

    def generate_summary(self, transactions: List[Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info("MockLLMClient: Generating local rule-based job summary and narrative.")
        
        # 1. Total spend by currency
        spend_by_currency = {}
        # 2. Spend by merchant
        merchant_spend = {}
        merchant_count = {}
        
        for txn in transactions:
            amt = txn.get("amount")
            curr = txn.get("currency", "USD").upper()
            merch = txn.get("merchant", "Unknown Merchant")
            
            if amt is not None:
                spend_by_currency[curr] = spend_by_currency.get(curr, 0.0) + amt
                merchant_spend[merch] = merchant_spend.get(merch, 0.0) + amt
                merchant_count[merch] = merchant_count.get(merch, 0) + 1
                
        # Format currencies
        for k, v in spend_by_currency.items():
            spend_by_currency[k] = round(v, 2)
            
        # Compile top merchants
        top_merchants_sorted = sorted(merchant_spend.items(), key=lambda x: x[1], reverse=True)[:3]
        top_merchants_list = [
            {
                "merchant": merch,
                "spend": round(spend, 2),
                "count": merchant_count[merch]
            }
            for merch, spend in top_merchants_sorted
        ]
        
        # 3. Anomaly count
        anomaly_count = len(anomalies)
        risk_level = "LOW"
        if anomaly_count >= 5:
            risk_level = "HIGH"
        elif anomaly_count > 0:
            risk_level = "MEDIUM"
            
        # 4. Generate professional executive narrative
        currency_summary_str = ", ".join([f"{v} {k}" for k, v in spend_by_currency.items()])
        narrative = (
            f"The batch processes a total of {len(transactions)} transactions with a consolidated spend of {currency_summary_str}. "
            f"We detected {anomaly_count} anomalous activity flags, indicating a {risk_level} operational risk rating. "
            f"Key exposure is centered around {', '.join([m['merchant'] for m in top_merchants_list[:2]])}. "
            "Verification of high-risk outliers is recommended for final ledger reconciliation."
        )
        
        return {
            "total_spend": spend_by_currency,
            "top_merchants": top_merchants_list,
            "anomaly_count": anomaly_count,
            "financial_narrative": narrative,
            "risk_level": risk_level,
            "token_usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "fallback_triggered": True
            }
        }


class GeminiClient(BaseLLMClient):
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self._initialized = False
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self._initialized = True
                logger.info(f"Gemini LLM client initialized using model {self.model_name}.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set. Gemini Client will be disabled.")

    def _clean_json_response(self, text: str) -> str:
        """Strip markdown fences and trim text to extract raw JSON."""
        # Find start of JSON structure { or [
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            return match.group(1)
        return text

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _call_gemini_api(self, prompt: str) -> tuple[str, Dict[str, int]]:
        """Wraps API call in retries and fetches response content."""
        if not self._initialized:
            raise RuntimeError("Gemini client is not initialized.")
            
        logger.debug("Dispatching request to Gemini API.")
        # Configure JSON response type
        response = self.model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0
        }
        # Safely extract token counts from response if available
        try:
            if hasattr(response, "usage_metadata"):
                token_usage["prompt_tokens"] = response.usage_metadata.prompt_token_count
                token_usage["completion_tokens"] = response.usage_metadata.candidates_token_count
        except Exception:
            pass
            
        return response.text, token_usage

    def classify_transactions(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Gemini Client not initialized.")

        # Map list elements to simplified JSON payloads to minimize token footprint
        simplified = [
            {
                "index": item.get("index"),
                "merchant": item.get("merchant"),
                "amount": item.get("amount"),
                "currency": item.get("currency"),
                "notes": item.get("notes")
            }
            for item in transactions
        ]
        
        prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
            transactions_json=json.dumps(simplified, indent=2)
        )
        
        raw_resp, token_usage = self._call_gemini_api(prompt)
        cleaned_json = self._clean_json_response(raw_resp)
        data = json.loads(cleaned_json)
        data["token_usage"] = token_usage
        return data

    def generate_summary(self, transactions: List[Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Gemini Client not initialized.")

        simplified_txns = [
            {
                "merchant": t.get("merchant"),
                "amount": t.get("amount"),
                "currency": t.get("currency")
            }
            for t in transactions
        ]
        
        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            total_count=len(transactions),
            anomaly_count=len(anomalies),
            anomalies_json=json.dumps(anomalies[:15], indent=2),  # Limit to avoid token blowout
            transactions_json=json.dumps(simplified_txns[:50], indent=2)  # Representative subset
        )
        
        raw_resp, token_usage = self._call_gemini_api(prompt)
        cleaned_json = self._clean_json_response(raw_resp)
        data = json.loads(cleaned_json)
        data["token_usage"] = token_usage
        return data


class ResilientLLMClient(BaseLLMClient):
    """
    Wrapper Client with circuit-breaker behavior. 
    If Gemini Client fails multiple times or is not configured, 
    automatically falls back to MockLLMClient to avoid disrupting async pipelines.
    """
    def __init__(self):
        self.gemini = GeminiClient()
        self.mock = MockLLMClient()
        self.consecutive_failures = 0
        self.max_failures_before_fallback = 3
        self.circuit_broken = False

    def classify_transactions(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.circuit_broken or not self.gemini._initialized:
            return self.mock.classify_transactions(transactions)
            
        try:
            res = self.gemini.classify_transactions(transactions)
            self.consecutive_failures = 0  # reset failures on success
            return res
        except Exception as e:
            self.consecutive_failures += 1
            logger.error(f"Gemini API failure during classification (failures={self.consecutive_failures}): {e}")
            if self.consecutive_failures >= self.max_failures_before_fallback:
                logger.error("Circuit broken! Falling back to local MockLLMClient for all remaining classification tasks.")
                self.circuit_broken = True
            return self.mock.classify_transactions(transactions)

    def generate_summary(self, transactions: List[Dict[str, Any]], anomalies: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self.circuit_broken or not self.gemini._initialized:
            return self.mock.generate_summary(transactions, anomalies)
            
        try:
            res = self.gemini.generate_summary(transactions, anomalies)
            self.consecutive_failures = 0
            return res
        except Exception as e:
            self.consecutive_failures += 1
            logger.error(f"Gemini API failure during summary generation (failures={self.consecutive_failures}): {e}")
            if self.consecutive_failures >= self.max_failures_before_fallback:
                logger.error("Circuit broken! Falling back to local MockLLMClient for all remaining summary tasks.")
                self.circuit_broken = True
            return self.mock.generate_summary(transactions, anomalies)


# Expose a default resilient client
llm_client = ResilientLLMClient()
