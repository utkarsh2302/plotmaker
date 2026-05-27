import { NextRequest, NextResponse } from "next/server";

const PYTHON_URL = process.env.PYTHON_SERVICE_URL ?? "http://127.0.0.1:8001";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();

    const res = await fetch(`${PYTHON_URL}/detect`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    // Connection refused means Python service is not running
    if (msg.includes("ECONNREFUSED") || msg.includes("fetch failed")) {
      return NextResponse.json(
        {
          detail:
            "Python detection service is not running. Start it with: cd python-service && uvicorn main:app --port 8001 --reload",
        },
        { status: 503 }
      );
    }
    return NextResponse.json({ detail: msg }, { status: 500 });
  }
}
