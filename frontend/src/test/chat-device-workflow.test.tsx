import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useChat } from "@/hooks/use-chat";
import type { ChatRequest, StreamHandlers } from "@/api/types";

const mock = vi.hoisted(() => ({ chat: vi.fn() }));
vi.mock("@/api", () => ({ getClient: () => ({ chat: mock.chat }) }));
afterEach(() => { vi.clearAllMocks(); localStorage.clear(); });

describe("device chat lifecycle", () => {
  it("stores answer metadata, forwards selection metadata, and starts a new conversation retaining history", async () => {
    mock.chat.mockImplementation(async (_req: ChatRequest, handlers: StreamHandlers) => {
      handlers.onEvent({ type: "meta", conversation_id: "old-conversation", resolved_nodes: ["TRN-031"], ignored_selection: null, resolution_note: null, question_type: "overview" });
      handlers.onEvent({ type: "token", text: "Known issues" });
      handlers.onEvent({ type: "done", message_id: "answer-1" });
    });
    const onMeta = vi.fn();
    const { result } = renderHook(() => useChat(onMeta));
    await act(async () => result.current.send("What are the known issues on TRN-031?", "TRN-031"));
    await waitFor(() => expect(result.current.busy).toBe(false));
    expect(result.current.messages[1]?.meta?.question_type).toBe("overview");
    expect(onMeta).toHaveBeenCalledWith(expect.objectContaining({ resolved_nodes: ["TRN-031"] }));
    act(() => result.current.newChat());
    expect(result.current.messages).toEqual([]);
    expect(result.current.chats[0]?.messages[1]?.text).toBe("Known issues");
    await act(async () => result.current.send("Traffic counters zero after SFP replacement?", "TRN-031"));
    expect(mock.chat.mock.calls[1]?.[0]).toMatchObject({ node_id: "TRN-031", conversation_id: undefined });
  });
  it("preserves and stops an in-flight chat when starting a fresh device chat", async () => {
    mock.chat.mockImplementation((_req: ChatRequest, handlers: StreamHandlers, signal: AbortSignal) => new Promise<void>((resolve) => {
      handlers.onEvent({ type: "token", text: "Partial answer" });
      signal.addEventListener("abort", () => resolve(), { once: true });
    }));
    const { result } = renderHook(() => useChat());
    act(() => result.current.send("TRN-031 no traffic", "TRN-031"));
    act(() => result.current.newChat());
    expect(result.current.messages).toEqual([]);
    expect(result.current.busy).toBe(false);
    expect(result.current.chats[0]?.messages[1]?.status).toBe("stopped");
    await act(async () => {});
  });
});