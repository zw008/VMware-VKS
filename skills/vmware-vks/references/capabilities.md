# Capabilities

Detailed capability breakdown for all 20 MCP tools.

## 1. Supervisor Layer (Read-Only)

| Tool | What it returns |
|------|----------------|
| `check_vks_compatibility` | vCenter version (pass/fail for 8.x+), WCP enabled status, network backend type |
| `get_supervisor_status` | Cluster ID, API endpoint URL, K8s server version, enabled/disabled state |
| `list_supervisor_storage_policies` | Policy names and IDs (required before creating Namespace or TKC) |

## 2. Namespace Layer

| Operation | CLI | MCP Tool | Confirmation | Details |
|-----------|-----|----------|:------------:|---------|
| List all | `namespace list` | `list_namespaces` | -- | Status, resource usage, phase |
| Get detail | `namespace get <name>` | `get_namespace` | -- | Quotas, storage bindings, role bindings |
| Create | `namespace create <name> --apply` | `create_namespace` | dry_run | CPU/memory quotas, storage policy |
| Update quotas | `namespace update <name>` | `update_namespace` | -- | CPU (MHz), memory (MB) |
| Delete | `namespace delete <name>` | `delete_namespace` | Double | Rejects if TKC clusters exist |
| VM classes | `namespace vm-classes` | `list_vm_classes` | -- | Available VM classes for TKC nodes |

## 3. TKC Layer

| Operation | CLI | MCP Tool | Confirmation | Details |
|-----------|-----|----------|:------------:|---------|
| List clusters | `tkc list [-n ns]` | `list_tkc_clusters` | -- | Status, node counts, K8s version |
| Get detail | `tkc get <name> -n <ns>` | `get_tkc_cluster` | -- | Nodes, versions, health conditions |
| Available versions | `tkc versions -n <ns>` | `get_tkc_available_versions` | -- | Supported K8s versions for Supervisor |
| Create | `tkc create <name> -n <ns> --apply` | `create_tkc_cluster` | dry_run | YAML plan -> confirm -> apply |
| Scale workers | `tkc scale <name> -n <ns> --workers N` | `scale_tkc_cluster` | -- | Adjust worker node count |
| Upgrade | `tkc upgrade <name> -n <ns> --version X.Y` | `upgrade_tkc_cluster` | -- | List available versions first |
| Delete | `tkc delete <name> -n <ns>` | `delete_tkc_cluster` | Double | Rejects if workloads running |

## 4. Access Layer (Read-Only)

| Tool | What it returns |
|------|----------------|
| `get_supervisor_kubeconfig` | Kubeconfig for Supervisor-level K8s API |
| `get_tkc_kubeconfig` | Kubeconfig for a specific TKC cluster (stdout or write to file) |
| `get_harbor_info` | Harbor URL, admin credentials, storage usage |
| `list_namespace_storage_usage` | PVC list and usage stats per Namespace |

## Safety Features

| Feature | Details |
|---------|---------|
| Plan -> Confirm -> Execute -> Log | Structured workflow: show YAML plan, confirm, execute, audit log |
| Dry-Run Default | `create_namespace` and `create_tkc_cluster` default to `dry_run=True` -- returns plan without applying |
| Double Confirmation | Delete ops require `confirmed=True` parameter |
| Namespace Delete Guard | Rejects if TKC clusters exist inside -- prevents orphaned clusters |
| TKC Delete Guard | Rejects if Deployments/StatefulSets/DaemonSets are running -- prevents data loss |
| Force Override | `force=True` on `delete_tkc_cluster` bypasses workload guard (explicit acknowledgement) |
| Audit Trail | All write operations logged to `~/.vmware/audit.db` (SQLite WAL, via vmware-policy) with timestamp, target, operation, parameters, result, user |
| Read-Only Majority | 12/20 tools are read-only |
| SSL Support | `verify_ssl: false` supported for self-signed vCenter certs (enterprise standard) |

## Version Compatibility

| vSphere Version | TKC API | Support |
|----------------|---------|---------|
| 8.0 / 8.0U1-U3 | `cluster.x-k8s.io/v1beta1` (ClusterClass) | Full |
| 9.x (planned) | `cluster.x-k8s.io/v1beta1` | Ready |
| 7.0 U3 | `run.tanzu.vmware.com/v1alpha3` | Not supported |
| 7.0 U1-U2 | `run.tanzu.vmware.com/v1alpha1` | Not supported |

> This skill targets vSphere 8.x+ exclusively. vSphere 7.x uses a different TKC API version -- use `kubectl` directly for 7.x environments.

## Prerequisites

- vCenter Server (no direct ESXi support -- VKS requires vCenter)
- vSphere with Tanzu license (Enterprise Plus or VCF)
- Workload Management (WCP) enabled on at least one cluster
- Network backend: NSX-T (recommended) or VDS + HAProxy (7.x alternative, 8.x limited)
