import { useEffect, useState } from "react";
import {
  MessageSquarePlus,
  Moon,
  Network,
  PanelLeft,
  PanelRight,
  Settings,
  Sun,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { getClient, useApiSettings, type Node } from "@/api";
import { useChat } from "@/hooks/use-chat";
import { useApiStatus, type ApiStatus } from "@/hooks/use-api-status";
import { useIsMobile } from "@/hooks/use-mobile";
import { useStats } from "@/hooks/use-stats";
import type { StoredChat } from "@/lib/chat-store";
import { cn } from "@/lib/utils";
import { Composer } from "./Composer";
import { DevicePanel } from "./DevicePanel";
import { EmptyState } from "./EmptyState";
import { MessageList } from "./MessageList";
import { SettingsDialog } from "./SettingsDialog";

const statusMeta: Record<ApiStatus, { label: string; dot: string }> = {
  live: { label: "Live", dot: "bg-success" },
  mock: { label: "Mock", dot: "bg-muted-foreground" },
  offline: { label: "Offline", dot: "bg-destructive" },
  checking: { label: "Checking", dot: "bg-warning animate-pulse" },
};

function useTheme() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("theme");
      setDark(saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches);
    } catch {
      /* ignore */
    }
  }, []);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);
  const toggle = () =>
    setDark((d) => {
      try {
        localStorage.setItem("theme", d ? "light" : "dark");
      } catch {
        /* ignore */
      }
      return !d;
    });
  return { dark, toggle };
}

function RecentChats({
  chats,
  activeId,
  onNew,
  onOpen,
}: {
  chats: StoredChat[];
  activeId: string;
  onNew: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <Button onClick={onNew} variant="outline" className="justify-start">
        <MessageSquarePlus className="size-4" /> New chat
      </Button>
      <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Recent chats</p>
      <nav className="-mx-1 flex-1 space-y-0.5 overflow-y-auto px-1">
        {chats.length === 0 && <p className="px-2 text-sm text-muted-foreground">No chats yet.</p>}
        {chats.map((c) => (
          <button
            key={c.id}
            onClick={() => onOpen(c.id)}
            className={cn(
              "block w-full truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-sidebar-accent",
              c.id === activeId && "bg-sidebar-accent font-medium",
            )}
          >
            {c.title}
          </button>
        ))}
      </nav>
    </div>
  );
}

/** Small muted knowledge-base counter, hidden below 640px. */
function StatsCounter() {
  const stats = useStats();
  if (!stats) return null;
  return (
    <span className="mr-1 hidden text-xs text-muted-foreground sm:block">
      {stats.valid_assertions} tips · {stats.devices} devices · {stats.sources} sources
    </span>
  );
}

export function AssistantApp() {
  const chat = useChat();
  const status = useApiStatus();
  const settings = useApiSettings();
  const isMobile = useIsMobile();
  const { dark, toggle } = useTheme();
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [leftSheet, setLeftSheet] = useState(false);
  const [rightSheet, setRightSheet] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [nodeId, setNodeId] = useState<string | undefined>();
  const [prefill, setPrefill] = useState<{ text: string; nonce: number } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getClient(settings)
      .nodes(ctrl.signal)
      .then(setNodes)
      .catch(() => setNodes([]));
    return () => ctrl.abort();
  }, [settings, status === "live"]); // eslint-disable-line react-hooks/exhaustive-deps

  const last = chat.messages.at(-1);
  const streaming = chat.busy && (last?.status === "streaming" || last?.status === "waiting");
  const sm = statusMeta[status];

  // Device chips in answers and cards: select the device and reveal the panel.
  const handleDeviceSelect = (id: string) => {
    setNodeId(id);
    if (isMobile) setRightSheet(true);
    else setRightOpen(true);
  };

  // "Ask about this device": select it and seed the composer with "<id>: ".
  const handleAsk = (id: string) => {
    setNodeId(id);
    setPrefill({ text: `${id}: `, nonce: Date.now() });
    if (isMobile) setRightSheet(false);
  };

  const panel = <DevicePanel nodeId={nodeId} onAsk={handleAsk} onDeviceSelect={handleDeviceSelect} />;

  const recent = (
    <RecentChats
      chats={chat.chats}
      activeId={chat.chatId}
      onNew={() => {
        chat.newChat();
        setLeftSheet(false);
      }}
      onOpen={(id) => {
        chat.openChat(id);
        setLeftSheet(false);
      }}
    />
  );

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b px-2 sm:px-3">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle chats"
          onClick={() => (isMobile ? setLeftSheet(true) : setLeftOpen((o) => !o))}
        >
          <PanelLeft className="size-4" />
        </Button>
        <div className="flex min-w-0 items-center gap-2">
          <Network className="size-5 shrink-0 text-primary" />
          <h1 className="truncate text-sm font-semibold sm:text-base">Network Knowledge Assistant</h1>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <StatsCounter />
          <span
            className="mr-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs text-muted-foreground"
            title={`API status: ${sm.label}`}
          >
            <span className={cn("size-2 rounded-full", sm.dot)} />
            {sm.label}
          </span>
          <Button variant="ghost" size="icon" aria-label="Settings" onClick={() => setSettingsOpen(true)}>
            <Settings className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label="Toggle dark mode" onClick={toggle}>
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Toggle device panel"
            onClick={() => (isMobile ? setRightSheet(true) : setRightOpen((o) => !o))}
          >
            <PanelRight className="size-4" />
          </Button>
        </div>
      </header>

      {status === "offline" && (
        <div className="flex items-center justify-center gap-2 border-b border-destructive/30 bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
          <WifiOff className="size-4" /> Can't reach the knowledge service. Retrying…
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {!isMobile && leftOpen && (
          <aside className="w-64 shrink-0 border-r bg-sidebar text-sidebar-foreground">{recent}</aside>
        )}

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            {chat.messages.length === 0 ? (
              <EmptyState onPick={(t) => chat.send(t, nodeId)} />
            ) : (
              <MessageList
                messages={chat.messages}
                busy={chat.busy}
                onRetry={chat.retry}
                onDeviceSelect={handleDeviceSelect}
                onVerdict={chat.setVerdict}
              />
            )}
          </div>
          <Composer
            nodes={nodes}
            nodeId={nodeId}
            onNodeChange={setNodeId}
            busy={chat.busy}
            streaming={streaming}
            onSend={(t) => chat.send(t, nodeId)}
            onStop={() => chat.stop()}
            prefill={prefill}
          />
        </main>

        {!isMobile && rightOpen && (
          <aside className="w-80 shrink-0 border-l bg-sidebar text-sidebar-foreground">{panel}</aside>
        )}
      </div>

      <Sheet open={isMobile && leftSheet} onOpenChange={setLeftSheet}>
        <SheetContent side="left" className="w-72 bg-sidebar p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Chats</SheetTitle>
          </SheetHeader>
          <div className="pt-10 h-full">{recent}</div>
        </SheetContent>
      </Sheet>
      <Sheet open={isMobile && rightSheet} onOpenChange={setRightSheet}>
        <SheetContent side="right" className="w-80 bg-sidebar p-0">
          <SheetHeader className="sr-only">
            <SheetTitle>Device</SheetTitle>
          </SheetHeader>
          <div className="h-full pt-8">{panel}</div>
        </SheetContent>
      </Sheet>

      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
    </div>
  );
}
