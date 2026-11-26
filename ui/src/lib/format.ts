// Time and number formatting shared by every page.
const two = (n: number) => String(Math.floor(n)).padStart(2, '0');

/** 5390 -> "1:29:50" */
export const hms = (s: number) => Math.floor(s / 3600) + ':' + two((s % 3600) / 60) + ':' + two(s % 60);
/** 125 -> "2:05" */
export const ms = (s: number) => Math.floor(s / 60) + ':' + two(s % 60);
/** hms for an hour or more, ms below */
export const clock = (s: number) => (s >= 3600 ? hms(s) : ms(s));
/** 9530 -> "2h 38m", 2700 -> "45m" */
export const length = (s: number | null | undefined) => {
  if (!s) return '';
  const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
};
/** 2820 -> "47 min", 7500 -> "2h 5m" */
export const took = (s: number | null | undefined) => {
  if (s === null || s === undefined) return '';
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.round(s / 60)} min`;
  return length(s);
};
export const money = (d: number | null | undefined) => '$' + (d || 0).toFixed(2);
export const plural = (n: number, one: string, many = one + 's') => `${n.toLocaleString()} ${n === 1 ? one : many}`;
/** "2026-11-26T01:02:03" -> "01:02" today, "Nov 25" before */
export const when = (iso: string | null | undefined) => {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) return d.toTimeString().slice(0, 5);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
};
export const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join('');
