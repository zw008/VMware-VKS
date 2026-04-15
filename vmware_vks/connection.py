"""Connection management for vCenter (Layer 1: pyVmomi).

Layer 2 (kubernetes client) is handled separately in vmware_vks.k8s_connection.
"""
from __future__ import annotations

import atexit
import ssl
from typing import TYPE_CHECKING

from pyVmomi import vmodl
from vmware_vks.config import AppConfig, TargetConfig, load_config

if TYPE_CHECKING:
    from pyVmomi.vim import ServiceInstance


class ConnectionManager:
    """Manages pyVmomi connections to multiple vCenter targets."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._connections: dict[str, ServiceInstance] = {}

    @classmethod
    def from_config(cls, config: AppConfig | None = None) -> ConnectionManager:
        cfg = config or load_config()
        return cls(cfg)

    def connect(self, target_name: str | None = None) -> ServiceInstance:
        target = (
            self._config.get_target(target_name)
            if target_name
            else self._config.default_target
        )
        if target.name in self._connections:
            si = self._connections[target.name]
            try:
                _ = si.content.sessionManager.currentSession
                return si
            except (vmodl.fault.NotAuthenticated, Exception):
                del self._connections[target.name]
        si = self._create_connection(target)
        self._connections[target.name] = si
        return si

    def list_targets(self) -> list[str]:
        return [t.name for t in self._config.targets]

    @staticmethod
    def _create_connection(target: TargetConfig) -> ServiceInstance:
        from pyVim.connect import Disconnect, SmartConnect

        context = None
        if not target.verify_ssl:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

        si = SmartConnect(
            host=target.host,
            user=target.username,
            pwd=target.password,
            port=target.port,
            sslContext=context,
            disableSslCertValidation=not target.verify_ssl,
        )
        # Tag the ServiceInstance with the target's trust preference so
        # downstream REST helpers (vmware_vks.ops.supervisor._build_ssl_context)
        # honour it instead of hardcoding CERT_NONE.
        si._vmware_vks_verify_ssl = target.verify_ssl
        atexit.register(Disconnect, si)
        return si
