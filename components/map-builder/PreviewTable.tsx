"use client";

import type { MappedPlot } from "@/lib/types";

interface Props {
  plots: MappedPlot[];
  unmatchedExcel: { plot_number: string }[];
}

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  matched: { bg: "rgba(34,197,94,0.1)", color: "#15803d", label: "✅ Matched" },
  missing_excel: { bg: "rgba(245,158,11,0.1)", color: "#b45309", label: "⚠️ Missing in Excel" },
  missing_map: { bg: "rgba(239,68,68,0.1)", color: "#dc2626", label: "❌ Missing on Map" },
};

export default function PreviewTable({ plots, unmatchedExcel }: Props) {
  const allRows = [
    ...plots,
    ...unmatchedExcel.map((r) => ({
      id: `unmatched_${r.plot_number}`,
      plot_number: r.plot_number,
      match_status: "missing_map" as const,
      points: [],
      number_detected: false,
      confidence: 0,
      sides: 0,
    })),
  ];

  return (
    <div className="overflow-x-auto rounded-xl border" style={{ borderColor: "rgba(0,0,0,0.08)" }}>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr style={{ background: "rgba(0,0,0,0.03)", borderBottom: "1px solid rgba(0,0,0,0.08)" }}>
            {["Plot #", "Size (sq.yd)", "Price", "Facing", "Type", "Status", "Match"].map((h) => (
              <th key={h} className="px-4 py-3 text-left text-xs font-semibold" style={{ color: "rgba(0,0,0,0.55)" }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {allRows.map((row, i) => {
            const s = STATUS_STYLE[row.match_status];
            return (
              <tr
                key={row.id}
                style={{
                  borderBottom: i < allRows.length - 1 ? "1px solid rgba(0,0,0,0.05)" : "none",
                }}
              >
                <td className="px-4 py-3 font-semibold" style={{ color: "#1d1d1f" }}>
                  {row.plot_number ?? "—"}
                </td>
                <td className="px-4 py-3" style={{ color: "rgba(0,0,0,0.65)" }}>
                  {row.size_sqyd ?? "—"}
                </td>
                <td className="px-4 py-3" style={{ color: "rgba(0,0,0,0.65)" }}>
                  {row.total_price ? `₹${row.total_price.toLocaleString("en-IN")}` : "—"}
                </td>
                <td className="px-4 py-3" style={{ color: "rgba(0,0,0,0.65)" }}>
                  {row.facing ?? "—"}
                </td>
                <td className="px-4 py-3" style={{ color: "rgba(0,0,0,0.65)" }}>
                  {row.plot_type ?? "—"}
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 rounded-md text-xs font-medium capitalize" style={{ background: "rgba(0,0,0,0.05)", color: "rgba(0,0,0,0.6)" }}>
                    {row.status ?? "—"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="px-2 py-0.5 rounded-md text-xs font-medium" style={{ background: s.bg, color: s.color }}>
                    {s.label}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
