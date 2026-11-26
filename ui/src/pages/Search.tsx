// Scene search: tags, a person and words in the dialogue. Built from docs/design/search.
// The search lives in the URL: ?tags=christmas,snow&person=ron-weasley&q=cloak&proposed=0
import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router';
import { api } from '../api/client';
import type { Person, SceneHit, VocabTag } from '../api/types';
import { css, Empty, ErrorBox, Loading, Switch } from '../components/kit';
import { hms } from '../lib/format';
import { useApi } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { bgUrl, chipCss, errText } from './review/labels';
import './search.css';

const PICKS = 10; // tags shown before "All 130 tags"
const PEOPLE = 6; // people shown as pills, the rest in a list

const AV = (size: number) =>
  `flex:none;display:inline-flex;align-items:center;justify-content:center;width:${size}px;height:${size}px;border-radius:50%;font:700 ${Math.round(size * 0.45)}px DM Sans,sans-serif;color:var(--text);background:var(--hover)`;

export default function Search() {
  const [params, setParams] = useSearchParams();
  const tags = useMemo(() => (params.get('tags') || '').split(',').filter(Boolean), [params]);
  const person = params.get('person') || '';
  const q = params.get('q') || '';
  const withProposed = params.get('proposed') !== '0';
  const toast = useToast();

  const [text, setText] = useState(q);
  useEffect(() => setText(q), [q]);
  const [allTags, setAllTags] = useState(false);
  const [shown, setShown] = useState<Record<string, boolean>>({});
  const [more, setMore] = useState<SceneHit[]>([]);
  const [page, setPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);

  const vocab = useApi(() => api.vocab(), []);
  const people = useApi(() => api.people(), []);

  const update = (ch: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(ch)) { if (v) p.set(k, v); else p.delete(k); }
    setParams(p);
  };
  const toggleTag = (id: string) => update({ tags: (tags.includes(id) ? tags.filter((t) => t !== id) : [...tags, id]).join(',') });
  const submit = (e: FormEvent) => { e.preventDefault(); update({ q: text.trim() }); };

  const asked = tags.length > 0 || !!person || !!q;
  const key = [tags.join(','), person, q, withProposed].join('|');
  const hits = useApi(
    () => (asked ? api.search({ tags, person: person || undefined, q: q || undefined, status: withProposed ? 'proposed' : 'accepted' }) : Promise.resolve({ total: 0, items: [] as SceneHit[] })),
    [key],
  );
  useEffect(() => { setMore([]); setPage(1); }, [key]);

  const loadMore = async () => {
    setLoadingMore(true);
    try {
      const r = await api.search({ tags, person: person || undefined, q: q || undefined, status: withProposed ? 'proposed' : 'accepted', page: page + 1 });
      setMore((m) => [...m, ...r.items]);
      setPage(page + 1);
    } catch (e) {
      toast(`Could not load more: ${errText(e)}`, true);
    } finally {
      setLoadingMore(false);
    }
  };

  // -- tag picks: the chosen ones, then the most used ------------------------------
  const vtags: VocabTag[] = useMemo(() => (vocab.data ? vocab.data.families.flatMap((f) => f.tags) : []), [vocab.data]);
  const byId = useMemo(() => new Map(vtags.map((t) => [t.id, t])), [vtags]);
  const picks = useMemo(() => {
    const used = [...vtags].filter((t) => !tags.includes(t.id)).sort((a, b) => (b.counts.accepted + b.counts.proposed) - (a.counts.accepted + a.counts.proposed));
    const chosen = tags.map((id) => byId.get(id) || ({ id, name: id, family: 'place' } as VocabTag));
    return [...chosen, ...used.slice(0, Math.max(0, PICKS - chosen.length))];
  }, [vtags, tags, byId]);

  const tagButton = (t: { id: string; name: string; family: string }) => {
    const on = tags.includes(t.id);
    const fv = `var(--f-${t.family})`;
    return (
      <button key={t.id} type="button" className="tg" aria-pressed={on} onClick={() => toggleTag(t.id)}
        style={css('border-left:4px solid ' + fv + (on ? ';background:var(--text);color:var(--bg);border-color:var(--text);border-left-color:' + fv : ''))}>
        {t.name}
      </button>
    );
  };

  // -- people picks ------------------------------------------------------------------
  const plist: Person[] = people.data?.items || [];
  const ranked = [...plist].sort((a, b) => (b.titles || 0) - (a.titles || 0));
  const pills = ranked.slice(0, PEOPLE);
  const chosenPerson = plist.find((p) => p.id === person);
  if (chosenPerson && !pills.includes(chosenPerson)) pills.push(chosenPerson);
  const rest = ranked.filter((p) => !pills.includes(p));
  const short = (p: Person) => (p.character || p.actor).split(/\s+/)[0];

  // -- results -----------------------------------------------------------------------
  const items = [...(hits.data?.items || []), ...more];
  const total = hits.data?.total ?? 0;
  const groups: { title: string; name: string; year: number | null; rows: SceneHit[] }[] = [];
  for (const h of items) {
    let g = groups.find((x) => x.title === h.title);
    if (!g) { g = { title: h.title, name: h.title_name, year: h.year, rows: [] }; groups.push(g); }
    g.rows.push(h);
  }
  const n = items.length;
  const order = (h: SceneHit) => [...h.tags.filter((t) => tags.includes(t.tag)), ...h.tags.filter((t) => !tags.includes(t.tag))].slice(0, 5);
  const isAccepted = (h: SceneHit) => {
    const mine = tags.length ? h.tags.filter((t) => tags.includes(t.tag)) : h.tags;
    return mine.length > 0 && mine.every((t) => t.status === 'accepted');
  };
  const sceneUrl = (h: SceneHit) => `/videos/${h.video}/scenes/${h.scene}`;
  const copy = (h: SceneHit) => {
    const link = `${location.origin}${sceneUrl(h)}`;
    navigator.clipboard.writeText(link).then(() => toast('Time link copied'), () => toast('Could not copy the link', true));
  };

  return (
    <div className="pg-search" style={{ display: 'contents' }}>
      <header style={css('display: flex; flex-direction: column; gap: 14px')}>
        <h1 className="h1">Search</h1>
        <form onSubmit={submit} style={css('display: flex; flex-wrap: wrap; gap: 10px')}>
          <label style={css('position: relative; flex: 1 1 360px')}>
            <span style={css('position: absolute; left: -9999px')}>Words in the dialogue</span>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--faint)" strokeWidth="2.2" aria-hidden="true" style={css('position: absolute; left: 16px; top: 15px')}><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></svg>
            <input type="search" className="srch" placeholder="Words in the dialogue" value={text} onChange={(e) => setText(e.target.value)} />
          </label>
          <button type="submit" className="btn pri" style={css('height: 50px; padding: 0 24px; font-size: 15px; border-radius: 12px')}>Search</button>
        </form>
        <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 6px')}>
          <span className="lab" style={css('width: 52px')}>Tags</span>
          {vocab.error ? <span style={css('font-size: 12.5px; color: var(--bad)')}>{vocab.error}</span> : null}
          {!allTags ? picks.map(tagButton) : null}
          <a href="#all-tags" role="button" aria-expanded={allTags} style={css('margin-left: 6px; font-size: 12.5px')} onClick={(e) => { e.preventDefault(); setAllTags(!allTags); }}>
            {allTags ? 'Fewer tags' : vtags.length ? `All ${vtags.length} tags` : 'All tags'}
          </a>
        </div>
        {allTags && vocab.data ? (
          <div style={css('display: flex; flex-direction: column; gap: 10px')}>
            {vocab.data.families.map((f) => (
              <div key={f.family} style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 6px')}>
                <span className="lab" style={css('width: 80px')}>{f.name}</span>
                {f.tags.map(tagButton)}
              </div>
            ))}
          </div>
        ) : null}
        <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 6px')}>
          <span className="lab" style={css('width: 52px')}>Person</span>
          {pills.map((p) => {
            const on = person === p.id;
            return (
              <button key={p.id} type="button" className={'pill' + (on ? ' on' : '')} aria-pressed={on} title={`${p.actor} as ${p.character}`}
                onClick={() => update({ person: on ? null : p.id })} style={css('padding-left: 4px')}>
                <span style={css(AV(22) + (p.photo ? ` url(${p.photo}) center/cover` : ''))}>{p.photo ? '' : short(p).charAt(0)}</span>{short(p)}
              </button>
            );
          })}
          {rest.length ? (
            <select className="sel" aria-label="More people" value="" onChange={(e) => e.target.value && update({ person: e.target.value })} style={css('height: 30px')}>
              <option value="">More people…</option>
              {rest.map((p) => <option key={p.id} value={p.id}>{p.character} ({p.actor})</option>)}
            </select>
          ) : null}
        </div>
      </header>

      <section aria-label="Results" style={css('display: flex; flex-direction: column; gap: 22px')}>
        <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px')}>
          <h2 className="h2" style={css('flex: 1 1 200px')}>
            {asked ? `${total || n} ${(total || n) === 1 ? 'scene' : 'scenes'} in ${groups.length} ${groups.length === 1 ? 'title' : 'titles'}` : 'Find a scene'}
          </h2>
          <Switch on={withProposed} label="Include proposed tags" onChange={(v) => update({ proposed: v ? null : '0' })} />
          <span style={css('font-size: 13px')}>Include proposed tags</span>
        </div>

        {!asked ? <Empty>Pick a tag or a person, or type words from the dialogue.</Empty>
          : hits.loading && !hits.data ? <Loading />
          : hits.error ? <ErrorBox error={hits.error} retry={hits.reload} />
          : n === 0 ? (
            <div style={css('padding: 28px 20px; border: 1px dashed var(--border); border-radius: 12px; font-size: 14px; color: var(--dim)')}>
              No scene has all of these. Take one tag off{withProposed ? '' : ', or include proposed tags'}.
            </div>
          ) : groups.map((g) => (
            <div key={g.title}>
              <div style={css('display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; padding-bottom: 10px; border-bottom: 1px solid var(--line); margin-bottom: 14px')}>
                <span className="hd" style={css('font-size: 17px; font-weight: 600')}>{g.name}</span>
                <span className="mono" style={css('font-size: 12px; color: var(--faint)')}>{g.year ?? ''}</span>
                <span className="mono" style={css('margin-left: auto; font-size: 12px; color: var(--dim)')}>{g.rows.length} {g.rows.length === 1 ? 'scene' : 'scenes'}</span>
              </div>
              <div className="res">
                {g.rows.map((h) => {
                  const id = `${h.video}/${h.scene}`;
                  const hidden = h.spoiler && !shown[id];
                  const text = hidden ? 'Hidden as a spoiler' : h.summary;
                  return (
                    <div key={id} style={css('display: flex; flex-direction: column; gap: 8px')}>
                      <Link to={sceneUrl(h)} aria-label={`Open scene ${h.scene}`} style={css('position: relative; display: block; aspect-ratio: 2.4/1; border-radius: 8px; overflow: hidden; background: #000')}>
                        <span style={{ ...css('display:block;width:100%;height:100%' + (hidden ? ';filter:blur(12px);transform:scale(1.2)' : '')), background: `${bgUrl(h.still)} center/cover` }} />
                        {isAccepted(h) ? <span className="bm" aria-hidden="true" /> : null}
                        <span className="mono" style={css('position: absolute; left: 8px; bottom: 8px; padding: 2px 7px; border-radius: 5px; background: rgba(16,19,23,.82); color: #f7f6ef; font-size: 12px')}>{hms(h.start)} to {hms(h.end)}</span>
                      </Link>
                      {text ? <div className="clamp" style={css('font-size: 13.5px; font-weight: 600')}>{text}</div> : null}
                      {h.line && !hidden ? <div className="clamp" style={css('font-size: 13px; color: var(--dim)')}>“{h.line}”</div> : null}
                      {!hidden ? (
                        <div style={css('display: flex; flex-wrap: wrap; gap: 5px')}>
                          {order(h).map((t) => <span key={t.id || t.tag} style={css(chipCss(t.family, t.status))}>{t.name}</span>)}
                        </div>
                      ) : null}
                      <div style={css('display: flex; gap: 6px')}>
                        {hidden ? <button type="button" className="btn sm pri" onClick={() => setShown({ ...shown, [id]: true })}>Show spoiler</button> : null}
                        <Link to={sceneUrl(h)} className="btn sm">Open scene</Link>
                        <button type="button" className="btn sm ghost" onClick={() => copy(h)}>Copy time link</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        {asked && hits.data && n < total ? (
          <div><button type="button" className="btn" disabled={loadingMore} onClick={() => void loadMore()}>{loadingMore ? 'Loading…' : `Show more (${total - n} left)`}</button></div>
        ) : null}
      </section>
    </div>
  );
}
