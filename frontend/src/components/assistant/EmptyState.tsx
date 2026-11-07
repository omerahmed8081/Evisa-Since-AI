import { Network } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage, useT } from "@/i18n";

export const EXAMPLES = [
  "TRN-031: SFP replaced, link up but no traffic. What should I do?",
  "BTS-233 cell down after a power outage",
  "How do I get to the TRN-042 site near Kolari?",
  "CRC errors on AGG-003 after maintenance",
  "MW-405 linkki alhaalla kovalla pakkasella",
];

export const EXAMPLES_FI = [
  "TRN-031: SFP vaihdettu, linkki ylhäällä mutta liikenne ei kulje. Mitä teen?",
  "BTS-233 solu alhaalla sähkökatkon jälkeen",
  "Miten pääsen TRN-042-asemalle Kolarissa?",
  "CRC-virheitä AGG-003:ssa huollon jälkeen",
  "MW-405 linkki alhaalla kovalla pakkasella",
];

export function EmptyState({ onPick, nodeId, questions }: { onPick: (text: string) => void; nodeId?: string | undefined; questions?: string[] | undefined }) {
  const t = useT();
  const { lang } = useLanguage();
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-5 grid size-12 place-items-center rounded-xl bg-accent text-accent-foreground">
        <Network className="size-6" />
      </div>
      <h2 className="text-2xl font-semibold">{nodeId ? <>{t.empty.askAbout} <span className="font-mono">{nodeId}</span></> : t.empty.title}</h2>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {(nodeId ? questions ?? [t.empty.knownIssues(nodeId)] : lang === "fi" ? EXAMPLES_FI : EXAMPLES).map((e) => (
          <Button variant="outline"
            key={e}
            onClick={() => onPick(e)}
            className="h-auto min-h-11 max-w-full whitespace-normal rounded-full px-3.5 py-2 text-left text-sm font-normal"
          >
            {e}
          </Button>
        ))}
      </div>
    </div>
  );
}
