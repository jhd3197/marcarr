// One scene: contact sheet, start/end trims, dialogue, tags to keep or drop, people.
// Built from docs/design/scene (the 760px media query gives the phone layout).
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { api, urls } from '../api/client';
import type { EvidenceItem, Face, Person, SceneDetail, Tag } from '../api/types';
import { css, ErrorBox, Loading } from '../components/kit';
import { useApp } from '../components/Shell';
import { lineFor } from '../lib/evidence';
import { evAt, evText, hms, ms } from '../lib/format';
import { useApi, useKeys } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { bgUrl, chipCss, errText, familyName, sourceName } from './review/labels';
import './scene.css';

const AV = (size: number) =>
  `flex:none;display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:50%;font:700 ${Math.round(size * 0.45)}px DM Sans,sans-serif;color:var(--text);background:var(--hover)`;
/** A face below this score, not yet confirmed or rejected, asks the person. */
const UNSURE_BELOW = 0.6;

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Split a dialogue line so words a tag "heard" are marked in the tag's family colour. */
function markLine(text: string, terms: Map<string, string>): ReactNode[] {
  if (!terms.size) return [text];
  const keys = [...terms.keys()].sort((a, b) => b.length - a.length);
  const re = new RegExp('(' + keys.map(escapeRe).join('|') + ')', 'gi');
  return text.split(re).filter((p) => p !== '').map((p, i) => {
    const fam = terms.get(p.toLowerCase());
    if (!fam) return <span key={i}>{p}</span>;
    const fv = `var(--f-${fam})`;
    return <span key={i} style={css(`border-radius:3px;padding:0 2px;font-weight:600;box-shadow:inset 0 -2px 0 ${fv};background:color-mix(in srgb,${fv} 22%,transparent)`)}>{p}</span>;
  });
}

/** Up to six stills spread evenly across the scene. */
function pickFrames(frames: { t: number; url: string }[], max = 6) {
  if (frames.length <= max) return frames;
  return Array.from({ length: max }, (_, i) => frames[Math.round((i * (frames.length - 1)) / (max - 1))]);
}

export default function ScenePage() {
  const { video = '', n: nParam = '1' } = useParams();
  const n = Number(nParam);
  const nav = useNavigate();
  const toast = useToast();
  const { refreshStatus } = useApp();
  const scene = useApi(() => api.scene(video, n), [video, n]);
  const s = scene.data;

  if (scene.loading && !s) return <Loading />;
  if (scene.error && !s) return <ErrorBox error={scene.error} retry={scene.reload} />;
  if (!s) return null;
  return <SceneView key={`${video}/${n}`} s={s} set={scene.set} nav={(m) => nav(`/videos/${video}/scenes/${m}`)} toast={toast} refreshStatus={refreshStatus} />;
}

function SceneView({ s, set, nav, toast, refreshStatus }: {
  s: SceneDetail; set: (v: SceneDetail) => void; nav: (n: number) => void;
  toast: (t: string, bad?: boolean) => void; refreshStatus: () => void;
}) {
  const [trim, setTrim] = useState({ s: s.start, e: s.end });
  const [busy, setBusy] = useState(false);
  const [play, setPlay] = useState<number | null>(null); // seconds into the clip, null = not playing
  const [adding, setAdding] = useState(false);
  const [vocab, setVocab] = useState<{ family: string; name: string; tags: { id: string; name: string }[] }[] | null>(null);
  const [pick, setPick] = useState('');
  const [faceState, setFaceState] = useState<Record<string, 'yes' | 'no'>>({});
  const videoRef = useRef<HTMLVideoElement>(null);
  const [frameAt, setFrameAt] = useState<{ t: number; what: string } | null>(null);
  const [flash, setFlash] = useState<number | null>(null);
  useEffect(() => {
    if (flash === null) return;
    const id = setTimeout(() => setFlash(null), 1800);
    return () => clearTimeout(id);
  }, [flash]);
  useEffect(() => {
    if (!frameAt) return;
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setFrameAt(null); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [frameAt]);

  // -- evidence: jump to the line that was heard, open the frame where it was seen --
  const toLine = (item: EvidenceItem) => {
    const i = lineFor(s.lines, item);
    if (i < 0) {
      toast(`"${evText(item)}" is not in this scene's dialogue`, true);
      return;
    }
    document.getElementById(`ln-${i}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setFlash(i);
  };
  const copyBrief = async () => {
    try {
      const link = `${location.origin}/titles/${encodeURIComponent(s.title.id)}?t=${Math.floor(s.start)}`;
      const { text } = await api.sceneBrief(s.video, s.n, link);
      await navigator.clipboard.writeText(text);
      toast('Brief copied');
    } catch (e) {
      toast(`Could not copy the brief: ${errText(e)}`, true);
    }
  };
  useEffect(() => setTrim({ s: s.start, e: s.end }), [s.start, s.end]);

  // Answers can come back out of order: always build on the latest scene.
  const cur = useRef(s);
  cur.current = s;
  const update = (f: (x: SceneDetail) => SceneDetail) => { cur.current = f(cur.current); set(cur.current); };
  const setTag = (t: Tag) => update((x) => ({ ...x, all_tags: x.all_tags.map((y) => (y.id === t.id ? t : y)) }));
  const proposed = s.all_tags.filter((t) => t.status === 'proposed');

  // -- tags ------------------------------------------------------------------------
  const decide = async (t: Tag, action: 'keep' | 'drop' | 'undo') => {
    try {
      const out = await (action === 'keep' ? api.keep(t.id) : action === 'drop' ? api.drop(t.id) : api.undo(t.id));
      setTag(out);
      refreshStatus();
    } catch (e) {
      toast(`Could not ${action} ${t.name}: ${errText(e)}`, true);
    }
  };
  const decideAll = async (action: 'keep' | 'drop') => {
    if (!proposed.length) return;
    const ids = new Set(proposed.map((t) => t.id));
    try {
      await api.bulk([...ids], action);
      const status = action === 'keep' ? 'accepted' : 'rejected';
      update((x) => ({ ...x, all_tags: x.all_tags.map((t) => (ids.has(t.id) ? { ...t, status } : t)) }));
      refreshStatus();
    } catch (e) {
      toast(`Could not ${action} the tags: ${errText(e)}`, true);
    }
  };
  useKeys({ k: () => void decideAll('keep'), d: () => void decideAll('drop') }, [s]);

  const openAdd = () => {
    setAdding(true);
    if (!vocab) api.vocab().then((v) => setVocab([...(v.mine.some((t) => !t.retired) ? [{ family: 'mine', name: 'My tags', tags: v.mine.filter((t) => !t.retired) }] : []), ...v.families]), (e) => toast(`Could not load the tags: ${errText(e)}`, true));
  };
  const addTag = async () => {
    if (!pick) return;
    try {
      const t = await api.proposeTag(s.video, { tag: pick, start: s.start, end: s.end, status: 'accepted' });
      update((x) => ({ ...x, all_tags: [...x.all_tags, t] }));
      setAdding(false);
      setPick('');
    } catch (e) {
      toast(`Could not add the tag: ${errText(e)}`, true);
    }
  };

  // -- start and end -----------------------------------------------------------------
  const move = async (body: { start?: number; end?: number; snap?: boolean }) => {
    setBusy(true);
    try {
      const out = await api.moveScene(s.video, s.n, body);
      update(() => out);
    } catch (e) {
      setTrim({ s: s.start, e: s.end });
      toast(`Could not move the scene: ${errText(e)}`, true);
    } finally {
      setBusy(false);
    }
  };
  const nudge = (k: 's' | 'e', d: number) => {
    const v = Math.max(0, trim[k] + d);
    setTrim({ ...trim, [k]: v });
    void move(k === 's' ? { start: v } : { end: v });
  };
  const snap = (k: 's' | 'e') => void move(k === 's' ? { start: trim.s, snap: true } : { end: trim.e, snap: true });

  // -- dialogue --------------------------------------------------------------------
  const terms = useMemo(() => {
    const m = new Map<string, string>();
    for (const t of s.all_tags) {
      if (t.status === 'rejected') continue;
      for (const h of (t.evidence?.heard || []).map(evText)) if (h.trim()) m.set(h.trim().toLowerCase(), t.family || 'place');
    }
    return m;
  }, [s.all_tags]);

  // -- people ----------------------------------------------------------------------
  const people = useMemo(() => {
    const byId = new Map<string, Person>(s.cast.map((p) => [p.id, p]));
    const faces = new Map<string, Face[]>();
    for (const f of s.faces) if (f.person) faces.set(f.person, [...(faces.get(f.person) || []), f]);
    const ids = [...faces.keys(), ...s.people.filter((p) => !faces.has(p))];
    return ids.map((id) => {
      const p = byId.get(id);
      const fs = faces.get(id) || [];
      const best = fs.reduce<Face | null>((a, f) => (!a || f.score > a.score ? f : a), null);
      const open = fs.filter((f) => f.confirmed === null);
      const confirmed = fs.some((f) => f.confirmed === true);
      const rejected = fs.length > 0 && fs.every((f) => f.confirmed === false);
      return { id, p, best, open, confirmed, rejected, unsure: !confirmed && !rejected && open.length > 0 && (best?.score ?? 1) < UNSURE_BELOW };
    });
  }, [s.cast, s.faces, s.people]);
  // People heard speaking (an app found them) or only named in the dialogue, not seen.
  const offscreen = useMemo(() => {
    const byId = new Map<string, Person>(s.cast.map((p) => [p.id, p]));
    const shown = new Set(people.map((x) => x.id));
    return [...(s.speakers || []).map((id) => ({ id, how: 'Heard speaking, not seen' })), ...(s.mentioned || []).map((id) => ({ id, how: 'Only named in the dialogue' }))]
      .filter((x) => !shown.has(x.id)).map((x) => ({ ...x, p: byId.get(x.id) }));
  }, [s.cast, s.speakers, s.mentioned, people]);

  const judgeFaces = async (id: string, faces: Face[], v: 'yes' | 'no') => {
    try {
      if (faces.length === 1) await (v === 'yes' ? api.confirmFace(faces[0].id) : api.rejectFace(faces[0].id));
      else await api.bulkFaces(faces.map((f) => f.id), v === 'yes' ? 'confirm' : 'reject');
      setFaceState((x) => ({ ...x, [id]: v }));
    } catch (e) {
      toast(`Could not save that: ${errText(e)}`, true);
    }
  };

  const frames = pickFrames(s.frames);
  const left = proposed.length;

  return (
    <div className="pg-scene" style={{ display: 'contents' }}>
      <header style={css('display: flex; align-items: flex-end; flex-wrap: wrap; gap: 10px 20px')}>
        <div style={css('flex: 1 1 420px; min-width: 0; display: flex; flex-direction: column; gap: 8px')}>
          <nav className="crumb" aria-label="Breadcrumb">
            <Link to="/">Library</Link><span>/</span>
            <Link to={`/titles/${encodeURIComponent(s.title.id)}`}>{s.title.name}</Link><span>/</span>
            <span>Scene {s.n}</span>
          </nav>
          <h1 className="h1">Scene {s.n}</h1>
          {s.summary ? <div style={css('font-size: 15px; color: var(--dim)')}>{s.summary}</div> : null}
        </div>
        <div style={css('display: flex; align-items: center; gap: 8px')}>
          <span className="mono" style={css('font-size: 12px; color: var(--dim)')}>{left ? `${left} to decide` : 'All decided'}</span>
          <button type="button" className="btn ghost" onClick={() => void copyBrief()}>Copy brief</button>
          <button type="button" className="btn" disabled={s.prev == null} onClick={() => s.prev != null && nav(s.prev)}>Previous scene</button>
          <button type="button" className="btn" disabled={s.next == null} onClick={() => s.next != null && nav(s.next)}>Next scene</button>
        </div>
      </header>

      <div style={css('display: flex; flex-wrap: wrap; gap: 22px 26px; align-items: flex-start')}>
        <div style={css('flex: 3 1 440px; min-width: 0; display: flex; flex-direction: column; gap: 22px')}>
          <section aria-label="Contact sheet" style={css('display: flex; flex-direction: column; gap: 6px')}>
            {play !== null ? (
              <div style={css('position: relative')}>
                <video
                  ref={videoRef}
                  src={urls.clip(s.video, s.start, s.end)}
                  controls
                  autoPlay
                  onLoadedMetadata={() => { if (videoRef.current && play > 0) videoRef.current.currentTime = play; }}
                  style={css('display: block; width: 100%; aspect-ratio: 2.4/1; border-radius: 6px; background: #000')}
                />
                <button type="button" className="btn sm" style={css('position: absolute; top: 8px; right: 8px')} onClick={() => setPlay(null)}>Close</button>
              </div>
            ) : null}
            <div className="cs">
              {frames.map((f, i) => (
                <span
                  key={f.t + ':' + i}
                  role="button"
                  tabIndex={0}
                  aria-label={`Frame ${i + 1} of ${frames.length}, play the scene from ${hms(f.t)}`}
                  style={{ backgroundImage: bgUrl(f.url), backgroundSize: 'cover', backgroundPosition: 'center' }}
                  onClick={() => setPlay(Math.max(0, f.t - s.start))}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPlay(Math.max(0, f.t - s.start)); } }}
                >
                  <i>{hms(f.t)}</i>
                </span>
              ))}
            </div>
          </section>

          <section aria-label="Start and end" className="box" style={css('padding: 14px 16px; display: flex; flex-wrap: wrap; gap: 12px 28px')}>
            {([['Start', 's'], ['End', 'e']] as const).map(([name, k]) => (
              <div key={k} style={css('display: flex; align-items: center; gap: 8px')}>
                <span className="lab" style={css('width: 40px')}>{name}</span>
                <button type="button" className="btn sm" aria-label={`${name} one second earlier`} disabled={busy} onClick={() => nudge(k, -1)}>−</button>
                <span className="mono" style={css('min-width: 70px; text-align: center; font-size: 15px')}>{hms(trim[k])}</span>
                <button type="button" className="btn sm" aria-label={`${name} one second later`} disabled={busy} onClick={() => nudge(k, 1)}>+</button>
                <button type="button" className="btn sm" disabled={busy} onClick={() => snap(k)}>Snap to cut</button>
              </div>
            ))}
            <span className="mono" style={css('align-self: center; font-size: 12px; color: var(--dim)')}>{ms(Math.max(0, trim.e - trim.s))} long</span>
          </section>

          <section aria-label="Dialogue">
            <h2 className="h2" style={css('padding-bottom: 8px')}>Dialogue</h2>
            {s.lines.length ? s.lines.map((l, i) => (
              <div key={l.start + ':' + i} id={`ln-${i}`} className={'dl' + (flash === i ? ' flash' : '')}>
                <span className="mono" style={css('flex: none; width: 58px; font-size: 12px; color: var(--faint); padding-top: 2px')}>{hms(l.start)}</span>
                <span>{markLine(l.text, terms)}</span>
              </div>
            )) : <div style={css('font-size: 13px; color: var(--faint)')}>No dialogue in this scene.</div>}
          </section>
        </div>

        <div style={css('flex: 2 1 360px; min-width: 0; display: flex; flex-direction: column; gap: 22px')}>
          <section aria-label="Tags" className="box" style={css('padding: 6px 18px')}>
            {s.all_tags.map((t) => {
              const byPerson = t.source === 'person';
              const heard = t.evidence?.heard || [];
              const seen = t.evidence?.seen || [];
              return (
                <div key={t.id} className="tr">
                  <div style={css('flex: 1 1 200px; min-width: 0; display: flex; flex-direction: column; gap: 5px')}>
                    <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px')}>
                      <span style={css(chipCss(t.family, t.status))}>{t.name}</span>
                      <span style={css('font-size: 12px; color: var(--faint)')}>
                        {familyName(t.family)}{byPerson ? ' · kept by you' : ' · proposed by ' + sourceName(t.source)}
                      </span>
                    </div>
                    {heard.length ? (
                      <div className="ev"><b>Heard</b>{heard.map((h, i) => (
                        <span key={i}>{i ? ', ' : ''}<button type="button" className="evb" title="Show the line" aria-label={`${evText(h)}: show the line`} onClick={() => toLine(h)}>
                          {evText(h)}{evAt(h) !== null ? <i>{hms(evAt(h)!)}</i> : null}
                        </button></span>
                      ))}</div>
                    ) : null}
                    {seen.length ? (
                      <div className="ev"><b>Seen</b>{seen.map((x, i) => {
                        const at = evAt(x);
                        return (
                          <span key={i}>{i ? ', ' : ''}{at !== null ? (
                            <button type="button" className="evb" title="Open the frame" aria-label={`${evText(x)}: open the frame at ${hms(at)}`} onClick={() => setFrameAt({ t: at, what: evText(x) })}>{evText(x)}<i>{hms(at)}</i></button>
                          ) : evText(x)}</span>
                        );
                      })}</div>
                    ) : null}
                  </div>
                  {t.status === 'proposed' ? (
                    <div style={css('display: flex; gap: 6px')}>
                      <button type="button" className="btn sm pri" onClick={() => void decide(t, 'keep')}>Keep</button>
                      <button type="button" className="btn sm" onClick={() => void decide(t, 'drop')}>Drop</button>
                    </div>
                  ) : (
                    <div style={css('display: flex; align-items: center; gap: 10px')}>
                      <span style={css('font-size:12.5px;font-weight:600;color:' + (t.status === 'accepted' ? 'var(--ok)' : 'var(--faint)'))}>{t.status === 'accepted' ? 'Accepted' : 'Rejected'}</span>
                      {!byPerson ? <button type="button" className="btn sm ghost" onClick={() => void decide(t, 'undo')}>Undo</button> : null}
                    </div>
                  )}
                </div>
              );
            })}
            {adding ? (
              <div className="tr" style={css('align-items: center')}>
                <select className="sel" aria-label="Tag to add" value={pick} onChange={(e) => setPick(e.target.value)} style={css('flex: 1 1 200px; min-width: 0')}>
                  <option value="">{vocab ? 'Pick a tag' : 'Loading…'}</option>
                  {(vocab || []).map((f) => (
                    <optgroup key={f.family} label={f.name}>
                      {f.tags.filter((v) => !s.all_tags.some((t) => t.tag === v.id && t.status !== 'rejected')).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                    </optgroup>
                  ))}
                </select>
                <button type="button" className="btn sm pri" disabled={!pick} onClick={() => void addTag()}>Add</button>
                <button type="button" className="btn sm ghost" onClick={() => { setAdding(false); setPick(''); }}>Cancel</button>
              </div>
            ) : null}
            <div className="tr" style={css('align-items: center')}>
              {!adding ? <button type="button" className="pill" style={css('border-style: dashed')} onClick={openAdd}>Add a tag</button> : null}
              <div style={css('flex: 1')} />
              <button type="button" className="btn sm" disabled={!left} onClick={() => void decideAll('keep')}>Keep all <span className="key">K</span></button>
              <button type="button" className="btn sm" disabled={!left} onClick={() => void decideAll('drop')}>Drop all <span className="key">D</span></button>
            </div>
          </section>

          <section aria-label="People in this scene">
            <h2 className="h2" style={css('padding-bottom: 8px')}>People</h2>
            {people.map(({ id, p, best, open, confirmed, unsure }) => {
              const short = (p?.character || p?.actor || id).split(/\s+/)[0];
              const fs = faceState[id];
              const name = fs === 'yes' ? short : fs === 'no' ? 'Not ' + short : unsure ? short + '?' : short;
              const who = p ? `${p.actor} as ${p.character}` : id;
              const sub = fs === 'yes' ? who + ' · confirmed by you' : fs === 'no' ? 'Face left without a name'
                : confirmed ? who + ' · confirmed' : best ? `${who} · ${best.score.toFixed(2)}` : who;
              const ask = unsure && !fs;
              const av = AV(44) + (p?.photo ? ` url(${p.photo}) center/cover` : '') + (ask ? ';outline:2px dashed var(--warn);outline-offset:2px' : '');
              return (
                <div key={id} style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; padding: 10px 0; border-top: 1px solid var(--line)')}>
                  <span style={css(av)} />
                  <div style={css('flex: 1 1 160px; min-width: 0')}>
                    <div style={css('font-size: 15px; font-weight: 600')}><Link to={`/people/${encodeURIComponent(id)}`} style={{ color: 'inherit', textDecoration: 'none' }}>{name}</Link></div>
                    <div style={css('font-size: 12px; color: var(--dim)')}>{sub}</div>
                  </div>
                  {ask ? (
                    <div style={css('display: flex; gap: 6px')}>
                      <button type="button" className="btn sm pri" onClick={() => void judgeFaces(id, open, 'yes')}>Confirm</button>
                      <button type="button" className="btn sm" onClick={() => void judgeFaces(id, open, 'no')}>Not him</button>
                    </div>
                  ) : null}
                </div>
              );
            })}
            {offscreen.map(({ id, p, how }) => (
              <div key={id} style={css('display: flex; align-items: center; gap: 12px; padding: 10px 0; border-top: 1px solid var(--line)')}>
                <span style={css(AV(44) + (p?.photo ? ` url(${p.photo}) center/cover` : '') + ';opacity:.6;outline:1.5px dotted var(--faint);outline-offset:2px')} />
                <div style={css('flex: 1 1 160px; min-width: 0')}>
                  <div style={css('font-size: 15px; font-weight: 600')}><Link to={`/people/${encodeURIComponent(id)}`} style={{ color: 'inherit', textDecoration: 'none' }}>{(p?.character || p?.actor || id).split(/\s+/)[0]}</Link></div>
                  <div style={css('font-size: 12px; color: var(--dim)')}>{how}</div>
                </div>
              </div>
            ))}
            {!people.length && !offscreen.length ? <div style={css('font-size: 13px; color: var(--faint); padding: 10px 0; border-top: 1px solid var(--line)')}>No one recognised in this scene.</div> : null}
          </section>
        </div>
      </div>
      {frameAt ? (
        <div role="dialog" aria-modal="true" aria-label={`Frame at ${hms(frameAt.t)}`} className="frame-over" onClick={(e) => { if (e.target === e.currentTarget) setFrameAt(null); }}>
          <div className="box" style={css('max-width: min(960px, 92vw); padding: 12px; display: flex; flex-direction: column; gap: 10px')}>
            <img src={urls.frame(s.video, frameAt.t, 720)} alt={`${frameAt.what} at ${hms(frameAt.t)}`} style={css('display: block; width: 100%; border-radius: 6px; background: #000')} />
            <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px')}>
              <span style={css('flex: 1; font-size: 13.5px')}><b>{frameAt.what}</b> <span className="mono" style={{ color: 'var(--dim)' }}>{hms(frameAt.t)}</span></span>
              <button type="button" className="btn sm" onClick={() => { setPlay(Math.max(0, frameAt.t - s.start)); setFrameAt(null); }}>Play from here</button>
              <button type="button" className="btn sm ghost" autoFocus onClick={() => setFrameAt(null)}>Close</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
