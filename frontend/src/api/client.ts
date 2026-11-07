import { createSseParser, frameToEvent } from "./sse";
import { adaptChatResponse, adaptFeedback, adaptHealth, adaptNodeDetail, adaptNodes } from "./adapter";
import type { ApiClient, FeedbackResponse } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

export function createRealClient(baseUrl: string): ApiClient {
  const base = baseUrl.replace(/\/+$/, "");

  async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
    const res = await fetch(`${base}${path}`, { signal: signal ?? null, headers: { Accept: "application/json" } });
    if (!res.ok) throw new ApiError(`${path} failed (${res.status})`, res.status);
    return res.json() as Promise<T>;
  }

  return {
    mode: "live",
    health: async (signal) => adaptHealth(await getJson("/api/health", signal)),
    nodes: async (signal) => adaptNodes(await getJson("/api/nodes", signal)),
    node: async (nodeId, signal) => adaptNodeDetail(await getJson(`/api/nodes/${encodeURIComponent(nodeId)}`, signal)),
    stats: (signal) => getJson("/api/stats", signal),
    async feedback(req) {
      const res = await fetch(`${base}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(adaptFeedback(req)),
      });
      if (!res.ok) throw new ApiError(`Feedback failed (${res.status})`, res.status);
      return res.json() as Promise<FeedbackResponse>;
    },
    async chat(req, { onEvent }, signal) {
      const res = await fetch(`${base}/api/chat`, {
        method: "POST",
        signal: signal ?? null,
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream, application/json",
        },
        body: JSON.stringify(req),
      });
      if (!res.ok) throw new ApiError(`Chat failed (${res.status})`, res.status);

      const ctype = res.headers.get("content-type") ?? "";
      // JSON fallback: server doesn't stream.
      if (!ctype.includes("text/event-stream") || !res.body) {
        const data = adaptChatResponse(await res.json());
        onEvent({ type: "meta", conversation_id: data.conversation_id });
        onEvent({ type: "token", text: data.answer });
        onEvent({ type: "cards", cards: data.cards ?? [] });
        onEvent({ type: "done", message_id: data.message_id });
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const parser = createSseParser();
      for (;;) {
        const { value, done } = await reader.read();
        const frames = done ? parser.flush() : parser.push(decoder.decode(value, { stream: true }));
        for (const f of frames) {
          const ev = frameToEvent(f);
          if (ev) onEvent(ev);
        }
        if (done) break;
      }
    },
  };
}
