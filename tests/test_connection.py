"""Tests for vmware_vks.connection (unit, no real vCenter)."""
from unittest.mock import MagicMock, patch
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
