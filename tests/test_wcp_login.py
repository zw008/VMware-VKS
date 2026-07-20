"""Wire-shape tests for the Supervisor /wcp/login bearer-token flow (fix #1).

The K8s bearer token MUST come from POST https://<host>/wcp/login with HTTP
Basic auth (what `kubectl vsphere login` does) — NOT the pyVmomi SOAP session
key. These tests mock HTTP only; the flow still needs live-Supervisor
validation before release (see wcp_login module docstring).
"""
from __future__ import annotations

import base64
import io
import json
import ssl
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from vmware_vks import wcp_login
from vmware_vks.errors import VksApiError


@pytest.fixture(autouse=True)
def _clear_token_cache():
    wcp_login._token_cache.clear()
    yield
    wcp_login._token_cache.clear()


def _mock_response(payload: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_wcp_login_posts_basic_auth_and_extracts_session_id():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": "jwt-abc"})
        token = wcp_login.wcp_login("vc.example.com", "admin@vsphere.local", "s3cret")

    assert token == "jwt-abc"
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://vc.example.com/wcp/login"
    assert req.get_method() == "POST"
    expected = base64.b64encode(b"admin@vsphere.local:s3cret").decode()
    assert req.get_header("Authorization") == f"Basic {expected}"


def test_wcp_login_caches_per_host_user():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": "jwt-abc"})
        t1 = wcp_login.wcp_login("vc.example.com", "admin", "pw")
        t2 = wcp_login.wcp_login("vc.example.com", "admin", "pw")
        # Different user → separate cache entry → second HTTP call
        wcp_login.wcp_login("vc.example.com", "other", "pw")

    assert t1 == t2 == "jwt-abc"
    assert mock_open.call_count == 2


def test_wcp_login_invalidate_drops_cache():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": "jwt-abc"})
        wcp_login.wcp_login("vc.example.com", "admin", "pw")
        wcp_login.invalidate_wcp_token("vc.example.com", "admin")
        wcp_login.wcp_login("vc.example.com", "admin", "pw")
    assert mock_open.call_count == 2


def test_wcp_login_401_raises_teaching_error_and_invalidates():
    err = urllib.error.HTTPError(
        "https://vc/wcp/login", 401, "Unauthorized", None, io.BytesIO(b"")
    )
    # Seed an expired cache entry — a 401 must drop it entirely.
    wcp_login._token_cache[("vc.example.com", "admin")] = ("stale", 0.0)
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(VksApiError) as exc_info:
            wcp_login.wcp_login("vc.example.com", "admin", "bad-pw")
    msg = str(exc_info.value)
    assert "Supervisor login failed (HTTP 401)" in msg
    assert "check vCenter SSO credentials" in msg
    assert "Workload Management permissions" in msg
    assert exc_info.value.status_code == 401
    assert ("vc.example.com", "admin") not in wcp_login._token_cache


def test_wcp_login_404_raises_teaching_error_and_invalidates():
    # 404 on /wcp/login is the headline issue-#13 unknown: the endpoint path
    # may differ on some Supervisor versions. A 404 must surface a teaching
    # error (not the generic 401/403 wording) and drop any cached token.
    err = urllib.error.HTTPError(
        "https://vc/wcp/login", 404, "Not Found", None, io.BytesIO(b"")
    )
    wcp_login._token_cache[("vc.example.com", "admin")] = ("stale", 0.0)
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(VksApiError) as exc_info:
            wcp_login.wcp_login("vc.example.com", "admin", "pw")
    msg = str(exc_info.value)
    assert "Supervisor login failed (HTTP 404)" in msg
    assert "https://vc.example.com/wcp/login" in msg
    assert exc_info.value.status_code == 404
    assert ("vc.example.com", "admin") not in wcp_login._token_cache


def test_wcp_login_timeout_raises_teaching_error():
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(VksApiError) as exc_info:
            wcp_login.wcp_login("vc.example.com", "admin", "pw")
    msg = str(exc_info.value)
    assert "reachable" in msg
    assert "https://vc.example.com/wcp/login" in msg


def test_wcp_login_403_raises_teaching_error():
    err = urllib.error.HTTPError(
        "https://vc/wcp/login", 403, "Forbidden", None, io.BytesIO(b"")
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(VksApiError) as exc_info:
            wcp_login.wcp_login("vc.example.com", "admin", "pw")
    assert "HTTP 403" in str(exc_info.value)
    assert "Workload Management permissions" in str(exc_info.value)
    assert exc_info.value.status_code == 403


def test_wcp_login_targets_exact_endpoint_path():
    # Pin the URL so any future endpoint drift (path/scheme) fails a unit test.
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": "jwt"})
        wcp_login.wcp_login("vc.example.com:443", "admin", "pw")
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://vc.example.com:443/wcp/login"
    assert req.data == b""  # POST with empty body, auth carried in header


def test_wcp_login_empty_session_id_raises():
    # An empty-string session_id is as broken as a missing one.
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": ""})
        with pytest.raises(VksApiError, match="session_id"):
            wcp_login.wcp_login("vc.example.com", "admin", "pw")


def test_wcp_login_unreachable_raises_teaching_error():
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        with pytest.raises(VksApiError, match="reachable"):
            wcp_login.wcp_login("vc.example.com", "admin", "pw")


def test_wcp_login_missing_session_id_raises():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"unexpected": "shape"})
        with pytest.raises(VksApiError, match="session_id"):
            wcp_login.wcp_login("vc.example.com", "admin", "pw")


def test_wcp_login_honors_verify_ssl_false():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": "jwt"})
        wcp_login.wcp_login("vc.example.com", "admin", "pw", verify_ssl=False)
    ctx = mock_open.call_args[1]["context"]
    assert ctx.verify_mode == ssl.CERT_NONE


def test_wcp_login_verify_ssl_true_keeps_verification():
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value = _mock_response({"session_id": "jwt"})
        wcp_login.wcp_login("vc.example.com", "admin", "pw", verify_ssl=True)
    ctx = mock_open.call_args[1]["context"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_get_wcp_token_uses_connection_target_config():
    from vmware_vks import connection
    from vmware_vks.config import TargetConfig

    si = MagicMock()
    target = TargetConfig(name="lab", host="vc.example.com",
                          config_username="admin", verify_ssl=False)
    connection._SI_TARGET[id(si)] = target
    connection._SI_VERIFY_SSL[id(si)] = False
    try:
        with patch.dict("os.environ", {"VMWARE_VKS_LAB_PASSWORD": "pw"}):
            with patch("urllib.request.urlopen") as mock_open:
                mock_open.return_value = _mock_response({"session_id": "jwt-si"})
                token = wcp_login.get_wcp_token(si)
        assert token == "jwt-si"
        req = mock_open.call_args[0][0]
        assert req.full_url == "https://vc.example.com/wcp/login"
    finally:
        connection._SI_TARGET.pop(id(si), None)
        connection._SI_VERIFY_SSL.pop(id(si), None)


def test_get_wcp_token_without_target_metadata_raises():
    si = MagicMock()
    with pytest.raises(VksApiError, match="ConnectionManager"):
        wcp_login.get_wcp_token(si)
