// Small building blocks that every page shares, drawn as in the design
// (docs/design/components). Inline styles are copied from the design's logic.
import type { CSSProperties, ReactNode } from 'react';
import type { Family, StateLine, Step, StepState, TagStatus } from '../api/types';
import { STEPS } from '../api/types';
import { initials } from '../lib/format';

// -- tag chips --------------------------------------------------------------------
export const famVar = (family: Family | string | null | undefined) => `var(--f-${family || 'place'})`;

export function chipStyle(family: Family | string | null | undefined, status: TagStatus): CSSProperties {
  const base: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', height: 24, padding: '0 9px 0 7px', borderRadius: 6,
    boxSizing: 'border-box', fontSize: 12, fontWeight: family === 'mood' ? 500 : 600, whiteSpace: 'nowrap',
  };
  if (status === 'proposed') return { ...base, border: `1.5px dashed ${famVar(family)}`, color: 'var(--text)' };
  if (status === 'rejected') return { ...base, border: '1px solid var(--line)', color: 'var(--faint)', textDecoration: 'line-through' };
  return { ...base, borderLeft: `4px solid ${famVar(family)}`, background: 'var(--raised)', color: 'var(--text)' };
}

/** A tag: solid with a family stripe when kept, dashed when proposed, struck when dropped. */
export function Chip({ name, family, status, onClick, title }: { name: string; family: Family | string | null; status: TagStatus; onClick?: () => void; title?: string }) {
  const style = chipStyle(family, status);
  if (onClick) {
    return <button type="button" style={{ ...style, cursor: 'pointer', background: style.background || 'transparent', fontFamily: 'inherit' }} onClick={onClick} title={title}>{name}</button>;
  }
  return <span style={style} title={title}>{name}</span>;
}

export function Chips({ tags, max }: { tags: { id?: string; tag?: string; name: string; family: Family | string | null; status: TagStatus }[]; max?: number }) {
  const shown = max ? tags.slice(0, max) : tags;
  return (
    <span style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
      {shown.map((t, i) => <Chip key={(t.id || t.tag || t.name) + i} name={t.name} family={t.family} status={t.status} />)}
      {max && tags.length > max ? <span style={{ fontSize: 12, color: 'var(--faint)', alignSelf: 'center' }}>+{tags.length - max}</span> : null}
    </span>
  );
}

// -- the seven steps ---------------------------------------------------------------
export const STATE_TEXT: Record<StepState, string> = {
  done: 'Done', rerun: 'Needs a rerun', failed: 'Failed', run: 'Running', queued: 'Waiting', notrun: 'Not run', none: 'Not supported here', off: 'Off',
};
const GLYPH: Partial<Record<StepState, string>> = { done: '✓', rerun: '↻', failed: '×', none: '/', off: '–' };
const CELL: Record<StepState, string> = {
  done: 'background:var(--ok);color:var(--bg)',
  rerun: 'border:2px solid var(--warn);color:var(--warn)',
  failed: 'background:var(--bad);color:var(--bg)',
  run: 'background:linear-gradient(90deg,var(--accent) 55%,var(--border) 55%)',
  queued: 'border:1.5px dashed var(--accent)',
  notrun: 'border:1.5px dashed var(--faint)',
  none: 'background:var(--raised);color:var(--faint)',
  off: 'border:1px solid var(--border);color:var(--faint)',
};

/** "a:b;c:d" -> React style object (lets pages reuse the design's inline strings). */
export function css(s: string): CSSProperties {
  const out: Record<string, string> = {};
  for (const part of s.split(';')) {
    const i = part.indexOf(':');
    if (i < 0) continue;
    const k = part.slice(0, i).trim();
    if (!k) continue;
    const key = k.startsWith('--') ? k : k.replace(/-([a-z])/g, (_m, c: string) => c.toUpperCase());
    out[key] = part.slice(i + 1).trim();
  }
  return out as CSSProperties;
}

export function StepCell({ step, state, progress }: { step: Step; state: StepState; progress?: number | null }) {
  let style = 'flex:none;display:inline-flex;align-items:center;justify-content:center;width:30px;height:18px;border-radius:4px;box-sizing:border-box;font:700 12px DM Mono,monospace;' + CELL[state];
  if (state === 'run' && progress != null) {
    const p = Math.round(progress * 100);
    style = style.replace('55%,var(--border) 55%', `${p}%,var(--border) ${p}%`);
  }
  return <span role="img" aria-label={`${step}: ${STATE_TEXT[state]}`} title={`${step}: ${STATE_TEXT[state]}`} style={css(style)}>{GLYPH[state] || ''}</span>;
}

export function StepRow({ steps, gap = 4 }: { steps: Record<Step, StepState> | null; gap?: number }) {
  if (!steps) return null;
  return <span style={{ display: 'inline-flex', gap }}>{STEPS.map((s) => <StepCell key={s} step={s} state={steps[s]} />)}</span>;
}

export const DOT: Record<StateLine['kind'], string> = {
  done: 'var(--ok)', run: 'var(--accent)', notrun: 'var(--faint)', failed: 'var(--bad)', rerun: 'var(--warn)', queued: 'var(--accent)',
};

export function Dot({ kind, size = 8 }: { kind: StateLine['kind']; size?: number }) {
  return <span style={{ flex: 'none', width: size, height: size, borderRadius: '50%', background: DOT[kind] }} />;
}

export function StateText({ state }: { state: StateLine }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, fontWeight: 600 }}>
      <Dot kind={state.kind} />{state.text}
    </span>
  );
}

// -- people ------------------------------------------------------------------------
export function Avatar({ name, photo, size = 24 }: { name: string; photo?: string | null; size?: number }) {
  const style: CSSProperties = {
    flex: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: size, height: size,
    borderRadius: '50%', font: `700 ${Math.round(size * 0.45)}px DM Sans,sans-serif`, color: 'var(--text)',
    background: photo ? `var(--hover) url("${photo}") center/cover` : 'var(--hover)',
  };
  return <span style={style} aria-hidden="true">{photo ? '' : initials(name)}</span>;
}

// -- controls ----------------------------------------------------------------------
export function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" className="sw" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}>
      <i />
    </button>
  );
}

export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}>{text}</button>
      ))}
    </div>
  );
}

export function Pills<T extends string>({ value, options, onChange }: { value: T; options: { key: T; name: string; n?: number }[]; onChange: (v: T) => void }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {options.map((o) => (
        <button key={o.key} type="button" className={'pill' + (value === o.key ? ' on' : '')} aria-pressed={value === o.key} onClick={() => onChange(o.key)}>
          {o.name}{o.n !== undefined ? <em>{o.n}</em> : null}
        </button>
      ))}
    </div>
  );
}

export function Crumbs({ items }: { items: { name: string; href?: string }[] }) {
  return (
    <nav className="crumb" aria-label="Breadcrumb">
      {items.map((c, i) => (
        <span key={i} style={{ display: 'inline-flex', gap: 8 }}>
          {i > 0 ? <span aria-hidden="true">/</span> : null}
          {c.href ? <a href={c.href}>{c.name}</a> : <span>{c.name}</span>}
        </span>
      ))}
    </nav>
  );
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <div className="loading">{text}</div>;
}

export function ErrorBox({ error, retry }: { error: string; retry?: () => void }) {
  return (
    <div className="err-box">
      {error} {retry ? <button type="button" className="btn sm" style={{ marginLeft: 10 }} onClick={retry}>Try again</button> : null}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

/** A still from a video, black while loading; `blur` hides spoilers. */
export function Still({ src, alt, style, blur, onClick }: { src: string; alt?: string; style?: CSSProperties; blur?: boolean; onClick?: () => void }) {
  return (
    <span className="still" style={{ position: 'relative', overflow: 'hidden', ...style }} onClick={onClick}>
      <img src={src} alt={alt || ''} loading="lazy" style={{ display: 'block', width: '100%', height: '100%', objectFit: 'cover', ...(blur ? { filter: 'blur(9px)', transform: 'scale(1.25)' } : {}) }} />
    </span>
  );
}
