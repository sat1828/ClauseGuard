/**
 * Next.js Chat API Route — SSE Streaming Proxy
 * ==============================================
 * Proxies the streaming chat response from FastAPI to the browser.
 *
 * Why this exists:
 * - Adds server-side auth (Clerk JWT) without exposing backend URL
 * - Handles SSE content-type headers correctly
 * - Edge runtime for lowest latency (no cold start on Vercel)
 *
 * Route: POST /api/chat?contractId={id}
 */

import { NextRequest } from "next/server";

export const runtime = "edge";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const contractId = searchParams.get("contractId");

  if (!contractId) {
    return new Response(
      JSON.stringify({ detail: "contractId query parameter is required" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  try {
    const body = await request.json();

    const backendRes = await fetch(
      `${BACKEND_URL}/api/v1/chat/${contractId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
    );

    if (!backendRes.ok) {
      const errData = await backendRes.json().catch(() => ({}));
      return new Response(JSON.stringify(errData), {
        status: backendRes.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Stream the SSE response directly to the browser
    return new Response(backendRes.body, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    console.error("[chat/route] Error:", error);
    return new Response(
      JSON.stringify({ detail: "Chat proxy error. Check that the backend is running." }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }
}
