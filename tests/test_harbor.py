"""Tests for harbor ops."""
from unittest.mock import MagicMock, patch
import pytest
from vmware_vks.ops.harbor import get_harbor_info


def _mock_si():
    si = MagicMock()
    si.content.about.version = "8.0.2"
    si._stub.host = "vcenter.example.com:443"
    si.content.sessionManager.currentSession.key = "session-123"
    return si


def test_get_harbor_info_returns_dict():
    si = _mock_si()
    with patch("vmware_vks.ops.harbor._rest_get") as mock_get:
        mock_get.return_value = [
            {
                "id": "harbor-1",
                "ui_access_url": "https://harbor.example.com",
                "storage_used_MB": 1024,
                "health": {"status": "HEALTHY"},
            }
        ]
        result = get_harbor_info(si)

    assert isinstance(result, dict)
    assert "registries" in result
    assert len(result["registries"]) == 1
    assert result["registries"][0]["url"] == "https://harbor.example.com"
    assert result["registries"][0]["storage_used_mb"] == 1024
    assert result["registries"][0]["status"] == "HEALTHY"


def test_get_harbor_info_not_configured():
    si = _mock_si()
    with patch("vmware_vks.ops.harbor._rest_get") as mock_get:
        mock_get.side_effect = Exception("404 Not Found")
        result = get_harbor_info(si)

    assert isinstance(result, dict)
    assert "error" in result
    assert "404" in result["error"]
    assert "hint" in result
