// The review queue: every proposed tag, as a list grouped by title or one big card.
// Built from docs/design/review. K keep, D drop, arrows move.
import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { api } from '../api/client';
import type { ReviewItem, TagStatus } from '../api/types';
import { css, ErrorBox, Loading, Seg } from '../components/kit';
import { useApp } from '../components/Shell';
import { evText, hms } from '../lib/format';
import { useApi, useKeys } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { bgUrl, chipCss, errText, FAMILIES, familyName, sourceName } from './review/labels';
import './review.css';

type View = 'list' | 'cards';
const CAP = 16;

export default function Review() {
  const [params, setParams] = useSearchParams();
  const family = params.get('family') || '';
  const source = params.get('source') || '';
  const title = params.get('title') || '';
  const toast = useToast();
  const { refreshStatus } = useApp();
  const q = useApi(() => api.review({ family, source, title, per_page: 500 }), [family, source, title]);

  const [view, setViewState] = useState<View>(() => (localStorage.getItem('marcarr.review.view') as View) || 'list');
  const setView = (v: View) => { localStorage.setItem('marcarr.review.view', v); setViewState(v); };
  const [dec, setDec] = useState<Record<string, TagStatus>>({});
  const [curId, setCurId] = useState<string | null>(null);
  const [all, setAll] = useState(false);
  useEffect(() => { setCurId(null); setAll(false); }, [family, source, title]);

  const setFilter = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    if (v) p.set(k, v); else p.delete(k);
    setParams(p, { replace: true });
  };

  const pool: ReviewItem[] = useMemo(() => (q.data ? q.data.groups.flatMap((g) => g.items) : []), [q.data]);
  const stateOf = (it: ReviewItem): TagStatus => dec[it.id] || it.status;
  const decidedHere = pool.filter((it) => it.status === 'proposed' && stateOf(it) !== 'proposed').length;
  const waiting = Math.max(0, (q.data?.total ?? 0) - decidedHere);

  let ci = pool.findIndex((it) => it.id === curId);
  if (ci < 0) ci = Math.max(0, pool.findIndex((it) => stateOf(it) === 'proposed'));
  const cur = pool[ci] as ReviewItem | undefined;

  const step = (d: number) => { if (pool.length) setCurId(pool[(ci + d + pool.length) % pool.length].id); };
  const decide = (v: 'keep' | 'drop') => {
    if (!cur) return;
    const it = cur;
    const was = dec[it.id];
    const st: TagStatus = v === 'keep' ? 'accepted' : 'rejected';
    const nd = { ...dec, [it.id]: st };
    let nx = it.id;
    for (let i = 1; i <= pool.length; i++) {
      const c = pool[(ci + i) % pool.length];
      if ((nd[c.id] || c.status) === 'proposed') { nx = c.id; break; }
    }
    setDec(nd);
    setCurId(nx);
    (v === 'keep' ? api.keep(it.id) : api.drop(it.id)).then(
      () => refreshStatus(),
      (e) => {
        setDec((x) => { const y = { ...x }; if (was) y[it.id] = was; else delete y[it.id]; return y; });
        toast(`Could not ${v} ${it.name}: ${errText(e)}`, true);
      },
    );
  };
  const undo = (it: ReviewItem) => {
    const was = dec[it.id];
    setDec((x) => ({ ...x, [it.id]: 'proposed' }));
    api.undo(it.id).then(
      () => refreshStatus(),
      (e) => {
        setDec((x) => { const y = { ...x }; if (was) y[it.id] = was; else delete y[it.id]; return y; });
        toast(`Could not undo: ${errText(e)}`, true);
      },
    );
  };
  useKeys({
    k: () => decide('keep'), d: () => decide('drop'),
    ArrowDown: () => step(1), ArrowRight: () => step(1), ArrowUp: () => step(-1), ArrowLeft: () => step(-1),
  }, [pool, ci, dec]);

  const facets = q.data?.facets;
  const filtered = !!(family || source || title);

  const head = (
    <>
      <header style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 10px 16px')}>
        <h1 className="h1">Review</h1>
        <span className="mono" style={css('flex: 1 1 200px; font-size: 12px; color: var(--dim)')}>{q.data ? `${waiting} waiting` : ''}</span>
        <Seg<View> label="View" value={view} options={[['list', 'List'], ['cards', 'One card']]} onChange={setView} />
      </header>
      <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px')}>
        <select className="sel" aria-label="Family" value={family} onChange={(e) => setFilter('family', e.target.value)}>
          <option value="">All families</option>
          {FAMILIES.map(([k, name]) => <option key={k} value={k}>{name}</option>)}
        </select>
        <select className="sel" aria-label="Source" value={source} onChange={(e) => setFilter('source', e.target.value)}>
          <option value="">All sources</option>
          {Object.keys(facets?.sources || {}).concat(source && !facets?.sources?.[source] ? [source] : []).map((k) => <option key={k} value={k}>{sourceName(k)}</option>)}
        </select>
        <select className="sel" aria-label="Title" value={title} onChange={(e) => setFilter('title', e.target.value)}>
          <option value="">All titles</option>
          {(facets?.titles || []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          {title && !facets?.titles.some((t) => t.id === title) ? <option value={title}>{title}</option> : null}
        </select>
        <div style={css('flex: 1')} />
        <span style={css('display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--dim)')}>
          <span className="key">K</span>keep<span className="key" style={css('margin-left: 8px')}>D</span>drop<span className="key" style={css('margin-left: 8px')}>↑ ↓</span>move
        </span>
      </div>
    </>
  );

  if (q.loading && !q.data) return <div className="pg-review" style={{ display: 'contents' }}>{head}<Loading /></div>;
  if (q.error && !q.data) return <div className="pg-review" style={{ display: 'contents' }}>{head}<ErrorBox error={q.error} retry={q.reload} /></div>;

  const cap = all ? pool.length : CAP;
  const shown = new Set(pool.slice(0, cap).map((it) => it.id));
  const cs = cur ? stateOf(cur) : 'proposed';

  return (
    <div className="pg-review" style={{ display: 'contents' }}>
      {head}
      {pool.length > 0 && cur ? (
        <div style={css('display: flex; flex-wrap: wrap; gap: 20px 24px; align-items: flex-start')}>
          {view === 'list' ? (
            <section aria-label="Queue" className="ql box" style={css('flex: 3 1 440px; min-width: 0; padding: 8px')}>
              {(q.data?.groups || []).map((g) => {
                const rows = g.items.filter((it) => shown.has(it.id));
                if (!rows.length) return null;
                const left = g.items.filter((it) => stateOf(it) === 'proposed').length;
                return (
                  <div key={g.title + g.video}>
                    <div style={css('display: flex; align-items: center; gap: 10px; padding: 8px 8px 6px')}>
                      <span className="hd" style={css('flex: 1; font-size: 15px; font-weight: 600')}>{g.name}</span>
                      <span className="mono" style={css('font-size: 11px; color: var(--faint)')}>{left} waiting</span>
                    </div>
                    {rows.map((it) => {
                      const st = stateOf(it);
                      const heard = (it.evidence?.heard || []).map(evText);
                      const seen = (it.evidence?.seen || []).map(evText);
                      const why = heard.length ? 'heard: ' + heard.join(', ') : seen.length ? 'seen: ' + seen.join(', ') : '';
                      return (
                        <button key={it.id} type="button" className="qr" aria-current={it.id === cur.id ? 'true' : undefined} onClick={() => setCurId(it.id)}
                          style={css(it.id === cur.id ? 'background:var(--raised);box-shadow:inset 0 0 0 1.5px var(--accent)' : '')}>
                          <span className="still" style={{ ...css('flex:none;width:58px;aspect-ratio:2.4;border-radius:4px' + (st === 'proposed' ? '' : ';opacity:.45')), background: `${bgUrl(it.still)} center/cover #000` }} />
                          <span className="mono" style={css('flex: none; width: 58px; font-size: 12px; color: var(--dim)')}>{hms(it.start)}</span>
                          <span style={css(chipCss(it.family, st))}>{it.name}</span>
                          <span style={css('flex: 1; min-width: 0; font-size: 12px; color: var(--faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis')}>{why}</span>
                          <span style={css('flex: none; font-size: 12px; color: var(--dim)')}>{sourceName(it.source)}</span>
                          <span style={css('flex:none;width:52px;text-align:right;font-size:11px;font-weight:600;color:' + (st === 'accepted' ? 'var(--ok)' : 'var(--faint)'))}>
                            {st === 'accepted' ? 'Kept' : st === 'rejected' ? 'Dropped' : ''}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                );
              })}
              {pool.length > cap ? (
                <div style={css('padding: 10px 8px 4px')}><button type="button" className="btn sm" onClick={() => setAll(true)}>Show all {pool.length}</button></div>
              ) : null}
            </section>
          ) : null}

          <section aria-label="The tag to decide" style={css('min-width:0;display:flex;flex-direction:column;gap:14px;' + (view === 'list' ? 'flex:2 1 360px' : 'flex:1 1 100%;max-width:760px;margin:0 auto'))}>
            <div style={css('position: relative; aspect-ratio: 2.4/1; border-radius: 10px; overflow: hidden; background: #000')}>
              <span role="img" aria-label="Still from the scene" style={{ display: 'block', width: '100%', height: '100%', background: `${bgUrl(cur.still)} center/cover` }} />
            </div>
            <div>
              <div className="mono" style={css('font-size: 12px; color: var(--dim)')}>
                {cur.title_name}{cur.scene != null ? ` · scene ${cur.scene}` : ''} · {hms(cur.start)} to {hms(cur.end)}
              </div>
              {cur.scene_summary || cur.summary ? <div className="clamp" style={css('margin-top: 3px; font-size: 15px; font-weight: 600')}>{cur.scene_summary || cur.summary}</div> : null}
            </div>
            <div className="box" style={css('padding: 16px 18px; display: flex; flex-direction: column; gap: 10px')}>
              <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 10px')}>
                <span className="hd" style={css(chipCss(cur.family, cs) + ';height:34px;font-size:18px;padding:0 14px 0 11px;border-radius:8px')}>{cur.name}</span>
                <span style={css('font-size: 13px; color: var(--dim)')}>
                  {familyName(cur.family)} · proposed by {sourceName(cur.source)}{cur.confidence != null ? ` · ${cur.confidence.toFixed(2)}` : ''}
                </span>
              </div>
              {cur.evidence?.heard?.length ? <div className="ev"><b>Heard</b>{cur.evidence.heard.map(evText).join(', ')}</div> : null}
              {cur.evidence?.seen?.length ? <div className="ev"><b>Seen</b>{cur.evidence.seen.map(evText).join(', ')}</div> : null}
              <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px; padding-top: 4px')}>
                <button type="button" className="btn pri" onClick={() => decide('keep')}>Keep <span className="key">K</span></button>
                <button type="button" className="btn" onClick={() => decide('drop')}>Drop <span className="key">D</span></button>
                <button type="button" className="btn ghost" onClick={() => step(1)}>Skip <span className="key">↓</span></button>
                <div style={css('flex: 1')} />
                <span style={css('font-size:13px;font-weight:600;color:' + (cs === 'accepted' ? 'var(--ok)' : 'var(--faint)'))}>{cs === 'accepted' ? 'Kept' : cs === 'rejected' ? 'Dropped' : ''}</span>
                {cs !== 'proposed' ? <button type="button" className="btn sm ghost" onClick={() => undo(cur)}>Undo</button> : null}
              </div>
            </div>
            <div style={css('display: flex; align-items: center; gap: 12px')}>
              {cur.scene != null ? <Link to={`/videos/${cur.video}/scenes/${cur.scene}`} className="btn sm">Open the scene</Link> : null}
              <span className="mono" style={css('font-size: 12px; color: var(--dim)')}>{ci + 1} of {pool.length}</span>
            </div>
          </section>
        </div>
      ) : (
        <div style={css('padding: 44px 24px; border: 1px dashed var(--border); border-radius: 12px; text-align: center')}>
          <div className="hd" style={css('font-size: 22px; font-weight: 600')}>Nothing to review</div>
          <div style={css('margin-top: 6px; font-size: 14px; color: var(--dim)')}>
            {filtered ? 'No proposed tag matches these filters.' : 'Every proposed tag has been kept or dropped.'}
          </div>
        </div>
      )}
    </div>
  );
}
