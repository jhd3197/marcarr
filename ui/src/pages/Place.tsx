// A named place and the places inside it (docs/design/place). The route is
// /places/* because a place id has slashes: /places/hogwarts/great-hall.
// /places on its own (optionally ?franchise=Harry Potter) lists every franchise's places.
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { api } from '../api/client';
import type { Place as PlaceT, Vocab } from '../api/types';
import { Chip, Crumbs, Empty, ErrorBox, Loading, css } from '../components/kit';
import { plural } from '../lib/format';
import { useApi } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { SceneGroupView, groupByTitle } from './person/SceneGroups';
import './Place.css';

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** vocab id -> name and family, for the implied-tag chips. */
function useTagNames() {
  const vocab = useApi<Vocab>(() => api.vocab(), []);
  const map = new Map<string, { name: string; family: string }>();
  for (const f of vocab.data?.families || []) for (const t of f.tags) map.set(t.id, { name: t.name, family: t.family });
  return (id: string) => map.get(id) || { name: id.replace(/[-_]/g, ' ').replace(/^./, (c) => c.toUpperCase()), family: 'place' };
}

/** "Add a place inside" (or "Add a place"): a dashed pill that opens a one-line form. */
function AddPlace({ label, inside, franchise, onAdded }: { label: string; inside: string | null; franchise: string; onAdded: (p: PlaceT) => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const n = name.trim();
    if (!n || busy) return;
    setBusy(true);
    try {
      const p = await api.addPlace({ name: n, inside, franchise });
      toast(`Added ${p.name}`);
      setName('');
      setOpen(false);
      onAdded(p);
    } catch (err) {
      toast(errText(err), true);
    } finally {
      setBusy(false);
    }
  };
  if (!open) {
    return <button type="button" className="pill" style={{ borderStyle: 'dashed' }} onClick={() => setOpen(true)}>{label}</button>;
  }
  return (
    <form onSubmit={submit} style={css('display:flex;flex-direction:column;gap:8px')}>
      <input className="inp" autoFocus placeholder="Name of the place" aria-label="Name of the place" value={name} onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Escape') setOpen(false); }} />
      <div style={css('display:flex;gap:6px')}>
        <button type="submit" className="btn sm pri" disabled={busy || !name.trim()}>Add</button>
        <button type="button" className="btn sm ghost" onClick={() => setOpen(false)}>Cancel</button>
      </div>
    </form>
  );
}

export default function Place() {
  const id = (useParams()['*'] || '').replace(/^\/+|\/+$/g, '');
  return id ? <PlaceView key={id} id={id} /> : <PlaceIndex />;
}

// -- one place ----------------------------------------------------------------------
function PlaceView({ id }: { id: string }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const sub = params.get('in') || '';
  const place = useApi(() => api.place(id), [id]);
  const scenes = useApi(() => api.placeScenes(sub || id), [id, sub]);
  const tagName = useTagNames();
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);

  if (place.error) return <ErrorBox error={place.error} retry={place.reload} />;
  if (!place.data) return <Loading />;
  const p = place.data;
  const pick = (s: string) => {
    const next = new URLSearchParams(params);
    if (s) next.set('in', s); else next.delete('in');
    setParams(next, { replace: true });
  };

  const rename = async (e: FormEvent) => {
    e.preventDefault();
    const n = name.trim();
    if (!n || saving) return;
    if (n === p.name) { setRenaming(false); return; }
    setSaving(true);
    try {
      const got = await api.editPlace(p.id, { name: n });
      place.set({ ...p, ...got, path: p.path.map((x) => (x.id === p.id ? { ...x, name: got.name } : x)) });
      toast(`Renamed to ${got.name}`);
      setRenaming(false);
      if (got.id !== p.id) navigate('/places/' + got.id, { replace: true });
    } catch (err) {
      toast(errText(err), true);
    } finally {
      setSaving(false);
    }
  };

  const ancestors = (p.path || []).filter((x) => x.id !== p.id);
  const crumbs = [
    { name: 'Library', href: '/' },
    { name: p.franchise, href: '/places?franchise=' + encodeURIComponent(p.franchise) },
    { name: 'Places', href: '/places' },
    ...ancestors.map((x) => ({ name: x.name, href: '/places/' + x.id })),
    { name: p.name },
  ];
  const groups = groupByTitle(scenes.data?.items || []);
  const subName = p.children.find((c) => c.id === sub)?.name;

  return (
    <>
      <header style={css('display:flex;flex-direction:column;gap:8px')}>
        <Crumbs items={crumbs} />
        <div style={css('display:flex;align-items:center;flex-wrap:wrap;gap:10px 16px')}>
          {renaming ? (
            <form onSubmit={rename} style={css('display:flex;align-items:center;gap:8px;flex:1 1 320px')}>
              <input className="inp" autoFocus aria-label="New name" value={name} onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Escape') setRenaming(false); }} style={{ maxWidth: 360 }} />
              <button type="submit" className="btn pri" disabled={saving || !name.trim()}>Save</button>
              <button type="button" className="btn ghost" onClick={() => setRenaming(false)}>Cancel</button>
            </form>
          ) : (
            <>
              <h1 className="h1">{p.name}</h1>
              {p.implies.map((t) => { const v = tagName(t); return <Chip key={t} name={v.name} family={v.family} status="accepted" />; })}
              {p.status === 'proposed' ? <Chip name="Proposed" family="place" status="proposed" title="A model named this place; it is not confirmed yet" /> : null}
              <div style={{ flex: 1 }} />
              <button type="button" className="btn" onClick={() => { setName(p.name); setRenaming(true); }}>Rename</button>
            </>
          )}
        </div>
      </header>

      <div style={css('display:flex;flex-wrap:wrap;gap:24px 32px;align-items:flex-start')}>
        <nav aria-label={'Places inside ' + p.name} style={css('flex:1 1 230px;max-width:280px;min-width:0')}>
          <button type="button" className="sub" aria-pressed={!sub} onClick={() => pick('')}>
            All of {p.name}<span className="c">{p.scenes}</span>
          </button>
          {p.children.map((c) => (
            <div key={c.id} style={css('display:flex;align-items:center;gap:2px')}>
              <button type="button" className="sub" aria-pressed={sub === c.id} onClick={() => pick(c.id)} style={{ paddingLeft: 26 }}>
                {c.name}<span className="c">{c.scenes}</span>
              </button>
              <Link to={'/places/' + c.id} className="btn sm ghost" aria-label={'Open ' + c.name} title={'Open ' + c.name}
                style={{ flex: 'none', color: 'var(--dim)', border: 0, padding: '0 8px' }}>›</Link>
            </div>
          ))}
          <div style={{ padding: '10px 10px 0' }}>
            <AddPlace label="Add a place inside" inside={p.id} franchise={p.franchise}
              onAdded={(c) => place.set({ ...p, children: [...p.children, { ...c, children: c.children || [] }] })} />
          </div>
        </nav>

        <div style={css('flex:3 1 560px;min-width:0;display:flex;flex-direction:column;gap:28px')}>
          <section aria-label="Reference stills">
            <div style={css('display:flex;align-items:center;gap:12px;padding-bottom:10px')}>
              <h2 className="h2" style={{ flex: 1 }}>Reference stills</h2>
              <button type="button" className="btn sm" disabled title="Reference stills come in a later version.">Add a still</button>
            </div>
            <Empty>Reference stills come in a later version.</Empty>
          </section>

          <section aria-label="Scenes set here" style={css('display:flex;flex-direction:column;gap:22px')}>
            {scenes.error ? <ErrorBox error={scenes.error} retry={scenes.reload} /> : null}
            {scenes.loading && !scenes.data ? <Loading /> : null}
            {scenes.data && !groups.length ? <Empty>No scenes are set in {subName || p.name} yet.</Empty> : null}
            {groups.map((g) => <SceneGroupView key={(sub || id) + g.title} group={g} first={6} maxTags={3} showYear />)}
          </section>
        </div>
      </div>
    </>
  );
}

// -- every place, by franchise --------------------------------------------------------
function Tree({ places, depth }: { places: PlaceT[]; depth: number }) {
  return (
    <>
      {places.map((c) => (
        <div key={c.id}>
          <Link to={'/places/' + c.id} className="sub" style={{ paddingLeft: 10 + depth * 16, color: 'var(--text)', textDecoration: 'none' }}>
            {c.name}<span className="c">{c.scenes}</span>
          </Link>
          {c.children?.length ? <Tree places={c.children} depth={depth + 1} /> : null}
        </div>
      ))}
    </>
  );
}

/** Nest a flat list by `inside` when the API sends one; keeps given children otherwise. */
function roots(items: PlaceT[]): PlaceT[] {
  if (items.some((p) => p.children?.length)) return items.filter((p) => !p.inside);
  const by = new Map<string, PlaceT>(items.map((p) => [p.id, { ...p, children: [] as PlaceT[] }]));
  const top: PlaceT[] = [];
  for (const p of by.values()) {
    const parent = p.inside ? by.get(p.inside) : undefined;
    if (parent) parent.children.push(p); else top.push(p);
  }
  return top;
}

function PlaceIndex() {
  const [params] = useSearchParams();
  const franchise = params.get('franchise') || '';
  const data = useApi(() => api.places(franchise || undefined), [franchise]);
  if (data.error) return <ErrorBox error={data.error} retry={data.reload} />;
  if (!data.data) return <Loading />;
  const top = roots(data.data.items);
  const names = franchise ? [franchise] : data.data.franchises.map((f) => f.name);
  for (const p of top) if (!names.includes(p.franchise)) names.push(p.franchise);
  const info = new Map(data.data.franchises.map((f) => [f.name, f]));

  return (
    <>
      <header style={css('display:flex;flex-direction:column;gap:8px')}>
        <Crumbs items={franchise
          ? [{ name: 'Library', href: '/' }, { name: 'Places', href: '/places' }, { name: franchise }]
          : [{ name: 'Library', href: '/' }, { name: 'Places' }]} />
        <h1 className="h1">{franchise ? franchise + ' places' : 'Places'}</h1>
      </header>
      {!names.length ? <Empty>No named places yet. They are added when a title in a franchise is analysed, or by hand from a scene.</Empty> : null}
      {names.map((n) => {
        const f = info.get(n);
        const mine = top.filter((p) => p.franchise === n);
        return (
          <section key={n} aria-label={n}>
            <div style={css('display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 12px;padding-bottom:10px;border-bottom:1px solid var(--line);margin-bottom:10px')}>
              <h2 className="h2">{franchise ? n : <Link to={'/places?franchise=' + encodeURIComponent(n)} style={{ color: 'inherit', textDecoration: 'none' }}>{n}</Link>}</h2>
              {f ? <span className="mono" style={css('margin-left:auto;font-size:12px;color:var(--dim)')}>{plural(f.places, 'place')} · {plural(f.titles, 'title')}</span> : null}
            </div>
            <div style={{ maxWidth: 420 }}>
              <Tree places={mine} depth={0} />
              <div style={{ padding: '10px 10px 0' }}>
                <AddPlace label="Add a place" inside={null} franchise={n} onAdded={() => data.reload()} />
              </div>
            </div>
          </section>
        );
      })}
    </>
  );
}
