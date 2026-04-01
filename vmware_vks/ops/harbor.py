"""Harbor registry info (read-only)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

from vmware_policy import sanitize

from vmware_vks.ops.supervisor import _rest_get


def get_harbor_info(si: ServiceInstance) -> dict:
    """Get embedded Harbor registry info."""
    try:
        data = _rest_get(si, "/vcenter/content/registries/harbor")
        registries = data if isinstance(data, list) else [data]
        return {
            "registries": [
                {
                    "id": r.get("id"),
                    "url": sanitize(r.get("ui_access_url", "")),
                    "storage_used_mb": r.get("storage_used_MB"),
                    "status": r.get("health", {}).get("status"),
                }
                for r in registries
            ]
        }
    except Exception as e:
        return {"error": str(e), "hint": "Harbor may not be enabled on this Supervisor"}
