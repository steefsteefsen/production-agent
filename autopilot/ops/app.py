"""Ops-Cockpit: lokale Steuerungsoberfläche für den Orchestrator-Betrieb.

http://localhost:8010 (make ops) – nur 127.0.0.1, Vanilla-JS mit 5-s-Polling.
Tabs: Ablauf (WP-Kacheln), Stand (Kennzahlen + Aktionen), Konfiguration, Präsentation.
Keine Shell-Freitexteingaben; jede Aktion wird ins Audit geschrieben.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

ROOT = Path(__file__).resolve().parent.parent.parent

STATE_PATH = ROOT / "autopilot" / "state" / "orchestrator.json"
PLAN_PATH = ROOT / "autopilot" / "plan.yaml"
STATUS_JSON = ROOT / "docs" / "status" / "status.json"
DECISIONS_YAML = ROOT / "decisions.yaml"
RUNTIME_YAML = ROOT / "config" / "runtime.yaml"
AUDIT_LOG = ROOT / "config" / "ops_audit.jsonl"
ESCALATION_MD = ROOT / "ESCALATION.md"
JOURNAL_DIR = ROOT / "autopilot" / "journal"
LOGS_DIR = ROOT / "autopilot" / "logs"
PRESENTATION_HTML = ROOT / "docs" / "presentation" / "index.html"
ORCHESTRATE_PY = ROOT / "autopilot" / "orchestrate.py"
SYNC_PY = ROOT / "autopilot" / "sync.py"

CONFIGURABLE: frozenset[str] = frozenset(
    {"alarm_prioritaet.verfahren", "audit.personenbezug", "konfidenz.schwelle_empfehlung"}
)

_orch_proc: subprocess.Popen[bytes] | None = None

app = FastAPI(title="Ops-Cockpit", docs_url=None, redoc_url=None)

# ---------------------------------------------------------------------------
# Sicherheit: nur lokaler Zugriff
# ---------------------------------------------------------------------------

_ALLOWED_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "testclient"})


@app.middleware("http")
async def localhost_only(request: Request, call_next: Any) -> Response:
    host = (request.client.host if request.client else None) or ""
    if host and host not in _ALLOWED_HOSTS:
        return JSONResponse({"detail": "Nur lokaler Zugriff erlaubt"}, status_code=403)
    return await call_next(request)


# ---------------------------------------------------------------------------
# HTML-Seite (kein Build-Schritt, Vanilla JS)
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ops-Cockpit – Production Agent</title>
<style>
:root{--teal:#0b4f6c;--teal2:#005a64;--wine:#5d0a1f;--sage:#679881;--bg:#f4f7f8;--txt:#12313c}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--txt);font-size:14px}
header{background:var(--teal);color:#fff;padding:12px 20px;display:flex;justify-content:space-between;align-items:center}
header h1{font-size:17px;font-weight:600}
#orch-badge{font-size:12px;padding:3px 8px;border-radius:10px;background:#fff2;color:#cfe0e4}
nav{background:var(--teal2);display:flex;padding:0 16px;gap:2px}
.tab{background:none;border:0;color:#cfe0e4;padding:10px 14px;cursor:pointer;font-size:13px;border-bottom:2px solid transparent}
.tab.active{background:var(--bg);color:var(--teal);font-weight:600;border-radius:6px 6px 0 0;border-bottom-color:var(--bg)}
.panel{display:none;padding:18px 20px;max-width:1200px;margin:0 auto}
.panel.active{display:block}
h2{font-size:15px;color:var(--teal);margin-bottom:10px;margin-top:16px}
h3{font-size:13px;color:var(--teal2);margin-bottom:6px;margin-top:12px}
.lane{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:10px 14px;margin-bottom:10px}
.lane-header{font-weight:600;color:var(--teal);margin-bottom:8px;font-size:13px}
.pkgs{display:flex;flex-wrap:wrap;gap:8px}
.tile{width:110px;min-height:72px;border-radius:6px;padding:7px 8px;cursor:pointer;color:#fff;font-size:12px;
  transition:opacity .15s;border:2px solid transparent}
.tile:hover{opacity:.85;border-color:#fff4}
.tile strong{display:block;font-size:14px;margin-bottom:2px}
.s-pending{background:#888}
.s-ready{background:var(--sage)}
.s-running{background:var(--teal);animation:pulse 1.5s infinite}
.s-gate_green{background:#2e7d32}
.s-review_pass{background:#558b2f}
.s-merged{background:#1565c0}
.s-exhausted{background:var(--wine)}
.s-escalated{background:#b71c1c}
.s-blocked{background:#e65100}
.s-quota{background:#6a1b9a}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
#detail-panel{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:12px;margin-top:10px;display:none}
#detail-panel h3{color:var(--teal)}
pre.log{background:#1a2a30;color:#cfe0e4;border-radius:6px;padding:10px;font-size:11px;
  line-height:1.5;max-height:280px;overflow-y:auto;white-space:pre-wrap;word-break:break-all}
.journal-entry{background:#fff;border-left:3px solid var(--sage);padding:8px 10px;margin-bottom:6px;border-radius:0 4px 4px 0}
.je-meta{font-size:11px;color:#666;margin-bottom:3px}
.card{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:12px;margin-bottom:8px}
.kpi-row{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
.kpi{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:10px 14px;min-width:130px}
.kpi-val{font-size:22px;font-weight:700;color:var(--teal)}
.kpi-lbl{font-size:11px;color:#666;margin-top:2px}
.escalation-box{background:#fff0f0;border:1px solid #e8cdd0;border-radius:8px;padding:12px;
  max-height:220px;overflow-y:auto;font-size:12px;white-space:pre-wrap;font-family:monospace}
.action-row{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
button.btn{padding:7px 14px;border-radius:5px;border:none;cursor:pointer;font-size:13px;font-weight:500}
.btn-teal{background:var(--teal);color:#fff}.btn-teal:hover{background:var(--teal2)}
.btn-sage{background:var(--sage);color:#fff}.btn-sage:hover{opacity:.85}
.btn-wine{background:var(--wine);color:#fff}.btn-wine:hover{opacity:.85}
.btn-neutral{background:#e0e8ea;color:var(--teal)}.btn-neutral:hover{background:#ccd8db}
.output-box{background:#1a2a30;color:#cfe0e4;border-radius:6px;padding:10px;font-size:11px;
  max-height:200px;overflow-y:auto;white-space:pre-wrap;margin-top:8px;display:none}
input[type=number],input[type=text],select{border:1px solid #bcd;border-radius:4px;padding:5px 8px;font-size:13px}
input[type=range]{width:180px;vertical-align:middle}
.cf-block{background:#fff;border:1px solid #dde5e8;border-radius:8px;padding:12px;margin-bottom:10px}
.cf-label{font-weight:600;color:var(--teal);margin-bottom:4px}
.cf-desc{font-size:11px;color:#666;margin-top:4px}
.cf-row{display:flex;align-items:center;gap:10px;margin-top:6px}
.readonly-hint{font-size:11px;color:#999;font-style:italic}
.constraint-card{background:#f0f7f5;border:1px solid #c2dcd5;border-radius:6px;
  padding:8px 12px;display:inline-flex;flex-direction:column;min-width:160px}
.constraint-name{font-size:11px;color:#555;margin-bottom:2px}
.constraint-val{font-weight:600;color:var(--teal2)}
.constraints-grid{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
pre.decisions{background:#f8fafb;border:1px solid #dde5e8;border-radius:6px;padding:12px;
  font-size:11px;max-height:400px;overflow-y:auto;white-space:pre;font-family:monospace}
.flag-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
#budget-input{width:90px}
#retry-wp,#skip-wp{width:90px}
.toast{position:fixed;bottom:20px;right:20px;background:var(--teal);color:#fff;
  padding:10px 16px;border-radius:6px;font-size:13px;opacity:0;transition:opacity .3s;z-index:99}
.toast.show{opacity:1}
</style>
</head>
<body>
<header>
  <h1>Production Agent – Ops-Cockpit</h1>
  <span id="orch-badge">●  —</span>
</header>
<nav>
  <button class="tab active" onclick="showTab('ablauf')">Ablauf</button>
  <button class="tab" onclick="showTab('stand')">Stand</button>
  <button class="tab" onclick="showTab('config')">Konfiguration</button>
  <button class="tab" onclick="showTab('presentation')">Präsentation</button>
</nav>

<div id="panel-ablauf" class="panel active">
  <h2>Ablauf</h2>
  <div id="lanes-container"><p style="color:#999">Lädt…</p></div>
  <div id="detail-panel">
    <h3 id="detail-title"></h3>
    <div style="margin-top:8px">
      <strong style="font-size:12px">Gate-Ausgabe</strong>
      <pre class="log" id="detail-gate"></pre>
    </div>
    <div style="margin-top:8px" id="detail-review-wrap">
      <strong style="font-size:12px">Reviewer-Urteil</strong>
      <pre class="log" id="detail-review"></pre>
    </div>
    <div id="detail-sync" style="margin-top:8px;font-size:12px"></div>
  </div>
  <h3 style="margin-top:16px">Live-Log</h3>
  <select id="log-wp-sel" onchange="loadLog(this.value)" style="margin-bottom:6px">
    <option value="">– Paket wählen –</option>
  </select>
  <pre class="log" id="log-tail" style="min-height:60px">—</pre>
  <h3 style="margin-top:14px">Journal</h3>
  <div id="journal-entries"><p style="color:#999;font-size:12px">Noch keine Einträge.</p></div>
</div>

<div id="panel-stand" class="panel">
  <h2>Kennzahlen</h2>
  <div class="kpi-row" id="kpi-row"></div>
  <h3>Eskalationen</h3>
  <div class="escalation-box" id="escalation-box">—</div>
  <h2>Aktionen</h2>
  <div class="card">
    <h3>Orchestrator</h3>
    <div class="flag-row">
      <label><input type="checkbox" id="flag-auto-decide"> --auto-decide</label>
      <label><input type="checkbox" id="flag-push"> --push</label>
      <label>Budget $<input type="number" id="budget-input" value="40" min="1" max="999"></label>
    </div>
    <div class="action-row">
      <button class="btn btn-teal" onclick="actionStart()">▶ Starten</button>
      <button class="btn btn-wine" onclick="actionStop()">■ Stoppen (SIGTERM)</button>
      <button class="btn btn-neutral" onclick="actionDryRun()">Dry-Run anzeigen</button>
    </div>
    <div class="output-box" id="dry-run-out"></div>
  </div>
  <div class="card">
    <h3>Paket-Aktionen</h3>
    <div class="action-row" style="align-items:center">
      <input type="text" id="retry-wp" placeholder="WP-ID">
      <button class="btn btn-sage" onclick="actionRetry()">Retry</button>
      <input type="text" id="skip-wp" placeholder="WP-ID">
      <button class="btn btn-neutral" onclick="actionSkip()">Skip (mit Bestätigung)</button>
      <input type="text" id="sync-wp" placeholder="WP-ID">
      <button class="btn btn-neutral" onclick="actionSync()">Sync-Paket erzeugen</button>
    </div>
    <div class="output-box" id="action-out"></div>
  </div>
</div>

<div id="panel-config" class="panel">
  <h2>Konfigurierbare Felder</h2>
  <div id="cf-container"><p style="color:#999">Lädt…</p></div>
  <h2 style="margin-top:18px">Aktive Constraints</h2>
  <div class="constraints-grid" id="constraints-grid"></div>
  <h2 style="margin-top:18px">decisions.yaml (read-only)</h2>
  <p class="readonly-hint">Entscheidungen – Änderung nur über decisions.yaml + GUARDIAN_ALLOW_DECISIONS</p>
  <pre class="decisions" id="decisions-pre">Lädt…</pre>
</div>

<div id="panel-presentation" class="panel" style="padding:0">
  <iframe id="pres-frame" src="/presentation" width="100%" height="680"
    style="border:none;display:block"></iframe>
</div>

<div class="toast" id="toast"></div>

<script>
let _currentTab = 'ablauf';
let _pollingTimer = null;
let _validWPs = [];

// --- Tab-Switching ---
function showTab(name) {
  _currentTab = name;
  document.querySelectorAll('.tab').forEach((t, i) => {
    t.classList.toggle('active', ['ablauf','stand','config','presentation'][i] === name);
  });
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  refresh();
}

// --- Polling ---
async function refresh() {
  updateBadge();
  if (_currentTab === 'ablauf') { await loadState(); await loadJournal(); }
  else if (_currentTab === 'stand') { await loadStatus(); await loadEscalation(); }
  else if (_currentTab === 'config') { await loadConfig(); await loadDecisions(); await loadConstraints(); }
}

function startPolling() {
  if (_pollingTimer) clearInterval(_pollingTimer);
  _pollingTimer = setInterval(refresh, 5000);
  refresh();
}

// --- Badge ---
async function updateBadge() {
  try {
    const r = await fetch('/api/orch-status');
    const d = await r.json();
    const el = document.getElementById('orch-badge');
    el.textContent = d.running ? '● läuft (PID ' + d.pid + ')' : '○  gestoppt';
    el.style.background = d.running ? '#1a7a4a44' : '#fff2';
  } catch(e) {}
}

// --- Ablauf ---
async function loadState() {
  try {
    const r = await fetch('/api/state');
    const data = await r.json();
    _validWPs = [];
    let html = '';
    for (const [lane, info] of Object.entries(data.lanes || {})) {
      html += '<div class="lane"><div class="lane-header">' + lane +
              ' <span style="font-weight:400;color:#555">(' + info.agent + ')</span></div><div class="pkgs">';
      for (const pkg of info.packages) {
        _validWPs.push(pkg.id);
        const ss = stateLabel(pkg.status);
        html += '<div class="tile s-' + pkg.status +
          '" onclick="selectWP(' + JSON.stringify(pkg) + ')" title="' + pkg.status + '">' +
          '<strong>' + pkg.id + '</strong>' + ss +
          (pkg.loops > 0 ? '<br><span style="font-size:10px">×' + pkg.loops + '</span>' : '') +
          (pkg.cost_usd > 0.001 ? '<br><span style="font-size:10px">$' + pkg.cost_usd.toFixed(2) + '</span>' : '') +
          (pkg.started_at ? '<br><span style="font-size:10px">' + fmtTime(pkg.started_at) + '</span>' : '') +
          '</div>';
      }
      html += '</div></div>';
    }
    document.getElementById('lanes-container').innerHTML = html || '<p style="color:#999">Kein State vorhanden.</p>';
    // WP-Selector befüllen
    const sel = document.getElementById('log-wp-sel');
    const cur = sel.value;
    sel.innerHTML = '<option value="">– Paket wählen –</option>' +
      _validWPs.map(w => '<option value="' + w + '"' + (w===cur?' selected':'') + '>' + w + '</option>').join('');
  } catch(e) { console.error(e); }
}

function stateLabel(s) {
  const m = {pending:'ausstehend',ready:'bereit',running:'läuft',gate_green:'Gate ✓',
    review_pass:'Review ✓',merged:'gemergt',exhausted:'erschöpft',escalated:'eskaliert',
    blocked:'blockiert',quota:'Quota'};
  return '<br><span style="font-size:11px">' + (m[s]||s) + '</span>';
}

function fmtTime(ts) {
  if (!ts) return '';
  try { return new Date(ts).toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit'}); }
  catch(e) { return ts.slice(11,16) || ''; }
}

function selectWP(pkg) {
  const dp = document.getElementById('detail-panel');
  dp.style.display = 'block';
  document.getElementById('detail-title').textContent = pkg.id + ' – ' + pkg.status;
  document.getElementById('detail-gate').textContent = pkg.last_gate_tail || '(keine Ausgabe)';
  const rev = pkg.last_review;
  document.getElementById('detail-review').textContent =
    rev ? JSON.stringify(rev, null, 2) : '(kein Reviewer-Urteil)';
  const syncDiv = document.getElementById('detail-sync');
  // kein inline-onclick mit verschachtelten Quotes (bricht im Python-String) – data-Attribut + Handler
  syncDiv.innerHTML = pkg.worktree
    ? '<a href="#" class="sync-link" data-wp="' + pkg.id + '">Sync-Paket für ' + pkg.id + ' erzeugen</a>'
    : '';
  const syncLink = syncDiv.querySelector('.sync-link');
  if (syncLink) syncLink.onclick = function () { actionSyncWP(syncLink.dataset.wp); return false; };
  // Log laden
  document.getElementById('log-wp-sel').value = pkg.id;
  loadLog(pkg.id);
}

async function actionSyncWP(wp) {
  await doAction('/api/actions/sync', {wp});
}

async function loadLog(wp) {
  if (!wp) return;
  try {
    const r = await fetch('/api/log/' + wp);
    const d = await r.json();
    document.getElementById('log-tail').textContent = (d.lines || []).join('\\n') || '(keine Logzeilen)';
  } catch(e) {}
}

async function loadJournal() {
  try {
    const r = await fetch('/api/journal');
    const entries = await r.json();
    const cont = document.getElementById('journal-entries');
    if (!entries.length) { cont.innerHTML = '<p style="color:#999;font-size:12px">Noch keine Einträge.</p>'; return; }
    cont.innerHTML = entries.slice().reverse().slice(0,20).map(e =>
      '<div class="journal-entry"><div class="je-meta">' + (e.wp||'') +
      ' &nbsp;·&nbsp; ' + (e.at ? e.at.slice(0,16).replace('T',' ') : '') +
      ' &nbsp;·&nbsp; ' + (e.ok ? '✅ ok' : '❌ fehler') + '</div>' +
      '<div>' + (e.summary || '').slice(0,200) + '</div></div>'
    ).join('');
  } catch(e) {}
}

// --- Stand ---
async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const pkgs = (d.packages || []);
    const done = pkgs.filter(p => p.state === 'fertig' || p.state === 'merged').length;
    const total = pkgs.length;
    const pct = total ? Math.round(done/total*100) : 0;
    const costs = d.costs || {};
    const qual = d.quality || {};
    document.getElementById('kpi-row').innerHTML = [
      kpi('Pakete', done + ' / ' + total),
      kpi('Fortschritt', pct + ' %'),
      kpi('Coverage', qual.coverage_total != null ? (qual.coverage_total*100).toFixed(0) + ' %' : '—'),
      kpi('Kosten', costs.total != null ? '$' + costs.total.toFixed(2) : '—'),
    ].join('');
  } catch(e) {}
}

function kpi(lbl, val) {
  return '<div class="kpi"><div class="kpi-val">' + val + '</div><div class="kpi-lbl">' + lbl + '</div></div>';
}

async function loadEscalation() {
  try {
    const r = await fetch('/api/escalation');
    const d = await r.json();
    document.getElementById('escalation-box').textContent = d.content || '(keine Eskalationen)';
  } catch(e) {}
}

// --- Stand-Aktionen ---
async function actionDryRun() {
  const box = document.getElementById('dry-run-out');
  box.style.display = 'block';
  box.textContent = 'Lädt…';
  try {
    const r = await fetch('/api/actions/dry-run', {method:'POST'});
    const d = await r.json();
    box.textContent = d.output || '(keine Ausgabe)';
  } catch(e) { box.textContent = 'Fehler: ' + e; }
}

async function actionStart() {
  const body = {
    auto_decide: document.getElementById('flag-auto-decide').checked,
    push: document.getElementById('flag-push').checked,
    budget: parseFloat(document.getElementById('budget-input').value) || 40,
  };
  await doAction('/api/actions/start', body);
  updateBadge();
}

async function actionStop() {
  await doAction('/api/actions/stop', {});
  updateBadge();
}

async function actionRetry() {
  const wp = document.getElementById('retry-wp').value.trim();
  if (!wp) { toast('Bitte WP-ID eingeben'); return; }
  await doAction('/api/actions/retry', {wp});
}

async function actionSkip() {
  const wp = document.getElementById('skip-wp').value.trim();
  if (!wp) { toast('Bitte WP-ID eingeben'); return; }
  if (!confirm('Paket ' + wp + ' als von Hand erledigt markieren?')) return;
  await doAction('/api/actions/skip', {wp});
}

async function actionSync() {
  const wp = document.getElementById('sync-wp').value.trim();
  if (!wp) { toast('Bitte WP-ID eingeben'); return; }
  await doAction('/api/actions/sync', {wp});
}

async function doAction(url, body) {
  const box = document.getElementById('action-out');
  box.style.display = 'block';
  box.textContent = 'Lädt…';
  try {
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)});
    const d = await r.json();
    if (!r.ok) { box.textContent = 'Fehler ' + r.status + ': ' + (d.detail || JSON.stringify(d)); }
    else { box.textContent = d.output || JSON.stringify(d, null, 2); toast(url.split('/').pop() + ' ok'); }
  } catch(e) { box.textContent = 'Fehler: ' + e; }
}

// --- Konfiguration ---
async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    const data = await r.json();
    let html = '';
    for (const [key, cfg] of Object.entries(data)) {
      html += '<div class="cf-block"><div class="cf-label">' + key + '</div>';
      if (cfg.type === 'select') {
        html += '<div class="cf-row"><select id="cf-' + key + '" onchange="">';
        (cfg.options || []).forEach(o => {
          html += '<option value="' + o + '"' + (o===cfg.value?' selected':'') + '>' + o + '</option>';
        });
        html += '</select><button class="btn btn-sage" onclick="saveCf(' + JSON.stringify(key) +
          ',document.getElementById(\\'cf-' + key + '\\').value)">Speichern</button></div>';
        if (cfg.descriptions && cfg.value && cfg.descriptions[cfg.value]) {
          html += '<div class="cf-desc">' + cfg.descriptions[cfg.value] + '</div>';
        }
      } else if (cfg.type === 'slider') {
        html += '<div class="cf-row">' +
          '<input type="range" id="cf-' + key + '" min="' + cfg.min + '" max="' + cfg.max +
          '" step="' + cfg.step + '" value="' + cfg.value + '" ' +
          'oninput="document.getElementById(\\'cf-' + key + '-val\\').textContent=this.value">' +
          '<span id="cf-' + key + '-val">' + cfg.value + '</span>' +
          '<button class="btn btn-sage" onclick="saveCf(' + JSON.stringify(key) +
          ',parseFloat(document.getElementById(\\'cf-' + key + '\\').value))">Speichern</button></div>';
        if (cfg.begruendung) html += '<div class="cf-desc">' + cfg.begruendung + '</div>';
      }
      html += '</div>';
    }
    document.getElementById('cf-container').innerHTML = html || '<p style="color:#999">Keine konfigurierbaren Felder gefunden.</p>';
  } catch(e) { console.error(e); }
}

async function saveCf(field, value) {
  try {
    const r = await fetch('/api/config', {method:'PUT',
      headers:{'Content-Type':'application/json'}, body: JSON.stringify({field, value})});
    const d = await r.json();
    if (!r.ok) toast('Fehler: ' + (d.detail || r.status), true);
    else { toast('Gespeichert: ' + field + ' = ' + value); loadConstraints(); }
  } catch(e) { toast('Fehler: ' + e, true); }
}

async function loadDecisions() {
  try {
    const r = await fetch('/api/decisions');
    const d = await r.json();
    document.getElementById('decisions-pre').textContent = d.content || '(nicht vorhanden)';
  } catch(e) {}
}

async function loadConstraints() {
  try {
    const r = await fetch('/api/constraints');
    const items = await r.json();
    document.getElementById('constraints-grid').innerHTML = items.map(c =>
      '<div class="constraint-card"><div class="constraint-name">' + c.name + '</div>' +
      '<div class="constraint-val">' + c.value + '</div></div>'
    ).join('');
  } catch(e) {}
}

// --- Toast ---
function toast(msg, err) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.background = err ? '#b71c1c' : 'var(--teal)';
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);
}

startPolling();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(_HTML)


@app.get("/presentation", response_class=HTMLResponse)
async def presentation() -> HTMLResponse:
    if PRESENTATION_HTML.exists():
        return HTMLResponse(PRESENTATION_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<html><body><p>Keine Präsentation vorhanden.</p></body></html>")


# ---------------------------------------------------------------------------
# API: Zustand
# ---------------------------------------------------------------------------


@app.get("/api/state")
async def api_state() -> JSONResponse:
    plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    state: dict = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}
    wp_state = state.get("wp", {})
    lanes: dict[str, dict] = {}
    for pkg in plan["packages"]:
        lane = pkg["lane"]
        pid = pkg["id"]
        w = wp_state.get(
            pid,
            {
                "status": "pending",
                "loops": 0,
                "cost_usd": 0.0,
                "started_at": None,
                "finished_at": None,
                "last_gate_tail": "",
                "last_review": None,
                "worktree": None,
            },
        )
        lanes.setdefault(lane, {"agent": plan["lanes"][lane]["agent"], "packages": []})
        lanes[lane]["packages"].append(
            {
                "id": pid,
                "status": w.get("status", "pending"),
                "loops": w.get("loops", 0),
                "cost_usd": w.get("cost_usd", 0.0),
                "started_at": w.get("started_at"),
                "finished_at": w.get("finished_at"),
                "last_gate_tail": w.get("last_gate_tail", ""),
                "last_review": w.get("last_review"),
                "worktree": w.get("worktree"),
            }
        )
    return JSONResponse(
        {
            "lanes": lanes,
            "budget_used": state.get("budget_used", 0.0),
            "budget_total": state.get("budget_total", 40.0),
        }
    )


@app.get("/api/status")
async def api_status() -> JSONResponse:
    if STATUS_JSON.exists():
        return JSONResponse(json.loads(STATUS_JSON.read_text(encoding="utf-8")))
    return JSONResponse({})


@app.get("/api/orch-status")
async def api_orch_status() -> JSONResponse:
    running = _orch_proc is not None and _orch_proc.poll() is None
    return JSONResponse({"running": running, "pid": _orch_proc.pid if running else None})


@app.get("/api/log/{wp}")
async def api_log(wp: str) -> JSONResponse:
    plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    valid = {p["id"] for p in plan["packages"]}
    if wp not in valid:
        raise HTTPException(status_code=404, detail=f"Unbekanntes Paket: {wp}")
    log_file = LOGS_DIR / f"orch-{wp}.log"
    if not log_file.exists():
        return JSONResponse({"lines": []})
    lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return JSONResponse({"lines": lines[-40:]})


@app.get("/api/journal")
async def api_journal() -> JSONResponse:
    entries: list[dict] = []
    if JOURNAL_DIR.exists():
        for p in sorted(JOURNAL_DIR.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            entries.extend(data if isinstance(data, list) else [data])
    return JSONResponse(entries)


@app.get("/api/escalation")
async def api_escalation() -> JSONResponse:
    if ESCALATION_MD.exists():
        return JSONResponse({"content": ESCALATION_MD.read_text(encoding="utf-8")})
    return JSONResponse({"content": ""})


@app.get("/api/decisions")
async def api_decisions() -> JSONResponse:
    return JSONResponse({"content": DECISIONS_YAML.read_text(encoding="utf-8")})


# ---------------------------------------------------------------------------
# API: Konfiguration
# ---------------------------------------------------------------------------


def _get_nested(d: dict, key: str) -> object:
    for part in key.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)  # type: ignore[assignment]
    return d


def _set_nested(d: dict, key: str, value: object) -> None:
    parts = key.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


@app.get("/api/config")
async def api_config() -> JSONResponse:
    decisions = yaml.safe_load(DECISIONS_YAML.read_text(encoding="utf-8"))
    runtime: dict = (
        yaml.safe_load(RUNTIME_YAML.read_text(encoding="utf-8")) or {}
        if RUNTIME_YAML.exists()
        else {}
    )
    ap = decisions.get("alarm_prioritaet", {})
    aud = decisions.get("audit", {})
    konf = decisions.get("konfidenz", {})
    result = {
        "alarm_prioritaet.verfahren": {
            "value": (runtime.get("alarm_prioritaet") or {}).get("verfahren")
            or ap.get("verfahren"),
            "options": list(ap.get("verfahren_optionen", {}).keys()),
            "descriptions": ap.get("verfahren_optionen", {}),
            "configurable": True,
            "type": "select",
        },
        "audit.personenbezug": {
            "value": (runtime.get("audit") or {}).get("personenbezug") or aud.get("personenbezug"),
            "options": list(aud.get("personenbezug_optionen", {}).keys()),
            "descriptions": aud.get("personenbezug_optionen", {}),
            "configurable": True,
            "type": "select",
        },
        "konfidenz.schwelle_empfehlung": {
            "value": (runtime.get("konfidenz") or {}).get("schwelle_empfehlung")
            or konf.get("schwelle_empfehlung"),
            "min": 0.0,
            "max": 1.0,
            "step": 0.05,
            "configurable": True,
            "type": "slider",
            "begruendung": konf.get("begruendung", ""),
        },
    }
    return JSONResponse(result)


@app.put("/api/config")
async def put_config(request: Request) -> JSONResponse:
    body = await request.json()
    field: str = body.get("field", "")
    value = body.get("value")
    if field not in CONFIGURABLE:
        raise HTTPException(
            status_code=403,
            detail=f"Feld '{field}' ist nicht konfigurierbar – "
            "Änderung nur über decisions.yaml + GUARDIAN_ALLOW_DECISIONS",
        )
    runtime: dict = (
        yaml.safe_load(RUNTIME_YAML.read_text(encoding="utf-8")) or {}
        if RUNTIME_YAML.exists()
        else {}
    )
    old_value = _get_nested(runtime, field)
    _set_nested(runtime, field, value)
    RUNTIME_YAML.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_YAML.write_text(
        yaml.dump(runtime, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    audit_entry = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "field": field,
        "old": old_value,
        "new": value,
        "role": "Stefan",
    }
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    return JSONResponse({"ok": True, "field": field, "old": old_value, "new": value})


@app.get("/api/constraints")
async def api_constraints() -> JSONResponse:
    decisions = yaml.safe_load(DECISIONS_YAML.read_text(encoding="utf-8"))
    runtime: dict = (
        yaml.safe_load(RUNTIME_YAML.read_text(encoding="utf-8")) or {}
        if RUNTIME_YAML.exists()
        else {}
    )
    konf_schwelle = (runtime.get("konfidenz") or {}).get("schwelle_empfehlung") or decisions.get(
        "konfidenz", {}
    ).get("schwelle_empfehlung")
    ap_verfahren = (runtime.get("alarm_prioritaet") or {}).get("verfahren") or decisions.get(
        "alarm_prioritaet", {}
    ).get("verfahren")
    aud_pz = (runtime.get("audit") or {}).get("personenbezug") or decisions.get("audit", {}).get(
        "personenbezug"
    )
    er = decisions.get("ereignis", {})
    fr = decisions.get("freigabe", {})
    return JSONResponse(
        [
            {"name": "Erstalarmdetektion", "value": f"±{er.get('erstalarm_fenster_s', '?')} s"},
            {
                "name": "Kurzstillstand-Grenze",
                "value": f"< {er.get('kurzstillstand_min', '?')} min",
            },
            {
                "name": "Alarmflut",
                "value": f"{er.get('alarmflut_alarme', '?')} Alarme / {er.get('alarmflut_fenster_min', '?')} min",
            },
            {"name": "Konfidenz-Schwelle", "value": str(konf_schwelle)},
            {"name": "Prioritätsverfahren", "value": str(ap_verfahren)},
            {"name": "Personenbezug (Audit)", "value": str(aud_pz)},
            {
                "name": "Vier-Augen ab",
                "value": f"{fr.get('vier_augen_ab_kosten_eur', '?')} €",
            },
            {"name": "Freigabe-Timeout", "value": f"{fr.get('timeout_min', '?')} min"},
        ]
    )


# ---------------------------------------------------------------------------
# API: Aktionen (nur benannte, feste Subprozess-Aufrufe)
# ---------------------------------------------------------------------------


def _validate_wp(wp: str | None) -> None:
    plan = yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))
    valid = {p["id"] for p in plan["packages"]}
    if wp not in valid:
        raise HTTPException(status_code=404, detail=f"Unbekanntes Paket: {wp}")


def _audit(action: str, params: dict) -> None:
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, **params}
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.post("/api/actions/dry-run")
async def action_dry_run() -> JSONResponse:
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(ORCHESTRATE_PY), "--dry-run"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    _audit("dry-run", {})
    return JSONResponse({"output": r.stdout + r.stderr, "returncode": r.returncode})


@app.post("/api/actions/start")
async def action_start(request: Request) -> JSONResponse:
    global _orch_proc  # noqa: PLW0603
    if _orch_proc and _orch_proc.poll() is None:
        return JSONResponse({"ok": False, "detail": "Orchestrator läuft bereits"}, status_code=409)
    body = await request.json()
    flags: list[str] = []
    if body.get("auto_decide"):
        flags += ["--auto-decide"]
    if body.get("push"):
        flags += ["--push"]
    if body.get("budget"):
        flags += ["--budget-total-usd", str(float(body["budget"]))]
    _orch_proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(ORCHESTRATE_PY)] + flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _audit("start", {"flags": flags, "pid": _orch_proc.pid})
    return JSONResponse({"ok": True, "pid": _orch_proc.pid})


@app.post("/api/actions/stop")
async def action_stop() -> JSONResponse:
    global _orch_proc  # noqa: PLW0603
    if not _orch_proc or _orch_proc.poll() is not None:
        return JSONResponse({"ok": False, "detail": "Kein laufender Orchestrator"}, status_code=409)
    _orch_proc.send_signal(signal.SIGTERM)
    _audit("stop", {})
    return JSONResponse({"ok": True})


@app.post("/api/actions/retry")
async def action_retry(request: Request) -> JSONResponse:
    body = await request.json()
    wp: str = body.get("wp", "")
    _validate_wp(wp)
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(ORCHESTRATE_PY), "--retry", wp],
        capture_output=True,
        text=True,
        timeout=10,
    )
    _audit("retry", {"wp": wp})
    return JSONResponse({"ok": r.returncode == 0, "output": r.stdout + r.stderr})


@app.post("/api/actions/skip")
async def action_skip(request: Request) -> JSONResponse:
    body = await request.json()
    wp: str = body.get("wp", "")
    _validate_wp(wp)
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(ORCHESTRATE_PY), "--skip", wp, "--yes"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    _audit("skip", {"wp": wp})
    return JSONResponse({"ok": r.returncode == 0, "output": r.stdout + r.stderr})


@app.post("/api/actions/sync")
async def action_sync(request: Request) -> JSONResponse:
    body = await request.json()
    wp: str = body.get("wp", "")
    _validate_wp(wp)
    r = subprocess.run(  # noqa: S603
        [sys.executable, str(SYNC_PY), wp],
        capture_output=True,
        text=True,
        timeout=60,
    )
    _audit("sync", {"wp": wp})
    return JSONResponse({"ok": r.returncode == 0, "output": r.stdout + r.stderr})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8010)
