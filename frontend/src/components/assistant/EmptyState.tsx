import { Network } from "lucide-react";

export const EXAMPLES = [
  "TRN-031: SFP replaced, link up but no traffic. What should I do?",
  "BTS-233 cell down after a power outage",
  "How do I get to the TRN-042 site near Kolari?",
  "CRC errors on AGG-003 after maintenance",
  "MW-405 linkki alhaalla kovalla pakkasella",
];

export function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center px-4 py-10 text-center">
      <div className="mb-5 grid size-12 place-items-center rounded-xl bg-accent text-accent-foreground">
        <Network className="size-6" />
      </div>
      <h2 className="text-2xl font-semibold tracking-tight">Ask about a device, a symptom or a fix.</h2>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {EXAMPLES.map((e) => (
          <button
            key={e}
            onClick={() => onPick(e)}
            className="rounded-full border bg-card px-3.5 py-2 text-left text-sm text-card-foreground transition hover:border-primary hover:bg-accent active:scale-[0.98]"
          >
            {e}
          </button>
        ))}
      </div>
    </div>
  );
}
