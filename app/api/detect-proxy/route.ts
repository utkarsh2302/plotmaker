import { NextRequest, NextResponse } from "next/server";

const PYTHON_URL = process.env.PYTHON_SERVICE_URL ?? "http://127.0.0.1:8001";

// Allow up to 3 minutes — large images take time
export const maxDuration = 180;

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();

    const res = await fetch(`${PYTHON_URL}/detect`, {
      method: "POST",
      body: formData,
      // Node.js fetch doesn't have a built-in timeout; AbortSignal handles it
      signal: AbortSignal.timeout(150_000), // 2.5 min
    });

    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";

    if (msg.includes("ECONNREFUSED") || msg.includes("fetch failed") || msg.includes("ENOTFOUND")) {
      return NextResponse.json(
        {
          detail:
            "Python detection service is not running. Start it with:\n\ncd python-service && uvicorn main:app --port 8001 --reload",
        },
        { status: 503 }
      );
    }

    if (msg.includes("TimeoutError") || msg.includes("AbortError")) {
      return NextResponse.json(
        { detail: "Detection timed out. Try again — large images can take up to 2 minutes." },
        { status: 504 }
      );
    }

    return NextResponse.json({ detail: msg }, { status: 500 });
  }
}
