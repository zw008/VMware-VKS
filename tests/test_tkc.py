"""Tests for TKC ops (unit, no real vCenter/K8s)."""
from unittest.mock import MagicMock, patch
import pytest
from vmware_vks.ops.tkc import (
    generate_tkc_yaml,
    list_tkc_clusters,
    get_tkc_available_versions,
    delete_tkc_cluster,
)


def test_generate_tkc_yaml_contains_cluster_name():
    yaml_str = generate_tkc_yaml(
        name="my-cluster", namespace="dev",
        k8s_version="v1.28.4+vmware.1", vm_class="best-effort-large",
        control_plane_count=1, worker_count=3, storage_class="vsphere-storage",
    )
    assert "my-cluster" in yaml_str
    assert "best-effort-large" in yaml_str
    assert "Cluster" in yaml_str


def test_generate_tkc_yaml_invalid_worker_count():
    with pytest.raises(ValueError, match="worker_count"):
        generate_tkc_yaml(
            name="bad", namespace="dev", k8s_version="v1.28.4+vmware.1",
            vm_class="best-effort-large", control_plane_count=1,
            worker_count=0, storage_class="vsphere-storage",
        )


def test_generate_tkc_yaml_invalid_control_plane():
    with pytest.raises(ValueError, match="control_plane_count"):
        generate_tkc_yaml(
            name="bad", namespace="dev", k8s_version="v1.28.4+vmware.1",
            vm_class="best-effort-large", control_plane_count=2,
            worker_count=3, storage_class="vsphere-storage",
        )


def test_list_tkc_clusters_empty():
    si = MagicMock()
    mock_api = MagicMock()
    mock_api.list_namespaced_custom_object.return_value = {"items": []}
    with (
        patch("vmware_vks.ops.tkc._get_custom_objects_api", return_value=mock_api),
        # _resolve_tkc_version was added after this test; it hits Supervisor
        # discovery (_rest_get) and must be stubbed for the unit test.
        patch("vmware_vks.ops.tkc._resolve_tkc_version", return_value="v1alpha3"),
    ):
        result = list_tkc_clusters(si, namespace="dev")
    assert result["clusters"] == []
    assert result["total"] == 0


def test_delete_tkc_cluster_requires_confirmed():
    # dry_run=False + confirmed=False must be refused (workload guard clean).
    si = MagicMock()
    with patch("vmware_vks.ops.tkc._check_running_workloads", return_value=[]):
        with pytest.raises(ValueError, match="confirmed=True"):
            delete_tkc_cluster(si, "my-cluster", "dev", confirmed=False, dry_run=False)


def test_delete_tkc_cluster_dry_run():
    si = MagicMock()
    with patch("vmware_vks.ops.tkc._check_running_workloads", return_value=[]):
        result = delete_tkc_cluster(si, "my-cluster", "dev", confirmed=True, dry_run=True)
    assert result["dry_run"] is True


def test_delete_tkc_cluster_rejects_with_workloads():
    si = MagicMock()
    workloads = [{"kind": "Deployment", "name": "app", "namespace": "default"}]
    with patch("vmware_vks.ops.tkc._check_running_workloads", return_value=workloads):
        with pytest.raises(RuntimeError, match="Deployment/app"):
            delete_tkc_cluster(si, "my-cluster", "dev", confirmed=True, dry_run=False, force=False)
