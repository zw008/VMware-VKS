"""A teaching message the agent never sees is not a teaching message.

``_safe_error`` reduces unrecognised exceptions to ``"<Class>: operation
failed."`` so raw API text cannot leak. The allowlist it checks against was an
enumeration, and an enumeration drifts: the one exception ``config.py`` raises —
the missing-password error, this family's most common first-run failure —
reached an MCP agent as ``OSError: operation failed.``

That message's entire remedy is the env var name it carries, so redacting it
left the agent with a failure it could not act on and no way to discover the
fix. The defect was invisible from the CLI, which prints the message in full,
and invisible to the error-quality eval, which reads the message at the raise
site rather than what survives the wrapper.

So the rule is the inverse of an enumeration: every exception this skill raises
on purpose passes through, and only genuinely unplanned ones are reduced.

Admitting bare ``OSError`` to reach that one message was too wide. ``sanitize``
strips control characters and truncates; it redacts nothing. ``socket.gaierror``
carries the host that failed to resolve and ``ConnectionError`` carries the full
``scheme://host:port/path``, and both are ``OSError`` subclasses — so the
allowlist that existed to carry one env var name was also carrying those. The
narrow ``ConfigError`` replaces it, and the connection layer translates transport
failures into an authored ``VksApiError`` so the diagnostic survives without the
raw text.

Narrowing the allowlist could not have been the whole fix. ``ValueError`` has
been on it since long before ``OSError`` was, and
``ssl.SSLCertVerificationError`` subclasses both — so the certificate subject
and the hostname were reaching the agent through the ``ValueError`` entry, and
would have kept doing so. An allowlist cannot express "not this one", which is
why ``ssl.SSLError`` is reduced *ahead* of it.

Bare ``RuntimeError`` stays out. ``VksError`` subclasses it, so it is tempting to
widen — but the same type also carries raw text from callers that never intended
an agent to read it. Reaching this skill's own messages would admit those too,
which is why the eight authored ``RuntimeError`` messages in the ops layer became
``VksApiError`` / ``VksSafetyError``. ``test_unplanned_runtime_error_is_still_reduced``
pins the boundary and ``test_ops_layer_raises_no_bare_runtime_error`` pins the
conversion.
"""

from __future__ import annotations

import ast
import socket
import ssl
from pathlib import Path

import pytest

from vmware_vks.config import ConfigError, TargetConfig
from vmware_vks.errors import VksApiError, VksSafetyError
from vmware_vks.mcp_server.server import _safe_error

TEACHING = "Namespace 'ns-99' not found — run 'vmware-vks namespace list' to find the exact name."

ENV_KEY = "VMWARE_VKS_PROD_PASSWORD"
MISSING_PASSWORD = f"Password not found. Set environment variable: {ENV_KEY}"

PKG_ROOT = Path(__file__).resolve().parent.parent / "vmware_vks"


def test_missing_password_keeps_the_env_var_name(monkeypatch):
    """The single config error this skill raises — the env var name IS the fix.

    Driven through the real raise site rather than a hand-built exception: the
    allowlist and the raise have to agree on the type, and only raising it for
    real can prove they do.
    """
    monkeypatch.delenv(ENV_KEY, raising=False)
    target = TargetConfig(name="prod", host="vc.example.com", config_username="admin")
    with pytest.raises(ConfigError) as exc_info:
        _ = target.password

    out = _safe_error(exc_info.value, "list_namespaces")
    assert ENV_KEY in out
    assert "operation failed" not in out


def test_config_error_stays_catchable_as_oserror():
    """CLI paths already catch OSError; narrowing the raise must not break them."""
    assert issubclass(ConfigError, OSError)


def test_bare_oserror_no_longer_passes_through():
    """The allowlist carries ConfigError, not every OSError under it."""
    assert _safe_error(OSError("raw text from somewhere else"), "t") == "OSError: operation failed."


def test_dns_failure_does_not_leak_the_hostname():
    """gaierror is an OSError and names the host it could not resolve.

    OSError is its only base, so narrowing the allowlist is what withholds it —
    this is the case that proves the narrowing did something.
    """
    out = _safe_error(socket.gaierror(-2, "Name or service not known: vc-prod.internal"), "t")
    assert out == "gaierror: operation failed."
    assert "vc-prod.internal" not in out


def test_tls_failure_does_not_leak_the_certificate_subject():
    """An allowlist cannot express "not this one", so SSLError is reduced first.

    ``ssl.SSLCertVerificationError`` subclasses ``ValueError`` as well as
    ``OSError``, and ``ValueError`` predates the whole allowlist — so removing
    ``OSError`` from it does nothing for TLS. Self-signed and mismatched
    certificates are this family's most common connection failure, and their
    text quotes the certificate subject and the hostname.
    """
    exc = ssl.SSLCertVerificationError(
        1,
        "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname "
        "mismatch, certificate is not valid for 'vc-prod.internal'",
    )
    assert isinstance(exc, ValueError), "the reason an allowlist alone cannot hold it"

    out = _safe_error(exc, "t")
    assert out == "SSLCertVerificationError: operation failed."
    assert "vc-prod.internal" not in out
    assert "CERTIFICATE_VERIFY_FAILED" not in out


def test_connection_error_does_not_leak_the_url():
    """ConnectionError is an OSError and carries scheme://host:port/path."""
    out = _safe_error(ConnectionError("HTTPSConnectionPool(host='vc.internal', port=443)"), "t")
    assert out == "ConnectionError: operation failed."
    assert "vc.internal" not in out


def test_vks_api_error_keeps_its_message():
    """The connection layer's teaching errors are the ones agents act on."""
    assert _safe_error(VksApiError(TEACHING, status_code=404), "get_namespace") == TEACHING


def test_vks_safety_error_keeps_its_message():
    """A guard refusal names the precondition to satisfy; that is the whole message."""
    refusal = (
        "Cannot delete namespace 'dev': 2 TKC cluster(s) still exist inside it. "
        "Run delete_tkc_cluster for each of those, then retry delete_namespace."
    )
    assert _safe_error(VksSafetyError(refusal), "delete_namespace") == refusal


@pytest.mark.parametrize("exc_type", [ValueError, FileNotFoundError, KeyError, PermissionError])
def test_validation_errors_still_pass_through(exc_type):
    assert "ns-99" in _safe_error(exc_type(TEACHING), "t")


def test_unplanned_runtime_error_is_still_reduced():
    """VksError subclasses RuntimeError; the base class must stay excluded."""
    out = _safe_error(RuntimeError("https://admin:hunter2@vc.internal/api/vcenter/namespaces"), "t")
    assert out == "RuntimeError: operation failed."
    assert "hunter2" not in out


def test_message_is_still_truncated():
    """Length capping is the other half of the guard."""
    assert len(_safe_error(VksApiError("x" * 900), "t")) <= 300


def test_ops_layer_raises_no_bare_runtime_error():
    """Every authored message must be raised as a type the wrapper lets through.

    A ``raise RuntimeError`` with teaching text in it is silently discarded on
    the way to an agent, and nothing about the raise site says so — which is how
    eight of them accumulated. Scanning is the only way to keep the rule true.
    """
    sources = sorted(PKG_ROOT.rglob("*.py"))
    assert sources, f"no sources found under {PKG_ROOT} — this check scanned nothing"

    offenders = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc
            func = exc.func if isinstance(exc, ast.Call) else exc
            if isinstance(func, ast.Name) and func.id == "RuntimeError":
                offenders.append(f"{path.relative_to(PKG_ROOT.parent)}:{node.lineno}")

    assert not offenders, (
        "raise RuntimeError(...) is reduced to 'RuntimeError: operation failed.' "
        f"before an agent sees it — use VksApiError or VksSafetyError at: {offenders}"
    )
