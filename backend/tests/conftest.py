import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

# Set test environment settings
import os
os.environ["ENV"] = "testing"

from app.main import app
from app.api.deps import get_db


@pytest.fixture
def mock_db():
    """Returns a mocked database session."""
    session = MagicMock()
    # Stub database execution returns
    session.execute = AsyncMock()
    return session


@pytest.fixture
def client(mock_db):
    """Returns a test client with overridden database dependencies."""
    def _get_db_override():
        yield mock_db

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
