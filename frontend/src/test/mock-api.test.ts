import { describe, expect, it } from "vitest";
import { findScenario, MOCK_NODES } from "@/api/mockData";
import { createSseParser, frameToEvent } from "@/api/sse";
import { MAX_CHATS, upsertChat } from "@/lib/chat-store";
import { EXAMPLES } from "@/components/assistant/EmptyState";

describe("mock scenarios", () => {
  it("routes each example chip to its scenario", () => {
    expect(EXAMPLES.map((e) => findScenario(e)?.id)).toEqual(["trn031", "bts233", "access", "agg", "mw405"]);
  });
  it("unknown questions get no scenario", () => {
    expect(findScenario("Fan noise on the rack")).toBeNull();
  });
  it("has 25 devices", () => expect(MOCK_NODES).toHaveLength(25));
});

describe("sse parser", () => {
  it("parses frames split across chunks", () => {
    const p = createSseParser();
    expect(p.push('event: token\ndata: {"text":"Hel')).toEqual([]);
    const frames = p.push('lo"}\n\nevent: done\ndata: {}\n\n');
    expect(frames.map(frameToEvent)).toEqual([{ type: "token", text: "Hello" }, { type: "done" }]);
  });
});

describe("recent chats", () => {
  it("keeps at most 20", () => {
    let list: Parameters<typeof upsertChat>[0] = [];
    for (let i = 0; i < 25; i++) list = upsertChat(list, { id: String(i), title: "t", messages: [], updatedAt: i });
    expect(list).toHaveLength(MAX_CHATS);
    expect(list[0]?.id).toBe("24");
  });
});
