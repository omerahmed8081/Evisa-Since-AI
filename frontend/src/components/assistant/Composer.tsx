import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Loader2, Square, X, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

interface Props {
  mobile: boolean;
  onOpenPanel: () => void;
  nodeId?: string | undefined;
  onNodeChange: (id?: string) => void;
  busy: boolean;
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  /** External text injection (e.g. "Ask about this device"); nonce retriggers. */
  prefill?: { text: string; nonce: number } | null;
}

export function Composer({ mobile, onOpenPanel, nodeId, onNodeChange, busy, streaming, onSend, onStop, prefill }: Props) {
  const t = useT();
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!prefill) return;
    setText(prefill.text);
    ta.current?.focus();
  }, [prefill]);

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "auto";
    const line = parseFloat(getComputedStyle(el).lineHeight) || 22;
    el.style.height = `${Math.min(el.scrollHeight, line * 6 + 16)}px`;
  }, [text]);

  const submit = () => {
    if (!text.trim() || busy) return;
    onSend(text);
    setText("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-3 pb-3 sm:px-4 sm:pb-4">
      <div className="rounded-2xl border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring/40">
        <textarea
          ref={ta}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          placeholder={nodeId ? t.composer.placeholderDevice(nodeId) : t.composer.placeholder}
          aria-label={t.composer.message}
          className="block max-h-60 w-full resize-none bg-transparent px-4 py-2 text-[15px] leading-[22px] outline-none placeholder:text-muted-foreground"
        />
        <div className="flex items-center gap-2 px-2 pb-2">
          {nodeId ? (
            <span className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 font-mono text-xs text-secondary-foreground">
              <Cpu className="size-3.5" />
              {nodeId}
              <Button variant="ghost" size="icon" aria-label={t.composer.removeDevice} onClick={() => onNodeChange(undefined)} className="ml-0.5 min-h-11 min-w-11 hover:text-destructive">
                <X className="size-3.5" />
              </Button>
            </span>
          ) : mobile ? (
            <Button variant="link" onClick={onOpenPanel} className="text-xs">{t.composer.selectDevice}</Button>
          ) : null}
          <div className="ml-auto">
            {streaming ? (
              <Button size="icon" variant="secondary" aria-label={t.composer.stop} onClick={onStop} className="min-h-11 min-w-11 rounded-full active:scale-[0.96]">
                <Square className="size-3.5 fill-current" />
              </Button>
            ) : (
              <Button
                size="icon"
                aria-label={t.composer.send}
                onClick={submit}
                disabled={!text.trim() || busy}
                className={cn("min-h-11 min-w-11 rounded-full transition-transform active:scale-[0.96]")}
              >
                {busy ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
