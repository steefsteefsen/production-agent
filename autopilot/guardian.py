#!/usr/bin/env python3
"""Guardian: läuft VOR jedem Commit (git pre-commit) und blockiert, wenn Sicherheit, Konsistenz oder
Dokumentationsaktualität verletzt sind. Deterministisch, in Sekunden, ohne LLM. Mit --llm zusätzlich ein
kontextfreier Doku-Konsistenz-Check über claude -p (nur wenn src/ und docs/ auseinanderlaufen könnten).

Regeln (jede mit Nummer, damit Fehlermeldungen zitierbar sind):
 S1  keine Secrets im Commit (Muster für API-Keys, private Keys, .env)
 S2  keine verbotenen Bibliotheken (Ausschlussliste aus CLAUDE.md) in pyproject/imports
 S3  MES-Server hat genau 6 @mcp.tool, RAG-Server genau 1, kein Werkzeug heißt *sql*/*query*/*write*
 S4  jede SQL-Tabelle in schema.sql steht in sql_guard.ALLOWED_TABLES (und umgekehrt)
 S5  decisions.yaml wird nie von einem Agenten geändert (Hash in .guardian/decisions.sha256; Änderung nur mit GUARDIAN_ALLOW_DECISIONS=1)
 S6  Sicherheitsmodule unverändert oder mit grünen tests/test_security.py + test_mcp_protocol.py
 K1  jedes neue/geänderte Modul unter src/ hat eine Testdatei tests/test_<name>.py, die mindestens einen Verifikations- und einen Falsifikationstest enthält
 K2  ruff check und bandit sauber
 D1  jedes Modul unter src/ ist in README.md oder docs/ namentlich erwähnt (Modulname)
 D2  jede Datei docs/adr/*.md hat die Pflichtabschnitte Kontext / Optionen / Entscheidung / Konsequenzen
 D3  wenn src/ geändert wurde, wurde in demselben Commit auch docs/ oder README.md oder ein Test geändert (Doku-Aktualität)
 S7  kein WERT aus der lokalen .env taucht in irgendeiner getrackten oder gestagten Datei auf (Kopier-Leck), und keine
     Datei, die .gitignore ausschließt, ist gestaged (git add -f umgangen)
 S8  Öffentlichkeits-Filter: keine Begriffe aus .guardian_public/blocklist.sha256 (als Hash hinterlegt) in getrackten Dateien
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_LIBS = [
    "databricks",
    "pyspark",
    "kafka",
    "dbt",
    "airflow",
    "terraform",
    "kubernetes",
    "google.cloud",
    "pyiceberg",
    "deltalake",
]
SECRET_PATTERNS = [
    r"sk-ant-[A-Za-z0-9\-_]{20,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"AKIA[0-9A-Z]{16}",
    r"ghp_[A-Za-z0-9]{30,}",
]
# Modul → Testdateien (explizit, damit ein Modul in mehreren Testdateien geprüft werden darf)
TEST_MAP = {
    "sql_guard": ["test_security.py"],
    "injection_guard": ["test_security.py"],
    "action_policy": ["test_security.py"],
    "audit": ["test_security.py", "test_mcp_protocol.py"],
    "mes_server": ["test_mcp_protocol.py"],
    "rag_server": ["test_rag_server.py"],
    "workflow": ["test_workflow.py", "test_trajectory.py"],
    "simulator": ["test_simulator.py"],
    "replay": ["test_replay.py"],
    "server": ["test_server.py"],
}
SECURITY_FILES = [
    "src/production_agent/security/",
    "src/production_agent/mcp/mes_server.py",
    "src/production_agent/graph/workflow.py",
]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout


def staged() -> list[str]:
    return [
        f
        for f in sh(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]).splitlines()
        if f
    ]


def staged_text(path: str) -> str:
    return sh(["git", "show", f":{path}"])


def main(use_llm: bool = False) -> int:
    files = staged()
    errors: list[str] = []
    warn: list[str] = []

    # S1 Secrets
    for f in files:
        if f == ".env" or f.endswith("/.env"):
            errors.append(f"S1 .env darf nie committet werden: {f}")
        txt = staged_text(f) if not f.endswith((".png", ".sqlite", ".zip")) else ""
        for pat in SECRET_PATTERNS:
            if re.search(pat, txt):
                errors.append(f"S1 Secret-Muster in {f}")

    # S7 .env-Werte dürfen nirgends sonst stehen; ignorierte Dateien dürfen nicht gestaged sein
    env = ROOT / ".env"
    tracked = [f for f in sh(["git", "ls-files"]).splitlines() if f] + files
    if env.exists():
        values = []
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                v = line.split("=", 1)[1].strip().strip("\"'")
                if (
                    len(v) >= 8
                    and not v.startswith(("sk-ant-...", "http://localhost"))
                    and v not in ("data/gold/mes.sqlite",)
                ):
                    values.append(v)
        for f in set(tracked):
            if f == ".env" or (ROOT / f).suffix in (".png", ".sqlite", ".zip", ".parquet"):
                continue
            try:
                txt = (
                    staged_text(f)
                    if f in files
                    else (ROOT / f).read_text(encoding="utf-8", errors="ignore")
                )
            except OSError:
                continue
            for v in values:
                if v in txt:
                    errors.append(
                        f"S7 Wert aus .env in {f} gefunden (Kopier-Leck: {v[:4]}…{v[-2:]})"
                    )
    for f in files:
        if subprocess.run(["git", "check-ignore", "-q", f], cwd=ROOT).returncode == 0:
            errors.append(f"S7 {f} steht in .gitignore, ist aber gestaged (git add -f?)")

    # S8 Öffentlichkeits-Filter
    bl = ROOT / ".guardian_public" / "blocklist.sha256"
    if bl.exists():
        hashes = {
            ln.strip()
            for ln in bl.read_text().splitlines()
            if ln.strip() and not ln.startswith("#")
        }
        word_re = re.compile(r"[a-zäöüß0-9]{3,}(?: [a-zäöüß]{3,})?")
        for f in set(tracked):
            if (ROOT / f).suffix in (".png", ".sqlite", ".zip", ".parquet") or f.startswith(
                ".guardian_public"
            ):
                continue
            try:
                txt = (
                    staged_text(f)
                    if f in files
                    else (ROOT / f).read_text(encoding="utf-8", errors="ignore")
                ).lower()
            except OSError:
                continue
            hits = {
                m.group(0)
                for m in word_re.finditer(txt)
                if hashlib.sha256(m.group(0).encode()).hexdigest() in hashes
            }
            single = {
                w
                for w in re.findall(r"[a-zäöüß0-9]{3,}", txt)
                if hashlib.sha256(w.encode()).hexdigest() in hashes
            }
            for h in sorted(hits | single):
                errors.append(f"S8 Begriff der Öffentlichkeits-Blockliste in {f}: '{h}'")

    # S2 verbotene Bibliotheken
    for f in files:
        if f.endswith((".py", ".toml", ".txt")) and not f.startswith("autopilot/guardian"):
            txt = staged_text(f).lower()
            for lib in FORBIDDEN_LIBS:
                if re.search(rf"(import|from|\"|')\s*{re.escape(lib)}", txt):
                    errors.append(
                        f"S2 verbotene Bibliothek '{lib}' in {f} (Ausschlussliste CLAUDE.md)"
                    )

    # S3 Werkzeuganzahl
    mes = (ROOT / "src/production_agent/mcp/mes_server.py").read_text(encoding="utf-8")
    rag = (ROOT / "src/production_agent/mcp/rag_server.py").read_text(encoding="utf-8")
    n_mes, n_rag = mes.count("@mcp.tool"), rag.count("@mcp.tool")
    if n_mes != 6:
        errors.append(f"S3 MES-Server hat {n_mes} Werkzeuge, erlaubt sind genau 6")
    if n_rag != 1:
        errors.append(f"S3 RAG-Server hat {n_rag} Werkzeuge, erlaubt ist genau 1")
    for name in re.findall(r"@mcp\.tool\(\)\s*\ndef\s+(\w+)", mes + rag):
        if any(x in name.lower() for x in ("sql", "query", "write", "exec")):
            errors.append(f"S3 Werkzeugname '{name}' deutet auf freies SQL/Schreiben hin")

    # S4 Schema ↔ Allowlist
    schema = (ROOT / "src/production_agent/data/schema.sql").read_text(encoding="utf-8")
    tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", schema))
    guard = (ROOT / "src/production_agent/security/sql_guard.py").read_text(encoding="utf-8")
    allowed = set(re.findall(r'"(\w+)",', guard.split("ALLOWED_TABLES")[1].split("}")[0]))
    if tables != allowed:
        errors.append(
            f"S4 schema.sql ≠ ALLOWED_TABLES: nur in Schema {tables - allowed}, nur in Allowlist {allowed - tables}"
        )

    # S5 decisions.yaml eingefroren
    dec = ROOT / "decisions.yaml"
    stamp = ROOT / ".guardian" / "decisions.sha256"
    h = hashlib.sha256(dec.read_bytes()).hexdigest()
    if stamp.exists() and stamp.read_text().strip() != h and "decisions.yaml" in files:
        import os

        if os.environ.get("GUARDIAN_ALLOW_DECISIONS") != "1":
            errors.append(
                "S5 decisions.yaml geändert – nur Stefan darf das: GUARDIAN_ALLOW_DECISIONS=1 git commit …"
            )
    if "decisions.yaml" in files and not errors:
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(h)

    # S6 Sicherheitsmodule → Tests müssen grün sein
    if any(f.startswith(tuple(SECURITY_FILES)) for f in files):
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_security.py",
                "tests/test_mcp_protocol.py",
                "tests/test_trajectory.py",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            errors.append("S6 Sicherheitsmodul geändert, Sicherheitstests rot:\n" + r.stdout[-800:])

    # K1 Tests je Modul (Verifikation + Falsifikation)
    for f in files:
        if (
            f.startswith("src/production_agent/")
            and f.endswith(".py")
            and not f.endswith("__init__.py")
        ):
            name = Path(f).stem
            if name in ("config", "state", "prompts", "schema"):
                continue
            cands = [ROOT / "tests" / t for t in TEST_MAP.get(name, [f"test_{name}.py"])]
            cands = [c for c in cands if c.exists()]
            if not cands:
                errors.append(f"K1 kein tests/test_{name}*.py für {f}")
                continue
            body = "\n".join(c.read_text(encoding="utf-8") for c in cands).lower()
            if "falsif" not in body:
                errors.append(
                    f"K1 {cands[0].name}: kein Falsifikationstest markiert (Wort 'falsif' im Namen/Kommentar)"
                )

    # K2 Lint / Bandit
    for tool, cmd in (
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("bandit", [sys.executable, "-m", "bandit", "-q", "-c", "pyproject.toml", "-r", "src"]),
    ):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"K2 {tool} rot: {(r.stdout + r.stderr)[-300:].strip()}")

    # D1 Modul in Doku erwähnt
    doc_text = (ROOT / "README.md").read_text(encoding="utf-8") + "".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "docs").rglob("*.md")
    )
    for f in files:
        if (
            f.startswith("src/production_agent/")
            and f.endswith(".py")
            and not f.endswith("__init__.py")
        ):
            if Path(f).name not in doc_text and Path(f).stem not in doc_text:
                errors.append(f"D1 {f} in README/docs nicht erwähnt")

    # D2 ADR-Pflichtabschnitte
    for adr in (ROOT / "docs/adr").glob("*.md"):
        if adr.name.startswith("0000"):
            continue
        t = adr.read_text(encoding="utf-8")
        missing = [
            h
            for h in ("## Kontext", "## Optionen", "## Entscheidung", "## Konsequenzen")
            if h not in t
        ]
        if missing:
            errors.append(f"D2 {adr.name} ohne Abschnitt(e) {missing}")

    # D3 Doku-Aktualität
    src_changed = any(f.startswith("src/") for f in files)
    doc_changed = any(f.startswith(("docs/", "tests/")) or f == "README.md" for f in files)
    if src_changed and not doc_changed:
        errors.append(
            "D3 src/ geändert, aber weder docs/, README.md noch tests/ – Doku oder Tests nachziehen"
        )

    # optional LLM-Konsistenz
    if use_llm and src_changed and not errors:
        diff = sh(["git", "diff", "--cached"])[:30000]
        prompt = (
            "Prüfe kontextfrei, ob dieser Diff Aussagen in README.md oder docs/ veraltet macht (Werkzeugnamen, "
            "Tabellen, Ablauf, Regeln). Antworte nur mit 'OK' oder einer Liste 'VERALTET: <Datei>: <Aussage>'.\n"
            + diff
        )
        r = subprocess.run(
            [
                "claude",
                "-p",
                prompt,
                "--model",
                "haiku",
                "--max-turns",
                "6",
                "--allowedTools",
                "Read,Grep",
                "--permission-mode",
                "dontAsk",
                "--output-format",
                "text",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if "VERALTET" in r.stdout:
            warn.append("LLM-Konsistenz: " + r.stdout.strip()[:800])

    for w in warn:
        print("WARNUNG", w)
    if errors:
        print("GUARDIAN blockiert den Commit:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"GUARDIAN ok ({len(files)} Dateien geprüft)")
    return 0


if __name__ == "__main__":
    if "--init" in sys.argv:  # Hash von decisions.yaml einfrieren (einmal, durch Stefan)
        (ROOT / ".guardian").mkdir(exist_ok=True)
        (ROOT / ".guardian/decisions.sha256").write_text(
            hashlib.sha256((ROOT / "decisions.yaml").read_bytes()).hexdigest()
        )
        print("decisions.yaml eingefroren")
        sys.exit(0)
    sys.exit(main(use_llm="--llm" in sys.argv))
