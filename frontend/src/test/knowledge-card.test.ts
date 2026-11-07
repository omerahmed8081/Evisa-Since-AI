import { describe, expect, it } from "vitest";
import { findScenario } from "@/api/mockData";
import { splitDeviceRefs } from "@/lib/device-refs";

describe("device refs", () => {
  it("splits device ids out of text", () => {
    expect(splitDeviceRefs("TRN-031 is down, check BTS-233 too")).toEqual([
      { kind: "device", value: "TRN-031" },
      { kind: "text", value: " is down, check " },
      { kind: "device", value: "BTS-233" },
      { kind: "text", value: " too" },
    ]);
  });
  it("leaves plain text untouched", () => {
    expect(splitDeviceRefs("no devices here")).toEqual([{ kind: "text", value: "no devices here" }]);
  });
});

describe("phase 2 mock answers", () => {
  it("access answer mentions lockbox code 2580", () => {
    expect(findScenario("How do I get to the TRN-042 site near Kolari?")?.answer).toContain("**2580**");
  });
  it("bts233 answer prescribes a cold restart", () => {
    expect(findScenario("BTS-233 cell down after a power outage")?.answer).toContain("cold restart");
  });
  it("agg answer blames the patch cable", () => {
    expect(findScenario("CRC errors on AGG-003 after maintenance")?.answer).toContain("patch cable");
  });
  it("mw405 answer names both experts", () => {
    const a = findScenario("MW-405 linkki alhaalla kovalla pakkasella")?.answer ?? "";
    expect(a).toContain("Erkki Expert");
    expect(a).toContain("Jari Jänne");
  });
});
