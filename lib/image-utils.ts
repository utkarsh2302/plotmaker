/**
 * Resize an image File using an off-screen canvas.
 * Returns a new File at the target max dimension, preserving aspect ratio.
 * Needed because site-plan images are often 300-500 MB (high-DPI TIF/PNG exports).
 * We keep up to MAX_DETECT_PX wide for OCR accuracy while cutting file size 95%+.
 */

const MAX_DETECT_PX = 5000;   // sent to Python — enough for OCR on dense plans
const MAX_PREVIEW_PX = 1800;  // shown in browser preview

export interface ResizeResult {
  file: File;
  objectUrl: string;
  originalSize: number;  // bytes
  resizedSize: number;   // bytes
  originalW: number;
  originalH: number;
  scale: number;         // resizedW / originalW — useful for coordinate mapping
}

export async function resizeForDetection(source: File): Promise<ResizeResult> {
  return resizeImage(source, MAX_DETECT_PX, 0.92);
}

export async function resizeForPreview(source: File): Promise<ResizeResult> {
  return resizeImage(source, MAX_PREVIEW_PX, 0.88);
}

async function resizeImage(
  source: File,
  maxDim: number,
  quality: number
): Promise<ResizeResult> {
  const bitmap = await createImageBitmap(source);
  const { width: origW, height: origH } = bitmap;

  const scale = Math.min(1, maxDim / Math.max(origW, origH));
  const targetW = Math.round(origW * scale);
  const targetH = Math.round(origH * scale);

  const canvas = new OffscreenCanvas(targetW, targetH);
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(bitmap, 0, 0, targetW, targetH);
  bitmap.close();

  const blob = await canvas.convertToBlob({ type: "image/jpeg", quality });
  const file = new File([blob], source.name.replace(/\.[^.]+$/, ".jpg"), {
    type: "image/jpeg",
  });

  return {
    file,
    objectUrl: URL.createObjectURL(file),
    originalSize: source.size,
    originalW: origW,
    originalH: origH,
    resizedSize: file.size,
    scale,
  };
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}
