"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MapPin, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import ImageUploader from "@/components/map-builder/ImageUploader";
import StepIndicator from "@/components/map-builder/StepIndicator";
import { detectPlots } from "@/lib/plot-detection";
import type { DetectedPlot } from "@/lib/types";

// Dummy project list — replace with Supabase fetch if needed
const DEMO_PROJECTS = [
  { id: "proj-1", name: "Green Valley Phase 1" },
  { id: "proj-2", name: "Sunrise Township" },
  { id: "proj-3", name: "BrickBay Residences" },
];

type DetectState = "idle" | "detecting" | "done" | "error";

export default function MapBuilderUploadPage() {
  const router = useRouter();
  const [projectId, setProjectId] = useState(DEMO_PROJECTS[0].id);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [detectState, setDetectState] = useState<DetectState>("idle");
  const [detectedPlots, setDetectedPlots] = useState<DetectedPlot[]>([]);
  const [errorMsg, setErrorMsg] = useState("");

  function handleFile(file: File) {
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
    setDetectState("idle");
    setDetectedPlots([]);
  }

  async function handleDetect() {
    if (!imageFile) return;
    setDetectState("detecting");
    setErrorMsg("");

    try {
      const plots = await detectPlots(imageFile);
      setDetectedPlots(plots);
      setDetectState("done");
    } catch (err) {
      setErrorMsg((err as Error).message);
      setDetectState("error");
    }
  }

  function handleProceed() {
    if (!imagePreview || detectedPlots.length === 0) return;

    // Pass data via sessionStorage (lightweight, no server needed for demo)
    sessionStorage.setItem(
      "mapBuilder",
      JSON.stringify({
        projectId,
        projectName: DEMO_PROJECTS.find((p) => p.id === projectId)?.name,
        imageUrl: imagePreview,
        plots: detectedPlots,
      })
    );

    router.push("/admin/map-builder/verify");
  }

  const withNumbers = detectedPlots.filter((p) => p.number_detected).length;
  const withoutNumbers = detectedPlots.length - withNumbers;

  return (
    <div className="min-h-screen" style={{ background: "#f5f5f7" }}>
      {/* Header */}
      <div className="border-b" style={{ background: "#fff", borderColor: "rgba(0,0,0,0.08)" }}>
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center"
              style={{ background: "#0071e3" }}
            >
              <MapPin className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base" style={{ color: "#1d1d1f" }}>
                Auto Plot Map Builder
              </h1>
              <p className="text-xs" style={{ color: "rgba(0,0,0,0.45)" }}>
                Upload → Detect → Verify → Publish
              </p>
            </div>
          </div>
          <StepIndicator current={1} />
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Project selector */}
        <div
          className="rounded-2xl p-6"
          style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
        >
          <h2 className="font-semibold mb-4" style={{ color: "#1d1d1f" }}>
            1. Select Project
          </h2>
          <select
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            className="w-full border rounded-xl px-4 py-2.5 text-sm outline-none"
            style={{
              borderColor: "rgba(0,0,0,0.15)",
              color: "#1d1d1f",
              background: "#fff",
            }}
          >
            {DEMO_PROJECTS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Image upload */}
        <div
          className="rounded-2xl p-6"
          style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
        >
          <h2 className="font-semibold mb-4" style={{ color: "#1d1d1f" }}>
            2. Upload Site Plan
          </h2>

          {imagePreview ? (
            <div className="space-y-4">
              <div className="relative rounded-xl overflow-hidden" style={{ maxHeight: 320 }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={imagePreview}
                  alt="Site plan preview"
                  className="w-full object-contain"
                  style={{ maxHeight: 320, background: "#f5f5f7" }}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm" style={{ color: "rgba(0,0,0,0.55)" }}>
                  {imageFile?.name}
                </span>
                <button
                  onClick={() => {
                    setImageFile(null);
                    setImagePreview(null);
                    setDetectState("idle");
                    setDetectedPlots([]);
                  }}
                  className="text-sm underline"
                  style={{ color: "#0071e3" }}
                >
                  Change image
                </button>
              </div>
            </div>
          ) : (
            <ImageUploader onFile={handleFile} />
          )}
        </div>

        {/* Detect button */}
        {imageFile && (
          <div
            className="rounded-2xl p-6"
            style={{ background: "#fff", border: "1px solid rgba(0,0,0,0.06)" }}
          >
            <h2 className="font-semibold mb-2" style={{ color: "#1d1d1f" }}>
              3. Auto-Detect Plots
            </h2>
            <p className="text-sm mb-5" style={{ color: "rgba(0,0,0,0.45)" }}>
              OpenCV will scan the site plan image and detect all plot boundaries automatically. This takes 10–15 seconds.
            </p>

            {detectState === "error" && (
              <div
                className="flex items-start gap-3 p-4 rounded-xl mb-4"
                style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "#ef4444" }} />
                <div>
                  <p className="text-sm font-medium" style={{ color: "#dc2626" }}>
                    Detection failed
                  </p>
                  <p className="text-sm mt-0.5" style={{ color: "rgba(0,0,0,0.55)" }}>
                    {errorMsg}
                  </p>
                  <p className="text-xs mt-1" style={{ color: "rgba(0,0,0,0.4)" }}>
                    Make sure the Python service is running on port 8001.
                  </p>
                </div>
              </div>
            )}

            {detectState === "done" && (
              <div
                className="flex items-center gap-3 p-4 rounded-xl mb-4"
                style={{ background: "rgba(34,197,94,0.06)", border: "1px solid rgba(34,197,94,0.2)" }}
              >
                <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: "#22c55e" }} />
                <div className="flex-1">
                  <p className="text-sm font-semibold" style={{ color: "#15803d" }}>
                    {detectedPlots.length} plots detected!
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "rgba(0,0,0,0.5)" }}>
                    {withNumbers} with plot numbers · {withoutNumbers} without numbers
                  </p>
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleDetect}
                disabled={detectState === "detecting"}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all"
                style={{
                  background: detectState === "detecting" ? "rgba(0,113,227,0.5)" : "#0071e3",
                  color: "#fff",
                  cursor: detectState === "detecting" ? "not-allowed" : "pointer",
                }}
              >
                {detectState === "detecting" ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Detecting plots…
                  </>
                ) : detectState === "done" ? (
                  "Re-detect"
                ) : (
                  "Detect Plots"
                )}
              </button>

              {detectState === "done" && detectedPlots.length > 0 && (
                <button
                  onClick={handleProceed}
                  className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold"
                  style={{ background: "#1d1d1f", color: "#fff" }}
                >
                  Continue to Verify →
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
