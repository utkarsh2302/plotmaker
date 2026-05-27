"use client";

import { useRef, useState } from "react";
import { Upload, ImageIcon } from "lucide-react";

interface Props {
  onFile: (file: File) => void;
  disabled?: boolean;
}

export default function ImageUploader({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) onFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className="border-2 border-dashed rounded-2xl p-12 flex flex-col items-center gap-3 cursor-pointer transition-all select-none"
      style={{
        borderColor: dragging ? "#0071e3" : "rgba(0,0,0,0.15)",
        background: dragging ? "rgba(0,113,227,0.04)" : "#fff",
        opacity: disabled ? 0.5 : 1,
        pointerEvents: disabled ? "none" : "auto",
      }}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{ background: "rgba(0,113,227,0.08)" }}
      >
        <ImageIcon className="w-7 h-7" style={{ color: "#0071e3" }} />
      </div>
      <div className="text-center">
        <p className="font-semibold" style={{ color: "#1d1d1f" }}>
          Drop your site plan here
        </p>
        <p className="text-sm mt-1" style={{ color: "rgba(0,0,0,0.45)" }}>
          JPG, PNG supported — or click to browse
        </p>
      </div>
      <div
        className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium"
        style={{ background: "#0071e3", color: "#fff" }}
      >
        <Upload className="w-4 h-4" />
        Browse Files
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleChange}
      />
    </div>
  );
}
