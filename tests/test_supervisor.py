"""Tests for supervisor ops (unit, mocked ServiceInstance)."""
from unittest.mock import MagicMock, patch
import pytest
from vmware_vks.ops.supervisor import (
    check_vks_compatibility,
    get_supervisor_status,
    list_supervisor_storage_policies,
)


def _mock_si(version="8.0.2"):
    si = MagicMock()
    si.content.about.version = version
    si.content.about.build = "21290409"
    si.content.sessionManager.currentSession.key = "session-123"
    si._stub.host = "vcenter.example.com:443"
    return si


def test_get_supervisor_status_returns_dict():
    si = _mock_si()
    with patch("vmware_vks.ops.supervisor._rest_get") as mock_get:
        mock_get.return_value = {
            "config_status": "RUNNING",
            "kubernetes_status": "READY",
            "api_server_cluster_endpoint": "192.168.1.10:6443",
        }
        result = get_supervisor_status(si, "domain-c1")
    assert result["kubernetes_status"] == "READY"
    assert "api_server_cluster_endpoint" in result


def test_check_vks_compatibility_v8():
    si = _mock_si("8.0.2")
    with patch("vmware_vks.ops.supervisor._rest_get") as mock_get:
        mock_get.return_value = []
        result = check_vks_compatibility(si)
    assert result["vcenter_version"] == "8.0.2"
    assert result["compatible"] is True


def test_check_vks_compatibility_v7_fails():
    si = _mock_si("7.0.3")
    with patch("vmware_vks.ops.supervisor._rest_get") as mock_get:
        mock_get.return_value = []
        result = check_vks_compatibility(si)
    assert result["compatible"] is False
    assert result["hint"] is not None


def test_list_supervisor_storage_policies_returns_list():
    si = _mock_si()
    with patch("vmware_vks.ops.supervisor._rest_get") as mock_get:
        mock_get.return_value = [
            {"storage_policy": "vsphere-storage", "compatible_clusters": ["domain-c1"]}
        ]
        result = list_supervisor_storage_policies(si)
    assert isinstance(result, list)
    assert result[0]["storage_policy"] == "vsphere-storage"
