---
name: vmware-vks
description: >
  Use this skill whenever the user needs to manage vSphere Kubernetes Service (VKS) — Supervisor clusters, vSphere Namespaces, and TKC cluster lifecycle.
  Directly handles: check VKS compatibility, create/delete namespaces, create/scale/upgrade/delete TKC clusters, get kubeconfig, check Harbor registry.
  Always use this skill for "create Kubernetes cluster", "scale workers", "upgrade K8s version", "create namespace", "get kubeconfig", or any VKS/TKC task.
  Do NOT use for vanilla VM operations (use vmware-aiops), non-vSphere Kubernetes (e.g., kubeadm, EKS, AKS), or AVI/AKO load balancing (use vmware-avi).
  For networking use vmware-nsx.
installer:
  kind: uv
  package: vmware-vks
allowed-tools:
  - Bash
metadata: {"openclaw":{"requires":{"env":["VMWARE_VKS_CONFIG"],"bins":["vmware-vks"],"config":["~/.vmware-vks/config.yaml","~/.vmware-vks/.env"]},"optional":{"env":["VMWARE_<TARGET>_PASSWORD"],"bins":["vmware-policy"]},"primaryEnv":"VMWARE_VKS_CONFIG","homepage":"https://github.com/zw008/VMware-VKS","emoji":"☸️","os":["macos","linux"]}}
compatibility: >
  vmware-policy auto-installed as Python dependency (provides @vmware_tool decorator and audit logging). All write operations audited to ~/.vmware/audit.db (single location, no other paths).
  Credentials: Each vCenter target requires a per-target password env var in ~/.vmware-vks/.env following the pattern VMWARE_<TARGET_NAME_UPPER>_PASSWORD (e.g., target "vcenter-01" → VMWARE_VCENTER_01_PASSWORD). Passwords are never logged, never echoed, never included in audit entries. Kubeconfig tokens returned by get_supervisor_kubeconfig and get_tkc_kubeconfig are short-lived vCenter session tokens, not persistent credentials.
---

# VMware VKS

> **Disclaimer**: This is a community-maintained open-source project and is **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom Inc.** "VMware" and "vSphere" are trademarks of Broadcom. Source code is publicly auditable at [github.com/zw008/VMware-VKS](https://github.com/zw008/VMware-VKS) under the MIT license.

AI-powered VMware vSphere Kubernetes Service (VKS) management — 20 MCP tools.

> Requires vSphere 8.x+ with Workload Management enabled.
> **Companion skills**: [vmware-aiops](https://github.com/zw008/VMware-AIops) (VM lifecycle), [vmware-monitor](https://github.com/zw008/VMware-Monitor) (monitoring), [vmware-storage](https://github.com/zw008/VMware-Storage) (storage), [vmware-nsx](https://github.com/zw008/VMware-NSX) (NSX networking), [vmware-nsx-security](https://github.com/zw008/VMware-NSX-Security) (DFW/firewall), [vmware-aria](https://github.com/zw008/VMware-Aria) (metrics/alerts/capacity), [vmware-avi](https://github.com/zw008/VMware-AVI) (AVI/ALB/AKO).
> | [vmware-pilot](../vmware-pilot/SKILL.md) (workflow orchestration) | [vmware-policy](../vmware-policy/SKILL.md) (audit/policy)

## What This Skill Does

| Category | Capabilities | Count |
|----------|-------------|:-----:|
| **Supervisor** | Compatibility check, status, storage policies | 3 |
| **Namespace** | List, get, create with quotas, update, delete with TKC guard, VM classes | 6 |
| **TKC Clusters** | List, get, versions, create, scale, upgrade, delete with workload guard | 7 |
| **Access** | Supervisor kubeconfig, TKC kubeconfig, Harbor registry, storage usage | 4 |

## Quick Install

```bash
uv tool install vmware-vks
vmware-vks doctor
```

## When to Use This Skill

- Check if vSphere environment supports VKS
- Create, update, or delete Supervisor Namespaces with resource quotas
- Deploy, scale, upgrade, or delete TKC (TanzuKubernetesCluster) clusters
- Get kubeconfig for Supervisor or TKC clusters
- Check Harbor registry info or storage usage

**Use companion skills for**:
- VM lifecycle, deployment → `vmware-aiops`
- Inventory, health, alarms → `vmware-monitor`
- iSCSI, vSAN, datastore → `vmware-storage`
- Load balancing, AVI/ALB, AKO, Ingress → `vmware-avi`

## Related Skills — Skill Routing

| User Intent | Recommended Skill |
|-------------|------------------|
| Read-only monitoring | **vmware-monitor** |
| Storage: iSCSI, vSAN | **vmware-storage** |
| VM lifecycle, deployment | **vmware-aiops** |
| vSphere Kubernetes Service (vSphere 8.x+) | **vmware-vks** ← this skill |
| NSX networking: segments, gateways, NAT | **vmware-nsx** |
| NSX security: DFW rules, security groups | **vmware-nsx-security** |
| Aria Ops: metrics, alerts, capacity planning | **vmware-aria** |
| Multi-step workflows with approval | **vmware-pilot** |
| Load balancer, AVI, ALB, AKO, Ingress | **vmware-avi** (`uv tool install vmware-avi`) |
| Audit log query | **vmware-policy** (`vmware-audit` CLI) |

## Common Workflows

### Deploy a New TKC Cluster

1. Check compatibility → `vmware-vks supervisor check --target prod`
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

## Usage Mode

| Scenario | Recommended | Why |
|----------|:-----------:|-----|
| Local/small models (Ollama, Qwen) | **CLI** | ~2K tokens vs ~8K for MCP |
| Cloud models (Claude, GPT-4o) | Either | MCP gives structured JSON I/O |
| Automated pipelines | **MCP** | Type-safe parameters, structured output |

## MCP Tools (20 — 12 read, 8 write)

All accept optional `target` parameter to specify a named vCenter.

| Category | Tool | Type |
|----------|------|:----:|
| **Supervisor** | `check_vks_compatibility` | Read |
| | `get_supervisor_status` | Read |
| | `list_supervisor_storage_policies` | Read |
| **Namespace** | `list_namespaces` | Read |
| | `get_namespace` | Read |
| | `create_namespace` | Write |
| | `update_namespace` | Write |
| | `delete_namespace` | Write |
| | `list_vm_classes` | Read |
| **TKC** | `list_tkc_clusters` | Read |
| | `get_tkc_cluster` | Read |
| | `get_tkc_available_versions` | Read |
| | `create_tkc_cluster` | Write |
| | `scale_tkc_cluster` | Write |
| | `upgrade_tkc_cluster` | Write |
| | `delete_tkc_cluster` | Write |
| **Access** | `get_supervisor_kubeconfig` | Read |
| | `get_tkc_kubeconfig` | Read |
| | `get_harbor_info` | Read |
| | `list_namespace_storage_usage` | Read |

`create_namespace` / `create_tkc_cluster` — defaults to `dry_run=True`, returns a YAML plan for review. Pass `dry_run=False` to apply.

`delete_namespace` — requires `confirmed=True` and rejects if TKC clusters still exist (prevents orphaned clusters).

`delete_tkc_cluster` — requires `confirmed=True` and checks for running workloads. Rejects if found unless `force=True`.

**Credential handling**: `get_supervisor_kubeconfig` and `get_tkc_kubeconfig` return short-lived session tokens (not long-lived credentials). Tokens are derived from the authenticated vCenter session and expire when the session ends. Kubeconfig output is intended for local `kubectl` use — agents should write it to a file (`-o <path>`) rather than displaying tokens in conversation context.

> Full capability details and safety features: see `references/capabilities.md`

## CLI Quick Reference

```bash
# Supervisor
vmware-vks check [--target <name>]
vmware-vks supervisor status <cluster-id> [--target <name>]
vmware-vks supervisor storage-policies [--target <name>]

# Namespace
vmware-vks namespace list [--target <name>]
vmware-vks namespace get <name> [--target <name>]
vmware-vks namespace create <name> --cluster <id> [--cpu <n>] [--memory <mb>] [--storage-policy <name>] [--apply]
vmware-vks namespace update <name> [--cpu <n>] [--memory <mb>] [--target <name>]
vmware-vks namespace delete <name> [--target <name>]

# TKC Clusters
vmware-vks tkc list [-n <namespace>] [--target <name>]
vmware-vks tkc create <name> -n <ns> [--version <v>] [--workers <n>] [--vm-class <name>] [--apply]
vmware-vks tkc scale <name> -n <ns> --workers <n> [--target <name>]
vmware-vks tkc upgrade <name> -n <ns> --version <v> [--target <name>]
vmware-vks tkc delete <name> -n <ns> [--force] [--target <name>]

# Kubeconfig
vmware-vks kubeconfig supervisor -n <namespace> [--target <name>]
vmware-vks kubeconfig get <cluster-name> -n <namespace> [-o <path>] [--target <name>]

# Harbor & Storage
vmware-vks harbor [--target <name>]
vmware-vks storage -n <namespace> [--target <name>]
```

> Full CLI reference with all flags and interactive creation: see `references/cli-reference.md`

## Troubleshooting

### "VKS not compatible" error

Workload Management must be enabled in vCenter. Check: vCenter UI → Workload Management. Requires vSphere 8.x+ with Enterprise Plus or VCF license.

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

## Prerequisites

- vSphere 8.x+ with Workload Management enabled
- Enterprise Plus or VCF license
- NSX-T (recommended) or VDS + HAProxy networking
- Supervisor Cluster configured and running

## Setup

```bash
uv tool install vmware-vks
mkdir -p ~/.vmware-vks
vmware-vks init
```

> All tools are automatically audited via vmware-policy. Audit logs: `vmware-audit log --last 20`

> Full setup guide, security details, and AI platform compatibility: see `references/setup-guide.md`

## Audit & Safety

All operations are automatically audited via vmware-policy (`@vmware_tool` decorator):
- Every tool call logged to `~/.vmware/audit.db` (SQLite, framework-agnostic)
- Policy rules enforced via `~/.vmware/rules.yaml` (deny rules, maintenance windows, risk levels)
- Risk classification: each tool tagged as low/medium/high/critical
- View recent operations: `vmware-audit log --last 20`
- View denied operations: `vmware-audit log --status denied`

vmware-policy is automatically installed as a dependency — no manual setup needed.

## License

MIT — [github.com/zw008/VMware-VKS](https://github.com/zw008/VMware-VKS)
