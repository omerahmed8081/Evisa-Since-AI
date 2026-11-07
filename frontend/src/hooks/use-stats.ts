import { useEffect, useState } from "react";
import { getClient, useApiSettings, type Stats } from "@/api";

const listeners = new Set<() => void>();

/** Re-fetch stats everywhere (e.g. after feedback is sent). */
export function refreshStats() {
  listeners.forEach((l) => l());
}

/** Knowledge-base stats for the header counter; refreshes on demand and on settings change. */
export function useStats(): Stats | null {
  const settings = useApiSettings();
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      getClient(settings)
        .stats()
        .then((s) => !cancelled && setStats(s))
        .catch(() => !cancelled && setStats(null));
    };
    load();
    listeners.add(load);
    return () => {
      cancelled = true;
      listeners.delete(load);
    };
  }, [settings]);

  return stats;
}
