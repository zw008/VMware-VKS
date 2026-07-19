"""List tools state their own completeness instead of leaving it inferred.

Source: VMware-AIops issue #31. Running the family against a local Llama 3.3
70B, the operator reported that "with long tool responses, it may omit existing
information or incorrectly state that no data was returned." A bare
``list[dict]`` gives a model no way to tell a whole answer from page one, so it
guesses — and a guess that reads "no data" looks like a finding.

Every read list tool here returns the family envelope. VKS reads its
collections in a single un-paged REST GET, so ``total`` is the real count and
``truncated`` is always False — "this is complete" stated outright.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vmware_vks.ops.namespace import list_namespaces, list_vm_classes
from vmware_vks.ops.supervisor import list_supervisor_storage_policies

ENVELOPE_KEYS = {"items", "returned", "limit", "total", "truncated", "hint"}


def _mock_si() -> MagicMock:
    si = MagicMock()
    si._stub.host = "vcenter.example.com"
    si.content.sessionManager.currentSession.key = "session-123"
    return si


# The three in-scope read list tools, with the ``_rest_get`` they call and a
# wire row that parses cleanly.
CASES = [
    pytest.param(
        list_namespaces,
        "vmware_vks.ops.namespace._rest_get",
        {"namespace": "dev", "config_status": "RUNNING", "description": ""},
        id="list_namespaces",
    ),
    pytest.param(
        list_vm_classes,
        "vmware_vks.ops.namespace._rest_get",
        {"id": "best-effort-large", "cpu_count": 4, "memory_MB": 8192},
        id="list_vm_classes",
    ),
    pytest.param(
        list_supervisor_storage_policies,
        "vmware_vks.ops.supervisor._rest_get",
        {"policy": "p-1", "name": "Gold", "description": ""},
        id="list_supervisor_storage_policies",
    ),
]


def _call(fn, rest_path: str, rows: list[dict]) -> dict:
    with patch(rest_path) as mock_get:
        mock_get.return_value = rows
        return fn(_mock_si())


# ---------------------------------------------------------------------------
# Shape — the six keys are the contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("fn", "rest_path", "row"), CASES)
def test_every_envelope_key_is_present(fn, rest_path, row) -> None:
    """Explicit nulls, never missing keys — a missing key invites invention."""
    result = _call(fn, rest_path, [row])
    assert ENVELOPE_KEYS <= set(result)


@pytest.mark.parametrize(("fn", "rest_path", "row"), CASES)
def test_returned_counts_the_items(fn, rest_path, row) -> None:
    result = _call(fn, rest_path, [row, dict(row)])
    assert result["returned"] == 2
    assert len(result["items"]) == 2


# ---------------------------------------------------------------------------
# Completeness — the whole point of the envelope on an un-paged endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("fn", "rest_path", "row"), CASES)
def test_result_is_reported_complete(fn, rest_path, row) -> None:
    """One un-paged GET returns the whole collection, so nothing is truncated.

    Stating ``truncated: false`` is the information the model needs: without
    it, a long list is indistinguishable from a first page.
    """
    result = _call(fn, rest_path, [row, dict(row)])
    assert result["truncated"] is False
    assert result["hint"] is None


@pytest.mark.parametrize(("fn", "rest_path", "row"), CASES)
def test_total_is_the_real_collection_size(fn, rest_path, row) -> None:
    """``total`` comes from the response itself, never an estimate."""
    result = _call(fn, rest_path, [row, dict(row), dict(row)])
    assert result["total"] == 3
    assert result["limit"] is None


@pytest.mark.parametrize(("fn", "rest_path", "row"), CASES)
def test_empty_collection_is_an_explicit_zero(fn, rest_path, row) -> None:
    """"No namespaces exist" must not read the same as "the call failed"."""
    result = _call(fn, rest_path, [])
    assert result["items"] == []
    assert result["returned"] == 0
    assert result["total"] == 0
    assert result["truncated"] is False
