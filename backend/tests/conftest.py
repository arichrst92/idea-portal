"""Pytest fixtures — shared across all tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client untuk simple endpoint tests."""
    return TestClient(app)
