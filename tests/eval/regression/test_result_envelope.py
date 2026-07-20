"""List tools state their own completeness instead of leaving it inferred.

Source: VMware-AIops issue #31. Running the family against a local Llama 3.3
70B, the operator reported that "with long tool responses, it may omit existing
information or incorrectly state that no data was returned." A bare
``list[dict]`` gives a model no way to tell a whole answer from page one, so it
guesses — and a guess that reads "no data" looks like a finding.

Every read list tool here returns the family envelope. VKS reads each
collection to exhaustion — a single un-paged REST GET, or a continue-token walk
for the Supervisor custom objects — so ``total`` is the real count and
``truncated`` is always False: "this is complete" stated outright.

All five list tools are covered. ``list_tkc_clusters`` and
``list_namespace_storage_usage`` returned their own hand-rolled shapes
(``{total, clusters}`` and ``{namespace, pvc_count, pvcs}``) until 2026-07-20,
which meant two of the five list surfaces gave an agent no truncation signal at
all. They are parametrised through the same assertions as the rest so the
contract is asserted in one place rather than restated per tool.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vmware_vks.ops.namespace import list_namespaces, list_vm_classes
from vmware_vks.ops.storage import list_namespace_storage_usage
from vmware_vks.ops.supervisor import list_supervisor_storage_policies
from vmware_vks.ops.tkc import list_tkc_clusters

ENVELOPE_KEYS = {"items", "returned", "limit", "total", "truncated", "hint"}


def _mock_si() -> MagicMock:
    si = MagicMock()
    si._stub.host = "vcenter.example.com"
    si.content.sessionManager.currentSession.key = "session-123"
    return si


def _rest_invoker(fn, rest_path: str, row: dict):
    """Build an invoker for a tool backed by a single ``_rest_get``."""

    def invoke(n: int) -> dict:
        with patch(rest_path) as mock_get:
            mock_get.return_value = [dict(row) for _ in range(n)]
            return fn(_mock_si())

    return invoke


def _tkc_invoker(n: int) -> dict:
    """``list_tkc_clusters`` goes through the Supervisor custom-objects API."""
    api = MagicMock()
    api.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {"name": f"c{i}", "namespace": "dev"},
                "status": {"phase": "Running"},
                "spec": {"topology": {"version": "v1.28"}},
            }
            for i in range(n)
        ]
    }
    with (
        patch("vmware_vks.ops.tkc._get_custom_objects_api", return_value=api),
        patch("vmware_vks.ops.tkc._resolve_tkc_version", return_value="v1beta1"),
    ):
        return list_tkc_clusters(_mock_si(), namespace="dev")


def _pvc_invoker(n: int) -> dict:
    """``list_namespace_storage_usage`` goes through the K8s CoreV1 API."""
    pvcs = []
    for i in range(n):
        pvc = MagicMock()
        pvc.metadata.name = f"vol-{i}"
        pvc.metadata.namespace = "dev"
        pvc.status.phase = "Bound"
        pvc.status.capacity = {"storage": "10Gi"}
        pvc.spec.storage_class_name = "vsphere-storage"
        pvcs.append(pvc)
    core = MagicMock()
    core.list_namespaced_persistent_volume_claim.return_value = MagicMock(items=pvcs)
    with (
        patch("vmware_vks.k8s_connection.get_k8s_client", return_value=MagicMock()),
        patch("kubernetes.client.CoreV1Api", return_value=core),
    ):
        return list_namespace_storage_usage(_mock_si(), "dev")


# Every read list tool, as an invoker taking a row count and returning the
# envelope. Uniform shape so the contract below is asserted once for all five.
CASES = [
    pytest.param(
        _rest_invoker(
            list_namespaces,
            "vmware_vks.ops.namespace._rest_get",
            {"namespace": "dev", "config_status": "RUNNING", "description": ""},
        ),
        id="list_namespaces",
    ),
    pytest.param(
        _rest_invoker(
            list_vm_classes,
            "vmware_vks.ops.namespace._rest_get",
            {"id": "best-effort-large", "cpu_count": 4, "memory_MB": 8192},
        ),
        id="list_vm_classes",
    ),
    pytest.param(
        _rest_invoker(
            list_supervisor_storage_policies,
            "vmware_vks.ops.supervisor._rest_get",
            {"policy": "p-1", "name": "Gold", "description": ""},
        ),
        id="list_supervisor_storage_policies",
    ),
    pytest.param(_tkc_invoker, id="list_tkc_clusters"),
    pytest.param(_pvc_invoker, id="list_namespace_storage_usage"),
]


# ---------------------------------------------------------------------------
# Shape — the six keys are the contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invoke", CASES)
def test_every_envelope_key_is_present(invoke) -> None:
    """Explicit nulls, never missing keys — a missing key invites invention."""
    result = invoke(1)
    assert ENVELOPE_KEYS <= set(result)


@pytest.mark.parametrize("invoke", CASES)
def test_returned_counts_the_items(invoke) -> None:
    result = invoke(2)
    assert result["returned"] == 2
    assert len(result["items"]) == 2


# ---------------------------------------------------------------------------
# Completeness — the whole point of the envelope on an un-paged endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invoke", CASES)
def test_result_is_reported_complete(invoke) -> None:
    """Each collection is read to exhaustion, so nothing is truncated.

    Stating ``truncated: false`` is the information the model needs: without
    it, a long list is indistinguishable from a first page.
    """
    result = invoke(2)
    assert result["truncated"] is False
    assert result["hint"] is None


@pytest.mark.parametrize("invoke", CASES)
def test_total_is_the_real_collection_size(invoke) -> None:
    """``total`` comes from the response itself, never an estimate."""
    result = invoke(3)
    assert result["total"] == 3
    assert result["limit"] is None


@pytest.mark.parametrize("invoke", CASES)
def test_empty_collection_is_an_explicit_zero(invoke) -> None:
    """"No namespaces exist" must not read the same as "the call failed"."""
    result = invoke(0)
    assert result["items"] == []
    assert result["returned"] == 0
    assert result["total"] == 0
    assert result["truncated"] is False


def test_storage_usage_keeps_the_queried_namespace() -> None:
    """The envelope's extras must not drop context the caller needs.

    ``list_namespace_storage_usage`` is the one list tool whose rows are
    meaningless without knowing which namespace was queried, so ``namespace``
    rides along as an envelope extra rather than being folded into the rows.
    """
    result = _pvc_invoker(1)
    assert result["namespace"] == "dev"
