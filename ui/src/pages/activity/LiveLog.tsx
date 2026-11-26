// The live log: what each step is doing right now, terminal-style, so a long
// step is seen moving (or seen stuck). Polls /activity/log with ?after=.
import { useEffect, useRef, useState } from 'react';
import { raw } from '../../api/client';

interface LogLine {
  n: number;
  at: string;
  video: string;
  step: string;
  text: string;
  pct: number | null;
}

const KEEP = 400;

export default function LiveLog({ video, names, height = 260, title = 'Live log' }: {
  video?: string;
  names: Record<string, string>; // video id -> title, for the all-videos log
  height?: number;
  title?: string;
}) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [error, setError] = useState('');
  const last = useRef(0);
  const box = useRef<HTMLDivElement>(null);
  const stick = useRef(true); // follow the newest line unless the person scrolled up

  useEffect(() => {
    last.current = 0;
    setLines([]);
    let live = true;
    const poll = async () => {
      try {
        const q = new URLSearchParams({ after: String(last.current) });
        if (video) q.set('video', video);
        const r = await raw.get<{ items: LogLine[]; last: number }>(`/activity/log?${q}`);
        if (!live) return;
        setError('');
        if (r.items.length) {
          last.current = r.last;
          setLines((xs) => [...xs, ...r.items].slice(-KEEP));
        }
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : String(e));
      }
    };
    poll();
    const id = setInterval(() => { if (document.visibilityState === 'visible') poll(); }, 1500);
    return () => { live = false; clearInterval(id); };
  }, [video]);

  useEffect(() => {
    const el = box.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [lines]);

  const onScroll = () => {
    const el = box.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
        <span className="lab">{title}</span>
        <span style={{ fontSize: 12, color: 'var(--faint)' }}>{error ? 'Not answering: ' + error : lines.length ? `${lines.length} lines, newest at the bottom` : 'Nothing yet: lines appear as soon as a step starts'}</span>
      </div>
      <div ref={box} onScroll={onScroll} role="log" aria-live="polite" aria-label={title}
        style={{ height, overflowY: 'auto', padding: '10px 12px', borderRadius: 10, background: '#0c0e11', border: '1px solid var(--line)', font: "12px/1.55 'DM Mono',ui-monospace,monospace", color: '#c9ced1' }}>
        {lines.map((l) => (
          <div key={l.n} style={{ display: 'flex', gap: 10, whiteSpace: 'pre-wrap' }}>
            <span style={{ color: '#6d767b', flex: 'none' }}>{l.at.slice(11, 19)}</span>
            {video ? null : <span style={{ color: '#9db4c8', flex: 'none', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{names[l.video] || l.video}</span>}
            <span style={{ color: '#f5d547', flex: 'none', width: 70 }}>{l.step}</span>
            <span style={{ color: '#7fd18b', flex: 'none', width: 48, textAlign: 'right' }}>{l.pct != null ? l.pct.toFixed(0) + '%' : ''}</span>
            <span style={{ color: /^failed/.test(l.text) ? '#f0706a' : undefined }}>{l.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
