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
        return paginated(items, total=len(items), namespace=namespace)
    finally:
        api_client.close()
