// Pick a model from what Prompture says the configured providers offer, like
// assistant-ui's model selector: a button with the current model, and a searchable
// list grouped by provider with what each model can do and costs.
import { useEffect, useMemo, useRef, useState } from 'react';
import { raw } from '../../api/client';

export interface ModelRow {
  id: string; // provider/model, what Prompture takes
  name: string;
  vision: boolean | null;
  reasoning: boolean | null;
  context: number | null;
  input_price: number | null; // dollars per million tokens
  output_price: number | null;
}

export interface ModelList {
  providers: { id: string; name: string; source: string; models: ModelRow[] }[];
  keys: { provider: string; set: boolean; listed: boolean }[];
}

const k = (n: number | null) => (n == null ? '' : n >= 1e6 ? `${(n / 1e6).toFixed(n % 1e6 ? 1 : 0)}M` : `${Math.round(n / 1000)}k`);
const price = (m: ModelRow) =>
  m.input_price == null ? (m.id.startsWith('claude-code/') || m.id.startsWith('codex/') ? 'your subscription' : '') : `$${m.input_price} / $${m.output_price} per 1M`;

function Badge({ children, on }: { children: string; on: boolean }) {
  return (
    <span style={{ font: "500 10.5px 'DM Mono',monospace", padding: '1px 6px', borderRadius: 4, border: '1px solid var(--border)', color: on ? 'var(--text)' : 'var(--faint)', background: on ? 'var(--raised)' : 'transparent' }}>{children}</span>
  );
}

export default function ModelSelector({ value, onChange, list, loading, needVision, label, placeholder }: {
  value: string;
  onChange: (id: string) => void;
  list: ModelList | null;
  loading: boolean;
  needVision?: boolean; // the vision model must see pictures
  label: string;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [hi, setHi] = useState(0);
  const wrap = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close);
    setTimeout(() => input.current?.focus(), 0);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const groups = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return (list?.providers || []).map((p) => ({
      ...p,
      models: p.models.filter((m) => (!needVision || m.vision !== false)
        && words.every((w) => (p.name + ' ' + m.id).toLowerCase().includes(w))),
    })).filter((p) => p.models.length);
  }, [list, q, needVision]);
  const flat = groups.flatMap((g) => g.models);
  const current = flat.find((m) => m.id === value) || list?.providers.flatMap((p) => p.models).find((m) => m.id === value);

  const pick = (id: string) => { onChange(id); setOpen(false); setQ(''); };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(flat.length - 1, h + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(0, h - 1)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (flat[hi]) pick(flat[hi].id); else if (q.includes('/')) pick(q.trim()); }
    else if (e.key === 'Escape') setOpen(false);
  };

  let n = -1;
  return (
    <div ref={wrap} style={{ position: 'relative' }}>
      <button type="button" className="sel" aria-haspopup="listbox" aria-expanded={open} aria-label={label} onClick={() => { setOpen(!open); setHi(0); }}
        style={{ width: 340, display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', textAlign: 'left' }}>
        <span className="mono" style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: value ? 'var(--text)' : 'var(--faint)' }}>{value || placeholder || 'Pick a model'}</span>
        {current?.vision ? <Badge on>vision</Badge> : null}
        {current?.reasoning ? <Badge on>reasoning</Badge> : null}
        <span aria-hidden="true" style={{ color: 'var(--faint)' }}>▾</span>
      </button>
      {open ? (
        <div role="dialog" aria-label={label} style={{ position: 'absolute', zIndex: 30, top: 40, left: 0, width: 520, maxHeight: 420, display: 'flex', flexDirection: 'column', background: 'var(--panel)', border: '1px solid var(--border)', borderRadius: 10, boxShadow: '0 10px 30px rgba(0,0,0,.35)' }}>
          <div style={{ padding: 8, borderBottom: '1px solid var(--line)' }}>
            <input ref={input} className="inp" placeholder="Search models, or type provider/model" value={q} onChange={(e) => { setQ(e.target.value); setHi(0); }} onKeyDown={onKey} />
          </div>
          <div role="listbox" aria-label="Models" style={{ overflowY: 'auto', padding: '4px 0' }}>
            {loading ? <div style={{ padding: 14, fontSize: 13, color: 'var(--dim)' }}>Asking the providers…</div> : null}
            {!loading && !groups.length ? (
              <div style={{ padding: 14, fontSize: 13, color: 'var(--dim)' }}>
                {q.includes('/') ? <>Press Enter to use <span className="mono">{q.trim()}</span> as written.</> : 'No model matches. Add a key for another provider below.'}
              </div>
            ) : null}
            {groups.map((g) => (
              <div key={g.id}>
                <div className="lab" style={{ padding: '8px 12px 4px' }}>{g.name}</div>
                {g.models.map((m) => {
                  n += 1;
                  const i = n;
                  return (
                    <button key={m.id} type="button" role="option" aria-selected={m.id === value} onMouseEnter={() => setHi(i)} onClick={() => pick(m.id)}
                      style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', border: 0, textAlign: 'left', cursor: 'pointer', color: 'var(--text)', background: i === hi ? 'var(--hover)' : 'transparent', font: "13px 'DM Sans',sans-serif" }}>
                      <span style={{ width: 12, color: 'var(--accent)' }}>{m.id === value ? '✓' : ''}</span>
                      <span className="mono" style={{ flex: 1, fontSize: 12.5 }}>{m.name}</span>
                      {m.vision ? <Badge on>vision</Badge> : null}
                      {m.reasoning ? <Badge on>reasoning</Badge> : null}
                      {m.context ? <Badge on={false}>{k(m.context)}</Badge> : null}
                      <span className="mono" style={{ fontSize: 11, color: 'var(--faint)', width: 150, textAlign: 'right' }}>{price(m)}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** The model list, fetched once per page (refresh after keys change). */
export function useModels(enabled: boolean): { list: ModelList | null; loading: boolean; reload: () => void; error: string } {
  const [list, setList] = useState<ModelList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    setLoading(true);
    raw.get<ModelList>(`/ai/models${tick ? '?refresh=true' : ''}`).then(
      (d) => { if (live) { setList(d); setError(''); setLoading(false); } },
      (e: unknown) => { if (live) { setError(e instanceof Error ? e.message : String(e)); setLoading(false); } },
    );
    return () => { live = false; };
  }, [enabled, tick]);
  return { list, loading, reload: () => setTick((t) => t + 1), error };
}
