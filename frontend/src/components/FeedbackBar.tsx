import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Send, SkipForward, ThumbsDown, ThumbsUp, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getClient, type Verdict } from "@/api";
import { refreshStats } from "@/hooks/use-stats";
import { useT } from "@/i18n";
import { cn } from "@/lib/utils";

export function FeedbackBar({
  assertionId,
  messageId,
  verdict,
  onVerdict,
}: {
  assertionId: string;
  /** Server message id of the answer this card came with (undefined in the device panel). */
  messageId?: string | undefined;
  verdict?: Verdict | undefined;
  onVerdict?: ((v: Verdict) => void) | undefined;
}) {
  const t = useT();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);
  const [comment, setComment] = useState("");
  const [commentSent, setCommentSent] = useState(false);

  const VERDICTS: { v: Verdict; label: string; icon: LucideIcon }[] = [
    { v: "worked", label: t.feedback.worked, icon: ThumbsUp },
    { v: "failed", label: t.feedback.failed, icon: ThumbsDown },
    { v: "skip", label: t.feedback.skip, icon: SkipForward },
  ];

  const post = async (v: Verdict, text: string | null) => {
    setPending(true);
    setError(false);
    try {
      const res = await getClient().feedback({
        message_id: messageId,
        assertion_id: assertionId,
        verdict: v,
        comment: text,
      });
      refreshStats();
      if (text != null) {
        setCommentSent(true);
        setComment("");
        if (res.comment_queued) toast.success(t.feedback.noteQueued);
        else toast.success(t.feedback.thanks);
      }
      return true;
    } catch {
      setError(true);
      return false;
    } finally {
      setPending(false);
    }
  };

  const choose = async (v: Verdict) => {
    if (pending) return;
    const ok = await post(v, null);
    if (ok) onVerdict?.(v);
  };

  const sendComment = async () => {
    const text = comment.trim();
    if (!text || !verdict || pending) return;
    await post(verdict, text);
  };

  return (
    <div className="mt-3 border-t pt-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {VERDICTS.map(({ v, label, icon: Icon }) => {
          const chosen = verdict === v;
          return (
            <button
              key={v}
              type="button"
              aria-pressed={chosen}
              disabled={pending}
              onClick={() => choose(v)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition disabled:opacity-50",
                chosen
                  ? "border-primary bg-primary/15 font-medium text-primary"
                  : verdict
                    ? "text-muted-foreground/70 hover:text-muted-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
              )}
            >
              {pending && chosen ? <Loader2 className="size-3.5 animate-spin" /> : <Icon className="size-3.5" />}
              {label}
            </button>
          );
        })}
        {error && (
          <button
            type="button"
            onClick={() => verdict && choose(verdict)}
            className="text-xs text-destructive underline underline-offset-2 hover:no-underline"
          >
            {t.feedback.saveFailed}
          </button>
        )}
      </div>
      {verdict && !commentSent && (
        <div className="mt-2 flex items-center gap-2">
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendComment()}
            placeholder={t.feedback.commentPlaceholder}
            className="h-8 min-w-0 flex-1 rounded-md border bg-background px-2.5 text-xs outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40"
          />
          <Button size="sm" variant="outline" className="h-8" onClick={sendComment} disabled={pending || !comment.trim()}>
            {pending ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />} {t.feedback.send}
          </Button>
        </div>
      )}
    </div>
  );
}
