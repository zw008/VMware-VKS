"""Kubeconfig retrieval for Supervisor and TKC clusters."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-vks.ops.kubeconfig")


def get_supervisor_kubeconfig_str(si: ServiceInstance, namespace: str) -> str:
    """Get kubeconfig YAML string for Supervisor namespace."""
    from vmware_vks.k8s_connection import get_supervisor_kubeconfig_str as _get
    return _get(si, namespace)


def get_tkc_kubeconfig_str(si: ServiceInstance, cluster_name: str, namespace: str) -> str:
    """Get kubeconfig YAML string for a TKC cluster via Supervisor API."""
    import kubernetes as k8s
    import yaml as _yaml
    from vmware_vks.k8s_connection import get_k8s_client

    api_client = get_k8s_client(si, namespace)
    try:
        custom_api = k8s.client.CustomObjectsApi(api_client)

        cluster = custom_api.get_namespaced_custom_object(
            group="cluster.x-k8s.io", version="v1beta1",
            namespace=namespace, plural="clusters", name=cluster_name,
        )

        control_plane_endpoint = cluster.get("spec", {}).get("controlPlaneEndpoint", {})
        host = control_plane_endpoint.get("host", "")
        port = control_plane_endpoint.get("port", 6443)

        if not host:
            raise RuntimeError(
                f"TKC cluster '{cluster_name}' control plane endpoint not available. "
                "Is the cluster fully provisioned?"
            )

        token = si.content.sessionManager.currentSession.key
        kubeconfig = {
            "apiVersion": "v1",
            "kind": "Config",
            "clusters": [{"name": cluster_name, "cluster": {
                "server": f"https://{host}:{port}",
                "insecure-skip-tls-verify": True,
            }}],
            "users": [{"name": "vsphere-user", "user": {"token": token}}],
            "contexts": [{"name": f"{cluster_name}-context", "context": {
                "cluster": cluster_name, "user": "vsphere-user",
            }}],
            "current-context": f"{cluster_name}-context",
        }
        return _yaml.dump(kubeconfig)
    finally:
        api_client.close()


def write_kubeconfig(
    si: ServiceInstance,
    cluster_name: str,
    namespace: str,
    output_path: Path | None = None,
) -> dict:
    """Write TKC kubeconfig to file or return as string."""
    kubeconfig_str = get_tkc_kubeconfig_str(si, cluster_name, namespace)
    if output_path:
        output_path.write_text(kubeconfig_str)
        output_path.chmod(0o600)
        return {"cluster": cluster_name, "written_to": str(output_path)}
    return {"cluster": cluster_name, "kubeconfig": kubeconfig_str}
