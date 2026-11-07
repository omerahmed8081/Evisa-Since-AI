import { useEffect, useState } from "react";
import { getClient, isMock, useApiSettings } from "@/api";

export type ApiStatus = "mock" | "live" | "offline" | "checking";

/** Polls /api/health in live mode; on failure retries with exponential backoff (2s → 30s). */
export function useApiStatus(): ApiStatus {
  const settings = useApiSettings();
  const [status, setStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    if (isMock(settings)) {
      setStatus("mock");
      return;
    }
    setStatus("checking");
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let delay = 2000;
    const client = getClient(settings);
    const check = async () => {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 5000);
      try {
        const h = await client.health(ctrl.signal);
        if (cancelled) return;
        setStatus(h.ok === false ? "offline" : "live");
        delay = 2000;
        timer = setTimeout(check, 60000);
      } catch {
        if (cancelled) return;
        setStatus("offline");
        timer = setTimeout(check, delay);
        delay = Math.min(delay * 2, 30000);
      } finally {
        clearTimeout(t);
      }
    };
    void check();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [settings]);

  return status;
}
