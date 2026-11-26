// Small helpers the scene, review and search pages share.
import type { Family } from '../../api/types';

/** Who proposed a tag, as the design writes it. */
export const SOURCE: Record<string, string> = { ai: 'AI', fanscut: 'FansCut', doblarr: 'Doblarr', mcp: 'MCP', person: 'you' };
export const sourceName = (s: string) => SOURCE[s.toLowerCase()] || s;

export const FAMILIES: [Family, string][] = [
  ['place', 'Place'], ['action', 'Action'], ['beat', 'Beat'], ['mood', 'Mood'], ['occasion', 'Occasion'],
  ['weather', 'Weather'], ['people', 'People'], ['creature', 'Creature'], ['content', 'Content'], ['element', 'Element'],
];
export const familyName = (f: Family | string | null | undefined) => (f ? f.charAt(0).toUpperCase() + f.slice(1) : '');

/** The design's chip as a style string (for places that add to it). */
export function chipCss(family: Family | string | null | undefined, status: 'proposed' | 'accepted' | 'rejected'): string {
  const fv = 'var(--f-' + (family || 'place') + ')';
  return 'display:inline-flex;align-items:center;height:24px;padding:0 9px 0 7px;border-radius:6px;box-sizing:border-box;font-size:12px;font-weight:600;white-space:nowrap;' +
    (status === 'proposed' ? 'border:1.5px dashed ' + fv + ';color:var(--text)' : status === 'rejected' ? 'border:1px solid var(--line);color:var(--faint);text-decoration:line-through' : 'border-left:4px solid ' + fv + ';background:var(--raised);color:var(--text)') +
    (family === 'mood' ? ';font-weight:500' : '');
}

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
export const bgUrl = (u: string) => `url("${u.replace(/"/g, '%22')}")`;
