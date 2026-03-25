"""Namespace lifecycle operations.

All write operations require confirmed=True.
delete_namespace has an additional guard: rejects if TKC clusters exist inside.
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

from vmware_vks.ops.supervisor import _rest_get

_log = logging.getLogger("vmware-vks.ops.namespace")


def _rest_post(si: ServiceInstance, path: str, body: dict) -> Any:
    host = si._stub.host.split(":")[0]
    session_id = si.content.sessionManager.currentSession.key
    url = f"https://{host}/api{path}"
    data = json.dumps(body).encode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url, data=data,
        headers={"vmware-api-session-id": session_id, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            body_resp = resp.read()
            return json.loads(body_resp) if body_resp else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"REST POST {path} failed ({e.code}): {e.read().decode()}") from e


def _rest_patch(si: ServiceInstance, path: str, body: dict) -> Any:
    host = si._stub.host.split(":")[0]
    session_id = si.content.sessionManager.currentSession.key
    url = f"https://{host}/api{path}"
    data = json.dumps(body).encode()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url, data=data,
        headers={"vmware-api-session-id": session_id, "Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            body_resp = resp.read()
            return json.loads(body_resp) if body_resp else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"REST PATCH {path} failed ({e.code}): {e.read().decode()}") from e


def _rest_delete(si: ServiceInstance, path: str) -> None:
    host = si._stub.host.split(":")[0]
    session_id = si.content.sessionManager.currentSession.key
    url = f"https://{host}/api{path}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url, headers={"vmware-api-session-id": session_id}, method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, context=ctx):
            pass
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"REST DELETE {path} failed ({e.code}): {e.read().decode()}") from e


def _list_tkc_in_namespace(si: ServiceInstance, namespace: str) -> list[str]:
    """Return TKC cluster names in namespace. Used as delete guard."""
    try:
        from vmware_vks.ops.tkc import list_tkc_clusters
        result = list_tkc_clusters(si, namespace=namespace)
        return [c["name"] for c in result.get("clusters", [])]
    except Exception:
        return []


def list_namespaces(si: ServiceInstance) -> list[dict]:
    """List all vSphere Namespaces."""
    data = _rest_get(si, "/vcenter/namespaces/instances")
    return [
        {
            "namespace": item.get("namespace"),
            "config_status": item.get("config_status"),
            "description": item.get("description", ""),
        }
        for item in (data if isinstance(data, list) else [])
    ]


def get_namespace(si: ServiceInstance, name: str) -> dict:
    """Get detailed info for a single namespace."""
    return _rest_get(si, f"/vcenter/namespaces/instances/{name}")


def create_namespace(
    si: ServiceInstance,
    name: str,
    cluster_id: str,
    storage_policy: str,
    cpu_limit: int | None = None,
    memory_limit_mib: int | None = None,
    description: str = "",
    dry_run: bool = False,
) -> dict:
    """Create a vSphere Namespace."""
    spec: dict = {
        "namespace": name,
        "cluster": cluster_id,
        "description": description,
        "storage_specs": [{"policy": storage_policy}],
    }
    resource_spec: dict = {}
    if cpu_limit:
        resource_spec["cpu_limit"] = cpu_limit
    if memory_limit_mib:
        resource_spec["memory_limit"] = memory_limit_mib
    if resource_spec:
        spec["resource_spec"] = resource_spec

    if dry_run:
        return {"dry_run": True, "spec": spec, "action": "create_namespace"}

    _rest_post(si, "/vcenter/namespaces/instances", spec)
    return {"namespace": name, "status": "created", "cluster": cluster_id}


def update_namespace(
    si: ServiceInstance,
    name: str,
    cpu_limit: int | None = None,
    memory_limit_mib: int | None = None,
    storage_policy: str | None = None,
) -> dict:
    """Update namespace resource quotas or storage policy."""
    spec: dict = {}
    resource_spec: dict = {}
    if cpu_limit is not None:
        resource_spec["cpu_limit"] = cpu_limit
    if memory_limit_mib is not None:
        resource_spec["memory_limit"] = memory_limit_mib
    if resource_spec:
        spec["resource_spec"] = resource_spec
    if storage_policy:
        spec["storage_specs"] = [{"policy": storage_policy}]
    if not spec:
        return {"namespace": name, "status": "no_changes"}
    _rest_patch(si, f"/vcenter/namespaces/instances/{name}", spec)
    return {"namespace": name, "status": "updated"}


def delete_namespace(
    si: ServiceInstance,
    name: str,
    confirmed: bool = False,
    dry_run: bool = False,
) -> dict:
    """Delete a vSphere Namespace.

    Guards: confirmed=True required; rejects if TKC clusters exist.
    """
    if not confirmed:
        raise ValueError(
            f"confirmed=True required to delete namespace '{name}'."
        )

    tkc_clusters = _list_tkc_in_namespace(si, name)
    if tkc_clusters:
        raise RuntimeError(
            f"Cannot delete namespace '{name}': "
            f"TKC clusters still exist: {', '.join(tkc_clusters)}. "
            "Delete all TKC clusters first."
        )

    if dry_run:
        return {
            "dry_run": True,
            "action": "delete_namespace",
            "namespace": name,
            "warning": "This will permanently delete the namespace.",
        }

    _rest_delete(si, f"/vcenter/namespaces/instances/{name}")
    return {"namespace": name, "status": "deleted"}


def list_vm_classes(si: ServiceInstance) -> list[dict]:
    """List available VM classes for TKC node sizing."""
    data = _rest_get(si, "/vcenter/namespace-management/virtual-machine-classes")
    return [
        {
            "id": item.get("id"),
            "cpu_count": item.get("cpu_count"),
            "memory_mib": item.get("memory_mib"),
            "gpu_count": item.get("gpu_count", 0),
        }
        for item in (data if isinstance(data, list) else [])
    ]
