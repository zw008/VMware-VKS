# Setup Guide

Full setup, security details, and AI platform compatibility for `vmware-vks`.

## Installation

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

### What Gets Installed

The `vmware-vks` package installs a Python CLI binary and its dependencies (pyVmomi, kubernetes Python client, Typer, Rich, python-dotenv, mcp). No background services or daemons are started during installation.

### Development Install

```bash
git clone https://github.com/zw008/VMware-VKS.git
cd VMware-VKS
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Configuration

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

## MCP Mode (Optional)

For Claude Code / Cursor users who prefer structured tool calls, add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "vmware-vks": {
      "command": "uvx",
      "args": ["--from", "vmware-vks", "vmware-vks-mcp"],
      "env": {
        "VMWARE_VKS_CONFIG": "/Users/you/.vmware-vks/config.yaml",
        "VMWARE_MYVENTER_PASSWORD": "your-password"
      }
    }
  }
}
```

## Usage Mode

Choose the best mode based on your environment:

| Scenario | Recommended Mode | Why |
|----------|-----------------|-----|
| **Cloud models** (Claude, GPT-4o, Gemini) | MCP or CLI | Both work well; MCP gives structured JSON I/O |
| **Local/small models** (Ollama, Llama, Qwen <32B) | **CLI** | Lower token cost (~2K vs ~8K), higher accuracy -- small models struggle with 20 MCP tool schemas |
| **Token-sensitive workflows** | **CLI** | CLI via SKILL.md uses ~2K tokens; MCP loads ~8K tokens of tool definitions into every conversation |
| **Automated pipelines / Agent chaining** | **MCP** | Structured JSON input/output, type-safe parameters, no shell parsing |

### Calling Priority

- **MCP-native tools** (Claude Code, Cursor): MCP first, CLI fallback
- **Local models / Token-sensitive**: CLI first (MCP not needed)

## Security

This skill follows a defense-in-depth approach with six security properties:

1. **Source Code** -- MIT-licensed, fully auditable. No obfuscated logic. Source at [github.com/zw008/VMware-VKS](https://github.com/zw008/VMware-VKS). The `uv` installer fetches the `vmware-vks` package from PyPI, which is built from this GitHub repository.

2. **Credentials** -- `config.yaml` contains vCenter hostnames and usernames only. Passwords are loaded exclusively from `~/.vmware-vks/.env` (read via `python-dotenv`). Passwords are never logged, never echoed to CLI output, and never included in audit log entries.

3. **Network Scope** -- No webhook, HTTP listener, or inbound network connection is ever started. MCP transport is stdio only. All outbound connections go to the user-configured vCenter host only.

4. **TLS Verification** -- `verify_ssl: false` is supported for self-signed vCenter certificates (standard in enterprise environments). Set `verify_ssl: true` in config for CA-signed certificates. Applies to both the SOAP API and REST API connections.

5. **Prompt Injection Protection** -- All tool inputs are passed as typed Python parameters (`str`, `int`, `bool`), never interpolated into shell commands. No `eval`, `exec`, or subprocess calls with user-controlled data.

6. **Least Privilege** -- 12/20 tools are read-only. All write operations default to `dry_run=True` where applicable. Destructive operations (`delete_namespace`, `delete_tkc_cluster`) require explicit `confirmed=True` and pass through safety guards that cannot be bypassed without `force=True`. All write operations are audit-logged to `~/.vmware/audit.db` (SQLite WAL, via vmware-policy).

## Supported AI Platforms

| Platform | Status |
|----------|--------|
| Claude Code | Native Skill |
| Goose (Block) | MCP via stdio |
| Cursor | MCP mode |
| Continue | MCP mode |
| VS Code Copilot | MCP mode |
| Python CLI | Standalone |
