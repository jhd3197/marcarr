// Settings (docs/design/settings): eleven tabs, one draft, "Unsaved changes / Discard / Save".
// Saving PUTs only the sections that changed, each whole. Secrets come back masked ("••••")
// and are sent back unchanged unless a new one was typed.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router';
import { api, urls } from '../api/client';
import type { PlexLibrary, Settings as S, Step } from '../api/types';
import { STEPS } from '../api/types';
import { ErrorBox, Loading, Seg, Switch } from '../components/kit';
import { useApp } from '../components/Shell';
import { useApi } from '../lib/hooks';
import { money, plural } from '../lib/format';
import { useToast } from '../lib/toast';
import AiTest from './settings/AiTest';
import { Apps } from './settings/Apps';
import { Places, type PlaceSources } from './settings/Places';
import { Webhooks } from './settings/Webhooks';
import { copyText, errText } from './settings/util';
import './Settings.css';

/** settings.places is not in types.ts yet (see the report): where places come from. */
type Draft = S & { places?: PlaceSources };
type Section = keyof Draft;

const SECS: [string, string][] = [
  ['general', 'General'], ['plex', 'Plex'], ['labels', 'Plex labels'], ['analysis', 'Analysis'], ['ai', 'AI'], ['tags', 'Tags'],
  ['faces', 'Faces'], ['places', 'Named places'], ['apps', 'Connected apps'], ['notify', 'Notifications'], ['backup', 'Backup and About'],
];
const WHAT: Record<Step, string> = {
  shots: 'Camera cuts', subtitles: 'Dialogue lines', scenes: 'Shots grouped into scenes', signals: 'Dark, silence, loud and the rest',
  cast: 'Actors and characters', faces: 'Who is on screen', tags: 'What each scene is',
};
const MASK = /^•+$/;
const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
const parseMoney = (s: string) => {
  const n = parseFloat(s.replace(/[$,\s]/g, ''));
  return Number.isFinite(n) && n >= 0 ? n : null;
};

function Row({ label, htmlFor, children, top }: { label: ReactNode; htmlFor?: string; children: ReactNode; top?: boolean }) {
  return (
    <div className="fr" style={top ? { alignItems: 'flex-start' } : undefined}>
      {htmlFor ? <label className="fl" htmlFor={htmlFor}>{label}</label> : <span className="fl" style={top ? { paddingTop: 5 } : undefined}>{label}</span>}
      <div className="fc">{children}</div>
    </div>
  );
}

/** A masked secret: dots and Change, or a password box once Change is pressed. */
function Secret({ id, value, onChange, label, reset }: { id: string; value: string; onChange: (v: string) => void; label: string; reset: number }) {
  const [editing, setEditing] = useState(false);
  useEffect(() => setEditing(false), [reset]);
  const masked = !value || MASK.test(value);
  if (!editing && masked) {
    return (
      <>
        <span className="mono" style={{ letterSpacing: '.1em' }}>{value ? '••••••••••••••••' : <span style={{ letterSpacing: 0, color: 'var(--faint)' }}>Not set</span>}</span>
        <button type="button" className="btn sm" onClick={() => { setEditing(true); onChange(''); }}>{value ? 'Change' : 'Set'}</button>
      </>
    );
  }
  return <input id={id} type="password" className="inp mono" aria-label={label} autoFocus={editing} placeholder="Paste it here" value={value} onChange={(e) => onChange(e.target.value)} style={{ flex: '1 1 240px', width: 'auto' }} />;
}

export default function Settings() {
  const toast = useToast();
  const { status, setTheme, refreshStatus } = useApp();
  const [params, setParams] = useSearchParams();
  const sec = SECS.some(([k]) => k === params.get('tab')) ? (params.get('tab') as string) : 'general';
  const pick = (k: string) => setParams((p) => { const n = new URLSearchParams(p); n.set('tab', k); return n; }, { replace: true });

  const loaded = useApi(() => api.settings(), []);
  const vocab = useApi(() => api.vocab(), []);
  const libs = useApi(() => api.plexLibraries().catch(() => [] as PlexLibrary[]), []);
  const [saved, setSaved] = useState<Draft | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [reset, setReset] = useState(0); // bumps on load/discard so uncontrolled inputs re-read the draft
  const [saving, setSaving] = useState(false);
  const [plexTest, setPlexTest] = useState<{ ok: boolean; text: string } | null>(null);
  const [testing, setTesting] = useState(false);
  const [labelPick, setLabelPick] = useState(false);
  const [addingHook, setAddingHook] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!loaded.data) return;
    const d: Draft = clone(loaded.data);
    setSaved(d);
    setDraft(clone(d));
    setReset((r) => r + 1);
  }, [loaded.data]);

  const changed = useMemo<Section[]>(() => {
    if (!saved || !draft) return [];
    return (Object.keys(draft) as Section[]).filter((k) => !same(draft[k], saved[k]));
  }, [saved, draft]);
  const dirty = changed.length > 0;

  useEffect(() => {
    if (!dirty) return;
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);

  if (loaded.error && !draft) return <div className="pg-settings" style={{ display: 'contents' }}><h1 className="h1">Settings</h1><ErrorBox error={loaded.error} retry={loaded.reload} /></div>;
  if (!draft || !saved) return <div className="pg-settings" style={{ display: 'contents' }}><h1 className="h1">Settings</h1><Loading /></div>;

  function set<K extends Section>(k: K, patch: Partial<NonNullable<Draft[K]>>) {
    setDraft((d) => (d ? { ...d, [k]: { ...(d[k] as object), ...patch } } : d));
  }

  const save = async () => {
    if (!dirty || saving) return;
    const body: Partial<Draft> = {};
    for (const k of changed) (body as Record<string, unknown>)[k] = draft[k];
    // An emptied secret box means "keep the old one".
    if (body.plex && !body.plex.token) body.plex = { ...body.plex, token: saved.plex.token };
    if (body.ai && !body.ai.api_key) body.ai = { ...body.ai, api_key: saved.ai.api_key };
    setSaving(true);
    try {
      const res = (await api.saveSettings(body as Partial<S>)) as Draft;
      const next: Draft = { ...clone(draft), ...clone(res) };
      setSaved(next);
      setDraft(clone(next));
      setReset((r) => r + 1);
      if (body.general) setTheme(next.general.theme);
      refreshStatus();
      toast('Settings saved');
    } catch (e) { toast('Could not save: ' + errText(e), true); }
    setSaving(false);
  };
  const discard = () => { setDraft(clone(saved)); setReset((r) => r + 1); setPlexTest(null); };

  const testPlex = async () => {
    setTesting(true);
    try {
      const r = await api.testPlex(draft.plex.url, draft.plex.token || saved.plex.token);
      if (r.ok) {
        setPlexTest({ ok: true, text: r.name ? `Connected to ${r.name}` : 'Connected' });
        if (r.libraries?.length) libs.set(r.libraries);
      } else setPlexTest({ ok: false, text: r.error || 'Plex did not answer' });
    } catch (e) { setPlexTest({ ok: false, text: errText(e) }); }
    setTesting(false);
  };

  const plexState = plexTest
    ? plexTest
    : status?.plex === 'connected' ? { ok: true, text: 'Connected' } : status?.plex === 'failing' ? { ok: false, text: 'Not answering' } : null;

  const families = vocab.data?.families || [];
  const allTags = families.flatMap((f) => f.tags);
  const tagName = (id: string) => allTags.find((t) => t.id === id)?.name || id;
  const modelsMissing = draft.faces.models.some((m) => !m.present);
  const atNight = !!(draft.analysis.window_start || draft.analysis.window_end);
  const sources: PlaceSources = draft.places || { from_dialogue: true, from_stills: true };

  const downloadModels = async () => {
    setDownloading(true);
    try {
      await api.downloadFaceModels();
      toast('Downloading the face models. This page updates when they are in.');
      const poll = setInterval(async () => {
        try {
          const s = await api.settings();
          if (s.faces.models.every((m) => m.present)) {
            clearInterval(poll);
            setDownloading(false);
            setSaved((v) => (v ? { ...v, faces: s.faces } : v));
            setDraft((v) => (v ? { ...v, faces: s.faces } : v));
          }
        } catch { /* keep trying */ }
      }, 5000);
      setTimeout(() => { clearInterval(poll); setDownloading(false); }, 30 * 60 * 1000);
    } catch (e) { toast(errText(e), true); setDownloading(false); }
  };
  const writeLabels = async () => {
    try { await api.writeLabels(); toast('Writing labels to Plex'); } catch (e) { toast(errText(e), true); }
  };
  const importFile = async (f: File) => {
    try {
      const doc = JSON.parse(await f.text());
      const r = await api.importBackup(doc);
      const parts = Object.entries(r.imported || {}).map(([k, n]) => `${n} ${k}`);
      toast('Imported ' + (parts.join(', ') || 'nothing new'));
    } catch (e) { toast('Could not import: ' + errText(e), true); }
    if (fileRef.current) fileRef.current.value = '';
  };

  return (
    <div className="pg-settings" style={{ display: 'contents' }}>
      <header style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px 12px' }}>
        <h1 className="h1" style={{ flex: '1 1 200px' }}>Settings</h1>
        {dirty ? <><span style={{ fontSize: 13, color: 'var(--warn)', fontWeight: 600 }}>Unsaved changes</span><button type="button" className="btn" onClick={discard}>Discard</button></> : null}
        <button type="button" className={dirty ? 'btn pri' : 'btn'} onClick={save} disabled={saving}>{saving ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}</button>
      </header>

      <div role="tablist" className="secs" aria-label="Settings">
        {SECS.map(([k, name]) => <button key={k} type="button" role="tab" aria-selected={sec === k} onClick={() => pick(k)}>{name}</button>)}
      </div>

      <div>
        <div className="forms" role="tabpanel">
          {sec === 'plex' ? (
            <section aria-labelledby="s-plex">
              <h2 id="s-plex" className="sh">Plex</h2>
              <Row label="Server">
                <input type="text" className="inp mono" value={draft.plex.url} aria-label="Server" placeholder="http://127.0.0.1:32400" onChange={(e) => { set('plex', { url: e.target.value }); setPlexTest(null); }} style={{ flex: '1 1 240px', width: 'auto' }} />
                <button type="button" className="btn sm" disabled={testing} onClick={testPlex}>{testing ? 'Testing…' : 'Test'}</button>
                {plexState ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 600, color: plexState.ok ? undefined : 'var(--bad)' }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: plexState.ok ? 'var(--ok)' : 'var(--bad)' }} />{plexState.text}
                  </span>
                ) : null}
              </Row>
              <Row label="Token"><Secret id="s-token" label="Plex token" value={draft.plex.token} reset={reset} onChange={(v) => { set('plex', { token: v }); setPlexTest(null); }} /></Row>
              {(libs.data || []).length === 0 ? (
                <Row label="Libraries"><span style={{ color: 'var(--dim)' }}>{libs.loading ? 'Loading…' : 'No libraries yet. Test the connection to list them.'}</span></Row>
              ) : (libs.data || []).map((l, i) => {
                const on = draft.plex.libraries.includes(l.key);
                const note = !on || l.count == null ? '' : l.type === 'movie' ? plural(l.count, 'film') : plural(l.count, 'show');
                return (
                  <Row key={l.key} label={i ? '' : 'Libraries'}>
                    <Switch on={on} label={'Include ' + l.title} onChange={(v) => set('plex', { libraries: v ? [...draft.plex.libraries, l.key] : draft.plex.libraries.filter((x) => x !== l.key) })} />
                    <span>{l.title}</span>
                    <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{note}</span>
                  </Row>
                );
              })}
              <Row label="Read now">
                <button type="button" className="btn sm" onClick={async () => {
                  try { await api.scanLibrary(); toast('Reading the Plex libraries. New films show up in the Library as they come.'); }
                  catch (e) { toast(e instanceof Error ? e.message : String(e), true); }
                }}>Read the libraries now</button>
                <span style={{ fontSize: 12.5, color: 'var(--dim)' }}>Files already read are skipped.</span>
              </Row>
              {draft.plex.path_map.length ? (
                <Row label="Paths" top>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {draft.plex.path_map.map((p, i) => <span key={i} className="mono" style={{ fontSize: 12.5, color: 'var(--dim)' }}>{p.from} → {p.to}</span>)}
                  </span>
                </Row>
              ) : null}
            </section>
          ) : null}

          {sec === 'labels' ? (
            <section aria-labelledby="s-labels">
              <h2 id="s-labels" className="sh">Plex labels</h2>
              <Row label="Write labels">
                <Switch on={draft.labels.write} label="Write labels to Plex" onChange={(v) => set('labels', { write: v })} />
                {saved.labels.write ? <button type="button" className="btn sm" onClick={writeLabels}>Write now</button> : null}
              </Row>
              <Row label="Prefix" htmlFor="s-prefix"><input id="s-prefix" type="text" className="inp mono" value={draft.labels.prefix} onChange={(e) => set('labels', { prefix: e.target.value })} style={{ width: 140 }} /></Row>
              <Row label="Tags to write" top>
                {draft.labels.tags.map((t) => (
                  <button key={t} type="button" className="lt" aria-label={'Stop writing ' + tagName(t)} onClick={() => set('labels', { tags: draft.labels.tags.filter((x) => x !== t) })}>
                    {draft.labels.prefix + t.toLowerCase()} <b>×</b>
                  </button>
                ))}
                {labelPick ? (
                  <select className="sel" autoFocus aria-label="Tag to write" value="" onBlur={() => setLabelPick(false)}
                    onChange={(e) => { if (e.target.value) set('labels', { tags: [...draft.labels.tags, e.target.value] }); setLabelPick(false); }}>
                    <option value="">Pick a tag…</option>
                    {families.map((f) => (
                      <optgroup key={f.family} label={f.name}>
                        {f.tags.filter((t) => !draft.labels.tags.includes(t.id)).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </optgroup>
                    ))}
                  </select>
                ) : (
                  <button type="button" className="pill" style={{ borderStyle: 'dashed', height: 28 }} onClick={() => setLabelPick(true)}>Add a tag</button>
                )}
              </Row>
            </section>
          ) : null}

          {sec === 'ai' ? (
            <section aria-labelledby="s-ai">
              <h2 id="s-ai" className="sh">AI</h2>
              <Row label="Use AI"><Switch on={draft.ai.enabled} label="Use AI" onChange={(v) => set('ai', { enabled: v })} /></Row>
              {draft.ai.enabled ? (
                <>
                  <Row label="Text model" htmlFor="s-text"><input id="s-text" type="text" className="sel mono" value={draft.ai.model} placeholder="provider/model" onChange={(e) => set('ai', { model: e.target.value })} style={{ width: 300 }} /></Row>
                  <Row label="Vision model" htmlFor="s-vision"><input id="s-vision" type="text" className="sel mono" value={draft.ai.vision_model} placeholder="provider/model" onChange={(e) => set('ai', { vision_model: e.target.value })} style={{ width: 300 }} /></Row>
                  <Row label="Server address" htmlFor="s-base"><input id="s-base" type="url" className="inp mono" value={draft.ai.base_url} placeholder="Leave empty for the provider's own" onChange={(e) => set('ai', { base_url: e.target.value })} style={{ flex: '1 1 240px', width: 'auto' }} /></Row>
                  <Row label="API key"><Secret id="s-aikey" label="AI API key" value={draft.ai.api_key} reset={reset} onChange={(v) => set('ai', { api_key: v })} /></Row>
                  <Row label="Check" top><AiTest dirty={dirty} /></Row>
                  <Row label="Monthly limit" htmlFor="s-limit">
                    <input key={'lim' + reset} id="s-limit" type="text" className="inp mono" defaultValue={money(draft.ai.monthly_limit)} style={{ width: 110 }}
                      onChange={(e) => { const n = parseMoney(e.target.value); if (n !== null) set('ai', { monthly_limit: n }); }}
                      onBlur={(e) => { e.target.value = money(draft.ai.monthly_limit); }} />
                    <span className="mono" style={{ fontSize: 12.5, color: 'var(--dim)' }}>{money(status?.ai.month_cost)} used this month</span>
                    <Link to="/activity" style={{ fontSize: 12.5 }}>Activity</Link>
                  </Row>
                </>
              ) : (
                <div style={{ marginTop: 12, padding: '16px 18px', border: '1px dashed var(--border)', borderRadius: 10, fontSize: 14, color: 'var(--dim)' }}>Shots, scenes, signals and cast still work. Tags and named places need AI.</div>
              )}
            </section>
          ) : null}

          {sec === 'tags' ? (
            <section aria-labelledby="s-tags">
              <div className="sh" style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                <h2 id="s-tags" style={{ flex: 1, margin: 0, font: 'inherit' }}>Tags the AI looks for</h2>
                <Link to="/tags" style={{ font: "500 12.5px 'DM Sans', sans-serif" }}>All {allTags.length || ''} tags</Link>
              </div>
              {vocab.loading && !vocab.data ? <Loading /> : vocab.error ? <ErrorBox error={vocab.error} retry={vocab.reload} /> : null}
              {families.map((f) => {
                const on = !draft.tags.families_off.includes(f.family);
                return (
                  <Row key={f.family} label={<span style={{ display: 'flex', alignItems: 'center', gap: 10 }}><span style={{ flex: 'none', width: 6, height: 20, borderRadius: 3, background: `var(--f-${f.family})` }} />{f.name}</span>}>
                    <Switch on={on} label={'Look for ' + f.name + ' tags'} onChange={(v) => set('tags', { families_off: v ? draft.tags.families_off.filter((x) => x !== f.family) : [...draft.tags.families_off, f.family] })} />
                    <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{plural(f.tags.length, 'tag')}</span>
                    {f.subjective ? <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, border: '1px solid var(--border)', color: 'var(--dim)' }}>Subjective</span> : null}
                  </Row>
                );
              })}
            </section>
          ) : null}

          {sec === 'faces' ? (
            <section aria-labelledby="s-faces">
              <h2 id="s-faces" className="sh">Faces</h2>
              {draft.faces.models.map((m) => (
                <Row key={m.name} label={m.name}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: m.present ? 'var(--ok)' : 'var(--warn)' }}>{m.present ? 'Downloaded' : downloading ? 'Downloading…' : 'Not downloaded'}</span>
                  {!m.present && !downloading ? <button type="button" className="btn sm pri" onClick={downloadModels}>Download</button> : null}
                </Row>
              ))}
              {modelsMissing ? <div style={{ paddingTop: 10, fontSize: 13, color: 'var(--warn)' }}>The faces step is skipped until both models are downloaded.</div> : null}
            </section>
          ) : null}

          {sec === 'apps' ? <Apps requireKey={draft.server.require_key} setRequireKey={(v) => set('server', { require_key: v })} /> : null}

          {sec === 'general' ? (
            <section aria-labelledby="s-gen">
              <h2 id="s-gen" className="sh">General</h2>
              <Row label="Theme"><Seg label="Theme" value={draft.general.theme} options={[['system', 'System'], ['dark', 'Dark'], ['light', 'Light']]} onChange={(v) => set('general', { theme: v })} /></Row>
              <Row label="Language" htmlFor="s-lang">
                <select id="s-lang" className="sel" value={draft.general.language} onChange={(e) => set('general', { language: e.target.value as S['general']['language'] })}>
                  <option value="en">English</option><option value="es">Español</option>
                </select>
              </Row>
              <Row label="Clock"><Seg label="Clock" value={draft.general.clock} options={[['24h', '24-hour'], ['12h', '12-hour']]} onChange={(v) => set('general', { clock: v })} /></Row>
            </section>
          ) : null}

          {sec === 'analysis' ? (
            <section aria-labelledby="s-an">
              <h2 id="s-an" className="sh">Analysis</h2>
              {STEPS.map((n) => {
                const note = n === 'tags' && !draft.ai.enabled ? 'Needs AI' : n === 'faces' && modelsMissing ? 'Needs the face models' : '';
                return (
                  <div className="fr" key={n}>
                    <span className="fl mono" style={{ fontWeight: 500 }}>{n}</span>
                    <div className="fc">
                      <Switch on={draft.analysis.steps[n]} label={'Run ' + n} onChange={(v) => set('analysis', { steps: { ...draft.analysis.steps, [n]: v } })} />
                      <span style={{ color: 'var(--dim)' }}>{WHAT[n]}</span>
                      {note ? <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--warn)' }}>{note}</span> : null}
                    </div>
                  </div>
                );
              })}
              <Row label="No subtitles"><Switch on={draft.analysis.transcribe} label="Transcribe the dialogue" onChange={(v) => set('analysis', { transcribe: v })} /><span>Transcribe the dialogue when a video has no subtitles</span></Row>
              <Row label="Videos at once" htmlFor="s-par">
                <select id="s-par" className="sel" value={draft.analysis.at_once} onChange={(e) => set('analysis', { at_once: Number(e.target.value) as 1 | 2 | 4 })}>
                  <option value={1}>1</option><option value={2}>2</option><option value={4}>4</option>
                </select>
              </Row>
              <Row label="When">
                <Seg label="When to analyse" value={atNight ? 'night' : 'always'} options={[['always', 'Always'], ['night', 'Only at night']]}
                  onChange={(v) => set('analysis', v === 'night' ? { window_start: saved.analysis.window_start || '01:00', window_end: saved.analysis.window_end || '07:00' } : { window_start: '', window_end: '' })} />
                {atNight ? (
                  <>
                    <input type="time" className="inp mono" value={draft.analysis.window_start} aria-label="From" onChange={(e) => set('analysis', { window_start: e.target.value })} style={{ width: 96 }} />
                    <span>to</span>
                    <input type="time" className="inp mono" value={draft.analysis.window_end} aria-label="To" onChange={(e) => set('analysis', { window_end: e.target.value })} style={{ width: 96 }} />
                  </>
                ) : null}
              </Row>
              <Row label="New videos"><Switch on={draft.analysis.on_new} label="Analyse new videos" onChange={(v) => set('analysis', { on_new: v })} /><span>Analyse when Plex adds them</span></Row>
            </section>
          ) : null}

          {sec === 'places' ? <Places sources={sources} setSources={(s) => setDraft((d) => (d ? { ...d, places: s } : d))} /> : null}

          {sec === 'notify' ? (
            <section aria-labelledby="s-no">
              <div className="sh" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <h2 id="s-no" style={{ flex: 1, margin: 0, font: 'inherit' }}>Notifications</h2>
                <Link to="/api?tab=events" className="btn sm">Events</Link>
                <button type="button" className="btn sm" onClick={() => setAddingHook(true)}>Add a webhook</button>
              </div>
              <Webhooks adding={addingHook} onAdded={() => setAddingHook(false)} />
            </section>
          ) : null}

          {sec === 'backup' ? (
            <section aria-labelledby="s-bk">
              <h2 id="s-bk" className="sh">Backup</h2>
              <Row label="Export"><span>Kept and dropped tags, confirmed faces, named places</span><a href={urls.backup()} className="btn sm" download>Export</a></Row>
              <Row label="Import">
                <button type="button" className="btn sm" onClick={() => fileRef.current?.click()}>Choose a file</button>
                <input ref={fileRef} type="file" accept="application/json,.json" className="sr" aria-label="Backup file" onChange={(e) => { const f = e.target.files?.[0]; if (f) importFile(f); }} />
              </Row>
              <h2 className="sh" style={{ marginTop: 34 }}>About</h2>
              <Row label="Version"><span className="mono">{status?.version || '…'}</span><a href="https://github.com/jhd3197/marcarr/releases" target="_blank" rel="noreferrer" className="btn sm">Check for updates</a></Row>
              <Row label="Logs"><a href={urls.logs()} target="_blank" rel="noreferrer" className="btn sm">Open logs</a><a href={urls.logs()} download="marcarr.log" className="btn sm">Download</a></Row>
              <Row label="Data folder">
                <span className="mono" style={{ overflowWrap: 'anywhere' }}>{draft.server.data_dir}</span>
                <button type="button" className="btn sm" onClick={async () => toast((await copyText(draft.server.data_dir)) ? 'Path copied' : 'Could not copy', false)}>Copy path</button>
              </Row>
              <Row label="Source"><span className="mono">github.com/jhd3197/marcarr</span><span style={{ color: 'var(--dim)' }}>MIT</span></Row>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
