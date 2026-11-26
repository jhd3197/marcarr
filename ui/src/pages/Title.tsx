// Title page: one movie or episode with its timeline and scenes. Shows share the
// route and are drawn by Show.tsx. Design: docs/design/title.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router';
import { api, urls } from '../api/client';
import { STEPS, type Person, type Scene, type Title, type Video } from '../api/types';
import { Avatar, Chips, css, DOT, ErrorBox, Loading, Pills } from '../components/kit';
import { hms, length, money, plural, took } from '../lib/format';
import { useApi } from '../lib/hooks';
import { useToast } from '../lib/toast';
import Show from './Show';
import { CrumbLinks, personName, placeHref, posterColour, shortName, titleHref } from './title/common';
import { Timeline } from './title/Timeline';
import './title.css';

const LIST_MAX = 8;
const EMPTY_BOX = 'padding: 28px 20px; border: 1px dashed var(--border); border-radius: 12px; font-size: 14px; color: var(--dim)';
const busy = (k: string | undefined) => k === 'run' || k === 'queued';

export default function TitlePage() {
  const { id = '' } = useParams();
  const [poll, setPoll] = useState(false);
  const res = useApi(() => api.title(id), [id], poll ? 10000 : undefined);
  useEffect(() => {
    const t = res.data;
    setPoll(!!t && (busy(t.state.kind) || busy(t.video?.state.kind)));
  }, [res.data]);

  if (res.error && !res.data) return <ErrorBox error={res.error} retry={res.reload} />;
  // Keep the previous title off screen while the next one loads.
  if (!res.data || (res.loading && res.data.id !== id)) return <Loading />;
  if (res.data.type === 'show') return <Show title={res.data} />;
  return <Film key={res.data.id} title={res.data} reload={res.reload} />;
}

/** "Analysed, 7 of 7 steps" or what is missing, with the dot colour. */
function statusOf(v: Video): { text: string; dot: string } {
  const st = v.steps;
  const done = STEPS.filter((s) => st[s] === 'done').length;
  if (busy(v.state.kind) || v.state.kind === 'failed') return { text: v.state.text, dot: DOT[v.state.kind] };
  if (done === STEPS.length) return { text: `Analysed, ${done} of ${STEPS.length} steps`, dot: 'var(--ok)' };
  const settled = STEPS.every((s) => st[s] === 'done' || st[s] === 'none' || st[s] === 'off');
  if (!settled) return { text: v.state.text, dot: DOT[v.state.kind] };
  const why = st.tags === 'off' ? 'Tags need AI'
    : st.subtitles === 'none' ? 'This file has no subtitles'
    : st.faces === 'none' || st.faces === 'off' ? 'Faces are not available'
    : STEPS.filter((s) => st[s] !== 'done').join(', ') + ' not available';
  return { text: `${done} of ${STEPS.length} steps. ${why}`, dot: 'var(--warn)' };
}

function Poster({ title }: { title: Title }) {
  if (title.poster) {
    return <span role="img" aria-label="Poster" style={css(`flex: none; width: 112px; aspect-ratio: 2/3; border-radius: 10px; background: url("${title.poster}") center/cover #000`)} />;
  }
  return (
    <span role="img" aria-label="Poster" className="hd" style={css(`flex: none; width: 112px; aspect-ratio: 2/3; border-radius: 10px; background: color-mix(in srgb, ${posterColour(title.id)} 55%, #171b20); display: flex; align-items: flex-end; padding: 12px; box-sizing: border-box; font-size: 20px; font-weight: 700; color: #ffffff; overflow: hidden`)}>
      {title.name}
    </span>
  );
}

function Film({ title, reload }: { title: Title; reload: () => void }) {
  const video = title.video;
  const toast = useToast();
  const [params] = useSearchParams();
  const stepsKey = video ? STEPS.map((s) => video.steps[s]).join(',') : '';
  // Reload scenes and signals whenever a step changes state (e.g. finishes while we watch).
  const scenesRes = useApi(() => (video ? api.scenes(video.id) : Promise.resolve(null)), [video?.id, stepsKey]);
  const signalsRes = useApi(() => (video ? api.signals(video.id).catch(() => null) : Promise.resolve(null)), [video?.id, stepsKey]);
  const scenes = useMemo<Scene[]>(() => [...(scenesRes.data?.items || [])].sort((a, b) => a.start - b.start), [scenesRes.data]);
  const signals = signalsRes.data?.items || [];
  const cast = useMemo(() => new Map<string, Person>(title.cast.map((p) => [p.id, p])), [title.cast]);

  const [selN, setSelN] = useState<number | null>(null);
  const [at, setAt] = useState(0);
  const [lf, setLf] = useState<'all' | 'review'>('all');
  const [showAll, setShowAll] = useState(false);
  const [revealed, setRevealed] = useState<Set<number>>(() => new Set());
  const [allCast, setAllCast] = useState(false);
  const playhead = useRef<HTMLElement>(null);

  const sceneAt = (t: number) => scenes.find((s) => t >= s.start && t < s.end) || [...scenes].reverse().find((s) => s.start <= t) || scenes[0];
  const seek = (t: number) => {
    setAt(t);
    const s = sceneAt(t);
    if (s) setSelN(s.n);
  };

  // First selection: ?t= from a copied link, else the first scene waiting for review, else one with tags.
  useEffect(() => {
    if (selN !== null || !scenes.length) return;
    const t = Number(params.get('t'));
    if (params.get('t') && Number.isFinite(t)) { seek(t); return; }
    const s = scenes.find((x) => x.to_review > 0) || scenes.find((x) => x.tags.length > 0) || scenes[0];
    setSelN(s.n);
    setAt(s.start);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenes]);

  const run = async () => {
    try {
      if (video) await api.runVideo(video.id); else await api.runTitle(title.id);
      toast('Added to the queue');
      reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), true);
    }
  };

  const copyLink = async () => {
    const url = `${location.origin}${titleHref(title.id)}?t=${Math.floor(at)}`;
    try {
      await navigator.clipboard.writeText(url);
      toast('Link copied');
    } catch {
      toast(url);
    }
  };

  const tagsOn = !video || video.steps.tags !== 'off' || scenes.some((s) => s.tags.length > 0);
  const facesOn = !!video && ((video.steps.faces !== 'none' && video.steps.faces !== 'off') || scenes.some((s) => s.people.length > 0));
  const toReview = video ? video.to_review : title.to_review;
  const anyDone = !!video && STEPS.some((s) => video.steps[s] === 'done');
  const status = video ? statusOf(video) : { text: title.state.text, dot: DOT[title.state.kind] };
  const sel = scenes.find((s) => s.n === selN) || null;
  const hidden = (s: Scene) => s.spoiler && !revealed.has(s.n);
  const reveal = (n: number) => setRevealed((r) => new Set(r).add(n));

  const meta = [
    title.type === 'episode' && title.season != null && title.episode != null ? `S${String(title.season).padStart(2, '0')}E${String(title.episode).padStart(2, '0')}` : '',
    title.year ? String(title.year) : '',
    length(video?.duration ?? title.duration),
    video?.edition || '',
    video && video.scenes ? plural(video.scenes, 'scene') : '',
  ].filter(Boolean).join(' · ');

  const castShown = allCast ? title.cast : title.cast.slice(0, 8);

  // Scene list: scenes with tags (all scenes when there are none yet, or tags are off).
  const withTags = tagsOn ? scenes.filter((s) => s.tags.length > 0) : [];
  const base = withTags.length ? withTags : scenes;
  const review = scenes.filter((s) => s.to_review > 0);
  const pool = lf === 'review' ? review : base;
  const listed = showAll ? pool : pool.slice(0, LIST_MAX);

  const duration = video?.duration || (scenes.length ? scenes[scenes.length - 1].end : 0);

  return (
    <div className="pg-title" style={{ display: 'contents' }}>
      <header style={css('display: flex; flex-wrap: wrap; gap: 16px 22px')}>
        <Poster title={title} />
        <div style={css('flex: 1 1 420px; min-width: 0; display: flex; flex-direction: column; gap: 10px')}>
          <CrumbLinks items={[{ name: 'Library', to: '/' }, ...(title.parent ? [{ name: title.parent.name, to: titleHref(title.parent.id) }] : []), { name: title.name }]} />
          <h1 className="h1">{title.name}</h1>
          <div className="mono" style={css('font-size: 12px; color: var(--dim)')}>{meta}</div>
          <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; font-size: 13px')}>
            <span style={css('display: inline-flex; align-items: center; gap: 7px; font-weight: 600')}><span style={css('width:8px;height:8px;border-radius:50%;background:' + status.dot)} />{status.text}</span>
            {video && video.seconds_spent > 0 ? <Link to="/activity" className="mono" style={{ fontSize: 12 }}>took {took(video.seconds_spent)} · AI cost {money(video.ai_cost)}</Link> : null}
          </div>
          {title.cast.length ? (
            <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 6px 14px')}>
              {castShown.map((p) => (
                <Link key={p.id} to={`/people/${encodeURIComponent(p.id)}`} title={p.actor} style={css('display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; color: var(--text); text-decoration: none')}>
                  <Avatar name={p.character || p.actor} photo={p.photo} size={24} />{p.character || p.actor}
                </Link>
              ))}
              {title.cast.length > 8 ? <button type="button" className="linkish" onClick={() => setAllCast(!allCast)}>{allCast ? 'Less' : 'All cast'}</button> : null}
            </div>
          ) : null}
        </div>
        <div style={css('display: flex; gap: 8px; align-items: flex-start')}>
          {!tagsOn ? <Link to="/settings" className="btn pri">Turn on AI</Link>
            : toReview > 0 ? <Link to={`/review?title=${encodeURIComponent(title.id)}`} className="btn pri">Review {plural(toReview, 'tag')}</Link> : null}
          {anyDone ? <button type="button" className="btn" disabled={video ? busy(video.state.kind) : false} onClick={run}>Analyse again</button> : null}
        </div>
      </header>

      {video && video.steps.subtitles === 'none' ? (
        <div role="status" style={css('padding: 12px 16px; border-radius: 10px; border: 1px solid var(--warn); font-size: 14px')}>No subtitles in this file, so the tags come from the picture only.</div>
      ) : null}

      {!video ? (
        <div style={css(EMPTY_BOX)}>No video file for this title yet. Marcarr picks files up from Plex on the next library scan.</div>
      ) : scenesRes.error && !scenesRes.data ? (
        <ErrorBox error={scenesRes.error} retry={scenesRes.reload} />
      ) : !scenesRes.data ? (
        <Loading />
      ) : scenes.length === 0 ? (
        <NotYet video={video} onRun={run} />
      ) : (
        <>
          {sel ? (
            <section ref={playhead} aria-label="At the playhead" style={css('display: flex; flex-wrap: wrap; gap: 16px 22px; scroll-margin-top: 16px')}>
              <div style={css('flex: 3 1 420px; min-width: 0; position: relative; aspect-ratio: 2.4/1; border-radius: 10px; overflow: hidden; background: #000')}>
                <span role="img" aria-label="Picture at the playhead" style={css(`display:block;width:100%;height:100%;background:url("${urls.frame(video.id, at, 480)}") center/cover,url("${sel.still || urls.still(video.id, sel.n)}") center/cover` + (hidden(sel) ? ';filter:blur(9px);transform:scale(1.25)' : ''))} />
                <span className="mono" style={css('position: absolute; left: 12px; top: 12px; padding: 3px 8px; border-radius: 6px; background: rgba(16,19,23,.8); color: #f7f6ef; font-size: 13px')}>{hms(at)}</span>
                <div style={css('position: absolute; left: 12px; bottom: 12px; display: flex; flex-wrap: wrap; gap: 6px')}>
                  {(facesOn ? sel.people : []).map((pid) => {
                    const p = cast.get(pid);
                    const name = shortName(personName(pid, cast));
                    return (
                      <span key={pid} style={css('display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px 3px 3px; border-radius: 14px; background: rgba(16,19,23,.8); color: #f7f6ef; font-size: 12.5px; font-weight: 600')}>
                        <Avatar name={name} photo={p?.photo} size={22} />{name}
                      </span>
                    );
                  })}
                </div>
              </div>
              <div style={css('flex: 2 1 300px; min-width: 0; display: flex; flex-direction: column; gap: 10px')}>
                <div className="mono" style={css('font-size: 12px; color: var(--dim)')}>Scene {sel.n} · {hms(sel.start)} to {hms(sel.end)}</div>
                <div className="hd" style={css('font-size: 20px; font-weight: 600; line-height: 1.25')}>
                  {hidden(sel) ? <button type="button" className="linkish" style={{ fontSize: 20 }} onClick={() => reveal(sel.n)}>Hidden as a spoiler. Show it</button> : sel.summary || 'No summary for this scene yet.'}
                </div>
                {tagsOn && sel.place && sel.place_name && !hidden(sel) ? <Link to={placeHref(sel.place)} style={{ fontSize: 13 }}>{sel.place_name}</Link> : null}
                {tagsOn && !hidden(sel) ? <Chips tags={sel.tags} /> : null}
                <div style={css('margin-top: auto; display: flex; flex-wrap: wrap; gap: 8px')}>
                  <Link to={`/videos/${video.id}/scenes/${sel.n}`} className={sel.to_review > 0 && tagsOn ? 'btn pri' : 'btn'}>{sel.to_review > 0 && tagsOn ? 'Review this scene' : 'Open scene'}</Link>
                  <button type="button" className="btn ghost" onClick={copyLink}>Copy time link</button>
                </div>
              </div>
            </section>
          ) : null}

          {duration > 0 ? (
            <Timeline duration={duration} scenes={scenes} signals={signals} cast={cast} tagsStep={video.steps.tags} facesStep={video.steps.faces}
              selected={selN} at={at} episode={title.type === 'episode'} onSeek={seek} />
          ) : null}

          <section aria-label="Scenes">
            <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; padding-bottom: 12px')}>
              <h2 className="h2" style={{ flex: '1 1 160px' }}>Scenes</h2>
              <Pills value={lf} onChange={(v) => { setLf(v); setShowAll(false); }}
                options={[{ key: 'all', name: withTags.length ? 'With tags' : 'All scenes', n: base.length }, { key: 'review', name: 'To review', n: review.length }]} />
            </div>
            {listed.map((s) => {
              const h = hidden(s);
              return (
                <div key={s.n} className="srow">
                  <button type="button" className="sb" aria-label={h ? 'Show the spoiler' : 'Still from the scene'}
                    onClick={() => {
                      if (h) { reveal(s.n); return; }
                      seek(s.start);
                      playhead.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }}>
                    <span style={css(`background:url("${s.still || urls.still(video.id, s.n)}") center/cover` + (h ? ';filter:blur(9px);transform:scale(1.25)' : ''))} />
                    {h ? <span className="sp">Spoiler</span> : null}
                  </button>
                  <Link to={`/videos/${video.id}/scenes/${s.n}`} style={css('flex: 1 1 320px; min-width: 0; color: var(--text); text-decoration: none')}>
                    <span className="mono" style={css('display: block; font-size: 12px; color: var(--dim)')}>Scene {s.n} · {hms(s.start)} to {hms(s.end)}</span>
                    <span className="clamp" style={css('margin-top: 2px; font-size: 14px; font-weight: 600')}>{h ? 'Hidden as a spoiler' : s.summary || 'No summary yet.'}</span>
                    {!h && tagsOn && s.tags.length ? <span style={css('margin-top: 6px; display: flex; flex-wrap: wrap; gap: 5px')}><Chips tags={s.tags} /></span> : null}
                  </Link>
                </div>
              );
            })}
            {pool.length === 0 ? <div style={css('padding: 12px 0; border-top: 1px solid var(--line); font-size: 14px; color: var(--dim)')}>{lf === 'review' ? 'Nothing waiting for review here.' : 'No scenes yet.'}</div> : null}
            {!showAll && pool.length > LIST_MAX ? (
              <div style={css('padding-top: 12px; border-top: 1px solid var(--line)')}><button type="button" className="btn" onClick={() => setShowAll(true)}>Show all {pool.length}</button></div>
            ) : null}
          </section>
        </>
      )}
    </div>
  );
}

/** A video with no scenes yet: waiting, running, failed or never analysed. */
function NotYet({ video, onRun }: { video: Video; onRun: () => void }) {
  const k = video.state.kind;
  if (busy(k)) {
    return (
      <div style={css(EMPTY_BOX)}>
        {video.state.text}{video.state.progress != null ? ` (${Math.round(video.state.progress * 100)}%)` : ''}. The timeline fills in once the scenes are found.{' '}
        <Link to="/activity">See Activity</Link>
      </div>
    );
  }
  if (video.steps.scenes === 'done') return <div style={css(EMPTY_BOX)}>No scenes were found in this file.</div>;
  return (
    <div style={css(EMPTY_BOX + '; display: flex; align-items: center; flex-wrap: wrap; gap: 12px 16px')}>
      <span style={{ flex: '1 1 300px' }}>
        {k === 'failed' ? `${video.state.text}.` : 'Not analysed yet.'} Analysing finds the shots, scenes and who is in them, then proposes tags for you to review.
      </span>
      <button type="button" className="btn pri" onClick={onRun}>{k === 'failed' ? 'Try again' : 'Analyse now'}</button>
    </div>
  );
}
