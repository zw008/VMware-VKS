<!-- mcp-name: io.github.zw008/vmware-vks -->
# VMware VKS

[English](README.md) | [中文](README-CN.md)

MCP Skill + CLI for managing vSphere with Tanzu (VKS) — Supervisor clusters, vSphere Namespaces, and TanzuKubernetesCluster lifecycle.

> **Part of the VMware MCP Skills family:**
>
> | Skill | Scope | Tools |
> |-------|-------|:-----:|
> | **vmware-monitor** (read-only) | Inventory, health, alarms, events | 8 |
> | **vmware-aiops** (full ops) | VM lifecycle, deployment, guest ops, plans | 33 |
> | **vmware-storage** | Datastores, iSCSI, vSAN | 11 |
> | **vmware-vks** (this) | Supervisor, Namespaces, TKC lifecycle | 20 |

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Prerequisites

- **vSphere 8.0+** — Workload Management (Supervisor) APIs require vSphere 8.x
- **Workload Management enabled** — WCP must be enabled on at least one compute cluster
- **License** — vSphere with Tanzu (Enterprise Plus or VMware Cloud Foundation)

Run `vmware-vks check` after setup to verify all requirements are met.

## Quick Start

```bash
# Install
uv tool install vmware-vks

# Configure
mkdir -p ~/.vmware-vks
cp config.example.yaml ~/.vmware-vks/config.yaml
# Edit config.yaml with your vCenter host and username

echo "VMWARE_MY_VCENTER_PASSWORD=your_password" > ~/.vmware-vks/.env
chmod 600 ~/.vmware-vks/.env

# Verify
vmware-vks check

# Common operations
vmware-vks supervisor status domain-c1
vmware-vks namespace list
vmware-vks tkc list
vmware-vks tkc create my-cluster -n dev --version v1.28.4+vmware.1 --vm-class best-effort-large
vmware-vks tkc create my-cluster -n dev --apply
```

## Tool Reference (20 tools)

### Supervisor

| Tool | Description | Type |
|------|-------------|------|
| `check_vks_compatibility` | vCenter version check + WCP status | Read |
| `get_supervisor_status` | Supervisor cluster status and K8s API endpoint | Read |
| `list_supervisor_storage_policies` | Available storage policies for Namespaces | Read |

### Namespace

| Tool | Description | Type |
|------|-------------|------|
| `list_namespaces` | All vSphere Namespaces with status | Read |
| `get_namespace` | Namespace detail (quotas, storage, roles) | Read |
| `create_namespace` | Create Namespace with dry-run preview | Write |
| `update_namespace` | Modify quotas and storage policy | Write |
| `delete_namespace` | Delete with TKC guard (rejects if clusters exist) | Write |
| `list_vm_classes` | Available VM classes for TKC sizing | Read |

### TKC

| Tool | Description | Type |
|------|-------------|------|
| `list_tkc_clusters` | TanzuKubernetesCluster list with status | Read |
| `get_tkc_cluster` | Cluster detail (nodes, health, conditions) | Read |
| `get_tkc_available_versions` | Supported K8s versions on Supervisor | Read |
| `create_tkc_cluster` | Create TKC with YAML plan + dry-run default | Write |
| `scale_tkc_cluster` | Scale worker node count | Write |
| `upgrade_tkc_cluster` | Upgrade K8s version | Write |
| `delete_tkc_cluster` | Delete with workload guard | Write |

### Access

| Tool | Description | Type |
|------|-------------|------|
| `get_supervisor_kubeconfig` | Supervisor kubeconfig YAML | Read |
| `get_tkc_kubeconfig` | TKC kubeconfig (stdout or file) | Read |
| `get_harbor_info` | Embedded Harbor registry info | Read |
| `list_namespace_storage_usage` | PVC list and capacity stats | Read |

## CLI Reference

```bash
# Pre-flight diagnostics
vmware-vks check

# Supervisor
vmware-vks supervisor status <cluster-id>
vmware-vks supervisor storage-policies

# Namespace
vmware-vks namespace list
vmware-vks namespace get <name>
vmware-vks namespace create <name> --cluster <id> --storage-policy <policy>
vmware-vks namespace create <name> --cluster <id> --storage-policy <policy> --apply
vmware-vks namespace update <name> [--cpu <mhz>] [--memory <mib>]
vmware-vks namespace delete <name>
vmware-vks namespace vm-classes

# TKC
vmware-vks tkc list [-n <namespace>]
vmware-vks tkc get <name> -n <namespace>
vmware-vks tkc versions -n <namespace>
vmware-vks tkc create <name> -n <namespace> [--version <v>] [--vm-class <c>]
vmware-vks tkc create <name> -n <namespace> --apply
vmware-vks tkc scale <name> -n <namespace> --workers <n>
vmware-vks tkc upgrade <name> -n <namespace> --version <v>
vmware-vks tkc delete <name> -n <namespace>

# Kubeconfig
vmware-vks kubeconfig supervisor -n <namespace>
vmware-vks kubeconfig get <cluster-name> -n <namespace> [-o <path>]

# Harbor & Storage
vmware-vks harbor
vmware-vks storage -n <namespace>
```

## MCP Server

```bash
# Run directly
vmware-vks-mcp

# Or via module
python -m mcp_server
```

### Agent Configuration

Add to your AI agent's MCP config:

```json
{
  "mcpServers": {
    "vmware-vks": {
      "command": "vmware-vks-mcp",
      "env": {
        "VMWARE_VKS_CONFIG": "~/.vmware-vks/config.yaml"
      }
    }
  }
}
```

## Safety

| Feature | Description |
|---------|-------------|
| Read-heavy | 12/20 tools are read-only |
| Dry-run default | `create_namespace`, `create_tkc_cluster`, `delete_namespace`, `delete_tkc_cluster` all default to `dry_run=True` |
| TKC guard | `delete_namespace` rejects if TKC clusters exist inside |
| Workload guard | `delete_tkc_cluster` rejects if Deployments/StatefulSets are running |
| Credential safety | Passwords only from environment variables (`.env` file), never in `config.yaml` |
| Audit logging | All write operations logged to `~/.vmware-vks/audit.log` |
| stdio transport | No network listener; MCP runs over stdio only |

## Version Compatibility

| vSphere | Support | Notes |
|---------|---------|-------|
| 8.0+ | Full | Workload Management APIs available |
| 7.x | Not supported | WCP API surface is different; use vSphere 8.x |

## License

[MIT](LICENSE)
