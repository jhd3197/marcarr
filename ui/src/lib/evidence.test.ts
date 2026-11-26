import { describe, expect, it } from 'vitest';
import { lineFor } from './evidence';
import { evAt, evText } from './format';

const LINES = [
  { start: 2, end: 5, text: 'Merry Christmas, everyone!' },
  { start: 8, end: 11, text: 'Look at the snow outside.' },
];

describe('evidence', () => {
  it('reads old and new items', () => {
    expect(evText('snow')).toBe('snow');
    expect(evText({ text: 'snow', at: 9 })).toBe('snow');
    expect(evAt('snow')).toBeNull();
    expect(evAt({ text: 'snow', at: 9 })).toBe(9);
  });

  it('finds the line by time first, then by its words', () => {
    expect(lineFor(LINES, { text: 'anything', at: 9 })).toBe(1);
    expect(lineFor(LINES, { text: 'Christmas', at: 40 })).toBe(0);
    expect(lineFor(LINES, 'SNOW')).toBe(1);
    expect(lineFor(LINES, 'rain')).toBe(-1);
    expect(lineFor(LINES, ' ')).toBe(-1);
  });
});
