"""Supervisor (Workload Control Plane) login — the real bearer-token flow.

Supervisor and TKC Kubernetes API auth is NOT the pyVmomi SOAP session key.
The real flow (what ``kubectl vsphere login`` does) is:

    POST https://<vcenter-or-supervisor>/wcp/login   (HTTP Basic auth)
    → 200 {"session_id": "<jwt>"}

That JWT is the Kubernetes bearer token. Tokens are cached per
(host, username) with a conservative TTL and invalidated on 401.

NOTE (release-notes): this flow replaces the previous (incorrect) use of
``si.content.sessionManager.currentSession.key`` as the bearer token and
still needs validation against a live Supervisor before the next release.
"""
from __future__ import annotations

import base64
import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

from vmware_vks.errors import VksApiError

_log = logging.getLogger("vmware-vks.wcp_login")

# Conservative TTL — Supervisor JWTs typically last ~10h; refresh at 8h.
_TOKEN_TTL_SECONDS = 8 * 3600

# (host, username) → (token, monotonic expiry). Tokens never touch disk.
_token_cache: dict[tuple[str, str], tuple[str, float]] = {}

_LOGIN_TIMEOUT = 30


def invalidate_wcp_token(host: str, username: str) -> None:
    """Drop the cached token for (host, username) — call on 401 responses."""
    _token_cache.pop((host, username), None)


def wcp_login(
    host: str,
    username: str,
    password: str,
    verify_ssl: bool = True,
) -> str:
    """Login to the Supervisor via POST /wcp/login and return the JWT.

    Uses HTTP Basic auth (vCenter SSO credentials). The returned
    ``session_id`` JWT is the Kubernetes bearer token. Cached per
    (host, username) for ~8h; call invalidate_wcp_token on 401.
    """
    key = (host, username)
    cached = _token_cache.get(key)
    if cached and time.monotonic() < cached[1]:
        return cached[0]

    url = f"https://{host}/wcp/login"
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    creds = base64.b64encode(f"{username}:{password}".encode()).decode()
    req = urllib.request.Request(
        url,
        data=b"",
        headers={"Authorization": f"Basic {creds}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=_LOGIN_TIMEOUT) as resp:  # nosec B310
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        invalidate_wcp_token(host, username)
        if e.code in (401, 403):
            raise VksApiError(
                f"Supervisor login failed (HTTP {e.code}) — check vCenter SSO "
                "credentials; the account needs Workload Management "
                "permissions.",
                status_code=e.code,
            ) from e
        raise VksApiError(
            f"Supervisor login failed (HTTP {e.code}) at {url}. "
            "Verify Workload Management is enabled on this vCenter.",
            status_code=e.code,
        ) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise VksApiError(
            f"Supervisor login failed: {e}. Check that {url} is reachable "
            "and Workload Management is enabled.",
        ) from e

    token = data.get("session_id") if isinstance(data, dict) else None
    if not token:
        raise VksApiError(
            "Supervisor login succeeded but the response had no 'session_id' "
            "field — unexpected /wcp/login response shape."
        )

    _token_cache[key] = (token, time.monotonic() + _TOKEN_TTL_SECONDS)
    return token


def get_wcp_token(si: "ServiceInstance") -> str:
    """Get a Supervisor bearer token for the target behind this connection.

    Pulls host/username/password from the connection-manager side store
    (see connection.get_target_config — 踩坑 #32 pattern) and honours the
    target's verify_ssl flag.
    """
    from vmware_vks.connection import get_target_config, get_verify_ssl

    target = get_target_config(si)
    if target is None:
        raise VksApiError(
            "No connection target metadata for this session — connect via "
            "ConnectionManager so Supervisor login credentials are available."
        )
    return wcp_login(
        target.host,
        target.username,
        target.password,
        verify_ssl=get_verify_ssl(si),
    )


def invalidate_wcp_token_for_si(si: "ServiceInstance") -> None:
    """Invalidate the cached token for the target behind this connection."""
    from vmware_vks.connection import get_target_config

    target = get_target_config(si)
    if target is not None:
        invalidate_wcp_token(target.host, target.username)
