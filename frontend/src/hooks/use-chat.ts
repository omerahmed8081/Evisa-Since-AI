import { useCallback, useEffect, useRef, useState } from "react";
import { getClient, type Verdict } from "@/api";
import type { ChatMeta } from "@/api/types";
import {
  insertChatAt,
  loadChats,
  removeChat,
  saveChats,
  titleFrom,
  upsertChat,
  type ChatMessage,
  type StoredChat,
} from "@/lib/chat-store";

const uid = () => crypto.randomUUID();

export function useChat(onMeta?: (meta: ChatMeta) => void, uiLanguage: "en" | "fi" = "en") {
  const onMetaRef = useRef(onMeta);
  onMetaRef.current = onMeta;
  const langRef = useRef(uiLanguage);
  langRef.current = uiLanguage;
  const [chats, setChats] = useState<StoredChat[]>([]);
  const [chatId, setChatId] = useState<string>(() => uid());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const convRef = useRef<string | undefined>(undefined);
  convRef.current = conversationId;
  const chatsRef = useRef<StoredChat[]>([]);
  chatsRef.current = chats;
  const chatIdRef = useRef(chatId);
  chatIdRef.current = chatId;

  useEffect(() => setChats(loadChats()), []);

  // Persist the current chat whenever it settles.
  useEffect(() => {
    if (busy || messages.length === 0) return;
    const first = messages.find((m) => m.role === "user");
    if (!first) return;
    setChats((prev) => {
      const next = upsertChat(prev, {
        id: chatId,
        title: titleFrom(first.text),
        conversationId,
        messages,
        updatedAt: Date.now(),
      });
      saveChats(next);
      return next;
    });
  }, [busy, messages, chatId, conversationId]);

  const patch = (id: string, fn: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => prev.map((m) => (m.id === id ? fn(m) : m)));

  const runBot = useCallback(async (text: string, nodeId: string | undefined, botId: string) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setBusy(true);
    let gotError = false;
    try {
      await getClient().chat(
        { message: text, node_id: nodeId, conversation_id: convRef.current, ui_language: langRef.current },
        {
          onEvent: (ev) => {
            if (controller.signal.aborted) return;
            switch (ev.type) {
              case "meta":
                if (ev.conversation_id) setConversationId(ev.conversation_id);
                patch(botId, (m) => ({ ...m, meta: ev }));
                onMetaRef.current?.(ev);
                break;
              case "token":
                patch(botId, (m) => ({ ...m, status: "streaming", text: m.text + ev.text }));
                break;
              case "cards":
                patch(botId, (m) => ({ ...m, cards: ev.cards ?? [] }));
                break;
              case "error":
                gotError = true;
                patch(botId, (m) => ({ ...m, status: "error", error: ev.message }));
                break;
              case "done":
                if (ev.message_id) patch(botId, (m) => ({ ...m, messageId: ev.message_id }));
                break;
            }
          },
        },
        controller.signal,
      );
      if (!gotError) patch(botId, (m) => ({ ...m, status: "done" }));
    } catch (e) {
      if ((e as Error).name === "AbortError") {
        patch(botId, (m) => ({ ...m, status: "stopped" }));
      } else {
        patch(botId, (m) => ({
          ...m,
          status: "error",
          error: (e as Error).message || "Request failed",
        }));
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        setBusy(false);
      }
    }
  }, []);

  const send = useCallback(
    (text: string, nodeId?: string) => {
      const t = text.trim();
      if (!t || abortRef.current) return;
      const botId = uid();
      setMessages((prev) => [
        ...prev,
        { id: uid(), role: "user", text: t, nodeId },
        { id: botId, role: "bot", text: "", status: "waiting" },
      ]);
      void runBot(t, nodeId, botId);
    },
    [runBot],
  );

  const retry = useCallback(
    (botId: string) => {
      if (abortRef.current) return;
      const idx = messages.findIndex((m) => m.id === botId);
      const user = messages
        .slice(0, idx)
        .reverse()
        .find((m) => m.role === "user");
      if (!user) return;
      patch(botId, (m) => ({ ...m, text: "", cards: undefined, meta: undefined, error: undefined, status: "waiting" }));
      void runBot(user.text, user.nodeId, botId);
    },
    [messages, runBot],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  /** Remember a feedback verdict on a bot message (persisted with the chat). */
  const setVerdict = useCallback((botId: string, assertionId: string, verdict: Verdict) => {
    patch(botId, (m) => ({ ...m, verdicts: { ...m.verdicts, [assertionId]: verdict } }));
  }, []);

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    const first = messages.find((m) => m.role === "user");
    if (first) setChats((prev) => {
      const next = upsertChat(prev, { id: chatId, title: titleFrom(first.text), conversationId,
        messages: messages.map((m) => m.status === "streaming" || m.status === "waiting" ? { ...m, status: "stopped" } : m), updatedAt: Date.now() });
      saveChats(next);
      return next;
    });
    convRef.current = undefined;
    setChatId(uid());
    setMessages([]);
    setConversationId(undefined);
  }, [messages, chatId, conversationId]);

  const openChat = useCallback(
    (id: string) => {
      const c = chats.find((x) => x.id === id);
      if (!c) return;
      abortRef.current?.abort();
      abortRef.current = null;
      setBusy(false);
      convRef.current = c.conversationId;
      setChatId(c.id);
      setMessages(c.messages);
      setConversationId(c.conversationId);
    },
    [chats],
  );

  /** Clear the open chat view without saving it (used when the open chat is deleted). */
  const clearOpen = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
    convRef.current = undefined;
    setChatId(uid());
    setMessages([]);
    setConversationId(undefined);
  }, []);

  /** Delete a chat from the list and storage. Returns the removed chat and its index for undo. */
  const deleteChat = useCallback(
    (id: string): { chat: StoredChat; index: number } | null => {
      const prev = chatsRef.current;
      const index = prev.findIndex((c) => c.id === id);
      if (index === -1) return null;
      const removed = { chat: prev[index]!, index };
      const next = removeChat(prev, id);
      setChats(next);
      saveChats(next);
      if (id === chatIdRef.current) clearOpen();
      return removed;
    },
    [clearOpen],
  );

  /** Restore a previously deleted chat at its original position (undo). */
  const restoreChat = useCallback((chat: StoredChat, index: number) => {
    setChats((prev) => {
      const next = insertChatAt(prev, chat, index);
      saveChats(next);
      return next;
    });
  }, []);

  /** Delete every chat and clear the open view. Browser-only: never calls the backend. */
  const deleteAllChats = useCallback(() => {
    setChats([]);
    saveChats([]);
    clearOpen();
  }, [clearOpen]);

  return { chats, chatId, messages, busy, send, retry, stop, newChat, openChat, setVerdict, deleteChat, restoreChat, deleteAllChats };
}
