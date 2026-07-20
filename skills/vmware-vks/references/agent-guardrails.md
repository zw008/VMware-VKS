# Operating vmware-vks with a local / small model

Claude-class models drive this skill without special instruction. Smaller and
locally-hosted models — Llama 3.3 70B, Qwen, Mistral, and similar, served
through Goose, Ollama, or OpenShift AI — need explicit operating rules to call
tools reliably.

This page exists because an operator wrote those rules by hand first. The
guardrails below are adapted, with thanks, from the working configuration
[@juanpf-ha](https://github.com/juanpf-ha) developed while running
vmware-monitor and vmware-aria against a production vSphere estate with Llama
3.3 70B FP8 on an on-prem H100
([VMware-AIops#31](https://github.com/zw008/VMware-AIops/issues/31)). The
cross-skill rules are identical across this family; the parts below marked
vmware-vks are specific to this skill.

vmware-vks exposes 20 MCP tools. Two things make it distinctive for a small
model: deleting a namespace or a Tanzu Kubernetes cluster destroys running
workloads, and two of its tools hand back live credentials.

> **Disclaimer**: This is a community-maintained open-source project and is
> **not affiliated with, endorsed by, or sponsored by VMware, Inc. or Broadcom
> Inc.** "VMware" and "vSphere" are trademarks of Broadcom.

---

## First: the rules you no longer need to write

Several guardrails from the original configuration are now enforced by the
skill itself. Prompt instructions are advisory — a model can ignore them.
These are structural, so it cannot.

| Guardrail you would otherwise prompt for | Now enforced by |
|---|---|
| "Work exclusively in read-only mode and never modify anything" | **Read-only mode.** Set `VMWARE_READ_ONLY=true` and 9 tools are removed from the registry at startup, leaving 11. `list_tools()` never offers them, so the model cannot call what it cannot see. |
| "Never hand a kubeconfig or session token back in conversation" | **The same gate, and it goes further than the markers.** `get_supervisor_kubeconfig` and `get_tkc_kubeconfig` carry a `[READ]` marker but are withheld anyway — they materialise a session-token credential file at a model-supplied local path. That is why 9 tools go where only 7 are marked Write. |
| "Preview a namespace or cluster creation before applying it" | **`dry_run` defaults to true.** `create_namespace` and `create_tkc_cluster` return a YAML plan for review unless you explicitly pass `dry_run=False`. Preview is the default path, not a habit the model must maintain. |
| "Confirm before deleting anything" | **`confirmed=True` is required.** `delete_namespace` additionally refuses while TKC clusters still exist inside it, and `delete_tkc_cluster` refuses while workloads are running unless `force=True`. |
| "Use explicit limits for queries that may return large amounts of data" | **The list envelope.** `list_namespaces`, `list_supervisor_storage_policies` and `list_vm_classes` return `{items, returned, limit, total, truncated, hint}`, so the model reads truncation instead of guessing at it. These three read their collection in one un-paged call, so `total` is the real count and `truncated` is always `false`. |
| "If a listing came back empty, say so rather than claiming the call failed" | Same envelope. Empty `items` with `truncated: false` means checked-and-none — a stated result, not a silence the model has to interpret. |
| "Log every state change you make" | **The `@vmware_tool` decorator.** Every write is recorded to `~/.vmware/audit.db` before the model sees the result, and policy rules are evaluated ahead of execution. |

### Turning read-only mode on

One variable covers every skill in the family:

```json
{
  "mcpServers": {
    "vmware-vks": {
      "command": "vmware-vks",
      "args": ["mcp"],
      "env": { "VMWARE_READ_ONLY": "true" }
    }
  }
}
```

Per-skill override — useful when this skill alone should stay writable:

```bash
VMWARE_READ_ONLY=true        # whole family read-only
VMWARE_VKS_READ_ONLY=false   # …except Kubernetes
```

Or permanently, in `~/.vmware-vks/config.yaml`:

```yaml
read_only: true
```

Precedence is per-skill env → family env → config file → off. The startup log
lists exactly which tools were withheld, and `vmware-vks check` reports the
resolved state and its source. An unparseable value (`VMWARE_READ_ONLY=ture`)
enables read-only mode rather than silently ignoring the typo.

A blocked tool is a lockdown, not a fault. When a tool is missing from
`list_tools()`, the model should name the operation it cannot perform and say
an operator must clear the switch — not retry, and not go looking for a
different tool that achieves the same change. This matters more here than
elsewhere: a model denied `get_tkc_kubeconfig` will sometimes try to reach the
cluster another way.

---

## The system prompt

Everything below still benefits from being stated explicitly. Copy this into
your agent's instruction block.

```text
## Tool use

- Always call an MCP tool before answering any question about the current
  VMware environment. Never answer from memory or assumption.
- Never describe a tool call, and never output a JSON example, instead of
  executing the tool. If you intend to call a tool, call it.
- If a tool fails, report the actual error text. Do not complete the answer
  with assumptions about what the result would have been.
- Use explicit limits on queries that may return large amounts of data. Do not
  request unlimited results unless the user asks for them.
- Namespace, cluster and storage-policy names are exact strings. Resolve them
  with a list tool before use; do not correct or reformat what the user typed.

## Skill routing

- vmware-vks: Supervisor status and compatibility, vSphere namespaces, VM
  classes, Tanzu Kubernetes clusters, kubeconfig retrieval, Harbor registry.
- vmware-monitor: read-only vCenter inventory, hosts, alarms, events. Prefer it
  for any question that only reads about the underlying vSphere estate.
- vmware-aiops: VM lifecycle for ordinary VMs, not Supervisor-managed ones.
- vmware-storage: datastores, iSCSI, vSAN backing the Supervisor.
- vmware-nsx / vmware-nsx-security: the networking and firewall a TKC sits on.
- vmware-pilot: multi-step workflows that need approval gates.

## Data fidelity

- Never invent namespaces, clusters, VM classes, storage policies, or node
  counts. If a tool did not return it, it does not exist for this answer.
- Preserve the exact phase and condition values the tools return (Creating,
  Running, Updating, and so on). Do not translate, normalise, or prettify them.
- A cluster's phase is not its health. Report the phase the tool gave you.
- If a requested field was not returned, show it as "not available". Do not
  infer it from other fields.
- Preserve the original order and the full set of fields when the user asks
  for specific ones.
- When a response is long, report every item it contains. If a result is
  truncated, the tool says so explicitly — report the truncation rather than
  describing the visible subset as the whole.

## Analysis discipline

- Separate observed data from interpretation. State which is which.
- Do not claim a capacity, scheduling, or networking problem unless the tool
  output contains explicit supporting evidence.
- Avoid generic recommendations that are not directly supported by the results.

## Credentials and writes in vmware-vks

- Never print a kubeconfig, session token or bearer token into the conversation.
  Write it to a file with the -o path argument and report the path only.
- A tool missing from the tool list means read-only mode is on. Name the blocked
  operation and stop. Do not retry, do not substitute another tool, and do not
  attempt to reach the cluster by another route.
- Storage policies are selected by Policy ID, not display name. Call
  list_supervisor_storage_policies and use the ID column.
- Leave dry_run at its default for create_namespace and create_tkc_cluster, show
  the returned YAML plan to the user, and only then pass dry_run=False.
- Scale and upgrade operations are rejected unless the cluster is in Running
  phase. Check the phase before proposing one.
```

---

## Known failure modes on small models

Observed with Llama 3.3 70B FP8 (Goose, on-prem H100), and useful as a
checklist when evaluating any local model against these skills:

| Symptom | Mitigation |
|---|---|
| Describes a tool call, or emits a JSON example, instead of executing it | The "never describe a tool call" rule above. Also check your harness is not echoing tool schemas into context — models imitate the nearest format they see. |
| Long tool responses: omits items, or reports "no data returned" when data was present | Ask for explicit limits so responses stay small. Check the envelope's `truncated` / `returned` / `total` fields rather than trusting the model's summary — a "no data" claim is checkable against `returned`. |
| Adds generic recommendations unsupported by results | The "analysis discipline" rules. |
| Drops requested fields or reorders results | State the required fields and ordering in the request itself, not only in the system prompt. |
| Multi-tool workflows take 30–50s end to end | `get_supervisor_status` and `get_tkc_cluster` each answer a whole question in one call — prefer them over rebuilding the same picture from several list tools. |
| Echoes a kubeconfig into the conversation, leaking a live token into context and logs | The credential rule above, and read-only mode, which withholds both kubeconfig tools outright. |
| Passes a storage policy's display name where the Policy ID is required | The `list_supervisor_storage_policies` rule above. The failure text is "storage policy not found", which reads like a missing object rather than a wrong identifier. |
| Reads "Creating" as "created" and reports success | The "a cluster's phase is not its health" rule. Have the model quote the phase verbatim. |
| Retries a delete that was refused for a stated reason | The refusals are guards: a namespace with clusters in it, a cluster with running workloads. Report the reason instead of retrying with `force`. |

## Reporting results

Local-model compatibility is an explicit design constraint for this family, and
the evidence base is small. If you evaluate a model against this skill —
Qwen, Mistral, Granite, or anything else — a report of what worked and what did
not is genuinely useful:
[github.com/zw008/VMware-VKS/issues](https://github.com/zw008/VMware-VKS/issues).
