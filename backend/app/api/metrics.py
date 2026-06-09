from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()


@router.get("/metrics")
def metrics_endpoint():
    """Exposes internal Prometheus metrics for scraper consumption."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
