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
    t = target or "default"
    params = {"cluster_id": cluster_id, "storage_policy": storage_policy}
    try:
        result = _ns.create_namespace(
            si, name=name, cluster_id=cluster_id, storage_policy=storage_policy,
            cpu_limit=cpu_limit, memory_limit_mib=memory_limit_mib,
            description=description, dry_run=dry_run,
        )
    except Exception as e:
        if not dry_run:
            _audit.log(
                target=t, operation="create_namespace",
                resource=name, parameters=params,
                result=f"failed: {e}",
            )
        raise
    if not dry_run:
        _audit.log(
            target=t, operation="create_namespace",
            resource=name, parameters=params,
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
    t = target or "default"
    try:
        result = _ns.update_namespace(si, name, cpu_limit=cpu_limit,
                                      memory_limit_mib=memory_limit_mib,
                                      storage_policy=storage_policy)
    except Exception as e:
        _audit.log(target=t, operation="update_namespace",
                   resource=name, parameters={}, result=f"failed: {e}")
        raise
    _audit.log(target=t, operation="update_namespace",
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
    t = target or "default"
    try:
        result = _ns.delete_namespace(si, name, confirmed=confirmed, dry_run=dry_run)
    except Exception as e:
        if not dry_run and confirmed:
            _audit.log(target=t, operation="delete_namespace",
                       resource=name, parameters={}, result=f"failed: {e}")
        raise
    if not dry_run and confirmed:
        _audit.log(target=t, operation="delete_namespace",
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


# ---------------------------------------------------------------------------
# TKC tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_tkc_clusters(namespace: str | None = None, target: str | None = None) -> dict:
    """List TanzuKubernetesCluster (TKC) clusters.

    Args:
        namespace: vSphere Namespace to filter by (lists all if not specified).
        target: vCenter target name.

    Returns: total count and list of clusters with status and K8s version.
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    return _tkc.list_tkc_clusters(si, namespace=namespace)


@mcp.tool()
def get_tkc_cluster(name: str, namespace: str, target: str | None = None) -> dict:
    """Get detailed info for a single TKC cluster.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace containing the cluster.
        target: vCenter target name.
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    return _tkc.get_tkc_cluster(si, name, namespace)


@mcp.tool()
def get_tkc_available_versions(namespace: str, target: str | None = None) -> dict:
    """List K8s versions available for new TKC clusters.

    Args:
        namespace: vSphere Namespace (used to connect to Supervisor).
        target: vCenter target name.
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    return _tkc.get_tkc_available_versions(si, namespace)


@mcp.tool()
def create_tkc_cluster(
    name: str,
    namespace: str,
    k8s_version: str,
    vm_class: str,
    control_plane_count: int = 1,
    worker_count: int = 3,
    storage_class: str = "vsphere-storage",
    dry_run: bool = True,
    target: str | None = None,
) -> dict:
    """Create a TanzuKubernetesCluster.

    IMPORTANT: dry_run=True by default — returns YAML plan. Set dry_run=False to apply.

    Workflow: call get_tkc_available_versions first to find valid k8s_version,
    call list_vm_classes to find valid vm_class.

    Args:
        name: Cluster name.
        namespace: vSphere Namespace.
        k8s_version: K8s version (e.g. 'v1.28.4+vmware.1').
        vm_class: VM class for nodes (e.g. 'best-effort-large').
        control_plane_count: 1 or 3.
        worker_count: Number of worker nodes (>= 1).
        storage_class: Storage class name.
        dry_run: Return YAML plan without applying (default: True).
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    params = {"k8s_version": k8s_version, "vm_class": vm_class, "workers": worker_count}
    try:
        result = _tkc.create_tkc_cluster(
            si, name=name, namespace=namespace, k8s_version=k8s_version,
            vm_class=vm_class, control_plane_count=control_plane_count,
            worker_count=worker_count, storage_class=storage_class, dry_run=dry_run,
        )
    except Exception as e:
        if not dry_run:
            _audit.log(
                target=t, operation="create_tkc_cluster",
                resource=f"{namespace}/{name}",
                parameters=params,
                result=f"failed: {e}",
            )
        raise
    if not dry_run:
        _audit.log(
            target=t, operation="create_tkc_cluster",
            resource=f"{namespace}/{name}",
            parameters=params,
            result="success",
        )
    return result


@mcp.tool()
def scale_tkc_cluster(
    name: str, namespace: str, worker_count: int, target: str | None = None
) -> dict:
    """Scale TKC cluster worker node count.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        worker_count: New worker node count (>= 1).
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    try:
        result = _tkc.scale_tkc_cluster(si, name, namespace, worker_count)
    except Exception as e:
        _audit.log(target=t, operation="scale_tkc_cluster",
                   resource=f"{namespace}/{name}", parameters={"worker_count": worker_count},
                   result=f"failed: {e}")
        raise
    _audit.log(target=t, operation="scale_tkc_cluster",
               resource=f"{namespace}/{name}", parameters={"worker_count": worker_count},
               result="success")
    return result


@mcp.tool()
def upgrade_tkc_cluster(
    name: str, namespace: str, k8s_version: str, target: str | None = None
) -> dict:
    """Upgrade TKC cluster to a new K8s version.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        k8s_version: Target K8s version (use get_tkc_available_versions to list).
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    try:
        result = _tkc.upgrade_tkc_cluster(si, name, namespace, k8s_version)
    except Exception as e:
        _audit.log(target=t, operation="upgrade_tkc_cluster",
                   resource=f"{namespace}/{name}", parameters={"k8s_version": k8s_version},
                   result=f"failed: {e}")
        raise
    _audit.log(target=t, operation="upgrade_tkc_cluster",
               resource=f"{namespace}/{name}", parameters={"k8s_version": k8s_version},
               result="success")
    return result


@mcp.tool()
def delete_tkc_cluster(
    name: str,
    namespace: str,
    confirmed: bool = False,
    dry_run: bool = True,
    force: bool = False,
    target: str | None = None,
) -> dict:
    """Delete a TKC cluster.

    SAFETY: Rejects if Deployments/StatefulSets are running (unless force=True).
    IMPORTANT: dry_run=True by default — set dry_run=False AND confirmed=True to delete.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        confirmed: Must be True to proceed (safety gate).
        dry_run: Preview without deleting (default: True).
        force: Skip workload check (dangerous).
    """
    si = _get_si(target)
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    try:
        result = _tkc.delete_tkc_cluster(
            si, name, namespace, confirmed=confirmed, dry_run=dry_run, force=force,
        )
    except Exception as e:
        if not dry_run and confirmed:
            _audit.log(target=t, operation="delete_tkc_cluster",
                       resource=f"{namespace}/{name}", parameters={"force": force},
                       result=f"failed: {e}")
        raise
    if not dry_run and confirmed:
        _audit.log(target=t, operation="delete_tkc_cluster",
                   resource=f"{namespace}/{name}", parameters={"force": force},
                   result="success")
    return result


# ---------------------------------------------------------------------------
# Access tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_supervisor_kubeconfig(namespace: str, target: str | None = None) -> dict:
    """Get kubeconfig for the Supervisor K8s API endpoint.

    Args:
        namespace: vSphere Namespace (context for the kubeconfig).
        target: vCenter target name.

    Returns: kubeconfig YAML string.
    """
    si = _get_si(target)
    from vmware_vks.ops import kubeconfig as _kc
    kc_str = _kc.get_supervisor_kubeconfig_str(si, namespace)
    return {"namespace": namespace, "kubeconfig": kc_str}


@mcp.tool()
def get_tkc_kubeconfig(
    name: str,
    namespace: str,
    output_path: str | None = None,
    target: str | None = None,
) -> dict:
    """Get kubeconfig for a TKC cluster.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        output_path: Write to file if provided (e.g. '~/.kube/my-cluster.yaml').
                     Returns kubeconfig string if not specified.
    """
    from pathlib import Path
    si = _get_si(target)
    from vmware_vks.ops import kubeconfig as _kc
    path = Path(output_path).expanduser() if output_path else None
    return _kc.write_kubeconfig(si, name, namespace, output_path=path)


@mcp.tool()
def get_harbor_info(target: str | None = None) -> dict:
    """Get embedded Harbor registry info (URL, storage usage, status).

    Returns registry URL, storage used, and health status.
    Returns error hint if Harbor is not enabled on this Supervisor.
    """
    si = _get_si(target)
    from vmware_vks.ops import harbor as _harbor
    return _harbor.get_harbor_info(si)


@mcp.tool()
def list_namespace_storage_usage(namespace: str, target: str | None = None) -> dict:
    """List PVCs and storage usage for a vSphere Namespace.

    Args:
        namespace: vSphere Namespace name.
        target: vCenter target name.
    """
    si = _get_si(target)
    from vmware_vks.ops import storage as _storage
    return _storage.list_namespace_storage_usage(si, namespace)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
