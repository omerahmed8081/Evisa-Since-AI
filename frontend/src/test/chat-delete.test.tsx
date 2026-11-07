import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useChat } from "@/hooks/use-chat";
import { insertChatAt, loadChats, removeChat, saveChats, type StoredChat } from "@/lib/chat-store";

const mock = vi.hoisted(() => ({ chat: vi.fn() }));
vi.mock("@/api", () => ({ getClient: () => ({ chat: mock.chat }) }));
afterEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

const chat = (id: string, title = id): StoredChat => ({
  id,
  title,
  messages: [{ id: `${id}-u`, role: "user", text: title }],
  updatedAt: 1,
});

describe("chat store deletion helpers", () => {
  it("removeChat removes only that chat", () => {
    const list = [chat("a"), chat("b"), chat("c")];
    expect(removeChat(list, "b").map((c) => c.id)).toEqual(["a", "c"]);
  });
  it("insertChatAt restores the chat at its original position", () => {
    const list = [chat("a"), chat("c")];
    expect(insertChatAt(list, chat("b"), 1).map((c) => c.id)).toEqual(["a", "b", "c"]);
  });
  it("insertChatAt clamps out-of-range indexes", () => {
    expect(insertChatAt([chat("a")], chat("b"), 99).map((c) => c.id)).toEqual(["a", "b"]);
  });
});

describe("deleting chats", () => {
  it("deletes one chat from state and localStorage, and undo restores it in place", () => {
    saveChats([chat("a", "First"), chat("b", "Second"), chat("c", "Third")]);
    const { result } = renderHook(() => useChat());
    expect(result.current.chats.map((c) => c.id)).toEqual(["a", "b", "c"]);

    let removed: { chat: StoredChat; index: number } | null = null;
    act(() => {
      removed = result.current.deleteChat("b");
    });
    expect(result.current.chats.map((c) => c.id)).toEqual(["a", "c"]);
    expect(loadChats().map((c) => c.id)).toEqual(["a", "c"]);
    expect(removed!.chat.title).toBe("Second");
    expect(removed!.index).toBe(1);

    act(() => result.current.restoreChat(removed!.chat, removed!.index));
    expect(result.current.chats.map((c) => c.id)).toEqual(["a", "b", "c"]);
    expect(loadChats().map((c) => c.id)).toEqual(["a", "b", "c"]);
  });

  it("delete-all empties the list and localStorage", () => {
    saveChats([chat("a"), chat("b")]);
    const { result } = renderHook(() => useChat());
    act(() => result.current.deleteAllChats());
    expect(result.current.chats).toEqual([]);
    expect(loadChats()).toEqual([]);
  });

  it("deleting the open chat clears the chat view", () => {
    saveChats([chat("a", "First"), chat("b", "Second")]);
    const { result } = renderHook(() => useChat());
    act(() => result.current.openChat("a"));
    expect(result.current.messages).toHaveLength(1);
    act(() => result.current.deleteChat("a"));
    expect(result.current.messages).toEqual([]);
    expect(result.current.chats.map((c) => c.id)).toEqual(["b"]);
  });

  it("makes no network request when deleting chats", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    saveChats([chat("a"), chat("b")]);
    const { result } = renderHook(() => useChat());
    act(() => result.current.deleteChat("a"));
    act(() => result.current.deleteAllChats());
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(mock.chat).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
