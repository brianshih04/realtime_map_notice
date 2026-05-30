"""Fixtures for cross-service integration tests. Requires docker compose up."""

import pytest
import httpx


@pytest.fixture(scope="session")
def location_url() -> str:
    return "http://localhost:8001"


@pytest.fixture(scope="session")
def event_url() -> str:
    return "http://localhost:8002"


@pytest.fixture(scope="session")
def notification_url() -> str:
    return "http://localhost:8003"


@pytest.fixture
async def location_client(location_url):
    async with httpx.AsyncClient(base_url=location_url, timeout=5.0) as client:
        yield client


@pytest.fixture
async def event_client(event_url):
    async with httpx.AsyncClient(base_url=event_url, timeout=5.0) as client:
        yield client


@pytest.fixture
async def notification_client(notification_url):
    async with httpx.AsyncClient(base_url=notification_url, timeout=5.0) as client:
        yield client
