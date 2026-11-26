// The multi-lane timeline of a title page: ruler, scenes, one lane per tag family,
// named places, the people with most screen time, and the measured signals.
import { useLayoutEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import type { Person, Scene, Signal, StepState } from '../../api/types';
import { Avatar, css } from '../../components/kit';
import { FAMILIES, personName, shortName } from './common';

interface Bar { t: string; s: string }
interface Lane { key: string; label: string; labelStyle: string; trackStyle: string; bars: Bar[]; person?: Person | null }

const ZOOMS = [1, 2, 4, 8];
const MAX_PEOPLE = 6;
const SIGNALS = ['dark', 'loud', 'silence'];
// Ruler spacing: the smallest step that keeps about six labels per screen width.
const TICKS = [60, 120, 300, 600, 900, 1800, 3600];

const two = (n: number) => String(Math.floor(n)).padStart(2, '0');
const lab = (h: number, extra = '') => `height:${h}px;display:flex;align-items:center;gap:6px;font-size:12px;color:var(--dim);white-space:nowrap;overflow:hidden${extra}`;
const trk = (h: number) => `position:relative;height:${h}px;border-radius:3px;background:var(--well)`;
const note = (text: string): Bar[] => [{ t: text, s: 'position:absolute;top:0;bottom:0;left:0;right:0;display:flex;align-items:center;padding:0 12px;font-size:12.5px;color:var(--dim);border:1px dashed var(--border);border-radius:6px;white-space:nowrap;overflow:hidden' }];

export interface TimelineProps {
  duration: number;
  scenes: Scene[];
  signals: Signal[];
  cast: Map<string, Person>;
  tagsStep: StepState;
  facesStep: StepState;
  cutoff?: number | null; // the story stops here (seconds); later is shaded and left empty
  selected: number | null; // scene number
  at: number; // playhead, seconds
  episode: boolean;
  onSeek: (t: number) => void;
}

export function Timeline({ duration: D, scenes, cutoff = null, signals, cast, tagsStep, facesStep, selected, at, episode, onSeek }: TimelineProps) {
  const [zi, setZi] = useState(0);
  const z = ZOOMS[zi];
  const scroller = useRef<HTMLDivElement>(null);
  const pct = (t: number) => ((t / D) * 100).toFixed(3) + '%';
  // Tags from people and other apps show even when the AI step is off.
  const tagsOn = tagsStep !== 'off' || scenes.some((s) => s.tags.length > 0);
  const facesOn = (facesStep !== 'none' && facesStep !== 'off') || scenes.some((s) => s.people.length > 0);
  const sel = scenes.find((s) => s.n === selected) || null;

  const lanes = useMemo<Lane[]>(() => {
    const out: Lane[] = [];
    const step = TICKS.find((s) => D / s <= 6 * z) || 3600;
    const ticks: number[] = [];
    for (let t = 0; t < D - step * 0.4; t += step) ticks.push(t);
    out.push({ key: 'ruler', label: '', labelStyle: lab(14), trackStyle: 'position:relative;height:14px', bars: ticks.map((t, i) => ({ t: Math.floor(t / 3600) + ':' + two((t % 3600) / 60), s: 'position:absolute;top:0;font:400 10px DM Mono,monospace;color:var(--faint);left:' + pct(t) + (i ? ';transform:translateX(-50%)' : '') })) });

    out.push({ key: 'scenes', label: 'Scenes', labelStyle: lab(28, ';font-weight:600;color:var(--text)'), trackStyle: 'position:relative;height:28px', bars: scenes.map((c) => ({ t: '', s: 'position:absolute;top:0;bottom:0;border-radius:2px;left:' + pct(c.start) + ';width:calc(' + pct(c.end - c.start) + ' - 1px);background:' + (c.n === selected ? 'var(--accent)' : 'var(--border)') })) });

    if (!tagsOn) out.push({ key: 'tags-off', label: 'Tags', labelStyle: lab(40), trackStyle: 'position:relative;height:40px', bars: note('Tags and named places need AI. Turn it on in Settings.') });
    else {
      const named = scenes.filter((m) => m.place_name);
      for (const [name, fam] of FAMILIES) {
        const bars: Bar[] = [];
        for (const m of scenes) {
          m.tags.filter((t) => t.family === fam).slice(0, 2).forEach((t, r) => {
            bars.push({ t: z >= 4 ? t.name : '', s: 'position:absolute;height:13px;top:' + r * 15 + 'px;box-sizing:border-box;border-radius:3px;overflow:hidden;padding:0 3px;font:600 10px/13px DM Sans,sans-serif;white-space:nowrap;left:' + pct(m.start) + ';width:calc(' + pct(m.end - m.start) + ' - 1px);' + (t.status === 'proposed' ? 'border:1.5px dashed var(--f-' + fam + ');color:var(--text);line-height:10px' : 'background:var(--f-' + fam + ');color:var(--bg)') });
          });
        }
        if (bars.length) out.push({ key: fam, label: name, labelStyle: lab(28, ';border-left:4px solid var(--f-' + fam + ');padding-left:7px;box-sizing:border-box'), trackStyle: trk(28), bars });
        if (fam === 'place' && named.length) {
          out.push({ key: 'named', label: 'Named places', labelStyle: lab(16, ';padding-left:11px;font-size:11px'), trackStyle: trk(16), bars: named.map((m) => ({ t: z >= 2 ? (m.place_name || '').split(/\s*[›>]\s*/).pop() || '' : '', s: 'position:absolute;top:1px;bottom:1px;box-sizing:border-box;border-radius:3px;overflow:hidden;padding:0 3px;font:600 10px/14px DM Sans,sans-serif;white-space:nowrap;color:var(--text);left:' + pct(m.start) + ';width:calc(' + pct(m.end - m.start) + ' - 1px);background:color-mix(in srgb,var(--f-place) 38%,var(--panel))' })) });
        }
      }
    }

    if (!facesOn) {
      const text = facesStep === 'off' ? 'Faces are turned off in Settings.' : 'Faces need two models that are not downloaded yet. Get them in Settings.';
      out.push({ key: 'faces-off', label: 'Faces', labelStyle: lab(40), trackStyle: 'position:relative;height:40px', bars: note(text) });
    } else {
      // Screen time per person from the scenes they are seen in; touching scenes merge
      // into one run. A scene where they are only heard or named is a hollow tick.
      const seenIn = (s: Scene) => s.seen || s.people;
      const time = new Map<string, number>();
      for (const s of scenes) for (const p of seenIn(s)) time.set(p, (time.get(p) || 0) + (s.end - s.start));
      const top = [...time.entries()].sort((a, b) => b[1] - a[1]).slice(0, MAX_PEOPLE).map(([p]) => p);
      for (const id of top) {
        const runs: [number, number][] = [];
        const ticks: Bar[] = [];
        for (const s of scenes) {
          if (!seenIn(s).includes(id)) {
            const how = s.speakers?.includes(id) ? 'heard' : s.mentioned?.includes(id) ? 'named' : '';
            if (how) ticks.push({ t: '', s: 'position:absolute;top:3px;bottom:3px;box-sizing:border-box;border-radius:2px;border:1.5px ' + (how === 'heard' ? 'solid' : 'dotted') + ' var(--dim);left:' + pct(s.start) + ';width:max(4px,calc(' + pct(s.end - s.start) + ' - 1px))' });
            continue;
          }
          const last = runs[runs.length - 1];
          if (last && s.start - last[1] < 1) last[1] = s.end; else runs.push([s.start, s.end]);
        }
        out.push({ key: 'p:' + id, label: shortName(personName(id, cast)), person: cast.get(id) || null, labelStyle: lab(14), trackStyle: trk(14), bars: [...ticks, ...runs.map((b) => ({ t: '', s: 'position:absolute;top:3px;bottom:3px;border-radius:2px;background:var(--dim);left:' + pct(b[0]) + ';width:' + pct(b[1] - b[0]) }))] });
      }
    }

    for (const g of SIGNALS) {
      const bars = signals.filter((x) => x.signal === g).map((x) => ({ t: '', s: 'position:absolute;top:0;bottom:0;background:var(--faint);left:' + pct(x.start) + ';width:' + pct(x.end - x.start) }));
      if (bars.length) out.push({ key: 's:' + g, label: g, labelStyle: lab(8, ';font:400 10px DM Mono,monospace;color:var(--faint)'), trackStyle: trk(8), bars });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [D, scenes, signals, cast, tagsOn, facesOn, facesStep, selected, z]);

  // After zooming, bring the playhead back into view.
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const inner = el.firstElementChild as HTMLElement | null;
    if (!inner) return;
    el.scrollLeft = Math.max(0, (at / D) * inner.offsetWidth - el.clientWidth / 2);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [z]);

  const seek = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    onSeek(Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * D);
  };

  const zoomNames = [episode ? 'Whole episode' : 'Whole film', '2x', '4x', '8x'];
  return (
    <section aria-label="Timeline" className="box" style={css('padding: 16px 18px 12px')}>
      <div style={css('display: flex; align-items: center; flex-wrap: wrap; gap: 8px 16px; padding-bottom: 12px')}>
        <h2 className="h2" style={{ flex: '1 1 160px' }}>Timeline</h2>
        <span style={css('display: inline-flex; align-items: center; gap: 14px; font-size: 12px; color: var(--dim)')}>
          <span style={css('display: inline-flex; align-items: center; gap: 6px')}><span style={css('width: 22px; height: 9px; border-radius: 2px; background: var(--dim)')} />Accepted</span>
          <span style={css('display: inline-flex; align-items: center; gap: 6px')}><span style={css('width: 22px; height: 9px; border-radius: 2px; border: 1.5px dashed var(--dim); box-sizing: border-box')} />Proposed</span>
          {facesOn ? <span style={css('display: inline-flex; align-items: center; gap: 6px')} title="A person heard speaking but not seen"><span style={css('width: 12px; height: 9px; border-radius: 2px; border: 1.5px solid var(--dim); box-sizing: border-box')} />Heard</span> : null}
          {facesOn ? <span style={css('display: inline-flex; align-items: center; gap: 6px')} title="A person only named in the dialogue"><span style={css('width: 12px; height: 9px; border-radius: 2px; border: 1.5px dotted var(--dim); box-sizing: border-box')} />Named</span> : null}
        </span>
        <div style={css('display: inline-flex; align-items: center; gap: 6px')}>
          <button type="button" className="btn sm" aria-label="Zoom out" disabled={zi === 0} onClick={() => setZi(Math.max(0, zi - 1))}>−</button>
          <span className="mono" style={css('min-width: 86px; text-align: center; font-size: 12px')}>{zoomNames[zi]}</span>
          <button type="button" className="btn sm" aria-label="Zoom in" disabled={zi === ZOOMS.length - 1} onClick={() => setZi(Math.min(ZOOMS.length - 1, zi + 1))}>+</button>
        </div>
      </div>
      <div className="lanes">
        <div className="ll" aria-hidden="true">
          {lanes.map((l) => (
            <div key={l.key} style={css(l.labelStyle)} title={l.person ? `${l.person.character} (${l.person.actor})` : undefined}>
              {l.key.startsWith('p:') ? <Avatar name={l.label} photo={l.person?.photo} size={14} /> : null}
              {l.label}
            </div>
          ))}
        </div>
        <div className="lt" ref={scroller}>
          <div onClick={seek} style={css('position:relative;display:flex;flex-direction:column;gap:6px;cursor:pointer;min-width:720px;width:' + z * 100 + '%')}
            role="slider" aria-label="Playhead" aria-valuemin={0} aria-valuemax={Math.round(D)} aria-valuenow={Math.round(at)} tabIndex={0}
            onKeyDown={(e) => {
              // Arrow keys step through scenes, like clicking the next one.
              if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
              e.preventDefault();
              const i = scenes.findIndex((s) => s.n === sel?.n);
              const next = scenes[Math.min(scenes.length - 1, Math.max(0, i + (e.key === 'ArrowRight' ? 1 : -1)))];
              if (next) onSeek(next.start);
            }}>
            {lanes.map((l) => (
              <div key={l.key} style={css(l.trackStyle)}>
                {l.bars.map((b, i) => <span key={i} style={css(b.s)}>{b.t}</span>)}
              </div>
            ))}
            {cutoff !== null && cutoff < D ? (
              <span title="After the point the story is stopped at" style={css('position:absolute;top:14px;bottom:0;right:0;pointer-events:none;border-left:2px dashed var(--accent);background:repeating-linear-gradient(135deg,color-mix(in srgb,var(--bg) 70%,transparent) 0 6px,color-mix(in srgb,var(--bg) 45%,transparent) 6px 12px);left:' + pct(cutoff))} />
            ) : null}
            <span style={css('position:absolute;top:14px;bottom:0;width:2px;margin-left:-1px;background:var(--text);pointer-events:none;left:' + pct(at))} />
          </div>
        </div>
      </div>
    </section>
  );
}
