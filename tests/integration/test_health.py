"""Tests for the health-check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert "version" in body


@pytest.mark.asyncio
async def test_root_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "PandaProbe"
