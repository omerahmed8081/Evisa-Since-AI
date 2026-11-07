import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CompactCard } from "@/components/assistant/DevicePanel";
import { findScenario, mockNodeDetail } from "@/api/mockData";

describe("device panel compact cards", () => {
  it("shows the not-needed note as the outdated note with the Outdated badge", () => {
    const card = mockNodeDetail("TRN-077")!.knowledge.find((c) => c.assertion_id === "T001-1")!;
    render(<CompactCard card={card} />);
    expect(screen.getByText("Outdated")).toBeInTheDocument();
    expect(screen.getByText(/Not needed on TRN-077/)).toBeInTheDocument();
    expect(screen.queryByText(/Upgrade fixes this/)).toBeNull();
  });

  it("shows the not-yet note as the upgrade-fixes-this note", () => {
    const card = findScenario("TRN-031 no traffic")!.cards.find((c) => c.assertion_id === "E007-1")!;
    render(<CompactCard card={card} />);
    expect(screen.getByText("Upgrade fixes this.")).toBeInTheDocument();
    expect(screen.getByText(/Not yet on TRN-031/)).toBeInTheDocument();
    expect(screen.queryByText("Outdated")).toBeNull();
  });
});
