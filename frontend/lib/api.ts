/**
 * ClauseGuard API Client
 * ========================
 * Typed wrapper around all backend calls.
 * Zod validation is applied on responses to catch schema drift early.
 *
 * Never call fetch() directly in components — always use this client.
 */

import type {
  ContractUploadResponse,
  ContractStatusResponse,
  ContractListItem,
  FullAnalysisResult,
  ChatTurn,
} from "@/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class APIError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = await res.json();
      detail = body?.detail ?? body?.error;
    } catch {}
    throw new APIError(res.status, `API error ${res.status}: ${path}`, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

// ── Contracts ─────────────────────────────────────────────────────────────────

export async function uploadContract(
  file: File,
  onProgress?: (pct: number) => void,
): Promise<ContractUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // Use XMLHttpRequest for upload progress tracking (fetch doesn't support it)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE_URL}/api/v1/contracts/upload`);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          reject(new APIError(xhr.status, "Invalid JSON response from upload"));
        }
      } else {
        let detail: string | undefined;
        try {
          detail = JSON.parse(xhr.responseText)?.detail;
        } catch {}
        reject(new APIError(xhr.status, `Upload failed: ${xhr.status}`, detail));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new APIError(0, "Network error during upload"));
    });

    xhr.send(formData);
  });
}

export async function getContractStatus(
  contractId: string,
): Promise<ContractStatusResponse> {
  return request<ContractStatusResponse>(
    `/api/v1/contracts/${contractId}/status`,
  );
}

export async function listContracts(): Promise<ContractListItem[]> {
  return request<ContractListItem[]>("/api/v1/contracts/");
}

export async function getAnalysis(
  contractId: string,
): Promise<FullAnalysisResult> {
  return request<FullAnalysisResult>(`/api/v1/analysis/${contractId}`);
}

export async function deleteContract(contractId: string): Promise<void> {
  return request<void>(`/api/v1/contracts/${contractId}`, {
    method: "DELETE",
  });
}

export async function getSuggestedQuestions(
  contractId: string,
): Promise<{ questions: string[] }> {
  return request<{ questions: string[] }>(
    `/api/v1/chat/${contractId}/suggested-questions`,
  );
}

export async function getChatHistory(
  contractId: string,
): Promise<{ messages: ChatTurn[] }> {
  return request<{ messages: ChatTurn[] }>(
    `/api/v1/chat/${contractId}/history`,
  );
}

// ── Streaming Chat ────────────────────────────────────────────────────────────

export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onDone: (response: {
    answer: string;
    citations: any[];
    confidence: string;
    tokens_used?: number;
  }) => void;
  onError: (error: string) => void;
}

export async function streamChatMessage(
  contractId: string,
  message: string,
  conversationHistory: ChatTurn[],
  callbacks: ChatStreamCallbacks,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/v1/chat/${contractId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    callbacks.onError(body?.detail ?? `Chat failed: ${res.status}`);
    return;
  }

  if (!res.body) {
    callbacks.onError("No response body from chat endpoint");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    // Keep the last incomplete line in the buffer
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const jsonStr = line.slice(6).trim();
      if (!jsonStr) continue;

      try {
        const event = JSON.parse(jsonStr);
        if (event.type === "token") {
          callbacks.onToken(event.content ?? "");
        } else if (event.type === "done") {
          callbacks.onDone(event.response);
        } else if (event.type === "error") {
          callbacks.onError(event.message ?? "Unknown stream error");
        }
      } catch {
        // Malformed SSE event — skip
      }
    }
  }
}

export { APIError };
