"""Harbor registry info (read-only)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

from vmware_policy import sanitize

from vmware_vks.ops.supervisor import _rest_get


def _enrich_registry(si: ServiceInstance, registry_id: str | None) -> dict:
    """Fetch health/storage from the per-registry Harbor.Info detail.

    ``GET /api/vcenter/content/registries/harbor/{registry}`` — Harbor.Info
    has ``health`` ({status, ...}) and ``storage`` ([{policy, capacity,
    used}], values in mebibytes). Degrades gracefully: any failure returns
    an empty dict so the Summary fields are still reported.
    """
    if not registry_id:
        return {}
    try:
        info = _rest_get(si, f"/vcenter/content/registries/harbor/{registry_id}")
        if not isinstance(info, dict):
            return {}
        health = info.get("health") or {}
        storage = [s for s in (info.get("storage") or []) if isinstance(s, dict)]
        return {
            "status": health.get("status"),
            "storage_used_mb": sum(s.get("used") or 0 for s in storage)
            if storage
            else None,
        }
    except Exception:
        return {}


def get_harbor_info(si: ServiceInstance) -> dict:
    """Get embedded Harbor registry info.

    ``GET /api/vcenter/content/registries/harbor`` returns Harbor.Summary[]
    = {cluster, registry, version, ui_access_url}. Health and storage usage
    are not on the summary — each entry is enriched via the per-registry
    detail call (graceful degradation: status/storage_used_mb stay None if
    that call fails).
    """
    try:
        data = _rest_get(si, "/vcenter/content/registries/harbor")
        summaries = data if isinstance(data, list) else [data]
        registries = []
        for r in summaries:
            base = {
                "id": r.get("registry"),
                "cluster": r.get("cluster"),
                "version": sanitize(r.get("version", "") or ""),
                "url": sanitize(r.get("ui_access_url", "") or ""),
                "status": None,
                "storage_used_mb": None,
            }
            registries.append({**base, **_enrich_registry(si, r.get("registry"))})
        return {"registries": registries}
    except Exception as e:
        return {"error": str(e), "hint": "Harbor may not be enabled on this Supervisor"}
