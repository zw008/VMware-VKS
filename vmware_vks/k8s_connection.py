"""Layer 2: kubernetes Python client connection to Supervisor K8s API endpoint.

Kubeconfig is built from the active pyVmomi session and vCenter REST info.
Used for TKC CR lifecycle (create/get/delete/scale/upgrade).
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

_log = logging.getLogger("vmware-vks.k8s_connection")


def _vcenter_host(si: ServiceInstance) -> str:
    return si._stub.host.split(":")[0]


def get_supervisor_kubeconfig_str(si: ServiceInstance, namespace: str) -> str:
    """Build a kubeconfig YAML string for the Supervisor API endpoint.

    Uses the vCenter session token as bearer token and queries the
    namespace-management API for the cluster API endpoint.
    """
    from vmware_vks.ops.supervisor import _rest_get
    import yaml as _yaml

    # Get supervisor clusters to find API endpoint
    try:
        clusters = _rest_get(si, "/vcenter/namespace-management/clusters")
        running = [c for c in clusters if c.get("config_status") == "RUNNING"]
        if not running:
            raise RuntimeError("No running Supervisor clusters found.")
        # Use api_server_cluster_endpoint from the first running cluster
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

    kubeconfig = {
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
    return _yaml.dump(kubeconfig)


def get_k8s_client(si: ServiceInstance, namespace: str):
    """Get a kubernetes ApiClient connected to the Supervisor namespace.

    Returns a kubernetes.client.ApiClient instance.
    Caller MUST close the client when done (use as context manager or call .close()).
    """
    import kubernetes as k8s

    kubeconfig_str = get_supervisor_kubeconfig_str(si, namespace)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(kubeconfig_str)
        tmpfile = f.name

    try:
        cfg = k8s.config.load_kube_config(config_file=tmpfile)
        return k8s.client.ApiClient(configuration=cfg)
    finally:
        Path(tmpfile).unlink(missing_ok=True)
