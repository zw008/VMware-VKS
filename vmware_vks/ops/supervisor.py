"""Supervisor layer operations (read-only).

Uses vCenter REST API via urllib (same session cookie as pyVmomi).
All functions take (si: ServiceInstance) as first argument.
"""
from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-vks.ops.supervisor")

_MIN_VERSION = (8, 0, 0)


def _vcenter_host(si: ServiceInstance) -> str:
    return si._stub.host.split(":")[0]


def _rest_get(si: ServiceInstance, path: str) -> Any:
    """Authenticated REST GET using active pyVmomi session cookie."""
    host = _vcenter_host(si)
    session_id = si.content.sessionManager.currentSession.key
    url = f"https://{host}/api{path}"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers={"vmware-api-session-id": session_id})
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:  # nosec B310
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"REST GET {path} failed ({e.code}): {body}") from e


def check_vks_compatibility(si: ServiceInstance) -> dict:
    """Check if this vCenter supports VKS (vSphere 8.x+)."""
    about = si.content.about
    version_str = about.version
    parts = tuple(int(x) for x in version_str.split(".")[:3])
    compatible = parts >= _MIN_VERSION

    try:
        clusters = _rest_get(si, "/vcenter/namespace-management/clusters")
    except Exception:
        clusters = []

    enabled = [c for c in clusters if c.get("config_status") == "RUNNING"]

    return {
        "compatible": compatible,
        "vcenter_version": version_str,
        "vcenter_build": about.build,
        "min_required_version": "8.0.0",
        "wcp_enabled_clusters": len(enabled),
        "wcp_clusters": [
            {"cluster": c.get("cluster"), "status": c.get("config_status")}
            for c in clusters
        ],
        "hint": None if compatible else "VKS requires vSphere 8.0+. Upgrade vCenter.",
    }


def get_supervisor_status(si: ServiceInstance, cluster_id: str) -> dict:
    """Get Supervisor Cluster status for a given compute cluster MoRef ID."""
    data = _rest_get(si, f"/vcenter/namespace-management/clusters/{cluster_id}")
    return {
        "cluster_id": cluster_id,
        "config_status": data.get("config_status"),
        "kubernetes_status": data.get("kubernetes_status"),
        "api_server_cluster_endpoint": data.get("api_server_cluster_endpoint"),
        "kubernetes_version": data.get("current_kubernetes_version"),
        "network_provider": data.get("network_provider"),
    }


def list_supervisor_storage_policies(si: ServiceInstance) -> list[dict]:
    """List storage policies compatible with Supervisor Namespaces."""
    data = _rest_get(si, "/vcenter/namespace-management/storage/storage-policies")
    return [
        {
            "storage_policy": item.get("storage_policy"),
            "compatible_clusters": item.get("compatible_clusters", []),
        }
        for item in (data if isinstance(data, list) else [])
    ]
