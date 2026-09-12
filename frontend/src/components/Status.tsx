import { useEffect, useState } from "react";

interface LineStatus {
  line: {
    line_id: string;
    name: string;
    plant: string;
    design_rate_per_hour: number;
    cost_per_downtime_minute_eur: number;
  } | null;
  equipment: Array<{
    equipment_id: string;
    name: string;
    position: number;
    packml_state: string | null;
    ts: string | null;
  }>;
  orders: Array<{
    order_id: string;
    product: string;
    planned_qty: number;
    produced_qty: number;
    due_ts: string;
    priority: number;
  }>;
}

const PACKML_COLOR: Record<string, string> = {
  Execute: "#0d9488",
  Held: "#d97706",
  Stopped: "#7b2d42",
  Suspended: "#b45309",
  Aborted: "#7b2d42",
};

export default function Status() {
  const [status, setStatus] = useState<LineStatus | null>(null);
  const [health, setHealth] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch("/mes/line/L1").then((r) => r.json()),
      fetch("/health").then((r) => r.json()),
    ])
      .then(([s, h]) => {
        setStatus(s);
        setHealth(h);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-400 text-xs">{error}</p>;
  if (!status) return <p className="text-gray-500 text-xs">Lade…</p>;

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Linie */}
      {status.line && (
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
          <p className="text-teal-600 text-xs font-bold uppercase tracking-widest mb-3">Linie</p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
            <span className="text-gray-400">Name</span>
            <span className="text-gray-100">{status.line.name}</span>
            <span className="text-gray-400">Werk</span>
            <span className="text-gray-100">{status.line.plant}</span>
            <span className="text-gray-400">Nennleistung</span>
            <span className="text-gray-100">
              {status.line.design_rate_per_hour.toLocaleString("de-DE")} St/h
            </span>
            <span className="text-gray-400">Stillstandskosten</span>
            <span className="text-gray-100">
              {status.line.cost_per_downtime_minute_eur} €/min
            </span>
          </div>
        </div>
      )}

      {/* Betriebsmittel */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
        <p className="text-teal-600 text-xs font-bold uppercase tracking-widest mb-3">
          Betriebsmittel (PackML)
        </p>
        <div className="space-y-1.5">
          {status.equipment.map((eq) => (
            <div key={eq.equipment_id} className="flex items-center gap-3 text-xs">
              <span className="w-4 text-gray-500">{eq.position}</span>
              <span className="w-32 text-gray-300">{eq.name}</span>
              {eq.packml_state ? (
                <span
                  className="px-2 py-0.5 rounded text-xs font-mono"
                  style={{
                    background: (PACKML_COLOR[eq.packml_state] ?? "#374151") + "33",
                    color: PACKML_COLOR[eq.packml_state] ?? "#9ca3af",
                    border: `1px solid ${(PACKML_COLOR[eq.packml_state] ?? "#374151")}66`,
                  }}
                >
                  {eq.packml_state}
                </span>
              ) : (
                <span className="text-gray-600">–</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Aufträge */}
      {status.orders.length > 0 && (
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
          <p className="text-teal-600 text-xs font-bold uppercase tracking-widest mb-3">
            Aktive Aufträge
          </p>
          <div className="space-y-2">
            {status.orders.map((o) => (
              <div key={o.order_id} className="flex gap-4 text-xs">
                <span className="w-16 font-mono text-gray-300">{o.order_id}</span>
                <span className="flex-1 text-gray-400">{o.product}</span>
                <span className="text-gray-500">
                  {o.produced_qty.toLocaleString("de-DE")} / {o.planned_qty.toLocaleString("de-DE")} St
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Health */}
      {health && (
        <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
          <p className="text-teal-600 text-xs font-bold uppercase tracking-widest mb-3">System</p>
          <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-xs">
            <span className="text-gray-400">API</span>
            <span className={health.ok ? "text-teal-500" : "text-red-400"}>
              {health.ok ? "OK" : "Fehler"}
            </span>
            <span className="text-gray-400">Modell</span>
            <span className="text-gray-100 font-mono">{String(health.model ?? "–")}</span>
            <span className="text-gray-400">Langfuse</span>
            <span className={health.langfuse ? "text-teal-500" : "text-gray-500"}>
              {health.langfuse ? "aktiv" : "inaktiv"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
