<!-- mcp-name: io.github.zw008/vmware-vks -->
# VMware VKS

[English](README.md) | [中文](README-CN.md)

MCP Skill + CLI，用于管理 vSphere with Tanzu (VKS) — Supervisor 集群、vSphere 命名空间和 TanzuKubernetesCluster 生命周期。

> **VMware MCP Skills 系列：**
>
> | Skill | 功能范围 | 工具数 |
> |-------|---------|:-----:|
> | **vmware-monitor**（只读） | 清单、健康、告警、事件 | 8 |
> | **vmware-aiops**（完整运维） | 虚拟机生命周期、部署、Guest 操作 | 33 |
> | **vmware-storage** | 数据存储、iSCSI、vSAN | 11 |
> | **vmware-vks**（本 Skill） | Supervisor、命名空间、TKC 生命周期 | 20 |

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 前置要求

- **vSphere 8.0+** — Workload Management（Supervisor）API 要求 vSphere 8.x
- **Workload Management 已启用** — 至少一个计算集群已开启 WCP
- **许可证** — vSphere with Tanzu（Enterprise Plus 或 VMware Cloud Foundation）

配置完成后运行 `vmware-vks check` 验证所有要求是否满足。

## 快速开始

```bash
# 安装
uv tool install vmware-vks

# 配置
mkdir -p ~/.vmware-vks
cp config.example.yaml ~/.vmware-vks/config.yaml
# 编辑 config.yaml，填入 vCenter 主机和用户名

echo "VMWARE_MY_VCENTER_PASSWORD=your_password" > ~/.vmware-vks/.env
chmod 600 ~/.vmware-vks/.env

# 验证
vmware-vks check

# 常用操作
vmware-vks supervisor status domain-c1
vmware-vks namespace list
vmware-vks tkc list
vmware-vks tkc create my-cluster -n dev --version v1.28.4+vmware.1 --vm-class best-effort-large
vmware-vks tkc create my-cluster -n dev --apply
```

## 工具参考（20 个工具）

### Supervisor

| 工具 | 描述 | 类型 |
|------|------|------|
| `check_vks_compatibility` | vCenter 版本检查 + WCP 状态 | 只读 |
| `get_supervisor_status` | Supervisor 集群状态和 K8s API 端点 | 只读 |
| `list_supervisor_storage_policies` | 命名空间可用存储策略列表 | 只读 |

### 命名空间

| 工具 | 描述 | 类型 |
|------|------|------|
| `list_namespaces` | 所有 vSphere 命名空间及状态 | 只读 |
| `get_namespace` | 命名空间详情（配额、存储、角色） | 只读 |
| `create_namespace` | 创建命名空间（默认 dry-run 预览） | 写操作 |
| `update_namespace` | 修改配额和存储策略 | 写操作 |
| `delete_namespace` | 删除（含 TKC 保护，存在集群时拒绝） | 写操作 |
| `list_vm_classes` | TKC 节点规格可用的 VM 类 | 只读 |

### TKC

| 工具 | 描述 | 类型 |
|------|------|------|
| `list_tkc_clusters` | TanzuKubernetesCluster 列表及状态 | 只读 |
| `get_tkc_cluster` | 集群详情（节点、健康、条件） | 只读 |
| `get_tkc_available_versions` | Supervisor 上支持的 K8s 版本 | 只读 |
| `create_tkc_cluster` | 创建 TKC（YAML 计划 + 默认 dry-run） | 写操作 |
| `scale_tkc_cluster` | 调整工作节点数量 | 写操作 |
| `upgrade_tkc_cluster` | 升级 K8s 版本 | 写操作 |
| `delete_tkc_cluster` | 删除（含工作负载保护） | 写操作 |

### 访问

| 工具 | 描述 | 类型 |
|------|------|------|
| `get_supervisor_kubeconfig` | Supervisor kubeconfig YAML | 只读 |
| `get_tkc_kubeconfig` | TKC kubeconfig（标准输出或文件） | 只读 |
| `get_harbor_info` | 内置 Harbor 仓库信息 | 只读 |
| `list_namespace_storage_usage` | PVC 列表和容量统计 | 只读 |

## CLI 参考

```bash
# 环境检查
vmware-vks check

# Supervisor
vmware-vks supervisor status <集群ID>
vmware-vks supervisor storage-policies

# 命名空间
vmware-vks namespace list
vmware-vks namespace get <名称>
vmware-vks namespace create <名称> --cluster <ID> --storage-policy <策略>
vmware-vks namespace create <名称> --cluster <ID> --storage-policy <策略> --apply
vmware-vks namespace update <名称> [--cpu <MHz>] [--memory <MiB>]
vmware-vks namespace delete <名称>
vmware-vks namespace vm-classes

# TKC
vmware-vks tkc list [-n <命名空间>]
vmware-vks tkc get <名称> -n <命名空间>
vmware-vks tkc versions -n <命名空间>
vmware-vks tkc create <名称> -n <命名空间> [--version <版本>] [--vm-class <类型>]
vmware-vks tkc create <名称> -n <命名空间> --apply
vmware-vks tkc scale <名称> -n <命名空间> --workers <数量>
vmware-vks tkc upgrade <名称> -n <命名空间> --version <版本>
vmware-vks tkc delete <名称> -n <命名空间>

# Kubeconfig
vmware-vks kubeconfig supervisor -n <命名空间>
vmware-vks kubeconfig get <集群名称> -n <命名空间> [-o <文件路径>]

# Harbor 和存储
vmware-vks harbor
vmware-vks storage -n <命名空间>
```

## MCP Server 配置

```json
{
  "mcpServers": {
    "vmware-vks": {
      "command": "vmware-vks-mcp",
      "env": {
        "VMWARE_VKS_CONFIG": "~/.vmware-vks/config.yaml"
      }
    }
  }
}
```

## 安全性

| 特性 | 说明 |
|------|------|
| 以只读为主 | 20 个工具中 12 个为只读 |
| 默认 dry-run | `create_namespace`、`create_tkc_cluster`、`delete_namespace`、`delete_tkc_cluster` 均默认 `dry_run=True` |
| TKC 保护 | `delete_namespace` 在命名空间内存在 TKC 集群时拒绝执行 |
| 工作负载保护 | `delete_tkc_cluster` 在 Deployment/StatefulSet 运行时拒绝执行 |
| 凭据安全 | 密码仅从环境变量（`.env` 文件）加载，不写入 `config.yaml` |
| 审计日志 | 所有写操作记录到 `~/.vmware-vks/audit.log` |
| stdio 传输 | 无网络监听端口；MCP 通过 stdio 运行 |

## 版本兼容性

| vSphere | 支持状态 | 说明 |
|---------|---------|------|
| 8.0+ | 完整支持 | Workload Management API 可用 |
| 7.x | 不支持 | WCP API 接口不同，请使用 vSphere 8.x |

## 许可证

[MIT](LICENSE)
