"""Tests for namespace ops."""
from unittest.mock import MagicMock, patch
import pytest
from vmware_vks.ops.namespace import (
    list_namespaces,
    get_namespace,
    create_namespace,
    update_namespace,
    delete_namespace,
    list_vm_classes,
)


def _mock_si():
    si = MagicMock()
    si.content.about.version = "8.0.2"
    si._stub.host = "vcenter.example.com:443"
    si.content.sessionManager.currentSession.key = "session-123"
    return si


def test_list_namespaces_returns_list():
    si = _mock_si()
    with patch("vmware_vks.ops.namespace._rest_get") as mock_get:
        mock_get.return_value = [
            {"namespace": "dev", "config_status": "RUNNING", "description": ""}
        ]
        result = list_namespaces(si)
    assert isinstance(result, list)
    assert result[0]["namespace"] == "dev"


def test_get_namespace_returns_dict():
    si = _mock_si()
    with patch("vmware_vks.ops.namespace._rest_get") as mock_get:
        mock_get.return_value = {
            "namespace": "dev",
            "config_status": "RUNNING",
            "resource_spec": {"cpu_limit": 4000, "memory_limit": 8192},
        }
        result = get_namespace(si, "dev")
    assert result["namespace"] == "dev"


def test_create_namespace_dry_run():
    si = _mock_si()
    result = create_namespace(
        si, name="dev", cluster_id="domain-c1",
        storage_policy="vsphere-storage", dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["action"] == "create_namespace"


def test_delete_namespace_requires_confirmed():
    si = _mock_si()
    with pytest.raises(ValueError, match="confirmed=True"):
        delete_namespace(si, "dev", confirmed=False)


def test_delete_namespace_rejects_if_tkc_exists():
    si = _mock_si()
    with patch("vmware_vks.ops.namespace._list_tkc_in_namespace") as mock_tkc:
        mock_tkc.return_value = ["cluster-a"]
        with pytest.raises(RuntimeError, match="cluster-a"):
            delete_namespace(si, "dev", confirmed=True)


def test_delete_namespace_dry_run():
    si = _mock_si()
    with patch("vmware_vks.ops.namespace._list_tkc_in_namespace") as mock_tkc:
        mock_tkc.return_value = []
        result = delete_namespace(si, "dev", confirmed=True, dry_run=True)
    assert result["dry_run"] is True


def test_list_vm_classes_returns_list():
    si = _mock_si()
    with patch("vmware_vks.ops.namespace._rest_get") as mock_get:
        mock_get.return_value = [
            {"id": "best-effort-large", "cpu_count": 4, "memory_mib": 8192}
        ]
        result = list_vm_classes(si)
    assert result[0]["id"] == "best-effort-large"
