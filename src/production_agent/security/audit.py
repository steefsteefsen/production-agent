"""Audit-Log: jeder Werkzeugaufruf und jede Freigabeentscheidung als JSONL-Zeile."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, **fields: Any) -> None:
        entry = {"ts": time.time(), "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
