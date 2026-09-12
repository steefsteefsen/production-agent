import { useEffect, useRef, useState } from "react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";

interface AlarmEvent {
  alarm_id: string;
  alarm_code: string;
  severity: number;
  priority: number;
  message: string;
  ts: string;
  topic: string;
  active: boolean;
}

const PRIO_COLOR: Record<number, string> = {
  1: "#7b2d42", // Wein – Sicherheit
  2: "#d97706", // Amber
  3: "#ca8a04", // Yellow
  4: "#7a9e7e", // Salbei – Info
};

const PRIO_LABEL: Record<number, string> = {
  1: "Prio 1 – Sicherheit",
  2: "Prio 2 – Dringend",
  3: "Prio 3 – Normal",
  4: "Prio 4 – Hinweis",
};

export default function LiveMES() {
  const [events, setEvents] = useState<AlarmEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource("/mes/stream?speed=120");
    esRef.current = es;
    es.onopen = () => setConnected(true);
    es.onmessage = (e) => {
      const ev: AlarmEvent = JSON.parse(e.data);
      setEvents((prev) => [...prev.slice(-199), ev]);
    };
    es.onerror = () => setConnected(false);
    return () => es.close();
  }, []);

  const chartData = events.map((e, i) => ({
    index: i,
    severity: e.severity,
    priority: e.priority,
    code: e.alarm_code,
  }));

  return (
    <div className="space-y-6">
      {/* Status-Zeile */}
      <div className="flex items-center gap-3">
        <span
          className={[
            "inline-block w-2 h-2 rounded-full",
            connected ? "bg-teal-600 animate-pulse" : "bg-gray-500",
          ].join(" ")}
        />
        <span className="text-gray-400 text-xs">
          {connected ? "SSE verbunden – Demo-Ereignis" : "Verbindungsaufbau…"}
        </span>
        <span className="ml-auto text-gray-500 text-xs">{events.length} Alarme</span>
      </div>

      {/* Severity-Chart */}
      {events.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
          <p className="text-gray-400 text-xs mb-3">Severity-Verlauf (OPC-UA 1–1000)</p>
          <ResponsiveContainer width="100%" height={140}>
            <ScatterChart>
              <XAxis dataKey="index" hide />
              <YAxis dataKey="severity" domain={[0, 1000]} width={35} tick={{ fontSize: 10 }} />
              <Tooltip
                content={({ payload }) =>
                  payload?.[0] ? (
                    <div className="bg-gray-800 border border-gray-600 rounded p-2 text-xs">
                      <p>{payload[0].payload.code}</p>
                      <p>Sev {payload[0].payload.severity}</p>
                    </div>
                  ) : null
                }
              />
              <Scatter data={chartData}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={PRIO_COLOR[d.priority] ?? "#6b7280"} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Alarm-Liste */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
        <div className="px-4 py-2 border-b border-gray-700 flex gap-4 text-xs text-gray-500">
          <span className="w-24">Zeit</span>
          <span className="w-16">Code</span>
          <span className="w-8">Prio</span>
          <span className="w-12">Sev</span>
          <span>Meldung</span>
        </div>
        <div className="max-h-96 overflow-y-auto">
          {events.length === 0 && (
            <p className="px-4 py-8 text-center text-gray-600 text-xs">
              Warte auf Alarmstrom…
            </p>
          )}
          {[...events].reverse().map((ev, i) => (
            <div
              key={ev.alarm_id + i}
              className="px-4 py-1.5 flex gap-4 text-xs border-b border-gray-800 hover:bg-gray-800/50"
            >
              <span className="w-24 text-gray-500 shrink-0">
                {new Date(ev.ts).toLocaleTimeString("de-DE")}
              </span>
              <span
                className="w-16 font-mono shrink-0"
                style={{ color: PRIO_COLOR[ev.priority] ?? "#9ca3af" }}
              >
                {ev.alarm_code}
              </span>
              <span
                className="w-8 shrink-0 font-bold"
                style={{ color: PRIO_COLOR[ev.priority] ?? "#9ca3af" }}
              >
                P{ev.priority}
              </span>
              <span className="w-12 text-gray-400 shrink-0">{ev.severity}</span>
              <span className="text-gray-300 truncate">{ev.message}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Legende */}
      <div className="flex gap-4 text-xs">
        {Object.entries(PRIO_LABEL).map(([p, label]) => (
          <span key={p} className="flex items-center gap-1">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: PRIO_COLOR[Number(p)] }}
            />
            <span className="text-gray-400">{label}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
