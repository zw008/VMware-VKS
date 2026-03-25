# MCP Configuration Templates

Copy the relevant config snippet into your AI agent's MCP configuration file.

## Prerequisites

```bash
# Install vmware-vks
uv tool install vmware-vks
# or: pip install vmware-vks

# Configure credentials
mkdir -p ~/.vmware-vks
cp config.example.yaml ~/.vmware-vks/config.yaml
# Edit config.yaml with your vCenter/ESXi host and username

echo "VMWARE_VKS_MY_VCENTER_PASSWORD=your_password" > ~/.vmware-vks/.env
chmod 600 ~/.vmware-vks/.env

# Verify setup
vmware-vks doctor
```

## Agent Configuration Files

| Agent | Config File | Template |
|-------|------------|----------|
| Claude Code | `~/.claude/settings.json` | [claude-code.json](claude-code.json) |
| Cursor | Cursor MCP settings | [cursor.json](cursor.json) |
| Goose | `goose configure` or UI | [goose.json](goose.json) |
| Continue | `~/.continue/config.yaml` | [continue.yaml](continue.yaml) |
| LocalCowork | MCP config panel | [localcowork.json](localcowork.json) |
| mcp-agent | `mcp_agent.config.yaml` | [mcp-agent.yaml](mcp-agent.yaml) |
| VS Code Copilot | `.vscode/mcp.json` | [vscode-copilot.json](vscode-copilot.json) |

## Using with Local Models (Ollama / LM Studio)

```bash
# Example: Continue + Ollama + vmware-vks MCP server
# 1. Configure Continue with your Ollama model
# 2. Add vmware-vks MCP config from continue.yaml
# 3. Ask naturally: "list all TKC clusters" or "show supervisor namespace status"
```

## Combining with Other VMware Skills

vmware-vks can run alongside other VMware MCP skills simultaneously:

```json
{
  "mcpServers": {
    "vmware-monitor": {
      "command": "vmware-monitor-mcp",
      "env": { "VMWARE_MONITOR_CONFIG": "~/.vmware-monitor/config.yaml" }
    },
    "vmware-vks": {
      "command": "vmware-vks-mcp",
      "env": { "VMWARE_VKS_CONFIG": "~/.vmware-vks/config.yaml" }
    }
  }
}
```
