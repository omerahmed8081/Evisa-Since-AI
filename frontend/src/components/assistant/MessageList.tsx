import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  KnowledgeCards,
  NoKnowledgeBox,
  linkifyDeviceChildren,
  type DeviceSelectHandler,
} from "@/components/KnowledgeCard";
import type { ChatMessage } from "@/lib/chat-store";
import type { Verdict } from "@/api/types";
import { cn } from "@/lib/utils";

function Typing() {
  return (
    <div className="flex gap-1 py-1" aria-label="Assistant is typing">
      {[0, 150, 300].map((d) => (
        <span
          key={d}
          className="typing-dot size-1.5 rounded-full bg-muted-foreground"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
    </div>
  );
}

function Bot({
  m,
  question,
  onRetry,
  canRetry,
  onDeviceSelect,
  onVerdict,
}: {
  m: ChatMessage;
  question?: string | undefined;
  onRetry: () => void;
  canRetry: boolean;
  onDeviceSelect?: DeviceSelectHandler | undefined;
  onVerdict?: ((assertionId: string, v: Verdict) => void) | undefined;
}) {
  const streaming = m.status === "streaming";
  return (
    <div className="animate-msg-in max-w-[44rem]">
      {m.status === "waiting" && !m.text ? (
        <Typing />
      ) : (
        // react-markdown never renders raw HTML, so output is sanitized.
        <div className={cn("prose-chat text-[15px] leading-relaxed", streaming && "[&>*:last-child]:stream-caret")}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              p: ({ children }) => <p>{linkifyDeviceChildren(children, onDeviceSelect)}</p>,
              li: ({ children }) => <li>{linkifyDeviceChildren(children, onDeviceSelect)}</li>,
            }}
          >
            {m.text}
          </ReactMarkdown>
        </div>
      )}
      {m.status === "stopped" && <p className="mt-2 text-xs text-muted-foreground">Stopped.</p>}
      {m.status === "error" && (
        <div className="mt-3 flex flex-wrap items-center gap-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertTriangle className="size-4" />
          <span className="flex-1">{m.error ?? "Something went wrong."}</span>
          <Button size="sm" variant="outline" onClick={onRetry} disabled={!canRetry}>
            <RotateCcw className="size-3.5" /> Retry
          </Button>
        </div>
      )}
      {m.status === "done" &&
        m.cards &&
        (m.cards.length ? (
          <KnowledgeCards
            cards={m.cards}
            onDeviceSelect={onDeviceSelect}
            messageId={m.messageId}
            verdicts={m.verdicts}
            onVerdict={onVerdict}
          />
        ) : (
          <NoKnowledgeBox question={question} />
        ))}
    </div>
  );
}

export function MessageList({
  messages,
  busy,
  onRetry,
  onDeviceSelect,
  onVerdict,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onRetry: (id: string) => void;
  onDeviceSelect?: DeviceSelectHandler;
  onVerdict?: (botId: string, assertionId: string, v: Verdict) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const last = messages.at(-1);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, last?.text.length, last?.status]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6">
      {messages.map((m, i) =>
        m.role === "user" ? (
          <div key={m.id} className="animate-msg-in flex flex-col items-end gap-1">
            {m.nodeId && <span className="font-mono text-[11px] text-muted-foreground">{m.nodeId}</span>}
            <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-user-bubble px-4 py-2.5 text-[15px] text-user-bubble-foreground">
              {m.text}
            </div>
          </div>
        ) : (
          <Bot
            key={m.id}
            m={m}
            question={messages
              .slice(0, i)
              .reverse()
              .find((x) => x.role === "user")?.text}
            onRetry={() => onRetry(m.id)}
            canRetry={!busy}
            onDeviceSelect={onDeviceSelect}
            onVerdict={onVerdict ? (assertionId, v) => onVerdict(m.id, assertionId, v) : undefined}
          />
        ),
      )}
      <div ref={end} />
    </div>
  );
}
