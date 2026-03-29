# Release Notes

## v1.4.0 — 2026-03-29

### Architecture: Unified Audit & Policy

- **vmware-policy integration**: All MCP tools now wrapped with `@vmware_tool` decorator
- **Unified audit logging**: Operations logged to `~/.vmware/audit.db` (SQLite WAL), replacing per-skill JSON Lines logs
- **Policy enforcement**: `check_allowed()` with rules.yaml, maintenance windows, risk-level gating
- **Sanitize consolidation**: Replaced local `_sanitize()` with shared `vmware_policy.sanitize()`
- **Risk classification**: Each tool tagged with risk_level (low/medium/high) for confirmation gating
- **Agent detection**: Audit logs identify calling agent (Claude/Codex/local)
- **New family members**: vmware-policy (audit/policy infrastructure) + vmware-pilot (workflow orchestration)

---

## v1.3.1 — 2026-03-27

### Family expansion: NSX, NSX-Security, Aria

- Added vmware-nsx, vmware-nsx-security, vmware-aria to companion skills routing table
- README updated with complete 7-skill family table
- vmware-aiops is now the family entry point (`vmware-aiops hub status`)

---

## v1.3.0 — 2026-03-26

### Docs / Skill optimization

- SKILL.md restructured with progressive disclosure (3-level loading)
- Created `references/` directory: cli-reference.md, capabilities.md, setup-guide.md
- Added trigger phrases to YAML description for better skill auto-loading
- Added Common Workflows section (Deploy TKC, Scale workers, Namespace management)
- Added Troubleshooting section (6 common issues)
- README.md and README-CN.md updated with Companion Skills, Workflows, Troubleshooting

---

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
