"""Centralized API error type with teaching hints (CLAUDE.md 踩坑 #37).

All REST (vCenter namespace-management) and Kubernetes (Supervisor / TKC)
failures are translated into VksApiError at the connection layer, so users
and agents see actionable guidance instead of raw tracebacks.
"""
from __future__ import annotations

from typing import Optional

# Transient gateway errors — safe to retry once for read-only requests.
TRANSIENT_STATUS_CODES = (502, 503, 504)


class VksApiError(RuntimeError):
    """API call failed — carries the HTTP status code and a teaching hint.

    Subclasses RuntimeError so existing ``except RuntimeError`` paths and
    tests keep working.
    """

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def rest_hint_for_status(status_code: Optional[int]) -> str:
    """Teaching hint for a vCenter REST (namespace-management) status code."""
    if status_code == 404:
        return (
            "Resource not found — run 'vmware-vks namespace list' to find "
            "the exact name."
        )
    if status_code in (401, 403):
        return (
            "Permission denied — verify the account has Workload Management "
            "permissions on this vCenter."
        )
    if status_code in TRANSIENT_STATUS_CODES:
        return (
            "vCenter/Supervisor REST endpoint not ready (transient gateway "
            "error) — wait a moment and retry."
        )
    return "Run 'vmware-vks check' to verify connectivity and configuration."


def translate_k8s_api_exception(
    exc: Exception,
    resource: str = "",
    namespace: str = "",
    kind: str = "TKC",
) -> VksApiError:
    """Translate a kubernetes.client ApiException into a VksApiError.

    Adds teaching hints per status code (404 → list command, 401/403 →
    permissions, 5xx → Supervisor not ready). Returns the error; caller
    decides to raise (keeps ``raise ... from exc`` chains at call sites).
    """
    status = getattr(exc, "status", None)
    reason = getattr(exc, "reason", None) or str(exc)

    if status == 404:
        msg = (
            f"{kind} '{resource}' not found in namespace '{namespace}' — "
            "run list_tkc_clusters to see available clusters."
        )
    elif status in (401, 403):
        msg = (
            f"Supervisor K8s API denied access ({status}) for {kind} "
            f"'{resource}' in namespace '{namespace}' — check vCenter SSO "
            "credentials; the account needs Workload Management permissions."
        )
    elif status in TRANSIENT_STATUS_CODES:
        msg = (
            f"Supervisor K8s API not ready ({status}) while accessing {kind} "
            f"'{resource}' in namespace '{namespace}' — the Supervisor may "
            "still be configuring; wait a moment and retry."
        )
    else:
        msg = (
            f"Supervisor K8s API call failed for {kind} '{resource}' in "
            f"namespace '{namespace}': {reason}"
        )
    return VksApiError(msg, status_code=status)
