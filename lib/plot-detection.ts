import type { DetectedPlot } from "./types";

const PYTHON_SERVICE_URL = "/api/detect-proxy";

export async function detectPlots(imageFile: File): Promise<DetectedPlot[]> {
  const formData = new FormData();
  formData.append("file", imageFile);

  const res = await fetch(PYTHON_SERVICE_URL, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail || `Detection failed (${res.status})`);
  }

  const data = await res.json();
  return data.plots as DetectedPlot[];
}
