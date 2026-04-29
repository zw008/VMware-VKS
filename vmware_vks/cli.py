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

tkc_app = typer.Typer(help="TanzuKubernetesCluster commands")
kubeconfig_app = typer.Typer(help="Kubeconfig commands")

app.add_typer(tkc_app, name="tkc")
app.add_typer(kubeconfig_app, name="kubeconfig")


@app.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server (stdio transport).

    Single-command entry point for MCP clients:
        vmware-vks mcp

    Equivalent to the legacy `vmware-vks-mcp` console script.
    """
    from mcp_server.server import main as _mcp_main

    _mcp_main()


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


# ---------------------------------------------------------------------------
# TKC commands
# ---------------------------------------------------------------------------

@tkc_app.command("list")
def tkc_list(
    namespace: Optional[str] = typer.Option(None, "-n", "--namespace"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """List TKC clusters (optionally filtered by namespace)."""
    from vmware_vks.ops.tkc import list_tkc_clusters
    si = _get_si(target)
    result = list_tkc_clusters(si, namespace=namespace)
    table = Table("Name", "Namespace", "Phase", "K8s Version")
    for c in result["clusters"]:
        table.add_row(c["name"], c["namespace"], c["phase"], c["k8s_version"])
    console.print(f"Total: {result['total']}")
    console.print(table)


@tkc_app.command("get")
def tkc_get(
    name: str = typer.Argument(...),
    namespace: str = typer.Option(..., "-n", "--namespace"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Get detailed info for a TKC cluster."""
    import json
    from vmware_vks.ops.tkc import get_tkc_cluster
    si = _get_si(target)
    result = get_tkc_cluster(si, name, namespace)
    console.print_json(json.dumps(result))


@tkc_app.command("versions")
def tkc_versions(
    namespace: str = typer.Option(..., "-n", "--namespace", help="vSphere Namespace"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """List available K8s versions for TKC clusters."""
    from vmware_vks.ops.tkc import get_tkc_available_versions
    si = _get_si(target)
    result = get_tkc_available_versions(si, namespace)
    if result.get("error"):
        console.print(f"[yellow]{result['error']}[/yellow]")
        console.print(f"[dim]{result.get('hint', '')}[/dim]")
        return
    table = Table("Version")
    for v in result["versions"]:
        table.add_row(v["version"])
    console.print(table)


@tkc_app.command("create")
def tkc_create(
    name: str = typer.Argument(...),
    namespace: str = typer.Option(..., "-n", "--namespace"),
    k8s_version: Optional[str] = typer.Option(None, "--version"),
    vm_class: Optional[str] = typer.Option(None, "--vm-class"),
    control_plane: int = typer.Option(1, "--control-plane"),
    workers: int = typer.Option(3, "--workers"),
    storage_policy: str = typer.Option("vsphere-storage", "--storage-policy"),
    apply: bool = typer.Option(False, "--apply", help="Apply (default: dry-run)"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Create a TKC cluster (dry-run by default, use --apply to create).

    Missing --version or --vm-class triggers interactive prompts.
    """
    import json
    from vmware_vks.ops.tkc import create_tkc_cluster, get_tkc_available_versions
    from vmware_vks.ops.namespace import list_vm_classes

    si = _get_si(target)

    # Interactive prompts for missing params
    if not k8s_version:
        versions_result = get_tkc_available_versions(si, namespace)
        version_choices = [v["version"] for v in versions_result.get("versions", [])]
        if version_choices:
            console.print(f"Available versions: {', '.join(version_choices[:5])}")
        k8s_version = typer.prompt("K8s version")

    if not vm_class:
        classes = list_vm_classes(si)
        class_choices = [c["id"] for c in classes if c.get("id")]
        if class_choices:
            console.print(f"Available VM classes: {', '.join(class_choices[:5])}")
        vm_class = typer.prompt("VM class")

    result = create_tkc_cluster(
        si, name=name, namespace=namespace, k8s_version=k8s_version,
        vm_class=vm_class, control_plane_count=control_plane,
        worker_count=workers, storage_class=storage_policy,
        dry_run=not apply,
    )
    console.print_json(json.dumps(result))


@tkc_app.command("scale")
def tkc_scale(
    name: str = typer.Argument(...),
    namespace: str = typer.Option(..., "-n", "--namespace"),
    workers: int = typer.Option(..., "--workers"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Scale TKC cluster worker node count."""
    import json
    from vmware_vks.ops.tkc import scale_tkc_cluster
    si = _get_si(target)
    result = scale_tkc_cluster(si, name, namespace, workers)
    console.print_json(json.dumps(result))


@tkc_app.command("upgrade")
def tkc_upgrade(
    name: str = typer.Argument(...),
    namespace: str = typer.Option(..., "-n", "--namespace"),
    version: str = typer.Option(..., "--version"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Upgrade TKC cluster to a new K8s version."""
    import json
    from vmware_vks.ops.tkc import upgrade_tkc_cluster
    si = _get_si(target)
    result = upgrade_tkc_cluster(si, name, namespace, version)
    console.print_json(json.dumps(result))


@tkc_app.command("delete")
def tkc_delete(
    name: str = typer.Argument(...),
    namespace: str = typer.Option(..., "-n", "--namespace"),
    force: bool = typer.Option(False, "--force"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Delete a TKC cluster (rejects if workloads running)."""
    import json
    from vmware_vks.ops.tkc import delete_tkc_cluster

    si = _get_si(target)

    # Show dry-run first
    dry = delete_tkc_cluster(si, name, namespace, confirmed=True, dry_run=True, force=force)
    console.print_json(json.dumps(dry))

    if not _double_confirm(name, "TKC cluster"):
        console.print("[yellow]Aborted.[/yellow]")
        raise typer.Exit(1)

    result = delete_tkc_cluster(si, name, namespace, confirmed=True, dry_run=False, force=force)
    console.print_json(json.dumps(result))


# ---------------------------------------------------------------------------
# Kubeconfig commands
# ---------------------------------------------------------------------------

@kubeconfig_app.command("supervisor")
def kubeconfig_supervisor(
    namespace: str = typer.Option(..., "-n", "--namespace"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Get Supervisor kubeconfig."""
    from vmware_vks.ops.kubeconfig import get_supervisor_kubeconfig_str
    si = _get_si(target)
    kc = get_supervisor_kubeconfig_str(si, namespace)
    console.print(kc)


@kubeconfig_app.command("get")
def kubeconfig_get(
    name: str = typer.Argument(...),
    namespace: str = typer.Option(..., "-n", "--namespace"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Get TKC cluster kubeconfig."""
    import json
    from vmware_vks.ops.kubeconfig import write_kubeconfig
    si = _get_si(target)
    result = write_kubeconfig(si, name, namespace, output_path=output)
    if output:
        console.print(f"[green]Written to {output}[/green]")
    else:
        console.print(result.get("kubeconfig", ""))


# ---------------------------------------------------------------------------
# Harbor command
# ---------------------------------------------------------------------------

@app.command("harbor")
def harbor_info(
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """Get Harbor registry info."""
    import json
    from vmware_vks.ops.harbor import get_harbor_info
    si = _get_si(target)
    result = get_harbor_info(si)
    console.print_json(json.dumps(result))


# ---------------------------------------------------------------------------
# Storage command
# ---------------------------------------------------------------------------

@app.command("storage")
def storage_usage(
    namespace: str = typer.Option(..., "-n", "--namespace"),
    target: Optional[str] = typer.Option(None, "-t", "--target"),
):
    """List PVC storage usage for a Namespace."""
    import json
    from vmware_vks.ops.storage import list_namespace_storage_usage
    si = _get_si(target)
    result = list_namespace_storage_usage(si, namespace)
    console.print_json(json.dumps(result))
