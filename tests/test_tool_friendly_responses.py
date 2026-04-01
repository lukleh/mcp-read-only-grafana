"""Tests for MCP tool-level friendly fallback responses."""

from types import SimpleNamespace

import pytest

from mcp_read_only_grafana.exceptions import GrafanaAPIError
from mcp_read_only_grafana.tools.datasource_tools import (
    _get_datasource_health_result,
)
from mcp_read_only_grafana.tools.user_tools import _get_current_user_result


class StubConnector:
    """Small async stub for tool-level response helpers."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        current_user_result=None,
        current_user_error: Exception | None = None,
        datasource_health_result=None,
        datasource_health_error: Exception | None = None,
        datasources=None,
    ):
        self.connection = SimpleNamespace(api_key=api_key)
        self._current_user_result = current_user_result
        self._current_user_error = current_user_error
        self._datasource_health_result = datasource_health_result
        self._datasource_health_error = datasource_health_error
        self._datasources = datasources or []

    async def get_current_user(self):
        if self._current_user_error:
            raise self._current_user_error
        return self._current_user_result

    async def get_datasource_health(self, datasource_uid: str):
        if self._datasource_health_error:
            raise self._datasource_health_error
        return self._datasource_health_result

    async def list_datasources(self):
        return self._datasources


@pytest.mark.asyncio
async def test_get_current_user_result_returns_api_key_explanation():
    """API-key auth should return a structured explanation instead of a raw 404."""
    connector = StubConnector(
        api_key="service-account-token",
        current_user_error=GrafanaAPIError(404, '{"message":"user not found"}', "test"),
    )

    result = await _get_current_user_result(connector)

    assert result["status"] == "unavailable"
    assert result["reason"] == "api_key_auth_has_no_user_profile"
    assert result["auth_mode"] == "api_key"


@pytest.mark.asyncio
async def test_get_current_user_result_reraises_non_api_key_404():
    """Session-auth 404s should still bubble up for callers to investigate."""
    connector = StubConnector(
        current_user_error=GrafanaAPIError(404, '{"message":"user not found"}', "test"),
    )

    with pytest.raises(GrafanaAPIError) as exc_info:
        await _get_current_user_result(connector)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_datasource_health_result_returns_unsupported_for_existing_datasource():
    """Existing datasources with no health endpoint should return an unsupported payload."""
    connector = StubConnector(
        datasource_health_error=GrafanaAPIError(404, '{"message":"Not found"}', "test"),
        datasources=[
            {"uid": "prom-1", "name": "VictoriaMetrics", "type": "prometheus"},
        ],
    )

    result = await _get_datasource_health_result(connector, "prom-1")

    assert result["status"] == "unsupported"
    assert result["reason"] == "health_endpoint_not_implemented"
    assert result["datasource_name"] == "VictoriaMetrics"
    assert result["datasource_type"] == "prometheus"


@pytest.mark.asyncio
async def test_get_datasource_health_result_returns_not_found_for_unknown_uid():
    """Unknown datasource UIDs should report a structured not-found result."""
    connector = StubConnector(
        datasource_health_error=GrafanaAPIError(404, '{"message":"Not found"}', "test"),
        datasources=[
            {"uid": "postgres-1", "name": "Ops DB", "type": "postgres"},
        ],
    )

    result = await _get_datasource_health_result(connector, "missing-uid")

    assert result["status"] == "not_found"
    assert result["reason"] == "datasource_uid_not_found"
    assert result["datasource_uid"] == "missing-uid"


@pytest.mark.asyncio
async def test_get_datasource_health_result_reraises_non_404_errors():
    """Unexpected health-check errors should still surface to the caller."""
    connector = StubConnector(
        datasource_health_error=GrafanaAPIError(
            500, '{"message":"Unable to load datasource metadata"}', "test"
        ),
    )

    with pytest.raises(GrafanaAPIError) as exc_info:
        await _get_datasource_health_result(connector, "prom-1")

    assert exc_info.value.status_code == 500
