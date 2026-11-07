import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { getSettings, isMock, resetSettings, saveSettings } from "@/api";

const env = import.meta.env as unknown as Record<string, string | undefined>;

function setEnv(url: string | undefined, mock: string | undefined) {
  env["VITE_API_BASE_URL"] = url;
  env["VITE_USE_MOCK"] = mock;
}

beforeEach(() => {
  localStorage.clear();
  resetSettings(); // drops the cached snapshot so the next read sees the new env
});

afterEach(() => setEnv(undefined, undefined));

describe("settings defaults", () => {
  it("uses VITE_API_BASE_URL and goes live when VITE_USE_MOCK is not 'true'", () => {
    setEnv("https://kb.example.com", undefined);
    expect(getSettings()).toEqual({ apiBaseUrl: "https://kb.example.com", useMock: false });
    expect(isMock(getSettings())).toBe(false);
  });

  it("VITE_USE_MOCK 'true' keeps mock data even with a base URL", () => {
    setEnv("https://kb.example.com", "true");
    expect(getSettings().useMock).toBe(true);
    expect(isMock(getSettings())).toBe(true);
  });

  it("without a base URL there is nothing to talk to, so mock", () => {
    setEnv("", "false");
    expect(getSettings()).toEqual({ apiBaseUrl: "", useMock: true });
    expect(isMock(getSettings())).toBe(true);
  });

  it("values saved in the dialog win over the defaults", () => {
    setEnv("https://kb.example.com", undefined);
    saveSettings({ apiBaseUrl: "https://saved.example.com", useMock: true });
    expect(getSettings()).toEqual({ apiBaseUrl: "https://saved.example.com", useMock: true });
  });

  it("an empty saved URL still wins: no default is injected", () => {
    setEnv("https://kb.example.com", undefined);
    saveSettings({ apiBaseUrl: "   ", useMock: false });
    expect(getSettings().apiBaseUrl).toBe("");
    expect(isMock(getSettings())).toBe(true);
  });

  it("reset clears both keys and goes back to the defaults", () => {
    setEnv("https://kb.example.com", undefined);
    saveSettings({ apiBaseUrl: "https://saved.example.com", useMock: true });
    resetSettings();
    expect(localStorage.getItem("apiBaseUrl")).toBeNull();
    expect(localStorage.getItem("useMock")).toBeNull();
    expect(getSettings()).toEqual({ apiBaseUrl: "https://kb.example.com", useMock: false });
  });
});
