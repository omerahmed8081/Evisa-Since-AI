import { describe, expect, it } from "vitest";
import { en, fi } from "@/i18n";
import { actionText, avoidText } from "@/lib/vocabulary";

/** Leaf paths of a dictionary; functions count as leaves. */
function keyPaths(obj: unknown, prefix = ""): string[] {
  if (typeof obj !== "object" || obj === null) return [prefix];
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    keyPaths(v, prefix ? `${prefix}.${k}` : k),
  );
}

describe("i18n dictionaries", () => {
  it("en and fi have exactly the same keys", () => {
    expect(keyPaths(fi).sort()).toEqual(keyPaths(en).sort());
  });
});

describe("vocabulary codes in Finnish", () => {
  it("translates known step codes", () => {
    expect(actionText({ code: "BOUNCE_INTERFACE", text: "Disable and re-enable the interface" }, "fi")).toBe(
      "Ota portti alas ja nosta se takaisin ylös",
    );
  });
  it("translates known avoid codes with proper negatives", () => {
    expect(avoidText({ code: "REPLACE_SFP", text: "Don't replace the SFP" }, "fi")).toBe("Älä vaihda SFP:tä");
    expect(avoidText({ code: "WARM_REBOOT", text: "Don't do a warm reboot" }, "fi")).toBe(
      "Älä tee lämmintä uudelleenkäynnistystä",
    );
  });
  it("prefixes unknown avoid codes with Vältä when the step translation exists", () => {
    expect(avoidText({ code: "REPLACE_PATCH_CABLE", text: "Don't replace the patch cable" }, "fi")).toBe(
      "Vältä: Vaihda patch-kaapeli",
    );
  });
  it("falls back to the backend text for unknown codes", () => {
    expect(actionText({ code: "SOME_NEW_CODE", text: "Do the new thing" }, "fi")).toBe("Do the new thing");
    expect(avoidText({ code: "SOME_NEW_CODE", text: "Don't do the new thing" }, "fi")).toBe("Don't do the new thing");
  });
  it("keeps English text in English mode", () => {
    expect(actionText({ code: "BOUNCE_INTERFACE", text: "Disable and re-enable the interface" }, "en")).toBe(
      "Disable and re-enable the interface",
    );
  });
});
