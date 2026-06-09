# Prompts and output schemas for Gemini LLM Integration

CLASSIFICATION_PROMPT_TEMPLATE = """
You are a financial transactions classifier. Your task is to classify uncategorized financial transactions into exactly one of the following categories:
- Food
- Shopping
- Travel
- Transport
- Utilities
- Cash Withdrawal
- Entertainment
- Other

Here is a list of uncategorized transactions. Each transaction has a temporary identifier (index), merchant name, amount, currency, and notes:
{transactions_json}

INSTRUCTIONS:
1. Review each transaction's merchant, notes, and context.
2. Classify it into one of the designated categories above.
3. Respond ONLY with a valid JSON object matching the schema below.
4. Do not include any markdown format tags like ```json or ```, plain JSON text only.

JSON SCHEMA:
{{
  "classifications": [
    {{
      "index": 0,
      "category": "Food"
    }}
  ]
}}
"""

SUMMARY_PROMPT_TEMPLATE = """
You are a senior financial analyst and forensic accountant. Review the following summary of transactions and anomalies detected in a recently uploaded ledger batch.

METRIC SUMMARIES:
- Total Transactions: {total_count}
- Total Anomalous Transactions: {anomaly_count}

ANOMALOUS TRANSACTIONS DETAILS:
{anomalies_json}

ALL TRANSACTIONS OVERVIEW:
{transactions_json}

INSTRUCTIONS:
1. Analyze the transactions for overall financial health, high-spend areas, and potential risks (fraud, duplication, unauthorized activity).
2. Generate an executive financial narrative (2-4 sentences, professional, sounding like a startup fintech report).
3. Determine the overall Risk Level of the batch: LOW, MEDIUM, or HIGH.
4. Group total spend by currency (e.g., INR, USD).
5. Extract top merchants by spend amount (including name, spend amount, and count).
6. Return your entire response in raw JSON format matching the schema below.
7. Do not include markdown code block characters, return plain JSON.

JSON SCHEMA:
{{
  "total_spend": {{
    "INR": 145000.50,
    "USD": 2300.00
  }},
  "top_merchants": [
    {{
      "merchant": "Amazon",
      "spend": 12000.50,
      "count": 5
    }}
  ],
  "anomaly_count": {anomaly_count},
  "financial_narrative": "A detailed narrative of the transactions and risks...",
  "risk_level": "LOW"
}}
"""
