"""A teaching message the agent never sees is not a teaching message.

``_safe_error`` reduces unrecognised exceptions to ``"<Class>: operation
failed."`` so raw API text cannot leak. The allowlist it checks against was an
enumeration, and an enumeration drifts: ``OSError`` was missing from it, so the
one exception ``config.py`` raises — the missing-password error, this family's
most common first-run failure — reached an MCP agent as
``OSError: operation failed.``

That message's entire remedy is the env var name it carries, so redacting it
left the agent with a failure it could not act on and no way to discover the
fix. The defect was invisible from the CLI, which prints the message in full,
and invisible to the error-quality eval, which reads the message at the raise
site rather than what survives the wrapper.

So the rule is the inverse of an enumeration: every exception this skill raises
on purpose passes through, and only genuinely unplanned ones are reduced.

The one deliberate exclusion is bare ``RuntimeError``. ``VksApiError``
subclasses it, so it is tempting to widen — but this skill also raises eight
authored ``RuntimeError`` messages in the ops layer, and the same type carries
raw text from callers that never intended an agent to read it. Reaching the
eight would admit the rest, so those want purpose-built domain exceptions
instead. ``test_unplanned_runtime_error_is_still_reduced`` pins that boundary.
"""

from __future__ import annotations

import pytest

from vmware_vks.errors import VksApiError
from vmware_vks.mcp_server.server import _safe_error

TEACHING = "Namespace 'ns-99' not found — run 'vmware-vks namespace list' to find the exact name."

ENV_KEY = "VMWARE_VKS_PROD_PASSWORD"
MISSING_PASSWORD = f"Password not found. Set environment variable: {ENV_KEY}"


def test_missing_password_keeps_the_env_var_name():
    """The single OSError config.py raises — and the whole point of it is the name."""
    out = _safe_error(OSError(MISSING_PASSWORD), "list_namespaces")
    assert ENV_KEY in out
    assert "operation failed" not in out


def test_vks_api_error_keeps_its_message():
    """The connection layer's teaching errors are the ones agents act on."""
    assert _safe_error(VksApiError(TEACHING, status_code=404), "get_namespace") == TEACHING


@pytest.mark.parametrize("exc_type", [ValueError, FileNotFoundError, KeyError, PermissionError])
def test_validation_errors_still_pass_through(exc_type):
    assert "ns-99" in _safe_error(exc_type(TEACHING), "t")


def test_unplanned_runtime_error_is_still_reduced():
    """VksApiError subclasses RuntimeError; the base class must stay excluded."""
    out = _safe_error(RuntimeError("https://admin:hunter2@vc.internal/api/vcenter/namespaces"), "t")
    assert out == "RuntimeError: operation failed."
    assert "hunter2" not in out


def test_message_is_still_truncated():
    """Length capping is the other half of the guard."""
    assert len(_safe_error(VksApiError("x" * 900), "t")) <= 300
