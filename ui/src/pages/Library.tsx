// Library: every movie and show, as posters or as a list with the seven steps.
// Design: docs/design/library.
import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { api } from '../api/client';
import { STEPS, type TitleSummary } from '../api/types';
import { css, ErrorBox, Loading, Pills, Seg, StepCell } from '../components/kit';
import { length, plural } from '../lib/format';
import { useApi } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { DOT_BG, posterColour, titleHref } from './title/common';
import './library.css';

type View = 'grid' | 'list';
const FILTERS: [string, string][] = [
  ['all', 'All'], ['movies', 'Movies'], ['shows', 'Shows'], ['analysed', 'Analysed'], ['review', 'Waiting for review'], ['failed', 'Failed'],
];
const PAGE = 120;

const dot = (t: TitleSummary) => 'flex:none;width:8px;height:8px;border-radius:50%;box-sizing:border-box;' + DOT_BG[t.state.kind];

function meta(t: TitleSummary): string {
  if (t.type === 'show' && t.episodes) return `${t.year ?? ''}${t.year ? ' · ' : ''}${plural(t.episodes.seasons, 'season')} · ${plural(t.episodes.total, 'episode')}`;
  return [t.year, length(t.duration)].filter(Boolean).join(' · ');
}

function posterStyle(t: TitleSummary): string {
  // The fade is for the name drawn on a poster-less tile; real posters carry their own title.
  return (t.poster ? `background:url("${t.poster}") center/cover` : 'background:linear-gradient(180deg,rgba(0,0,0,0) 45%,rgba(0,0,0,.88))')
    + `,color-mix(in srgb,${posterColour(t.id)} 55%,#171b20)`
    + (t.state.kind === 'notrun' ? ';filter:saturate(.6)' : '');
}

export default function Library() {
  const [params, setParams] = useSearchParams();
  const filter = params.get('f') || 'all';
  const [view, setViewState] = useState<View>(() => (localStorage.getItem('marcarr.libraryView') as View) || 'grid');
  const setView = (v: View) => { localStorage.setItem('marcarr.libraryView', v); setViewState(v); };
  const [typed, setTyped] = useState(() => params.get('q') || '');
  const [q, setQ] = useState(() => params.get('q') || '');
  const [pages, setPages] = useState(1);
  const [running, setRunning] = useState(false);
  const toast = useToast();
  const navigate = useNavigate();

  useEffect(() => {
    const id = setTimeout(() => { setQ(typed.trim()); setPages(1); }, 250);
    return () => clearTimeout(id);
  }, [typed]);

  const res = useApi(() => api.titles({ filter, q, per_page: PAGE * pages }), [filter, q, pages], running ? 10000 : undefined);
  const items = res.data?.items || [];
  // Poll only while something is being analysed.
  useEffect(() => {
    setRunning(items.some((t) => t.state.kind === 'run' || t.state.kind === 'queued'));
  }, [res.data]);

  const pick = (f: string) => { setParams(f === 'all' ? {} : { f }, { replace: true }); setPages(1); };

  const analyseLeft = async () => {
    try {
      const r = await api.analyseLeft();
      toast(r.queued ? `${plural(r.queued, 'video')} added to the queue` : 'Nothing left to analyse');
      navigate('/activity');
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), true);
    }
  };

  const counts = res.data?.counts || {};
  const emptyText = filter === 'shows'
    ? 'No shows in the libraries Marcarr looks at. Add a library in Settings.'
    : !q && filter === 'all' ? 'Nothing in the library yet. Connect Plex in Settings and Marcarr will list your movies and shows.'
    : 'Nothing matches.';

  return (
    <div className="pg-library" style={{ display: 'contents' }}>
      <header style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 10px 14px')}>
        <h1 className="h1" style={{ flex: '1 1 160px' }}>Library</h1>
        <label style={{ flex: '1 1 220px', maxWidth: 320 }}>
          <span style={{ position: 'absolute', left: -9999 }}>Search by name</span>
          <input type="search" className="inp" placeholder="Search by name" value={typed} onChange={(e) => setTyped(e.target.value)} />
        </label>
        <Seg<View> label="View" value={view} options={[['grid', 'Posters'], ['list', 'List']]} onChange={setView} />
        <button type="button" className="btn pri" onClick={analyseLeft}>Analyse what is left</button>
      </header>
      <Pills value={filter} onChange={pick} options={FILTERS.map(([key, name]) => ({ key, name, n: counts[key] ?? (key === 'all' ? res.data?.total : undefined) }))} />

      {res.error && !res.data ? <ErrorBox error={res.error} retry={res.reload} /> : null}
      {res.loading && !res.data ? <Loading /> : null}

      {res.data && items.length > 0 && view === 'grid' ? (
        <div className="grid">
          {items.map((t) => (
            <Link key={t.id} to={titleHref(t.id)} className="pc">
              <span className="po" style={css(posterStyle(t))}>
                {t.to_review > 0 ? <span className="flag" aria-label={`${t.to_review} tags to review`}>{t.to_review}</span> : null}
                {t.poster ? null : <span className="hd" style={css('position: absolute; left: 12px; right: 12px; bottom: 12px; font-size: 17px; font-weight: 700; line-height: 1.15; color: #ffffff; text-wrap: balance')}>{t.name}</span>}
                {t.state.kind === 'run' ? (
                  <span style={css('position: absolute; left: 0; right: 0; bottom: 0; height: 4px; background: rgba(255,255,255,.25)')}>
                    <span style={css(`display:block;height:100%;width:${Math.round((t.state.progress ?? 0) * 100)}%;background:#f5d547`)} />
                  </span>
                ) : null}
              </span>
              <span style={css('display: flex; align-items: center; gap: 7px; margin-top: 9px; font-size: 12.5px; font-weight: 600')}><span style={css(dot(t))} />{t.state.text}</span>
              <span className="mono" style={css('display: block; margin-top: 2px; font-size: 11px; color: var(--faint)')}>{meta(t)}</span>
            </Link>
          ))}
        </div>
      ) : null}

      {res.data && items.length > 0 && view === 'list' ? (
        <div className="box" style={css('padding: 16px 16px 6px; overflow-x: auto')}>
          <div role="table" aria-label="Titles" style={{ minWidth: 900 }}>
            <div role="row" className="lr" style={{ paddingBottom: 8 }}>
              <span role="columnheader" className="lab">Title</span>
              {STEPS.map((s) => <span key={s} role="columnheader" className="th">{s}</span>)}
              <span role="columnheader" className="lab" style={{ textAlign: 'right' }}>To review</span>
              <span role="columnheader" className="lab">State</span>
            </div>
            {items.map((t) => (
              <div key={t.id} role="row" className="lr td">
                <span role="cell" style={{ minWidth: 0 }}>
                  <Link to={titleHref(t.id)} style={css('display: block; font-size: 14px; font-weight: 600; color: var(--text); text-decoration: none')}>{t.name}</Link>
                  <span className="mono" style={css('font-size: 11px; color: var(--faint)')}>{meta(t)}</span>
                </span>
                {STEPS.map((s) => (
                  <span key={s} role="cell" style={{ textAlign: 'center' }}>
                    {t.steps ? <StepCell step={s} state={t.steps[s]} /> : null}
                  </span>
                ))}
                <span role="cell" className="mono" style={css('text-align: right; font-size: 13px')}>{t.to_review || ''}</span>
                <span role="cell" style={css('display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px; font-weight: 600')}><span style={css(dot(t))} />{t.state.text}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {res.data && items.length < res.data.total ? (
        <div><button type="button" className="btn" onClick={() => setPages((p) => p + 1)}>Show more ({(res.data.total - items.length).toLocaleString()} left)</button></div>
      ) : null}

      {res.data && items.length === 0 ? (
        <div style={css('padding: 28px 20px; border: 1px dashed var(--border); border-radius: 12px; font-size: 14px; color: var(--dim)')}>{emptyText}</div>
      ) : null}
    </div>
  );
}
