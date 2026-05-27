"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  MapPin, Upload, Download, CheckCircle2, AlertCircle, Loader2, ArrowLeft, FileSpreadsheet,
} from "lucide-react";
import StepIndicator from "@/components/map-builder/StepIndicator";
import PreviewTable from "@/components/map-builder/PreviewTable";
import { parseExcel, mapExcelToPlots, generateExcelTemplate } from "@/lib/excel-mapper";
import type { MapBuilderSession, MappedPlot, ExcelRow } from "@/lib/types";

type ParseState = "idle" | "parsing" | "done" | "error";
type PublishState = "idle" | "publishing" | "done" | "error";

export default function ExcelPage() {
  const router = useRouter();
  const [session, setSession] = useState<MapBuilderSession | null>(null);
  const [parseState, setParseState] = useState<ParseState>("idle");
  const [publishState, setPublishState] = useState<PublishState>("idle");
  const [mappedPlots, setMappedPlots] = useState<MappedPlot[]>([]);
  const [unmatchedExcel, setUnmatchedExcel] = useState<ExcelRow[]>([]);
  const [errorMsg, setErrorMsg] = useState("");
  const [excelFile, setExcelFile] = useState<File | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem("mapBuilder");
    if (!raw) {
      router.push("/admin/map-builder");
      return;
    }
    setSession(JSON.parse(raw) as MapBuilderSession);
  }, [router]);

  async function handleExcelFile(file: File) {
    setExcelFile(file);
    setParseState("parsing");
    setErrorMsg("");

    try {
      const rows = await parseExcel(file);
      if (!session) return;
      const { mapped, unmatchedExcel: unmatched } = mapExcelToPlots(session.plots as MappedPlot[], rows);
      setMappedPlots(mapped);
      setUnmatchedExcel(unmatched);
      setParseState("done");
    } catch (err) {
      setErrorMsg((err as Error).message);
      setParseState("error");
    }
  }

  async function handlePublish() {
    if (mappedPlots.length === 0) return;
    setPublishState("publishing");

    // Store final data in sessionStorage for a real integration to pick up
    sessionStorage.setItem("publishedMap", JSON.stringify({ mappedPlots, unmatchedExcel }));

    // Simulate a short delay (replace with real Supabase calls)
    await new Promise((r) => setTimeout(r, 1500));

    setPublishState("done");
  }

  const matched = mappedPlots.filter((p) => p.match_status === "matched").length;
  const missingExcel = mappedPlots.filter((p) => p.match_status === "missing_excel").length;

  if (!session) return null;

  if (publishState === "done") {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "#f5f5f7" }}>
        <div
          className="text-center p-12 rounded-3xl max-w-md"
          style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
        >
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-5"
            style={{ background: "rgba(34,197,94,0.1)" }}
          >
            <CheckCircle2 className="w-9 h-9" style={{ color: "#22c55e" }} />
          </div>
          <h2 className="text-xl font-bold mb-2" style={{ color: "#1d1d1f" }}>Map Published!</h2>
          <p className="text-sm mb-6" style={{ color: "rgba(0,0,0,0.55)" }}>
            {matched} plots are now live on{" "}
            <span className="font-semibold">{session.projectName}</span>.
          </p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => router.push("/admin/map-builder")}
              className="px-5 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: "#0071e3", color: "#fff" }}
            >
              Build Another Map
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "#f5f5f7" }}>
      {/* Header */}
      <div className="border-b" style={{ background: "#fff", borderColor: "rgba(0,0,0,0.08)" }}>
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push("/admin/map-builder/verify")} style={{ color: "rgba(0,0,0,0.45)" }}>
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "#0071e3" }}
            >
              <MapPin className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base" style={{ color: "#1d1d1f" }}>
                Excel & Publish
              </h1>
              <p className="text-xs" style={{ color: "rgba(0,0,0,0.45)" }}>
                {session.projectName} · {session.plots.length} plots on map
              </p>
            </div>
          </div>
          <StepIndicator current={3} />
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Template download */}
        <div
          className="rounded-2xl p-6 flex items-center justify-between flex-wrap gap-4"
          style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
        >
          <div>
            <h2 className="font-semibold" style={{ color: "#1d1d1f" }}>
              1. Download Excel Template
            </h2>
            <p className="text-sm mt-1" style={{ color: "rgba(0,0,0,0.45)" }}>
              Fill in plot details: size, price, facing, status, etc.
            </p>
          </div>
          <button
            onClick={generateExcelTemplate}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold"
            style={{ background: "rgba(0,0,0,0.05)", color: "#1d1d1f", border: "1px solid rgba(0,0,0,0.1)" }}
          >
            <Download className="w-4 h-4" />
            Download Template
          </button>
        </div>

        {/* Excel upload */}
        <div
          className="rounded-2xl p-6"
          style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
        >
          <h2 className="font-semibold mb-4" style={{ color: "#1d1d1f" }}>
            2. Upload Filled Excel
          </h2>

          <ExcelDropZone onFile={handleExcelFile} fileName={excelFile?.name} disabled={parseState === "parsing"} />

          {parseState === "parsing" && (
            <div className="flex items-center gap-2 mt-4 text-sm" style={{ color: "rgba(0,0,0,0.5)" }}>
              <Loader2 className="w-4 h-4 animate-spin" />
              Parsing Excel and matching plots…
            </div>
          )}

          {parseState === "error" && (
            <div
              className="flex items-start gap-3 p-4 rounded-xl mt-4"
              style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}
            >
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "#ef4444" }} />
              <p className="text-sm" style={{ color: "#dc2626" }}>{errorMsg}</p>
            </div>
          )}

          {parseState === "done" && (
            <div
              className="flex items-center gap-6 p-4 rounded-xl mt-4 flex-wrap"
              style={{ background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.2)" }}
            >
              <StatPill color="#15803d" label={`${matched} matched`} />
              <StatPill color="#b45309" label={`${missingExcel} missing in Excel`} />
              <StatPill color="#dc2626" label={`${unmatchedExcel.length} in Excel but not on map`} />
            </div>
          )}
        </div>

        {/* Preview table */}
        {parseState === "done" && (
          <div
            className="rounded-2xl p-6"
            style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
          >
            <h2 className="font-semibold mb-4" style={{ color: "#1d1d1f" }}>
              3. Preview & Confirm
            </h2>
            <PreviewTable plots={mappedPlots} unmatchedExcel={unmatchedExcel} />
          </div>
        )}

        {/* Publish */}
        {parseState === "done" && matched > 0 && (
          <div className="flex justify-end pb-8">
            <button
              onClick={handlePublish}
              disabled={publishState === "publishing"}
              className="flex items-center gap-2 px-8 py-3 rounded-xl text-base font-bold transition-all"
              style={{
                background: "#0071e3",
                color: "#fff",
                opacity: publishState === "publishing" ? 0.7 : 1,
              }}
            >
              {publishState === "publishing" ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Publishing…
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-5 h-5" />
                  Publish Map ({matched} plots)
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ExcelDropZone({
  onFile,
  fileName,
  disabled,
}: {
  onFile: (f: File) => void;
  fileName?: string;
  disabled?: boolean;
}) {
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  }

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className="flex flex-col items-center gap-3 py-10 border-2 border-dashed rounded-2xl cursor-pointer transition-all"
      style={{
        borderColor: dragging ? "#0071e3" : "rgba(0,0,0,0.12)",
        background: dragging ? "rgba(0,113,227,0.03)" : "transparent",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center"
        style={{ background: "rgba(34,197,94,0.1)" }}
      >
        <FileSpreadsheet className="w-6 h-6" style={{ color: "#16a34a" }} />
      </div>
      {fileName ? (
        <div className="text-center">
          <p className="text-sm font-semibold" style={{ color: "#1d1d1f" }}>{fileName}</p>
          <p className="text-xs mt-0.5" style={{ color: "rgba(0,0,0,0.4)" }}>Click to change file</p>
        </div>
      ) : (
        <div className="text-center">
          <p className="text-sm font-semibold" style={{ color: "#1d1d1f" }}>Drop Excel file here</p>
          <p className="text-xs mt-0.5" style={{ color: "rgba(0,0,0,0.4)" }}>.xlsx or .xls</p>
        </div>
      )}
      <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handleChange} />
    </label>
  );
}

function StatPill({ color, label }: { color: string; label: string }) {
  return (
    <span className="text-sm font-semibold" style={{ color }}>
      {label}
    </span>
  );
}
