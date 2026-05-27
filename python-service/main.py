from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from detect import detect_plots, debug_pipeline

app = FastAPI(title="Plot Detection Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/detect")
async def detect(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are accepted")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        plots = detect_plots(image_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")
    return {"total_detected": len(plots), "plots": plots}


@app.post("/debug")
async def debug(file: UploadFile = File(...)):
    """
    Returns step-by-step intermediate images as base64 PNGs.
    Open http://localhost:8001/debug-view to upload and visualise.
    """
    image_bytes = await file.read()
    try:
        result = debug_pipeline(image_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@app.get("/debug-view", response_class=HTMLResponse)
def debug_view():
    """Simple browser UI to upload an image and see each processing step."""
    return """
<!DOCTYPE html>
<html>
<head>
  <title>Detection Debug</title>
  <style>
    body { font-family: sans-serif; background: #111; color: #eee; padding: 24px; }
    h2 { color: #0af; }
    .grid { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 20px; }
    .card { background: #222; border-radius: 12px; padding: 12px; max-width: 480px; }
    .card h4 { margin: 0 0 8px; font-size: 13px; color: #aaa; }
    .card img { width: 100%; border-radius: 8px; }
    input[type=file], button { margin: 8px 4px; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; }
    button { background: #0071e3; color: #fff; }
    #status { margin-top: 12px; color: #0af; }
  </style>
</head>
<body>
  <h2>Plot Detection Debug</h2>
  <input type="file" id="f" accept="image/*">
  <button onclick="run()">Run Debug</button>
  <div id="status"></div>
  <div class="grid" id="out"></div>
  <script>
    async function run() {
      const file = document.getElementById('f').files[0];
      if (!file) return;
      document.getElementById('status').textContent = 'Processing…';
      const fd = new FormData();
      fd.append('file', file);
      const res = await fetch('/debug', { method: 'POST', body: fd });
      const data = await res.json();
      document.getElementById('status').textContent = 'Detected: ' + data.total_detected + ' plots';
      const out = document.getElementById('out');
      out.innerHTML = '';
      const labels = {
        original: 'Original', grayscale: 'Grayscale', enhanced: 'CLAHE Enhanced',
        line_mask: 'Line Mask (what algo thinks are boundaries)',
        thick_lines: 'Thickened Lines (gap closed)',
        plot_areas: 'Plot Areas (inverted)',
        annotated: 'Final — detected plots (green) + numbers (red)'
      };
      for (const [key, label] of Object.entries(labels)) {
        if (!data[key]) continue;
        out.innerHTML += '<div class="card"><h4>' + label + '</h4><img src="data:image/png;base64,' + data[key] + '"></div>';
      }
    }
  </script>
</body>
</html>
"""
