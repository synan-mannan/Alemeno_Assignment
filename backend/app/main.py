import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.metrics import router as metrics_router
from app.core.config import settings
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Scalable distributed pipeline to ingest transaction CSV files, perform NLP-based category classification, flag statistical anomalies, and generate financial summaries.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 1. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Logging and Telemetry Middleware
@app.middleware("http")
async def telemetry_and_logging_middleware(request: Request, call_next):
    # Retrieve or generate standard correlation ID
    request_id = request.headers.get("X-Request-ID")
    if not request_id:
        request_id = str(uuid.uuid4())

    # Inject correlation ID into Loguru execution thread context
    with logger.contextualize(request_id=request_id):
        start_time = time.perf_counter()
        path = request.url.path
        
        logger.info(f"HTTP Request Started: {request.method} '{path}'")
        
        try:
            response = await call_next(request)
        except Exception as err:
            duration = time.perf_counter() - start_time
            logger.exception(f"Unhandled server exception on {request.method} '{path}': {err}")
            
            # Record failed request metric
            REQUEST_COUNT.labels(method=request.method, endpoint=path, http_status=500).inc()
            REQUEST_LATENCY.labels(method=request.method, endpoint=path).observe(duration)
            raise err

        duration = time.perf_counter() - start_time
        
        # Inject headers in response for downstream debugging
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.4f}s"
        
        # Record metrics (excluding metrics endpoint itself to avoid scraping noise)
        if path != "/metrics":
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=path,
                http_status=response.status_code
            ).inc()
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=path
            ).observe(duration)

        logger.info(
            f"HTTP Request Completed: {request.method} '{path}' -> {response.status_code} in {duration:.4f}s"
        )
        return response


# 3. Mount Routers
app.include_router(health_router, prefix=f"{settings.API_V1_STR}/system", tags=["System & Health"])
app.include_router(jobs_router, prefix=f"{settings.API_V1_STR}/jobs", tags=["Transaction Jobs"])
app.include_router(metrics_router, tags=["Telemetry"])


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing API application servers.")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Gracefully stopping API application servers.")
