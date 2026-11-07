import { useCallback, useEffect, useState } from "react";
import { format } from "date-fns";
import {
  AlertTriangle,
  ArrowUpCircle,
  Bell,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Cpu,
  MessageSquarePlus,
  RotateCcw,
  Truck,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { getClient, useApiSettings, type NodeDetail, type NodeEvent } from "@/api";
import { ApiError } from "@/api/client";
import { KnowledgeCard, ScopeNote, isOutdated, statusMeta, type DeviceSelectHandler } from "@/components/KnowledgeCard";
import type { KnowledgeCard as KnowledgeCardData } from "@/api/types";
import { cn } from "@/lib/utils";

const EVENT_META: Record<string, { icon: LucideIcon; className: string }> = {
  alarm_raised: { icon: Bell, className: "text-destructive" },
  alarm_cleared: { icon: CheckCircle2, className: "text-success" },
  work_order: { icon: ClipboardList, className: "text-muted-foreground" },
  firmware_upgrade: { icon: ArrowUpCircle, className: "text-primary" },
  hw_replacement: { icon: Wrench, className: "text-muted-foreground" },
  dispatch: { icon: Truck, className: "text-muted-foreground" },
};

function eventMeta(type: string) {
  return EVENT_META[type] ?? { icon: ClipboardList, className: "text-muted-foreground" };
}

function formatEventDate(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : format(d, "d MMM yyyy, HH:mm");
}

function Skeleton() {
  return (
    <div className="space-y-6 p-4" aria-label="Loading device">
      <div className="space-y-2">
        <div className="h-6 w-28 rounded bg-muted motion-safe:animate-pulse" />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-4 w-full rounded bg-muted motion-safe:animate-pulse" />
        ))}
      </div>
      <div className="space-y-2">
        <div className="h-3 w-32 rounded bg-muted motion-safe:animate-pulse" />
        <div className="h-24 w-full rounded-lg bg-muted motion-safe:animate-pulse" />
      </div>
      <div className="space-y-2">
        <div className="h-3 w-28 rounded bg-muted motion-safe:animate-pulse" />
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-10 w-full rounded bg-muted motion-safe:animate-pulse" />
        ))}
      </div>
    </div>
  );
}

/** Compact knowledge card for the panel; expands to the full card on click. */
export function CompactCard({ card, onDeviceSelect }: { card: KnowledgeCardData; onDeviceSelect?: DeviceSelectHandler | undefined }) {
  const [open, setOpen] = useState(false);
  if (open) {
    return (
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="absolute -right-1 -top-1 z-10 rounded-full border bg-card p-1 text-muted-foreground shadow-sm hover:text-foreground"
          aria-label="Collapse card"
        >
          <ChevronRight className="size-3.5 rotate-90" />
        </button>
        <KnowledgeCard card={card} onDeviceSelect={onDeviceSelect} />
      </div>
    );
  }
  const notNeeded = card.scope_note?.startsWith("Not needed") ?? false;
  const status = statusMeta(card.status);
  const StatusIcon = status.icon;
  return (
    <button
      type="button"
      onClick={() => setOpen(true)}
      className={cn(
        "block w-full rounded-lg border bg-card p-3 text-left shadow-sm transition hover:shadow-md",
        (isOutdated(card.status) || notNeeded) && "opacity-70",
      )}
    >
      <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <span className="rounded bg-secondary px-1.5 py-px text-secondary-foreground">
          {(card.knowledge_type ?? "").replace(/_/g, " ")}
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded px-1.5 py-px font-medium normal-case",
            status.className,
          )}
        >
          <StatusIcon className="size-3" /> {status.label}
        </span>
        <ChevronRight className="ml-auto size-3.5" />
      </span>
      <span className="mt-1.5 line-clamp-3 block text-sm font-medium leading-snug">{card.summary}</span>
      {(card.actions ?? []).length > 0 && (
        <ol className="mt-2 space-y-1">
          {(card.actions ?? []).map((a, i) => (
            <li key={a.code} className="flex gap-1.5 text-xs text-muted-foreground">
              <span className="font-mono text-primary">{i + 1}.</span> {a.text}
            </li>
          ))}
        </ol>
      )}
      {(card.avoid ?? []).length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {(card.avoid ?? []).map((a) => (
            <li key={a.code} className="flex gap-1.5 text-xs text-destructive">
              <span aria-hidden>✕</span> {a.text}
            </li>
          ))}
        </ul>
      )}
      <ScopeNote card={card} className="mt-2 text-[11px]" />
    </button>
  );
}

function Timeline({ events }: { events: NodeEvent[] }) {
  if (!events.length) return <p className="text-sm text-muted-foreground">No recent events.</p>;
  return (
    <ol className="relative space-y-4 border-l pl-5">
      {events.map((e) => {
        const meta = eventMeta(e.event_type);
        const Icon = meta.icon;
        return (
          <li key={e.event_id} className="relative">
            <span className="absolute -left-[27px] grid size-5 place-items-center rounded-full border bg-card">
              <Icon className={cn("size-3", meta.className)} />
            </span>
            <p className="text-xs text-muted-foreground">{formatEventDate(e.timestamp ?? "")}</p>
            <p className="mt-0.5 text-sm leading-snug">
              {e.detail}
              {e.event_type === "firmware_upgrade" && e.from_firmware && e.to_firmware && (
                <span className="ml-1.5 font-mono text-xs text-muted-foreground">
                  {e.from_firmware} → {e.to_firmware}
                </span>
              )}
            </p>
            {e.related_thread && (
              <span className="mt-1 inline-block rounded-full border px-1.5 py-px font-mono text-[10px] text-muted-foreground">
                {e.related_thread}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Detail({ detail, onAsk, onDeviceSelect }: { detail: NodeDetail; onAsk: (id: string) => void; onDeviceSelect?: DeviceSelectHandler | undefined }) {
  const { node } = detail;
  const older = !!node.install_date && node.install_date < "2020-01-01";
  return (
    <div className="space-y-6 p-4">
      <section>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-mono text-lg font-semibold">{node.node_id}</h2>
          {older && (
            <span className="rounded-full bg-warning/20 px-2 py-0.5 text-[11px] font-medium text-warning-foreground dark:text-warning">
              Older unit
            </span>
          )}
        </div>
        <dl className="mt-3 space-y-1.5 text-sm">
          {(
            [
              ["Type", (node.type ?? "").replace(/_/g, " ")],
              ["Location", node.location],
              ["Firmware", node.firmware],
              ["Installed", node.install_date],
              ["Status", (node.status ?? "").replace(/_/g, " ")],
            ] as const
          ).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="text-right">{v}</dd>
            </div>
          ))}
        </dl>
        <Button size="sm" variant="outline" className="mt-3 w-full" onClick={() => onAsk(node.node_id)}>
          <MessageSquarePlus className="size-3.5" /> Ask about this device
        </Button>
      </section>

      <section>
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Knowledge for this device
        </p>
        {(detail.knowledge ?? []).length ? (
          <div className="space-y-2.5">
            {(detail.knowledge ?? []).map((c) => (
              <CompactCard key={c.assertion_id} card={c} onDeviceSelect={onDeviceSelect} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No captured knowledge for this device yet.</p>
        )}
      </section>

      <section>
        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Recent events</p>
        <Timeline events={detail.events ?? []} />
      </section>
    </div>
  );
}

export function DevicePanel({
  nodeId,
  onAsk,
  onDeviceSelect,
}: {
  nodeId?: string | undefined;
  onAsk: (id: string) => void;
  onDeviceSelect?: DeviceSelectHandler | undefined;
}) {
  const settings = useApiSettings();
  const [state, setState] = useState<
    { kind: "idle" } | { kind: "loading" } | { kind: "error"; notFound: boolean } | { kind: "ok"; detail: NodeDetail }
  >({ kind: "idle" });

  const load = useCallback(
    (id: string, signal?: AbortSignal) => {
      setState({ kind: "loading" });
      getClient(settings)
        .node(id, signal)
        .then((detail) => setState({ kind: "ok", detail }))
        .catch((e) => {
          if ((e as Error).name === "AbortError") return;
          setState({ kind: "error", notFound: e instanceof ApiError && e.status === 404 });
        });
    },
    [settings],
  );

  useEffect(() => {
    if (!nodeId) {
      setState({ kind: "idle" });
      return;
    }
    const ctrl = new AbortController();
    load(nodeId, ctrl.signal);
    return () => ctrl.abort();
  }, [nodeId, load]);

  return (
    <div className="h-full overflow-y-auto">
      {state.kind === "idle" && (
        <div className="flex h-full flex-col items-center justify-center gap-2 p-4 text-center text-sm text-muted-foreground">
          <Cpu className="size-6 opacity-60" />
          Select a device to see its details.
        </div>
      )}
      {state.kind === "loading" && <Skeleton />}
      {state.kind === "error" && (
        <div className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center text-sm">
          <AlertTriangle className="size-6 text-destructive" />
          {state.notFound ? (
            <p className="text-muted-foreground">Unknown device.</p>
          ) : (
            <>
              <p className="text-muted-foreground">Couldn't load this device.</p>
              {nodeId && (
                <Button size="sm" variant="outline" onClick={() => load(nodeId)}>
                  <RotateCcw className="size-3.5" /> Retry
                </Button>
              )}
            </>
          )}
        </div>
      )}
      {state.kind === "ok" && <Detail detail={state.detail} onAsk={onAsk} onDeviceSelect={onDeviceSelect} />}
    </div>
  );
}
