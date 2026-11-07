import { useSyncExternalStore } from "react";
import { createRealClient } from "./client";
import { createMockClient } from "./mock";
import type { ApiClient } from "./types";

export * from "./types";

/**
 * Mode switch: mock mode is used when the "useMock" setting is on OR no API base URL is set.
 * Otherwise the real client talks to the saved "apiBaseUrl".
 * Until something is saved in the Settings dialog, both values come from the build
 * environment: VITE_API_BASE_URL and VITE_USE_MOCK.
 */
export interface ApiSettings {
  apiBaseUrl: string;
  useMock: boolean;
}

const KEY_URL = "apiBaseUrl";
const KEY_MOCK = "useMock";

/**
 * Build-time defaults, used only while nothing is saved in localStorage.
 * VITE_USE_MOCK === "true" means mock; a VITE_API_BASE_URL with anything else means live.
 */
function envDefaults(): ApiSettings {
  const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").trim();
  const useMock = import.meta.env.VITE_USE_MOCK === "true" ? true : !apiBaseUrl;
  return { apiBaseUrl, useMock };
}

function read(): ApiSettings {
  const d = envDefaults();
  try {
    const saved = localStorage.getItem(KEY_URL);
    const m = localStorage.getItem(KEY_MOCK);
    return {
      // A saved value always wins, even an empty one; the default only fills a missing key.
      apiBaseUrl: saved === null ? d.apiBaseUrl : saved.trim(),
      useMock: m === null ? d.useMock : m === "true",
    };
  } catch {
    return d;
  }
}

const SERVER: ApiSettings = envDefaults();
let current: ApiSettings | null = null;
const listeners = new Set<() => void>();

export function getSettings(): ApiSettings {
  if (typeof window === "undefined") return SERVER;
  return (current ??= read());
}

export function saveSettings(next: ApiSettings) {
  current = { apiBaseUrl: next.apiBaseUrl.trim(), useMock: next.useMock };
  try {
    localStorage.setItem(KEY_URL, current.apiBaseUrl);
    localStorage.setItem(KEY_MOCK, String(current.useMock));
  } catch {
    /* ignore */
  }
  clientCache = null;
  listeners.forEach((l) => l());
}

/** Drop the saved values and fall back to the build-environment defaults. */
export function resetSettings() {
  try {
    localStorage.removeItem(KEY_URL);
    localStorage.removeItem(KEY_MOCK);
  } catch {
    /* ignore */
  }
  current = null;
  clientCache = null;
  listeners.forEach((l) => l());
}

export function isMock(s: ApiSettings) {
  return s.useMock || !s.apiBaseUrl;
}

let clientCache: { key: string; client: ApiClient } | null = null;
export function getClient(s: ApiSettings = getSettings()): ApiClient {
  const key = isMock(s) ? "mock" : s.apiBaseUrl;
  if (clientCache?.key !== key) {
    clientCache = { key, client: isMock(s) ? createMockClient() : createRealClient(s.apiBaseUrl) };
  }
  return clientCache.client;
}

export function useApiSettings(): ApiSettings {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    getSettings,
    () => SERVER,
  );
}

export { createRealClient, createMockClient };
