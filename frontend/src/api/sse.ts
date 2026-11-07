import type { StreamEvent } from "./types";
import { adaptCards, adaptDone, adaptMeta } from "./adapter";

export interface SseFrame {
  event: string;
  data: string;
}

/** Incremental SSE parser: feed text chunks, get complete frames back. */
export function createSseParser() {
  let buffer = "";
  return {
    push(chunk: string): SseFrame[] {
      buffer += chunk.replace(/\r\n?/g, "\n");
      const frames: SseFrame[] = [];
      let idx: number;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const frame = parseFrame(raw);
        if (frame) frames.push(frame);
      }
      return frames;
    },
    flush(): SseFrame[] {
      const rest = buffer.trim();
      buffer = "";
      const f = rest ? parseFrame(rest) : null;
      return f ? [f] : [];
    },
  };
}

function parseFrame(raw: string): SseFrame | null {
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  if (!data.length && event === "message") return null;
  return { event, data: data.join("\n") };
}

/** Map an SSE frame to a typed stream event. Unknown events return null. */
export function frameToEvent(frame: SseFrame): StreamEvent | null {
  let payload: unknown = frame.data;
  try {
    payload = frame.data ? JSON.parse(frame.data) : {};
  } catch {
    /* plain text data */
  }
  const p = payload as Record<string, unknown>;
  switch (frame.event) {
    case "meta":
      return adaptMeta(payload);
    case "token":
      return { type: "token", text: typeof payload === "string" ? payload : String(p?.["text"] ?? "") };
    case "cards":
      return { type: "cards", cards: adaptCards(Array.isArray(payload) ? payload : p?.["cards"]) };
    case "done":
      return adaptDone(payload);
    case "error":
      return {
        type: "error",
        message: typeof payload === "string" ? payload : String(p?.["message"] ?? "Unknown error"),
      };
    default:
      return null;
  }
}
