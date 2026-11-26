import { describe, expect, it } from 'vitest';
import type { CharacterGraph, GraphPerson } from '../../api/types';
import { ends, HEIGHT, label, layout, neighbours, R_MAX, R_MIN, radius, shown, strokeWidth, WIDTH } from './graphLayout';

const person = (id: string, scenes: number[], seconds = scenes.length * 60): GraphPerson => ({
  id, name: id, actor: '', photo: null, seconds, scenes, named: 0,
  first: scenes.length ? { n: scenes[0], start: 0 } : null, last: null, gap: null, partners: [],
});

const G: CharacterGraph = {
  title: 't', video: 'v', total_scenes: 10, through: null, scenes: 10,
  people: [person('ann', [1, 2, 3, 4]), person('bo', [1, 2, 3]), person('cy', [4]), person('dee', [])],
  pairs: [
    { a: 'ann', b: 'bo', scenes: [1, 2, 3], seconds: 180 },
    { a: 'ann', b: 'cy', scenes: [4], seconds: 60 },
  ],
};

describe('shown', () => {
  it('leaves out minor characters and their links unless asked', () => {
    const v = shown(G, 1, false);
    expect(v.people.map((p) => p.id)).toEqual(['ann', 'bo']);
    expect(v.pairs).toHaveLength(1);
    expect(v.hiddenPeople).toBe(2);
    expect(shown(G, 1, true).people).toHaveLength(4);
  });

  it('keeps only pairs with enough scenes together', () => {
    expect(shown(G, 2, true).pairs.map((e) => e.b)).toEqual(['bo']);
    expect(shown(G, 1, true).maxShared).toBe(3);
  });

  it('falls back to everyone seen when nobody is a main character', () => {
    const few = { ...G, people: [person('cy', [4]), person('dee', [])], pairs: [] };
    expect(shown(few, 1, false).people.map((p) => p.id)).toEqual(['cy']);
  });
});

describe('sizes', () => {
  it('grows circles with screen time', () => {
    expect(radius(0, 100)).toBe(R_MIN);
    expect(radius(100, 100)).toBe(R_MAX);
    expect(radius(25, 100)).toBeGreaterThan(R_MIN);
  });

  it('thickens lines with scenes together', () => {
    expect(strokeWidth(1, 1)).toBe(1.5);
    expect(strokeWidth(1, 5)).toBe(1.5);
    expect(strokeWidth(5, 5)).toBe(8);
  });
});

describe('layout', () => {
  it('places everyone inside the drawing, the same way every time', () => {
    const v = shown(G, 1, true);
    const a = layout(v.people, v.pairs);
    const b = layout(v.people, v.pairs);
    expect([...a.entries()]).toEqual([...b.entries()]);
    for (const p of a.values()) {
      expect(p.x).toBeGreaterThanOrEqual(p.r);
      expect(p.x).toBeLessThanOrEqual(WIDTH - p.r);
      expect(p.y).toBeGreaterThanOrEqual(p.r);
      expect(p.y).toBeLessThanOrEqual(HEIGHT - p.r);
    }
  });

  it('pulls a strong pair closer than people with no link', () => {
    const v = shown(G, 1, true);
    const at = layout(v.people, v.pairs);
    const d = (x: string, y: string) => Math.hypot(at.get(x)!.x - at.get(y)!.x, at.get(x)!.y - at.get(y)!.y);
    expect(d('ann', 'bo')).toBeLessThan(d('bo', 'dee'));
  });
});

describe('helpers', () => {
  it('finds the neighbourhood of a person', () => {
    expect([...neighbours(G.pairs, 'ann')].sort()).toEqual(['ann', 'bo', 'cy']);
    expect([...neighbours(G.pairs, 'dee')]).toEqual(['dee']);
  });

  it('starts and ends a line at the circle edges', () => {
    const l = ends({ x: 0, y: 0, r: 10 }, { x: 100, y: 0, r: 20 });
    expect(l).toEqual({ x1: 10, y1: 0, x2: 80, y2: 0 });
  });
});

describe('label', () => {
  it('keeps an article with the word after it', () => {
    expect(label('Mira Vale')).toBe('Mira');
    expect(label('The Keeper')).toBe('The Keeper');
    expect(label('Gandalf')).toBe('Gandalf');
  });
});
