// One cast member across the library (docs/design/person): faces waiting for a
// name, confirmed in bulk, then the person's scenes grouped by title.
import { useState } from 'react';
import { useParams } from 'react-router';
import { api, urls } from '../api/client';
import type { Face } from '../api/types';
import { Crumbs, Empty, ErrorBox, Loading, css } from '../components/kit';
import { hms, initials, plural } from '../lib/format';
import { useApi } from '../lib/hooks';
import { useToast } from '../lib/toast';
import { SceneGroupView, groupByTitle } from './person/SceneGroups';
import './Person.css';

export default function Person() {
  const { id = '' } = useParams();
  const toast = useToast();
  const person = useApi(() => api.person(id), [id]);
  const faces = useApi(() => api.personFaces(id), [id]);
  const scenes = useApi(() => api.personScenes(id), [id]);
  const [pick, setPick] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);

  if (person.error) return <ErrorBox error={person.error} retry={person.reload} />;
  if (!person.data) return <Loading />;
  const p = person.data;

  // Faces still unsure (confirmed === null) are the ones waiting for a name.
  const open: Face[] = (faces.data?.items || []).filter((f) => f.confirmed === null);
  const nPick = open.filter((f) => pick[f.id]).length;
  const who = (p.character || p.actor).split(/\s+/)[0];

  const decide = async (action: 'confirm' | 'reject') => {
    const ids = open.filter((f) => pick[f.id] || !nPick).map((f) => f.id);
    if (!ids.length || busy) return;
    setBusy(true);
    try {
      if (ids.length === 1) {
        if (action === 'confirm') await api.confirmFace(ids[0]);
        else await api.rejectFace(ids[0]);
      } else {
        await api.bulkFaces(ids, action);
      }
      const gone = new Set(ids);
      if (faces.data) {
        faces.set({
          ...faces.data,
          items: faces.data.items.map((f) => (gone.has(f.id) ? { ...f, confirmed: action === 'confirm' } : f)),
        });
      }
      setPick({});
      toast(action === 'confirm' ? `Confirmed ${plural(ids.length, 'face')}` : `Marked ${plural(ids.length, 'face')} as not ${who}`);
      if (action === 'confirm') scenes.reload();
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), true);
    } finally {
      setBusy(false);
    }
  };

  const titleCount = p.titles ?? p.titles_in.length;
  const analysed = p.titles_in.filter((t) => t.scenes > 0).length;
  const counts = 'In ' + plural(titleCount, 'title') + ' · ' + plural(p.scene_count, 'scene') +
    (analysed && analysed < titleCount ? ' in the ' + analysed + ' analysed here' : '');
  const only = p.titles_in.length === 1 ? p.titles_in[0].name : '';

  const groups = groupByTitle(scenes.data?.items || []);
  for (const g of groups) {
    const t = p.titles_in.find((x) => x.id === g.title);
    if (t && t.scenes > g.total) g.total = t.scenes;
  }

  return (
    <>
      <header style={css('display:flex;align-items:center;flex-wrap:wrap;gap:16px 22px')}>
        <span
          role="img"
          aria-label={p.actor}
          style={{
            ...css('flex:none;width:104px;height:104px;border-radius:16px;display:flex;align-items:center;justify-content:center;font:700 36px Outfit,DM Sans,sans-serif;color:var(--dim)'),
            background: p.photo ? `var(--hover) url("${p.photo}") center/cover` : 'var(--hover)',
          }}
        >
          {p.photo ? '' : initials(p.actor || p.character)}
        </span>
        <div style={css('flex:1 1 320px;min-width:0;display:flex;flex-direction:column;gap:8px')}>
          <Crumbs items={[{ name: 'Library', href: '/' }, { name: 'People' }, { name: p.actor || p.character }]} />
          <h1 className="h1">{p.actor || p.character}</h1>
          {p.character ? <div style={{ fontSize: 15, color: 'var(--dim)' }}>{p.character}{only ? ' in ' + only : ''}</div> : null}
          <div className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{counts}</div>
        </div>
      </header>

      <section aria-label="Faces waiting for a name">
        <div style={css('display:flex;align-items:center;flex-wrap:wrap;gap:8px 12px;padding-bottom:12px')}>
          <h2 className="h2" style={{ flex: '1 1 200px' }}>
            {open.length ? plural(open.length, 'face') + ' waiting for a name' : faces.loading ? 'Faces' : 'No faces waiting'}
          </h2>
          {open.length ? (
            <>
              <button type="button" className="btn sm ghost" onClick={() => {
                const next: Record<string, boolean> = {};
                if (nPick !== open.length) open.forEach((f) => { next[f.id] = true; });
                setPick(next);
              }}>{nPick === open.length ? 'Pick none' : 'Pick all'}</button>
              <button type="button" className="btn sm" disabled={busy} onClick={() => decide('reject')}>Not them</button>
              <button type="button" className="btn sm pri" disabled={busy} onClick={() => decide('confirm')}>{nPick ? 'Confirm ' + nPick : 'Confirm all'}</button>
            </>
          ) : null}
        </div>
        {faces.error ? <ErrorBox error={faces.error} retry={faces.reload} /> : faces.loading && !faces.data ? <Loading /> : null}
        {open.length ? (
          <div style={css('display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px')}>
            {open.map((f) => (
              <div key={f.id} style={css('display:flex;flex-direction:column;gap:6px')}>
                <button
                  type="button"
                  className="pk"
                  aria-pressed={!!pick[f.id]}
                  aria-label={'Face at ' + hms(f.at)}
                  onClick={() => setPick({ ...pick, [f.id]: !pick[f.id] })}
                  style={{ background: `#000 url("${f.still || urls.face(f.id)}") center/cover` }}
                >
                  <span className="tm">{hms(f.at)}</span>
                </button>
                <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{who}? {f.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section aria-label="Scenes" style={css('display:flex;flex-direction:column;gap:22px')}>
        {scenes.error ? <ErrorBox error={scenes.error} retry={scenes.reload} /> : null}
        {scenes.loading && !scenes.data ? <Loading /> : null}
        {scenes.data && !groups.length ? <Empty>No scenes with {p.actor || p.character} yet. They appear once a title with them is analysed.</Empty> : null}
        {groups.map((g) => (
          <SceneGroupView
            key={g.title}
            group={g}
            first={8}
            maxTags={4}
            showYear={false}
            onShowAll={() => api.personScenes(id, g.title).then((r) => r.items)}
          />
        ))}
      </section>
    </>
  );
}
