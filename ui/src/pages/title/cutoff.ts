// "Through this scene": the title page can stop the story at a scene, so the cast,
// places, tags and graph show only what has happened so far. The scene number rides
// in the URL (?through=12) so a copied link opens at the same point.
import type { Person, Scene } from '../../api/types';

/** ?through= as a scene number, or null for the whole story (missing, bad, or past the end). */
export function parseThrough(raw: string | null, total: number): number | null {
  if (!raw) return null;
  const n = Math.floor(Number(raw));
  if (!Number.isFinite(n) || n < 1) return null;
  return total && n >= total ? null : n;
}

/** The scenes up to the cutoff (scenes are numbered from 1). */
export function scenesThrough(scenes: Scene[], through: number | null): Scene[] {
  return through === null ? scenes : scenes.filter((s) => s.n <= through);
}

/** Is this scene past the cutoff? */
export const pastCutoff = (s: Scene, through: number | null) => through !== null && s.n > through;

/** The cast in the scenes so far: people seen, heard or named in them, in cast order.
 *  With no cutoff, the whole cast. */
export function castThrough(cast: Person[], scenes: Scene[], through: number | null): Person[] {
  if (through === null) return cast;
  const met = new Set<string>();
  for (const s of scenesThrough(scenes, through)) {
    for (const p of [...(s.seen || s.people), ...(s.speakers || []), ...(s.mentioned || [])]) met.add(p);
  }
  return cast.filter((p) => met.has(p.id));
}

/** Where the cutoff falls in time: the end of the last scene shown. */
export function cutoffTime(scenes: Scene[], through: number | null): number | null {
  if (through === null) return null;
  const last = scenesThrough(scenes, through).at(-1);
  return last ? last.end : 0;
}

/** A link to the title page at a time, keeping the view and the cutoff. */
export function timeLink(origin: string, path: string, at: number, view: 'timeline' | 'graph', through: number | null): string {
  const q = new URLSearchParams({ t: String(Math.floor(at)) });
  if (view === 'graph') q.set('view', 'graph');
  if (through !== null) q.set('through', String(through));
  return `${origin}${path}?${q.toString()}`;
}
