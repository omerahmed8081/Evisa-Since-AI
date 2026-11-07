import type { KnowledgeCard, Verdict } from "@/api/types";

export interface ChatMessage {
  id: string;
  role: "user" | "bot";
  text: string;
  nodeId?: string | undefined;
  cards?: KnowledgeCard[] | undefined;
  status?: "waiting" | "streaming" | "done" | "error" | "stopped";
  error?: string | undefined;
  /** Server message id from the done event; used for feedback. */
  messageId?: string | undefined;
  /** Chosen feedback verdict per assertion_id, persisted with the chat. */
  verdicts?: Record<string, Verdict> | undefined;
}

export interface StoredChat {
  id: string;
  title: string;
  conversationId?: string | undefined;
  messages: ChatMessage[];
  updatedAt: number;
}

const KEY = "recentChats";
export const MAX_CHATS = 20;

export function loadChats(): StoredChat[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as StoredChat[]) : [];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_CHATS) : [];
  } catch {
    return [];
  }
}

export function saveChats(chats: StoredChat[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats.slice(0, MAX_CHATS)));
  } catch {
    /* storage full or unavailable */
  }
}

/** Insert/replace a chat at the top, keeping at most MAX_CHATS. */
export function upsertChat(chats: StoredChat[], chat: StoredChat): StoredChat[] {
  return [chat, ...chats.filter((c) => c.id !== chat.id)].slice(0, MAX_CHATS);
}

export function titleFrom(message: string) {
  const t = message.trim().replace(/\s+/g, " ");
  return t.length > 60 ? `${t.slice(0, 57)}…` : t;
}

/** Device IDs like TRN-031, BTS-233, AGG-003, MW-405 typed in free text. */
export function findDeviceIds(text: string): string[] {
  return Array.from(new Set((text.toUpperCase().match(/\b(?:TRN|BTS|AGG|MW)-\d{3}\b/g) ?? [])));
}
