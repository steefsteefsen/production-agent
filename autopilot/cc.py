"""Claude Code im Abo-Betrieb (Max 5×): eine Stelle für Umgebung, Modelle, Preflight, Quota-Erkennung.

Grundsatz: Die Builder-/Reviewer-/Decider-Läufe kosten nichts extra – sie laufen über das Abo, nicht über
die API. Deshalb bekommen ihre claude-Subprozesse KEINEN ANTHROPIC_API_KEY (sonst würde nach Verbrauch
abgerechnet). Nur der Production-Agent/die Evals nutzen den Key aus .env – das ist die einzige Stelle mit Kosten.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MODEL = {"builder": "sonnet", "reviewer": "sonnet", "decider": "opus"}
# 429 / Nutzungsgrenze / "resets at ..." – Signale einer erschöpften Abo-Quote
_QUOTA_RE = re.compile(
    r"\b429\b|rate[ -]?limit|quota|usage limit|too many requests|resets? at|limit reached", re.I
)


def env(api_billing: bool = False) -> dict:
    """Umgebung für claude-Subprozesse: ohne ANTHROPIC_API_KEY (Abo), außer --api-billing ist gesetzt."""
    e = dict(os.environ)
    if not api_billing:
        e.pop("ANTHROPIC_API_KEY", None)
    return e


def _settings() -> dict:
    out: dict[str, str] = {}
    p = ROOT / "settings.env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def model(role: str) -> str:
    """Modell je Rolle aus settings.env (CC_MODEL_BUILDER/REVIEWER/DECIDER) mit Standard sonnet/sonnet/opus."""
    return _settings().get(f"CC_MODEL_{role.upper()}", _DEFAULT_MODEL[role])


def is_quota(returncode: int, output: str) -> bool:
    """Deutet die Ausgabe auf eine erschöpfte Quote (429/Limit) hin?"""
    return bool(_QUOTA_RE.search(output or ""))


def preflight(api_billing: bool = False) -> tuple[bool, str]:
    """Vor dem Start: ist Claude Code über das Abo angemeldet? Sonst klarer Abbruch statt Kosten/Hänger."""
    try:
        r = subprocess.run(
            ["claude", "auth", "status"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=60,
            env=env(api_billing),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, f"claude auth status: {e}"
    if r.returncode != 0:
        return False, "Claude Code ist nicht angemeldet"
    out = (r.stdout + r.stderr).lower()
    if (
        not api_billing
        and ("api key" in out or "anthropic_api_key" in out)
        and "subscription" not in out
    ):
        return False, "Claude Code ist nicht über das Abo angemeldet (API-Key erkannt)"
    return True, "ok"
