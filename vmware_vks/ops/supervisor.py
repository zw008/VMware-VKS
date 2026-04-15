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

from vmware_policy import sanitize

_log = logging.getLogger("vmware-vks.ops.supervisor")

_MIN_VERSION = (8, 0, 0)

# Default REST request timeout in seconds — prevents indefinite hangs when
# the vCenter REST endpoint is unreachable or slow. Override with the
# ``VMWARE_VKS_REST_TIMEOUT`` env var.
_REST_TIMEOUT = 30


def _vcenter_host(si: ServiceInstance) -> str:
    return si._stub.host.split(":")[0]


def _build_ssl_context(si: ServiceInstance) -> ssl.SSLContext:
    """Build an SSL context that mirrors the pyVmomi connection's trust config.

    The connection manager tags the ``ServiceInstance`` with
    ``_vmware_vks_verify_ssl`` at connect time. When True we use the default
    verifying context; when False (self-signed / lab certificates) we disable
    hostname and cert verification. This replaces the previous hardcoded
    ``CERT_NONE`` which silently ignored ``target.verify_ssl: true`` in
    user config.
    """
    verify_ssl = getattr(si, "_vmware_vks_verify_ssl", True)
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _rest_request(
    si: ServiceInstance,
    method: str,
    path: str,
    body: dict | None = None,
) -> Any:
    """Authenticated REST request using the active pyVmomi session cookie.

    Handles GET/POST/PATCH/PUT/DELETE with uniform SSL verification and
    timeout behaviour. Returns parsed JSON on success; returns ``None`` when
    the response body is empty (e.g. DELETE).
    """
    host = _vcenter_host(si)
    session_id = si.content.sessionManager.currentSession.key
    url = f"https://{host}/api{path}"
    ctx = _build_ssl_context(si)

    headers = {"vmware-api-session-id": session_id}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=_REST_TIMEOUT) as resp:  # nosec B310
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"REST {method} {path} failed ({e.code}): {detail}") from e


def _rest_get(si: ServiceInstance, path: str) -> Any:
    """Authenticated REST GET using active pyVmomi session cookie."""
    return _rest_request(si, "GET", path)


def _rest_post(si: ServiceInstance, path: str, body: dict) -> Any:
    return _rest_request(si, "POST", path, body)


def _rest_patch(si: ServiceInstance, path: str, body: dict) -> Any:
    return _rest_request(si, "PATCH", path, body)


def _rest_delete(si: ServiceInstance, path: str) -> None:
    _rest_request(si, "DELETE", path)


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
        "api_server_cluster_endpoint": sanitize(data.get("api_server_cluster_endpoint", "")),
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
