// Show page: seasons on the left, the chosen season's episodes on the right.
// Rendered by Title.tsx when the title is a show. Design: docs/design/show.
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { api } from '../api/client';
import type { StateLine, Title, TitleSummary } from '../api/types';
import { css, ErrorBox, Loading } from '../components/kit';
import { plural } from '../lib/format';
import { useApi } from '../lib/hooks';
import { CrumbLinks, DOT_BG, posterColour, titleHref } from './title/common';
import './show.css';

const cell = (kind: StateLine['kind']) => 'width:11px;height:11px;border-radius:3px;box-sizing:border-box;' + DOT_BG[kind];
const busy = (k: string) => k === 'run' || k === 'queued';

export default function Show({ title }: { title: Title }) {
  const seasons = title.seasons || [];
  const [params, setParams] = useSearchParams();
  const sn = Number(params.get('season')) || seasons[0]?.season || 1;
  const pick = (s: number) => setParams({ season: String(s) }, { replace: true });

  const [poll, setPoll] = useState(false);
  const eps = useApi(() => api.titles({ parent: title.id, season: sn, per_page: 500 }), [title.id, sn], poll ? 10000 : undefined);
  const episodes = [...(eps.data?.items || [])];
  useEffect(() => { setPoll((eps.data?.items || []).some((e) => busy(e.state.kind))); }, [eps.data]);

  const total = title.episodes?.total ?? seasons.reduce((n, s) => n + s.episodes, 0);
  const analysed = title.episodes?.analysed ?? seasons.reduce((n, s) => n + s.analysed, 0);
  const pct = total ? (analysed / total) * 100 : 0;
  const metaParts = [title.year ? String(title.year) : '', plural(seasons.length || title.episodes?.seasons || 0, 'season'), plural(total, 'episode')];
  const statusText = `${analysed} of ${total} episodes analysed`;
  const dotBg = busy(title.state.kind) ? 'var(--accent)' : analysed === total && total > 0 ? 'var(--ok)' : 'var(--faint)';

  return (
    <div className="pg-show" style={{ display: 'contents' }}>
      <header style={css('display: flex; flex-wrap: wrap; gap: 16px 22px')}>
        {title.poster ? (
          <span role="img" aria-label="Poster" style={css(`flex: none; width: 112px; aspect-ratio: 2/3; border-radius: 10px; background: url("${title.poster}") center/cover #000`)} />
        ) : (
          <span role="img" aria-label="Poster" className="hd" style={css(`flex: none; width: 112px; aspect-ratio: 2/3; border-radius: 10px; background: color-mix(in srgb, ${posterColour(title.id)} 55%, #171b20); display: flex; align-items: flex-end; padding: 12px; box-sizing: border-box; font-size: 20px; font-weight: 700; color: #ffffff; overflow: hidden`)}>{title.name}</span>
        )}
        <div style={css('flex: 1 1 420px; min-width: 0; display: flex; flex-direction: column; gap: 10px')}>
          <CrumbLinks items={[{ name: 'Library', to: '/' }, { name: title.name }]} />
          <h1 className="h1">{title.name}</h1>
          <div className="mono" style={css('font-size: 12px; color: var(--dim)')}>{metaParts.filter(Boolean).join(' · ')}</div>
          <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; font-size: 13px')}>
            <span style={css('display: inline-flex; align-items: center; gap: 7px; font-weight: 600')}><span style={css('width: 8px; height: 8px; border-radius: 50%; background: ' + dotBg)} />{statusText}</span>
            {title.state.text && title.state.text !== statusText ? <span style={{ color: 'var(--dim)' }}>{title.state.text}</span> : null}
          </div>
          <div role="progressbar" aria-label="Episodes analysed" aria-valuemin={0} aria-valuemax={total} aria-valuenow={analysed} style={css('max-width: 420px; height: 8px; border-radius: 4px; background: var(--raised); overflow: hidden')}>
            <div style={css(`height: 100%; width: ${pct.toFixed(3)}%; background: var(--accent)`)} />
          </div>
        </div>
        <div style={css('display: flex; gap: 8px; align-items: flex-start')}>
          {title.to_review > 0 ? <Link to={`/review?title=${encodeURIComponent(title.id)}`} className="btn pri">Review {plural(title.to_review, 'tag')}</Link> : null}
          <Link to="/activity" className="btn">Activity</Link>
        </div>
      </header>

      <div style={css('display: flex; flex-wrap: wrap; gap: 24px 32px; align-items: flex-start')}>
        <nav aria-label="Seasons" className="box" style={css('flex: 1 1 400px; max-width: 520px; min-width: 0; padding: 10px')}>
          {seasons.map((s) => {
            // The open season shows each episode's real state; the others only have counts.
            const cells: StateLine['kind'][] = s.season === sn && episodes.length
              ? episodes.map((e) => e.state.kind)
              : Array.from({ length: s.episodes }, (_x, i) => (i < s.analysed ? 'done' : 'notrun'));
            return (
              <button key={s.season} type="button" className="sn" aria-pressed={s.season === sn} onClick={() => pick(s.season)}>
                <span style={css('flex: 0 0 76px; font-weight: 600')}>{s.season === 0 ? 'Specials' : `Season ${s.season}`}</span>
                <span style={css('flex: 1; display: flex; flex-wrap: wrap; gap: 3px')}>{cells.map((k, i) => <span key={i} style={css(cell(k))} />)}</span>
                <span className="mono" style={css('flex: 0 0 62px; text-align: right; font-size: 12px; color: var(--dim)')}>{s.analysed} of {s.episodes}</span>
              </button>
            );
          })}
          {seasons.length === 0 ? <div style={{ padding: 8, color: 'var(--dim)' }}>No seasons found yet.</div> : null}
        </nav>

        <section aria-label="Episodes" style={css('flex: 3 1 560px; min-width: 0; overflow-x: auto')}>
          <div style={{ minWidth: 760 }}>
            <h2 className="h2" style={css('padding: 0 8px 10px')}>{sn === 0 ? 'Specials' : `Season ${sn}`}</h2>
            {eps.error && !eps.data ? <ErrorBox error={eps.error} retry={eps.reload} /> : null}
            {!eps.data && !eps.error ? <Loading /> : null}
            {episodes.map((e) => <EpisodeRow key={e.id} e={e} />)}
            {eps.data && episodes.length === 0 ? <div style={css('padding: 8px; border-top: 1px solid var(--line); color: var(--dim)')}>No episodes in this season.</div> : null}
          </div>
        </section>
      </div>
    </div>
  );
}

function EpisodeRow({ e }: { e: TitleSummary }) {
  // Episode numbers live on Title, not TitleSummary; the id ends in sNNeNN for TVDB episodes.
  const m = /e(\d+)$/i.exec(e.id);
  const n = m ? 'E' + Number(m[1]) : '';
  return (
    <div className="er">
      <span className="mono" style={{ color: 'var(--dim)' }}>{n}</span>
      <Link to={titleHref(e.id)} className="et">{e.name}</Link>
      <span className="mono" style={css('font-size: 12px; color: var(--dim)')}>{e.duration ? `${Math.round(e.duration / 60)} min` : ''}</span>
      <span style={css('display: flex; flex-wrap: wrap; gap: 5px')} />
      <span className="mono" style={css('font-size: 12px; color: var(--mark)')}>{e.to_review ? `${e.to_review} to review` : ''}</span>
      <span style={css('display: inline-flex; align-items: center; gap: 7px; font-size: 12.5px')}>
        <span style={css('flex:none;width:8px;height:8px;border-radius:50%;box-sizing:border-box;' + DOT_BG[e.state.kind])} />{e.state.text}
      </span>
    </div>
  );
}
