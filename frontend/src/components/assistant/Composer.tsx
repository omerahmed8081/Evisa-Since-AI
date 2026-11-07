import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, ChevronsUpDown, Loader2, Square, X, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import type { Node } from "@/api/types";
import { findDeviceIds } from "@/lib/chat-store";
import { cn } from "@/lib/utils";

interface Props {
  nodes: Node[];
  nodeId?: string | undefined;
  onNodeChange: (id?: string) => void;
  busy: boolean;
  streaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  /** External text injection (e.g. "Ask about this device"); nonce retriggers. */
  prefill?: { text: string; nonce: number } | null;
}

export function Composer({ nodes, nodeId, onNodeChange, busy, streaming, onSend, onStop, prefill }: Props) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
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

  const suggestion = useMemo(() => {
    const ids = findDeviceIds(text).filter((id) => id !== nodeId && nodes.some((n) => n.node_id === id));
    return ids[0];
  }, [text, nodeId, nodes]);

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
      {suggestion && (
        <button
          onClick={() => onNodeChange(suggestion)}
          className="animate-msg-in mb-2 inline-flex items-center gap-1.5 rounded-full bg-accent px-3 py-1 text-xs text-accent-foreground hover:opacity-90"
        >
          <Cpu className="size-3.5" /> Select <span className="font-mono font-medium">{suggestion}</span> as
          device?
        </button>
      )}
      <div className="rounded-2xl border bg-card shadow-sm focus-within:ring-2 focus-within:ring-ring/40">
        <textarea
          ref={ta}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          placeholder="Describe the device and symptom…"
          className="block max-h-60 w-full resize-none bg-transparent px-4 py-2 text-[15px] leading-[22px] outline-none placeholder:text-muted-foreground"
        />
        <div className="flex items-center gap-2 px-2 pb-2">
          {nodeId ? (
            <span className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 font-mono text-xs text-secondary-foreground">
              <Cpu className="size-3.5" />
              {nodeId}
              <button aria-label="Remove device" onClick={() => onNodeChange(undefined)} className="ml-0.5 hover:text-destructive">
                <X className="size-3.5" />
              </button>
            </span>
          ) : (
            <Popover open={open} onOpenChange={setOpen}>
              <PopoverTrigger asChild>
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  <Cpu className="size-4" /> Device <ChevronsUpDown className="size-3.5 opacity-60" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-72 p-0" align="start">
                <Command>
                  <CommandInput placeholder="Search devices…" />
                  <CommandList>
                    <CommandEmpty>No device found.</CommandEmpty>
                    <CommandGroup>
                      {nodes.map((n) => (
                        <CommandItem
                          key={n.node_id}
                          value={`${n.node_id} ${n.location} ${n.type}`}
                          onSelect={() => {
                            onNodeChange(n.node_id);
                            setOpen(false);
                          }}
                        >
                          <span className="font-mono text-sm">{n.node_id}</span>
                          <span className="ml-auto text-xs text-muted-foreground">{n.location}</span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          )}
          <div className="ml-auto">
            {streaming ? (
              <Button size="icon" variant="secondary" aria-label="Stop" onClick={onStop} className="rounded-full active:scale-[0.96]">
                <Square className="size-3.5 fill-current" />
              </Button>
            ) : (
              <Button
                size="icon"
                aria-label="Send"
                onClick={submit}
                disabled={!text.trim() || busy}
                className={cn("rounded-full transition-transform active:scale-[0.96]")}
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
