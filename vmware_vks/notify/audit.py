"""Audit logger — writes JSON Lines to ~/.vmware-vks/audit.log."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

_AUDIT_DIR = Path.home() / ".vmware-vks"
_AUDIT_FILE = _AUDIT_DIR / "audit.log"
_log = logging.getLogger("vmware-vks.audit")


class AuditLogger:
    def __init__(self, log_file: Path = _AUDIT_FILE) -> None:
        self._file = log_file
        self._file.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        target: str,
        operation: str,
        resource: str,
        parameters: dict,
        result: str,
        user: str = "",
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": target,
            "operation": operation,
            "resource": resource,
            "parameters": parameters,
            "result": result,
            "user": user,
        }
        try:
            with open(self._file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            _log.warning("Failed to write audit log: %s", e)
