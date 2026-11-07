import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptCard, adaptFeedback, adaptHealth, adaptNode, adaptNodeDetail } from "@/api/adapter";
import { createRealClient } from "@/api/client";
import { frameToEvent } from "@/api/sse";
import type { StreamEvent } from "@/api/types";

const source = { thread_id: "thread-7", channel: "feedback", author: "Ari", timestamp: "2026-11-07", excerpt: "Fixed it" };
const node = { node_id: "TRN-077", node_type: "transmission", install_date: "2019-01-01", firmware: "3.4", location: "Helsinki", status: "in_service" };
const card = {
  assertion_id: "E007-1", knowledge_ids: ["E007"], knowledge_type: "device_fact", summary: "Firmware fix",
  actions: ["upgrade_firmware", "check_link"], actions_text: ["Upgrade to 3.4"],
  avoid: ["bounce_port"], avoid_text: [], outcome: "worked", status: "outdated", confidence: 0.9,
  symptom_match: true, how_it_applies: null,
  scope: { node_type: "transmission", installed_before: null, firmware_below: "3.4", firmware_at_least: null },
  scope_text: null, scope_note: null, observed_on: ["TRN-015", "TRN-077"], valid_from: "2026-01-01", valid_to: null,
  details: null, sources: [source], conflicts_with: [], related_failed: [],
};

afterEach(() => vi.unstubAllGlobals());

describe("backend adapter", () => {
  it("maps node_type to type and preserves device facts", () => {
    expect(adaptNode(node)).toEqual({ ...node, type: "transmission", node_type: undefined });
  });
  it("maps action labels and humanises missing labels for actions and avoid", () => {
    expect(adaptCard(card).actions).toEqual([{ code: "upgrade_firmware", text: "Upgrade to 3.4" }, { code: "check_link", text: "check link" }]);
    expect(adaptCard(card).avoid).toEqual([{ code: "bounce_port", text: "bounce port" }]);
  });
  it("maps source identifiers and channels and scope device type", () => {
    const result = adaptCard(card);
    expect(result.sources).toEqual([{ source_id: "thread-7", source_type: "feedback", author: "Ari", timestamp: "2026-11-07", excerpt: "Fixed it" }]);
    expect(result.scope).toEqual({ device_type: "transmission", firmware_below: "3.4" });
    expect(result.status).toBe("outdated");
    expect(result.observed_on).toEqual(["TRN-015", "TRN-077"]);
  });
  it("recursively maps conflicting cards and flattens related failures", () => {
    const result = adaptCard({ ...card, conflicts_with: [{ ...card, assertion_id: "other" }], related_failed: [
      { assertion_id: "failed", summary: "Bounce failed", knowledge_ids: [], actions_text: [], sources: [source] },
      { assertion_id: "empty", summary: "No source", sources: [] },
    ] });
    expect(result.conflicts_with?.[0]?.sources[0]?.source_id).toBe("thread-7");
    expect(result.related_failed).toEqual([
      { assertion_id: "failed", summary: "Bounce failed", author: "Ari", source_type: "feedback", date: "2026-11-07" },
      { assertion_id: "empty", summary: "No source", author: "", source_type: "teams", date: "" },
    ]);
  });
  it("converts optional nulls to undefined in cards, sources and events", () => {
    const result = adaptNodeDetail({ node, knowledge: [{ ...card, sources: [{ ...source, excerpt: null }] }], events: [
      { event_id: "ev1", timestamp: "2026-11-07", event_type: "firmware_upgrade", detail: "Upgraded", from_firmware: null, to_firmware: "3.4", related_thread: null },
    ] });
    expect(result.node.type).toBe("transmission");
    expect(result.knowledge[0]?.details).toBeUndefined();
    expect(result.knowledge[0]?.valid_to).toBeUndefined();
    expect(result.knowledge[0]?.scope_note).toBeUndefined();
    expect(result.knowledge[0]?.sources[0]?.excerpt).toBeUndefined();
    expect(result.events[0]?.from_firmware).toBeUndefined();
    expect(result.events[0]?.related_thread).toBeUndefined();
    expect(result.events[0]?.to_firmware).toBe("3.4");
  });
  it("maps health status exactly", () => {
    expect(adaptHealth({ status: "ok" })).toEqual({ ok: true });
    expect(adaptHealth({ status: "error" })).toEqual({ ok: false });
  });
  it("maps skipped feedback and retains null comments and answer IDs", () => {
    expect(adaptFeedback({ message_id: "answer-7", assertion_id: "E007-1", verdict: "skip", comment: null })).toEqual({
      message_id: "answer-7", assertion_id: "E007-1", verdict: "skipped", comment: null,
    });
    expect(adaptFeedback({ assertion_id: "E007-1", verdict: "worked" }).verdict).toBe("worked");
    expect(adaptFeedback({ assertion_id: "E007-1", verdict: "failed" }).verdict).toBe("failed");
  });
});

describe("live response boundaries", () => {
  it("adapts both streamed card payload forms and preserves meta and done data", () => {
    for (const data of [[card], { cards: [card] }]) {
      expect(frameToEvent({ event: "cards", data: JSON.stringify(data) })).toEqual({ type: "cards", cards: [adaptCard(card)] });
    }
    expect(frameToEvent({ event: "meta", data: JSON.stringify({ conversation_id: "chat-7", resolved_nodes: ["TRN-077"] }) })).toEqual({ type: "meta", conversation_id: "chat-7", resolved_nodes: ["TRN-077"] });
    expect(frameToEvent({ event: "done", data: '{"message_id":"answer-7"}' })).toEqual({ type: "done", message_id: "answer-7" });
  });
  it("adapts REST responses and sends the backend feedback shape", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ status: "ok" }))
      .mockResolvedValueOnce(Response.json([node]))
      .mockResolvedValueOnce(Response.json({ node, knowledge: [card], events: [] }))
      .mockResolvedValueOnce(Response.json({ ok: true, updated: [], comment_queued: false }));
    vi.stubGlobal("fetch", fetcher);
    const client = createRealClient("https://backend.example");
    expect(await client.health()).toEqual({ ok: true });
    expect((await client.nodes())[0]?.type).toBe("transmission");
    expect((await client.node("TRN-077")).knowledge[0]?.actions[0]?.text).toBe("Upgrade to 3.4");
    await client.feedback({ assertion_id: "E007-1", message_id: "answer-7", verdict: "skip", comment: null });
    expect(JSON.parse(fetcher.mock.calls[3]?.[1].body)).toEqual({ assertion_id: "E007-1", message_id: "answer-7", verdict: "skipped", comment: null });
  });
  it("adapts JSON fallback cards and retains the message ID", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ conversation_id: "chat-7", message_id: "answer-7", answer: "Fixed", cards: [card] })));
    const events: StreamEvent[] = [];
    await createRealClient("https://backend.example").chat({ message: "TRN-077" }, { onEvent: e => events.push(e) });
    expect(events).toEqual([{ type: "meta", conversation_id: "chat-7" }, { type: "token", text: "Fixed" }, { type: "cards", cards: [adaptCard(card)] }, { type: "done", message_id: "answer-7" }]);
  });
  it("adapts the real client's SSE flow and retains the message ID", async () => {
    const body = `event: meta\ndata: {"conversation_id":"chat-7"}\n\nevent: cards\ndata: ${JSON.stringify([card])}\n\nevent: done\ndata: {"message_id":"answer-7"}\n\n`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { headers: { "Content-Type": "text/event-stream" } })));
    const events: StreamEvent[] = [];
    await createRealClient("https://backend.example").chat({ message: "TRN-077" }, { onEvent: e => events.push(e) });
    expect(events).toEqual([{ type: "meta", conversation_id: "chat-7" }, { type: "cards", cards: [adaptCard(card)] }, { type: "done", message_id: "answer-7" }]);
  });
});