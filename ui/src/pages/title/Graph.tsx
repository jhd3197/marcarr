// The character graph of a title page: one circle per person, sized by screen time,
// and a line between two people for every pair seen in the same scenes. Built from
// sightings only: someone named in the dialogue draws no line.
import { useMemo, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router';
import { api } from '../../api/client';
import type { CharacterGraph, GraphPair, GraphPerson, Scene } from '../../api/types';
import { Avatar, css, ErrorBox, Loading, Switch } from '../../components/kit';
import { hms, length, plural } from '../../lib/format';
import { useApi } from '../../lib/hooks';
import { ends, HEIGHT, label as shortLabel, layout, neighbours, shown, strokeWidth, WIDTH } from './graphLayout';

type Pick = { kind: 'person'; id: string } | { kind: 'pair'; a: string; b: string } | null;

export interface GraphProps {
  title: string;
  video: string;
  through: number | null;
  scenes: Scene[];
  stepsKey: string; // reload when a step changes state
  onSeek: (t: number) => void;
}

const readable = (p: GraphPerson) => (p.name === p.id ? p.id.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) : p.name);
const on = (e: KeyboardEvent, fn: () => void) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fn();
  }
};

export function Graph({ title, video, through, scenes, stepsKey, onSeek }: GraphProps) {
  const res = useApi(() => api.graph(title, { video, through }), [title, video, through, stepsKey]);
  return (
    <section aria-label="Who is seen with whom" className="box" style={css('padding: 16px 18px 14px')}>
      {res.error && !res.data ? <ErrorBox error={res.error} retry={res.reload} />
        : !res.data ? <Loading />
        : <GraphBody g={res.data} scenes={scenes} video={video} onSeek={onSeek} />}
    </section>
  );
}

function GraphBody({ g, scenes, video, onSeek }: { g: CharacterGraph; scenes: Scene[]; video: string; onSeek: (t: number) => void }) {
  const [minShared, setMinShared] = useState(1);
  const [minor, setMinor] = useState(false);
  const [pick, setPick] = useState<Pick>(null);
  const [hover, setHover] = useState<string | null>(null);

  const view = useMemo(() => shown(g, minShared, minor), [g, minShared, minor]);
  const placed = useMemo(() => layout(view.people, view.pairs), [view]);
  const byId = useMemo(() => new Map(g.people.map((p) => [p.id, p])), [g.people]);
  const most = view.maxShared;
  const focus = hover ?? (pick?.kind === 'person' ? pick.id : null);
  const lit = focus ? neighbours(view.pairs, focus) : null;
  const pickedPair = pick?.kind === 'pair' ? g.pairs.find((e) => e.a === pick.a && e.b === pick.b) || null : null;
  const pickedPerson = pick?.kind === 'person' ? byId.get(pick.id) || null : null;
  const isPair = (e: GraphPair) => pick?.kind === 'pair' && pick.a === e.a && pick.b === e.b;

  const header = (
    <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 18px; padding-bottom: 12px')}>
      <h2 className="h2" style={{ flex: '1 0 auto', whiteSpace: 'nowrap' }}>Who is seen with whom</h2>
      <span className="mono" style={css('font-size: 12px; color: var(--dim)')}>
        {plural(view.people.length, 'person', 'people')} · {plural(view.pairs.length, 'link')}
        {g.through ? ` · through scene ${g.through} of ${g.total_scenes}` : ''}
      </span>
      <label style={css('display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--dim)')}>
        Together in at least
        <input type="range" min={1} max={Math.max(1, most)} value={Math.min(minShared, Math.max(1, most))} disabled={most <= 1}
          onChange={(e) => setMinShared(Number(e.target.value))} aria-label="Scenes together" style={{ width: 110 }} />
        <span className="mono" style={{ minWidth: 64 }}>{plural(Math.min(minShared, Math.max(1, most)), 'scene')}</span>
      </label>
      <span style={css('display: inline-flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--dim)')}>
        <Switch on={minor} onChange={setMinor} label="Show minor characters" />Minor characters{view.hiddenPeople > 0 && !minor ? ` (${view.hiddenPeople} hidden)` : ''}
      </span>
    </div>
  );

  if (!g.people.length) {
    return (
      <>
        {header}
        <div style={css('padding: 28px 20px; border: 1px dashed var(--border); border-radius: 12px; font-size: 14px; color: var(--dim)')}>
          Nobody is recognised in {g.through ? 'these scenes' : 'this video'} yet. The graph fills in once faces are matched to the cast, or tags name who is on screen.
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <div style={css('display: flex; flex-wrap: wrap; gap: 14px')}>
        <div style={css('flex: 3 1 520px; min-width: 0; border-radius: 10px; background: var(--well)')}>
          <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Character graph" style={{ display: 'block', width: '100%', height: 'auto' }}
            onClick={(e) => { if (e.target === e.currentTarget) setPick(null); }}>
            <defs>
              {view.people.map((p, i) => {
                const at = placed.get(p.id);
                return at ? <clipPath key={p.id} id={'gc-' + i}><circle cx={at.x} cy={at.y} r={at.r - 2} /></clipPath> : null;
              })}
            </defs>
            {view.pairs.map((e) => {
              const a = placed.get(e.a), b = placed.get(e.b);
              if (!a || !b) return null;
              const l = ends(a, b);
              const dim = lit && !(lit.has(e.a) && lit.has(e.b) && (e.a === focus || e.b === focus));
              const sel = isPair(e);
              const label = `${readable(byId.get(e.a)!)} and ${readable(byId.get(e.b)!)}: ${plural(e.scenes.length, 'scene')} together`;
              return (
                <g key={e.a + '|' + e.b} role="button" tabIndex={0} aria-label={label} style={{ cursor: 'pointer' }}
                  onClick={() => setPick({ kind: 'pair', a: e.a, b: e.b })} onKeyDown={(k) => on(k, () => setPick({ kind: 'pair', a: e.a, b: e.b }))}>
                  <title>{label}</title>
                  <line {...l} stroke={sel ? 'var(--accent)' : 'var(--dim)'} strokeOpacity={dim ? 0.12 : sel ? 1 : 0.55} strokeWidth={strokeWidth(e.scenes.length, most)} strokeLinecap="round" />
                  <line {...l} stroke="transparent" strokeWidth={14} />
                </g>
              );
            })}
            {view.people.map((p, i) => {
              const at = placed.get(p.id);
              if (!at) return null;
              const dim = lit && !lit.has(p.id);
              const sel = pick?.kind === 'person' ? pick.id === p.id : pick?.kind === 'pair' ? pick.a === p.id || pick.b === p.id : false;
              const name = readable(p);
              const onlyNamed = p.scenes.length === 0;
              return (
                <g key={p.id} role="button" tabIndex={0} aria-label={`${name}: seen in ${plural(p.scenes.length, 'scene')}`} style={{ cursor: 'pointer' }} opacity={dim ? 0.25 : 1}
                  onClick={() => setPick({ kind: 'person', id: p.id })} onKeyDown={(k) => on(k, () => setPick({ kind: 'person', id: p.id }))}
                  onMouseEnter={() => setHover(p.id)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(p.id)} onBlur={() => setHover(null)}>
                  <title>{`${name}${p.actor && p.actor !== name ? ` (${p.actor})` : ''}: ${onlyNamed ? 'only heard or named' : `seen in ${plural(p.scenes.length, 'scene')}, ${length(p.seconds) || '<1m'}`}`}</title>
                  <circle cx={at.x} cy={at.y} r={at.r} fill="var(--hover)" stroke={sel ? 'var(--accent)' : onlyNamed ? 'var(--faint)' : 'var(--border)'}
                    strokeWidth={sel ? 3 : 1.5} strokeDasharray={onlyNamed ? '3 3' : undefined} />
                  {p.photo ? <image href={p.photo} x={at.x - at.r} y={at.y - at.r} width={at.r * 2} height={at.r * 2} preserveAspectRatio="xMidYMid slice" clipPath={`url(#gc-${i})`} />
                    : <text x={at.x} y={at.y} dy="0.35em" textAnchor="middle" fill="var(--text)" style={{ font: `700 ${Math.round(at.r * 0.7)}px DM Sans,sans-serif`, pointerEvents: 'none' }}>{initials(name)}</text>}
                  <text x={at.x} y={at.y + at.r + 13} textAnchor="middle" fill={sel ? 'var(--text)' : 'var(--dim)'} style={{ font: `${sel ? 700 : 600} 11.5px DM Sans,sans-serif`, pointerEvents: 'none' }}>{shortLabel(name)}</text>
                </g>
              );
            })}
          </svg>
          <div style={css('display: flex; flex-wrap: wrap; gap: 6px 16px; padding: 8px 12px; font-size: 11.5px; color: var(--faint)')}>
            <span>Circle size: screen time</span>
            <span>Line weight: scenes together</span>
            <span>Dashed circle: only heard or named</span>
          </div>
        </div>
        <aside aria-label="Details" style={css('flex: 1 1 260px; min-width: 0; max-height: 600px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px')}>
          {pickedPerson ? <PersonPanel p={pickedPerson} byId={byId} onSeek={onSeek} onPair={(id) => {
            const [a, b] = pickedPerson.id < id ? [pickedPerson.id, id] : [id, pickedPerson.id];
            setPick({ kind: 'pair', a, b });
          }} />
            : pickedPair ? <PairPanel e={pickedPair} byId={byId} scenes={scenes} video={video} onSeek={onSeek} onPerson={(id) => setPick({ kind: 'person', id })} />
            : <div style={css('padding: 16px; border: 1px dashed var(--border); border-radius: 10px; font-size: 13.5px; color: var(--dim)')}>
                Pick a person to see when they first appear, their longest absence and who they share scenes with. Pick a line to list the scenes two people share.
              </div>}
        </aside>
      </div>
    </>
  );
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('');
}

const row = 'display: flex; align-items: baseline; justify-content: space-between; gap: 10px; font-size: 13px';
const jump = 'padding: 0; border: 0; background: none; color: var(--mark); font: 600 12.5px DM Mono,monospace; cursor: pointer; white-space: nowrap';

function PersonPanel({ p, byId, onSeek, onPair }: { p: GraphPerson; byId: Map<string, GraphPerson>; onSeek: (t: number) => void; onPair: (id: string) => void }) {
  const name = readable(p);
  return (
    <>
      <div style={css('display: flex; align-items: center; gap: 10px')}>
        <Avatar name={name} photo={p.photo} size={44} />
        <div style={css('min-width: 0')}>
          <Link to={`/people/${encodeURIComponent(p.id)}`} className="hd" style={css('display: block; font-size: 17px; font-weight: 700; color: var(--text); text-decoration: none')}>{name}</Link>
          {p.actor && p.actor !== name ? <div style={css('font-size: 12.5px; color: var(--dim)')}>{p.actor}</div> : null}
        </div>
      </div>
      <div style={css('display: flex; flex-direction: column; gap: 8px; padding: 12px 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line)')}>
        <div style={css(row)}><span>Seen in</span><b>{plural(p.scenes.length, 'scene')}{p.seconds ? ` · ${length(p.seconds) || '<1m'}` : ''}</b></div>
        {p.named ? <div style={css(row)}><span>Only heard or named</span><b>{plural(p.named, 'scene')}</b></div> : null}
        {p.first ? <div style={css(row)}><span>First seen</span><button type="button" style={css(jump)} onClick={() => onSeek(p.first!.start)}>Scene {p.first.n} · {hms(p.first.start)}</button></div> : null}
        {p.last && p.last.n !== p.first?.n ? <div style={css(row)}><span>Last seen</span><button type="button" style={css(jump)} onClick={() => onSeek(p.last!.start)}>Scene {p.last.n} · {hms(p.last.start)}</button></div> : null}
        {p.gap ? (
          <div style={css('display: flex; flex-direction: column; gap: 4px; font-size: 13px')}>
            <div style={css(row)}><span>Longest absence</span><b>{length(p.gap.seconds) || '<1m'}</b></div>
            <div style={css('display: flex; justify-content: space-between; gap: 8px')}>
              <button type="button" style={css(jump)} onClick={() => onSeek(Math.max(0, p.gap!.start - 5))}>Leaves after scene {p.gap.from}</button>
              <button type="button" style={css(jump)} onClick={() => onSeek(p.gap!.end)}>Back in scene {p.gap.to}</button>
            </div>
          </div>
        ) : null}
      </div>
      {p.partners.length ? (
        <div style={css('display: flex; flex-direction: column; gap: 6px')}>
          <div style={css('font-size: 12px; font-weight: 700; color: var(--dim)')}>Seen most with</div>
          {p.partners.map((x) => {
            const q = byId.get(x.id);
            const n = q ? readable(q) : x.id;
            return (
              <button key={x.id} type="button" className="btn ghost" style={css('justify-content: flex-start; height: 34px; gap: 8px')} onClick={() => onPair(x.id)}>
                <Avatar name={n} photo={q?.photo} size={22} /><span style={{ flex: 1, textAlign: 'left' }}>{n}</span><span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{plural(x.scenes, 'scene')}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </>
  );
}

function PairPanel({ e, byId, scenes, video, onSeek, onPerson }: { e: GraphPair; byId: Map<string, GraphPerson>; scenes: Scene[]; video: string; onSeek: (t: number) => void; onPerson: (id: string) => void }) {
  const a = byId.get(e.a), b = byId.get(e.b);
  const byN = new Map(scenes.map((s) => [s.n, s]));
  return (
    <>
      <div style={css('display: flex; align-items: center; gap: 8px; flex-wrap: wrap')}>
        {[a, b].map((p, i) => p ? (
          <button key={p.id} type="button" className="linkish" style={css('display: inline-flex; align-items: center; gap: 6px; font-size: 15px; font-weight: 700; color: var(--text)')} onClick={() => onPerson(p.id)}>
            {i ? <span style={{ fontWeight: 400, color: 'var(--dim)' }}>and</span> : null}<Avatar name={readable(p)} photo={p.photo} size={26} />{readable(p)}
          </button>
        ) : null)}
      </div>
      <div style={css('font-size: 13px; color: var(--dim)')}>Together in {plural(e.scenes.length, 'scene')}, {length(e.seconds) || 'under a minute'}.</div>
      <div style={css('display: flex; flex-direction: column')}>
        {e.scenes.map((n) => {
          const s = byN.get(n);
          return (
            <div key={n} style={css('display: flex; align-items: baseline; gap: 10px; padding: 8px 0; border-top: 1px solid var(--line)')}>
              <button type="button" style={css(jump)} onClick={() => s && onSeek(s.start)}>Scene {n}{s ? ` · ${hms(s.start)}` : ''}</button>
              <span className="clamp" style={css('flex: 1; min-width: 0; font-size: 13px')}>{s?.spoiler ? 'Hidden as a spoiler' : s?.summary || ''}</span>
              <Link to={`/videos/${video}/scenes/${n}`} style={{ fontSize: 12.5 }}>Open</Link>
            </div>
          );
        })}
      </div>
    </>
  );
}
