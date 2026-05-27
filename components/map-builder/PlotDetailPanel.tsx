"use client";

import type { PlotWithDetails } from "@/lib/types";

interface Props {
  plot: PlotWithDetails | null;
  onUpdate: (id: string, changes: Partial<PlotWithDetails>) => void;
  onDelete: (id: string) => void;
}

export default function PlotDetailPanel({ plot, onUpdate, onDelete }: Props) {
  if (!plot) {
    return (
      <div
        className="h-full flex items-center justify-center p-6 text-center"
        style={{ color: "rgba(0,0,0,0.35)" }}
      >
        <div>
          <div className="text-3xl mb-2">⬅</div>
          <p className="text-sm">Click a plot on the canvas to select it</p>
        </div>
      </div>
    );
  }

  const statusColor = (plot.plot_number && plot.number_detected)
    ? "#22c55e"
    : plot.confidence > 0.5
    ? "#f59e0b"
    : "#ef4444";

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm" style={{ color: "#1d1d1f" }}>
          Selected Plot
        </h3>
        <div
          className="w-2.5 h-2.5 rounded-full"
          style={{ background: statusColor }}
        />
      </div>

      {/* Plot Number */}
      <div>
        <label className="block text-xs font-medium mb-1.5" style={{ color: "rgba(0,0,0,0.55)" }}>
          Plot Number
        </label>
        <input
          type="text"
          value={plot.plot_number ?? ""}
          onChange={(e) =>
            onUpdate(plot.id, {
              plot_number: e.target.value || null,
              number_detected: !!e.target.value,
            })
          }
          placeholder="e.g. A-12"
          className="w-full border rounded-lg px-3 py-2 text-sm outline-none focus:ring-2"
          style={{
            borderColor: "rgba(0,0,0,0.15)",
            background: "#fff",
            color: "#1d1d1f",
            focusRingColor: "#0071e3",
          }}
        />
      </div>

      {/* Confidence */}
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs" style={{ color: "rgba(0,0,0,0.55)" }}>
            Confidence
          </span>
          <span className="text-xs font-semibold" style={{ color: statusColor }}>
            {Math.round(plot.confidence * 100)}%
          </span>
        </div>
        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(0,0,0,0.08)" }}>
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${plot.confidence * 100}%`,
              background: statusColor,
            }}
          />
        </div>
      </div>

      {/* Sides */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg p-3" style={{ background: "rgba(0,0,0,0.03)" }}>
          <div className="text-xs mb-0.5" style={{ color: "rgba(0,0,0,0.45)" }}>Sides</div>
          <div className="font-semibold text-sm">{plot.sides}</div>
        </div>
        <div className="rounded-lg p-3" style={{ background: "rgba(0,0,0,0.03)" }}>
          <div className="text-xs mb-0.5" style={{ color: "rgba(0,0,0,0.45)" }}>Points</div>
          <div className="font-semibold text-sm">{plot.points.length}</div>
        </div>
      </div>

      {/* Verify */}
      <button
        onClick={() => onUpdate(plot.id, { verified: true })}
        disabled={plot.verified}
        className="w-full py-2 rounded-lg text-sm font-semibold transition-all"
        style={{
          background: plot.verified ? "rgba(34,197,94,0.12)" : "#0071e3",
          color: plot.verified ? "#16a34a" : "#fff",
          cursor: plot.verified ? "default" : "pointer",
        }}
      >
        {plot.verified ? "✓ Verified" : "Mark as Verified"}
      </button>

      {/* Delete */}
      <button
        onClick={() => onDelete(plot.id)}
        className="w-full py-2 rounded-lg text-sm font-medium transition-all"
        style={{
          background: "rgba(239,68,68,0.06)",
          color: "#ef4444",
          border: "1px solid rgba(239,68,68,0.2)",
        }}
      >
        Delete Plot
      </button>
    </div>
  );
}
