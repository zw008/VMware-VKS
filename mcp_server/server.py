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
* All write operations audited twice: the central ~/.vmware/audit.db (SQLite,
  via the @vmware_tool decorator) plus a local JSON-Lines mirror at
  ~/.vmware-vks/audit.log

Source: https://github.com/zw008/VMware-VKS
"""

import logging
import os
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP
from vmware_policy import sanitize, vmware_tool

from vmware_vks.config import load_config
from vmware_vks.connection import ConnectionManager
from vmware_vks.errors import VksApiError
from vmware_vks.notify.audit import AuditLogger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vmware-vks.mcp")

def _safe_error(exc: Exception, tool: str) -> str:
    """Return an agent-safe error string; log full detail server-side only.

    Raw exception text can carry API response bodies, internal paths, or
    host:port pairs. Full traceback goes to the server log; the agent sees only
    a control-char-stripped, length-capped message. Intentional validation
    errors (ValueError/FileNotFoundError/KeyError/PermissionError) and
    teaching errors (VksApiError, already sanitized at the connection layer)
    pass through.
    """
    logger.error("Tool %s failed", tool, exc_info=True)
    if isinstance(
        exc, (VksApiError, ValueError, FileNotFoundError, KeyError, PermissionError)
    ):
        return sanitize(str(exc), 300)
    return f"{type(exc).__name__}: operation failed."


mcp = FastMCP("VMware VKS")
_audit = AuditLogger()

_conn_mgr: Optional[ConnectionManager] = None


def _get_conn_mgr() -> ConnectionManager:
    global _conn_mgr
    if _conn_mgr is None:
        config_path = os.environ.get("VMWARE_VKS_CONFIG")
        config = load_config(Path(config_path) if config_path else None)
        _conn_mgr = ConnectionManager(config)
    return _conn_mgr


def _get_si(target: Optional[str] = None):
    return _get_conn_mgr().connect(target)


# ---------------------------------------------------------------------------
# Supervisor tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def check_vks_compatibility(target: Optional[str] = None) -> dict:
    """[READ] Check if this vCenter supports VKS (requires vSphere 8.x+).

    Returns: compatible (bool), vcenter_version, wcp_enabled_clusters, hint.
    Call this first before any VKS operations.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import supervisor as _sup
        return _sup.check_vks_compatibility(si)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_supervisor_status(cluster_id: str, target: Optional[str] = None) -> dict:
    """[READ] Get the status of one Supervisor Cluster (vSphere with Tanzu control plane).

    Returns cluster_id, config_status (RUNNING = healthy, CONFIGURING, ERROR,
    REMOVING), kubernetes_status (READY / WARNING / ERROR),
    api_server_cluster_endpoint (Supervisor K8s API address),
    kubernetes_version (from the software/clusters endpoint; null plus a
    kubernetes_version_hint if that call fails), and network_provider.
    Read-only. Run
    check_vks_compatibility first to discover cluster IDs; use this to verify
    a Supervisor is healthy before creating namespaces or TKC clusters on it.

    Args:
        cluster_id: Compute cluster MoRef ID, e.g. 'domain-c1' (from the
            wcp_clusters field of check_vks_compatibility).
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import supervisor as _sup
        return _sup.get_supervisor_status(si, cluster_id)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_supervisor_storage_policies(target: Optional[str] = None) -> list[dict]:
    """[READ] List vCenter storage policies (the policies assigned to Supervisor Namespaces).

    Returns a list of {policy (policy ID), name (display name), description}.
    Returns all policies in one call — no pagination. Read-only, no side
    effects. Call this before create_namespace or update_namespace to obtain
    a valid storage_policy value (pass the 'policy' ID). For PVC-level usage
    inside a namespace, use list_namespace_storage_usage instead.

    Args:
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import supervisor as _sup
        return _sup.list_supervisor_storage_policies(si)
    except Exception as e:
        return [{"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}]


# ---------------------------------------------------------------------------
# Namespace tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_namespaces(target: Optional[str] = None) -> list[dict]:
    """[READ] List all vSphere Namespaces on the target vCenter with their configuration status.

    Returns a list of objects: namespace (name), config_status (RUNNING = healthy,
    CONFIGURING = being set up, REMOVING = being deleted, ERROR = failed), and
    description. Returns all namespaces in one call — no pagination. Read-only,
    no side effects. Use this to discover namespace names, then call
    get_namespace for full details of one, or update_namespace / delete_namespace
    to change it.

    Args:
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import namespace as _ns
        return _ns.list_namespaces(si)
    except Exception as e:
        return [{"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}]


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_namespace(name: str, target: Optional[str] = None) -> dict:
    """[READ] Get detailed information for a single vSphere Namespace.

    Args:
        name: Namespace name (e.g. 'dev', 'production').
        target: vCenter target name (uses default if not specified).
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import namespace as _ns
        return _ns.get_namespace(si, name)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_namespace(
    name: str,
    cluster_id: str,
    storage_policy: str,
    cpu_limit: Optional[int] = None,
    memory_limit_mib: Optional[int] = None,
    description: str = "",
    dry_run: bool = True,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a vSphere Namespace on a Supervisor Cluster.

    IMPORTANT: dry_run=True by default — set dry_run=False to actually create.

    Args:
        name: Namespace name (lowercase, no spaces).
        cluster_id: Supervisor cluster MoRef (use get_supervisor_status to find).
        storage_policy: Storage policy name (use list_supervisor_storage_policies).
        cpu_limit: CPU limit in MHz (optional).
        memory_limit_mib: Memory limit in MiB (optional).
        dry_run: Preview without creating (default: True).
    """
    from vmware_vks.ops import namespace as _ns
    t = target or "default"
    params = {"cluster_id": cluster_id, "storage_policy": storage_policy}
    try:
        si = _get_si(target)
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
                result=f"error: {sanitize(str(e), 200)}",
            )
        return {"error": _safe_error(e, "create_namespace")}
    if not dry_run:
        _audit.log(
            target=t, operation="create_namespace",
            resource=name, parameters=params,
            result="success",
        )
    return result


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def update_namespace(
    name: str,
    cpu_limit: Optional[int] = None,
    memory_limit_mib: Optional[int] = None,
    storage_policy: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Update resource quotas or storage policy of an existing vSphere Namespace.

    Only the fields you provide are patched; omitted fields keep their current
    values. If no field is provided, returns status "no_changes" without calling
    the API. On success returns {namespace, status: "updated"}. Applies
    immediately (no dry_run); not destructive. Audited to ~/.vmware/audit.db
    (SQLite) and ~/.vmware-vks/audit.log (JSON Lines).
    Use create_namespace for new namespaces; use list_supervisor_storage_policies
    to find valid storage_policy values.

    Args:
        name: Existing namespace name (discover via list_namespaces).
        cpu_limit: New CPU limit in MHz. Omit to keep current.
        memory_limit_mib: New memory limit in MiB. Omit to keep current.
        storage_policy: New storage policy name. Omit to keep current.
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    from vmware_vks.ops import namespace as _ns
    t = target or "default"
    try:
        si = _get_si(target)
        result = _ns.update_namespace(si, name, cpu_limit=cpu_limit,
                                      memory_limit_mib=memory_limit_mib,
                                      storage_policy=storage_policy)
    except Exception as e:
        _audit.log(target=t, operation="update_namespace",
                   resource=name, parameters={}, result=f"error: {sanitize(str(e), 200)}")
        return {"error": _safe_error(e, "update_namespace")}
    _audit.log(target=t, operation="update_namespace",
               resource=name, parameters={}, result="success")
    return result


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_namespace(
    name: str,
    confirmed: bool = False,
    dry_run: bool = True,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Delete a vSphere Namespace.

    SAFETY: Rejects if TKC clusters exist inside. Delete TKC clusters first.
    IMPORTANT: dry_run=True by default — set dry_run=False AND confirmed=True to delete.

    Args:
        name: Namespace name to delete.
        confirmed: Must be True to proceed (safety gate).
        dry_run: Preview without deleting (default: True).
    """
    from vmware_vks.ops import namespace as _ns
    t = target or "default"
    try:
        si = _get_si(target)
        result = _ns.delete_namespace(si, name, confirmed=confirmed, dry_run=dry_run)
    except Exception as e:
        if not dry_run and confirmed:
            _audit.log(target=t, operation="delete_namespace",
                       resource=name, parameters={}, result=f"error: {sanitize(str(e), 200)}")
        return {"error": _safe_error(e, "delete_namespace")}
    if not dry_run and confirmed:
        _audit.log(target=t, operation="delete_namespace",
                   resource=name, parameters={}, result="success")
    return result


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_vm_classes(target: Optional[str] = None) -> list[dict]:
    """[READ] List VM classes available for sizing TKC cluster nodes.

    Returns a list of {id (class name, e.g. 'best-effort-large'), cpu_count
    (vCPUs), memory_mb (RAM in MB), gpu_count (vGPU + dynamic DirectPath I/O
    devices; 0 if none)}. Returns all
    classes in one call — no pagination. Read-only, no side effects. Call this
    before create_tkc_cluster and pass the chosen 'id' as its vm_class
    argument; 'guaranteed-*' classes reserve resources, 'best-effort-*'
    classes do not.

    Args:
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import namespace as _ns
        return _ns.list_vm_classes(si)
    except Exception as e:
        return [{"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}]


# ---------------------------------------------------------------------------
# TKC tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_tkc_clusters(namespace: Optional[str] = None, target: Optional[str] = None) -> dict:
    """[READ] List TanzuKubernetesCluster (TKC) clusters.

    Args:
        namespace: vSphere Namespace to filter by (lists all if not specified).
        target: vCenter target name.

    Returns: total count and list of clusters with status and K8s version.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import tkc as _tkc
        return _tkc.list_tkc_clusters(si, namespace=namespace)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_tkc_cluster(name: str, namespace: str, target: Optional[str] = None) -> dict:
    """[READ] Get detailed info for a single TKC cluster.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace containing the cluster.
        target: vCenter target name.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import tkc as _tkc
        return _tkc.get_tkc_cluster(si, name, namespace)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_tkc_available_versions(namespace: str, target: Optional[str] = None) -> dict:
    """[READ] List Kubernetes versions (TanzuKubernetesReleases) available on the Supervisor.

    Returns {versions: [{name (release name), version (e.g.
    'v1.28.4+vmware.1')}]} sorted newest first. If the TanzuKubernetesRelease
    API is unavailable on this Supervisor, returns an empty versions list with
    error and hint fields instead of raising. Read-only, no side effects. Call
    this before create_tkc_cluster or upgrade_tkc_cluster to pick a valid
    k8s_version.

    Args:
        namespace: vSphere Namespace used to reach the Supervisor K8s API.
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import tkc as _tkc
        return _tkc.get_tkc_available_versions(si, namespace)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def create_tkc_cluster(
    name: str,
    namespace: str,
    k8s_version: str,
    vm_class: str,
    control_plane_count: int = 1,
    worker_count: int = 3,
    storage_class: str = "vsphere-storage",
    dry_run: bool = True,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Create a TanzuKubernetesCluster.

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
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    params = {"k8s_version": k8s_version, "vm_class": vm_class, "workers": worker_count}
    try:
        si = _get_si(target)
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
                result=f"error: {sanitize(str(e), 200)}",
            )
        return {"error": _safe_error(e, "create_tkc_cluster")}
    if not dry_run:
        _audit.log(
            target=t, operation="create_tkc_cluster",
            resource=f"{namespace}/{name}",
            parameters=params,
            result="success",
        )
    return result


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def scale_tkc_cluster(
    name: str,
    namespace: str,
    worker_count: int,
    pool_name: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Scale the worker node count of an existing TanzuKubernetesCluster (TKC).

    Asynchronous: patches the cluster spec and returns immediately with
    status "scaling" — node provisioning or removal continues in the
    background; poll get_tkc_cluster to watch progress. Scales workers only
    (control plane is unchanged); use upgrade_tkc_cluster to change the K8s
    version instead. Not destructive, but reducing worker_count drains the
    removed nodes. Audited to ~/.vmware/audit.db (SQLite) and
    ~/.vmware-vks/audit.log (JSON Lines).

    Args:
        name: TKC cluster name (discover via list_tkc_clusters).
        namespace: vSphere Namespace containing the cluster.
        worker_count: Desired total worker node count, integer >= 1 (values
            below 1 are rejected with an error).
        pool_name: Node pool (machineDeployment) to scale. Omit to scale the
            first existing pool. Other pools are always preserved.
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    params = {"worker_count": worker_count, "pool_name": pool_name}
    try:
        si = _get_si(target)
        result = _tkc.scale_tkc_cluster(
            si, name, namespace, worker_count, pool_name=pool_name
        )
    except Exception as e:
        _audit.log(target=t, operation="scale_tkc_cluster",
                   resource=f"{namespace}/{name}", parameters=params,
                   result=f"error: {sanitize(str(e), 200)}")
        return {"error": _safe_error(e, "scale_tkc_cluster")}
    _audit.log(target=t, operation="scale_tkc_cluster",
               resource=f"{namespace}/{name}", parameters=params,
               result="success")
    return result


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="medium")
def upgrade_tkc_cluster(
    name: str, namespace: str, k8s_version: str, target: Optional[str] = None
) -> dict:
    """[WRITE] Upgrade TKC cluster to a new K8s version.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        k8s_version: Target K8s version (use get_tkc_available_versions to list).
    """
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    try:
        si = _get_si(target)
        result = _tkc.upgrade_tkc_cluster(si, name, namespace, k8s_version)
    except Exception as e:
        _audit.log(target=t, operation="upgrade_tkc_cluster",
                   resource=f"{namespace}/{name}", parameters={"k8s_version": k8s_version},
                   result=f"error: {sanitize(str(e), 200)}")
        return {"error": _safe_error(e, "upgrade_tkc_cluster")}
    _audit.log(target=t, operation="upgrade_tkc_cluster",
               resource=f"{namespace}/{name}", parameters={"k8s_version": k8s_version},
               result="success")
    return result


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True})
@vmware_tool(risk_level="high")
def delete_tkc_cluster(
    name: str,
    namespace: str,
    confirmed: bool = False,
    dry_run: bool = True,
    force: bool = False,
    target: Optional[str] = None,
) -> dict:
    """[WRITE] Delete a TKC cluster.

    SAFETY: Rejects if Deployments/StatefulSets are running (unless force=True).
    IMPORTANT: dry_run=True by default — set dry_run=False AND confirmed=True to delete.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        confirmed: Must be True to proceed (safety gate).
        dry_run: Preview without deleting (default: True).
        force: Skip workload check (dangerous).
    """
    from vmware_vks.ops import tkc as _tkc
    t = target or "default"
    try:
        si = _get_si(target)
        result = _tkc.delete_tkc_cluster(
            si, name, namespace, confirmed=confirmed, dry_run=dry_run, force=force,
        )
    except Exception as e:
        if not dry_run and confirmed:
            _audit.log(target=t, operation="delete_tkc_cluster",
                       resource=f"{namespace}/{name}", parameters={"force": force},
                       result=f"error: {sanitize(str(e), 200)}")
        return {"error": _safe_error(e, "delete_tkc_cluster")}
    if not dry_run and confirmed:
        _audit.log(target=t, operation="delete_tkc_cluster",
                   resource=f"{namespace}/{name}", parameters={"force": force},
                   result="success")
    return result


# ---------------------------------------------------------------------------
# Access tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_supervisor_kubeconfig(namespace: str, target: Optional[str] = None) -> dict:
    """[READ] Get kubeconfig for the Supervisor K8s API endpoint.

    Security: The returned kubeconfig contains a short-lived session token.
    Treat the raw output as a credential — do not log or share.

    Args:
        namespace: vSphere Namespace (context for the kubeconfig).
        target: vCenter target name.

    Returns: kubeconfig YAML string.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import kubeconfig as _kc
        kc_str = _kc.get_supervisor_kubeconfig_str(si, namespace)
        return {"namespace": namespace, "kubeconfig": kc_str}
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_tkc_kubeconfig(
    name: str,
    namespace: str,
    output_path: Optional[str] = None,
    target: Optional[str] = None,
) -> dict:
    """[READ] Get kubeconfig for a TKC cluster.

    Security: The returned kubeconfig contains a short-lived session token.
    Prefer writing to file (output_path) over returning inline to reduce
    credential exposure in agent context.

    Args:
        name: TKC cluster name.
        namespace: vSphere Namespace.
        output_path: Write to file if provided (e.g. '~/.kube/my-cluster.yaml').
                     Returns kubeconfig string if not specified.
    """
    try:
        from pathlib import Path
        si = _get_si(target)
        from vmware_vks.ops import kubeconfig as _kc
        path = Path(output_path).expanduser() if output_path else None
        return _kc.write_kubeconfig(si, name, namespace, output_path=path)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def get_harbor_info(target: Optional[str] = None) -> dict:
    """[READ] Get status of the embedded Harbor container registry on the Supervisor.

    Returns {registries: [...]} where each entry has id (registry ID),
    cluster (Supervisor cluster MoRef), version, url (UI access URL),
    status (registry health, e.g. RUNNING), and storage_used_mb. Status and
    storage come from a per-registry detail call and are null if that call
    fails. If Harbor is
    not enabled on this Supervisor, returns {error, hint} instead of raising.
    Read-only, no side effects. Use this to check registry health or find the
    registry URL before pushing images; it does not list repositories or images.

    Args:
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import harbor as _harbor
        return _harbor.get_harbor_info(si)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
@vmware_tool(risk_level="low")
def list_namespace_storage_usage(namespace: str, target: Optional[str] = None) -> dict:
    """[READ] List PersistentVolumeClaims and storage usage inside one vSphere Namespace.

    Connects to the Supervisor K8s API and returns {namespace, pvc_count,
    pvcs: [{name, namespace, status (Bound / Pending / Lost), capacity
    (e.g. '10Gi'), storage_class}]}. Returns all PVCs — no pagination.
    Read-only, no side effects. Use list_namespaces to find namespace names;
    use list_supervisor_storage_policies for policy-level (not PVC-level)
    information.

    Args:
        namespace: vSphere Namespace name to inspect.
        target: Name of a vCenter entry in ~/.vmware-vks/config.yaml. Omit to
            use the default target defined in that file.
    """
    try:
        si = _get_si(target)
        from vmware_vks.ops import storage as _storage
        return _storage.list_namespace_storage_usage(si, namespace)
    except Exception as e:
        return {"error": _safe_error(e, "vks"), "hint": "Run 'vmware-vks doctor' to verify connectivity."}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
