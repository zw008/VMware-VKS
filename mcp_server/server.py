"""MCP server for VMware VKS (vSphere with Tanzu).

Exposes Supervisor and Namespace management via MCP stdio transport.

Tool categories
---------------
* **Read-only**: check_vks_compatibility, get_supervisor_status,
  list_supervisor_storage_policies, list_namespaces, get_namespace, list_vm_classes
* **Write** (dry_run=True by default): create_namespace, update_namespace
* **Write** (confirmed + TKC guard): delete_namespace

Security
--------
* Credentials loaded from ~/.vmware-vks/.env (chmod 600 recommended)
* stdio transport only — no network listener
* delete_namespace rejects if TKC clusters exist inside
* All write operations logged to ~/.vmware-vks/audit.log

Source: https://github.com/zw008/VMware-VKS
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from vmware_vks.config import load_config
from vmware_vks.connection import ConnectionManager
from vmware_vks.notify.audit import AuditLogger
from vmware_vks.ops.supervisor import (
    check_vks_compatibility,
    get_supervisor_status,
    list_supervisor_storage_policies,
)
from vmware_vks.ops.namespace import (
    create_namespace,
    delete_namespace,
    get_namespace,
    list_namespaces,
    list_vm_classes,
    update_namespace,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vmware-vks.mcp")

mcp = FastMCP("VMware VKS")
_audit = AuditLogger()

_conn_mgr: ConnectionManager | None = None


def _get_conn_mgr() -> ConnectionManager:
    global _conn_mgr
    if _conn_mgr is None:
        config_path = os.environ.get("VMWARE_VKS_CONFIG")
        config = load_config(Path(config_path) if config_path else None)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr


def _get_si(target: str | None = None):
    return _get_conn_mgr().connect(target)


# ---------------------------------------------------------------------------
# Supervisor tools
# ---------------------------------------------------------------------------

@mcp.tool()
def check_vks_compatibility(target: str | None = None) -> dict:
    """Check if this vCenter supports VKS (requires vSphere 8.x+).

    Returns: compatible (bool), vcenter_version, wcp_enabled_clusters, hint.
    Call this first before any VKS operations.
    """
    si = _get_si(target)
    from vmware_vks.ops import supervisor as _sup
    return _sup.check_vks_compatibility(si)


@mcp.tool()
def get_supervisor_status(cluster_id: str, target: str | None = None) -> dict:
    """Get Supervisor Cluster status.

    Args:
        cluster_id: Compute cluster MoRef ID (e.g. 'domain-c1').
        target: vCenter target name (uses default if not specified).

    Returns: config_status, kubernetes_status, api_server_endpoint, k8s_version.
    """
    si = _get_si(target)
    from vmware_vks.ops import supervisor as _sup
    return _sup.get_supervisor_status(si, cluster_id)


@mcp.tool()
def list_supervisor_storage_policies(target: str | None = None) -> list[dict]:
    """List storage policies available for Supervisor Namespaces.

    Returns list of storage policies with compatible cluster IDs.
    Use this to find valid storage_policy values before creating namespaces.
    """
    si = _get_si(target)
    from vmware_vks.ops import supervisor as _sup
    return _sup.list_supervisor_storage_policies(si)


# ---------------------------------------------------------------------------
# Namespace tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_namespaces(target: str | None = None) -> list[dict]:
    """List all vSphere Namespaces with status."""
    si = _get_si(target)
    from vmware_vks.ops import namespace as _ns
    return _ns.list_namespaces(si)


@mcp.tool()
def get_namespace(name: str, target: str | None = None) -> dict:
    """Get detailed information for a single vSphere Namespace.

    Args:
        name: Namespace name (e.g. 'dev', 'production').
        target: vCenter target name (uses default if not specified).
    """
    si = _get_si(target)
    from vmware_vks.ops import namespace as _ns
    return _ns.get_namespace(si, name)


@mcp.tool()
def create_namespace(
    name: str,
    cluster_id: str,
    storage_policy: str,
    cpu_limit: int | None = None,
    memory_limit_mib: int | None = None,
    description: str = "",
    dry_run: bool = True,
    target: str | None = None,
) -> dict:
    """Create a vSphere Namespace on a Supervisor Cluster.

    IMPORTANT: dry_run=True by default — set dry_run=False to actually create.

    Args:
        name: Namespace name (lowercase, no spaces).
        cluster_id: Supervisor cluster MoRef (use get_supervisor_status to find).
        storage_policy: Storage policy name (use list_supervisor_storage_policies).
        cpu_limit: CPU limit in MHz (optional).
        memory_limit_mib: Memory limit in MiB (optional).
        dry_run: Preview without creating (default: True).
    """
    si = _get_si(target)
    from vmware_vks.ops import namespace as _ns
    result = _ns.create_namespace(
        si, name=name, cluster_id=cluster_id, storage_policy=storage_policy,
        cpu_limit=cpu_limit, memory_limit_mib=memory_limit_mib,
        description=description, dry_run=dry_run,
    )
    if not dry_run:
        _audit.log(
            target=target or "default", operation="create_namespace",
            resource=name, parameters={"cluster_id": cluster_id, "storage_policy": storage_policy},
            result="success",
        )
    return result


@mcp.tool()
def update_namespace(
    name: str,
    cpu_limit: int | None = None,
    memory_limit_mib: int | None = None,
    storage_policy: str | None = None,
    target: str | None = None,
) -> dict:
    """Update vSphere Namespace resource quotas or storage policy.

    Args:
        name: Namespace name.
        cpu_limit: New CPU limit in MHz (optional).
        memory_limit_mib: New memory limit in MiB (optional).
        storage_policy: New storage policy name (optional).
    """
    si = _get_si(target)
    from vmware_vks.ops import namespace as _ns
    result = _ns.update_namespace(si, name, cpu_limit=cpu_limit,
                                  memory_limit_mib=memory_limit_mib,
                                  storage_policy=storage_policy)
    _audit.log(target=target or "default", operation="update_namespace",
               resource=name, parameters={}, result="success")
    return result


@mcp.tool()
def delete_namespace(
    name: str,
    confirmed: bool = False,
    dry_run: bool = True,
    target: str | None = None,
) -> dict:
    """Delete a vSphere Namespace.

    SAFETY: Rejects if TKC clusters exist inside. Delete TKC clusters first.
    IMPORTANT: dry_run=True by default — set dry_run=False AND confirmed=True to delete.

    Args:
        name: Namespace name to delete.
        confirmed: Must be True to proceed (safety gate).
        dry_run: Preview without deleting (default: True).
    """
    si = _get_si(target)
    from vmware_vks.ops import namespace as _ns
    result = _ns.delete_namespace(si, name, confirmed=confirmed, dry_run=dry_run)
    if not dry_run and confirmed:
        _audit.log(target=target or "default", operation="delete_namespace",
                   resource=name, parameters={}, result="success")
    return result


@mcp.tool()
def list_vm_classes(target: str | None = None) -> list[dict]:
    """List available VM classes for TKC node sizing.

    Returns list with id, cpu_count, memory_mib per VM class.
    Use the 'id' field when creating TKC clusters.
    """
    si = _get_si(target)
    from vmware_vks.ops import namespace as _ns
    return _ns.list_vm_classes(si)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
