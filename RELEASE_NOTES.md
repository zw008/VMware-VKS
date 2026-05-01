## v1.5.17 (2026-05-01)

**Family alignment** — no source changes in this skill.

This release tracks vmware-pilot v1.5.17 (new `investigate_alert` template + `review_workflow` MCP tool + `parallel_group` step type) and vmware-policy v1.5.17 (L5 pattern matcher integrated into `@vmware_tool`). Both work with the existing skill MCP surface unchanged.

- **align:** Family version bump to v1.5.17.

## v1.5.16 (2026-04-30)

**Enterprise Harness Engineering alignment** — adapted from the Linkloud × addxai framework articles ([part 1](https://mp.weixin.qq.com/s/hz4W7ILHJ1yz_pG0Z1xP-A), [part 2](https://mp.weixin.qq.com/s/F3qYbyB3S8oIqx-Y4BrWNQ)).

- **docs:** "Automation Level Reference" section in `references/capabilities.md` — every tool tagged L1-L5 per the EHE framework.
- **docs:** Common Workflows in `SKILL.md` rewritten with pre-flight judgment for TKC deploy (storage policy + VM class + quota), worker scaling (drain before scale-down), and namespace quota changes.
- **align:** Family version bump to v1.5.16.

## v1.5.15 (2026-04-29)

**UX improvements from real user feedback**

- **feat:** New top-level CLI subcommand `vmware-vks mcp` starts the MCP server. Single command, single binary on PATH after `uv tool install vmware-vks` — no more `uvx --from`, no PyPI re-resolve, no TLS-proxy issues.
- **feat:** Default `verify_ssl: true` on new targets (was `false`). Self-signed cert environments must now opt in explicitly with `verify_ssl: false` in `config.yaml`. Strengthens default security posture.
- **docs:** README, SKILL.md, setup-guide.md, and `examples/mcp-configs/*.json` switched to `command: "vmware-vks"`, `args: ["mcp"]`. uvx form moved to fallback with TLS-proxy troubleshooting note.
- **compat:** Legacy `vmware-vks-mcp` console script kept — existing user configs continue to work.

## v1.5.14 (2026-04-21)

**Bug fixes from code review by @yjs-2026 (follow-up)**

- **fix:** `tkc.py` — all 8 functions using K8s ApiClient now close it via try/finally, preventing urllib3 connection pool leaks in long-lived MCP servers
- **fix:** `storage.py` — same ApiClient leak fix for `list_namespace_storage_usage`
- **fix:** `kubeconfig.py` — same ApiClient leak fix for `get_tkc_kubeconfig_str`

## v1.5.13 (2026-04-21)

- Align with VMware skill family v1.5.13 (code review bug fixes)

## v1.5.12 (2026-04-17)

- Align with VMware skill family v1.5.12 (security & bug fixes from code review by @yjs-2026)

## v1.5.11 (2026-04-17)

- Align with VMware skill family v1.5.11 (AVI 22.x fixes from @timwangbc)

## v1.5.10 (2026-04-16)

- Security: bump python-multipart 0.0.22→0.0.26 (DoS via large multipart preamble/epilogue)
- Align with VMware skill family v1.5.10

## v1.5.9 (2026-04-15)

- Docs: corrected vSphere version requirement in SKILL.md routing table from "vSphere 7.x+" to "vSphere 8.x+" (matches the `_MIN_VERSION = (8, 0, 0)` enforced in `vmware_vks/ops/supervisor.py`). The earlier TKGS / vSphere with Tanzu product worked on 7.x; the "VKS" rebrand applies to the vSphere 8.x+ Workload Management API surface this skill targets.
- Docs: branding cleanup from external contributor — TKGS → VKS, NSX-T → NSX, HAProxy → Avi Networks (#6, credit @ryanconley1).

## v1.5.8 (2026-04-15)

- Align with VMware skill family v1.5.8 (NSX/AVI/Aria/AIops bug fixes)

## v1.5.7 (2026-04-15)

- Fix: VKS REST calls hardcoded `ssl.CERT_NONE` regardless of `target.verify_ssl` config, silently ignoring users who opted in to certificate verification. Added `_build_ssl_context(si)` that honours the trust preference recorded on the ServiceInstance by the connection manager.
- Fix: VKS REST calls had no timeout — default global socket timeout could hang the session on unreachable endpoints. Added `timeout=30` seconds on all REST requests (override via `VMWARE_VKS_REST_TIMEOUT`).
- Refactor: de-duplicated `_rest_post/_rest_patch/_rest_delete` helpers into a single `_rest_request(method, path, body)` in supervisor.py; namespace.py now imports from supervisor.
- Align with VMware skill family v1.5.7

## v1.5.6 (2026-04-15)

- Align with VMware skill family v1.5.6 (AVI bugfixes + packaging hotfix)

## v1.5.5 (2026-04-15)

- Align with VMware skill family v1.5.5

## v1.5.4 (2026-04-14)

- Security: bump pytest 9.0.2→9.0.3 (CVE-2025-71176, insecure tmpdir handling)

## v1.5.0 (2026-04-12)

### Anthropic Best Practices Integration

- **[READ]/[WRITE] tool prefixes**: All MCP tool descriptions now start with [READ] or [WRITE] to clearly indicate operation type
- **Read/write split counts**: SKILL.md MCP Tools section header shows exact read vs write tool counts
- **Negative routing**: Description frontmatter includes "Do NOT use when..." clause to prevent misrouting
- **Broadcom author attestation**: README.md, README-CN.md, and pyproject.toml include VMware by Broadcom author identity (wei-wz.zhou@broadcom.com) to resolve Snyk E005 brand warnings

### VKS-specific

- **Kubeconfig security notes**: get_supervisor_kubeconfig and get_tkc_kubeconfig docstrings include credential handling warnings (Snyk W007)

## v1.4.9 (2026-04-11)

- Fix: require explicit VMware/vSphere context in skill routing triggers (prevent false triggers on generic "clone", "deploy", "alarms" etc.)
- Fix: clarify vmware-policy compatibility field (Python transitive dep, not a required standalone binary)

## v1.4.8 (2026-04-09)

- Security: bump cryptography 46.0.6→46.0.7 (CVE-2026-39892, buffer overflow)
- Security: bump urllib3 2.3.0→2.6.3 (multiple CVEs) [VMware-VKS]
- Security: bump requests 2.32.5→2.33.0 (medium CVE) [VMware-VKS]

## v1.4.7 (2026-04-08)

- Fix: align openclaw metadata with actual runtime requirements
- Fix: standardize audit log path to ~/.vmware/audit.db across all docs
- Fix: update credential env var docs to correct VMWARE_<TARGET>_PASSWORD convention
- Fix: declare .env config and vmware-policy optional dependency in metadata

# Release Notes

## v1.4.5 — 2026-04-03

- **Security**: bump pygments 2.19.2 → 2.20.0 (fix ReDoS CVE in GUID matching regex)
- **Infrastructure**: add uv.lock for reproducible builds and Dependabot security tracking


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.4.0 — 2026-03-29

### Architecture: Unified Audit & Policy

- **vmware-policy integration**: All MCP tools now wrapped with `@vmware_tool` decorator
- **Unified audit logging**: Operations logged to `~/.vmware/audit.db` (SQLite WAL), replacing per-skill JSON Lines logs
- **Policy enforcement**: `check_allowed()` with rules.yaml, maintenance windows, risk-level gating
- **Sanitize consolidation**: Replaced local `_sanitize()` with shared `vmware_policy.sanitize()`
- **Risk classification**: Each tool tagged with risk_level (low/medium/high) for confirmation gating
- **Agent detection**: Audit logs identify calling agent (Claude/Codex/local)
- **New family members**: vmware-policy (audit/policy infrastructure) + vmware-pilot (workflow orchestration)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.1 — 2026-03-27

### Family expansion: NSX, NSX-Security, Aria

- Added vmware-nsx, vmware-nsx-security, vmware-aria to companion skills routing table
- README updated with complete 7-skill family table
- vmware-aiops is now the family entry point (`vmware-aiops hub status`)


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

---

## v1.3.0 — 2026-03-26

### Docs / Skill optimization

- SKILL.md restructured with progressive disclosure (3-level loading)
- Created `references/` directory: cli-reference.md, capabilities.md, setup-guide.md
- Added trigger phrases to YAML description for better skill auto-loading
- Added Common Workflows section (Deploy TKC, Scale workers, Namespace management)
- Added Troubleshooting section (6 common issues)
- README.md and README-CN.md updated with Companion Skills, Workflows, Troubleshooting


## v1.4.6 — 2026-04-06

- fix: remove suspicious content from SKILL.md for ClawHub clean scan

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