/**
 * Next.js Upload API Route
 * =========================
 * Proxies file upload to the FastAPI backend.
 * This route exists to:
 * 1. Keep the backend URL server-side (not exposed in browser)
 * 2. Allow adding server-side auth headers (Clerk JWT) centrally
 * 3. Handle CORS without browser preflight on the file upload
 *
 * Route: POST /api/upload
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();

    // Forward to FastAPI backend
    const backendRes = await fetch(`${BACKEND_URL}/api/v1/contracts/upload`, {
      method: "POST",
      body: formData,
      // Do NOT set Content-Type — let fetch set multipart boundary automatically
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    return NextResponse.json(data, { status: backendRes.status });
  } catch (error) {
    console.error("[upload/route] Error:", error);
    return NextResponse.json(
      { detail: "Upload proxy error. Check that the backend is running." },
      { status: 502 },
    );
  }
}

export const config = {
  api: {
    bodyParser: false, // Disable Next.js body parsing — we pass formData directly
  },
};
