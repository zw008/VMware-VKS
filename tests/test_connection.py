"""Tests for vmware_vks.connection (unit, no real vCenter)."""
from unittest.mock import MagicMock, patch
from vmware_vks import connection as conn_mod
from vmware_vks.config import AppConfig, TargetConfig
from vmware_vks.connection import ConnectionManager


def _make_config():
    target = TargetConfig(name="vc1", host="vc.example.com", username="admin@vsphere.local")
    return AppConfig(targets=(target,))


def test_connection_manager_list_targets():
    mgr = ConnectionManager(_make_config())
    assert mgr.list_targets() == ["vc1"]


def test_connection_manager_connect_reuses_session(monkeypatch):
    monkeypatch.setenv("VMWARE_VKS_VC1_PASSWORD", "pw")
    mgr = ConnectionManager(_make_config())

    mock_si = MagicMock()
    mock_si.content.sessionManager.currentSession = "active"

    with patch.object(mgr, "_create_connection", return_value=mock_si) as mock_create:
        si1 = mgr.connect("vc1")
        si2 = mgr.connect("vc1")
        assert si1 is si2
        mock_create.assert_called_once()


def test_connect_eviction_pops_id_si_side_stores(monkeypatch):
    """Evicting a stale session must drop its id(si)-keyed metadata immediately,
    not wait for atexit — otherwise GC + id() reuse leaks stale verify_ssl/target
    onto a new si for a different target (id-reuse hazard, code-review LOW)."""
    monkeypatch.setenv("VMWARE_VKS_VC1_PASSWORD", "pw")
    target = _make_config().targets[0]
    mgr = ConnectionManager(_make_config())

    stale_si = MagicMock()
    # Simulate a dead session: currentSession access raises -> triggers eviction.
    type(stale_si).content = property(
        lambda self: (_ for _ in ()).throw(Exception("session dead"))
    )
    fresh_si = MagicMock()
    fresh_si.content.sessionManager.currentSession = "active"

    # Seed the connection cache + side stores as if stale_si was a live connect().
    mgr._connections["vc1"] = stale_si
    key = id(stale_si)
    conn_mod._SI_VERIFY_SSL[key] = target.verify_ssl
    conn_mod._SI_TARGET[key] = target

    with patch.object(mgr, "_create_connection", return_value=fresh_si):
        result = mgr.connect("vc1")

    assert result is fresh_si
    # The stale si's side-store entries must be gone right now.
    assert key not in conn_mod._SI_VERIFY_SSL
    assert key not in conn_mod._SI_TARGET
