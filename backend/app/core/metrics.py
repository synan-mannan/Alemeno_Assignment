from prometheus_client import Counter, Gauge, Histogram

# HTTP request tracking
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency",
    ["method", "endpoint"]
)

# Transaction Platform specific metrics
TRANSACTIONS_PROCESSED = Counter(
    "transactions_processed_total",
    "Total number of transactions processed",
    ["status"]
)

ANOMALIES_DETECTED = Counter(
    "anomalies_detected_total",
    "Total number of transaction anomalies flagged",
    ["rule_type"]
)

JOBS_IN_PROGRESS = Gauge(
    "jobs_in_progress_total",
    "Total number of jobs currently processing"
)

LLM_TOKEN_USAGE = Counter(
    "llm_token_usage_total",
    "Total number of LLM tokens consumed",
    ["task_type", "token_type"]
)
