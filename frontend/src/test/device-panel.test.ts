import { describe, expect, it } from "vitest";
import { createMockClient } from "@/api/mock";
import { findScenario, mockNodeDetail, MOCK_STATS } from "@/api/mockData";

describe("mock node detail", () => {
  it("TRN-031 has facts, knowledge and 5 timeline events", () => {
    const d = mockNodeDetail("TRN-031");
    expect(d).not.toBeNull();
    expect(d!.node.node_id).toBe("TRN-031");
    expect(d!.knowledge.map((c) => c.assertion_id)).toEqual(["T001-1"]);
    expect(d!.events).toHaveLength(5);
    // newest first
    expect(d!.events[0]!.timestamp > d!.events.at(-1)!.timestamp).toBe(true);
  });

  it("TRN-077 shows the bounce fix as outdated with the not-needed note", () => {
    const d = mockNodeDetail("TRN-077")!;
    const bounce = d.knowledge.find((c) => c.assertion_id === "T001-1");
    expect(bounce?.status).toBe("outdated");
    expect(bounce?.scope_note).toBe(
      "Not needed on TRN-077: only applies below firmware 3.4, device has 3.4.0",
    );
    // Firmware 3.4 is installed here, so the "not yet" note does not apply.
    const fw = d.knowledge.find((c) => c.assertion_id === "E007-1");
    expect(fw?.scope_note).toBeUndefined();
    const up = d.events.find((e) => e.event_type === "firmware_upgrade");
    expect(up?.from_firmware).toBe("3.2.1");
    expect(up?.to_firmware).toBe("3.4.0");
  });

  it("the firmware 3.4 card is observed on the upgraded units only", () => {
    const fw = findScenario("TRN-031 no traffic")!.cards.find((c) => c.assertion_id === "E007-1");
    expect(fw?.observed_on).toEqual(["TRN-015", "TRN-077"]);
    expect(mockNodeDetail("TRN-015")!.knowledge.map((c) => c.assertion_id)).toContain("E007-1");
    expect(mockNodeDetail("TRN-042")!.knowledge.map((c) => c.assertion_id)).not.toContain("E007-1");
  });

  it("devices below firmware 3.4 keep the bounce fix active", () => {
    const bounce = mockNodeDetail("TRN-042")!.knowledge.find((c) => c.assertion_id === "T001-1");
    expect(bounce?.status).toBe("confirmed");
    expect(bounce?.scope_note).toBeUndefined();
  });

  it("devices without history get facts only", () => {
    const d = mockNodeDetail("TRN-101")!;
    expect(d.knowledge).toHaveLength(0);
    expect(d.events).toHaveLength(0);
  });

  it("unknown devices return null", () => {
    expect(mockNodeDetail("TRN-999")).toBeNull();
  });
});

describe("mock feedback", () => {
  it("queues comments of 8+ chars and counts feedback", async () => {
    const client = createMockClient();
    const before = MOCK_STATS.feedback;
    const short = await client.feedback({ assertion_id: "T001-1", verdict: "worked", comment: "ok" });
    expect(short.comment_queued).toBe(false);
    const long = await client.feedback({
      assertion_id: "T001-1",
      verdict: "worked",
      comment: "this fixed it on site",
    });
    expect(long.comment_queued).toBe(true);
    const none = await client.feedback({ assertion_id: "T001-1", verdict: "skip", comment: null });
    expect(none.comment_queued).toBe(false);
    expect(MOCK_STATS.feedback).toBe(before + 3);
  });

  it("chat done event carries a message_id", async () => {
    const client = createMockClient();
    const events: { type: string; message_id?: string | undefined }[] = [];
    await client.chat({ message: "TRN-031 no traffic" }, { onEvent: (e) => events.push(e) });
    const done = events.find((e) => e.type === "done");
    expect(done?.message_id).toMatch(/^msg-/);
  });
});
