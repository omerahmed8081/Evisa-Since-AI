import { afterEach, describe, expect, it, vi } from "vitest";
import { createMockClient } from "@/api/mock";
import { mockNodeDetail } from "@/api/mockData";
import { EXAMPLES_FI } from "@/components/assistant/EmptyState";
import { findScenario } from "@/api/mockData";
import type { ChatRequest, StreamEvent } from "@/api/types";

afterEach(() => vi.useRealTimers());
async function chat(message: string, node_id?: string, ui_language?: ChatRequest["ui_language"]) {
  vi.useFakeTimers();
  const events: StreamEvent[] = [];
  const pending = createMockClient().chat({ message, node_id, ui_language }, { onEvent: (e) => events.push(e) });
  await vi.runAllTimersAsync();
  await pending;
  return events;
}

function answerOf(events: StreamEvent[]): string {
  return events.filter((e) => e.type === "token").map((e) => (e.type === "token" ? e.text : "")).join("");
}
describe("mock resolution", () => {
  it("names the device from the question instead of the selected device", async () => {
    const events = await chat("TRN-077 link up no traffic", "TRN-031");
    expect(events[0]).toMatchObject({ type: "meta", resolved_nodes: ["TRN-077"], ignored_selection: "TRN-031", question_type: "problem" });
  });
  it.each(["What are the known issues on TRN-031?", "all faults on TRN-031", "what do we know about TRN-031"])("returns all observed cards for overview: %s", async (question) => {
    const events = await chat(question);
    expect(events[0]).toMatchObject({ resolved_nodes: ["TRN-031"], question_type: "overview" });
    expect(events.find((e) => e.type === "cards")).toEqual({ type: "cards", cards: mockNodeDetail("TRN-031")?.knowledge });
  });
  it("includes both MW-405 expert cards in overview", async () => {
    const events = await chat("all faults on MW-405");
    const cards = events.find((e) => e.type === "cards");
    expect(cards?.type === "cards" ? cards.cards.map((c) => c.assertion_id) : []).toEqual(["T017-1", "T003-1"]);
  });
});

describe("mock Finnish mode", () => {
  it("routes each Finnish example chip to its scenario", () => {
    expect(EXAMPLES_FI.map((e) => findScenario(e)?.id)).toEqual(["trn031", "bts233", "access", "agg", "mw405"]);
  });
  it("answers the TRN-031 scenario in Finnish when ui_language is fi", async () => {
    const events = await chat("TRN-031: SFP vaihdettu, linkki ylhäällä mutta liikenne ei kulje. Mitä teen?", undefined, "fi");
    const answer = answerOf(events);
    expect(answer).toContain("liikennelaskurit kasvavat");
    expect(answer).not.toContain("forwarding-state issue");
  });
  it("answers in English by default", async () => {
    const events = await chat("TRN-031: SFP replaced, link up but no traffic. What should I do?");
    expect(answerOf(events)).toContain("forwarding-state issue");
  });
});