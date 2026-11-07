import { describe, expect, it } from "vitest";
import type { KnowledgeCard, NodeDetail, NodeEvent } from "@/api/types";
import { mockNodeDetail } from "@/api/mockData";
import { deviceSuggestions } from "@/lib/device-suggestions";

const now = new Date("2026-11-07T20:12:00Z");
const fixture = mockNodeDetail("TRN-031");
if (!fixture) throw new Error("Missing fixture");
const baseCard = fixture.knowledge[0];
if (!baseCard) throw new Error("Missing card");
const card = (changes: Partial<KnowledgeCard>): KnowledgeCard => ({ ...baseCard, ...changes });
const event = (detail: string, timestamp: string, event_type = "alarm_raised"): NodeEvent => ({ event_id: `${detail}-${timestamp}`, detail, timestamp, event_type });
const suggestions = (events: NodeEvent[], knowledge: KnowledgeCard[] = []) => deviceSuggestions({ ...fixture, events, knowledge } as NodeDetail, now);

describe("device suggestions", () => {
  it("builds the TRN-031 acceptance questions", () => {
    expect(deviceSuggestions(fixture, now)).toEqual(["LOS on port 1/1/2 since 13 Feb 08:15: what should I do?", "Traffic counters zero after SFP replacement?", "What are the known issues on TRN-031?"]);
  });
  it("deduplicates alarm details, sorts newest first and limits to two", () => {
    expect(suggestions([event("A", "2026-11-07T08:00:00Z"), event("a", "2026-11-07T09:00:00Z"), event("B", "2026-11-07T10:00:00Z"), event("C", "2026-11-07T07:00:00Z")])).toEqual(["B since 12:00: what should I do?", "a since 11:00: what should I do?", "What are the known issues on TRN-031?"]);
  });
  it("clears only later case-insensitive prefix matching alarms", () => {
    expect(suggestions([event("LOS", "2026-11-07T08:00:00Z"), event("los cleared", "2026-11-07T09:00:00Z", "alarm_cleared")])).toEqual(["What are the known issues on TRN-031?"]);
    expect(suggestions([event("LOS", "2026-11-07T10:00:00Z"), event("LOS cleared", "2026-11-07T09:00:00Z", "alarm_cleared")])[0]).toBe("LOS since 12:00: what should I do?");
  });
  it("uses Helsinki today across midnight and summer time", () => {
    expect(deviceSuggestions({ ...fixture, knowledge: [], events: [event("Alarm", "2026-07-01T21:15:00Z")] }, new Date("2026-07-01T22:00:00Z"))[0]).toBe("Alarm since 00:15: what should I do?");
  });
  it("filters ineligible tips, skips normal symptoms and ranks unique tips", () => {
    expect(suggestions([], [card({ status: "outdated", confidence: 1 }), card({ outcome: "failed", confidence: 1 }), card({ symptoms: ["INTERFACE_UP", "ALARMS_CLEARED"], confidence: 1 }), card({ symptoms: ["CRC_ERRORS"], events: ["PATCH_CABLE_CHANGE"], confidence: 0.8 }), card({ confidence: 0.9 }), card({ confidence: 0.7 }), card({ symptoms: ["LINK_DOWN"], events: [], confidence: 0.6 })])).toEqual(["Traffic counters zero after SFP replacement?", "CRC errors after a patch cable change?", "What are the known issues on TRN-031?"]);
  });
  it("humanises unknown codes and supports tips without events", () => {
    expect(suggestions([], [card({ symptoms: ["CUSTOM_FAULT"], events: [] })])[0]).toBe("custom fault: what should I do?");
  });
  it("places access after tips and never exceeds five", () => {
    const result = suggestions([event("A", "2026-11-07T08:00:00Z"), event("B", "2026-11-07T09:00:00Z")], [card({}), card({ symptoms: ["CELL_DOWN"], events: ["POWER_OUTAGE"] }), card({ knowledge_type: "access_info" })]);
    expect(result).toHaveLength(5);
    expect(result[4]).toBe("How do I get to the TRN-031 site?");
  });
});

describe("device suggestions in Finnish", () => {
  it("builds the TRN-031 acceptance questions in Finnish", () => {
    expect(deviceSuggestions(fixture, now, "fi")).toEqual([
      "LOS on port 1/1/2 13.2. klo 8.15 alkaen: mitä teen?",
      "Liikennelaskurit nollassa SFP-vaihdon jälkeen?",
      "Mitä tunnettuja vikoja laitteella TRN-031 on?",
    ]);
  });
  it("keeps the alarm detail as-is and uses Helsinki time today", () => {
    expect(suggestions([event("LOS", "2026-11-07T08:00:00Z")]).length).toBeGreaterThan(0);
    expect(deviceSuggestions({ ...fixture, knowledge: [], events: [event("LOS", "2026-11-07T08:00:00Z")] }, now, "fi")[0]).toBe("LOS 10.00 alkaen: mitä teen?");
  });
  it("phrases tips without events and access questions in Finnish", () => {
    const result = deviceSuggestions(
      { ...fixture, events: [], knowledge: [card({ symptoms: ["LINK_DOWN"], events: [] }), card({ knowledge_type: "access_info", symptoms: [], events: [] })] } as NodeDetail,
      now,
      "fi",
    );
    expect(result).toEqual([
      "Linkki alhaalla: mitä teen?",
      "Miten pääsen laitteen TRN-031 sijaintiin?",
      "Mitä tunnettuja vikoja laitteella TRN-031 on?",
    ]);
  });
});