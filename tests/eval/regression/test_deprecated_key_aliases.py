"""Regression — the v1.8.0 envelope renamed two VKS payload keys in silence.

Source: the v1.8.6 audit of the v1.8.0 envelope conversion.

v1.8.0 wrapped every ``[READ]`` list tool in the family envelope. For the 51
tools that had returned a bare ``list[dict]`` that broke loudly: ``result[0]``
raises on a dict, so the caller finds out on the first run.

Two VKS tools were not in those 51. Both already returned a keyed dict, so the
conversion changed only the name of the key holding the rows:

===============================  ==============================  ==========
tool                             v1.7.7                          v1.8.0
===============================  ==============================  ==========
``list_tkc_clusters``            ``{total, clusters}``           ``clusters`` -> ``items``
``list_namespace_storage_usage`` ``{namespace, pvc_count, pvcs}``  ``pvcs`` -> ``items``, ``pvc_count`` deleted
===============================  ==============================  ==========

A pre-v1.8.0 caller written as ``result.get("clusters", [])`` kept running and
silently saw zero clusters -- which reads as "this namespace is empty", not as
a failure. ``pvc_count`` vanished outright, so a caller indexing it got a
``KeyError`` only if it used ``[]`` and nothing at all if it used ``.get``.

This file also fixes an omission of its own: ``tests/eval/regression/
test_result_envelope.py`` has recorded both old shapes in its module docstring
since 2026-07-20, so the shapes were known here while the release notes still
told every reader the change only affected bare arrays.

The fix is a compatibility alias, not a revert: ``items`` remains the primary
key, the old keys point at the *same list object*, and they go away in 2.0.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vmware_vks.ops.storage import list_namespace_storage_usage
from vmware_vks.ops.tkc import list_tkc_clusters

ENVELOPE_KEYS = ("items", "returned", "limit", "total", "truncated", "hint")


def _mock_si() -> MagicMock:
    si = MagicMock()
    si._stub.host = "vcenter.example.com"
    si.content.sessionManager.currentSession.key = "session-123"
    return si


def _clusters(n: int) -> dict:
    """``list_tkc_clusters`` via the Supervisor custom-objects API."""
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


def _pvcs(n: int) -> dict:
    """``list_namespace_storage_usage`` via the K8s CoreV1 API."""
    rows = []
    for i in range(n):
        pvc = MagicMock()
        pvc.metadata.name = f"vol-{i}"
        pvc.metadata.namespace = "dev"
        pvc.status.phase = "Bound"
        pvc.status.capacity = {"storage": "10Gi"}
        pvc.spec.storage_class_name = "vsphere-storage"
        rows.append(pvc)
    core = MagicMock()
    core.list_namespaced_persistent_volume_claim.return_value = MagicMock(items=rows)
    with (
        patch("vmware_vks.k8s_connection.get_k8s_client", return_value=MagicMock()),
        patch("kubernetes.client.CoreV1Api", return_value=core),
    ):
        return list_namespace_storage_usage(_mock_si(), "dev")


# ---------------------------------------------------------------------------
# list_tkc_clusters — "clusters"
# ---------------------------------------------------------------------------


def test_pre_1_8_0_caller_still_sees_the_clusters() -> None:
    """``result.get("clusters", [])`` must not answer "none" when there are three.

    The regression verbatim: the default in ``.get`` is what made the break
    silent, so it is written with the default in place.
    """
    assert len(_clusters(3).get("clusters", [])) == 3


def test_clusters_is_the_same_object_as_items() -> None:
    """Identity, not equality — a copy would let the two drift apart."""
    result = _clusters(3)
    assert result["clusters"] is result["items"]


def test_clusters_alias_tracks_items_through_mutation() -> None:
    """Proves the identity above is real rather than incidentally equal."""
    result = _clusters(2)
    result["items"].append({"name": "c-late"})
    assert result["clusters"][-1] == {"name": "c-late"}


def test_empty_cluster_list_is_an_explicit_empty_list() -> None:
    """"No TKC clusters here" must stay distinguishable from a dropped key."""
    result = _clusters(0)
    assert "clusters" in result
    assert result["clusters"] == []


def test_cluster_envelope_remains_intact() -> None:
    """The alias is additive; the envelope is still the primary shape."""
    result = _clusters(3)
    assert set(ENVELOPE_KEYS) <= set(result)
    assert result["items"] == result["clusters"]
    assert result["returned"] == 3
    assert result["total"] == 3
    assert result["truncated"] is False


# ---------------------------------------------------------------------------
# list_namespace_storage_usage — "pvcs" and the deleted "pvc_count"
# ---------------------------------------------------------------------------


def test_pre_1_8_0_caller_still_sees_the_pvcs() -> None:
    assert len(_pvcs(3).get("pvcs", [])) == 3


def test_pvcs_is_the_same_object_as_items() -> None:
    result = _pvcs(3)
    assert result["pvcs"] is result["items"]


def test_pvcs_alias_tracks_items_through_mutation() -> None:
    result = _pvcs(2)
    result["items"].append({"name": "vol-late"})
    assert result["pvcs"][-1] == {"name": "vol-late"}


def test_pvc_count_is_restored() -> None:
    """``pvc_count`` was deleted outright, not renamed — put it back.

    It is derived from ``returned`` rather than recomputed, so it cannot
    disagree with the list it counts.
    """
    result = _pvcs(3)
    assert result["pvc_count"] == 3
    assert result["pvc_count"] == len(result["pvcs"])
    assert result["pvc_count"] == result["returned"]


def test_empty_namespace_reports_zero_pvcs_explicitly() -> None:
    """A namespace with no storage must say so, not go quiet."""
    result = _pvcs(0)
    assert "pvcs" in result
    assert result["pvcs"] == []
    assert result["pvc_count"] == 0


def test_storage_envelope_remains_intact() -> None:
    result = _pvcs(3)
    assert set(ENVELOPE_KEYS) <= set(result)
    assert result["namespace"] == "dev"
    assert result["returned"] == 3
    assert result["truncated"] is False
