"""Regression evals for list-call scaling hardening (2026-07).

Two low-risk scaling fixes:

S1. harbor.get_harbor_info — a per-registry detail (Harbor.Info) failure
    must degrade gracefully: the Summary entry is still reported with
    status/storage_used_mb=None, and the whole listing is NOT aborted.
    Non-dict summary entries are skipped rather than crashing the loop.
S2. tkc.list_tkc_clusters — the all-namespace list must page with
    limit/continue so a huge fleet never lands in one response. Output
    shape ({"total", "clusters"}) is preserved.

All REST/K8s traffic is mocked at the helper boundary.
"""
from unittest.mock import MagicMock, patch

from vmware_vks.ops.harbor import get_harbor_info
from vmware_vks.ops.tkc import _LIST_PAGE_LIMIT, list_tkc_clusters


def _mock_si():
    si = MagicMock()
    si._stub.host = "vcenter.example.com:443"
    return si


def test_harbor_degrades_on_failing_enrich():
    """A failing per-registry detail call keeps the entry (status=None)."""
    si = _mock_si()

    def fake_get(si_arg, path):
        if path == "/vcenter/content/registries/harbor":
            return [
                {
                    "cluster": "domain-c8",
                    "registry": "harbor-1",
                    "version": "v2.7.1",
                    "ui_access_url": "https://harbor.example.com",
                }
            ]
        # Per-registry detail blows up — must NOT abort the listing.
        raise RuntimeError("503 Service Unavailable")

    with patch("vmware_vks.ops.harbor._rest_get", side_effect=fake_get):
        result = get_harbor_info(si)

    assert "error" not in result
    assert len(result["registries"]) == 1
    entry = result["registries"][0]
    assert entry["id"] == "harbor-1"
    assert entry["version"] == "v2.7.1"
    # Enrichment failed → degraded fields stay None, keys unchanged.
    assert entry["status"] is None
    assert entry["storage_used_mb"] is None


def test_harbor_multi_registry_one_failure_does_not_abort():
    """With >1 registry, one bad detail call must not drop the others."""
    si = _mock_si()

    def fake_get(si_arg, path):
        if path == "/vcenter/content/registries/harbor":
            return [
                {"cluster": "c1", "registry": "good", "version": "v2",
                 "ui_access_url": "https://good"},
                {"cluster": "c2", "registry": "bad", "version": "v2",
                 "ui_access_url": "https://bad"},
            ]
        if path.endswith("/good"):
            return {"health": {"status": "HEALTHY"},
                    "storage": [{"used": 512}]}
        raise RuntimeError("boom")  # detail for 'bad'

    with patch("vmware_vks.ops.harbor._rest_get", side_effect=fake_get):
        result = get_harbor_info(si)

    ids = {r["id"]: r for r in result["registries"]}
    assert set(ids) == {"good", "bad"}
    assert ids["good"]["status"] == "HEALTHY"
    assert ids["good"]["storage_used_mb"] == 512
    assert ids["bad"]["status"] is None


def test_harbor_skips_non_dict_summary_entry():
    """A malformed (non-dict) summary entry is skipped, not fatal."""
    si = _mock_si()

    def fake_get(si_arg, path):
        if path == "/vcenter/content/registries/harbor":
            return ["garbage", {"cluster": "c1", "registry": "ok",
                                "version": "v2", "ui_access_url": "https://ok"}]
        return {"health": {"status": "HEALTHY"}, "storage": []}

    with patch("vmware_vks.ops.harbor._rest_get", side_effect=fake_get):
        result = get_harbor_info(si)

    assert [r["id"] for r in result["registries"]] == ["ok"]


def test_list_tkc_clusters_passes_limit():
    """The all-namespace list must request a bounded page (limit)."""
    si = _mock_si()
    mock_api = MagicMock()
    mock_api.list_cluster_custom_object.return_value = {"items": []}

    with (
        patch("vmware_vks.ops.tkc._get_custom_objects_api", return_value=mock_api),
        patch("vmware_vks.ops.tkc._resolve_tkc_version", return_value="v1beta1"),
    ):
        result = list_tkc_clusters(si)  # namespace=None → all namespaces

    assert result == {"total": 0, "clusters": []}
    _, kwargs = mock_api.list_cluster_custom_object.call_args
    assert kwargs["limit"] == _LIST_PAGE_LIMIT
    assert kwargs["_continue"] is None


def test_list_tkc_clusters_follows_continue_token():
    """Paging walks the continue token and concatenates pages, shape intact."""
    si = _mock_si()
    mock_api = MagicMock()

    def _item(name):
        return {
            "metadata": {"name": name, "namespace": "ns"},
            "status": {"phase": "Running"},
            "spec": {"topology": {"version": "v1.28"}},
        }

    pages = [
        {"items": [_item("a")], "metadata": {"continue": "TOKEN"}},
        {"items": [_item("b")], "metadata": {"continue": ""}},
    ]
    mock_api.list_cluster_custom_object.side_effect = pages

    with (
        patch("vmware_vks.ops.tkc._get_custom_objects_api", return_value=mock_api),
        patch("vmware_vks.ops.tkc._resolve_tkc_version", return_value="v1beta1"),
    ):
        result = list_tkc_clusters(si)

    assert result["total"] == 2
    assert [c["name"] for c in result["clusters"]] == ["a", "b"]
    # Second call must carry the continue token from page one.
    second_kwargs = mock_api.list_cluster_custom_object.call_args_list[1].kwargs
    assert second_kwargs["_continue"] == "TOKEN"
