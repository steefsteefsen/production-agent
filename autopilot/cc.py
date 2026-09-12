"""Claude Code im Abo-Betrieb (Max 5×): eine Stelle für Umgebung, Modelle, Preflight, Quota-Erkennung.

Grundsatz: Die Builder-/Reviewer-/Decider-Läufe kosten nichts extra – sie laufen über das Abo, nicht über
die API. Deshalb bekommen ihre claude-Subprozesse KEINEN ANTHROPIC_API_KEY (sonst würde nach Verbrauch
abgerechnet). Nur der Production-Agent/die Evals nutzen den Key aus .env – das ist die einzige Stelle mit Kosten.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_MODEL = {"builder": "sonnet", "reviewer": "sonnet", "decider": "opus"}
# Klartext-Signale einer erschöpften Quote – nur zusammen mit einer echten Fehlerantwort ausgewertet
_QUOTA_TEXT = ("rate limit", "usage limit", "resets at", "insufficient credit")
DENIED_PATH = ROOT / "autopilot" / "state" / "denied.json"
# Muster, die NIE als Recht gelernt werden dürfen – die Deny-Liste bleibt unantastbar
NEVER_LEARN = ("git push", "rm -rf", "rm ", "sudo", ".env", "decisions.yaml", "tests/acceptance")


def is_forbidden(pattern_or_cmd: str) -> bool:
    """True, wenn ein Befehl/Muster nie automatisch erlaubt werden darf (git push, rm -rf, .env …)."""
    low = (pattern_or_cmd or "").lower()
    return any(t in low for t in NEVER_LEARN)


def _pattern(cmd: str) -> str | None:
    """'npm test --watch' → 'Bash(npm test:*)': Werkzeug + Unterbefehl bis zum ersten Argument."""
    cmd = (cmd or "").strip()
    if not cmd:
        return None
    toks = cmd.split()
    prefix: list[str] = []
    for t in toks:
        if t.startswith("-"):
            break
        prefix.append(t)
        if len(prefix) >= 2:  # Werkzeug + Unterbefehl reicht als Präfix
            break
    return f"Bash({' '.join(prefix) or toks[0]}:*)"


def learn_denials(output: str, path: Path = DENIED_PATH) -> list[str]:
    """permission_denials einer claude-Antwort als Befehlsmuster nach denied.json schreiben; NEUE zurückgeben."""
    data = _last_json(output)
    denials = data.get("permission_denials", []) if isinstance(data, dict) else []
    existing: list = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    seen = {e.get("pattern") for e in existing if isinstance(e, dict)}
    new: list[str] = []
    for d in denials:
        cmd = d.get("command") or (d.get("tool_input") or {}).get("command") or ""
        pat = _pattern(cmd)
        if pat and pat not in seen:
            seen.add(pat)
            existing.append({"pattern": pat, "command": cmd})
            new.append(pat)
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return new


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


def _last_json(output: str) -> dict | None:
    for line in reversed((output or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None


def is_quota(returncode: int, output: str) -> bool:
    """Erschöpfte Quote nur bei ECHTER Fehlerantwort: is_error true UND 429/402 oder klarer Quota-Text.
    Eine erfolgreiche Antwort (auch wenn das Wort 'limit' im Text steht) löst NIE eine Pause aus."""
    data = _last_json(output)
    if isinstance(data, dict):
        if not data.get("is_error"):
            return False
        status = str(data.get("api_error_status") or data.get("status") or "")
        blob = json.dumps(data, ensure_ascii=False).lower()
        return status in ("429", "402") or any(s in blob for s in _QUOTA_TEXT)
    low = (output or "").lower()
    return bool(re.search(r"\b(429|402)\b", low)) and any(s in low for s in _QUOTA_TEXT)


def probe(api_billing: bool = False, timeout: int = 120) -> bool:
    """Aktive Quota-Probe: ein winziger claude-Aufruf. True = Abo nimmt wieder an, False = noch erschöpft.

    Dient der Wiederaufnahme nach einer Quota-Pause (orchestrate.py) – statt blind zu warten, wird je
    Wartrunde geprüft, ob das Abo wieder Anfragen annimmt. Fehler/Timeout → False (vorsichtshalber weiter warten)."""
    try:
        r = subprocess.run(
            [
                "claude",
                "-p",
                "ping",
                "--model",
                model("builder"),
                "--max-turns",
                "1",
                "--output-format",
                "json",
                "--permission-mode",
                "dontAsk",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            env=env(api_billing),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return not is_quota(r.returncode, r.stdout + r.stderr)


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
