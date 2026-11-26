// Tags (docs/design/tags): every tag by family, how many scenes have it (kept, and
// waiting for review; each count opens those scenes in search), and which ones are
// written to Plex as labels (the bookmark toggles that). Saved searches (collections)
// are listed on top when there are any. "My tags" are the person's own: made, changed
// and removed here, for the whole library or for one show or movie.
import { useEffect, useState, type FormEvent, type MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { api, collectionHref } from '../api/client';
import type { CustomTag, Family, Vocab, VocabTag } from '../api/types';
import { ErrorBox, Loading } from '../components/kit';
import { useApi } from '../lib/hooks';
import { plural } from '../lib/format';
import { useToast } from '../lib/toast';
import { FAMILIES, familyName } from './review/labels';
import { errText } from './settings/util';
import './Tags.css';

type AnyTag = VocabTag | CustomTag;
const stop = (e: MouseEvent) => e.stopPropagation();
const searchHref = (t: AnyTag, proposed?: '0' | 'only') => `/search?tags=${encodeURIComponent(t.id)}${proposed ? `&proposed=${proposed}` : ''}`;

/** One line when nothing can be counted yet: tags come from the AI step. */
function why(g: Vocab['tagging'] | undefined): { text: string; link: string; to: string } | null {
  if (!g) return null;
  if (!g.enabled) return { text: 'AI tagging is off, so scenes are not being tagged.', link: 'Turn it on in Settings', to: '/settings?tab=ai' };
  if (!g.model) return { text: 'AI tagging has no model, so scenes are not being tagged.', link: 'Pick one in Settings', to: '/settings?tab=ai' };
  if (!g.videos_done) return { text: 'No title has finished the Tags step yet, so the counts are empty.', link: 'Check the steps in Settings', to: '/settings?tab=analysis' };
  return null;
}

/** The new / edit form of a custom tag. id null: a new one. */
interface Draft {
  id: string | null;
  name: string;
  family: Family | '';
  hint: string;
  see: string;
  hear: string;
  scoped: boolean; // false: the whole library
  title: { id: string; name: string } | null;
}
const EMPTY: Draft = { id: null, name: '', family: '', hint: '', see: '', hear: '', scoped: false, title: null };
const draftOf = (t: CustomTag): Draft => ({
  id: t.id, name: t.name, family: t.family || '', hint: t.hint, see: t.see.join(', '), hear: t.hear.join(', '),
  scoped: !!t.scope, title: t.scope ? { id: t.scope.title, name: t.scope.name } : null,
});
const field = { display: 'flex', flexDirection: 'column', gap: 5, fontSize: 12.5, color: 'var(--dim)' } as const;

/** Find one show or movie by name (the library's own title search). */
function TitlePick({ onPick }: { onPick: (t: { id: string; name: string }) => void }) {
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(id);
  }, [text]);
  const found = useApi(() => (q.length < 2 ? Promise.resolve(null) : api.titles({ q, per_page: 8 })), [q]);
  const items = q.length < 2 ? [] : found.data?.items || [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <input className="inp" type="search" aria-label="Find a show or movie" placeholder="Find a show or movie" value={text}
        onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') e.preventDefault(); }} />
      {items.length ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {items.map((t) => (
            <button key={t.id} type="button" className="pill" onClick={() => onPick({ id: t.id, name: t.name })}>
              {t.name}<em>{t.type === 'show' ? 'show' : t.year || 'movie'}</em>
            </button>
          ))}
        </div>
      ) : q.length >= 2 && !found.loading ? <span style={{ fontSize: 12.5 }}>{found.error || 'Nothing by that name'}</span> : null}
    </div>
  );
}

function TagForm({ start, onSaved, onCancel }: { start: Draft; onSaved: (t: CustomTag, isNew: boolean) => void; onCancel: () => void }) {
  const toast = useToast();
  const [d, setD] = useState(start);
  const [busy, setBusy] = useState(false);
  const set = (part: Partial<Draft>) => setD((x) => ({ ...x, ...part }));
  const ready = !!d.name.trim() && (!d.scoped || !!d.title);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    const body = { name: d.name.trim(), family: d.family || null, hint: d.hint, see: d.see, hear: d.hear, scope: d.scoped && d.title ? d.title.id : null };
    try {
      onSaved(d.id ? await api.editCustomTag(d.id, body) : await api.addCustomTag(body), !d.id);
    } catch (err) {
      toast(errText(err), true);
      setBusy(false);
    }
  };
  return (
    <form onSubmit={save} aria-label={d.id ? `Change ${start.name}` : 'New tag'} onKeyDown={(e) => { if (e.key === 'Escape') onCancel(); }}
      style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(240px, 100%), 1fr))', gap: '12px 14px', margin: '0 2px 12px', padding: 14, borderRadius: 10, background: 'var(--raised)' }}>
      <label style={field}>Name
        <input className="inp" autoFocus maxLength={60} placeholder="Like Running gag" value={d.name} onChange={(e) => set({ name: e.target.value })} />
      </label>
      <label style={field}>Family
        <select className="sel" value={d.family} onChange={(e) => set({ family: e.target.value as Family | '' })}>
          <option value="">None</option>
          {FAMILIES.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
      </label>
      <label style={{ ...field, gridColumn: '1 / -1' }}>What it means
        <input className="inp" maxLength={300} placeholder="One line the AI reads, like: the stapler goes missing again" value={d.hint} onChange={(e) => set({ hint: e.target.value })} />
      </label>
      <label style={field}>Things to see, separated by commas
        <input className="inp" placeholder="stapler, empty desk" value={d.see} onChange={(e) => set({ see: e.target.value })} />
      </label>
      <label style={field}>Words to hear, separated by commas
        <input className="inp" placeholder="where's my stapler" value={d.hear} onChange={(e) => set({ hear: e.target.value })} />
      </label>
      <div style={{ ...field, gridColumn: '1 / -1' }}>
        <span>Where it applies</span>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
          <span className="seg">
            <button type="button" aria-pressed={!d.scoped} onClick={() => set({ scoped: false })}>Whole library</button>
            <button type="button" aria-pressed={d.scoped} onClick={() => set({ scoped: true })}>One show or movie</button>
          </span>
          {d.scoped && d.title ? (
            <>
              <span style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text)' }}>{d.title.name}</span>
              <button type="button" className="btn sm ghost" onClick={() => set({ title: null })}>Change</button>
            </>
          ) : null}
        </div>
        {d.scoped && !d.title ? <TitlePick onPick={(t) => set({ title: t })} /> : null}
      </div>
      <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <button type="submit" className="btn sm pri" disabled={!ready || busy}>{d.id ? 'Save' : 'Add tag'}</button>
        <button type="button" className="btn sm ghost" onClick={onCancel}>Cancel</button>
        {d.see.trim() ? <span style={{ fontSize: 12.5 }}>With things to see, the AI only proposes it when it sees one of them.</span> : null}
      </div>
    </form>
  );
}

export default function Tags() {
  const toast = useToast();
  const nav = useNavigate();
  const [used, setUsed] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const vocab = useApi(() => api.vocab(), []);
  const saved = useApi(() => api.collections(), []);

  const saved_ = (t: CustomTag, isNew: boolean) => {
    const v = vocab.data;
    if (v) vocab.set({ ...v, mine: isNew ? [...v.mine, t] : v.mine.map((x) => (x.id === t.id ? t : x)) });
    setDraft(null);
    toast(isNew ? `${t.name} added. The AI proposes it the next time the Tags step runs` : `${t.name} saved`);
  };
  const removeMine = async (t: CustomTag) => {
    if (!window.confirm(`Remove ${t.name}? If scenes have it, they keep it and the tag is only retired.`)) return;
    try {
      const r = await api.deleteCustomTag(t.id);
      const v = vocab.data;
      if (v) vocab.set({ ...v, mine: r.tag ? v.mine.map((x) => (x.id === t.id ? r.tag! : x)) : v.mine.filter((x) => x.id !== t.id) });
      if (draft?.id === t.id) setDraft(null);
      toast(r.retired ? `${t.name} is on scenes, so it is retired: they keep it, the AI stops proposing it` : `${t.name} removed`);
    } catch (e) { toast(errText(e), true); }
  };
  const restoreMine = async (t: CustomTag) => {
    try {
      const out = await api.editCustomTag(t.id, { retired: false });
      const v = vocab.data;
      if (v) vocab.set({ ...v, mine: v.mine.map((x) => (x.id === t.id ? out : x)) });
      toast(`${t.name} is proposed again`);
    } catch (e) { toast(errText(e), true); }
  };

  const toggleLabel = async (t: AnyTag) => {
    const v = vocab.data;
    if (!v) return;
    const flip = (doc: Vocab, label: boolean): Vocab => ({
      ...doc,
      mine: doc.mine.map((x) => (x.id === t.id ? { ...x, label } : x)),
      families: doc.families.map((f) => ({ ...f, tags: f.tags.map((x) => (x.id === t.id ? { ...x, label } : x)) })),
    });
    vocab.set(flip(v, !t.label));
    try {
      const r = await api.setTagLabel(t.id, !t.label);
      toast(r.label ? `${t.name} is written to Plex as a label` : `${t.name} is no longer written to Plex`);
    } catch (e) {
      vocab.set(flip(v, t.label));
      toast(errText(e), true);
    }
  };

  const head = (
    <header style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px 16px' }}>
      <h1 className="h1" style={{ flex: '1 1 200px' }}>Tags</h1>
      <span style={{ fontSize: 12.5, color: 'var(--dim)' }}>Scenes: kept, <span style={{ color: 'var(--mark)' }}>to review</span></span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--dim)' }}><span className="bm" />Written to Plex as a label</span>
      <button type="button" role="switch" className="sw" aria-checked={used} aria-label="Only tags in use" onClick={() => setUsed(!used)}><i /></button>
      <span style={{ fontSize: 13 }}>Only tags in use</span>
    </header>
  );

  if (!vocab.data) {
    return <div className="pg-tags" style={{ display: 'contents' }}>{head}{vocab.error ? <ErrorBox error={vocab.error} retry={vocab.reload} /> : <Loading />}</div>;
  }
  const v = vocab.data;
  const note = why(v.tagging);
  const mine = v.mine.filter((t) => !used || t.counts.accepted > 0 || t.counts.proposed > 0);
  const nameLink = (t: AnyTag) => (
    <Link to={searchHref(t)} onClick={stop} style={t.counts.accepted || t.counts.proposed ? { fontWeight: 600 } : { color: 'var(--dim)' }}>{t.name}</Link>
  );
  const bookmark = (t: AnyTag) => (
    <button type="button" className={'bm' + (t.label ? ' on' : '')} aria-pressed={t.label}
      aria-label={t.label ? `Stop writing ${t.name} to Plex` : `Write ${t.name} to Plex as a label`}
      title={t.label ? 'Written to Plex as a label' : 'Write to Plex as a label'}
      onClick={(e) => { e.stopPropagation(); toggleLabel(t); }} />
  );
  const countsOf = (t: AnyTag) => {
    const kept = t.counts.accepted;
    const wait = t.counts.proposed;
    return (
      <span className="cs">
        {kept ? <Link to={searchHref(t, '0')} onClick={stop} title={`${plural(kept, 'scene')} kept`} aria-label={`${t.name}: ${plural(kept, 'scene')} kept`}>{kept}</Link>
          : <span title="No scenes kept">0</span>}
        {wait ? <Link to={searchHref(t, 'only')} onClick={stop} className="rv" title={`${plural(wait, 'scene')} to review`} aria-label={`${t.name}: ${plural(wait, 'scene')} to review`}>{wait}</Link>
          : <span title="No scenes to review">0</span>}
      </span>
    );
  };

  return (
    <div className="pg-tags" style={{ display: 'contents' }}>
      {head}
      {note ? <p role="status" style={{ margin: 0, fontSize: 13.5, color: 'var(--dim)' }}>{note.text} <Link to={note.to}>{note.link}</Link></p> : null}

      {saved.data?.items.length ? (
        <section className="box" aria-label="Saved combinations" style={{ padding: '14px 18px 16px' }}>
          <h2 className="h2" style={{ paddingBottom: 10 }}>Saved combinations</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {saved.data.items.map((c) => (
              <Link key={c.id} to={collectionHref(c)} className="pill" title={plural(c.scenes, 'scene') + ' kept'} style={{ color: 'var(--text)' }}>
                {c.name}<em>{c.scenes}</em>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <section className="box" aria-label="My tags" style={{ padding: '14px 16px 12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px 14px', padding: '0 2px 6px' }}>
          <span style={{ flex: 'none', width: 6, height: 22, borderRadius: 3, background: 'var(--accent)' }} />
          <h2 className="h2">My tags</h2>
          {v.mine.length ? <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{plural(v.mine.length, 'tag')}</span> : null}
          <div style={{ flex: 1 }} />
          {draft ? null : <button type="button" className="btn sm" onClick={() => setDraft(EMPTY)}>New tag</button>}
        </div>
        <p style={{ margin: '0 2px 12px', fontSize: 13.5, color: 'var(--dim)' }}>
          Tags of your own, like a running gag or a catchphrase in one show. The AI proposes them and you keep them.
        </p>
        {draft ? <TagForm key={draft.id || 'new'} start={draft} onSaved={saved_} onCancel={() => setDraft(null)} /> : null}
        {mine.map((t) => (
          <div key={t.id} className="tl" title={t.hint || undefined} onClick={() => nav(searchHref(t))}
            style={{ height: 'auto', minHeight: 32, flexWrap: 'wrap', rowGap: 2, padding: '3px 8px', opacity: t.retired || t.off ? 0.55 : undefined }}>
            <span style={{ flex: 'none', width: 4, height: 16, borderRadius: 2, background: t.family ? `var(--f-${t.family})` : 'var(--accent)' }} />
            {nameLink(t)}
            {bookmark(t)}
            <span style={{ flex: '1 1 140px', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12.5, color: 'var(--dim)' }}>
              {t.retired ? 'Retired: not proposed any more' : [t.scope ? `Only ${t.scope.name}` : 'Whole library', familyName(t.family), t.off ? 'family off in Settings' : ''].filter(Boolean).join(' · ')}
            </span>
            {countsOf(t)}
            {t.retired
              ? <button type="button" className="btn sm ghost" onClick={(e) => { e.stopPropagation(); void restoreMine(t); }}>Restore</button>
              : <button type="button" className="btn sm ghost" aria-label={`Edit ${t.name}`} onClick={(e) => { e.stopPropagation(); setDraft(draftOf(t)); }}>Edit</button>}
            <button type="button" className="btn sm ghost" aria-label={`Remove ${t.name}`} onClick={(e) => { e.stopPropagation(); void removeMine(t); }}>Remove</button>
          </div>
        ))}
        {used && v.mine.length && !mine.length ? <p style={{ margin: '0 2px', fontSize: 13, color: 'var(--faint)' }}>None of your tags is on a scene yet.</p> : null}
      </section>

      {v.families.map((f) => {
        const tags = f.tags.filter((t) => !used || t.counts.accepted > 0 || t.counts.proposed > 0);
        if (used && !tags.length) return null;
        return (
          <section key={f.family} className="box" aria-label={f.name} style={{ padding: '14px 16px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px 14px', padding: '0 2px 10px' }}>
              <span style={{ flex: 'none', width: 6, height: 22, borderRadius: 3, background: `var(--f-${f.family})` }} />
              <h2 className="h2">{f.name}</h2>
              <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{plural(f.tags.length, 'tag')}</span>
              {f.subjective ? <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, border: '1px solid var(--border)', color: 'var(--dim)' }}>Subjective</span> : null}
              <div style={{ flex: 1 }} />
              {f.off ? <Link to="/settings?tab=tags" style={{ fontSize: 12.5 }}>Off in Settings</Link> : null}
            </div>
            <div className="tgrid" style={f.off ? { opacity: 0.45 } : undefined}>
              {tags.map((t) => (
                <div key={t.id} className="tl" title={t.hint || undefined} onClick={() => nav(searchHref(t))}>
                  {nameLink(t)}
                  {bookmark(t)}
                  {countsOf(t)}
                </div>
              ))}
            </div>
          </section>
        );
      })}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(360px, 100%), 1fr))', gap: 18 }}>
        <section className="box" aria-label="Marcarr's own tags" style={{ padding: '14px 18px 16px' }}>
          <h2 className="h2" style={{ paddingBottom: 8 }}>Marcarr&apos;s own</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {v.own.map((o) => (
              <span key={o.id} title={o.hint || undefined} style={{ display: 'inline-flex', alignItems: 'center', height: 24, padding: '0 9px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'var(--raised)', borderLeft: '4px solid var(--accent)' }}>{o.name}</span>
            ))}
          </div>
        </section>
        <section className="box" aria-label="Signals" style={{ padding: '14px 18px 16px' }}>
          <h2 className="h2" style={{ paddingBottom: 8 }}>Signals</h2>
          <div className="mono" style={{ fontSize: 12.5, lineHeight: 1.9, color: 'var(--dim)' }}>{v.signals.map((s) => s.name).join(' · ')}</div>
        </section>
      </div>
    </div>
  );
}
