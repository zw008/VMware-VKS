"""Typer CLI for vmware-vks."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="vmware-vks", help="vSphere with Tanzu (VKS) management CLI")
supervisor_app = typer.Typer(help="Supervisor cluster commands")
namespace_app = typer.Typer(help="Namespace commands")

app.add_typer(supervisor_app, name="supervisor")
app.add_typer(namespace_app, name="namespace")

console = Console()


def _get_si(target: str | None = None):
    from vmware_vks.config import load_config
    from vmware_vks.connection import ConnectionManager
    config_path = os.environ.get("VMWARE_VKS_CONFIG")
    config = load_config(Path(config_path) if config_path else None)
    mgr = ConnectionManager(config)
    return mgr.connect(target)


def _double_confirm(resource: str, resource_type: str = "resource") -> bool:
    console.print(f"[red]WARNING: You are about to delete {resource_type} '{resource}'.[/red]")
    typed = typer.prompt(f"Type '{resource}' to confirm")
    return typed == resource


@app.command("check")
def cmd_check(
    config: Optional[Path] = typer.Option(None, help="Path to config.yaml"),
):
    """Run pre-flight checks (config, passwords, vCenter version, WCP)."""
    from vmware_vks.doctor import run_doctor
    ok = run_doctor(config)
    raise typer.Exit(0 if ok else 1)


@supervisor_app.command("status")
def supervisor_status(
    cluster_id: str = typer.Argument(..., help="Compute cluster MoRef (e.g. domain-c1)"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Get Supervisor Cluster status."""
    from vmware_vks.ops.supervisor import get_supervisor_status
    si = _get_si(target)
    result = get_supervisor_status(si, cluster_id)
    for k, v in result.items():
        console.print(f"  [bold]{k}:[/bold] {v}")


@supervisor_app.command("storage-policies")
def supervisor_storage_policies(
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """List storage policies available for Namespaces."""
    from vmware_vks.ops.supervisor import list_supervisor_storage_policies
    si = _get_si(target)
    policies = list_supervisor_storage_policies(si)
    table = Table("Storage Policy", "Compatible Clusters")
    for p in policies:
        table.add_row(p["storage_policy"], str(p["compatible_clusters"]))
    console.print(table)


@namespace_app.command("list")
def namespace_list(
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """List all vSphere Namespaces."""
    from vmware_vks.ops.namespace import list_namespaces
    si = _get_si(target)
    nss = list_namespaces(si)
    table = Table("Namespace", "Status", "Description")
    for ns in nss:
        table.add_row(ns["namespace"], ns["config_status"], ns.get("description", ""))
    console.print(table)


@namespace_app.command("get")
def namespace_get(
    name: str = typer.Argument(...),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Get details for a single Namespace."""
    import json
    from vmware_vks.ops.namespace import get_namespace
    si = _get_si(target)
    result = get_namespace(si, name)
    console.print_json(json.dumps(result))


@namespace_app.command("create")
def namespace_create(
    name: str = typer.Argument(...),
    cluster_id: str = typer.Option(..., "--cluster", help="Supervisor cluster MoRef"),
    storage_policy: str = typer.Option(..., "--storage-policy"),
    cpu_limit: Optional[int] = typer.Option(None, "--cpu"),
    memory_mib: Optional[int] = typer.Option(None, "--memory"),
    description: str = typer.Option("", "--description"),
    apply: bool = typer.Option(False, "--apply", help="Apply (default: dry-run)"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Create a vSphere Namespace (dry-run by default, use --apply to create)."""
    import json
    from vmware_vks.ops.namespace import create_namespace
    si = _get_si(target)
    result = create_namespace(
        si, name=name, cluster_id=cluster_id, storage_policy=storage_policy,
        cpu_limit=cpu_limit, memory_limit_mib=memory_mib,
        description=description, dry_run=not apply,
    )
    console.print_json(json.dumps(result))


@namespace_app.command("update")
def namespace_update(
    name: str = typer.Argument(...),
    cpu_limit: Optional[int] = typer.Option(None, "--cpu"),
    memory_mib: Optional[int] = typer.Option(None, "--memory"),
    storage_policy: Optional[str] = typer.Option(None, "--storage-policy"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Update Namespace resource quotas or storage policy."""
    import json
    from vmware_vks.ops.namespace import update_namespace
    si = _get_si(target)
    result = update_namespace(si, name, cpu_limit=cpu_limit,
                              memory_limit_mib=memory_mib, storage_policy=storage_policy)
    console.print_json(json.dumps(result))


@namespace_app.command("delete")
def namespace_delete(
    name: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force", help="Skip interactive confirm"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Delete a vSphere Namespace (rejects if TKC clusters exist inside)."""
    import json
    from vmware_vks.ops.namespace import delete_namespace

    si = _get_si(target)
    # Show dry-run first
    dry = delete_namespace(si, name, confirmed=True, dry_run=True)
    console.print_json(json.dumps(dry))

    if not force:
        if not _double_confirm(name, "namespace"):
            console.print("[yellow]Aborted.[/yellow]")
            raise typer.Exit(1)

    result = delete_namespace(si, name, confirmed=True, dry_run=False)
    console.print_json(json.dumps(result))


@namespace_app.command("vm-classes")
def namespace_vm_classes(
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """List available VM classes for TKC node sizing."""
    from vmware_vks.ops.namespace import list_vm_classes
    si = _get_si(target)
    classes = list_vm_classes(si)
    table = Table("ID", "CPU", "Memory (MiB)", "GPU")
    for c in classes:
        table.add_row(str(c["id"]), str(c["cpu_count"]), str(c["memory_mib"]), str(c["gpu_count"]))
    console.print(table)
