// Settings > Connected apps: API keys. A new key is shown once, with Copy.
import { useState } from 'react';
import { Link } from 'react-router';
import { api } from '../../api/client';
import type { ApiKey } from '../../api/types';
import { css, Empty, ErrorBox, Loading, Switch } from '../../components/kit';
import { useApi } from '../../lib/hooks';
import { useToast } from '../../lib/toast';
import { ago, copyText, errText } from './util';

const SCOPES: ApiKey['scopes'] = ['read', 'propose', 'review', 'run'];
const SCOPE_WHAT: Record<ApiKey['scopes'][number], string> = {
  read: 'Read titles, scenes and tags',
  propose: 'Propose tags for review',
  review: 'Keep and drop tags',
  run: 'Start analysis',
};
const COLORS: Record<string, string> = { fanscut: '#00aeef', doblarr: '#ff8f73' };
const OTHER = ['#a991ff', '#5fcfc0', '#d9b08c', '#56c7e8', '#e57fd2'];
function color(name: string) {
  const k = name.toLowerCase().replace(/\s+/g, '');
  if (COLORS[k]) return COLORS[k];
  if (/mcp|assistant|claude/.test(k)) return '#929a9d';
  let h = 0;
  for (const c of k) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return OTHER[h % OTHER.length];
}
const isMcp = (k: ApiKey) => /mcp|assistant|claude/i.test(k.name);
const pill = 'font-size:11px;padding:2px 7px;border-radius:10px;border:1px solid var(--border);color:var(--dim)';

export function Apps({ requireKey, setRequireKey }: { requireKey: boolean; setRequireKey: (v: boolean) => void }) {
  const toast = useToast();
  const keys = useApi(() => api.keys(), []);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [scopes, setScopes] = useState<ApiKey['scopes']>(['read', 'propose']);
  const [fresh, setFresh] = useState<{ id: string; key: string } | null>(null);
  const [busy, setBusy] = useState('');

  const create = async () => {
    if (!name.trim()) { toast('Give the app a name', true); return; }
    setBusy('add');
    try {
      const k = await api.addKey(name.trim(), scopes);
      keys.set([...(keys.data || []), k]);
      if (k.key) setFresh({ id: k.id, key: k.key });
      setAdding(false);
      setName('');
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const renew = async (k: ApiKey) => {
    if (!window.confirm(`Make a new key for ${k.name}? The old key stops working now.`)) return;
    setBusy('n' + k.id);
    try {
      const n = await api.renewKey(k.id);
      keys.set((keys.data || []).map((x) => (x.id === k.id ? n : x)));
      if (n.key) setFresh({ id: n.id, key: n.key });
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const remove = async (k: ApiKey) => {
    if (!window.confirm(`Remove ${k.name}? Its key stops working.`)) return;
    try {
      await api.deleteKey(k.id);
      keys.set((keys.data || []).filter((x) => x.id !== k.id));
      if (fresh?.id === k.id) setFresh(null);
    } catch (e) { toast(errText(e), true); }
  };
  const copy = async (text: string) => toast((await copyText(text)) ? 'Key copied' : 'Could not copy: select it and copy by hand', false);

  return (
    <section aria-labelledby="s-apps">
      <div className="sh" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 id="s-apps" style={{ flex: 1, margin: 0, font: 'inherit' }}>Connected apps</h2>
        <Link to="/api" className="btn sm">API reference</Link>
        <button type="button" className="btn sm" onClick={() => setAdding(true)}>Add an app</button>
      </div>
      <div className="fr">
        <span className="fl">Require a key</span>
        <div className="fc"><Switch on={requireKey} onChange={setRequireKey} label="Require a key for the API" /><span style={{ color: 'var(--dim)' }}>{requireKey ? 'Every call to the API needs a key' : 'Apps on this network can call the API without a key'}</span></div>
      </div>

      {adding ? (
        <div className="fr" style={{ alignItems: 'flex-start' }}>
          <span className="fl" style={{ paddingTop: 8 }}>New app</span>
          <div className="fc" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
            <input type="text" className="inp" placeholder="Name, like FansCut" aria-label="App name" value={name} autoFocus onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') create(); }} />
            <span style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {SCOPES.map((s) => {
                const on = scopes.includes(s);
                return (
                  <button key={s} type="button" className={'pill' + (on ? ' on' : '')} aria-pressed={on} title={SCOPE_WHAT[s]}
                    onClick={() => setScopes(on ? scopes.filter((x) => x !== s) : [...scopes, s])}>
                    <span className="mono">{s}</span>
                  </button>
                );
              })}
            </span>
            <span style={{ display: 'flex', gap: 8 }}>
              <button type="button" className="btn sm pri" disabled={busy === 'add'} onClick={create}>Make a key</button>
              <button type="button" className="btn sm ghost" onClick={() => setAdding(false)}>Cancel</button>
            </span>
          </div>
        </div>
      ) : null}

      {keys.loading && !keys.data ? <Loading /> : keys.error ? <ErrorBox error={keys.error} retry={keys.reload} /> : null}
      {keys.data && !keys.data.length && !adding ? <div style={{ paddingTop: 12 }}><Empty>No apps yet. Add one to give FansCut, Doblarr or an assistant a key.</Empty></div> : null}
      {(keys.data || []).map((k) => {
        const shown = fresh && fresh.id === k.id ? fresh.key : null;
        return (
          <div key={k.id}>
            <div className="fr">
              <span className="fl" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={css('flex:none;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:7px;font:700 13px Outfit,sans-serif;color:#101317;background:' + color(k.name))}>{k.name.charAt(0).toUpperCase()}</span>
                {k.name}
              </span>
              <div className="fc">
                <span style={{ flex: '0 0 90px', fontSize: 12.5, color: 'var(--dim)' }}>{isMcp(k) ? 'MCP client' : 'App'}</span>
                <span className="mono" style={{ letterSpacing: '.08em', color: 'var(--dim)' }} title={k.prefix + '…'}>{k.prefix ? k.prefix + '••••' : '••••••••'}</span>
                <span style={{ display: 'inline-flex', gap: 4 }}>{k.scopes.map((c) => <span key={c} className="mono" style={css(pill)}>{c}</span>)}</span>
                <span style={{ flex: '1 1 130px', fontSize: 12.5, color: 'var(--dim)' }}>{k.last_used ? 'Last called ' + ago(k.last_used) : 'Never called'}</span>
                {shown ? <button type="button" className="btn sm" onClick={() => copy(shown)}>Copy key</button> : null}
                <button type="button" className="btn sm" disabled={busy === 'n' + k.id} onClick={() => renew(k)}>New key</button>
                <button type="button" className="btn sm ghost" onClick={() => remove(k)}>Remove</button>
              </div>
            </div>
            {shown ? (
              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px 12px', padding: '12px 14px', margin: '8px 0', border: '1px solid var(--accent)', borderRadius: 10 }}>
                <span className="mono" style={{ flex: '1 1 280px', minWidth: 0, overflowWrap: 'anywhere', userSelect: 'all' }}>{shown}</span>
                <button type="button" className="btn sm pri" onClick={() => copy(shown)}>Copy key</button>
                <span style={{ flex: '1 1 100%', fontSize: 12.5, color: 'var(--warn)', fontWeight: 600 }}>This is the only time the whole key is shown. Copy it into {k.name} now.</span>
              </div>
            ) : null}
          </div>
        );
      })}
    </section>
  );
}
