import { useEffect, useState } from "react";
import { toast } from "sonner";
import type { NodeDetail } from "@/api/types";
import { deviceSuggestions } from "@/lib/device-suggestions";
import {
  MessageSquarePlus,
  Moon,
  Network,
  PanelLeft,
  PanelRight,
  Settings,
  Sun,
  Trash2,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { getClient, useApiSettings, type Node } from "@/api";
import { useChat } from "@/hooks/use-chat";
import { useLanguage, useT, type Lang } from "@/i18n";
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

const statusDot: Record<ApiStatus, string> = {
  live: "bg-success",
  mock: "bg-muted-foreground",
  offline: "bg-destructive",
  checking: "bg-warning animate-pulse",
};

/** EN | FI switch, shown in the header and inside the mobile chats sheet. */
function LanguageSwitch() {
  const { lang, setLang } = useLanguage();
  const t = useT();
  return (
    <span role="group" aria-label={t.language.label} className="inline-flex items-center rounded-md border text-xs">
      {(["en", "fi"] as Lang[]).map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={lang === l}
          onClick={() => setLang(l)}
          className={cn(
            "min-h-9 min-w-9 px-1.5 py-1 font-medium transition",
            lang === l ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {t.language[l]}
        </button>
      ))}
    </span>
  );
}

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
  onDelete,
  onDeleteAll,
}: {
  chats: StoredChat[];
  activeId: string;
  onNew: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
}) {
  const t = useT();
  const [confirmAll, setConfirmAll] = useState(false);
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <Button onClick={onNew} variant="outline" className="justify-start">
        <MessageSquarePlus className="size-4" /> {t.chats.newChat}
      </Button>
      <p className="px-2 pt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">{t.chats.recent}</p>
      <nav className="-mx-1 flex-1 space-y-0.5 overflow-y-auto px-1">
        {chats.length === 0 && <p className="px-2 text-sm text-muted-foreground">{t.chats.empty}</p>}
        {chats.map((c) => (
          <div key={c.id} className="group flex items-center">
            <button
              onClick={() => onOpen(c.id)}
              className={cn(
                "min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-sidebar-accent",
                c.id === activeId && "bg-sidebar-accent font-medium",
              )}
            >
              {c.title}
            </button>
            <button
              type="button"
              aria-label={t.chats.deleteChat(c.title)}
              onClick={() => onDelete(c.id)}
              className="ml-1 grid size-9 shrink-0 place-items-center rounded-md text-muted-foreground transition hover:bg-sidebar-accent hover:text-destructive focus-visible:opacity-100 [@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-focus-within:opacity-100 [@media(hover:hover)]:group-hover:opacity-100"
            >
              <Trash2 className="size-4" />
            </button>
          </div>
        ))}
      </nav>
      {chats.length > 0 && (
        <button
          type="button"
          onClick={() => setConfirmAll(true)}
          className="self-start rounded-md px-2 py-1.5 text-sm text-muted-foreground transition hover:text-destructive"
        >
          {t.chats.deleteAll}
        </button>
      )}
      <AlertDialog open={confirmAll} onOpenChange={setConfirmAll}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t.chats.deleteAllTitle}</AlertDialogTitle>
            <AlertDialogDescription>{t.chats.deleteAllBody}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t.chats.cancel}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={onDeleteAll}
            >
              {t.chats.confirmDeleteAll}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** Small muted knowledge-base counter, hidden below 640px. */
function StatsCounter() {
  const stats = useStats();
  const t = useT();
  if (!stats) return null;
  return (
    <span className="mr-1 hidden text-xs text-muted-foreground sm:block">
      {t.header.stats(stats.valid_assertions, stats.devices, stats.sources)}
    </span>
  );
}

export function AssistantApp() {
  const status = useApiStatus();
  const settings = useApiSettings();
  const isMobile = useIsMobile(1024);
  const { dark, toggle } = useTheme();
  const t = useT();
  const { lang } = useLanguage();
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [leftSheet, setLeftSheet] = useState(false);
  const [rightSheet, setRightSheet] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [nodeId, setNodeId] = useState<string | undefined>();
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const chat = useChat((meta) => {
    const id = meta.resolved_nodes[0];
    if (!id || (nodeId && !meta.ignored_selection)) return;
    setNodeId(id);
    if (window.matchMedia("(min-width: 1024px)").matches) setRightOpen(true);
    if (meta.ignored_selection) toast(t.header.switchedDevice(id));
  }, lang);
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
  const statusLabel = t.header.status[status];

  // Device chips in answers and cards: select the device and reveal the panel.
  const handleDeviceSelect = (id: string) => {
    setNodeId(id);
    if (isMobile) setRightSheet(true);
    else setRightOpen(true);
  };

  // Keep the device selected while starting a fresh conversation.
  const handleAsk = (id: string) => {
    setNodeId(id);
    chat.newChat();
    setPrefill({ text: "", nonce: Date.now() });
    if (isMobile) setRightSheet(false);
  };

  const panel = <DevicePanel nodeId={nodeId} nodes={nodes} onAsk={handleAsk} onDeviceSelect={setNodeId}
    onDetail={setDetail} onQuestion={(text) => { chat.send(text, nodeId); if (isMobile) setRightSheet(false); }} />;

  // Delete is browser-only: remove from list + storage, offer a 5s undo toast.
  const handleDeleteChat = (id: string) => {
    const removed = chat.deleteChat(id);
    if (!removed) return;
    toast(t.chats.deleted, {
      duration: 5000,
      action: { label: t.chats.undo, onClick: () => chat.restoreChat(removed.chat, removed.index) },
    });
  };

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
      onDelete={handleDeleteChat}
      onDeleteAll={chat.deleteAllChats}
    />
  );

  return (
    <div className="flex h-dvh flex-col bg-background text-foreground">
      <header className="flex h-14 shrink-0 items-center gap-2 border-b px-2 sm:px-3">
        <Button
          variant="ghost"
          size="icon"
          aria-label={t.header.toggleChats}
          onClick={() => (isMobile ? setLeftSheet(true) : setLeftOpen((o) => !o))}
        >
          <PanelLeft className="size-4" />
        </Button>
        <div className="flex min-w-0 items-center gap-2">
          <Network className="size-5 shrink-0 text-primary" />
          <div className="min-w-0 leading-tight">
            <h1 className="truncate text-sm font-semibold sm:text-base">{t.appName}</h1>
            <p className="hidden truncate text-xs text-muted-foreground sm:block">{t.header.subtitle}</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <StatsCounter />
          <LanguageSwitch />
          <span
            className="mr-1 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs text-muted-foreground"
            title={t.header.statusTitle(statusLabel)}
          >
            <span className={cn("size-2 rounded-full", statusDot[status])} />
            <span className="hidden sm:inline">{statusLabel}</span>
          </span>
          <Button variant="ghost" size="icon" aria-label={t.header.settings} onClick={() => setSettingsOpen(true)}>
            <Settings className="size-4" />
          </Button>
          <Button variant="ghost" size="icon" aria-label={t.header.toggleTheme} onClick={toggle}>
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label={t.header.togglePanel}
            onClick={() => (isMobile ? setRightSheet(true) : setRightOpen((o) => !o))}
          >
            <PanelRight className="size-4" />
          </Button>
        </div>
      </header>

      {status === "offline" && (
        <div className="flex items-center justify-center gap-2 border-b border-destructive/30 bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
          <WifiOff className="size-4" /> {t.header.offlineBanner}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {!isMobile && leftOpen && (
          <aside className="w-64 shrink-0 border-r bg-sidebar text-sidebar-foreground">{recent}</aside>
        )}

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            {chat.messages.length === 0 ? (
              <EmptyState nodeId={nodeId} questions={detail && detail.node.node_id === nodeId ? deviceSuggestions(detail, undefined, lang) : undefined} onPick={(text) => chat.send(text, nodeId)} />
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
            mobile={isMobile}
            onOpenPanel={() => setRightSheet(true)}
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
          <div className="absolute bottom-3 left-3">
            <LanguageSwitch />
          </div>
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
