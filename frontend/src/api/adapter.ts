import type {
  ChatMeta, ChatResponse, FeedbackRequest, Health, KnowledgeCard, KnowledgeScope,
  KnowledgeSource, Node, NodeDetail, NodeEvent, RelatedFailed, StreamEvent,
} from "./types";

type JsonObject = Record<string, unknown>;
const object = (value: unknown): JsonObject =>
  value !== null && typeof value === "object" ? value as JsonObject : {};
const text = (value: unknown): string => typeof value === "string" ? value : "";
const array = (value: unknown): unknown[] => Array.isArray(value) ? value : [];
const strings = (value: unknown): string[] => array(value).filter((v): v is string => typeof v === "string");

/** Optional backend nulls are omitted, so internal optional fields never contain null. */
function optionalText<K extends string>(key: K, value: unknown): Partial<Record<K, string>> {
  return typeof value === "string" ? { [key]: value } as Record<K, string> : {};
}

export function humanise(code: string): string {
  return code.replace(/[_-]+/g, " ");
}

export function adaptSource(value: unknown): KnowledgeSource {
  const s = object(value);
  return {
    source_id: text(s["thread_id"]), source_type: text(s["channel"]) || "teams",
    author: text(s["author"]), timestamp: text(s["timestamp"]),
    ...optionalText("excerpt", s["excerpt"]),
  };
}

function adaptActions(codes: unknown, labels: unknown) {
  const descriptions = array(labels);
  return strings(codes).map((code, i) => ({
    code, text: typeof descriptions[i] === "string" ? descriptions[i] : humanise(code),
  }));
}

function adaptRelatedFailed(value: unknown): RelatedFailed {
  const f = object(value);
  const source = object(array(f["sources"])[0]);
  return {
    assertion_id: text(f["assertion_id"]), summary: text(f["summary"]),
    author: text(source["author"]), source_type: text(source["channel"]) || "teams",
    date: text(source["timestamp"]),
  };
}

export function adaptCard(value: unknown): KnowledgeCard {
  const c = object(value);
  const s = object(c["scope"]);
  const scope: KnowledgeScope = {
    ...(typeof s["node_type"] === "string" ? { device_type: s["node_type"] as NonNullable<KnowledgeScope["device_type"]> } : {}),
    ...optionalText("installed_before", s["installed_before"]),
    ...optionalText("firmware_below", s["firmware_below"]),
    ...optionalText("firmware_at_least", s["firmware_at_least"]),
  };
  return {
    assertion_id: text(c["assertion_id"]), knowledge_ids: strings(c["knowledge_ids"]),
    knowledge_type: text(c["knowledge_type"]),
    status: (text(c["status"]) || "unconfirmed") as KnowledgeCard["status"],
    outcome: (text(c["outcome"]) || "unknown") as KnowledgeCard["outcome"],
    confidence: typeof c["confidence"] === "number" ? c["confidence"] : 0,
    symptoms: strings(c["symptoms"]), events: strings(c["events"]),
    summary: text(c["summary"]), actions: adaptActions(c["actions"], c["actions_text"]),
    avoid: adaptActions(c["avoid"], c["avoid_text"]), scope,
    observed_on: strings(c["observed_on"]), sources: array(c["sources"]).map(adaptSource),
    ...optionalText("details", c["details"]), ...optionalText("scope_text", c["scope_text"]),
    ...optionalText("scope_note", c["scope_note"]), ...optionalText("valid_from", c["valid_from"]),
    ...optionalText("valid_to", c["valid_to"]), ...optionalText("how_it_applies", c["how_it_applies"]),
    ...(Array.isArray(c["conflicts_with"]) ? { conflicts_with: c["conflicts_with"].map(adaptCard) } : {}),
    ...(Array.isArray(c["related_failed"]) ? { related_failed: c["related_failed"].map(adaptRelatedFailed) } : {}),
  };
}

export const adaptCards = (value: unknown): KnowledgeCard[] => array(value).map(adaptCard);

export function adaptNode(value: unknown): Node {
  const n = object(value);
  return {
    node_id: text(n["node_id"]), type: text(n["node_type"]) as Node["type"],
    install_date: text(n["install_date"]), firmware: text(n["firmware"]),
    location: text(n["location"]), status: text(n["status"]) as Node["status"],
  };
}
export const adaptNodes = (value: unknown): Node[] => array(value).map(adaptNode);

export function adaptNodeDetail(value: unknown): NodeDetail {
  const d = object(value);
  return {
    node: adaptNode(d["node"]), knowledge: adaptCards(d["knowledge"]),
    events: array(d["events"]).map((value): NodeEvent => {
      const e = object(value);
      return {
        event_id: text(e["event_id"]), timestamp: text(e["timestamp"]),
        event_type: text(e["event_type"]), detail: text(e["detail"]),
        ...optionalText("from_firmware", e["from_firmware"]),
        ...optionalText("to_firmware", e["to_firmware"]),
        ...optionalText("related_thread", e["related_thread"]),
      };
    }),
  };
}

export function adaptHealth(value: unknown): Health {
  const h = object(value);
  return { ok: h["status"] === "ok", ...optionalText("version", h["version"]) };
}

export function adaptChatResponse(value: unknown): ChatResponse {
  const c = object(value);
  return {
    conversation_id: text(c["conversation_id"]), answer: text(c["answer"]),
    cards: adaptCards(c["cards"]), ...optionalText("message_id", c["message_id"]),
    ...metaFields(c),
  };
}

function metaFields(p: JsonObject): ChatMeta {
  const kind = p["question_type"];
  return {
    resolved_nodes: strings(p["resolved_nodes"]),
    ignored_selection: typeof p["ignored_selection"] === "string" ? p["ignored_selection"] : null,
    resolution_note: typeof p["resolution_note"] === "string" ? p["resolution_note"] : null,
    question_type: kind === "overview" || kind === "history" ? kind : "problem" as const,
  };
}

export function adaptMeta(value: unknown): Extract<StreamEvent, { type: "meta" }> {
  const p = object(value);
  return {
    type: "meta", conversation_id: text(p["conversation_id"]),
    ...metaFields(p),
  };
}

export function adaptDone(value: unknown): Extract<StreamEvent, { type: "done" }> {
  return { type: "done", ...optionalText("message_id", object(value)["message_id"]) };
}

export function adaptFeedback(req: FeedbackRequest) {
  return { ...req, verdict: req.verdict === "skip" ? "skipped" : req.verdict };
}