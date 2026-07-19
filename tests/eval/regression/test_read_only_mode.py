"""Read-only mode must remove write tools from the real FastMCP registry.

Regression source: VMware-AIops issue #31 (juanpf-ha). An operator driving the
family with a local Llama 3.3 70B had to hand-write the prompt instruction
"work exclusively in read-only mode and never modify alerts, definitions,
reports or configuration", because read-only was only ever a documented
intent. A weak model can ignore a prompt; it cannot call a tool that is not in
list_tools().

vmware_policy/tests/test_readonly.py pins the gate's *semantics* against a
stand-in registry. This file pins the other half: that the real FastMCP API the
gate reaches for still behaves as assumed, and that this skill's actual tool
inventory splits the way its docs claim.
"""

import asyncio
import importlib
import sys

import pytest

#: Every tool whose docstring starts with ``[WRITE]``.
WRITE_TOOLS = {
    "create_namespace",
    "create_tkc_cluster",
    "delete_namespace",
    "delete_tkc_cluster",
    "scale_tkc_cluster",
    "update_namespace",
    "upgrade_tkc_cluster",
}

#: Marked ``[READ]`` — read-only against vCenter — but on the gate's FORCE_WRITE
#: list: both materialise a session-token kubeconfig at a model-supplied local
#: path. A locked-down deployment opts into that explicitly.
FORCE_WRITE_TOOLS = {"get_supervisor_kubeconfig", "get_tkc_kubeconfig"}

WITHHELD = WRITE_TOOLS | FORCE_WRITE_TOOLS


def _load_server(monkeypatch, read_only: str | None):
    """Import vmware_vks.mcp_server.server fresh under the given read-only env."""
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.delenv("VMWARE_VKS_READ_ONLY", raising=False)
    if read_only is not None:
        monkeypatch.setenv("VMWARE_READ_ONLY", read_only)

    for name in [m for m in sys.modules if m.startswith("vmware_vks.mcp_server")]:
        del sys.modules[name]
    return importlib.import_module("vmware_vks.mcp_server.server")


def _tool_names(server) -> set[str]:
    return {t.name for t in asyncio.run(server.mcp.list_tools())}


@pytest.fixture(autouse=True)
def _restore_modules():
    """Leave sys.modules as we found it so other test files import normally."""
    yield
    for name in [m for m in sys.modules if m.startswith("vmware_vks.mcp_server")]:
        del sys.modules[name]


def test_default_mode_exposes_write_tools(monkeypatch):
    """Baseline: without the switch every tool is present."""
    server = _load_server(monkeypatch, None)
    names = _tool_names(server)
    assert WITHHELD <= names
    assert server.WITHHELD_WRITE_TOOLS == []


def test_read_only_removes_every_write_tool(monkeypatch):
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    assert not (WITHHELD & names), f"write tools survived: {WITHHELD & names}"


def test_read_only_keeps_read_tools(monkeypatch):
    """The gate must not be a blunt instrument — reads still work."""
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    for tool in ("list_namespaces", "get_namespace", "list_tkc_clusters", "get_tkc_cluster"):
        assert tool in names


def test_withheld_list_is_reported(monkeypatch):
    """Startup must be able to tell the operator what was withheld."""
    server = _load_server(monkeypatch, "true")
    assert set(server.WITHHELD_WRITE_TOOLS) == WITHHELD


def test_kubeconfig_tools_withheld_despite_read_marker(monkeypatch):
    """FORCE_WRITE outranks the [READ] docstring marker.

    Neither kubeconfig tool modifies vCenter, but both materialise a
    session-token credential file at a model-supplied local path — the same
    shape as AIops's vm_guest_download (read-only upstream, write-effecting
    locally). A read-only deployment must not hand out credential files.
    """
    server = _load_server(monkeypatch, "true")
    names = _tool_names(server)
    for tool in ("get_supervisor_kubeconfig", "get_tkc_kubeconfig"):
        assert tool not in names
        assert tool in server.WITHHELD_WRITE_TOOLS


def test_every_surviving_tool_is_marked_read(monkeypatch):
    """End-to-end contract against the live registry."""
    server = _load_server(monkeypatch, "true")
    for tool in asyncio.run(server.mcp.list_tools()):
        assert (tool.description or "").lstrip().startswith("[READ]"), tool.name


def test_skill_env_var_also_works(monkeypatch):
    monkeypatch.delenv("VMWARE_READ_ONLY", raising=False)
    monkeypatch.setenv("VMWARE_VKS_READ_ONLY", "true")
    for name in [m for m in sys.modules if m.startswith("vmware_vks.mcp_server")]:
        del sys.modules[name]
    server = importlib.import_module("vmware_vks.mcp_server.server")
    assert not (WITHHELD & _tool_names(server))


def test_fastmcp_registry_api_still_present(monkeypatch):
    """The gate reaches into _tool_manager.list_tools(); pin that it exists.

    If an mcp upgrade moves this, we want a red test here rather than a gate
    that silently stops removing anything.
    """
    server = _load_server(monkeypatch, None)
    assert callable(getattr(server.mcp, "remove_tool", None))
    assert callable(getattr(server.mcp._tool_manager, "list_tools", None))
    assert server.mcp._tool_manager.list_tools()
