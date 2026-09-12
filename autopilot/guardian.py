#!/usr/bin/env python3
"""Guardian: läuft VOR jedem Commit (git pre-commit) und blockiert, wenn Sicherheit, Konsistenz oder
Dokumentationsaktualität verletzt sind. Deterministisch, ohne LLM, in Sekunden. Mit --llm zusätzlich
ein kontextfreier Doku-Konsistenz-Check über claude -p (manuell, nicht im Hook – Kosten/Nichtdeterminismus).

Regeln (S1–S9, K1–K9, D1–D11), je eine Zeile – hieraus erzeugt status.py den Marker auto:guardian_rules:
 S1  keine Secrets, keine .env committet
 S2  keine verbotene Bibliothek der Ausschlussliste (CLAUDE.md)
 S3  MES-Server genau 6 Werkzeuge, RAG genau 1, kein Werkzeug *sql/query/write/exec*
 S4  schema.sql und ALLOWED_TABLES identisch
 S5  decisions.yaml eingefroren (Hash; Aenderung nur mit GUARDIAN_ALLOW_DECISIONS=1)
 S6  Sicherheitsmodul geaendert -> Sicherheits-, Protokoll- und Trajektorientests gruen
 S7  kein .env-Wert (len>=8) in anderer getrackter/gestagter Datei; S7b .env nur KEY|SECRET|TOKEN|PASSWORD-Schluessel; S7c .env.example-Werte enden auf -EXAMPLE
 S8  keine Begriffe der Oeffentlichkeits-Blocklist (.guardian_public/blocklist.sha256)
 S9  gestagte Binaerdateien nur unter docs/status/ oder docs/images/ und < 500 KB
 K1  jedes src-Modul hat eine Testdatei mit Verifikations- und Falsifikationstest
 K2  ruff und bandit sauber
 K3  Commit-Message folgt der Konvention (commit-msg-Hook)
 K4  Coverage: gesamt >=80, security >=95, mes_server/workflow >=85
 K5  jede entry-Zeile in .pre-commit-config.yaml beginnt mit .venv/bin/python
 K6  tasks.yaml-WPs stehen in plan.yaml, Abhaengigkeiten sind aufloesbar und azyklisch
 K7  tests/acceptance/ nur mit GUARDIAN_ALLOW_ACCEPTANCE=1 aenderbar (Abnahmetests = Spezifikation)
 K8  autopilot/ geaendert -> autopilot/selfcheck.py grün (GUARDIAN_SKIP_K8=1 unterdrueckt)
 K9  gelernte Rechte (state/denied.json) noch nicht erlaubt -> WARNUNG mit Allow-Vorschlag (blockiert nie)
 D1  jedes src-Modul ist in README oder docs/ namentlich erwaehnt
 D2  jede ADR hat Kontext / Optionen / Entscheidung / Konsequenzen
 D3  src geaendert -> auch docs/, README oder tests/ geaendert
 D4  docs/AENDERUNGEN.md vorhanden und nicht leer
 D5  README.md verlinkt docs/status/index.html
 D6  docs/status/status.json gestaged, frisch (<10 min), commit leer oder == HEAD
 D7  jeder auto-Marker in getrackten *.md hat den von status.py berechneten Wert
 D8  ausserhalb Markern keine getippten Zahlen/Regelbereiche/Coverage in README.md und docs/*.md
 D9  README.md hat Abschnitt "## Stand" mit nicht-leerem auto:stand-Marker
 D11 jede Datei unter docs/ steht in docs/index.md

GUARDIAN_ENV_FILE (Standard .env) waehlt die Geheimnis-Datei (Selbsttest nutzt eine Kopie).
GUARDIAN_SKIP_D6=1 unterdrueckt D6 (status.py ruft den Guardian, bevor status.json gestaged ist).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

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
BINARY_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".sqlite",
    ".parquet",
    ".pyc",
    ".woff",
    ".woff2",
    ".ico",
)
SECRET_KEY_RE = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD)$")
DOC_FACT_PATTERNS = [
    (re.compile(r"\b\d+\s+Tests?\b"), "auto:tests"),
    (re.compile(r"\bS1\s*[–-]\s*S\d"), "auto:guardian_rules"),
    (re.compile(r"\bK1\s*[–-]\s*K\d"), "auto:guardian_rules"),
    (re.compile(r"\bD1\s*[–-]\s*D\d"), "auto:guardian_rules"),
    (re.compile(r"\b\d+\s+Werkzeuge?\b"), "auto:tools_mes"),
]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True).stdout.decode(
        "utf-8", errors="replace"
    )


def is_binary(path: Path) -> bool:
    """S9-Hilfe: Binär bei bekannter Endung oder NUL-Byte in den ersten 8 KiB."""
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        return b"\x00" in path.read_bytes()[:8192]
    except OSError:
        return False


def staged() -> list[str]:
    return [
        f
        for f in sh(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]).splitlines()
        if f
    ]


def staged_text(path: str) -> str:
    return sh(["git", "show", f":{path}"])


# --- importierbare Prüffunktionen (testbar) ----------------------------------------------


def _env_pairs(env_text: str) -> list[tuple[str, str]]:
    pairs = []
    for line in env_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        pairs.append((k.strip(), v.strip().strip("\"'")))
    return pairs


def is_placeholder(v: str) -> bool:
    return v.endswith("-EXAMPLE") or v.endswith("...")


def check_env_leak(env_text: str, files: dict[str, str]) -> list[str]:
    """S7: kein .env-Wert (len>=8) darf in einer anderen Datei stehen. Platzhalter sind ausgenommen."""
    errs = []
    values = [(k, v) for k, v in _env_pairs(env_text) if len(v) >= 8 and not is_placeholder(v)]
    for fname, txt in files.items():
        for k, v in values:
            if v in txt:
                errs.append(
                    f"S7 Wert aus .env ({k}) in {fname} gefunden (Kopier-Leck: {v[:4]}…{v[-2:]})"
                )
    return errs


def check_env_keys(env_text: str) -> list[str]:
    """S7b: .env darf nur Geheimnis-Schlüssel enthalten (KEY|SECRET|TOKEN|PASSWORD)."""
    return [
        f"S7b .env-Schlüssel {k} ist kein Geheimnis – gehört in settings.env"
        for k, _ in _env_pairs(env_text)
        if not SECRET_KEY_RE.search(k)
    ]


def check_example_suffix(example_text: str) -> list[str]:
    """S7c: jeder Wert in .env.example endet auf -EXAMPLE."""
    return [
        f"S7c .env.example {k} endet nicht auf -EXAMPLE"
        for k, v in _env_pairs(example_text)
        if v and not v.endswith("-EXAMPLE")
    ]


def check_binary_placement(files: list[str], root: Path = ROOT) -> list[str]:
    """S9: gestagte Binärdateien nur unter docs/status/ oder docs/images/ und < 500 KB."""
    errs = []
    for f in files:
        p = root / f
        if is_binary(p):
            allowed = f.startswith(("docs/status/", "docs/images/"))
            size = p.stat().st_size if p.exists() else 0
            if not allowed or size >= 500 * 1024:
                errs.append(f"S9 Binärdatei {f}")
    return errs


def d6_applies(files: list[str]) -> bool:
    """D6 prüft den Projektstatus nur, wenn überhaupt etwas gestaged ist (leerer Index → kein D6)."""
    return bool(files)


def check_precommit_entries(text: str) -> list[str]:
    """K5: jede entry-Zeile beginnt mit .venv/bin/python."""
    errs = []
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"\s*entry:\s*(.+)$", line)
        if m and not m.group(1).strip().strip("\"'").startswith(".venv/bin/python"):
            errs.append(
                f"K5 .pre-commit-config.yaml:{i} entry beginnt nicht mit .venv/bin/python: "
                f"{m.group(1).strip()[:40]}"
            )
    return errs


def _blank_markers(text: str) -> str:
    return re.sub(
        r"<!-- auto:[a-z_]+ -->.*?<!-- /auto:[a-z_]+ -->",
        lambda m: "\n" * m.group(0).count("\n"),
        text,
        flags=re.S,
    )


def check_doc_facts(files: dict[str, str]) -> list[str]:
    """D8: außerhalb von Markern keine getippten Zahlen/Regelbereiche/Coverage-Prozente."""
    errs = []
    for fname, txt in files.items():
        for i, line in enumerate(_blank_markers(txt).splitlines(), 1):
            for pat, marker in DOC_FACT_PATTERNS:
                if pat.search(line):
                    errs.append(
                        f"D8 {fname}:{i} getippte Angabe – nutze <!-- {marker} -->: {line.strip()[:60]}"
                    )
            if "coverage" in line.lower() and re.search(r"\b\d+\s*%", line):
                errs.append(
                    f"D8 {fname}:{i} getippte Coverage – nutze <!-- auto:coverage_total -->: {line.strip()[:60]}"
                )
    return errs


def check_markers(files: dict[str, str], values: dict[str, str]) -> list[str]:
    """D7: jeder auto-Marker hat den berechneten Wert."""
    errs = []
    for fname, txt in files.items():
        for key, val in values.items():
            for m in re.finditer(rf"<!-- auto:{key} -->(.*?)<!-- /auto:{key} -->", txt, re.S):
                if m.group(1).strip() != val.strip():
                    errs.append(
                        f"D7 {fname}: Marker auto:{key} veraltet – status.py --stage ausführen"
                    )
                    break
    return errs


# --- Hauptlauf ---------------------------------------------------------------------------


def main(use_llm: bool = False) -> int:  # noqa: C901
    files = staged()
    errors: list[str] = []
    warn: list[str] = []
    tracked = [f for f in sh(["git", "ls-files"]).splitlines() if f] + files

    def get_text(f: str) -> str:
        try:
            return (
                staged_text(f)
                if f in files
                else (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            )
        except OSError:
            return ""

    # S1 Secrets
    for f in files:
        if f == ".env" or f.endswith("/.env"):
            errors.append(f"S1 .env darf nie committet werden: {f}")
        if is_binary(ROOT / f):
            continue
        txt = get_text(f)
        for pat in SECRET_PATTERNS:
            if re.search(pat, txt):
                errors.append(f"S1 Secret-Muster in {f}")

    # S9 gestagte Binärdateien nur unter docs/status/ oder docs/images/ und < 500 KB
    errors += check_binary_placement(files)

    # S7 .env-Werte, S7b Schlüssel, S7c Beispielwerte, ignorierte Dateien nicht gestaged
    env_path = Path(os.environ.get("GUARDIAN_ENV_FILE", str(ROOT / ".env")))
    if not env_path.is_absolute():
        env_path = ROOT / env_path
    if env_path.exists():
        env_text = env_path.read_text(encoding="utf-8")
        files_map = {
            f: get_text(f)
            for f in set(tracked)
            if not is_binary(ROOT / f) and (ROOT / f).resolve() != env_path.resolve()
        }
        errors += check_env_leak(env_text, files_map)
        errors += check_env_keys(env_text)
        ph = [k for k, v in _env_pairs(env_text) if is_placeholder(v)]
        if ph:
            warn.append(f"Platzhalter in .env – Key fehlt ({', '.join(ph)})")
    ex = ROOT / ".env.example"
    if ex.exists():
        errors += check_example_suffix(ex.read_text(encoding="utf-8"))
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
        for f in set(tracked):
            if is_binary(ROOT / f) or f.startswith(".guardian_public"):
                continue
            txt = get_text(f).lower()
            single = {
                w
                for w in re.findall(r"[a-zäöüß0-9]{3,}", txt)
                if hashlib.sha256(w.encode()).hexdigest() in hashes
            }
            for h in sorted(single):
                errors.append(f"S8 Begriff der Öffentlichkeits-Blockliste in {f}: '{h}'")

    # S2 verbotene Bibliotheken
    for f in files:
        if f.endswith((".py", ".toml", ".txt")) and not f.startswith("autopilot/guardian"):
            txt = get_text(f).lower()
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
        if os.environ.get("GUARDIAN_ALLOW_DECISIONS") != "1":
            errors.append(
                "S5 decisions.yaml geändert – nur Stefan darf das: GUARDIAN_ALLOW_DECISIONS=1 git commit …"
            )
    if "decisions.yaml" in files and not errors:
        stamp.parent.mkdir(exist_ok=True)
        stamp.write_text(h)

    # S6 Sicherheitsmodule → Tests müssen grün sein (ohne Coverage-Gate, sonst Teilmenge < 80 %)
    if any(f.startswith(tuple(SECURITY_FILES)) for f in files):
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--no-cov",
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
                    f"K1 {cands[0].name}: kein Falsifikationstest markiert (Wort 'falsif')"
                )

    # K2 Lint / Bandit – nur PRÜFEN, nicht formatieren. Das Formatieren/Autofixen erledigt der Committer
    # (journal.commit, publish.py) VOR dem git add; würde der Guardian hier Dateien ändern und neu stagen,
    # meldete pre-commit „files were modified by this hook" und jeder Commit scheiterte einmal.
    for tool, cmd in (
        ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
        ("bandit", [sys.executable, "-m", "bandit", "-q", "-c", "pyproject.toml", "-r", "src"]),
    ):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"K2 {tool} rot: {(r.stdout + r.stderr)[-300:].strip()}")

    # K4 Coverage-Grenzen – nur .guardian/coverage.json aus dem VOLLEN Lauf zählt (Teilläufe ignoriert)
    cov_path = ROOT / ".guardian" / "coverage.json"
    if not cov_path.exists() or (time.time() - cov_path.stat().st_mtime) > 3600:
        cov_path.parent.mkdir(exist_ok=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:warnings",
                "--cov=production_agent",
                "--cov-report=json:.guardian/coverage.json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    if cov_path.exists():
        cov = json.loads(cov_path.read_text(encoding="utf-8"))
        total = cov.get("totals", {}).get("percent_covered", 0)
        if total < 80:
            errors.append(f"K4 Coverage gesamt {total:.0f}% < 80%")
        for path, info in cov.get("files", {}).items():
            pct = info["summary"]["percent_covered"]
            pp = path.replace("\\", "/")
            if "/security/" in pp and pct < 95:
                errors.append(f"K4 {pp} {pct:.0f}% < 95% (security)")
            if pp.endswith("mcp/mes_server.py") and pct < 85:
                errors.append(f"K4 {pp} {pct:.0f}% < 85%")
            if pp.endswith("graph/workflow.py") and pct < 85:
                errors.append(f"K4 {pp} {pct:.0f}% < 85%")
    else:
        errors.append("K4 coverage.json fehlt")

    # K5 pre-commit entry-Zeilen
    pc = ROOT / ".pre-commit-config.yaml"
    if pc.exists():
        errors += check_precommit_entries(pc.read_text(encoding="utf-8"))

    # K6 plan.yaml ⇔ tasks.yaml, azyklisch
    if (ROOT / "autopilot" / "plan.yaml").exists():
        try:
            import orchestrate  # noqa: PLC0415

            tids = {t["id"] for t in orchestrate.load_tasks()}
            errors += orchestrate.check_plan(tids, orchestrate.load_plan())
        except Exception as exc:  # noqa: BLE001
            warn.append(f"K6 plan.yaml nicht auswertbar: {exc}")

    # K7 Abnahmetests sind Spezifikation – Änderung nur mit ausdrücklicher Freigabe
    if os.environ.get("GUARDIAN_ALLOW_ACCEPTANCE") != "1":
        modified = sh(["git", "diff", "--cached", "--name-only", "--diff-filter=M"]).splitlines()
        for f in modified:
            if f.startswith("tests/acceptance/") and f.endswith(".py"):
                errors.append(f"K7 {f} geändert – Abnahmetest, nur mit GUARDIAN_ALLOW_ACCEPTANCE=1")

    # K8 Autopilot geändert → Selbstcheck muss grün sein (falsches Flag/Importfehler blockiert den Commit)
    if (
        any(f.startswith("autopilot/") and f.endswith(".py") for f in files)
        and os.environ.get("GUARDIAN_SKIP_K8") != "1"
    ):
        r = subprocess.run(  # noqa: S603
            [sys.executable, str(ROOT / "autopilot" / "selfcheck.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if r.returncode != 0:
            errors.append("K8 Selbstcheck rot:\n" + (r.stdout + r.stderr)[-800:].strip())

    # K9 gelernte, noch nicht erlaubte Rechte als WARNUNG melden (blockiert nie; Deny bleibt tabu)
    import cc  # noqa: PLC0415

    if cc.DENIED_PATH.exists():
        try:
            learned = json.loads(cc.DENIED_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            learned = []
        local = ROOT / ".claude" / "settings.local.json"
        allow = (
            json.loads(local.read_text(encoding="utf-8")).get("permissions", {}).get("allow", [])
            if local.exists()
            else []
        )
        for e in learned:
            pat = e.get("pattern") if isinstance(e, dict) else e
            cmd = e.get("command", "") if isinstance(e, dict) else ""
            if pat and pat not in allow and not cc.is_forbidden(pat) and not cc.is_forbidden(cmd):
                warn.append(
                    f"K9 neue Rechteanforderung {pat} – übernehmen mit "
                    f"`python autopilot/orchestrate.py --allow-learned` (→ .claude/settings.local.json)"
                )

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
            x
            for x in ("## Kontext", "## Optionen", "## Entscheidung", "## Konsequenzen")
            if x not in t
        ]
        if missing:
            errors.append(f"D2 {adr.name} ohne Abschnitt(e) {missing}")

    # D3 Doku-Aktualität
    src_changed = any(f.startswith("src/") for f in files)
    if src_changed and not any(
        f.startswith(("docs/", "tests/")) or f == "README.md" for f in files
    ):
        errors.append("D3 src/ geändert, aber weder docs/, README.md noch tests/ – nachziehen")

    # D4 Änderungshistorie
    ae = ROOT / "docs/AENDERUNGEN.md"
    if not ae.exists() or not ae.read_text(encoding="utf-8").strip():
        errors.append("D4 docs/AENDERUNGEN.md fehlt oder ist leer")

    # D5 Statusseite verlinkt
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "docs/status/index.html" not in readme:
        errors.append("D5 README.md verlinkt docs/status/index.html nicht")

    # D6 Projektstatus gestaged, frisch, commit == HEAD (nur bei nicht-leerem Index)
    if d6_applies(files) and os.environ.get("GUARDIAN_SKIP_D6") != "1":
        sj = "docs/status/status.json"
        if sj not in files:
            errors.append("D6 docs/status/status.json nicht gestaged (status.py --stage im Hook?)")
        else:
            try:
                data = json.loads(staged_text(sj))
                head = sh(["git", "rev-parse", "HEAD"]).strip()
                cf = data.get("commit", "")
                if cf and head and cf != head:
                    errors.append(f"D6 status.json commit={cf[:7]} ≠ HEAD {head[:7]}")
                try:
                    age = (
                        datetime.now() - datetime.fromisoformat(data["generated_at"])
                    ).total_seconds()
                    if age > 600:
                        errors.append(f"D6 status.json ist {int(age // 60)} min alt (>10)")
                except (KeyError, ValueError):
                    errors.append("D6 status.json generated_at unlesbar")
            except json.JSONDecodeError:
                errors.append("D6 status.json ist kein gültiges JSON")

    # D7 Marker aktuell / D8 keine getippten Fakten / D9 Stand-Abschnitt
    md_files = {f: get_text(f) for f in set(tracked) if f.endswith(".md")}
    doc_scope = {
        f: t
        for f, t in md_files.items()
        if f == "README.md" or (f.startswith("docs/") and "/" not in f[len("docs/") :])
    }
    errors += check_doc_facts(doc_scope)
    try:
        import status  # noqa: PLC0415

        errors += check_markers(md_files, status.marker_values())
    except Exception as exc:  # noqa: BLE001
        warn.append(f"D7 status.marker_values nicht auswertbar: {exc}")
    m = re.search(r"## Stand\b.*?<!-- auto:stand -->(.*?)<!-- /auto:stand -->", readme, re.S)
    if not m:
        errors.append("D9 README.md ohne Abschnitt '## Stand' mit auto:stand-Marker")
    elif not m.group(1).strip():
        errors.append("D9 auto:stand-Marker ist leer")

    # D11 jede Datei unter docs/ steht in docs/index.md
    index_md = ROOT / "docs" / "index.md"
    if not index_md.exists():
        errors.append("D11 docs/index.md fehlt")
    else:
        idx = index_md.read_text(encoding="utf-8")
        for p in sorted((ROOT / "docs").rglob("*.md")):
            rel = p.relative_to(ROOT / "docs").as_posix()
            if p.name != "index.md" and rel not in idx:
                errors.append(f"D11 docs/{rel} fehlt in docs/index.md")

    # optional LLM-Konsistenz (manuell)
    if use_llm and src_changed and not errors:
        import cc  # noqa: PLC0415

        diff = sh(["git", "diff", "--cached"])[:30000]
        try:
            r = subprocess.run(
                [
                    "claude",
                    "-p",
                    "Prüfe kontextfrei, ob dieser Diff Aussagen in README.md oder docs/ veraltet macht. "
                    "Antworte nur mit 'OK' oder Liste 'VERALTET: <Datei>: <Aussage>'.\n" + diff,
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
                stdin=subprocess.DEVNULL,
                timeout=600,
                env=cc.env(),
            )
            if "VERALTET" in r.stdout:
                warn.append("LLM-Konsistenz: " + r.stdout.strip()[:800])
        except subprocess.TimeoutExpired:
            warn.append("LLM-Konsistenz: Timeout nach 600s")

    for w in warn:
        print("WARNUNG", w)
    if errors:
        print("GUARDIAN blockiert den Commit:")
        for e in errors:
            print(" -", e)
        return 1
    print("GUARDIAN ok (0 Dateien)" if not files else f"GUARDIAN ok ({len(files)} Dateien geprüft)")
    return 0


if __name__ == "__main__":
    if "--init" in sys.argv:
        (ROOT / ".guardian").mkdir(exist_ok=True)
        (ROOT / ".guardian/decisions.sha256").write_text(
            hashlib.sha256((ROOT / "decisions.yaml").read_bytes()).hexdigest()
        )
        print("decisions.yaml eingefroren")
        sys.exit(0)
    sys.exit(main(use_llm="--llm" in sys.argv))
