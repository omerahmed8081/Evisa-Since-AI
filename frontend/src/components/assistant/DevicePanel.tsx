import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, ChevronRight, ChevronsUpDown, Cpu, MessageSquarePlus, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { getClient, useApiSettings, type Node, type NodeDetail } from "@/api";
import { ApiError } from "@/api/client";
import { KnowledgeCard, ScopeNote, isOutdated, statusMeta, typeMeta, type DeviceSelectHandler } from "@/components/KnowledgeCard";
import type { KnowledgeCard as KnowledgeCardData, Verdict } from "@/api/types";
import { useLanguage, useT } from "@/i18n";
import { deviceSuggestions } from "@/lib/device-suggestions";
import { cn } from "@/lib/utils";

function Skeleton() {
  const t = useT();
  return <div className="space-y-4 p-4" aria-label={t.panel.loading}>{[0, 1, 2, 3].map((i) => <div key={i} className="h-11 rounded bg-muted motion-safe:animate-pulse" />)}</div>;
}

export function CompactCard({ card, onDeviceSelect, messageId, verdict, onVerdict }: {
  card: KnowledgeCardData; onDeviceSelect?: DeviceSelectHandler | undefined;
  messageId?: string | undefined; verdict?: Verdict | undefined; onVerdict?: ((v: Verdict) => void) | undefined;
}) {
  const [open, setOpen] = useState(false);
  const t = useT();
  const { lang } = useLanguage();
  const status = statusMeta(card.status, lang);
  const StatusIcon = status.icon;
  if (open) return <div className="relative pt-1">
    <Button variant="outline" size="icon" aria-label={t.panel.collapseCard} onClick={() => setOpen(false)} className="absolute right-1 top-1 z-10"><ChevronRight className="size-4 rotate-90" /></Button>
    <div className="[&_article>header]:pr-10"><KnowledgeCard card={card} onDeviceSelect={onDeviceSelect} messageId={messageId} verdict={verdict} onVerdict={onVerdict} /></div>
  </div>;
  return <Button variant="outline" aria-expanded={false} onClick={() => setOpen(true)} className={cn("h-auto min-h-11 w-full flex-col items-stretch gap-1.5 whitespace-normal rounded-lg p-3 text-left", (isOutdated(card.status) || card.scope_note?.startsWith("Not needed")) && "opacity-70")}>
    <span className="flex w-full flex-wrap items-center gap-2">
      <span className="rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground">{typeMeta(card.knowledge_type, lang).label}</span>
      <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs", status.className)}><StatusIcon className="size-3" />{status.label}</span>
      <span title={card.summary} className="min-w-0 flex-1 basis-48 truncate text-sm font-medium">{card.summary}</span>
      <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
    </span>
    <ScopeNote card={card} className="text-xs" />
  </Button>;
}

function Detail({ detail, onAsk, onQuestion }: { detail: NodeDetail; onAsk: (id: string) => void; onQuestion: (text: string) => void }) {
  const t = useT();
  const { lang } = useLanguage();
  const { node } = detail;
  const older = !!node.install_date && node.install_date < "2020-01-01";
  const types = t.panel.types as Record<string, string>;
  return <div className="space-y-6 p-4">
    <section>
      <div className="flex flex-wrap items-center gap-2"><h2 className="font-mono text-lg font-semibold">{node.node_id}</h2>{older && <span className="rounded bg-warning/20 px-2 py-1 text-xs text-warning-foreground dark:text-warning">{t.panel.olderUnit}</span>}</div>
      <p className="mt-1 text-sm text-muted-foreground">{types[node.type] ?? node.type}</p>
      <Button variant="outline" className="mt-4 min-h-11 w-full" onClick={() => onAsk(node.node_id)}><MessageSquarePlus className="size-4" />{t.panel.askAbout}</Button>
    </section>
    <section><h3 className="mb-2 text-xs font-medium uppercase text-muted-foreground">{t.panel.suggested}</h3>
      <div className="space-y-2">{deviceSuggestions(detail, undefined, lang).map((question) => <Button key={question} variant="ghost" onClick={() => onQuestion(question)} className="h-auto min-h-11 w-full justify-start whitespace-normal border px-3 py-2.5 text-left text-sm font-normal">{question}</Button>)}</div>
    </section>
  </div>;
}

export function DevicePanel({
  nodeId,
  onAsk,
  onDeviceSelect,
  nodes,
  onQuestion,
  onDetail,
}: {
  nodeId?: string | undefined;
  onAsk: (id: string) => void;
  onDeviceSelect: DeviceSelectHandler;
  nodes: Node[];
  onQuestion: (text: string) => void;
  onDetail: (detail: NodeDetail) => void;
}) {
  const settings = useApiSettings();
  const t = useT();
  const [selectorOpen, setSelectorOpen] = useState(false);
  const detailCallback = useRef(onDetail);
  detailCallback.current = onDetail;
  const [state, setState] = useState<
    { kind: "idle" } | { kind: "loading" } | { kind: "error"; notFound: boolean } | { kind: "ok"; detail: NodeDetail }
  >({ kind: "idle" });

  const load = useCallback(
    (id: string, signal?: AbortSignal) => {
      setState({ kind: "loading" });
      getClient(settings)
        .node(id, signal)
        .then((detail) => {
          if (signal?.aborted) return;
          setState({ kind: "ok", detail });
          detailCallback.current(detail);
        })
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
      <div className="border-b p-4">
        <Popover open={selectorOpen} onOpenChange={setSelectorOpen}>
          <PopoverTrigger asChild>
            <Button variant="outline" role="combobox" aria-expanded={selectorOpen} aria-label={t.panel.selectDevice} className="min-h-11 w-full justify-between">
              <Cpu className="size-4" /><span className={nodeId ? "font-mono" : ""}>{nodeId ?? t.panel.selectDevice}</span><ChevronsUpDown className="size-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72 p-0" align="start">
            <Command><CommandInput placeholder={t.panel.searchDevices} /><CommandList><CommandEmpty>{t.panel.noDeviceFound}</CommandEmpty><CommandGroup>
              {nodes.map((n) => <CommandItem key={n.node_id} value={`${n.node_id} ${n.location} ${n.type}`} onSelect={() => { onDeviceSelect(n.node_id); setSelectorOpen(false); }} className="min-h-11">
                <span className="font-mono">{n.node_id}</span><span className="ml-auto text-xs text-muted-foreground">{n.location}</span>
              </CommandItem>)}
            </CommandGroup></CommandList></Command>
          </PopoverContent>
        </Popover>
      </div>
      {state.kind === "idle" && (
        <div className="flex flex-col items-center justify-center gap-2 p-4 text-center text-sm text-muted-foreground">
          <Cpu className="size-6 opacity-60" />
          {t.panel.noDeviceSelected}
        </div>
      )}
      {state.kind === "loading" && <Skeleton />}
      {state.kind === "error" && (
        <div className="flex flex-col items-center justify-center gap-3 p-4 text-center text-sm">
          <AlertTriangle className="size-6 text-destructive" />
          <>
              <p className="text-muted-foreground">{state.notFound ? t.panel.unknownDevice : t.panel.loadFailed}</p>
              {nodeId && (
                <Button size="sm" variant="outline" onClick={() => load(nodeId)}>
                  <RotateCcw className="size-3.5" /> {t.panel.retry}
                </Button>
              )}
          </>
        </div>
      )}
      {state.kind === "ok" && <Detail detail={state.detail} onAsk={onAsk} onQuestion={onQuestion} />}
    </div>
  );
}
