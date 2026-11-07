import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { createRealClient, getSettings, resetSettings, saveSettings } from "@/api";

export function SettingsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [url, setUrl] = useState("");
  const [mock, setMock] = useState(true);
  const [test, setTest] = useState<"idle" | "testing" | "ok" | "fail">("idle");

  useEffect(() => {
    if (open) {
      const s = getSettings();
      setUrl(s.apiBaseUrl);
      setMock(s.useMock);
      setTest("idle");
    }
  }, [open]);

  const resetToDefaults = () => {
    resetSettings();
    const d = getSettings();
    setUrl(d.apiBaseUrl);
    setMock(d.useMock);
    setTest("idle");
  };

  const runTest = async () => {
    setTest("testing");
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 6000);
    try {
      const h = await createRealClient(url).health(ctrl.signal);
      setTest(h.ok === false ? "fail" : "ok");
    } catch {
      setTest("fail");
    } finally {
      clearTimeout(t);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
          <DialogDescription>Connect to the knowledge service or use built-in sample data.</DialogDescription>
        </DialogHeader>
        <div className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="api-url">API base URL</Label>
            <div className="flex gap-2">
              <Input
                id="api-url"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value);
                  setTest("idle");
                }}
                placeholder="https://knowledge.example.com"
              />
              <Button variant="outline" onClick={runTest} disabled={!url.trim() || test === "testing"}>
                {test === "testing" && <Loader2 className="size-4 animate-spin" />}
                Test connection
              </Button>
            </div>
            {test === "ok" && (
              <p className="flex items-center gap-1.5 text-sm text-success">
                <CheckCircle2 className="size-4" /> Connected.
              </p>
            )}
            {test === "fail" && (
              <p className="flex items-center gap-1.5 text-sm text-destructive">
                <XCircle className="size-4" /> Couldn't reach /api/health.
              </p>
            )}
          </div>
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <Label htmlFor="use-mock">Use mock data</Label>
              <p className="text-xs text-muted-foreground">Sample answers, no server needed.</p>
            </div>
            <Switch id="use-mock" checked={mock} onCheckedChange={setMock} />
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              Defaults come from the build environment: VITE_API_BASE_URL and VITE_USE_MOCK.
            </p>
            <Button type="button" variant="link" size="sm" className="shrink-0 px-0" onClick={resetToDefaults}>
              Reset to defaults
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              saveSettings({ apiBaseUrl: url, useMock: mock });
              onOpenChange(false);
            }}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
