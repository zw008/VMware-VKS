"""Tests for storage ops."""
from unittest.mock import MagicMock, patch, call
import pytest
from vmware_vks.ops.storage import list_namespace_storage_usage


def _mock_si():
    si = MagicMock()
    si.content.about.version = "8.0.2"
    si._stub.host = "vcenter.example.com:443"
    si.content.sessionManager.currentSession.key = "session-123"
    return si


def _make_pvc(name: str, namespace: str, phase: str, capacity_gb: str, sc: str):
    pvc = MagicMock()
    pvc.metadata.name = name
    pvc.metadata.namespace = namespace
    pvc.status.phase = phase
    pvc.status.capacity = {"storage": capacity_gb}
    pvc.spec.storage_class_name = sc
    return pvc


def test_list_namespace_storage_usage_returns_list():
    si = _mock_si()
    mock_api_client = MagicMock()
    mock_core_api = MagicMock()

    pvc1 = _make_pvc("data-vol", "dev", "Bound", "10Gi", "vsphere-storage")
    pvc2 = _make_pvc("log-vol", "dev", "Bound", "5Gi", "vsphere-storage")
    mock_core_api.list_namespaced_persistent_volume_claim.return_value = MagicMock(items=[pvc1, pvc2])

    with patch("vmware_vks.k8s_connection.get_k8s_client", return_value=mock_api_client):
        with patch("kubernetes.client.CoreV1Api", return_value=mock_core_api):
            result = list_namespace_storage_usage(si, "dev")

    assert result["namespace"] == "dev"
    assert result["pvc_count"] == 2
    assert len(result["pvcs"]) == 2
    assert result["pvcs"][0]["name"] == "data-vol"
    assert result["pvcs"][1]["capacity"] == "5Gi"


def test_list_namespace_storage_usage_uses_correct_namespace():
    """Regression test: verify namespace parameter is passed through to the k8s API call."""
    si = _mock_si()
    mock_api_client = MagicMock()
    mock_core_api = MagicMock()
    mock_core_api.list_namespaced_persistent_volume_claim.return_value = MagicMock(items=[])

    with patch("vmware_vks.k8s_connection.get_k8s_client", return_value=mock_api_client) as mock_get_client:
        with patch("kubernetes.client.CoreV1Api", return_value=mock_core_api):
            list_namespace_storage_usage(si, "production")

    # Verify the namespace was passed to both the k8s client and the PVC list call
    mock_get_client.assert_called_once_with(si, "production")
    mock_core_api.list_namespaced_persistent_volume_claim.assert_called_once_with(namespace="production")


def test_list_namespace_storage_usage_empty():
    si = _mock_si()
    mock_api_client = MagicMock()
    mock_core_api = MagicMock()
    mock_core_api.list_namespaced_persistent_volume_claim.return_value = MagicMock(items=[])

    with patch("vmware_vks.k8s_connection.get_k8s_client", return_value=mock_api_client):
        with patch("kubernetes.client.CoreV1Api", return_value=mock_core_api):
            result = list_namespace_storage_usage(si, "empty-ns")

    assert result["namespace"] == "empty-ns"
    assert result["pvc_count"] == 0
    assert result["pvcs"] == []
