---
name: vmware-vks
description: >
  AI-powered VMware vSphere with Tanzu (VKS) management.
  Manage Supervisor Namespaces and TanzuKubernetesCluster lifecycle via AI model.
  20 MCP tools: compatibility checks, Namespace CRUD (with quota management),
  TKC lifecycle (create/scale/upgrade/delete), kubeconfig retrieval, Harbor registry, storage usage.
  Requires vSphere 8.x+ with Workload Management (WCP) enabled and a vSphere with Tanzu license.
installer:
  kind: uv
  package: vmware-vks
metadata: {"openclaw":{"requires":{"env":["VMWARE_VKS_CONFIG"],"bins":["vmware-vks"],"config":["~/.vmware-vks/config.yaml"]},"primaryEnv":"VMWARE_VKS_CONFIG","homepage":"https://github.com/zw008/VMware-VKS","emoji":"☸️","os":["macos","linux"]}}
---

# VMware VKS

AI-powered VMware vSphere with Tanzu (VKS) management — 20 MCP tools for Supervisor clusters, vSphere Namespaces, and TanzuKubernetesCluster lifecycle. Manage your Tanzu Kubernetes infrastructure using natural language.

## What This Skill Does

| Category | Examples |
|----------|---------|
| **Supervisor** | compatibility check, cluster status, storage policy discovery |
| **Namespace** | list, create with resource quotas, update CPU/memory limits, delete with TKC guard |
| **TKC** | list clusters, create with YAML plan, scale workers, upgrade K8s version, delete with workload guard |
| **Access** | retrieve Supervisor kubeconfig, TKC kubeconfig, Harbor registry info, storage usage |

## Quick Install

```bash
uv tool install vmware-vks
vmware-vks check
```

## When to Use This Skill

- Check if your vCenter supports VKS before starting (compatibility + WCP status)
- Create and manage vSphere Namespaces with CPU/memory/storage quotas
- Provision TanzuKubernetesCluster — review YAML plan first (`dry_run=True`), then apply
- Scale TKC worker nodes up or down
- Upgrade TKC clusters to newer K8s versions
- Retrieve kubeconfigs for Supervisor and TKC clusters
- Check Harbor embedded registry URL, credentials, and storage usage
- Monitor per-namespace PVC usage statistics

## Related Skills — Skill Routing

> Need VM operations, storage management, or read-only monitoring? Use the right skill:

| User Intent | Recommended Skill | Install |
|-------------|------------------|---------|
| Supervisor, Namespace, TKC lifecycle ← | **vmware-vks** (this skill) | — |
| Read-only monitoring, alarms, events | **vmware-monitor** | `uv tool install vmware-monitor` |
| Power on/off VM, create, delete, deploy OVA | **vmware-aiops** | `uv tool install vmware-aiops` |
| Datastores, iSCSI, vSAN | **vmware-storage** | `uv tool install vmware-storage` |

## Quick Install

All install methods fetch from the same source: [github.com/zw008/VMware-VKS](https://github.com/zw008/VMware-VKS) (MIT licensed). We recommend reviewing the source code before installing.

```bash
# Via Skills.sh (fetches from GitHub)
npx skills add zw008/VMware-VKS

# Via ClawHub (fetches from ClawHub registry snapshot of GitHub)
clawhub install vmware-vks

# Via PyPI (recommended for version pinning)
uv tool install vmware-vks==1.2.3
```

### Claude Code

```
/plugin marketplace add zw008/VMware-VKS
/plugin install vmware-ops
/vmware-ops:vmware-vks
```

## Usage Mode

Choose the best mode based on your environment:

| Scenario | Recommended Mode | Why |
|----------|-----------------|-----|
| **Cloud models** (Claude, GPT-4o, Gemini) | MCP or CLI | Both work well; MCP gives structured JSON I/O |
| **Local/small models** (Ollama, Llama, Qwen <32B) | **CLI** | Lower token cost (~2K vs ~8K), higher accuracy — small models struggle with 20 MCP tool schemas |
| **Token-sensitive workflows** | **CLI** | CLI via SKILL.md uses ~2K tokens; MCP loads ~8K tokens of tool definitions into every conversation |
| **Automated pipelines / Agent chaining** | **MCP** | Structured JSON input/output, type-safe parameters, no shell parsing |

### Calling Priority

- **MCP-native tools** (Claude Code, Cursor): MCP first, CLI fallback
- **Local models / Token-sensitive**: CLI first (MCP not needed)

### CLI Examples

```bash
# Pre-flight check
vmware-vks check

# Supervisor
vmware-vks supervisor status domain-c1
vmware-vks supervisor storage-policies

# Namespace
vmware-vks namespace list
vmware-vks namespace get dev
vmware-vks namespace create dev --cluster domain-c1 --storage-policy vsphere-storage --apply
vmware-vks namespace update dev --cpu 20000 --memory 65536
vmware-vks namespace delete dev

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

# Access
vmware-vks kubeconfig supervisor -n dev
vmware-vks kubeconfig get my-cluster -n dev
vmware-vks kubeconfig get my-cluster -n dev -o ~/.kube/my-cluster.yaml
vmware-vks harbor
vmware-vks storage -n dev
```

### MCP Mode (Optional)

For Claude Code / Cursor users who prefer structured tool calls, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vmware-vks": {
      "command": "uvx",
      "args": ["vmware-vks-mcp"],
      "env": {
        "VMWARE_VKS_CONFIG": "/Users/you/.vmware-vks/config.yaml",
        "VMWARE_MYVENTER_PASSWORD": "your-password"
      }
    }
  }
}
```

## MCP Tools (20)

All accept optional `target` parameter to specify a named vCenter.

| Category | Tool | Type | Safety |
|----------|------|------|--------|
| **Supervisor** | `check_vks_compatibility` | Read | — |
| **Supervisor** | `get_supervisor_status` | Read | — |
| **Supervisor** | `list_supervisor_storage_policies` | Read | — |
| **Namespace** | `list_namespaces` | Read | — |
| **Namespace** | `get_namespace` | Read | — |
| **Namespace** | `create_namespace` | Write | `dry_run=True` default |
| **Namespace** | `update_namespace` | Write | — |
| **Namespace** | `delete_namespace` | Write | `dry_run=True` + TKC guard |
| **Namespace** | `list_vm_classes` | Read | — |
| **TKC** | `list_tkc_clusters` | Read | — |
| **TKC** | `get_tkc_cluster` | Read | — |
| **TKC** | `get_tkc_available_versions` | Read | — |
| **TKC** | `create_tkc_cluster` | Write | `dry_run=True` default |
| **TKC** | `scale_tkc_cluster` | Write | — |
| **TKC** | `upgrade_tkc_cluster` | Write | — |
| **TKC** | `delete_tkc_cluster` | Write | `dry_run=True` + workload guard |
| **Access** | `get_supervisor_kubeconfig` | Read | — |
| **Access** | `get_tkc_kubeconfig` | Read | — |
| **Access** | `get_harbor_info` | Read | — |
| **Access** | `list_namespace_storage_usage` | Read | — |

`create_namespace` / `create_tkc_cluster` — defaults to `dry_run=True`, returns a YAML plan for review. Pass `dry_run=False` to apply.

`delete_namespace` — requires `confirmed=True` and rejects the request if TKC clusters still exist inside the namespace (prevents orphaned clusters).

`delete_tkc_cluster` — requires `confirmed=True` and checks for running Deployments/StatefulSets/DaemonSets inside the cluster. Rejects if workloads are found unless `force=True` is explicitly passed.

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

## Capabilities

### 1. Supervisor Layer (Read-Only)

| Tool | What it returns |
|------|----------------|
| `check_vks_compatibility` | vCenter version (pass/fail for 8.x+), WCP enabled status, network backend type |
| `get_supervisor_status` | Cluster ID, API endpoint URL, K8s server version, enabled/disabled state |
| `list_supervisor_storage_policies` | Policy names and IDs (required before creating Namespace or TKC) |

### 2. Namespace Layer

| Operation | CLI | MCP Tool | Confirmation | Details |
|-----------|-----|----------|:------------:|---------|
| List all | `namespace list` | `list_namespaces` | — | Status, resource usage, phase |
| Get detail | `namespace get <name>` | `get_namespace` | — | Quotas, storage bindings, role bindings |
| Create | `namespace create <name> --apply` | `create_namespace` | dry_run | CPU/memory quotas, storage policy |
| Update quotas | `namespace update <name>` | `update_namespace` | — | CPU (MHz), memory (MB) |
| Delete | `namespace delete <name>` | `delete_namespace` | Double | Rejects if TKC clusters exist |
| VM classes | `namespace vm-classes` | `list_vm_classes` | — | Available VM classes for TKC nodes |

### 3. TKC Layer

| Operation | CLI | MCP Tool | Confirmation | Details |
|-----------|-----|----------|:------------:|---------|
| List clusters | `tkc list [-n ns]` | `list_tkc_clusters` | — | Status, node counts, K8s version |
| Get detail | `tkc get <name> -n <ns>` | `get_tkc_cluster` | — | Nodes, versions, health conditions |
| Available versions | `tkc versions -n <ns>` | `get_tkc_available_versions` | — | Supported K8s versions for Supervisor |
| Create | `tkc create <name> -n <ns> --apply` | `create_tkc_cluster` | dry_run | YAML plan → confirm → apply |
| Scale workers | `tkc scale <name> -n <ns> --workers N` | `scale_tkc_cluster` | — | Adjust worker node count |
| Upgrade | `tkc upgrade <name> -n <ns> --version X.Y` | `upgrade_tkc_cluster` | — | List available versions first |
| Delete | `tkc delete <name> -n <ns>` | `delete_tkc_cluster` | Double | Rejects if workloads running |

### 4. Access Layer (Read-Only)

| Tool | What it returns |
|------|----------------|
| `get_supervisor_kubeconfig` | Kubeconfig for Supervisor-level K8s API |
| `get_tkc_kubeconfig` | Kubeconfig for a specific TKC cluster (stdout or write to file) |
| `get_harbor_info` | Harbor URL, admin credentials, storage usage |
| `list_namespace_storage_usage` | PVC list and usage stats per Namespace |

### Interactive TKC Creation (CLI)

When params are missing, the CLI guides interactively:

```
$ vmware-vks tkc create my-cluster -n dev
? K8s version (v1.27 / v1.28 / v1.29): v1.28
? VM class (best-effort-small / best-effort-large / guaranteed-large): best-effort-large
? Control plane nodes (1 / 3): 1
? Worker nodes [3]: 3
? Storage policy (vsphere-storage / vsphere-gold): vsphere-storage

Plan:
  Cluster   : my-cluster
  Namespace : dev
  K8s       : v1.28.4+vmware.1
  Control   : 1x best-effort-large
  Workers   : 3x best-effort-large
  Storage   : vsphere-storage

Apply? [y/N]: y
```

The same guided flow applies in MCP: the AI model collects missing params through follow-up questions before generating the YAML and applying.

## Safety Features

| Feature | Details |
|---------|---------|
| Plan → Confirm → Execute → Log | Structured workflow: show YAML plan, confirm, execute, audit log |
| Dry-Run Default | `create_namespace` and `create_tkc_cluster` default to `dry_run=True` — returns plan without applying |
| Double Confirmation | Delete ops require `confirmed=True` parameter |
| Namespace Delete Guard | Rejects if TKC clusters exist inside — prevents orphaned clusters |
| TKC Delete Guard | Rejects if Deployments/StatefulSets/DaemonSets are running — prevents data loss |
| Force Override | `force=True` on `delete_tkc_cluster` bypasses workload guard (explicit acknowledgement) |
| Audit Trail | All write operations logged to `~/.vmware-vks/audit.log` (JSON Lines) with timestamp, target, operation, parameters, result, user |
| Read-Only Majority | 12/20 tools are read-only |
| SSL Support | `verify_ssl: false` supported for self-signed vCenter certs (enterprise standard) |

## Version Compatibility

| vSphere Version | TKC API | Support |
|----------------|---------|---------|
| 8.0 / 8.0U1–U3 | `cluster.x-k8s.io/v1beta1` (ClusterClass) | ✅ Full |
| 9.x (planned) | `cluster.x-k8s.io/v1beta1` | ✅ Ready |
| 7.0 U3 | `run.tanzu.vmware.com/v1alpha3` | ❌ Not supported |
| 7.0 U1–U2 | `run.tanzu.vmware.com/v1alpha1` | ❌ Not supported |

> This skill targets vSphere 8.x+ exclusively. vSphere 7.x uses a different TKC API version — use `kubectl` directly for 7.x environments.

**Prerequisites:**
- vCenter Server (no direct ESXi support — VKS requires vCenter)
- vSphere with Tanzu license (Enterprise Plus or VCF)
- Workload Management (WCP) enabled on at least one cluster
- Network backend: NSX-T (recommended) or VDS + HAProxy (7.x alternative, 8.x limited)

## Supported AI Platforms

| Platform | Status |
|----------|--------|
| Claude Code | ✅ Native Skill |
| Goose (Block) | ✅ MCP via stdio |
| Cursor | ✅ MCP mode |
| Continue | ✅ MCP mode |
| VS Code Copilot | ✅ MCP mode |
| Python CLI | ✅ Standalone |

## Setup

```bash
# 1. Install from PyPI
uv tool install vmware-vks

# 2. Configure
mkdir -p ~/.vmware-vks
cat > ~/.vmware-vks/config.yaml << 'EOF'
targets:
  - name: vcenter01
    host: vcenter.example.com
    username: admin@vsphere.local
    port: 443
    verify_ssl: false
EOF

echo "VMWARE_VKS_VCENTER01_PASSWORD=your_password" > ~/.vmware-vks/.env
chmod 600 ~/.vmware-vks/.env

# 3. Verify
vmware-vks check
```

### What Gets Installed

The `vmware-vks` package installs a Python CLI binary and its dependencies (pyVmomi, kubernetes Python client, Typer, Rich, python-dotenv, mcp). No background services or daemons are started during installation.

### Development Install

```bash
git clone https://github.com/zw008/VMware-VKS.git
cd VMware-VKS
uv venv && source .venv/bin/activate
uv pip install -e .
```

## CLI Reference

```bash
# Pre-flight check
vmware-vks check [--target <name>]

# Supervisor
vmware-vks supervisor status <cluster-id> [--target <name>]
vmware-vks supervisor storage-policies [--target <name>]

# Namespace
vmware-vks namespace list [--target <name>]
vmware-vks namespace get <name> [--target <name>]
vmware-vks namespace create <name> --cluster <id> [--cpu <n>] [--memory <mb>] [--storage-policy <name>] [--apply]
vmware-vks namespace update <name> [--cpu <n>] [--memory <mb>] [--target <name>]
vmware-vks namespace delete <name> [--target <name>]
vmware-vks namespace vm-classes [--target <name>]

# TKC
vmware-vks tkc list [-n <namespace>] [--target <name>]
vmware-vks tkc get <cluster-name> -n <namespace> [--target <name>]
vmware-vks tkc versions -n <namespace> [--target <name>]
vmware-vks tkc create <cluster-name> -n <namespace> [--version <k8s-ver>] [--control-plane <n>] [--workers <n>] [--vm-class <name>] [--storage-policy <name>] [--apply]
vmware-vks tkc scale <cluster-name> -n <namespace> --workers <n> [--target <name>]
vmware-vks tkc upgrade <cluster-name> -n <namespace> --version <k8s-ver> [--target <name>]
vmware-vks tkc delete <cluster-name> -n <namespace> [--force] [--target <name>]

# Kubeconfig
vmware-vks kubeconfig supervisor -n <namespace> [--target <name>]
vmware-vks kubeconfig get <cluster-name> -n <namespace> [-o <output-path>] [--target <name>]

# Harbor & Storage
vmware-vks harbor [--target <name>]
vmware-vks storage -n <namespace> [--target <name>]
```

## Security

This skill follows a defense-in-depth approach with six security properties:

1. **Source Code** — MIT-licensed, fully auditable. No obfuscated logic. Source at [github.com/zw008/VMware-VKS](https://github.com/zw008/VMware-VKS). The `uv` installer fetches the `vmware-vks` package from PyPI, which is built from this GitHub repository.

2. **Credentials** — `config.yaml` contains vCenter hostnames and usernames only. Passwords are loaded exclusively from `~/.vmware-vks/.env` (read via `python-dotenv`). Passwords are never logged, never echoed to CLI output, and never included in audit log entries.

3. **Network Scope** — No webhook, HTTP listener, or inbound network connection is ever started. MCP transport is stdio only. All outbound connections go to the user-configured vCenter host only.

4. **TLS Verification** — `verify_ssl: false` is supported for self-signed vCenter certificates (standard in enterprise environments). Set `verify_ssl: true` in config for CA-signed certificates. Applies to both the SOAP API and REST API connections.

5. **Prompt Injection Protection** — All tool inputs are passed as typed Python parameters (`str`, `int`, `bool`), never interpolated into shell commands. No `eval`, `exec`, or subprocess calls with user-controlled data.

6. **Least Privilege** — 12/20 tools are read-only. All write operations default to `dry_run=True` where applicable. Destructive operations (`delete_namespace`, `delete_tkc_cluster`) require explicit `confirmed=True` and pass through safety guards that cannot be bypassed without `force=True`. All write operations are audit-logged to `~/.vmware-vks/audit.log`.

## License

MIT
