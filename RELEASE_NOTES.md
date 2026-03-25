# Release Notes

## v0.1.0 (2026-03-25)

### New Features

**Phase 1 — Supervisor + Namespace (9 tools)**
- `check_vks_compatibility` — vCenter version check + WCP status
- `get_supervisor_status` — Supervisor cluster status and K8s API endpoint
- `list_supervisor_storage_policies` — Available storage policies
- `list_namespaces` — All vSphere Namespaces with status
- `get_namespace` — Namespace detail (quotas, storage, roles)
- `create_namespace` — Create Namespace with dry-run preview
- `update_namespace` — Modify quotas and storage policy
- `delete_namespace` — Delete with TKC guard (rejects if clusters exist)
- `list_vm_classes` — Available VM classes for TKC sizing

**Phase 2 — TKC + Access (11 tools)**
- `list_tkc_clusters` — TanzuKubernetesCluster list with status
- `get_tkc_cluster` — Cluster detail (nodes, health, conditions)
- `get_tkc_available_versions` — Supported K8s versions on Supervisor
- `create_tkc_cluster` — Create TKC with YAML plan + dry-run default
- `scale_tkc_cluster` — Scale worker node count
- `upgrade_tkc_cluster` — Upgrade K8s version
- `delete_tkc_cluster` — Delete with workload guard
- `get_supervisor_kubeconfig` — Supervisor kubeconfig YAML
- `get_tkc_kubeconfig` — TKC kubeconfig (stdout or file)
- `get_harbor_info` — Embedded Harbor registry info
- `list_namespace_storage_usage` — PVC list and capacity stats

**CLI**
- `vmware-vks check` — Pre-flight diagnostics
- `vmware-vks supervisor status|storage-policies`
- `vmware-vks namespace list|get|create|update|delete|vm-classes`
- `vmware-vks tkc list|get|versions|create|scale|upgrade|delete`
- `vmware-vks kubeconfig supervisor|get`
- `vmware-vks harbor`
- `vmware-vks storage`

### Requirements
- vSphere 8.0+ with Workload Management (Supervisor) enabled
- vSphere with Tanzu license (Enterprise Plus or VCF)
