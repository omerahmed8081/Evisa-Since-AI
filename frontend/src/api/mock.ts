import { findScenario, MOCK_NODES, MOCK_STATS, mockNodeDetail, NO_KNOWLEDGE_ANSWER } from "./mockData";
import { ApiError } from "./client";
import type { ApiClient } from "./types";

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

/** Split text into small word-ish chunks (1–3 words incl. whitespace). */
export function chunkText(text: string): string[] {
  const parts = text.match(/\s*\S+/g) ?? [];
  const out: string[] = [];
  for (let i = 0; i < parts.length; ) {
    const n = 1 + Math.floor(Math.random() * 3);
    out.push(parts.slice(i, i + n).join(""));
    i += n;
  }
  const tail = text.match(/\s+$/)?.[0];
  if (tail) out.push(tail);
  return out;
}

export function createMockClient(): ApiClient {
  return {
    mode: "mock",
    async health() {
      return { ok: true, version: "mock" };
    },
    async nodes(signal) {
      await sleep(150, signal);
      return MOCK_NODES;
    },
    async node(nodeId, signal) {
      await sleep(250, signal);
      const detail = mockNodeDetail(nodeId);
      if (!detail) throw new ApiError(`Unknown device: ${nodeId}`, 404);
      return detail;
    },
    async stats() {
      return { ...MOCK_STATS };
    },
    async feedback(req) {
      await sleep(300);
      MOCK_STATS.feedback += 1;
      return { ok: true, updated: [], comment_queued: req.comment != null && req.comment.length >= 8 };
    },
    async chat(req, { onEvent }, signal) {
      const conversation_id = req.conversation_id ?? `mock-${crypto.randomUUID()}`;
      await sleep(500, signal);
      onEvent({ type: "meta", conversation_id });
      const scenario = findScenario(req.message, req.node_id);
      const answer = scenario?.answer ?? NO_KNOWLEDGE_ANSWER;
      for (const chunk of chunkText(answer)) {
        await sleep(20 + Math.random() * 20, signal);
        onEvent({ type: "token", text: chunk });
      }
      onEvent({ type: "cards", cards: scenario?.cards ?? [] });
      onEvent({ type: "done", message_id: `msg-${crypto.randomUUID()}` });
    },
  };
}
