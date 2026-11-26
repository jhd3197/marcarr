// API (docs/design/api): the v1 reference, webhook events (with the real webhooks
// and their last calls) and the MCP tools. Endpoint docs are static (./api/reference).
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { BASE } from '../api/client';
import { useToast } from '../lib/toast';
import { ENDPOINTS, EVENTS, MCP_CONFIG, TOOLS, USERS } from './api/reference';
import { Webhooks } from './settings/Webhooks';
import { copyText } from './settings/util';
import './Api.css';

const TABS: [string, string][] = [['ref', 'Reference'], ['events', 'Events'], ['mcp', 'MCP']];
const mcls = (m: string) => 'm' + (m === 'POST' ? ' post' : '');

export default function Api() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some(([k]) => k === params.get('tab')) ? (params.get('tab') as string) : 'ref';
  const pick = (k: string) => setParams((p) => { const n = new URLSearchParams(p); n.set('tab', k); return n; }, { replace: true });
  const [sel, setSel] = useState(() => Math.max(0, ENDPOINTS.findIndex((e) => e.path === '/search/scenes')));
  const [ev, setEv] = useState(0);
  const [addingHook, setAddingHook] = useState(false);

  const base = `${window.location.origin}${BASE}`;
  const copy = async (text: string, what = 'Copied') => toast((await copyText(text)) ? what : 'Could not copy', false);

  const e = ENDPOINTS[sel];
  const groups: { name: string; rows: { i: number; method: string; path: string }[] }[] = [];
  ENDPOINTS.forEach((x, i) => {
    let g = groups.find((y) => y.name === x.group);
    if (!g) { g = { name: x.group, rows: [] }; groups.push(g); }
    g.rows.push({ i, method: x.method, path: x.path });
  });
  const request = 'curl ' + (e.method === 'POST' ? '-X POST ' : '') + '-H "X-Api-Key: $MARCARR_KEY" \\\n  '
    + (e.body ? '-H "Content-Type: application/json" \\\n  -d \'' + e.body.split('\n').join('\n  ') + '\' \\\n  ' : '')
    + '"' + base + e.example + '"';

  return (
    <div className="pg-api" style={{ display: 'contents' }}>
      <header style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px 14px' }}>
        <h1 className="h1">API</h1>
        <span className="mono" style={{ flex: '1 1 260px', minWidth: 0, fontSize: 13, color: 'var(--dim)' }}>{base}</span>
        <button type="button" className="btn" onClick={() => copy(base, 'Address copied')}>Copy address</button>
        <a href={`${BASE}/openapi.json`} className="btn" target="_blank" rel="noreferrer">OpenAPI file</a>
        <Link to="/settings?tab=apps" className="btn pri">Keys</Link>
      </header>

      <div role="tablist" className="tabs" aria-label="API">
        {TABS.map(([k, name]) => <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => pick(k)}>{name}</button>)}
      </div>

      {tab === 'ref' ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px 28px', alignItems: 'flex-start' }}>
          <nav aria-label="Endpoints" style={{ flex: '1 1 280px', maxWidth: 320, minWidth: 0 }}>
            {groups.map((g) => (
              <div key={g.name}>
                <div className="lab" style={{ padding: '10px 8px 4px' }}>{g.name}</div>
                {g.rows.map((r) => (
                  <button key={r.i} type="button" className="er" aria-pressed={r.i === sel} onClick={() => setSel(r.i)}>
                    <span className={mcls(r.method)}>{r.method}</span><span>{r.path}</span>
                  </button>
                ))}
              </div>
            ))}
          </nav>

          <section aria-label="Endpoint" style={{ flex: '2 1 320px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h2 className="hd" style={{ margin: 0, fontSize: 24, fontWeight: 600, lineHeight: 1.2 }}>{e.title}</h2>
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px 10px' }}>
              <span className={mcls(e.method)}>{e.method}</span>
              <span className="mono" style={{ fontSize: 14, overflowWrap: 'anywhere' }}>{BASE + e.path}</span>
              <span className="sc">{e.scope}</span>
            </div>
            {e.params.length ? (
              <div>
                <div className="lab" style={{ paddingBottom: 6 }}>{e.method === 'POST' ? 'Body' : 'Parameters'}</div>
                {e.params.map((p) => (
                  <div key={p.name} className="pr">
                    <span className="mono" style={{ flex: '0 0 90px', fontWeight: 500 }}>{p.name}</span>
                    <span className="mono" style={{ flex: '0 0 150px', color: 'var(--faint)', fontSize: 12 }}>{p.type}</span>
                    <span style={{ flex: '1 1 160px', color: 'var(--dim)' }}>{p.what}</span>
                  </div>
                ))}
              </div>
            ) : null}
            <div>
              <div className="lab" style={{ paddingBottom: 6 }}>Used by</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {USERS[e.scope].map((u) => <span key={u} className="sc" style={{ fontFamily: "'DM Sans', sans-serif", fontSize: 12, color: 'var(--text)' }}>{u}</span>)}
              </div>
            </div>
          </section>

          <section aria-label="Example" style={{ flex: '2 1 380px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <div className="cap"><span className="lab" style={{ flex: 1 }}>Request</span><button type="button" className="btn sm" onClick={() => copy(request)}>Copy</button></div>
              <pre className="code">{request}</pre>
            </div>
            <div>
              <div className="cap"><span className="lab" style={{ flex: 1 }}>Response</span><span className="mono" style={{ fontSize: 12, color: 'var(--ok)' }}>200</span><button type="button" className="btn sm" onClick={() => copy(e.response)}>Copy</button></div>
              <pre className="code">{e.response}</pre>
            </div>
          </section>
        </div>
      ) : null}

      {tab === 'events' ? (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px 28px', alignItems: 'flex-start' }}>
            <section aria-label="Events" style={{ flex: '1 1 300px', maxWidth: 360, minWidth: 0 }}>
              {EVENTS.map((x, i) => (
                <button key={x.name} type="button" className="er" aria-pressed={i === ev} onClick={() => setEv(i)} style={{ height: 'auto', padding: 8 }}>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <span style={{ fontWeight: 500 }}>{x.name}</span>
                    <span style={{ fontFamily: "'DM Sans', sans-serif", color: 'var(--dim)' }}>{x.what}</span>
                  </span>
                </button>
              ))}
            </section>
            <section aria-label="Payload" style={{ flex: '2 1 360px', minWidth: 0 }}>
              <div className="cap"><span className="lab" style={{ flex: 1 }}>Payload</span><Link to="/settings?tab=notify" className="btn sm">Webhooks</Link><button type="button" className="btn sm" onClick={() => copy(EVENTS[ev].payload)}>Copy</button></div>
              <pre className="code">{EVENTS[ev].payload}</pre>
            </section>
          </div>
          <section aria-label="Webhooks" style={{ maxWidth: 960 }}>
            <div className="cap"><h2 className="h2" style={{ flex: 1 }}>Webhooks</h2><button type="button" className="btn sm" onClick={() => setAddingHook(true)}>Add a webhook</button></div>
            <Webhooks wide adding={addingHook} onAdded={() => setAddingHook(false)} />
          </section>
        </>
      ) : null}

      {tab === 'mcp' ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px 28px', alignItems: 'flex-start' }}>
          <section aria-label="Tools" style={{ flex: '2 1 420px', minWidth: 0 }}>
            <div className="cap"><h2 className="h2" style={{ flex: 1 }}>Tools</h2><span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>marcarr mcp</span></div>
            {TOOLS.map((t) => (
              <div key={t.name} className="pr" style={{ alignItems: 'center'}}>
                <span className="mono" style={{ flex: '0 0 130px', fontWeight: 500 }}>{t.name}</span>
                <span style={{ flex: '1 1 200px', color: 'var(--dim)' }}>{t.what}</span>
                <span className="mono" style={{ flex: '0 1 260px', fontSize: 12, color: 'var(--faint)', overflowWrap: 'anywhere' }}>{t.path}</span>
                <span className="sc">{t.scope}</span>
              </div>
            ))}
          </section>
          <section aria-label="Set up" style={{ flex: '1 1 340px', minWidth: 0 }}>
            <div className="cap"><span className="lab" style={{ flex: 1 }}>Add to an assistant</span><button type="button" className="btn sm" onClick={() => copy(MCP_CONFIG)}>Copy</button></div>
            <pre className="code">{MCP_CONFIG}</pre>
          </section>
        </div>
      ) : null}
    </div>
  );
}
