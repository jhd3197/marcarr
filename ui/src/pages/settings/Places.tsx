// Settings > Named places: franchises, where places come from, fan wiki import.
import { useState } from 'react';
import { Link } from 'react-router';
import { api, raw } from '../../api/client';
import type { Place } from '../../api/types';
import { Empty, ErrorBox, Loading, Switch } from '../../components/kit';
import { useApi } from '../../lib/hooks';
import { plural } from '../../lib/format';
import { useToast } from '../../lib/toast';
import { errText } from './util';

/** Not in types.ts yet: where named places come from (kept under settings.places). */
export interface PlaceSources { from_dialogue: boolean; from_stills: boolean }

function waiting(ps: Place[]): number {
  return ps.reduce((n, p) => n + (p.status === 'proposed' ? 1 : 0) + waiting(p.children || []), 0);
}

export function Places({ sources, setSources }: { sources: PlaceSources; setSources: (s: PlaceSources) => void }) {
  const toast = useToast();
  const places = useApi(() => api.places(), []);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [wiki, setWiki] = useState('');
  const [imported, setImported] = useState<number | null>(null);
  const [busy, setBusy] = useState('');

  const add = async () => {
    const n = name.trim();
    if (!n) return;
    setBusy('add');
    try {
      await api.addPlace({ name: n, franchise: n, inside: null });
      setName('');
      setAdding(false);
      places.reload();
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const importWiki = async () => {
    if (!/^https?:\/\//.test(wiki.trim())) { toast('Give the address of a fan wiki page', true); return; }
    setBusy('wiki');
    try {
      const r = await raw.post<{ imported: number }>('/places/import', { url: wiki.trim() });
      setImported(r.imported);
      places.reload();
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };

  const items = places.data?.items || [];
  return (
    <section aria-labelledby="s-pl">
      <div className="sh" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 id="s-pl" style={{ flex: 1, margin: 0, font: 'inherit' }}>Named places</h2>
        <button type="button" className="btn sm" onClick={() => setAdding(true)}>Add a franchise</button>
      </div>
      {adding ? (
        <div className="fr">
          <label className="fl" htmlFor="s-fr">Franchise</label>
          <div className="fc">
            <input id="s-fr" type="text" className="inp" placeholder="Like Harry Potter" value={name} autoFocus onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') add(); }} style={{ flex: '1 1 220px', width: 'auto' }} />
            <button type="button" className="btn sm pri" disabled={busy === 'add'} onClick={add}>Add</button>
            <button type="button" className="btn sm ghost" onClick={() => setAdding(false)}>Cancel</button>
          </div>
        </div>
      ) : null}
      {places.loading && !places.data ? <Loading /> : places.error ? <ErrorBox error={places.error} retry={places.reload} /> : null}
      {places.data && !places.data.franchises.length && !adding ? <div style={{ paddingTop: 12 }}><Empty>No named places yet. The tags step proposes them when AI is on, or add a franchise.</Empty></div> : null}
      {(places.data?.franchises || []).map((f) => {
        const mine = items.filter((p) => p.franchise === f.name);
        const top = mine.find((p) => !p.inside) || mine[0];
        const w = waiting(mine);
        return (
          <div className="fr" key={f.name}>
            <span className="fl">{f.name}</span>
            <div className="fc">
              <span className="mono" style={{ fontSize: 12.5, color: 'var(--dim)' }}>{plural(f.titles, 'title')} · {plural(f.places, 'place')}</span>
              {w ? <span style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--warn)' }}>{w} to review</span> : null}
              <div style={{ flex: 1 }} />
              {top ? <Link to={`/places/${top.id}`} className="btn sm">Open</Link> : null}
            </div>
          </div>
        );
      })}
      <h3 className="lab" style={{ margin: '24px 0 4px' }}>Where places come from</h3>
      <div className="fr"><span className="fl">Dialogue</span><div className="fc"><Switch on={sources.from_dialogue} onChange={(v) => setSources({ ...sources, from_dialogue: v })} label="Dialogue" /></div></div>
      <div className="fr"><span className="fl">Reference stills</span><div className="fc"><Switch on={sources.from_stills} onChange={(v) => setSources({ ...sources, from_stills: v })} label="Reference stills" /></div></div>
      <div className="fr">
        <label className="fl" htmlFor="s-wiki">Fan wiki</label>
        <div className="fc">
          <input id="s-wiki" type="url" className="inp mono" placeholder="https://" value={wiki} onChange={(e) => setWiki(e.target.value)} style={{ flex: '1 1 220px', width: 'auto' }} />
          <button type="button" className="btn sm" disabled={busy === 'wiki'} onClick={importWiki}>{busy === 'wiki' ? 'Importing…' : 'Import'}</button>
          {imported !== null ? <span style={{ flex: '1 1 100%', fontSize: 12.5, color: 'var(--dim)' }}>{plural(imported, 'place')} imported. They wait for review.</span> : null}
        </div>
      </div>
    </section>
  );
}
