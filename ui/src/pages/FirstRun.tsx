// First run (docs/design/first-run): connect Plex, pick libraries, AI or not, start.
// Finishing saves the settings, starts the first scan and marks setup as done.
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router';
import { api } from '../api/client';
import type { PlexLibrary, Settings } from '../api/types';
import { Bare, useApp } from '../components/Shell';
import { money, plural } from '../lib/format';
import { errText } from './settings/util';
import './FirstRun.css';

const NAMES = ['Plex', 'Libraries', 'AI', 'Start'];
const MASK = /^•+$/;

// -- Sign in with Plex: the plex.tv PIN flow, all from the browser ---------------------
function plexClientId(): string {
  let id = localStorage.getItem('marcarr.plexClient');
  if (!id) {
    id = 'marcarr-' + (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2));
    localStorage.setItem('marcarr.plexClient', id);
  }
  return id;
}
const plexHeaders = () => ({ Accept: 'application/json', 'X-Plex-Product': 'Marcarr', 'X-Plex-Client-Identifier': plexClientId() });

async function plexSignIn(signal: { cancelled: boolean }): Promise<string> {
  const res = await fetch('https://plex.tv/api/v2/pins?strong=true', { method: 'POST', headers: plexHeaders() });
  if (!res.ok) throw new Error('plex.tv did not answer');
  const pin = (await res.json()) as { id: number; code: string };
  const url = `https://app.plex.tv/auth#?clientID=${encodeURIComponent(plexClientId())}&code=${encodeURIComponent(pin.code)}&context%5Bdevice%5D%5Bproduct%5D=Marcarr`;
  const win = window.open(url, 'plex-auth', 'width=800,height=700');
  const until = Date.now() + 5 * 60 * 1000;
  while (Date.now() < until && !signal.cancelled) {
    await new Promise((r) => setTimeout(r, 2000));
    const r = await fetch(`https://plex.tv/api/v2/pins/${pin.id}`, { headers: plexHeaders() });
    if (r.ok) {
      const j = (await r.json()) as { authToken: string | null };
      if (j.authToken) { try { win?.close(); } catch { /* ignore */ } return j.authToken; }
    }
  }
  throw new Error(signal.cancelled ? 'Cancelled' : 'Plex sign-in timed out');
}

const DEFAULT_AI: Settings['ai'] = { enabled: true, model: '', vision_model: '', base_url: '', api_key: '', keys: {}, effort: 'low', monthly_limit: 10, auto_accept: 0 };

export default function FirstRun() {
  const { refreshStatus } = useApp();
  const [step, setStep] = useState(1);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [url, setUrl] = useState('http://127.0.0.1:32400');
  const [token, setToken] = useState('');
  const [testing, setTesting] = useState(false);
  const [tested, setTested] = useState<{ ok: boolean; text: string } | null>(null);
  const [libs, setLibs] = useState<PlexLibrary[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [ai, setAi] = useState(true);
  const [aiCfg, setAiCfg] = useState<Settings['ai']>(DEFAULT_AI);
  const [limitText, setLimitText] = useState('$10.00');
  const [signing, setSigning] = useState(false);
  const signRef = useRef({ cancelled: false });
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');
  const [scanning, setScanning] = useState(false);
  const [found, setFound] = useState<{ movies: number; shows: number } | null>(null);

  // Start from whatever is saved already (a re-run of setup keeps the old values).
  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s);
      if (s.plex.url) setUrl(s.plex.url);
      if (s.plex.token && !MASK.test(s.plex.token)) setToken(s.plex.token);
      if (s.plex.libraries.length) setPicked(s.plex.libraries);
      setAi(s.ai.model ? s.ai.enabled : true);
      setAiCfg({ ...DEFAULT_AI, ...s.ai });
      setLimitText(money(s.ai.monthly_limit || 10));
    }, () => undefined);
    return () => { signRef.current.cancelled = true; };
  }, []);

  // While scanning, count what the library has found so far.
  useEffect(() => {
    if (!scanning) return;
    let live = true;
    const tick = async () => {
      try {
        const [m, s] = await Promise.all([api.titles({ type: 'movie', per_page: 1 }), api.titles({ type: 'show', per_page: 1 })]);
        if (live) setFound({ movies: m.total, shows: s.total });
      } catch { /* backend busy */ }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => { live = false; clearInterval(id); };
  }, [scanning]);

  const test = async () => {
    setTesting(true);
    setTested(null);
    try {
      const r = await api.testPlex(url.trim(), token || settings?.plex.token || '');
      if (r.ok) {
        setLibs(r.libraries || []);
        setPicked((p) => (p.length ? p.filter((k) => r.libraries.some((l) => l.key === k)) : r.libraries.map((l) => l.key)));
        setTested({ ok: true, text: `Connected. ${plural(r.libraries.length, 'library', 'libraries')} found` });
      } else setTested({ ok: false, text: r.error || 'Plex did not answer' });
    } catch (e) { setTested({ ok: false, text: errText(e) }); }
    setTesting(false);
  };
  const signIn = async () => {
    signRef.current = { cancelled: false };
    setSigning(true);
    setTested(null);
    try { setToken(await plexSignIn(signRef.current)); } catch (e) { setTested({ ok: false, text: errText(e) }); }
    setSigning(false);
  };

  const libNote = (l: PlexLibrary) => (l.count == null ? '' : l.type === 'movie' ? plural(l.count, 'film') : plural(l.count, 'show'));
  const pickedNames = libs.filter((l) => picked.includes(l.key)).map((l) => l.title);
  const expected = libs.filter((l) => picked.includes(l.key)).reduce((n, l) => n + (l.count || 0), 0);
  const foundTotal = found ? found.movies + found.shows : 0;
  const pct = expected ? Math.min(100, Math.round((foundTotal / expected) * 100)) : 0;

  const start = async () => {
    setStarting(true);
    setError('');
    const limit = parseFloat(limitText.replace(/[$,\s]/g, ''));
    try {
      const base = settings;
      await api.saveSettings({
        plex: { url: url.trim(), token: token || base?.plex.token || '', libraries: picked, path_map: base?.plex.path_map || [] },
        ai: { ...aiCfg, enabled: ai, monthly_limit: Number.isFinite(limit) && limit >= 0 ? limit : aiCfg.monthly_limit },
        ...(base ? { analysis: { ...base.analysis, steps: { ...base.analysis.steps, tags: ai ? base.analysis.steps.tags : false } } } : {}),
      });
      await api.scanLibrary();
      await api.finishSetup();
      refreshStatus();
      setScanning(true);
    } catch (e) { setError('Could not start: ' + errText(e)); }
    setStarting(false);
  };

  const canNext = step === 1 ? !!tested?.ok : step === 2 ? picked.length > 0 : step === 3 ? !ai || !!aiCfg.model : true;
  const next = () => (step === 4 ? start() : setStep(step + 1));

  return (
    <Bare>
      <main className="main pg-setup">
        <div style={{ width: '100%', maxWidth: 640, marginTop: '5vh', display: 'flex', flexDirection: 'column', gap: 26 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <svg width="24" height="33" viewBox="0 0 22 31" aria-hidden="true"><path fill="var(--accent)" d="M5 0h11.2c.5 0 1 .2 1.3.5l4 4c.3.4.5.8.5 1.3v22.5c0 1.5-1.8 2.3-2.9 1.3L11 22.2l-8.1 7.4C1.8 30.6 0 29.8 0 28.3V5a5 5 0 0 1 5-5z" /></svg>
            <span className="hd" style={{ fontSize: 28, fontWeight: 700 }}>Marcarr</span>
          </div>
          <ol style={{ display: 'flex', gap: 10, margin: 0, padding: 0, listStyle: 'none' }}>
            {NAMES.map((n, i) => (
              <li key={n} className={'stp' + (i + 1 === step ? ' on' : i + 1 < step ? ' done' : '')} aria-current={i + 1 === step ? 'step' : undefined}><i>{i + 1}</i>{n}</li>
            ))}
          </ol>

          <section className="box" style={{ padding: '24px 26px 26px' }}>
            {step === 1 ? (
              <>
                <h1 className="h1" style={{ fontSize: 26, paddingBottom: 12 }}>Connect Plex</h1>
                <div className="fr"><label className="fl" htmlFor="u-srv">Server</label><input id="u-srv" type="text" className="inp mono" value={url} onChange={(e) => { setUrl(e.target.value); setTested(null); }} style={{ flex: '1 1 240px', width: 'auto' }} /></div>
                <div className="fr">
                  <label className="fl" htmlFor="u-tok">Token</label>
                  <input id="u-tok" type="password" className="inp mono" placeholder={settings?.plex.token && MASK.test(settings.plex.token) ? 'Saved already. Paste a new one to change it' : 'Paste a token'} value={token} onChange={(e) => { setToken(e.target.value); setTested(null); }} style={{ flex: '1 1 200px', width: 'auto' }} />
                  <span style={{ color: 'var(--dim)' }}>or</span>
                  <button type="button" className="btn sm" disabled={signing} onClick={signIn}>{signing ? 'Waiting for Plex…' : 'Sign in with Plex'}</button>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, paddingTop: 16 }}>
                  <button type="button" className="btn" disabled={testing || !url.trim()} onClick={test}>{testing ? 'Testing…' : 'Test'}</button>
                  {tested ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontWeight: 600, color: tested.ok ? undefined : 'var(--bad)' }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: tested.ok ? 'var(--ok)' : 'var(--bad)' }} />{tested.text}
                    </span>
                  ) : null}
                </div>
              </>
            ) : null}

            {step === 2 ? (
              <>
                <h1 className="h1" style={{ fontSize: 26, paddingBottom: 12 }}>Pick libraries</h1>
                {libs.length === 0 ? <div style={{ color: 'var(--dim)' }}>Plex has no film or show libraries.</div> : null}
                {libs.map((b) => {
                  const on = picked.includes(b.key);
                  return (
                    <div className="fr" key={b.key}>
                      <button type="button" role="switch" className="sw" aria-checked={on} aria-label={b.title} onClick={() => setPicked(on ? picked.filter((k) => k !== b.key) : [...picked, b.key])}><i /></button>
                      <span style={{ flex: 1, fontSize: 15, fontWeight: 600 }}>{b.title}</span>
                      <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{libNote(b)}</span>
                    </div>
                  );
                })}
              </>
            ) : null}

            {step === 3 ? (
              <>
                <h1 className="h1" style={{ fontSize: 26, paddingBottom: 16 }}>Use AI?</h1>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                  <button type="button" className="opt" aria-pressed={ai} onClick={() => setAi(true)}><span className="hd" style={{ fontSize: 18, fontWeight: 600 }}>Use AI</span><span style={{ color: 'var(--dim)' }}>Tags and named places</span></button>
                  <button type="button" className="opt" aria-pressed={!ai} onClick={() => setAi(false)}><span className="hd" style={{ fontSize: 18, fontWeight: 600 }}>Not now</span><span style={{ color: 'var(--dim)' }}>Shots, scenes, signals and cast still work</span></button>
                </div>
                {ai ? (
                  <>
                    <div className="fr" style={{ marginTop: 10 }}><label className="fl" htmlFor="u-tm">Text model</label><input id="u-tm" type="text" className="sel mono" placeholder="provider/model" value={aiCfg.model} onChange={(e) => setAiCfg({ ...aiCfg, model: e.target.value })} style={{ flex: '1 1 240px' }} /></div>
                    <div className="fr"><label className="fl" htmlFor="u-vm">Vision model</label><input id="u-vm" type="text" className="sel mono" placeholder="provider/model" value={aiCfg.vision_model} onChange={(e) => setAiCfg({ ...aiCfg, vision_model: e.target.value })} style={{ flex: '1 1 240px' }} /></div>
                    <div className="fr"><label className="fl" htmlFor="u-key">API key</label><input id="u-key" type="password" className="inp mono" placeholder={MASK.test(aiCfg.api_key) ? 'Saved already' : 'From your AI provider'} value={MASK.test(aiCfg.api_key) ? '' : aiCfg.api_key} onChange={(e) => setAiCfg({ ...aiCfg, api_key: e.target.value || (settings?.ai.api_key ?? '') })} style={{ flex: '1 1 240px', width: 'auto' }} /></div>
                    <div className="fr"><label className="fl" htmlFor="u-lim">Monthly limit</label><input id="u-lim" type="text" className="inp mono" value={limitText} onChange={(e) => setLimitText(e.target.value)} style={{ width: 110 }} /></div>
                  </>
                ) : null}
              </>
            ) : null}

            {step === 4 ? (
              <>
                <h1 className="h1" style={{ fontSize: 26, paddingBottom: 12 }}>{scanning ? 'Scanning' : 'Ready'}</h1>
                <div className="fr"><span className="fl">Plex</span><span className="mono">{url}</span></div>
                <div className="fr"><span className="fl">Libraries</span><span>{pickedNames.length ? pickedNames.join(', ') : 'None picked'}</span></div>
                <div className="fr"><span className="fl">AI</span><span>{ai ? `On, up to ${money(parseFloat(limitText.replace(/[$,\s]/g, '')) || 0)} a month` : 'Off'}</span></div>
                {error ? <div style={{ paddingTop: 14, color: 'var(--bad)', fontWeight: 600 }}>{error}</div> : null}
                {scanning ? (
                  <div style={{ paddingTop: 18 }}>
                    <div role="progressbar" aria-label="First scan" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} style={{ height: 8, borderRadius: 4, background: 'var(--raised)', overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: pct + '%', background: 'var(--accent)' }} />
                    </div>
                    <div style={{ marginTop: 8, color: 'var(--dim)' }}>
                      {found ? `Reading the library: ${plural(found.movies, 'film')} and ${plural(found.shows, 'show')} found` : 'Reading the library…'}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </section>

          <div style={{ display: 'flex', gap: 10 }}>
            {step > 1 && !scanning ? <button type="button" className="btn" onClick={() => setStep(step - 1)}>Back</button> : null}
            <div style={{ flex: 1 }} />
            {!scanning ? <button type="button" className="btn pri" disabled={!canNext || starting} onClick={next}>{step === 4 ? (starting ? 'Starting…' : 'Start the first scan') : 'Next'}</button> : null}
            {scanning ? <Link to="/activity" className="btn pri">Go to Activity</Link> : null}
          </div>
        </div>
      </main>
    </Bare>
  );
}
