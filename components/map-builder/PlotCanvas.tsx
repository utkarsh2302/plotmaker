"use client";

import { useEffect, useRef, useState } from "react";
import type { PlotWithDetails } from "@/lib/types";
import {
  pointsToFlatArray,
  polygonCenter,
  getPlotColor,
} from "@/lib/plot-canvas-utils";

// Lazy-import Konva only on client
let Stage: typeof import("react-konva")["Stage"];
let Layer: typeof import("react-konva")["Layer"];
let Image: typeof import("react-konva")["Image"];
let Line: typeof import("react-konva")["Line"];
let Text: typeof import("react-konva")["Text"];
let Circle: typeof import("react-konva")["Circle"];

interface Props {
  imageUrl: string;
  plots: PlotWithDetails[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onUpdatePoints: (id: string, newPoints: PlotWithDetails["points"]) => void;
  addMode?: boolean;
  onAddComplete?: (points: PlotWithDetails["points"]) => void;
}

export default function PlotCanvas({
  imageUrl,
  plots,
  selectedId,
  onSelect,
  onUpdatePoints,
  addMode = false,
  onAddComplete,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasW, setCanvasW] = useState(800);
  const [canvasH, setCanvasH] = useState(600);
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);
  const [konvaLoaded, setKonvaLoaded] = useState(false);
  const [addingPoints, setAddingPoints] = useState<{ x: number; y: number }[]>([]);

  // Load Konva dynamically (SSR-safe)
  useEffect(() => {
    import("react-konva").then((rk) => {
      Stage = rk.Stage;
      Layer = rk.Layer;
      Image = rk.Image;
      Line = rk.Line;
      Text = rk.Text;
      Circle = rk.Circle;
      setKonvaLoaded(true);
    });
  }, []);

  // Load background image
  useEffect(() => {
    const img = new window.Image();
    img.src = imageUrl;
    img.onload = () => {
      setBgImage(img);
      if (containerRef.current) {
        const cw = containerRef.current.clientWidth;
        const ratio = img.naturalHeight / img.naturalWidth;
        setCanvasW(cw);
        setCanvasH(Math.round(cw * ratio));
      }
    };
  }, [imageUrl]);

  // Resize observer
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(() => {
      if (containerRef.current && bgImage) {
        const cw = containerRef.current.clientWidth;
        const ratio = bgImage.naturalHeight / bgImage.naturalWidth;
        setCanvasW(cw);
        setCanvasH(Math.round(cw * ratio));
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, [bgImage]);

  function handleStageClick(e: { target: { getStage: () => { getPointerPosition: () => { x: number; y: number } | null } } }) {
    if (!addMode) return;
    const stage = e.target.getStage();
    const pos = stage?.getPointerPosition();
    if (!pos) return;

    const newPts = [...addingPoints, { x: pos.x, y: pos.y }];
    setAddingPoints(newPts);

    // Close polygon on 3+ points if double-clicking (handled by dblclick)
  }

  function handleStageDblClick() {
    if (!addMode || addingPoints.length < 3) return;
    const normalized = addingPoints.map((p) => ({
      x: p.x / canvasW,
      y: p.y / canvasH,
    }));
    onAddComplete?.(normalized);
    setAddingPoints([]);
  }

  if (!konvaLoaded || !bgImage) {
    return (
      <div ref={containerRef} className="w-full" style={{ minHeight: 400, background: "#f0f0f0" }}>
        <div className="flex items-center justify-center h-96 text-sm" style={{ color: "rgba(0,0,0,0.4)" }}>
          Loading canvas...
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full overflow-hidden rounded-xl" style={{ background: "#000" }}>
      <Stage
        width={canvasW}
        height={canvasH}
        onClick={handleStageClick}
        onDblClick={handleStageDblClick}
        style={{ display: "block", cursor: addMode ? "crosshair" : "default" }}
      >
        <Layer>
          {/* Background image */}
          <Image image={bgImage} width={canvasW} height={canvasH} />

          {/* Plot polygons */}
          {plots.map((plot) => {
            const flatPts = pointsToFlatArray(plot.points, canvasW, canvasH);
            const center = polygonCenter(plot.points, canvasW, canvasH);
            const isSelected = plot.id === selectedId;
            const { fill, stroke } = getPlotColor(plot);

            return (
              <Line
                key={plot.id}
                points={flatPts}
                closed
                fill={fill}
                stroke={isSelected ? "#ff6b00" : stroke}
                strokeWidth={isSelected ? 2.5 : 1.5}
                onClick={(e) => {
                  e.cancelBubble = true;
                  onSelect(plot.id === selectedId ? null : plot.id);
                }}
                onMouseEnter={(e) => {
                  const container = e.target.getStage()?.container();
                  if (container) container.style.cursor = "pointer";
                }}
                onMouseLeave={(e) => {
                  const container = e.target.getStage()?.container();
                  if (container) container.style.cursor = addMode ? "crosshair" : "default";
                }}
              />
            );
          })}

          {/* Labels */}
          {plots.map((plot) => {
            if (!plot.plot_number) return null;
            const center = polygonCenter(plot.points, canvasW, canvasH);
            return (
              <Text
                key={`label-${plot.id}`}
                text={plot.plot_number}
                x={center.x - 18}
                y={center.y - 7}
                width={36}
                align="center"
                fontSize={Math.max(9, Math.min(13, canvasW / 80))}
                fill="#1d1d1f"
                fontStyle="bold"
                listening={false}
              />
            );
          })}

          {/* Add-mode: preview polygon being drawn */}
          {addMode && addingPoints.length > 0 && (
            <>
              <Line
                points={addingPoints.flatMap((p) => [p.x, p.y])}
                stroke="#0071e3"
                strokeWidth={2}
                dash={[6, 3]}
              />
              {addingPoints.map((p, i) => (
                <Circle
                  key={i}
                  x={p.x}
                  y={p.y}
                  radius={4}
                  fill="#0071e3"
                />
              ))}
            </>
          )}
        </Layer>
      </Stage>
      {addMode && (
        <div
          className="text-center py-2 text-xs font-medium"
          style={{ background: "rgba(0,113,227,0.08)", color: "#0071e3" }}
        >
          Click to add points · Double-click to close polygon ({addingPoints.length} points)
        </div>
      )}
    </div>
  );
}
