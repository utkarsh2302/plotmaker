"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import {
  MapPin, Undo2, Plus, Trash2, PenLine, CheckCheck, Save, ArrowLeft
} from "lucide-react";
import StepIndicator from "@/components/map-builder/StepIndicator";
import PlotDetailPanel from "@/components/map-builder/PlotDetailPanel";
import type { PlotWithDetails, MapBuilderSession } from "@/lib/types";

// Konva must be client-only
const PlotCanvas = dynamic(() => import("@/components/map-builder/PlotCanvas"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-96 rounded-xl flex items-center justify-center" style={{ background: "#e5e7eb" }}>
      <span className="text-sm" style={{ color: "rgba(0,0,0,0.4)" }}>Loading canvas…</span>
    </div>
  ),
});

type Tool = "select" | "add" | "delete";

export default function VerifyPage() {
  const router = useRouter();
  const [session, setSession] = useState<MapBuilderSession | null>(null);
  const [plots, setPlots] = useState<PlotWithDetails[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [history, setHistory] = useState<PlotWithDetails[][]>([]);
  const [saving, setSaving] = useState(false);

  // Load session from sessionStorage
  useEffect(() => {
    const raw = sessionStorage.getItem("mapBuilder");
    if (!raw) {
      router.push("/admin/map-builder");
      return;
    }
    const data = JSON.parse(raw) as MapBuilderSession;
    setSession(data);
    setPlots(data.plots as PlotWithDetails[]);
  }, [router]);

  function pushHistory(current: PlotWithDetails[]) {
    setHistory((h) => [...h.slice(-19), current]);
  }

  function undo() {
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setPlots(prev);
    setHistory((h) => h.slice(0, -1));
    setSelectedId(null);
  }

  const handleUpdatePlot = useCallback(
    (id: string, changes: Partial<PlotWithDetails>) => {
      setPlots((prev) => {
        pushHistory(prev);
        return prev.map((p) => (p.id === id ? { ...p, ...changes } : p));
      });
    },
    []
  );

  const handleDeletePlot = useCallback(
    (id: string) => {
      setPlots((prev) => {
        pushHistory(prev);
        return prev.filter((p) => p.id !== id);
      });
      setSelectedId(null);
    },
    []
  );

  function handleAddComplete(points: PlotWithDetails["points"]) {
    const newPlot: PlotWithDetails = {
      id: `manual_${Date.now()}`,
      points,
      plot_number: null,
      number_detected: false,
      confidence: 0.5,
      sides: points.length,
      verified: false,
    };
    setPlots((prev) => {
      pushHistory(prev);
      return [...prev, newPlot];
    });
    setSelectedId(newPlot.id);
    setTool("select");
  }

  function handleVerifyAll() {
    setPlots((prev) => {
      pushHistory(prev);
      return prev.map((p) => ({ ...p, verified: true }));
    });
  }

  function handleCanvasSelect(id: string | null) {
    if (tool === "delete" && id) {
      handleDeletePlot(id);
    } else {
      setSelectedId(id);
    }
  }

  function handleSaveAndNext() {
    if (!session) return;
    setSaving(true);

    // Persist updated plots to sessionStorage
    const updated = { ...session, plots };
    sessionStorage.setItem("mapBuilder", JSON.stringify(updated));

    router.push("/admin/map-builder/excel");
  }

  const selectedPlot = plots.find((p) => p.id === selectedId) ?? null;

  const withNumbers = plots.filter((p) => p.number_detected && p.plot_number).length;
  const noNumbers = plots.filter((p) => !p.number_detected || !p.plot_number).length;
  const verified = plots.filter((p) => p.verified).length;

  if (!session) return null;

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "#f5f5f7" }}>
      {/* Header */}
      <div className="border-b shrink-0" style={{ background: "#fff", borderColor: "rgba(0,0,0,0.08)" }}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push("/admin/map-builder")} style={{ color: "rgba(0,0,0,0.45)" }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "#0071e3" }}>
              <MapPin className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base" style={{ color: "#1d1d1f" }}>
                Verify Plots
              </h1>
              <p className="text-xs" style={{ color: "rgba(0,0,0,0.45)" }}>
                {session.projectName}
              </p>
            </div>
          </div>
          <StepIndicator current={2} />
        </div>
      </div>

      {/* Stats bar */}
      <div className="border-b" style={{ background: "#fff", borderColor: "rgba(0,0,0,0.06)" }}>
        <div className="max-w-7xl mx-auto px-6 py-2.5 flex items-center gap-6 flex-wrap">
          <Stat color="#22c55e" label={`${withNumbers} number detected`} icon="✅" />
          <Stat color="#f59e0b" label={`${noNumbers} no number`} icon="⚠️" />
          <Stat color="#6366f1" label={`${verified} verified`} icon="✓" />
          <Stat color="rgba(0,0,0,0.5)" label={`${plots.length} total plots`} icon="#" />
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden max-w-7xl mx-auto w-full px-6 py-4 gap-4">
        {/* Left: canvas area */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          {/* Toolbar */}
          <div className="flex items-center gap-2 flex-wrap">
            <ToolBtn active={tool === "select"} onClick={() => setTool("select")} icon={<PenLine className="w-4 h-4" />} label="Select" />
            <ToolBtn active={tool === "add"} onClick={() => setTool("add")} icon={<Plus className="w-4 h-4" />} label="Add Plot" />
            <ToolBtn active={tool === "delete"} onClick={() => setTool("delete")} icon={<Trash2 className="w-4 h-4" />} label="Delete" danger />
            <div className="w-px h-6 mx-1" style={{ background: "rgba(0,0,0,0.1)" }} />
            <ToolBtn active={false} onClick={undo} icon={<Undo2 className="w-4 h-4" />} label="Undo" disabled={history.length === 0} />
            <ToolBtn active={false} onClick={handleVerifyAll} icon={<CheckCheck className="w-4 h-4" />} label="Verify All" />
            <div className="ml-auto">
              <button
                onClick={handleSaveAndNext}
                disabled={saving || plots.length === 0}
                className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold"
                style={{ background: "#0071e3", color: "#fff" }}
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving…" : "Save & Continue →"}
              </button>
            </div>
          </div>

          {/* Canvas */}
          <PlotCanvas
            imageUrl={session.imageUrl}
            plots={plots}
            selectedId={selectedId}
            onSelect={handleCanvasSelect}
            onUpdatePoints={(id, pts) => handleUpdatePlot(id, { points: pts })}
            addMode={tool === "add"}
            onAddComplete={handleAddComplete}
          />
        </div>

        {/* Right: detail panel */}
        <div
          className="w-72 shrink-0 rounded-2xl overflow-hidden"
          style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)", alignSelf: "flex-start" }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: "rgba(0,0,0,0.06)" }}>
            <h3 className="text-sm font-semibold" style={{ color: "#1d1d1f" }}>Plot Details</h3>
          </div>
          <PlotDetailPanel
            plot={selectedPlot}
            onUpdate={handleUpdatePlot}
            onDelete={handleDeletePlot}
          />
        </div>
      </div>
    </div>
  );
}

function Stat({ color, label, icon }: { color: string; label: string; icon: string }) {
  return (
    <div className="flex items-center gap-1.5 text-sm">
      <span>{icon}</span>
      <span style={{ color, fontWeight: 500 }}>{label}</span>
    </div>
  );
}

function ToolBtn({
  active,
  onClick,
  icon,
  label,
  danger,
  disabled,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
      style={{
        background: active
          ? danger
            ? "rgba(239,68,68,0.12)"
            : "rgba(0,113,227,0.1)"
          : "rgba(0,0,0,0.04)",
        color: active
          ? danger
            ? "#dc2626"
            : "#0071e3"
          : danger
          ? "#dc2626"
          : "rgba(0,0,0,0.62)",
        border: active
          ? danger
            ? "1px solid rgba(239,68,68,0.3)"
            : "1px solid rgba(0,113,227,0.3)"
          : "1px solid transparent",
        opacity: disabled ? 0.4 : 1,
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {icon}
      {label}
    </button>
  );
}
