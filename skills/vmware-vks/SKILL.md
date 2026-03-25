---
name: vmware-vks
description: >
  VMware vSphere with Tanzu (VKS) management: Supervisor clusters, vSphere Namespaces, TanzuKubernetesCluster lifecycle.
  Requires vSphere 8.x+ with Workload Management (WCP) enabled and a vSphere with Tanzu license.
  20 MCP tools: compatibility checks, Namespace CRUD, TKC lifecycle (create/scale/upgrade/delete), kubeconfig retrieval, Harbor registry, storage usage.
installer:
  kind: uv
  package: vmware-vks
metadata: {"openclaw":{"requires":{"env":["VMWARE_VKS_CONFIG"],"bins":["vmware-vks"],"config":["~/.vmware-vks/config.yaml"]},"primaryEnv":"VMWARE_VKS_CONFIG","homepage":"https://github.com/zw008/VMware-VKS","emoji":"☸️","os":["macos","linux"]}}
---

# VMware VKS

VMware vSphere with Tanzu (VKS) management — 20 MCP tools for Supervisor clusters, vSphere Namespaces, and TanzuKubernetesCluster lifecycle. Requires vSphere 8.x+ with Workload Management enabled.

## What This Skill Does

| Category | Tools | Type |
|----------|-------|------|
| **Supervisor** | compatibility check, cluster status, storage policies | Read-only |
| **Namespace** | list, get, create, update, delete, VM classes | Read + Write |
| **TKC** | list, get, available versions, create, scale, upgrade, delete | Read + Write |
| **Access** | Supervisor kubeconfig, TKC kubeconfig, Harbor info, storage usage | Read-only |

## Quick Install

```bash
uv tool install vmware-vks
vmware-vks check
```

## When to Use

- Check if vCenter supports VKS before starting (compatibility + WCP status)
- Create and manage vSphere Namespaces with resource quotas
- Provision TanzuKubernetesCluster — get YAML plan first (dry_run=True), then apply
- Retrieve kubeconfigs for Supervisor and TKC clusters
- Monitor Harbor embedded registry and Namespace storage usage

## Related Skills — Skill Routing

> Need VM operations or storage management? Use the right skill:

| User Intent | Recommended Skill | Install |
|-------------|------------------|---------|
| Supervisor, Namespace, TKC lifecycle ← | **vmware-vks** (this skill) | — |
| Read-only monitoring, alarms, events | **vmware-monitor** | `uv tool install vmware-monitor` |
| Power on/off VM, create, delete, deploy OVA | **vmware-aiops** | `uv tool install vmware-aiops` |
| Datastores, iSCSI, vSAN | **vmware-storage** | `uv tool install vmware-storage` |

## Setup

```bash
uv tool install vmware-vks

mkdir -p ~/.vmware-vks
cp config.example.yaml ~/.vmware-vks/config.yaml
# Edit with your vCenter credentials

echo "VMWARE_MY_VCENTER_PASSWORD=your_password" > ~/.vmware-vks/.env
chmod 600 ~/.vmware-vks/.env

vmware-vks check
```

## CLI Usage

```bash
# Pre-flight check
vmware-vks check

# Supervisor
vmware-vks supervisor status domain-c1
vmware-vks supervisor storage-policies

# Namespace
vmware-vks namespace list
vmware-vks namespace get dev
vmware-vks namespace create dev --cluster domain-c1 --storage-policy vsphere-storage
vmware-vks namespace create dev --cluster domain-c1 --storage-policy vsphere-storage --apply
vmware-vks namespace update dev --cpu 20000 --memory 65536
vmware-vks namespace delete dev
vmware-vks namespace vm-classes

# TKC
vmware-vks tkc list
vmware-vks tkc list -n dev
vmware-vks tkc get my-cluster -n dev
vmware-vks tkc versions -n dev
vmware-vks tkc create my-cluster -n dev --version v1.28.4+vmware.1 --vm-class best-effort-large
vmware-vks tkc create my-cluster -n dev --apply
vmware-vks tkc scale my-cluster -n dev --workers 5
vmware-vks tkc upgrade my-cluster -n dev --version v1.29.2+vmware.1
vmware-vks tkc delete my-cluster -n dev

# Kubeconfig
vmware-vks kubeconfig supervisor -n dev
vmware-vks kubeconfig get my-cluster -n dev
vmware-vks kubeconfig get my-cluster -n dev -o ~/.kube/my-cluster.yaml

# Harbor & Storage
vmware-vks harbor
vmware-vks storage -n dev
```

## MCP Tools (20)

All accept optional `target` parameter to specify a named vCenter.

| Category | Tool | Type |
|----------|------|------|
| **Supervisor** | `check_vks_compatibility` | Read |
| **Supervisor** | `get_supervisor_status` | Read |
| **Supervisor** | `list_supervisor_storage_policies` | Read |
| **Namespace** | `list_namespaces` | Read |
| **Namespace** | `get_namespace` | Read |
| **Namespace** | `create_namespace` | Write (dry_run=True default) |
| **Namespace** | `update_namespace` | Write |
| **Namespace** | `delete_namespace` | Write (dry_run=True + TKC guard) |
| **Namespace** | `list_vm_classes` | Read |
| **TKC** | `list_tkc_clusters` | Read |
| **TKC** | `get_tkc_cluster` | Read |
| **TKC** | `get_tkc_available_versions` | Read |
| **TKC** | `create_tkc_cluster` | Write (dry_run=True default) |
| **TKC** | `scale_tkc_cluster` | Write |
| **TKC** | `upgrade_tkc_cluster` | Write |
| **TKC** | `delete_tkc_cluster` | Write (dry_run=True + workload guard) |
| **Access** | `get_supervisor_kubeconfig` | Read |
| **Access** | `get_tkc_kubeconfig` | Read |
| **Access** | `get_harbor_info` | Read |
| **Access** | `list_namespace_storage_usage` | Read |

## Security

This skill follows a defense-in-depth approach with six security properties:

1. **Source Code** — MIT-licensed, auditable. No obfuscated logic. Source at `https://github.com/zw008/VMware-VKS`.

2. **Config File Contents** — `config.yaml` contains vCenter hostnames and usernames only. Passwords are loaded exclusively from `~/.vmware-vks/.env` (environment variable injection). The `.env` file is never read into config objects and never logged.

3. **Webhook Data Scope** — No webhook or HTTP listener is started. MCP transport is stdio only. No inbound network connections are accepted.

4. **TLS Verification** — TLS verification is disabled by default to support self-signed vCenter certificates (common in enterprise environments). Production deployments with trusted certificates should set `verify_ssl: true` in config. This trade-off is documented explicitly.

5. **Prompt Injection Protection** — All tool inputs are passed as typed Python parameters (str, int, bool), never interpolated into shell commands or SQL. No `eval`, `exec`, or subprocess calls with user data.

6. **Least Privilege** — 12/20 tools are read-only. Write operations require explicit parameters. Destructive operations (`delete_namespace`, `delete_tkc_cluster`, `create_namespace`, `create_tkc_cluster`) default to `dry_run=True` — the agent must explicitly pass `dry_run=False` to make changes. `delete_namespace` rejects the request if TKC clusters exist inside. `delete_tkc_cluster` rejects if workloads are running (unless `force=True`). All write operations are audit-logged to `~/.vmware-vks/audit.log`.

## Architecture

```
User (natural language)
  ↓
AI Agent (Claude Code / Goose / Cursor)
  ↓ reads SKILL.md
vmware-vks CLI or MCP
  ↓ pyVmomi (vSphere SOAP API) + kubernetes client (Supervisor K8s API)
vCenter Server 8.x+ (Workload Management enabled)
  ↓
Supervisor Cluster / vSphere Namespaces / TKC Clusters
```
