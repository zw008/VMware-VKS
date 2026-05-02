"""Layer 2: kubernetes Python client connection to Supervisor K8s API endpoint.

Kubeconfig is built from the active pyVmomi session and vCenter REST info.
Used for TKC CR lifecycle (create/get/delete/scale/upgrade).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-vks.k8s_connection")


def _vcenter_host(si: ServiceInstance) -> str:
    return si._stub.host.split(":")[0]


def _build_supervisor_kubeconfig(si: ServiceInstance, namespace: str) -> dict[str, Any]:
    """Build kubeconfig as a dict for the Supervisor API endpoint.

    Uses the vCenter session token as bearer token and queries the
    namespace-management API for the cluster API endpoint.
    """
    from vmware_vks.ops.supervisor import _rest_get

    try:
        clusters = _rest_get(si, "/vcenter/namespace-management/clusters")
        running = [c for c in clusters if c.get("config_status") == "RUNNING"]
        if not running:
            raise RuntimeError("No running Supervisor clusters found.")
        cluster_data = _rest_get(
            si,
            f"/vcenter/namespace-management/clusters/{running[0]['cluster']}"
        )
        api_endpoint = cluster_data.get("api_server_cluster_endpoint", "")
        if not api_endpoint:
            raise RuntimeError("Could not determine Supervisor API endpoint.")
    except Exception as e:
        raise RuntimeError(
            f"Could not retrieve Supervisor API endpoint: {e}. "
            "Ensure Workload Management is enabled."
        ) from e

    token = si.content.sessionManager.currentSession.key

    return {
        "apiVersion": "v1",
        "kind": "Config",
        "clusters": [{
            "name": "supervisor",
            "cluster": {
                "server": f"https://{api_endpoint}",
                "insecure-skip-tls-verify": True,
            }
        }],
        "users": [{"name": "vsphere-user", "user": {"token": token}}],
        "contexts": [{
            "name": "supervisor-context",
            "context": {
                "cluster": "supervisor",
                "user": "vsphere-user",
                "namespace": namespace,
            }
        }],
        "current-context": "supervisor-context",
    }


def get_supervisor_kubeconfig_str(si: ServiceInstance, namespace: str) -> str:
    """Build a kubeconfig YAML string for the Supervisor API endpoint.

    Used by CLI/MCP `kubeconfig get` to export to a user-chosen path.
    For in-process kubernetes client use, prefer get_k8s_client which
    keeps the bearer token in memory only.
    """
    import yaml as _yaml
    return _yaml.dump(_build_supervisor_kubeconfig(si, namespace))


def get_k8s_client(si: ServiceInstance, namespace: str):
    """Get a kubernetes ApiClient connected to the Supervisor namespace.

    Loads kubeconfig from an in-memory dict via load_kube_config_from_dict —
    the bearer token never touches disk, eliminating the temp-file TOCTOU
    window of the previous implementation.

    Caller MUST close the client when done (use as context manager or call .close()).
    """
    import kubernetes as k8s

    cfg_dict = _build_supervisor_kubeconfig(si, namespace)
    client_cfg = k8s.client.Configuration()
    k8s.config.load_kube_config_from_dict(
        config_dict=cfg_dict, client_configuration=client_cfg
    )
    return k8s.client.ApiClient(configuration=client_cfg)
