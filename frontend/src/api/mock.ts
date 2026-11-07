import { findScenario, MOCK_NODES, MOCK_STATS, mockNodeDetail, NO_KNOWLEDGE_ANSWER, NO_KNOWLEDGE_ANSWER_FI } from "./mockData";
import { ApiError } from "./client";
import type { ApiClient } from "./types";
import { findDeviceIds } from "@/lib/chat-store";

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
      const named = findDeviceIds(req.message)[0];
      const device = named ?? req.node_id;
      const resolved_nodes = device ? [device] : [];
      const ignored_selection = named && req.node_id && named !== req.node_id ? req.node_id : null;
      const overview = /known issues|all faults|what do we know/i.test(req.message);
      onEvent({ type: "meta", conversation_id, resolved_nodes, ignored_selection,
        resolution_note: null, question_type: overview ? "overview" : "problem" });
      const scenario = findScenario(req.message, device);
      const cards = overview && device ? mockNodeDetail(device)?.knowledge ?? [] : scenario?.cards ?? [];
      const fi = req.ui_language === "fi";
      const noKnowledge = fi ? NO_KNOWLEDGE_ANSWER_FI : NO_KNOWLEDGE_ANSWER;
      const answer = overview
        ? cards.length
          ? fi
            ? `Tunnetut viat laitteella ${device}:`
            : `Known issues on ${device}:`
          : noKnowledge
        : (fi ? scenario?.answerFi : scenario?.answer) ?? noKnowledge;
      for (const chunk of chunkText(answer)) {
        await sleep(20 + Math.random() * 20, signal);
        onEvent({ type: "token", text: chunk });
      }
      onEvent({ type: "cards", cards });
      onEvent({ type: "done", message_id: `msg-${crypto.randomUUID()}` });
    },
  };
}
