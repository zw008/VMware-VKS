"""Pre-flight diagnostics for vmware-vks."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from rich.console import Console
from rich.table import Table

_log = logging.getLogger("vmware-vks.doctor")
console = Console()


def _config_read_only() -> bool | None:
    """Read ``read_only`` from the config file the MCP server's gate would use.

    Deliberately mirrors ``mcp_server.server._config_read_only`` instead of
    importing it: importing that module applies the gate as a side effect. The
    path comes from ``VMWARE_VKS_CONFIG`` rather than this command's
    ``--config`` argument, because the question doctor answers is what the
    *server* will decide, not what this invocation was pointed at.
    """
    try:
        from vmware_vks.config import load_config

        config_path = os.environ.get("VMWARE_VKS_CONFIG")
        return load_config(Path(config_path) if config_path else None).read_only
    except Exception:  # noqa: BLE001 — absent/unreadable config is not an error here
        return None


def _check_read_only() -> tuple[bool, str]:
    """Report the resolved read-only state and where it came from.

    Never fails — read-only being on is a posture, not a fault. It is here
    because an operator who set the switch had no way to confirm it took: the
    only signal was a line in the MCP server's start-up log.
    """
    from vmware_policy.readonly import read_only_status

    status = read_only_status("vmware-vks", _config_read_only())
    if not status.recognised:
        return True, (
            f"{status.source}={status.raw!r} is not a recognised value. It resolves "
            f"to ON (fail-closed), so all 9 write tools are withheld — probably not "
            f"what was intended. Use true or false."
        )
    if status.enabled:
        return True, (
            f"ON (from {status.source}) — 9 write tools withheld, 11 read tools "
            f"exposed. Clear that switch and restart the server to expose them."
        )
    return True, f"off (from {status.source}) — all 20 tools are exposed"


def run_doctor(config_path: Path | None = None) -> bool:
    """Run all pre-flight checks. Returns True if all pass."""
    from vmware_vks.config import CONFIG_FILE, ENV_FILE, load_config

    checks: list[tuple[str, bool, str]] = []

    # 1. Config file
    path = config_path or CONFIG_FILE
    if path.exists():
        checks.append(("Config file", True, str(path)))
    else:
        checks.append(
            (
                "Config file",
                False,
                f"Not found: {path}. Run 'vmware-vks init' "
                "(or copy config.example.yaml by hand).",
            )
        )

    # 2. Load config
    config = None
    try:
        config = load_config(path)
        checks.append(("Config parse", True, f"{len(config.targets)} target(s)"))
    except Exception as e:
        checks.append(("Config parse", False, str(e)))

    # 3. Passwords
    if config:
        for t in config.targets:
            try:
                _ = t.password
                checks.append((f"Password ({t.name})", True, "Set"))
            except OSError as e:
                checks.append(
                    (
                        f"Password ({t.name})",
                        False,
                        f"{e} Run 'vmware-vks init' to set it (or add it to "
                        "~/.vmware-vks/.env by hand).",
                    )
                )

    # 4. vCenter reachable + version + WCP
    if config:
        for t in config.targets:
            try:
                from vmware_vks.connection import ConnectionManager

                mgr = ConnectionManager(config)
                si = mgr.connect(t.name)
                version = si.content.about.version
                checks.append((f"vCenter reachable ({t.name})", True, f"v{version}"))

                parts = tuple(int(x) for x in version.split(".")[:2])
                if parts >= (8, 0):
                    checks.append(
                        (f"vCenter version ({t.name})", True, f"{version} >= 8.0 ✓")
                    )
                else:
                    checks.append(
                        (
                            f"vCenter version ({t.name})",
                            False,
                            f"{version} < 8.0 (requires 8.x+)",
                        )
                    )

                from vmware_vks.ops.supervisor import _rest_get

                clusters = _rest_get(si, "/vcenter/namespace-management/clusters")
                running = [c for c in clusters if c.get("config_status") == "RUNNING"]
                if running:
                    checks.append(
                        (
                            f"WCP enabled ({t.name})",
                            True,
                            f"{len(running)} cluster(s) running",
                        )
                    )
                else:
                    checks.append(
                        (
                            f"WCP enabled ({t.name})",
                            False,
                            "No running Supervisor. Enable Workload Management in vCenter UI.",
                        )
                    )
            except Exception as e:
                checks.append((f"vCenter reachable ({t.name})", False, str(e)))

    # 5. Read-only mode — state, not pass/fail
    passed, detail = _check_read_only()
    checks.append(("Read-only mode", passed, detail))

    # Print table
    table = Table(title="vmware-vks Doctor", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    all_passed = True
    for name, passed, detail in checks:
        status = "[green]✓ PASS[/green]" if passed else "[red]✗ FAIL[/red]"
        table.add_row(name, status, detail)
        if not passed:
            all_passed = False

    console.print(table)
    return all_passed
