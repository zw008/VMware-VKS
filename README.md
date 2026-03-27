<!-- mcp-name: io.github.zw008/vmware-vks -->
# VMware VKS

[English](README.md) | [中文](README-CN.md)

MCP Skill + CLI for VMware vSphere with Tanzu (VKS) management — Supervisor clusters, vSphere Namespaces, and TanzuKubernetesCluster lifecycle. 20 MCP tools.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Companion Skills

> **Part of the VMware MCP Skills family.** Each skill handles a distinct domain — install only what you need.

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** ⭐ entry point | VM lifecycle, deployment, guest ops, clusters | 31 | `uv tool install vmware-aiops` |
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | Read-only monitoring, alarms, events, VM info | 8 | `uv tool install vmware-monitor` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-nsx](https://github.com/zw008/VMware-NSX)** | NSX networking: segments, gateways, NAT, IPAM | 31 | `uv tool install vmware-nsx-mgmt` |
| **[vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security)** | DFW microsegmentation, security groups, Traceflow | 20 | `uv tool install vmware-nsx-security` |
| **[vmware-aria](https://github.com/zw008/VMware-Aria)** | Aria Ops metrics, alerts, capacity planning | 18 | `uv tool install vmware-aria` |

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

## Common Workflows

### Deploy a New TKC Cluster

1. Check compatibility → `vmware-vks check`
2. List available K8s versions → `vmware-vks tkc versions -n dev`
3. Create namespace (if needed) → `vmware-vks namespace create dev --cluster domain-c1 --storage-policy vSAN --cpu 16000 --memory 32768 --apply`
4. Create TKC cluster → `vmware-vks tkc create dev-cluster -n dev --version v1.28.4+vmware.1 --control-plane 1 --workers 3 --vm-class best-effort-large --apply`
5. Get kubeconfig → `vmware-vks kubeconfig get dev-cluster -n dev`

### Scale Workers for Load Testing

1. Check current state → `vmware-vks tkc get dev-cluster -n dev`
2. Scale up → `vmware-vks tkc scale dev-cluster -n dev --workers 6`
3. Monitor progress → `vmware-vks tkc get dev-cluster -n dev` (watch phase)
4. Scale back down after test

### Namespace Resource Management

1. List namespaces → `vmware-vks namespace list`
2. Check usage → `vmware-vks storage -n dev`
3. Update quota → `vmware-vks namespace update dev --cpu 32000 --memory 65536`

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

## Architecture

```
User (Natural Language)
  ↓
AI Agent (Claude Code / Goose / Cursor)
  ↓ reads SKILL.md
  ↓
vmware-vks CLI  ─── or ───  vmware-vks MCP Server (stdio)
  │
  ├─ Layer 1: pyVmomi → vCenter REST API
  │   Supervisor status, storage policies, Namespace CRUD, VM classes, Harbor
  │
  └─ Layer 2: kubernetes client → Supervisor K8s API endpoint
      TKC CR apply / get / delete  (cluster.x-k8s.io/v1beta1)
      Kubeconfig built from Layer 1 session token
  ↓
vCenter Server 8.x+ (Workload Management enabled)
  ↓
Supervisor Cluster → vSphere Namespaces → TanzuKubernetesCluster
```

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

# Or via uvx (recommended when installed with uv tool install)
uvx --from vmware-vks vmware-vks-mcp
```

### Agent Configuration

Add to your AI agent's MCP config:

```json
{
  "mcpServers": {
    "vmware-vks": {
      "command": "uvx",
      "args": ["--from", "vmware-vks", "vmware-vks-mcp"],
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

## Troubleshooting

### "VKS not compatible" error

Workload Management must be enabled in vCenter. Check: vCenter UI -> Workload Management. Requires vSphere 8.x+ with Enterprise Plus or VCF license.

### Namespace creation fails with "storage policy not found"

List available policies first: `vmware-vks supervisor storage-policies`. Policy names are case-sensitive.

### TKC cluster stuck in "Creating" phase

Check Supervisor events in vCenter. Common causes: insufficient resources on ESXi hosts, network issues with NSX-T, or storage policy not available on target datastore.

### Kubeconfig retrieval fails

Supervisor API endpoint must be reachable from the machine running vmware-vks. Check firewall rules for port 6443.

### Scale operation has no effect

Verify the cluster is in "Running" phase before scaling. Clusters in "Creating" or "Updating" phase reject scale operations.

### Delete namespace rejected unexpectedly

The namespace delete guard prevents deletion when TKC clusters exist inside. Delete all TKC clusters in the namespace first, then retry.

## Version Compatibility

| vSphere | Support | Notes |
|---------|---------|-------|
| 8.0+ | Full | Workload Management APIs available |
| 7.x | Not supported | WCP API surface is different; use vSphere 8.x |

## Related Projects

| Skill | Scope | Tools | Install |
|-------|-------|:-----:|---------|
| **[vmware-aiops](https://github.com/zw008/VMware-AIops)** ⭐ entry point | VM lifecycle, deployment, guest ops, clusters | 31 | `uv tool install vmware-aiops` |
| **[vmware-monitor](https://github.com/zw008/VMware-Monitor)** | Read-only monitoring, alarms, events, VM info | 8 | `uv tool install vmware-monitor` |
| **[vmware-storage](https://github.com/zw008/VMware-Storage)** | Datastores, iSCSI, vSAN | 11 | `uv tool install vmware-storage` |
| **[vmware-nsx](https://github.com/zw008/VMware-NSX)** | NSX networking: segments, gateways, NAT, IPAM | 31 | `uv tool install vmware-nsx-mgmt` |
| **[vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security)** | DFW microsegmentation, security groups, Traceflow | 20 | `uv tool install vmware-nsx-security` |
| **[vmware-aria](https://github.com/zw008/VMware-Aria)** | Aria Ops metrics, alerts, capacity planning | 18 | `uv tool install vmware-aria` |

## License

[MIT](LICENSE)
