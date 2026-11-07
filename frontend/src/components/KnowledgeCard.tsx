import { Children, cloneElement, isValidElement, useState, type ReactNode } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  ArrowUpCircle,
  Ban,
  BellOff,
  CheckCircle2,
  ChevronDown,
  Clock,
  Copy,
  Cpu,
  HelpCircle,
  KeyRound,
  Lightbulb,
  Mail,
  MessageCircle,
  MessageSquare,
  Pencil,
  Phone,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { KnowledgeCard as KnowledgeCardData, KnowledgeSource, RelatedFailed, Verdict } from "@/api/types";
import { FeedbackBar } from "@/components/FeedbackBar";
import { en, fi, useLanguage, useT, type Lang } from "@/i18n";
import { splitDeviceRefs } from "@/lib/device-refs";
import { actionText, avoidText } from "@/lib/vocabulary";
import { cn } from "@/lib/utils";

export type DeviceSelectHandler = (nodeId: string) => void;

/** "12 Mar 2025" (en) / "12.3.2025" (fi), Europe/Helsinki. */
export function formatCardDate(ts: string | undefined, lang: Lang = "en"): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return new Intl.DateTimeFormat(lang === "fi" ? "fi-FI" : "en-GB", {
    timeZone: "Europe/Helsinki",
    day: "numeric",
    month: lang === "fi" ? "numeric" : "short",
    year: "numeric",
  }).format(d);
}

/** Monospace device button; clicking selects the device and opens the device panel. */
export function DeviceChip({ id, onSelect }: { id: string; onSelect?: DeviceSelectHandler | undefined }) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(id)}
      className="inline-flex items-center whitespace-nowrap rounded border border-primary/30 bg-accent px-1.5 py-px align-baseline font-mono text-[0.82em] font-medium text-accent-foreground transition hover:bg-primary hover:text-primary-foreground"
    >
      {id}
    </button>
  );
}

export function TextWithDevices({ text, onDeviceSelect }: { text: string; onDeviceSelect?: DeviceSelectHandler | undefined }) {
  return (
    <>
      {splitDeviceRefs(text ?? "").map((seg, i) =>
        seg.kind === "device" ? (
          <DeviceChip key={i} id={seg.value} onSelect={onDeviceSelect} />
        ) : (
          <span key={i}>{seg.value}</span>
        ),
      )}
    </>
  );
}

/** Recursively swap device IDs inside rendered markdown children for chips. */
export function linkifyDeviceChildren(children: ReactNode, onDeviceSelect?: DeviceSelectHandler | undefined): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child === "string") return <TextWithDevices text={child} onDeviceSelect={onDeviceSelect} />;
    if (isValidElement<{ children?: ReactNode }>(child) && child.props.children != null) {
      return cloneElement(child, undefined, linkifyDeviceChildren(child.props.children, onDeviceSelect));
    }
    return child;
  });
}

const TYPE_ICONS: Record<string, LucideIcon> = {
  troubleshooting_rule: Wrench,
  warning: BellOff,
  known_false_alarm: BellOff,
  device_fact: Cpu,
  hardware_compatibility: Cpu,
  procedure: Lightbulb,
  practical_tip: Lightbulb,
  access_info: KeyRound,
};

/** Knowledge-type badge meta in the active language. */
export function typeMeta(type: string, lang: Lang = "en"): { label: string; icon: LucideIcon } {
  const labels = (lang === "fi" ? fi : en).card.types as Record<string, string>;
  return { label: labels[type] ?? (type ?? "").replace(/_/g, " "), icon: TYPE_ICONS[type] ?? Wrench };
}

interface StatusMeta {
  label: string;
  icon: LucideIcon;
  className: string;
}

const STATUS_STYLE: Record<string, { icon: LucideIcon; className: string }> = {
  confirmed: { icon: CheckCircle2, className: "bg-success/15 text-success" },
  disputed: { icon: AlertTriangle, className: "bg-warning/20 text-warning-foreground dark:text-warning" },
  superseded: { icon: Clock, className: "bg-muted text-muted-foreground" },
  outdated: { icon: Clock, className: "bg-muted text-muted-foreground" },
  unconfirmed: { icon: HelpCircle, className: "bg-secondary text-secondary-foreground" },
};

/** Status badge meta; unknown statuses fall back to "Unconfirmed". */
export function statusMeta(status: string, lang: Lang = "en"): StatusMeta {
  const labels = (lang === "fi" ? fi : en).card.status as Record<string, string>;
  const style = STATUS_STYLE[status] ?? STATUS_STYLE["unconfirmed"]!;
  return { label: labels[status] ?? labels["unconfirmed"]!, ...style };
}

/** Outdated cards are greyed out and carry the 🕓 badge. */
export function isOutdated(status: string): boolean {
  return status === "outdated" || status === "superseded";
}

const SOURCE_ICONS: Record<string, LucideIcon> = {
  teams: MessageSquare,
  email: Mail,
  call: Phone,
  feedback: MessageCircle,
  manual: Pencil,
};

function sourceMeta(type: string, lang: Lang) {
  const labels = (lang === "fi" ? fi : en).card.sourceTypes as Record<string, string>;
  return { label: labels[type] ?? type, icon: SOURCE_ICONS[type] ?? Pencil };
}

function SectionTitle({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground", className)}>
      {children}
    </p>
  );
}

function SourceChip({ source }: { source: KnowledgeSource }) {
  const [open, setOpen] = useState(false);
  const { lang } = useLanguage();
  const meta = sourceMeta(source.source_type, lang);
  const Icon = meta.icon;
  const quote = source.excerpt ?? source.note;
  return (
    <div className="min-w-0 max-w-full">
      <button
        type="button"
        onClick={() => quote && setOpen((o) => !o)}
        className={cn(
          "inline-flex max-w-full items-center gap-1.5 rounded-full border bg-card px-2.5 py-1 text-xs text-muted-foreground transition",
          quote && "hover:-translate-y-0.5 hover:text-foreground hover:shadow-md",
        )}
      >
        <Icon className="size-3.5 shrink-0" />
        <span className="truncate">
          {meta.label} · {source.author} · {formatCardDate(source.timestamp, lang)}
        </span>
      </button>
      <div
        className={cn(
          "grid transition-all duration-300 ease-out",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
        )}
      >
        <div className="overflow-hidden">
          {quote && (
            <blockquote className="mt-1.5 border-l-2 border-border pl-3 text-xs italic leading-relaxed text-muted-foreground">
              {quote}
            </blockquote>
          )}
        </div>
      </div>
    </div>
  );
}

function Sources({ sources }: { sources: KnowledgeSource[] }) {
  const [showAll, setShowAll] = useState(false);
  const t = useT();
  if (!sources.length) return null;
  const visible = showAll ? sources : sources.slice(0, 3);
  return (
    <section>
      <SectionTitle>{t.card.sources}</SectionTitle>
      <div className="flex flex-wrap items-start gap-1.5">
        {visible.map((s) => (
          <SourceChip key={s.source_id} source={s} />
        ))}
        {!showAll && sources.length > 3 && (
          <button
            type="button"
            onClick={() => setShowAll(true)}
            className="rounded-full border border-dashed px-2.5 py-1 text-xs text-muted-foreground transition hover:text-foreground"
          >
            {t.card.moreSources(sources.length - 3)}
          </button>
        )}
      </div>
    </section>
  );
}

function DetailsBlock({ details }: { details: string }) {
  const t = useT();
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(details);
      toast.success(t.card.copied, { duration: 1500 });
    } catch {
      toast.error(t.card.copyFailed, { duration: 1500 });
    }
  };
  return (
    <div className="flex items-start gap-2 rounded-md border bg-muted/60 px-3 py-2">
      <span className="min-w-0 flex-1 whitespace-pre-wrap font-mono text-xs leading-relaxed">{details}</span>
      <button
        type="button"
        onClick={copy}
        aria-label={t.card.copyDetails}
        className="-mr-1 -mt-0.5 shrink-0 rounded p-1 text-muted-foreground transition hover:bg-background hover:text-foreground"
      >
        <Copy className="size-3.5" />
      </button>
    </div>
  );
}

function Steps({ card }: { card: KnowledgeCardData }) {
  const t = useT();
  const { lang } = useLanguage();
  if (!(card.actions ?? []).length) return null;
  return (
    <section>
      <SectionTitle>{t.card.steps}</SectionTitle>
      <ol className="space-y-1.5">
        {(card.actions ?? []).map((a, i) => (
          <li key={a.code} className="animate-msg-in flex gap-2 text-sm" style={{ animationDelay: `${i * 50}ms` }}>
            <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-primary/15 font-mono text-[11px] font-medium text-primary">
              {i + 1}
            </span>
            <span>{actionText(a, lang)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function AvoidList({ card }: { card: KnowledgeCardData }) {
  const t = useT();
  const { lang } = useLanguage();
  if (!(card.avoid ?? []).length) return null;
  return (
    <section>
      <SectionTitle className="text-destructive">{t.card.avoid}</SectionTitle>
      <ul className="space-y-1">
        {(card.avoid ?? []).map((a) => (
          <li key={a.code} className="flex gap-2 text-sm text-destructive">
            <Ban className="mt-0.5 size-4 shrink-0" />
            <span>{avoidText(a, lang)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ScopeLine({ card, onDeviceSelect }: { card: KnowledgeCardData; onDeviceSelect?: DeviceSelectHandler | undefined }) {
  const t = useT();
  // "Only the device(s) …" scope just repeats the Seen-on chips — skip it.
  const scopeText = card.scope_text?.startsWith("Only the device") ? undefined : card.scope_text;
  if (!scopeText && !(card.observed_on ?? []).length) return null;
  return (
    <section className="text-sm">
      {scopeText && (
        <p>
          <span className="text-muted-foreground">{t.card.appliesTo} </span>
          {scopeText}
        </p>
      )}
      {(card.observed_on ?? []).length > 0 && (
        <p className="mt-1 flex flex-wrap items-center gap-1">
          <span className="text-muted-foreground">{t.card.seenOn}</span>
          {(card.observed_on ?? []).map((id) => (
            <DeviceChip key={id} id={id} onSelect={onDeviceSelect} />
          ))}
        </p>
      )}
    </section>
  );
}

function ValidLine({ card }: { card: KnowledgeCardData }) {
  const t = useT();
  const { lang } = useLanguage();
  if (!card.valid_from) return null;
  if (card.valid_to) {
    const text = t.card.validUntil(formatCardDate(card.valid_from, lang), formatCardDate(card.valid_to, lang));
    const to = formatCardDate(card.valid_to, lang);
    const [before, after] = text.split(to);
    return (
      <p className="text-xs text-muted-foreground">
        {before}
        <s>{to}</s>
        {after}
      </p>
    );
  }
  return <p className="text-xs text-muted-foreground">{t.card.validSince(formatCardDate(card.valid_from, lang))}</p>;
}

/** Compact muted section for things that were tried and failed — never styled as advice. */
function WhatDidntWork({ items }: { items: RelatedFailed[] }) {
  const t = useT();
  const { lang } = useLanguage();
  if (!items.length) return null;
  return (
    <section className="rounded-md bg-muted/50 px-3 py-2">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{t.card.whatDidntWork}</p>
      <ul className="mt-1.5 space-y-1.5">
        {items.map((f) => {
          const Icon = sourceMeta(f.source_type, lang).icon;
          return (
            <li key={f.assertion_id} className="flex gap-2 text-sm text-muted-foreground">
              <X className="mt-0.5 size-4 shrink-0" />
              <span>
                {f.summary}{" "}
                <span className="ml-1 inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-px align-middle text-[11px]">
                  <Icon className="size-3" /> {f.author} · {formatCardDate(f.date, lang)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** A top-level card whose outcome is "failed" renders as a compact "What didn't work" card. */
function FailedCard({ card }: { card: KnowledgeCardData }) {
  const t = useT();
  return (
    <div className="rounded-lg border bg-muted/40 p-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{t.card.whatDidntWork}</p>
      <p className="mt-1 flex gap-2 text-sm text-muted-foreground">
        <X className="mt-0.5 size-4 shrink-0" />
        {card.summary}
      </p>
      <div className="mt-2">
        <Sources sources={card.sources ?? []} />
      </div>
    </div>
  );
}

/** One side of a disputed card, labelled with the expert who said it. */
function Opinion({ card }: { card: KnowledgeCardData }) {
  const t = useT();
  const author = card.sources?.[0]?.author ?? t.card.expert;
  return (
    <div className="min-w-0 rounded-md border bg-background/60 p-3">
      <p className="text-xs font-medium text-muted-foreground">{t.card.says(author)}</p>
      <p className="mt-1 text-sm font-medium leading-snug">{card.summary}</p>
      <div className="mt-2 space-y-2.5">
        <Steps card={card} />
        {card.details && <DetailsBlock details={card.details} />}
        <Sources sources={card.sources ?? []} />
      </div>
    </div>
  );
}

/**
 * Per-device note under a card, same look everywhere:
 * "Not needed…" = grey outdated note, "Not yet…" = blue "Upgrade fixes this" note.
 */
export function ScopeNote({ card, className }: { card: KnowledgeCardData; className?: string }) {
  const t = useT();
  const note = card.scope_note;
  if (!note) return null;
  if (note.startsWith("Not needed")) {
    return (
      <span
        className={cn(
          "flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1.5 text-xs text-muted-foreground",
          className,
        )}
      >
        <Clock className="size-3.5 shrink-0" /> {note}
      </span>
    );
  }
  if (note.startsWith("Not yet")) {
    return (
      <span
        className={cn(
          "flex items-start gap-1.5 rounded-md border border-primary/30 bg-accent/60 px-2.5 py-1.5 text-xs text-accent-foreground",
          className,
        )}
      >
        <ArrowUpCircle className="mt-px size-3.5 shrink-0" />
        <span>
          <span className="font-medium">{t.card.upgradeFixes}</span> {note}
        </span>
      </span>
    );
  }
  return (
    <span
      className={cn("flex items-start rounded-md bg-muted/60 px-2.5 py-1.5 text-xs text-muted-foreground", className)}
    >
      {note}
    </span>
  );
}

export function KnowledgeCard({
  card,
  onDeviceSelect,
  messageId,
  verdict,
  onVerdict,
}: {
  card: KnowledgeCardData;
  onDeviceSelect?: DeviceSelectHandler | undefined;
  messageId?: string | undefined;
  verdict?: Verdict | undefined;
  onVerdict?: ((v: Verdict) => void) | undefined;
}) {
  const t = useT();
  const { lang } = useLanguage();
  if (card.outcome === "failed") return <FailedCard card={card} />;

  const disputed = card.status === "disputed";
  const showOpinions = disputed && !!card.conflicts_with?.length;
  const notNeeded = card.scope_note?.startsWith("Not needed") ?? false;
  const notYet = !notNeeded && (card.scope_note?.startsWith("Not yet") ?? false);
  const greyed = isOutdated(card.status) || notNeeded;
  const type = typeMeta(card.knowledge_type, lang);
  const status = statusMeta(card.status, lang);
  const TypeIcon = type.icon;
  const StatusIcon = status.icon;
  const pct = Math.round((card.confidence ?? 0) * 100);

  return (
    <article
      className={cn(
        "animate-msg-in rounded-lg border bg-card p-4 shadow-sm",
        disputed && "border-warning/60",
        greyed && "opacity-70",
      )}
    >
      {notNeeded && <ScopeNote card={card} className="mb-2" />}

      <header className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-secondary-foreground">
          <TypeIcon className="size-3.5" /> {type.label}
        </span>
        {disputed ? (
          <span className="inline-flex items-center gap-1.5 rounded-md bg-warning/20 px-2 py-0.5 text-xs font-medium text-warning-foreground dark:text-warning">
            <AlertTriangle className="size-3.5" /> {t.card.expertsDisagree}
          </span>
        ) : (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium",
              status.className,
            )}
          >
            <StatusIcon className="size-3.5" /> {status.label}
          </span>
        )}
        <span className="ml-auto inline-flex items-center gap-2 text-xs text-muted-foreground">
          <span className="hidden h-1 w-16 overflow-hidden rounded-full bg-muted sm:block">
            <span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
          </span>
          {pct}% · {t.card.sourceCount((card.sources ?? []).length)}
        </span>
      </header>

      {/* Disputed cards speak through the side-by-side opinions — no repeated summary on top. */}
      {!showOpinions && (
        <>
          {card.how_it_applies && <p className="mt-2 text-xs italic text-muted-foreground">{card.how_it_applies}</p>}
          <p className="mt-1.5 text-sm font-medium leading-snug">{card.summary}</p>
        </>
      )}

      {notYet && <ScopeNote card={card} className="mt-2" />}

      <div className="mt-3 space-y-3">
        {showOpinions ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {[...(card.conflicts_with ?? []), card].map((c) => (
              <Opinion key={c.assertion_id} card={c} />
            ))}
          </div>
        ) : (
          <>
            <Steps card={card} />
            <AvoidList card={card} />
            {card.details && <DetailsBlock details={card.details} />}
          </>
        )}
        <ScopeLine card={card} onDeviceSelect={onDeviceSelect} />
        <ValidLine card={card} />
        <Sources sources={card.sources ?? []} />
        {card.related_failed && <WhatDidntWork items={card.related_failed} />}
      </div>

      <footer>
        <FeedbackBar assertionId={card.assertion_id} messageId={messageId} verdict={verdict} onVerdict={onVerdict} />
      </footer>
    </article>
  );
}

/** Card list under a bot answer: first 2 cards, then a "Show N more tips" button. */
export function KnowledgeCards({
  cards,
  onDeviceSelect,
  messageId,
  verdicts,
  onVerdict,
}: {
  cards: KnowledgeCardData[];
  onDeviceSelect?: DeviceSelectHandler | undefined;
  messageId?: string | undefined;
  verdicts?: Record<string, Verdict> | undefined;
  onVerdict?: ((assertionId: string, v: Verdict) => void) | undefined;
}) {
  const [expanded, setExpanded] = useState(false);
  const t = useT();
  if (!cards.length) return null;
  const visible = expanded ? cards : cards.slice(0, 2);
  return (
    <div className="mt-3 space-y-3">
      {visible.map((c) => (
        <KnowledgeCard
          key={c.assertion_id}
          card={c}
          onDeviceSelect={onDeviceSelect}
          messageId={messageId}
          verdict={verdicts?.[c.assertion_id]}
          onVerdict={onVerdict ? (v) => onVerdict(c.assertion_id, v) : undefined}
        />
      ))}
      {!expanded && cards.length > 2 && (
        <Button variant="outline" size="sm" onClick={() => setExpanded(true)}>
          <ChevronDown className="size-4" /> {t.card.showMore(cards.length - 2)}
        </Button>
      )}
    </div>
  );
}

/** Shown when the service returns no cards at all. */
export function NoKnowledgeBox({ question }: { question?: string | undefined }) {
  const t = useT();
  const ask = async () => {
    try {
      await navigator.clipboard.writeText(question ?? "");
      toast.success(t.card.questionCopied, { duration: 1500 });
    } catch {
      toast.error(t.card.copyFailed, { duration: 1500 });
    }
  };
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-dashed bg-muted/40 px-4 py-3 text-sm text-muted-foreground">
      <span className="min-w-40 flex-1">{t.card.noKnowledge}</span>
      <Button size="sm" variant="outline" onClick={ask}>
        <Copy className="size-3.5" /> {t.card.askExpert}
      </Button>
    </div>
  );
}
