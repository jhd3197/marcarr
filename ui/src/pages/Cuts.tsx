// A film's versions and cuts: /titles/:id/cuts. Which file is which cut, and the
// footage one cut has that another lacks ("only in Extended"), marked by a person,
// measured by comparing two local versions, or looked up online.
import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import { api } from '../api/client';
import type { CutKind, CutRange, CutVersion, TitleCuts } from '../api/types';
import { Empty, ErrorBox, Loading, css } from '../components/kit';
import { clock, length, money, plural, when } from '../lib/format';
import { useApi } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { CrumbLinks, titleHref } from './title/common';

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
const KIND: Record<CutKind, string> = { added: 'Added scene', longer: 'Runs longer', removed: 'Removed' };
const SOURCE: Record<string, string> = { person: 'You', compare: 'Compared files', research: 'Found online' };

/** "1:02:10" or "62:10" or "3730" -> seconds; null when empty or unreadable. */
export function parseTime(s: string): number | null {
  const t = s.trim();
  if (!t) return null;
  if (/^\d+(\.\d+)?$/.test(t)) return Number(t);
  const parts = t.split(':').map(Number);
  if (parts.some((n) => !Number.isFinite(n)) || parts.length > 3) return null;
  return parts.reduce((acc, n) => acc * 60 + n, 0);
}

function span(r: CutRange): string {
  if (r.start == null) return 'Time not known';
  const a = clock(r.start);
  if (r.end == null) return `around ${a}`;
  return `${r.rough ? 'around ' : ''}${a} to ${clock(r.end)}`;
}

export default function CutsPage() {
  const { id = '' } = useParams();
  const res = useApi(() => api.cuts(id), [id]);
  if (res.error && !res.data) return <ErrorBox error={res.error} retry={res.reload} />;
  if (!res.data) return <Loading />;
  return <Cuts data={res.data} reload={res.reload} />;
}

function Cuts({ data, reload }: { data: TitleCuts; reload: () => void }) {
  const toast = useToast();
  const t = data.title;
  const present = data.versions.filter((v) => v.in_plex);
  const byId = new Map(data.versions.map((v) => [v.id, v]));
  const waiting = data.ranges.filter((r) => r.status === 'proposed');
  const shown = data.ranges.filter((r) => r.status !== 'rejected');
  const dropped = data.ranges.length - shown.length;
  const [showDropped, setShowDropped] = useState(false);

  const act = async (fn: () => Promise<unknown>, done: string) => {
    try {
      await fn();
      toast(done);
      reload();
    } catch (e) {
      toast(errText(e), true);
    }
  };

  const rows = showDropped ? data.ranges : shown;
  return (
    <div style={{ display: 'contents' }}>
      <header style={css('display: flex; flex-direction: column; gap: 10px')}>
        <CrumbLinks items={[{ name: 'Library', to: '/' }, { name: t.name, to: titleHref(t.id) }, { name: 'Versions and cuts' }]} />
        <h1 className="h1">Versions and cuts</h1>
        <p style={css('margin: 0; max-width: 680px; font-size: 14px; color: var(--dim)')}>
          What each file of {t.name} is, and the footage one cut has that another lacks. Tags and fan cuts made on one cut use this to find their way in another.
        </p>
      </header>

      <section aria-label="Versions" className="box" style={css('padding: 16px 18px')}>
        <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; padding-bottom: 10px')}>
          <h2 className="h2" style={{ flex: '1 1 200px' }}>{plural(present.length, 'version')} in Plex</h2>
          <button type="button" className="btn" disabled={!!data.can.compare} title={data.can.compare || undefined}
            onClick={() => act(() => api.compareVersions(t.id), 'Comparing the two versions. This finds the camera cuts of each first, so it takes a few minutes.')}>
            Compare versions
          </button>
          <button type="button" className="btn" disabled={!!data.can.research} title={data.can.research || undefined}
            onClick={() => act(() => api.researchCuts(t.id), 'Looking the cuts up online')}>
            Look it up online
          </button>
        </div>
        {data.versions.map((v) => <VersionRow key={v.id} v={v} />)}
        {data.can.research ? <p style={css('margin: 10px 0 0; font-size: 12.5px; color: var(--dim)')}>Looking it up online: {data.can.research}.</p> : null}
        {data.compare && !data.compare.same_film ? (
          <p role="status" style={css('margin: 10px 0 0; font-size: 13px; color: var(--warn)')}>
            The last comparison could not line these files up ({Math.round(data.compare.coverage * 100)}% of camera cuts matched). They may be different films.
          </p>
        ) : data.compare ? (
          <p style={css('margin: 10px 0 0; font-size: 12.5px; color: var(--dim)')}>
            Last compared: {Math.round(data.compare.coverage * 100)}% of camera cuts matched
            {Math.abs(data.compare.speed - 1) > 0.005 ? `, one plays at ${data.compare.speed.toFixed(3)}x (a PAL speed-up)` : ''}.
          </p>
        ) : null}
      </section>

      <section aria-label="Differences">
        <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; padding-bottom: 12px')}>
          <h2 className="h2" style={{ flex: '1 1 200px' }}>Differences between the cuts</h2>
          {waiting.length ? <button type="button" className="btn pri" onClick={() => act(() => api.keepCuts(t.id), `Kept ${plural(waiting.length, 'difference')}`)}>Keep all {waiting.length}</button> : null}
          {dropped ? <button type="button" className="linkish" onClick={() => setShowDropped(!showDropped)}>{showDropped ? 'Hide dropped' : `Show ${dropped} dropped`}</button> : null}
        </div>
        {rows.length === 0 ? (
          <Empty>
            {present.length >= 2 ? 'No differences marked yet. Compare the versions to measure them, or mark one below.'
              : 'No differences marked yet. With one version on disk, look the cuts up online or mark one below.'}
          </Empty>
        ) : rows.map((r) => <RangeRow key={r.id} r={r} video={r.video_id ? byId.get(r.video_id) : undefined} titleId={t.id} act={act} />)}
        <MarkForm data={data} onDone={reload} />
      </section>

      {data.research.length ? <ResearchBox run={data.research[0]} /> : null}
    </div>
  );
}

function VersionRow({ v }: { v: CutVersion }) {
  return (
    <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 6px 14px; padding: 10px 0; border-top: 1px solid var(--line); font-size: 14px' + (v.in_plex ? '' : '; opacity: .55'))}>
      <span style={css('flex: 0 0 180px; font-weight: 600')}>
        {v.edition || 'Unnamed'}{v.guessed ? <span style={css('font-weight: 400; color: var(--dim)')}> (guessed)</span> : null}
      </span>
      <span className="mono" style={css('flex: 0 0 72px; font-size: 12.5px')}>{length(v.duration)}</span>
      <span className="mono" title={v.file} style={css('flex: 1 1 240px; min-width: 0; font-size: 12px; color: var(--dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap')}>{v.file}</span>
      <span style={css('font-size: 12.5px; color: var(--dim)')}>
        {[v.audio.filter(Boolean).join(', ') && `audio ${v.audio.filter(Boolean).join(', ')}`,
          v.current ? 'analysed by the library' : v.steps_done ? `${v.steps_done} of 7 steps` : 'not analysed',
          v.in_plex ? '' : 'no longer in Plex'].filter(Boolean).join(' · ')}
      </span>
    </div>
  );
}

function RangeRow({ r, video, titleId, act }: { r: CutRange; video?: CutVersion; titleId: string; act: (fn: () => Promise<unknown>, done: string) => void }) {
  const src = SOURCE[r.source_kind] || r.source_kind;
  const proposed = r.status === 'proposed';
  return (
    <div style={css('display: flex; flex-wrap: wrap; gap: 8px 16px; padding: 12px 0; border-top: 1px solid var(--line)' + (r.status === 'rejected' ? '; opacity: .5' : ''))}>
      <div style={css('flex: 1 1 360px; min-width: 0; display: flex; flex-direction: column; gap: 4px')}>
        <span style={css('font-size: 14px; font-weight: 600')}>
          {KIND[r.kind]}{r.extra ? `, ${Math.round(Math.abs(r.extra))} s` : ''} · only in {r.edition}{r.base ? ` (not in ${r.base})` : ''}
        </span>
        <span className="mono" style={css('font-size: 12.5px; color: var(--dim)')}>
          {video && r.start != null ? <Link to={`${titleHref(titleId)}?t=${Math.floor(r.start)}`}>{span(r)}</Link> : span(r)}
          {video ? ` in ${video.edition || 'this version'}` : r.start != null ? ' in their copy' : ''}
          {r.rough ? ' · published time, check it' : ''}
        </span>
        {r.note ? <span style={css('font-size: 13.5px')}>{r.note}</span> : null}
        <span style={css('font-size: 12px; color: var(--dim)')}>
          {src}{proposed ? ', waiting for review' : r.status === 'rejected' ? ', dropped' : ''}
          {r.source_kind === 'research' && r.evidence.length ? <> · {r.evidence.map((u, i) => <a key={u} href={u} target="_blank" rel="noreferrer noopener" style={{ marginLeft: i ? 6 : 4 }}>source {i + 1}</a>)}</> : null}
        </span>
      </div>
      <div style={css('display: flex; align-items: flex-start; gap: 8px')}>
        {proposed ? <button type="button" className="btn pri sm" onClick={() => act(() => api.editCut(r.id, { status: 'accepted' }), 'Kept')}>Keep</button> : null}
        {r.status !== 'rejected' ? <button type="button" className="btn sm" onClick={() => act(() => api.editCut(r.id, { status: 'rejected' }), 'Dropped')}>Drop</button>
          : <button type="button" className="btn sm" onClick={() => act(() => api.editCut(r.id, { status: 'proposed' }), 'Back for review')}>Undo</button>}
        {r.source_kind === 'person' ? <button type="button" className="btn ghost sm" onClick={() => act(() => api.deleteCut(r.id), 'Deleted')}>Delete</button> : null}
      </div>
    </div>
  );
}

/** Mark a difference by hand: which cut has it, on which version, from when to when. */
function MarkForm({ data, onDone }: { data: TitleCuts; onDone: () => void }) {
  const toast = useToast();
  const present = data.versions.filter((v) => v.in_plex);
  const longest = [...present].sort((a, b) => (b.duration || 0) - (a.duration || 0))[0];
  const [open, setOpen] = useState(false);
  const [video, setVideo] = useState(longest?.id || '');
  const [edition, setEdition] = useState(longest?.edition || 'Extended');
  const [base, setBase] = useState('Theatrical');
  const [kind, setKind] = useState<CutKind>('added');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const a = parseTime(from);
    const b = parseTime(to);
    if (a == null || b == null || b <= a) {
      toast('Give a start and an end, like 1:02:10 and 1:03:15', true);
      return;
    }
    setBusy(true);
    try {
      await api.markCut(data.title.id, { edition: edition.trim(), base: base.trim(), kind, video: video || null, start: a, end: b, note: note.trim() });
      toast('Marked');
      setFrom(''); setTo(''); setNote('');
      setOpen(false);
      onDone();
    } catch (err) {
      toast(errText(err), true);
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return <div style={css('padding-top: 12px; border-top: 1px solid var(--line)')}><button type="button" className="btn" onClick={() => setOpen(true)}>Mark a difference</button></div>;
  }
  const field = 'display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--dim)';
  return (
    <form onSubmit={submit} className="box" style={css('margin-top: 12px; padding: 16px 18px; display: flex; flex-wrap: wrap; gap: 12px 16px; align-items: flex-end')}>
      <label style={css(field)}>On the version
        <select className="inp" value={video} onChange={(e) => { setVideo(e.target.value); const v = present.find((x) => x.id === e.target.value); if (v?.edition) setEdition(v.edition); }}>
          {present.map((v) => <option key={v.id} value={v.id}>{v.edition || 'Unnamed'} · {length(v.duration)}</option>)}
          <option value="">None on disk (times as published)</option>
        </select>
      </label>
      <label style={css(field)}>What
        <select className="inp" value={kind} onChange={(e) => setKind(e.target.value as CutKind)}>
          {(Object.keys(KIND) as CutKind[]).map((k) => <option key={k} value={k}>{KIND[k]}</option>)}
        </select>
      </label>
      <label style={css(field)}>Only in<input className="inp" value={edition} onChange={(e) => setEdition(e.target.value)} style={{ width: 150 }} /></label>
      <label style={css(field)}>Not in<input className="inp" value={base} onChange={(e) => setBase(e.target.value)} style={{ width: 130 }} /></label>
      <label style={css(field)}>From<input className="inp mono" placeholder="1:02:10" value={from} onChange={(e) => setFrom(e.target.value)} style={{ width: 100 }} /></label>
      <label style={css(field)}>To<input className="inp mono" placeholder="1:03:15" value={to} onChange={(e) => setTo(e.target.value)} style={{ width: 100 }} /></label>
      <label style={css(field + '; flex: 1 1 240px')}>What happens<input className="inp" placeholder="Dobby at the window runs longer" value={note} onChange={(e) => setNote(e.target.value)} /></label>
      <div style={css('display: flex; gap: 8px')}>
        <button type="submit" className="btn pri" disabled={busy}>Mark it</button>
        <button type="button" className="btn ghost" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}

function ResearchBox({ run }: { run: TitleCuts['research'][number] }) {
  const cited = run.sources.filter((s) => s.cited);
  return (
    <section aria-label="Looked up online" className="box" style={css('padding: 16px 18px; display: flex; flex-direction: column; gap: 8px')}>
      <h2 className="h2">Looked up online</h2>
      <span style={css('font-size: 12.5px; color: var(--dim)')}>{when(run.created_at)} · {run.model} · {money(run.cost)}</span>
      {run.editions.length ? (
        <span style={css('font-size: 14px')}>
          Published runtimes: {run.editions.map((e) => `${e.name}${e.runtime_minutes ? ` ${Math.round(e.runtime_minutes)} min` : ''}`).join(' · ')}
        </span>
      ) : null}
      <span style={css('font-size: 13px; color: var(--dim)')}>Asked: {run.question}</span>
      {cited.length ? (
        <ol style={css('margin: 0; padding-left: 20px; font-size: 13px')}>
          {cited.map((s) => <li key={s.url}><a href={s.url} target="_blank" rel="noreferrer noopener">{s.title || s.url}</a></li>)}
        </ol>
      ) : <span style={css('font-size: 13px')}>No page answered it.</span>}
    </section>
  );
}
