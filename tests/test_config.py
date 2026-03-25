"""Tests for vmware_vks.config."""
import os
from pathlib import Path
import pytest
from vmware_vks.config import AppConfig, TargetConfig, load_config


def test_target_config_password_from_env(monkeypatch):
    monkeypatch.setenv("VMWARE_VKS_VCENTER01_PASSWORD", "secret123")
    t = TargetConfig(name="vcenter01", host="vc.example.com", username="admin@vsphere.local")
    assert t.password == "secret123"


def test_target_config_password_missing_raises(monkeypatch):
    monkeypatch.delenv("VMWARE_VKS_VCENTER01_PASSWORD", raising=False)
    t = TargetConfig(name="vcenter01", host="vc.example.com", username="admin@vsphere.local")
    with pytest.raises(OSError, match="VMWARE_VKS_VCENTER01_PASSWORD"):
        _ = t.password


def test_load_config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "targets:\n"
        "  - name: vc1\n"
        "    host: vc.example.com\n"
        "    username: admin@vsphere.local\n"
    )
    config = load_config(cfg_file)
    assert len(config.targets) == 1
    assert config.targets[0].name == "vc1"
    assert config.default_target.host == "vc.example.com"


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))


def test_get_target_not_found(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "targets:\n"
        "  - name: vc1\n"
        "    host: vc.example.com\n"
        "    username: admin@vsphere.local\n"
    )
    config = load_config(cfg_file)
    with pytest.raises(KeyError, match="vc2"):
        config.get_target("vc2")
