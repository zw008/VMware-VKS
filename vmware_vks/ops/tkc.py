"""TanzuKubernetesCluster (TKC) lifecycle operations.

Uses cluster.x-k8s.io/v1beta1 API (vSphere 8.x).
All cluster operations go through the Supervisor K8s API endpoint (Layer 2).

Safety:
- delete_tkc_cluster rejects if Deployments/StatefulSets/DaemonSets are running
- create_tkc_cluster defaults to dry_run=True (returns YAML plan)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance

from vmware_policy import sanitize

_log = logging.getLogger("vmware-vks.ops.tkc")

_TKC_GROUP = "cluster.x-k8s.io"
_TKC_VERSION = "v1beta1"
_TKC_PLURAL = "clusters"


def _get_custom_objects_api(si: ServiceInstance, namespace: str):
    """Get kubernetes CustomObjectsApi connected to Supervisor namespace."""
    import kubernetes as k8s
    from vmware_vks.k8s_connection import get_k8s_client
    api_client = get_k8s_client(si, namespace)
    return k8s.client.CustomObjectsApi(api_client)


def generate_tkc_yaml(
    name: str,
    namespace: str,
    k8s_version: str,
    vm_class: str,
    control_plane_count: int,
    worker_count: int,
    storage_class: str,
) -> str:
    """Generate TKC cluster YAML (cluster.x-k8s.io/v1beta1 for vSphere 8.x)."""
    if worker_count < 1:
        raise ValueError(f"worker_count must be >= 1, got {worker_count}")
    if control_plane_count not in (1, 3):
        raise ValueError(f"control_plane_count must be 1 or 3, got {control_plane_count}")

    manifest = {
        "apiVersion": f"{_TKC_GROUP}/{_TKC_VERSION}",
        "kind": "Cluster",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "clusterNetwork": {
                "pods": {"cidrBlocks": ["192.168.0.0/16"]},
                "services": {"cidrBlocks": ["10.96.0.0/12"]},
            },
            "topology": {
                "class": "tanzukubernetescluster",
                "version": k8s_version,
                "controlPlane": {
                    "replicas": control_plane_count,
                    "metadata": {},
                    "nodeDrainTimeout": "60s",
                },
                "workers": {
                    "machineDeployments": [{
                        "class": "node-pool",
                        "name": "worker-pool",
                        "replicas": worker_count,
                        "metadata": {},
                        "nodeDrainTimeout": "60s",
                    }]
                },
                "variables": [
                    {"name": "vmClass", "value": vm_class},
                    {"name": "storageClass", "value": storage_class},
                ],
            },
        },
    }
    return yaml.dump(manifest, default_flow_style=False)


def list_tkc_clusters(si: ServiceInstance, namespace: str | None = None) -> dict:
    """List TKC clusters in a namespace (or all namespaces)."""
    ns = namespace or "default"
    api = _get_custom_objects_api(si, ns)
    try:
        if namespace:
            raw = api.list_namespaced_custom_object(
                group=_TKC_GROUP, version=_TKC_VERSION,
                namespace=namespace, plural=_TKC_PLURAL,
            )
        else:
            raw = api.list_cluster_custom_object(
                group=_TKC_GROUP, version=_TKC_VERSION, plural=_TKC_PLURAL,
            )
        items = raw.get("items", [])
        clusters = [
            {
                "name": sanitize(item["metadata"]["name"]),
                "namespace": sanitize(item["metadata"]["namespace"]),
                "phase": item.get("status", {}).get("phase", "Unknown"),
                "k8s_version": item["spec"]["topology"].get("version", ""),
            }
            for item in items
        ]
        return {"total": len(clusters), "clusters": clusters}
    finally:
        api.api_client.close()


def get_tkc_cluster(si: ServiceInstance, name: str, namespace: str) -> dict:
    """Get detailed TKC cluster info."""
    api = _get_custom_objects_api(si, namespace)
    try:
        raw = api.get_namespaced_custom_object(
            group=_TKC_GROUP, version=_TKC_VERSION,
            namespace=namespace, plural=_TKC_PLURAL, name=name,
        )
        status = raw.get("status", {})
        conditions = [
            {
                "type": sanitize(c.get("type", "")),
                "status": c.get("status", ""),
                "message": sanitize(c.get("message", ""), max_len=500),
            }
            for c in status.get("conditions", [])
        ]
        return {
            "name": name,
            "namespace": namespace,
            "phase": status.get("phase"),
            "k8s_version": raw["spec"]["topology"].get("version"),
            "control_plane_replicas": raw["spec"]["topology"]["controlPlane"].get("replicas"),
            "worker_replicas": raw["spec"]["topology"]["workers"]["machineDeployments"][0].get("replicas"),
            "conditions": conditions,
            "infrastructure_ready": status.get("infrastructureReady", False),
            "control_plane_ready": status.get("controlPlaneReady", False),
        }
    finally:
        api.api_client.close()


def get_tkc_available_versions(si: ServiceInstance, namespace: str) -> dict:
    """List K8s versions available for TKC clusters on this Supervisor."""
    import kubernetes as k8s
    from vmware_vks.k8s_connection import get_k8s_client

    api_client = get_k8s_client(si, namespace)
    try:
        custom_api = k8s.client.CustomObjectsApi(api_client)
        raw = custom_api.list_cluster_custom_object(
            group="run.tanzu.vmware.com",
            version="v1alpha3",
            plural="tanzukubernetesreleases",
        )
        versions = [
            {
                "name": item["metadata"]["name"],
                "version": item["spec"].get("version", item["metadata"]["name"]),
            }
            for item in raw.get("items", [])
        ]
        return {"versions": sorted(versions, key=lambda x: x["version"], reverse=True)}
    except Exception as e:
        return {"versions": [], "error": str(e),
                "hint": "TanzuKubernetesRelease API may not be available on this Supervisor"}
    finally:
        api_client.close()


def create_tkc_cluster(
    si: ServiceInstance,
    name: str,
    namespace: str,
    k8s_version: str,
    vm_class: str,
    control_plane_count: int = 1,
    worker_count: int = 3,
    storage_class: str = "vsphere-storage",
    dry_run: bool = True,
) -> dict:
    """Create a TKC cluster. dry_run=True returns YAML plan without applying."""
    yaml_str = generate_tkc_yaml(
        name=name, namespace=namespace, k8s_version=k8s_version,
        vm_class=vm_class, control_plane_count=control_plane_count,
        worker_count=worker_count, storage_class=storage_class,
    )

    if dry_run:
        return {
            "dry_run": True,
            "action": "create_tkc_cluster",
            "name": name,
            "namespace": namespace,
            "yaml": yaml_str,
            "hint": "Set dry_run=False to apply this manifest.",
        }

    manifest = yaml.safe_load(yaml_str)
    api = _get_custom_objects_api(si, namespace)
    try:
        api.create_namespaced_custom_object(
            group=_TKC_GROUP, version=_TKC_VERSION,
            namespace=namespace, plural=_TKC_PLURAL, body=manifest,
        )
        return {"name": name, "namespace": namespace, "status": "creating", "yaml": yaml_str}
    finally:
        api.api_client.close()


def scale_tkc_cluster(
    si: ServiceInstance, name: str, namespace: str, worker_count: int
) -> dict:
    """Scale TKC worker node count."""
    if worker_count < 1:
        raise ValueError(f"worker_count must be >= 1, got {worker_count}")
    api = _get_custom_objects_api(si, namespace)
    try:
        patch = {
            "spec": {
                "topology": {
                    "workers": {
                        "machineDeployments": [{"name": "worker-pool", "replicas": worker_count}]
                    }
                }
            }
        }
        api.patch_namespaced_custom_object(
            group=_TKC_GROUP, version=_TKC_VERSION,
            namespace=namespace, plural=_TKC_PLURAL, name=name, body=patch,
        )
        return {"name": name, "namespace": namespace, "worker_count": worker_count, "status": "scaling"}
    finally:
        api.api_client.close()


def upgrade_tkc_cluster(
    si: ServiceInstance, name: str, namespace: str, k8s_version: str
) -> dict:
    """Upgrade TKC cluster K8s version."""
    api = _get_custom_objects_api(si, namespace)
    try:
        patch = {"spec": {"topology": {"version": k8s_version}}}
        api.patch_namespaced_custom_object(
            group=_TKC_GROUP, version=_TKC_VERSION,
            namespace=namespace, plural=_TKC_PLURAL, name=name, body=patch,
        )
        return {"name": name, "namespace": namespace, "new_version": k8s_version, "status": "upgrading"}
    finally:
        api.api_client.close()


def _check_running_workloads(si: ServiceInstance, name: str, namespace: str) -> list[dict]:
    """Check for running Deployments/StatefulSets in the TKC cluster."""
    from vmware_vks.ops.kubeconfig import get_tkc_kubeconfig_str
    import kubernetes as k8s
    import tempfile

    try:
        kubeconfig_str = get_tkc_kubeconfig_str(si, name, namespace)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(kubeconfig_str)
            tmpfile = f.name
        try:
            cfg = k8s.config.load_kube_config(config_file=tmpfile)
            api_client = k8s.client.ApiClient(configuration=cfg)
            try:
                apps_api = k8s.client.AppsV1Api(api_client)
                workloads = []
                for deploy in apps_api.list_deployment_for_all_namespaces().items:
                    if deploy.status.ready_replicas and deploy.status.ready_replicas > 0:
                        workloads.append({
                            "kind": "Deployment",
                            "name": deploy.metadata.name,
                            "namespace": deploy.metadata.namespace,
                        })
                for ss in apps_api.list_stateful_set_for_all_namespaces().items:
                    if ss.status.ready_replicas and ss.status.ready_replicas > 0:
                        workloads.append({
                            "kind": "StatefulSet",
                            "name": ss.metadata.name,
                            "namespace": ss.metadata.namespace,
                        })
                for ds in apps_api.list_daemon_set_for_all_namespaces().items:
                    if ds.status and ds.status.number_ready and ds.status.number_ready > 0:
                        workloads.append({
                            "kind": "DaemonSet",
                            "name": ds.metadata.name,
                            "namespace": ds.metadata.namespace,
                            "ready": ds.status.number_ready,
                        })
                return workloads
            finally:
                api_client.close()
        finally:
            Path(tmpfile).unlink(missing_ok=True)
    except Exception as e:
        _log.warning("Could not verify workloads in cluster '%s': %s", name, e)
        raise RuntimeError(
            f"Cannot verify workloads in TKC cluster '{name}': {e}. "
            "Use force=True to skip workload check."
        ) from e


def delete_tkc_cluster(
    si: ServiceInstance,
    name: str,
    namespace: str,
    confirmed: bool = False,
    dry_run: bool = True,
    force: bool = False,
) -> dict:
    """Delete a TKC cluster with workload guard.

    Guards: confirmed=True required; rejects if workloads running (unless force=True).
    """
    if not confirmed:
        raise ValueError(
            f"confirmed=True required to delete TKC cluster '{name}'."
        )

    if not force:
        workloads = _check_running_workloads(si, name, namespace)
        if workloads:
            raise RuntimeError(
                f"Cannot delete TKC cluster '{name}': "
                f"{len(workloads)} running workload(s) detected: "
                f"{[w['kind'] + '/' + w['name'] for w in workloads[:5]]}. "
                "Delete workloads first or use force=True."
            )

    if dry_run:
        return {
            "dry_run": True,
            "action": "delete_tkc_cluster",
            "name": name,
            "namespace": namespace,
            "warning": "This will permanently delete the TKC cluster.",
        }

    api = _get_custom_objects_api(si, namespace)
    api.delete_namespaced_custom_object(
        group=_TKC_GROUP, version=_TKC_VERSION,
        namespace=namespace, plural=_TKC_PLURAL, name=name,
    )
    return {"name": name, "namespace": namespace, "status": "deleting"}
