"""Namespace storage usage (PVC list + usage stats)."""
from __future__ import annotations
from typing import TYPE_CHECKING

from vmware_policy import paginated, sanitize

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


def list_namespace_storage_usage(si: ServiceInstance, namespace: str) -> dict:
    """List PVCs and storage usage for a vSphere Namespace.

    Returns the family list envelope, with the queried ``namespace`` carried as
    an extra key. The K8s call returns the whole collection in one response, so
    ``total`` is the real PVC count and ``truncated`` is always False.

    .. deprecated:: 1.8.6
       ``pvcs`` and ``pvc_count`` are compatibility aliases for ``items`` and
       ``returned``, and will be removed in 2.0. Until v1.8.0 this function
       returned ``{namespace, pvc_count, pvcs}``; the envelope renamed ``pvcs``
       to ``items`` and dropped ``pvc_count`` entirely. Because the payload was
       already a keyed dict the break was silent — ``result.get("pvcs", [])``
       started returning ``[]``, which reads as "this namespace uses no
       storage" rather than as a failure. ``pvcs`` is the *same* list object as
       ``items``, so they cannot drift, and ``pvc_count`` is always
       ``len(pvcs)``. Migrate to ``items`` / ``returned``.
    """
    import kubernetes as k8s
    from vmware_vks.k8s_connection import get_k8s_client

    api_client = get_k8s_client(si, namespace)
    try:
        core_api = k8s.client.CoreV1Api(api_client)
        pvcs = core_api.list_namespaced_persistent_volume_claim(namespace=namespace)
        items = [
            {
                "name": sanitize(pvc.metadata.name),
                "namespace": sanitize(pvc.metadata.namespace),
                "status": pvc.status.phase,
                "capacity": pvc.status.capacity.get("storage") if pvc.status.capacity else None,
                "storage_class": pvc.spec.storage_class_name,
            }
            for pvc in pvcs.items
        ]
        envelope = paginated(items, total=len(items), namespace=namespace)
        # Deprecated aliases for pre-v1.8.0 callers; removed in 2.0. ``pvcs`` is
        # the same list object as ``items`` — a copy would let the two drift —
        # and ``pvc_count`` tracks it via ``returned`` rather than recomputing.
        return {
            **envelope,
            "pvcs": envelope["items"],
            "pvc_count": envelope["returned"],
        }
    finally:
        api_client.close()
