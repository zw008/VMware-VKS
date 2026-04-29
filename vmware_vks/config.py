"""Configuration management for VMware VKS.

Loads targets and settings from YAML config file + environment variables.
Passwords are NEVER stored in config files — always via environment variables.
"""

from __future__ import annotations

import logging
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path


import yaml
from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".vmware-vks"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
ENV_FILE = CONFIG_DIR / ".env"

_log = logging.getLogger("vmware-vks.config")

load_dotenv(ENV_FILE)


def _check_env_permissions() -> None:
    if not ENV_FILE.exists():
        return
    try:
        mode = ENV_FILE.stat().st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            _log.warning(
                "Security warning: %s has permissions %s (should be 600). "
                "Run: chmod 600 %s",
                ENV_FILE,
                oct(stat.S_IMODE(mode)),
                ENV_FILE,
            )
    except OSError:
        pass


_check_env_permissions()


@dataclass(frozen=True)
class TargetConfig:
    """A vCenter connection target."""

    name: str
    host: str
    username: str
    port: int = 443
    verify_ssl: bool = True

    @property
    def password(self) -> str:
        env_key = f"VMWARE_VKS_{self.name.upper().replace('-', '_')}_PASSWORD"
        pw = os.environ.get(env_key, "")
        if not pw:
            raise OSError(
                f"Password not found. Set environment variable: {env_key}"
            )
        return pw


@dataclass(frozen=True)
class AppConfig:
    """Top-level application config."""

    targets: tuple[TargetConfig, ...] = ()

    def get_target(self, name: str) -> TargetConfig:
        for t in self.targets:
            if t.name == name:
                return t
        available = ", ".join(t.name for t in self.targets)
        raise KeyError(f"Target '{name}' not found. Available: {available}")

    @property
    def default_target(self) -> TargetConfig:
        if not self.targets:
            raise ValueError("No targets configured. Check config.yaml")
        return self.targets[0]


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load config from YAML file."""
    path = config_path or CONFIG_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy config.example.yaml to {CONFIG_FILE} and edit it."
        )
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    targets = tuple(
        TargetConfig(
            name=t["name"],
            host=t["host"],
            username=t.get("username", "administrator@vsphere.local"),
            port=t.get("port", 443),
            verify_ssl=t.get("verify_ssl", True),
        )
        for t in raw.get("targets", [])
    )
    return AppConfig(targets=targets)
