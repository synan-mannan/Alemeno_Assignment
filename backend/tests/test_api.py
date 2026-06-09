import uuid
from fastapi import status
from unittest.mock import patch, AsyncMock, MagicMock


def test_health_endpoint(client):
    response = client.get("/api/v1/system/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "healthy", "version": "1.0.0"}


@patch("redis.asyncio.from_url")
def test_readiness_endpoint_healthy(mock_redis, client, mock_db):
    # Setup database response mock
    mock_db.execute.return_value = CustomDBResultMock()
    
    # Setup redis response mock
    mock_redis_client = mock_redis.return_value
    mock_redis_client.ping = AsyncMock()
    mock_redis_client.close = AsyncMock()
    
    response = client.get("/api/v1/system/readiness")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ready"


def test_upload_invalid_extension(client):
    files = {"file": ("test.txt", b"some content", "text/plain")}
    response = client.post("/api/v1/jobs/upload", files=files)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid file format" in response.json()["detail"]


@patch("app.workers.tasks.process_transaction_job.delay")
def test_upload_success(mock_celery, client, mock_db):
    # Mock DB job creation response
    job_id = uuid.uuid4()
    mock_job = MagicMock()
    mock_job.id = job_id
    mock_job.filename = "test.csv"
    mock_job.status = "PENDING"
    
    # Mock repository call
    with patch("app.repositories.job.JobRepository.create", return_value=mock_job):
        files = {"file": ("test.csv", b"txn_id,date,merchant,amount,currency,status,category,account_id,notes\nTX1,04-09-2024,Flipkart,100,INR,SUCCESS,Shopping,ACC3,None\n", "text/csv")}
        response = client.post("/api/v1/jobs/upload", files=files)
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        json_data = response.json()
        assert json_data["filename"] == "test.csv"
        assert json_data["status"] == "PENDING"
        assert "job_id" in json_data
        
        # Verify celery tasks was enqueued
        mock_celery.assert_called_once()


def test_get_job_status_not_found(client, mock_db):
    with patch("app.repositories.job.JobRepository.get_by_id", return_value=None):
        job_uuid = uuid.uuid4()
        response = client.get(f"/api/v1/jobs/{job_uuid}/status")
        assert response.status_code == status.HTTP_404_NOT_FOUND


# Supporting mock classes for testing return values
class CustomDBResultMock(object):
    def __init__(self, *args, **kwargs):
        pass
    def scalar_one_or_none(self):
        return None
    def scalar(self):
        return 0
