// "Test": one tiny call to the saved text and vision models, so a wrong key or
// model name shows up here and not as a failed tags step an hour later.
import { useState } from 'react';
import { raw } from '../../api/client';
import { money } from '../../lib/format';

interface Check {
  ok: boolean;
  model: string;
  seconds: number;
  cost: number;
  error: string;
}

export default function AiTest({ dirty }: { dirty: boolean }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<{ text: Check; vision: Check } | null>(null);
  const [err, setErr] = useState('');

  const run = async () => {
    setBusy(true);
    setErr('');
    setRes(null);
    try {
      setRes(await raw.post<{ text: Check; vision: Check }>('/settings/ai/test'));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const line = (label: string, c: Check) => (
    <span style={{ display: 'flex', gap: 8, alignItems: 'baseline', fontSize: 12.5 }}>
      <span style={{ fontWeight: 700, color: c.ok ? 'var(--ok)' : 'var(--bad)' }}>{c.ok ? 'Works' : 'Failed'}</span>
      <span style={{ color: 'var(--dim)' }}>{label}</span>
      <span className="mono" style={{ color: 'var(--dim)' }}>{c.model}</span>
      {c.ok ? <span className="mono" style={{ color: 'var(--faint)' }}>{c.seconds.toFixed(1)} s · {money(c.cost)}</span> : <span style={{ color: 'var(--bad)' }}>{c.error}</span>}
    </span>
  );

  return (
    <span style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button type="button" className="btn sm" disabled={busy || dirty} onClick={run}>{busy ? 'Testing…' : 'Test'}</button>
        <span style={{ fontSize: 12.5, color: 'var(--dim)' }}>{dirty ? 'Save first: the test uses the saved settings.' : 'One short question to each model, with a tiny picture for the vision one.'}</span>
      </span>
      {res ? <>{line('Text', res.text)}{line('Vision', res.vision)}</> : null}
      {err ? <span style={{ fontSize: 12.5, color: 'var(--bad)' }}>{err}</span> : null}
    </span>
  );
}
