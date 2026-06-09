from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import logger
from app.core.metrics import JOBS_IN_PROGRESS
from app.schemas.job import JobResponse, JobUploadResponse
from app.schemas.transaction import TransactionResponse
from app.schemas.summary import JobSummaryResponse
from app.repositories.job import JobRepository
from app.repositories.transaction import TransactionRepository
from app.workers.tasks import process_transaction_job

router = APIRouter()


@router.post(
    "/upload",
    response_model=JobUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload transaction CSV file",
)
async def upload_transactions(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts a CSV transaction ledger file, validates its type and size,
    and submits an asynchronous job to Celery for extraction and enrichment.
    """
    # 1. Validate file extension
    filename = file.filename or "unknown.csv"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        logger.warning(f"File upload rejected: Invalid extension '{ext}' for file '{filename}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Allowed extensions are: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    # 2. Read contents and validate size
    try:
        contents = await file.read()
        filesize = len(contents)
        if filesize > settings.MAX_FILE_SIZE_BYTES:
            logger.warning(f"File upload rejected: Size {filesize} bytes exceeds limit of {settings.MAX_FILE_SIZE_BYTES}")
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size limit of {settings.MAX_FILE_SIZE_BYTES / 1024 / 1024:.1f}MB."
            )
        csv_content = contents.decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Failed to read upload payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse uploaded file: {str(e)}"
        )

    # 3. Register Job in Database
    job = await JobRepository.create(db=db, filename=filename, filesize=filesize)
    logger.info(f"Registered job record {job.id} for file '{filename}'")

    # Increment Active Jobs metric
    JOBS_IN_PROGRESS.inc()

    # 4. Enqueue Asynchronous Celery Pipeline
    try:
        process_transaction_job.delay(str(job.id), csv_content)
        logger.info(f"Dispatched async Celery pipeline task for job {job.id}")
    except Exception as task_err:
        logger.exception(f"Failed to dispatch Celery task for job {job.id}: {task_err}")
        # Mark job as failed immediately if queuing fails
        job.status = "FAILED"
        job.progress = 100
        job.error_summary = {"system_error": "Failed to schedule job for worker processing."}
        await db.commit()
        JOBS_IN_PROGRESS.dec()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Worker queue is temporarily unavailable."
        )

    return {
        "job_id": job.id,
        "filename": job.filename,
        "status": job.status,
        "message": "Transaction ingestion pipeline queued successfully."
    }


@router.get(
    "/{job_id}/status",
    response_model=JobResponse,
    summary="Get job processing status",
)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves current execution progress and processing details of a job."""
    job = await JobRepository.get_by_id(db=db, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )
        
    # Decrement metrics if active job has resolved
    if job.status in ["COMPLETED", "FAILED"]:
        # Safety decrease (checks internally could be done, or let it decrease)
        # Note: Gauge updates should normally be task-driven, but we decrement safely here or let exporter handle it.
        pass
        
    return job


@router.get(
    "/{job_id}/results",
    summary="Get completed transaction results",
)
async def get_job_results(
    job_id: UUID,
    category: Optional[str] = Query(None, description="Filter transactions by category"),
    is_anomaly: Optional[bool] = Query(None, description="Filter transactions by anomaly flag"),
    account_id: Optional[str] = Query(None, description="Filter transactions by account ID"),
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(100, ge=1, le=500, description="Limit for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves the job execution summary and the list of processed, enriched,
    and anomaly-checked transactions. Supports filtering and pagination.
    """
    job = await JobRepository.get_by_id(db=db, job_id=job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {job_id} not found."
        )

    if job.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job processing is not finalized yet. Current status: {job.status}. Progress: {job.progress}%"
        )

    # 1. Fetch Job Summary
    summary = await JobRepository.get_summary_by_job_id(db=db, job_id=job_id)
    summary_resp = None
    if summary:
        summary_resp = JobSummaryResponse.model_validate(summary)

    # 2. Fetch Paginated Cleaned Transactions
    txns = await TransactionRepository.get_by_job_id(
        db=db,
        job_id=job_id,
        category=category,
        is_anomaly=is_anomaly,
        account_id=account_id,
        skip=skip,
        limit=limit
    )
    txns_resp = [TransactionResponse.model_validate(t) for t in txns]

    # 3. Total match count for pagination
    total_count = await TransactionRepository.count_by_job_id(
        db=db,
        job_id=job_id,
        category=category,
        is_anomaly=is_anomaly,
        account_id=account_id
    )

    return {
        "job_id": job.id,
        "filename": job.filename,
        "status": job.status,
        "summary": summary_resp,
        "transactions": txns_resp,
        "pagination": {
            "total": total_count,
            "skip": skip,
            "limit": limit
        }
    }


@router.get(
    "",
    response_model=List[JobResponse],
    summary="List all processing jobs",
)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Lists recent jobs uploaded to the platform, ordered by upload date."""
    jobs = await JobRepository.get_multi(db=db, skip=skip, limit=limit)
    return jobs
