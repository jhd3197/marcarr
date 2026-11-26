// Scenes grouped by title, as drawn on the Person and Place boards
// (docs/design/person, docs/design/place). Used by both pages.
import { useState } from 'react';
import { Link } from 'react-router';
import type { SceneHit } from '../../api/types';
import { Chip, css } from '../../components/kit';
import { hms, plural } from '../../lib/format';

export interface SceneGroup {
  title: string; // title id
  name: string;
  year: number | null;
  rows: SceneHit[];
  total: number; // scenes for this title, may be more than rows
}

/** Group hits by title, keeping the order the API gave them. */
export function groupByTitle(hits: SceneHit[]): SceneGroup[] {
  const out: SceneGroup[] = [];
  const at = new Map<string, SceneGroup>();
  for (const h of hits) {
    let g = at.get(h.title);
    if (!g) {
      g = { title: h.title, name: h.title_name, year: h.year, rows: [], total: 0 };
      at.set(h.title, g);
      out.push(g);
    }
    g.rows.push(h);
    g.total += 1;
  }
  return out;
}

export function SceneCard({ hit, maxTags }: { hit: SceneHit; maxTags: number }) {
  const text = hit.summary || hit.line || '';
  const frame = 'display:block;width:100%;height:100%;background:url("' + hit.still + '") center/cover' +
    (hit.spoiler ? ';filter:blur(9px);transform:scale(1.25)' : '');
  return (
    <div className="fcard">
      <Link to={`/videos/${hit.video}/scenes/${hit.scene}`} className="fst" aria-label="Open the scene">
        <span style={css(frame)} />
        <span className="tm">{hms(hit.start)} to {hms(hit.end)}</span>
      </Link>
      {text ? <div className="clamp" style={{ fontSize: 13.5, fontWeight: 600 }}>{text}</div> : null}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
        {hit.tags.slice(0, maxTags).map((t) => <Chip key={t.id} name={t.name} family={t.family} status={t.status} />)}
      </div>
    </div>
  );
}

/** One title's heading, its scene cards and a "Show all N" button. */
export function SceneGroupView({ group, first, maxTags, showYear, onShowAll }: {
  group: SceneGroup;
  first: number; // cards shown before "Show all"
  maxTags: number;
  showYear: boolean;
  onShowAll?: () => Promise<SceneHit[] | null> | void; // loads the rest when the page did not have them
}) {
  const [all, setAll] = useState(false);
  const [extra, setExtra] = useState<SceneHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const rows = extra || group.rows;
  const total = Math.max(group.total, rows.length);
  const shown = all ? rows : rows.slice(0, first);
  const more = !all && total > shown.length;
  const showAll = async () => {
    if (rows.length < total && onShowAll) {
      setBusy(true);
      try {
        const got = await onShowAll();
        if (got) setExtra(got);
      } finally {
        setBusy(false);
      }
    }
    setAll(true);
  };
  return (
    <div>
      <div style={css('display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 12px;padding-bottom:10px;border-bottom:1px solid var(--line);margin-bottom:14px')}>
        <h2 className="h2"><Link to={`/titles/${encodeURIComponent(group.title)}`} style={{ color: 'inherit', textDecoration: 'none' }}>{group.name}</Link></h2>
        {showYear && group.year ? <span className="mono" style={{ fontSize: 12, color: 'var(--faint)' }}>{group.year}</span> : null}
        <span className="mono" style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--dim)' }}>{plural(total, 'scene')}</span>
      </div>
      <div className="res">{shown.map((h) => <SceneCard key={h.video + ':' + h.scene} hit={h} maxTags={maxTags} />)}</div>
      {more ? (
        <div style={{ paddingTop: 16 }}>
          <button type="button" className="btn" disabled={busy} onClick={showAll}>{busy ? 'Loading…' : 'Show all ' + total}</button>
        </div>
      ) : null}
    </div>
  );
}
