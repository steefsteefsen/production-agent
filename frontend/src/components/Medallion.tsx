import { useEffect, useState } from "react";

interface Lineage {
  event_id: number;
  reason_code: string;
  packml_state: string;
  start_ts: string;
  end_ts: string | null;
  duration_min: number | null;
  first_alarm_code: string;
  alarm_count: number;
  bronze_ids: string[];
  silver_alarms: Array<{
    alarm_id: number;
    alarm_code: string;
    priority: number;
    severity: number;
    ts: string;
    source_row_id: string;
  }>;
  rules_applied: string[];
}

export default function Medallion() {
  const [eventId, setEventId] = useState(1);
  const [lineage, setLineage] = useState<Lineage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    fetch(`/mes/lineage/${eventId}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setLineage)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [eventId]);

  return (
    <div className="space-y-6">
      {/* Selektor */}
      <div className="flex items-center gap-3">
        <label className="text-gray-400 text-xs">Ereignis-ID</label>
        <input
          type="number"
          min={1}
          value={eventId}
          onChange={(e) => setEventId(Number(e.target.value))}
          className="w-20 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm text-gray-100 focus:outline-none focus:border-teal-600"
        />
      </div>

      {loading && <p className="text-gray-500 text-xs">Lade…</p>}
      {error && <p className="text-red-400 text-xs">Fehler: {error}</p>}

      {lineage && (
        <div className="space-y-4">
          {/* Gold */}
          <div className="rounded-lg border border-amber-800/60 bg-amber-950/20 p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-amber-400 text-xs font-bold uppercase tracking-widest">
                Gold
              </span>
              <span className="text-amber-700 text-xs">Ereignis {lineage.event_id}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
              <span className="text-gray-400">Grund</span>
              <span className="text-gray-100">{lineage.reason_code ?? "–"}</span>
              <span className="text-gray-400">PackML</span>
              <span className="text-gray-100">{lineage.packml_state}</span>
              <span className="text-gray-400">Dauer</span>
              <span className="text-gray-100">
                {lineage.duration_min != null ? `${lineage.duration_min.toFixed(1)} min` : "–"}
              </span>
              <span className="text-gray-400">Erstalarm</span>
              <span className="text-gray-100">{lineage.first_alarm_code}</span>
              <span className="text-gray-400">Alarme</span>
              <span className="text-gray-100">{lineage.alarm_count}</span>
            </div>
          </div>

          {/* Silber – Regel-Chips */}
          <div className="rounded-lg border border-gray-600/60 bg-gray-800/30 p-4">
            <p className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-3">
              Silber – Regelanwendung
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
              {lineage.rules_applied.map((rule, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-full text-xs bg-salbei-700/30 text-salbei-500 border border-salbei-700/40"
                >
                  {rule}
                </span>
              ))}
            </div>
            <p className="text-gray-500 text-xs mb-2">
              {lineage.silver_alarms.length} Alarme in dieser Sequenz
            </p>
            <div className="max-h-40 overflow-y-auto space-y-0.5">
              {lineage.silver_alarms.slice(0, 20).map((a) => (
                <div key={a.alarm_id} className="flex gap-3 text-xs text-gray-400">
                  <span className="w-5 text-gray-500">P{a.priority}</span>
                  <span className="w-14 font-mono text-gray-300">{a.alarm_code}</span>
                  <span className="w-20 text-gray-500">{new Date(a.ts).toLocaleTimeString("de-DE")}</span>
                  <span className="text-gray-600 truncate">{a.source_row_id}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bronze */}
          <div className="rounded-lg border border-orange-900/40 bg-orange-950/10 p-4">
            <p className="text-gray-400 text-xs font-bold uppercase tracking-widest mb-3">
              Bronze – Rohdaten
            </p>
            <p className="text-gray-500 text-xs mb-2">
              {lineage.bronze_ids.length} source_row_ids
            </p>
            <div className="max-h-32 overflow-y-auto space-y-0.5">
              {lineage.bronze_ids.slice(0, 15).map((bid, i) => (
                <span key={i} className="block text-xs text-orange-700/80 font-mono">
                  {bid}
                </span>
              ))}
              {lineage.bronze_ids.length > 15 && (
                <span className="text-gray-600 text-xs">
                  … +{lineage.bronze_ids.length - 15} weitere
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
