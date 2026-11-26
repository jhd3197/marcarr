import { describe, expect, it } from 'vitest';
import type { Person, Scene } from '../../api/types';
import { castThrough, cutoffTime, parseThrough, pastCutoff, scenesThrough, timeLink } from './cutoff';

const scene = (n: number, seen: string[] = [], mentioned: string[] = []): Scene => ({
  n, start: (n - 1) * 10, end: n * 10, shots: 1, people: seen, seen, speakers: [], mentioned, tags: [],
  place: null, place_name: null, summary: '', still: '', spoiler: false, uncertain: false, to_review: 0,
});
const person = (id: string): Person => ({ id, actor: id, character: id, photo: null });

const SCENES = [scene(1, ['ann']), scene(2, ['ann'], ['cy']), scene(3, ['bo'])];
const CAST = [person('ann'), person('bo'), person('cy'), person('dee')];

describe('parseThrough', () => {
  it('reads a scene number and ignores the rest', () => {
    expect(parseThrough('2', 3)).toBe(2);
    expect(parseThrough('2.7', 3)).toBe(2);
    expect(parseThrough(null, 3)).toBeNull();
    expect(parseThrough('x', 3)).toBeNull();
    expect(parseThrough('0', 3)).toBeNull();
    expect(parseThrough('3', 3)).toBeNull(); // the last scene is the whole story
    expect(parseThrough('9', 0)).toBe(9); // scenes not loaded yet: keep it
  });
});

describe('the cutoff', () => {
  it('keeps the scenes so far', () => {
    expect(scenesThrough(SCENES, 2).map((s) => s.n)).toEqual([1, 2]);
    expect(scenesThrough(SCENES, null)).toBe(SCENES);
    expect(pastCutoff(SCENES[2], 2)).toBe(true);
    expect(pastCutoff(SCENES[2], null)).toBe(false);
  });

  it('keeps the cast met so far, named ones included', () => {
    expect(castThrough(CAST, SCENES, 2).map((p) => p.id)).toEqual(['ann', 'cy']);
    expect(castThrough(CAST, SCENES, null)).toBe(CAST);
  });

  it('places the cutoff at the end of the last scene shown', () => {
    expect(cutoffTime(SCENES, 2)).toBe(20);
    expect(cutoffTime(SCENES, null)).toBeNull();
  });
});

describe('timeLink', () => {
  it('keeps the view and the cutoff', () => {
    expect(timeLink('https://m', '/titles/x', 65.4, 'timeline', null)).toBe('https://m/titles/x?t=65');
    expect(timeLink('https://m', '/titles/x', 5, 'graph', 12)).toBe('https://m/titles/x?t=5&view=graph&through=12');
  });
});
