// Webhooks and their last calls (Settings > Notifications and API > Events).
// Rows use the page's .fr / .lab classes, so the host page must define them.
import { useState } from 'react';
import { api } from '../../api/client';
import type { Webhook, WebhookCall } from '../../api/types';
import { css, Empty, ErrorBox, Loading } from '../../components/kit';
import { useApi } from '../../lib/hooks';
import { when } from '../../lib/format';
import { useToast } from '../../lib/toast';
import { EVENTS } from '../api/reference';
import { errText } from './util';

const STATE: Record<Webhook['state'], [string, string]> = {
  working: ['Working', 'var(--ok)'],
  failing: ['Failing', 'var(--bad)'],
  unused: ['Not called yet', 'var(--dim)'],
};
const okCode = (c: number | null) => c !== null && c >= 200 && c < 300;
const scopePill = 'font-size:11px;padding:2px 7px;border-radius:10px;border:1px solid var(--border);color:var(--dim)';

/** `wide` = the API page's widths (70px state, 40px code); Settings uses 60/36. */
export function Webhooks({ adding, onAdded, wide = false }: { adding: boolean; onAdded: () => void; wide?: boolean }) {
  const toast = useToast();
  const hooks = useApi(() => api.webhooks(), []);
  const calls = useApi(() => api.webhookCalls(), [], 10000);
  const [url, setUrl] = useState('');
  const [events, setEvents] = useState<string[]>(['video.analysed']);
  const [busy, setBusy] = useState('');

  const add = async () => {
    if (!/^https?:\/\//.test(url.trim())) { toast('Give an address that starts with http:// or https://', true); return; }
    if (!events.length) { toast('Pick at least one event', true); return; }
    setBusy('add');
    try {
      const h = await api.addWebhook(url.trim(), events);
      hooks.set([...(hooks.data || []), h]);
      setUrl('');
      onAdded();
      toast('Webhook added');
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const test = async (h: Webhook) => {
    setBusy('t' + h.id);
    try {
      const c: WebhookCall = await api.testWebhook(h.id);
      toast(okCode(c.code) ? `Test sent: ${c.code}` : `Test failed: ${c.code ?? c.error}`, !okCode(c.code));
      calls.reload();
      hooks.reload();
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const remove = async (h: Webhook) => {
    if (!window.confirm(`Stop sending events to ${h.url}?`)) return;
    try {
      await api.deleteWebhook(h.id);
      hooks.set((hooks.data || []).filter((x) => x.id !== h.id));
    } catch (e) { toast(errText(e), true); }
  };
  const resend = async (c: WebhookCall) => {
    setBusy('r' + c.id);
    try {
      const n = await api.resendCall(c.id);
      toast(okCode(n.code) ? `Sent again: ${n.code}` : `Failed again: ${n.code ?? n.error}`, !okCode(n.code));
      calls.reload();
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };

  const stateW = wide ? 70 : 60, codeW = wide ? 40 : 36;
  return (
    <>
      {adding ? (
        <div className="fr">
          <input type="url" className="inp mono" placeholder="https://" aria-label="Webhook address" value={url} onChange={(e) => setUrl(e.target.value)} style={{ flex: '1 1 280px', width: 'auto' }} />
          <span style={{ flex: '1 1 100%', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {EVENTS.map((ev) => {
              const on = events.includes(ev.name);
              return (
                <button key={ev.name} type="button" className={'pill' + (on ? ' on' : '')} aria-pressed={on} title={ev.what}
                  onClick={() => setEvents(on ? events.filter((x) => x !== ev.name) : [...events, ev.name])}>
                  <span className="mono" style={{ fontSize: 11.5 }}>{ev.name}</span>
                </button>
              );
            })}
          </span>
          <button type="button" className="btn sm pri" disabled={busy === 'add'} onClick={add}>Add</button>
          <button type="button" className="btn sm ghost" onClick={onAdded}>Cancel</button>
        </div>
      ) : null}

      {hooks.loading && !hooks.data ? <Loading /> : hooks.error ? <ErrorBox error={hooks.error} retry={hooks.reload} /> : null}
      {hooks.data && !hooks.data.length && !adding ? <div style={{ paddingTop: 12 }}><Empty>No webhooks yet. Add one to tell another app when something changes here.</Empty></div> : null}
      {(hooks.data || []).map((h) => {
        const [st, color] = STATE[h.state] || STATE.unused;
        return (
          <div className="fr" key={h.id}>
            <span className="mono" style={{ flex: '1 1 280px', minWidth: 0, overflowWrap: 'anywhere', opacity: h.enabled ? 1 : 0.55 }}>{h.url}</span>
            <span style={{ flex: '1 1 200px', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {h.events.map((c) => <span key={c} className="mono" style={css(scopePill)}>{c}</span>)}
            </span>
            <span style={css(`flex:0 0 ${stateW}px;font-size:12.5px;font-weight:600;color:${color}`)}>{h.enabled ? st : 'Off'}</span>
            <button type="button" className="btn sm" disabled={busy === 't' + h.id} onClick={() => test(h)}>Send a test</button>
            <button type="button" className="btn sm ghost" onClick={() => remove(h)}>Remove</button>
          </div>
        );
      })}

      <h3 className="lab" style={{ margin: '24px 0 4px' }}>Last calls</h3>
      {calls.error ? <ErrorBox error={calls.error} retry={calls.reload} /> : null}
      {calls.data && !calls.data.length ? <div style={{ padding: '10px 0', fontSize: 13, color: 'var(--dim)' }}>No calls yet.</div> : null}
      {(calls.data || []).slice(0, 20).map((d) => {
        const ok = okCode(d.code);
        return (
          <div className="fr" key={d.id}>
            <span className="mono" style={{ flex: '0 0 60px', color: 'var(--dim)' }}>{when(d.at)}</span>
            <span className="mono" style={{ flex: '0 0 130px' }}>{d.event}</span>
            <span className="mono" style={{ flex: '1 1 240px', minWidth: 0, color: 'var(--dim)', overflowWrap: 'anywhere' }}>{d.url}</span>
            <span className="mono" title={d.error || undefined} style={css(`flex:0 0 ${codeW}px;font-weight:500;color:${ok ? 'var(--ok)' : 'var(--bad)'}`)}>{d.code ?? 'Error'}</span>
            {!ok ? <button type="button" className="btn sm" disabled={busy === 'r' + d.id} onClick={() => resend(d)}>Send again</button> : null}
          </div>
        );
      })}
    </>
  );
}
