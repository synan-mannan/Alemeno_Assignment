import traceback
from typing import Dict, Any, List
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.core.database import sync_session_maker
from app.models.job import Job
from app.models.transaction import Transaction
from app.models.summary import JobSummary
from app.pipelines.cleaner import clean_csv_payload
from app.pipelines.anomalies import AnomalyDetector
from app.llm.client import llm_client

# Celery task logger that binds to Celery context
logger = get_task_logger(__name__)


@celery_app.task(name="app.workers.tasks.process_transaction_job", bind=True, max_retries=3)
def process_transaction_job(self, job_id: str, csv_content: str) -> Dict[str, Any]:
    """
    Ingest, clean, enrich, analyze anomalies, and summarize transactions from CSV.
    """
    task_id = self.request.id
    logger.info(f"Starting transaction job {job_id} on Celery task {task_id}")
    
    db = sync_session_maker()
    
    try:
        # 1. Fetch Job
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found in database.")
            return {"status": "FAILED", "error": "Job not found"}
            
        # Update status and progress
        job.status = "PROCESSING"
        job.progress = 10
        db.commit()

        # 2. Parse & Clean CSV
        logger.info(f"Parsing CSV content for job {job_id}")
        try:
            cleaned_rows, parse_errors = clean_csv_payload(csv_content)
        except Exception as csv_err:
            logger.error(f"Failed to parse CSV: {csv_err}")
            job.status = "FAILED"
            job.progress = 100
            job.error_summary = {"system_error": f"CSV structure is malformed: {str(csv_err)}"}
            db.commit()
            return {"status": "FAILED", "error": str(csv_err)}

        job.progress = 35
        # Save validation errors if any
        job.error_summary = {"malformed_rows": parse_errors} if parse_errors else None
        db.commit()

        if not cleaned_rows:
            logger.warning(f"No valid rows found in CSV for job {job_id}")
            job.status = "COMPLETED"
            job.progress = 100
            db.commit()
            return {"status": "COMPLETED", "message": "No valid transactions to process"}

        # 3. LLM Classification (Batching uncategorized transactions)
        logger.info(f"Beginning LLM Classification for job {job_id}")
        
        # List transactions that need categorization (category is empty/None)
        uncategorized = []
        for index, item in enumerate(cleaned_rows):
            # Annotate index for correlation in batch responses
            item["index"] = index
            if not item.get("category"):
                uncategorized.append(item)

        total_tokens = {
            "classification": {"prompt_tokens": 0, "completion_tokens": 0, "fallback_triggered": False},
            "summary": {"prompt_tokens": 0, "completion_tokens": 0, "fallback_triggered": False}
        }

        # Process in batches of 25 to reduce token usage and respect context windows
        batch_size = 25
        if uncategorized:
            logger.info(f"Found {len(uncategorized)} uncategorized transactions. Running classification in batches.")
            for i in range(0, len(uncategorized), batch_size):
                batch = uncategorized[i : i + batch_size]
                try:
                    result = llm_client.classify_transactions(batch)
                    
                    # Track tokens
                    usage = result.get("token_usage", {})
                    total_tokens["classification"]["prompt_tokens"] += usage.get("prompt_tokens", 0)
                    total_tokens["classification"]["completion_tokens"] += usage.get("completion_tokens", 0)
                    if usage.get("fallback_triggered"):
                        total_tokens["classification"]["fallback_triggered"] = True

                    # Apply classifications back to our list
                    for classification in result.get("classifications", []):
                        idx = classification.get("index")
                        cat = classification.get("category")
                        if idx is not None and idx < len(cleaned_rows):
                            # Record original category as empty and update the cleaned category
                            cleaned_rows[idx]["category"] = cat
                            # Add categorization history to cleaning metadata
                            cleaned_rows[idx]["cleaning_metadata"]["category"] = {
                                "modified": True,
                                "original": "",
                                "cleaned": cat,
                                "reason": "Enriched category using LLM model classification."
                            }
                except Exception as llm_err:
                    logger.error(f"Failed classification for batch: {llm_err}. Gracefully continuing.")
                    
        job.progress = 65
        db.commit()

        # 4. Anomaly Detection
        logger.info(f"Running anomaly detection for job {job_id}")
        
        # Fetch accounts present in current batch
        account_ids = list(set(item["account_id"] for item in cleaned_rows if item.get("account_id")))
        
        # Query historical transactions for stats calculations
        historical_txns_db = db.query(Transaction).filter(
            Transaction.account_id.in_(account_ids)
        ).all()
        
        historical_txns = [
            {
                "txn_id": t.txn_id,
                "account_id": t.account_id,
                "amount": t.amount,
                "currency": t.currency,
                "merchant": t.merchant,
                "date": t.date,
                "notes": t.notes
            }
            for t in historical_txns_db
        ]

        # Run Anomaly Detector (updates transactions in-place)
        cleaned_rows = AnomalyDetector.process_anomalies(cleaned_rows, historical_txns)
        
        # Separate anomalies for summary generation
        anomalies = [txn for txn in cleaned_rows if txn.get("is_anomaly")]

        job.progress = 80
        db.commit()

        # 5. LLM Summary Generation
        logger.info(f"Generating LLM Summary for job {job_id}")
        try:
            summary_data = llm_client.generate_summary(cleaned_rows, anomalies)
            
            # Track tokens
            usage = summary_data.get("token_usage", {})
            total_tokens["summary"]["prompt_tokens"] = usage.get("prompt_tokens", 0)
            total_tokens["summary"]["completion_tokens"] = usage.get("completion_tokens", 0)
            if usage.get("fallback_triggered"):
                total_tokens["summary"]["fallback_triggered"] = True

            # Save summary object
            job_summary = JobSummary(
                job_id=job.id,
                total_spend=summary_data.get("total_spend", {}),
                top_merchants=summary_data.get("top_merchants", []),
                anomaly_count=len(anomalies),
                financial_narrative=summary_data.get("financial_narrative", ""),
                risk_level=summary_data.get("risk_level", "LOW").upper(),
                token_usage=total_tokens
            )
            db.add(job_summary)
        except Exception as sum_err:
            logger.error(f"Failed to generate summary: {sum_err}. Using generic default summary.")
            
            # Graceful summary fallback if both LLM and Mock fail somehow
            total_spend_fallback = {}
            for item in cleaned_rows:
                total_spend_fallback[item["currency"]] = total_spend_fallback.get(item["currency"], 0.0) + item["amount"]
            
            job_summary = JobSummary(
                job_id=job.id,
                total_spend={k: round(v, 2) for k, v in total_spend_fallback.items()},
                top_merchants=[],
                anomaly_count=len(anomalies),
                financial_narrative="LLM summary generation failed. Transactions have been cleaned and processed successfully.",
                risk_level="MEDIUM" if anomalies else "LOW",
                token_usage=total_tokens
            )
            db.add(job_summary)

        job.progress = 90
        db.commit()

        # 6. Bulk Save Transactions
        logger.info(f"Saving {len(cleaned_rows)} transactions to database for job {job_id}")
        
        transaction_models = []
        for item in cleaned_rows:
            # Create Model instances
            model = Transaction(
                job_id=job.id,
                txn_id=item["txn_id"],
                original_txn_id=item["original_txn_id"],
                date=item["date"],
                original_date=item["original_date"],
                merchant=item["merchant"],
                original_merchant=item["original_merchant"],
                amount=item["amount"],
                original_amount=item["original_amount"],
                currency=item["currency"],
                original_currency=item["original_currency"],
                status=item["status"],
                original_status=item["original_status"],
                category=item["category"],
                original_category=item["original_category"],
                account_id=item["account_id"],
                notes=item["notes"],
                original_notes=item["original_notes"],
                is_anomaly=item["is_anomaly"],
                anomalies=item["anomalies"],
                cleaning_metadata=item["cleaning_metadata"]
            )
            transaction_models.append(model)
            
        db.add_all(transaction_models)
        
        # 7. Finalize Job
        job.status = "COMPLETED"
        job.progress = 100
        # Update raw metadata with execution insights
        job.raw_metadata = {
            "total_records": len(cleaned_rows),
            "anomaly_records": len(anomalies),
            "validation_errors": len(parse_errors) if parse_errors else 0,
            "task_id": task_id
        }
        
        db.commit()
        logger.info(f"Successfully finalized job {job_id}")
        return {"status": "SUCCESS", "job_id": job_id}
        
    except Exception as exc:
        db.rollback()
        logger.exception(f"Unhandled exception in task for job {job_id}: {exc}")
        
        # Set Job to failed so the UI/API can display errors
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = "FAILED"
                job.progress = 100
                job.error_summary = {
                    "system_error": f"Unhandled exception during processing: {str(exc)}",
                    "traceback": traceback.format_exc()
                }
                db.commit()
        except Exception as db_exc:
            logger.error(f"Double fault: failed to update job status to FAILED: {db_exc}")
            
        # Reraise so Celery handles retries
        raise self.retry(exc=exc)
        
    finally:
        db.close()
