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


# ServiceInstance is a pyVmomi ManagedObject — its __setattr__ rejects any
# attribute not in its allowed list (raises "Managed object attributes are
# read-only" on pyVmomi 8.x). We keep per-connection metadata in this module
# dict, keyed by id(si). Cleared via atexit when the SI is disconnected.
# 踩坑 #32 (2026-05-19, 客户 vCenter 8.0U3 现场).
_SI_VERIFY_SSL: dict[int, bool] = {}


def get_verify_ssl(si: "ServiceInstance") -> bool:
    """Return verify_ssl flag stashed by the connect() that created ``si``.

    Defaults to True (strict) if the SI was created outside this manager.
    """
    return _SI_VERIFY_SSL.get(id(si), True)


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
        # Stash verify_ssl in module dict (NOT on si — pyVmomi 8.x rejects
        # setattr on ManagedObject, see 踩坑 #32). Consumers read via
        # get_verify_ssl(si).
        _SI_VERIFY_SSL[id(si)] = target.verify_ssl

        def _cleanup(_si: "ServiceInstance" = si) -> None:
            _SI_VERIFY_SSL.pop(id(_si), None)
            try:
                Disconnect(_si)
            except Exception:
                pass

        atexit.register(_cleanup)
        return si
