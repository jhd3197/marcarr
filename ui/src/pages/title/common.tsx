// Bits shared by the Library, Title and Show pages.
import { Fragment } from 'react';
import { Link } from 'react-router';
import type { Family, Person, StateLine } from '../../api/types';

/** Poster colours from the design; a title without a poster gets one picked from its id. */
const POSTER_COLOURS = ['#d3a85a', '#6fa36a', '#5b93c7', '#9a86d6', '#47b3ad', '#c27a5c', '#b5b9c2', '#d98fb0'];
export function posterColour(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return POSTER_COLOURS[Math.abs(h) % POSTER_COLOURS.length];
}

export const titleHref = (id: string) => `/titles/${encodeURIComponent(id)}`;
// Place ids carry slashes on purpose (hogwarts/great-hall); the route is /places/*.
export const placeHref = (id: string) => '/places/' + id.split('/').map(encodeURIComponent).join('/');

/** Tag families in the order the timeline draws them. */
export const FAMILIES: [string, Family][] = [
  ['Place', 'place'], ['Action', 'action'], ['Beat', 'beat'], ['Mood', 'mood'], ['Occasion', 'occasion'],
  ['Weather', 'weather'], ['Time of day', 'time'], ['People', 'people'], ['Creature', 'creature'], ['Content', 'content'], ['Element', 'element'],
];

/** The design's dot colours, as used under posters and in rows. */
export const DOT_BG: Record<StateLine['kind'], string> = {
  done: 'background:var(--ok)', run: 'background:var(--accent)', queued: 'background:var(--accent)',
  notrun: 'border:1.5px dashed var(--faint)', failed: 'background:var(--bad)', rerun: 'background:var(--warn)',
};

/** Breadcrumb with router links (kit's Crumbs uses plain hrefs, which reload the page). */
export function CrumbLinks({ items }: { items: { name: string; to?: string }[] }) {
  return (
    <nav className="crumb" aria-label="Breadcrumb">
      {items.map((c, i) => (
        <Fragment key={i}>
          {i > 0 ? <span>/</span> : null}
          {c.to ? <Link to={c.to}>{c.name}</Link> : <span>{c.name}</span>}
        </Fragment>
      ))}
    </nav>
  );
}

/** Name to show for a person id: the character from the cast, else the id made readable. */
export function personName(id: string, cast: Map<string, Person>): string {
  const p = cast.get(id);
  if (p) return p.character || p.actor;
  return id.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
export const shortName = (full: string) => full.split(/\s+/)[0] || full;
