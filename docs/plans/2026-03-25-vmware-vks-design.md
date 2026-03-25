# vmware-vks Design

> Date: 2026-03-25
> Status: Approved
> vSphere target: 8.x+ (9.x ready)

---

## Overview

MCP Skill + CLI tool for managing vSphere with Tanzu (VKS) — Supervisor Namespaces and TanzuKubernetesCluster lifecycle — via AI model or command line.

**Two delivery modes:**
- `vmware-vks` CLI → direct use by ops engineers
- `vmware-vks-mcp` MCP server → AI model tool calls (Claude, GPT, etc.)

---

## Architecture

### Dual-layer connection

```
Layer 1: pyVmomi → vCenter REST API
  - Supervisor status, storage policies, compatibility check
  - Namespace CRUD, quota management, VM class listing
  - Harbor registry info, PVC usage

Layer 2: kubernetes Python client → Supervisor K8s API endpoint
  - TKC CR apply / get / delete (cluster.x-k8s.io/v1beta1)
  - Kubeconfig injected from Layer 1 namespace detail response
```

### Directory structure

```
VMware-VKS/
├── mcp_server/
│   ├── __init__.py
│   ├── __main__.py
│   └── server.py                  ← FastMCP, pure delegation layer
├── vmware_vks/
│   ├── __init__.py
│   ├── config.py                  ← Frozen dataclass config, password via env var
│   ├── connection.py              ← VcenterConnection + K8sConnection managers
│   ├── cli.py                     ← Typer CLI (namespace/tkc/supervisor/kubeconfig)
│   ├── doctor.py                  ← Pre-flight: vCenter version + WCP enabled check
│   └── ops/
│       ├── __init__.py
│       ├── supervisor.py          ← Supervisor status, storage policies, compatibility
│       ├── namespace.py           ← Namespace CRUD + quota + workload guard
│       ├── tkc.py                 ← TKC lifecycle: YAML gen + K8s apply
│       ├── kubeconfig.py          ← kubeconfig retrieval (supervisor + TKC)
│       ├── harbor.py              ← Harbor registry info
│       └── storage.py             ← StorageClass / PVC usage
├── tests/
│   ├── test_no_destructive_vm_code.py   ← Guard: no pyVmomi VM lifecycle ops
│   ├── test_config.py
│   ├── test_supervisor.py
│   ├── test_namespace.py
│   └── test_tkc.py
├── skills/vmware-vks/SKILL.md
├── pyproject.toml
├── server.json
├── config.example.yaml
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
├── README-CN.md
└── RELEASE_NOTES.md
```

---

## MCP Tools (20 total)

### Supervisor layer (3, read-only)

| Tool | Description |
|------|-------------|
| `check_vks_compatibility` | vCenter version, WCP status, network backend type |
| `get_supervisor_status` | Supervisor enabled state, API endpoint, K8s version |
| `list_supervisor_storage_policies` | Available storage policies (required before create) |

### Namespace layer (6)

| Tool | Description |
|------|-------------|
| `list_namespaces` | All namespaces + status + resource usage |
| `get_namespace` | Single namespace detail (quotas, storage, role bindings) |
| `create_namespace` | Create with interactive guidance if params missing |
| `update_namespace` | Modify CPU/memory quotas or storage policy |
| `delete_namespace` | Double-confirm + guard: reject if TKC clusters exist inside |
| `list_vm_classes` | Available VM classes (required before TKC create) |

### TKC layer (7)

| Tool | Description |
|------|-------------|
| `list_tkc_clusters` | All TKC clusters + status + node count |
| `get_tkc_cluster` | Single TKC detail (nodes, version, health) |
| `get_tkc_available_versions` | K8s versions supported by current Supervisor |
| `create_tkc_cluster` | Params → YAML plan → user confirm → apply |
| `scale_tkc_cluster` | Scale worker node count |
| `upgrade_tkc_cluster` | Upgrade K8s version (list available first) |
| `delete_tkc_cluster` | Double-confirm + guard: reject if workloads running |

### Access layer (4)

| Tool | Description |
|------|-------------|
| `get_supervisor_kubeconfig` | Supervisor-level kubeconfig |
| `get_tkc_kubeconfig` | TKC kubeconfig (stdout or write to file) |
| `get_harbor_info` | Harbor URL, storage usage, login info |
| `list_namespace_storage_usage` | PVC list + usage stats per namespace |

---

## CLI Design

```bash
# Pre-flight
vmware-vks check

# Supervisor
vmware-vks supervisor status
vmware-vks supervisor storage-policies

# Namespace
vmware-vks namespace list
vmware-vks namespace get <name>
vmware-vks namespace create <name> [--cpu N] [--memory Gi] [--storage-policy NAME]
vmware-vks namespace update <name> [--cpu N] [--memory Gi]
vmware-vks namespace delete <name>          # double-confirm + TKC guard
vmware-vks namespace vm-classes

# TKC
vmware-vks tkc list [-n NAMESPACE]
vmware-vks tkc get <name> -n <namespace>
vmware-vks tkc versions                     # available K8s versions
vmware-vks tkc create <name> -n <namespace> [--version X.Y] [--control-plane N] [--workers N] [--vm-class NAME]
vmware-vks tkc scale <name> -n <namespace> --workers N
vmware-vks tkc upgrade <name> -n <namespace> --version X.Y
vmware-vks tkc delete <name> -n <namespace> # double-confirm + workload guard

# Access
vmware-vks kubeconfig supervisor
vmware-vks kubeconfig get <tkc-name> -n <namespace> [--output PATH]
vmware-vks harbor info
vmware-vks storage usage -n <namespace>
```

### Interactive guidance (params missing)

```
$ vmware-vks tkc create my-cluster -n dev
? K8s version (1.27 / 1.28 / 1.29): 1.28
? VM class (best-effort-small / best-effort-large / guaranteed-large): best-effort-large
? Control plane nodes (1 / 3): 1
? Worker nodes [3]: 3
? Storage policy (vsphere-storage / vsphere-gold): vsphere-storage

Plan:
  Cluster : my-cluster
  Namespace: dev
  K8s     : 1.28
  Control : 1x best-effort-large
  Workers : 3x best-effort-large
  Storage : vsphere-storage

Apply? [y/N]: y
```

Same flow applies to MCP: model collects missing params through follow-up questions before generating YAML.

---

## Safety Design

### Namespace delete guard
```
1. Double-confirm (type namespace name)
2. Query TKC clusters inside namespace
3. If any TKC exists → reject with list of clusters to delete first
4. Proceed only if namespace is empty
```

### TKC delete guard
```
1. Double-confirm (type cluster name)
2. Query running Deployments/StatefulSets/DaemonSets in cluster
3. If workloads found → reject with workload summary
4. dry_run=True → show what would be deleted without executing
5. Proceed only if cluster is empty or --force explicitly passed
```

### Audit log
All write operations logged to `~/.vmware-vks/audit.log` (JSON Lines):
```json
{"timestamp": "2026-03-25T10:00:00Z", "target": "vcenter01", "operation": "create_namespace", "resource": "dev", "parameters": {...}, "result": "success", "user": "admin@vsphere.local"}
```

---

## Configuration

```yaml
# ~/.vmware-vks/config.yaml
targets:
  - name: vcenter01
    host: vcenter.example.com
    username: admin@vsphere.local
    port: 443
    verify_ssl: false
```

```bash
# ~/.vmware-vks/.env
VMWARE_VKS_VCENTER01_PASSWORD=secret
```

---

## Dependencies

```toml
dependencies = [
    "pyvmomi>=8.0.3.0,<10.0",
    "kubernetes>=29.0,<35.0",       # K8s Python client for TKC CR ops
    "pyaml>=24.0,<27.0",
    "typer>=0.12,<1.0",
    "rich>=13.0,<15.0",
    "python-dotenv>=1.0,<2.0",
    "mcp[cli]>=1.0,<2.0",
]
```

---

## Implementation Phases

### Phase 1 — Supervisor + Namespace (9 tools + CLI)
- `check_vks_compatibility`, `get_supervisor_status`, `list_supervisor_storage_policies`
- `list_namespaces`, `get_namespace`, `create_namespace`, `update_namespace`, `delete_namespace`, `list_vm_classes`
- Full CLI for all 9 tools
- doctor.py pre-flight check
- Tests: config, supervisor, namespace

### Phase 2 — TKC + Access (11 tools + CLI)
- All TKC tools (7) + access tools (4)
- kubernetes Python client integration
- TKC YAML generator (v1beta1 ClusterClass for 8.x)
- Workload guard for delete
- Tests: tkc, kubeconfig, harbor, storage

---

## Version & Publishing

- Initial release: v0.1.0 (Phase 1 complete)
- v1.0.0: Phase 2 complete, full test coverage
- Channels: PyPI, GitHub Release, MCP Registry, ClawHub, Smithery
