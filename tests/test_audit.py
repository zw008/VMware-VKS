"""Tests for AuditLogger."""
import json
from unittest.mock import patch
import pytest
from vmware_vks.notify.audit import AuditLogger


def test_audit_log_writes_json_line(tmp_path):
    log_file = tmp_path / "audit.log"
    logger = AuditLogger(log_file=log_file)

    logger.log(
        target="vcenter.example.com",
        operation="create_namespace",
        resource="dev",
        parameters={"cluster_id": "domain-c1"},
        result="success",
        user="admin@vsphere.local",
    )

    content = log_file.read_text().strip()
    entry = json.loads(content)
    assert entry["target"] == "vcenter.example.com"
    assert entry["operation"] == "create_namespace"
    assert entry["resource"] == "dev"
    assert entry["parameters"] == {"cluster_id": "domain-c1"}
    assert entry["result"] == "success"
    assert entry["user"] == "admin@vsphere.local"
    assert "timestamp" in entry


def test_audit_log_creates_directory(tmp_path):
    nested_dir = tmp_path / "sub" / "dir"
    log_file = nested_dir / "audit.log"

    # Directory should not exist yet
    assert not nested_dir.exists()

    logger = AuditLogger(log_file=log_file)

    # Directory should be created by __init__
    assert nested_dir.exists()

    logger.log(
        target="vcenter.example.com",
        operation="test",
        resource="test-res",
        parameters={},
        result="ok",
    )
    assert log_file.exists()


def test_audit_log_appends(tmp_path):
    log_file = tmp_path / "audit.log"
    logger = AuditLogger(log_file=log_file)

    logger.log(
        target="vc1",
        operation="op1",
        resource="res1",
        parameters={},
        result="success",
    )
    logger.log(
        target="vc2",
        operation="op2",
        resource="res2",
        parameters={"key": "val"},
        result="failure",
    )

    lines = log_file.read_text().strip().split("\n")
    assert len(lines) == 2

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])
    assert entry1["target"] == "vc1"
    assert entry2["target"] == "vc2"
    assert entry2["result"] == "failure"
