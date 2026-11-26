// Tag evidence on the scene page: which dialogue line a piece of it points at.
import type { EvidenceItem, Line } from '../api/types';
import { evAt, evText } from './format';

/** The dialogue line a piece of "heard" evidence points at: the line playing at its
 *  time, else the first line that says its words. -1 when the scene has none. */
export function lineFor(lines: Line[], item: EvidenceItem): number {
  const at = evAt(item);
  if (at !== null) {
    const i = lines.findIndex((l) => l.start - 0.5 <= at && at < l.end + 0.5);
    if (i >= 0) return i;
  }
  const words = evText(item).trim().toLowerCase();
  return words ? lines.findIndex((l) => l.text.toLowerCase().includes(words)) : -1;
}
