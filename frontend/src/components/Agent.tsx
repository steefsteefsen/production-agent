import { useState } from "react";

interface Investigation {
  thread_id: string;
  state: Record<string, unknown>;
  interrupt?: unknown;
}

export default function Agent() {
  const [lineId, setLineId] = useState("L1");
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [approvalComment, setApprovalComment] = useState("");

  const startInvestigation = async () => {
    setLoading(true);
    setError("");
    try {
      const r = await fetch("/investigations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ line_id: lineId }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setInvestigation(await r.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const approve = async (approved: boolean) => {
    if (!investigation) return;
    setLoading(true);
    try {
      const r = await fetch("/investigations/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: investigation.thread_id,
          approved,
          comment: approvalComment,
          approved_action_titles: [],
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setInvestigation(await r.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const state = investigation?.state ?? {};
  const hasInterrupt = Boolean(investigation?.interrupt);

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Start */}
      <div className="flex gap-3 items-end">
        <div>
          <label className="text-gray-400 text-xs block mb-1">Linie</label>
          <input
            value={lineId}
            onChange={(e) => setLineId(e.target.value)}
            className="w-20 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-teal-600"
          />
        </div>
        <button
          onClick={startInvestigation}
          disabled={loading}
          className="px-4 py-1.5 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm disabled:opacity-50 transition-colors"
        >
          {loading ? "Läuft…" : "Untersuchung starten"}
        </button>
      </div>

      {error && <p className="text-red-400 text-xs">{error}</p>}

      {investigation && (
        <div className="space-y-4">
          <p className="text-gray-500 text-xs">Thread: {investigation.thread_id}</p>

          {/* Hypothese */}
          {!!state.hypotheses && (
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
              <p className="text-gray-400 text-xs mb-2 font-semibold">Hypothesen</p>
              <pre className="text-xs text-gray-300 whitespace-pre-wrap">
                {JSON.stringify(state.hypotheses, null, 2)}
              </pre>
            </div>
          )}

          {/* Maßnahmen */}
          {!!state.actions && (
            <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
              <p className="text-gray-400 text-xs mb-2 font-semibold">Empfohlene Maßnahmen</p>
              <pre className="text-xs text-gray-300 whitespace-pre-wrap">
                {JSON.stringify(state.actions, null, 2)}
              </pre>
            </div>
          )}

          {/* Freigabe-Dialog */}
          {hasInterrupt && (
            <div className="bg-gray-900 rounded-lg border border-wein-600 p-4 space-y-3">
              <p className="text-wein-500 text-xs font-semibold uppercase tracking-wide">
                Freigabe erforderlich
              </p>
              <textarea
                value={approvalComment}
                onChange={(e) => setApprovalComment(e.target.value)}
                placeholder="Kommentar (optional)"
                rows={2}
                className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs focus:outline-none focus:border-teal-600 resize-none"
              />
              <div className="flex gap-3">
                <button
                  onClick={() => approve(true)}
                  disabled={loading}
                  className="px-4 py-1.5 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm disabled:opacity-50"
                >
                  Freigeben
                </button>
                <button
                  onClick={() => approve(false)}
                  disabled={loading}
                  className="px-4 py-1.5 rounded bg-wein-600 hover:bg-wein-500 text-white text-sm disabled:opacity-50"
                >
                  Ablehnen
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
