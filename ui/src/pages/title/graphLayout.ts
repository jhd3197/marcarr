// What the character graph draws: which people and links are shown, how big each one
// is, and where it sits. Kept apart from the component so it can be tested.
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationLinkDatum, type SimulationNodeDatum } from 'd3-force';
import type { CharacterGraph, GraphPair, GraphPerson } from '../../api/types';

/** Seen in fewer scenes than this: a minor character, hidden unless asked for. */
export const MINOR_SCENES = 3;
/** The most people drawn when minor characters are hidden. */
export const MAX_MAIN = 30;
export const R_MIN = 9;
export const R_MAX = 28;
export const WIDTH = 860;
export const HEIGHT = 540;

export interface Shown {
  people: GraphPerson[];
  pairs: GraphPair[];
  maxShared: number; // the most scenes any shown pair shares
  hiddenPeople: number;
}

/** The people and links to draw. A pair needs at least `minShared` scenes together.
 *  Without `showMinor`, people seen in only a scene or two, or only named, are left out. */
export function shown(g: CharacterGraph, minShared: number, showMinor: boolean): Shown {
  const main = g.people.filter((p) => p.scenes.length >= MINOR_SCENES).slice(0, MAX_MAIN);
  const people = showMinor ? g.people : main.length ? main : g.people.filter((p) => p.scenes.length > 0).slice(0, MAX_MAIN);
  const ids = new Set(people.map((p) => p.id));
  const pairs = g.pairs.filter((e) => e.scenes.length >= minShared && ids.has(e.a) && ids.has(e.b));
  const maxShared = g.pairs.reduce((m, e) => (ids.has(e.a) && ids.has(e.b) ? Math.max(m, e.scenes.length) : m), 0);
  return { people, pairs, maxShared, hiddenPeople: g.people.length - people.length };
}

/** A node's radius: its area grows with screen time. Only named: the smallest. */
export function radius(seconds: number, most: number): number {
  if (!most || seconds <= 0) return R_MIN;
  return R_MIN + (R_MAX - R_MIN) * Math.sqrt(seconds / most);
}

/** A link's stroke width: 1.5 for one scene together, up to 8 for the strongest pair. */
export function strokeWidth(shared: number, most: number): number {
  if (most <= 1) return 1.5;
  return 1.5 + (6.5 * (shared - 1)) / (most - 1);
}

/** A short name to write under a circle: the first word, unless that is an article
 *  ("The Keeper" stays whole, "Mira Vale" becomes "Mira"). */
export function label(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length > 1 && /^(the|a|an|el|la|los|las|le|les|der|die|das)$/i.test(words[0])) return words.slice(0, 2).join(' ');
  return words[0] || name;
}

/** The ids linked to `id` (and `id` itself), to light up its neighbourhood. */
export function neighbours(pairs: GraphPair[], id: string): Set<string> {
  const out = new Set([id]);
  for (const e of pairs) {
    if (e.a === id) out.add(e.b);
    else if (e.b === id) out.add(e.a);
  }
  return out;
}

export interface Placed { x: number; y: number; r: number }

interface Node extends SimulationNodeDatum { id: string; r: number }

/** Where each person sits: a force layout run to rest, so the same graph always lands
 *  the same way. Strong pairs pull together, everyone pushes apart, nobody overlaps. */
export function layout(people: GraphPerson[], pairs: GraphPair[], width = WIDTH, height = HEIGHT): Map<string, Placed> {
  const most = people.reduce((m, p) => Math.max(m, p.seconds), 0);
  const maxShared = pairs.reduce((m, e) => Math.max(m, e.scenes.length), 1);
  // Start on a circle, biggest first, so the result does not depend on chance.
  const nodes: Node[] = people.map((p, i) => {
    const a = (2 * Math.PI * i) / Math.max(1, people.length);
    const ring = Math.min(width, height) * 0.32;
    return { id: p.id, r: radius(p.seconds, most), x: width / 2 + ring * Math.cos(a), y: height / 2 + ring * Math.sin(a) };
  });
  const links: (SimulationLinkDatum<Node> & { w: number })[] = pairs.map((e) => ({ source: e.a, target: e.b, w: e.scenes.length / maxShared }));
  // Spread to fill the drawing: the push grows with the room each person has.
  const room = Math.sqrt((width * height) / Math.max(1, nodes.length));
  const sim = forceSimulation(nodes)
    .force('link', forceLink<Node, SimulationLinkDatum<Node> & { w: number }>(links).id((d) => d.id)
      .distance((l) => room * (1.1 - 0.5 * l.w)).strength((l) => 0.05 + 0.25 * l.w))
    .force('charge', forceManyBody<Node>().strength(-room * 4))
    .force('collide', forceCollide<Node>((d) => d.r + 22))
    .force('x', forceX<Node>(width / 2).strength(0.04))
    .force('y', forceY<Node>(height / 2).strength(0.07))
    .stop();
  for (let i = 0; i < 320; i++) sim.tick();
  const out = new Map<string, Placed>();
  for (const n of nodes) {
    const pad = n.r + 18; // room for the name below
    out.set(n.id, { x: clamp(n.x ?? width / 2, n.r + 4, width - n.r - 4), y: clamp(n.y ?? height / 2, n.r + 4, height - pad), r: n.r });
  }
  return out;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Where a link starts and ends: at the edge of each circle, not its centre. */
export function ends(a: Placed, b: Placed): { x1: number; y1: number; x2: number; y2: number } {
  const dx = b.x - a.x, dy = b.y - a.y;
  const d = Math.hypot(dx, dy) || 1;
  return { x1: a.x + (dx / d) * a.r, y1: a.y + (dy / d) * a.r, x2: b.x - (dx / d) * b.r, y2: b.y - (dy / d) * b.r };
}
