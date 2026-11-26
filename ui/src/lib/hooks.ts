import { useCallback, useEffect, useRef, useState } from 'react';

export interface Loaded<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
  set: (v: T) => void;
}

/** Run an API call when deps change; reload() runs it again. `every` polls (ms). */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[], every?: number): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    let live = true;
    setLoading(true);
    fnRef.current().then(
      (d) => { if (live) { setData(d); setError(null); setLoading(false); } },
      (e: unknown) => { if (live) { setError(e instanceof Error ? e.message : String(e)); setLoading(false); } },
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  useEffect(() => {
    if (!every) return;
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fnRef.current().then((d) => setData(d), () => undefined);
      }
    }, every);
    return () => clearInterval(id);
  }, [every]);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload, set: setData };
}

/** Key handler for review pages: K keep, D drop and so on. Ignores typing in inputs. */
export function useKeys(map: Record<string, () => void>, deps: unknown[]) {
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const f = map[e.key] || map[e.key.toLowerCase()];
      if (f) { e.preventDefault(); f(); }
    };
    window.addEventListener('keydown', on);
    return () => window.removeEventListener('keydown', on);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
