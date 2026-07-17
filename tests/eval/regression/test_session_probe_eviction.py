"""Regression — session liveness probe must evict dead cached sessions.

Family fix from an external fork report (VMware-AIops PR #32, 2026-07). VKS
used the real ``vim.fault.NotAuthenticated`` class so the raise path already
evicted correctly (pinned here to keep it that way), but shared the second
dead-session shape with the rest of the family:

An expired token can make ``sessionManager.currentSession`` return ``None``
without raising — a dead session that a raise-only probe treats as live.

Three shapes pinned: probe raises -> evict + reconnect; probe returns None ->
evict + reconnect; live session -> cache preserved (no reconnect). Side-store
eviction on the raise path is covered by tests/test_connection.py.
"""

from unittest.mock import MagicMock, patch

from vmware_vks.config import AppConfig, TargetConfig
from vmware_vks.connection import ConnectionManager


def _mgr() -> ConnectionManager:
    target = TargetConfig(name="vc1", host="vc.example.com", username="admin@vsphere.local")
    return ConnectionManager(AppConfig(targets=(target,)))


def _live_si() -> MagicMock:
    si = MagicMock()
    si.content.sessionManager.currentSession = MagicMock()
    return si


def test_probe_exception_evicts_and_reconnects():
    mgr = _mgr()
    dead_si = MagicMock()
    type(dead_si).content = property(
        lambda self: (_ for _ in ()).throw(Exception("session dead"))
    )
    mgr._connections["vc1"] = dead_si

    fresh_si = _live_si()
    with patch.object(mgr, "_create_connection", return_value=fresh_si) as create:
        result = mgr.connect("vc1")

    assert result is fresh_si
    create.assert_called_once()
    assert mgr._connections["vc1"] is fresh_si


def test_probe_none_session_evicts_and_reconnects():
    mgr = _mgr()
    dead_si = MagicMock()
    dead_si.content.sessionManager.currentSession = None
    mgr._connections["vc1"] = dead_si

    fresh_si = _live_si()
    with patch.object(mgr, "_create_connection", return_value=fresh_si) as create:
        result = mgr.connect("vc1")

    assert result is fresh_si
    create.assert_called_once()
    assert mgr._connections["vc1"] is fresh_si


def test_live_session_reused_without_reconnect():
    mgr = _mgr()
    live_si = _live_si()
    mgr._connections["vc1"] = live_si

    with patch.object(mgr, "_create_connection") as create:
        result = mgr.connect("vc1")

    assert result is live_si
    create.assert_not_called()
