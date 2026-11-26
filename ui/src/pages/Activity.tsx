// Activity (docs/design/activity): the queue, the seven steps of each video, time and AI cost.
import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { api } from '../api/client';
import type { ActivityRow, Step, StepState } from '../api/types';
import { STEPS } from '../api/types';
import { ErrorBox, Loading, Pills, STATE_TEXT, StepCell } from '../components/kit';
import { useApi } from '../lib/hooks';
import { length, money, plural, took } from '../lib/format';
import { useToast } from '../lib/toast';
import { errText } from './settings/util';
import './Activity.css';

type Filter = 'all' | 'running' | 'waiting' | 'notstarted' | 'failed' | 'done';
const FILTERS: [Filter, string][] = [['all', 'All'], ['running', 'Running'], ['waiting', 'In the queue'], ['notstarted', 'Not started'], ['failed', 'Needs a look'], ['done', 'Done']];

/** The one button a row offers, from its step states. */
function action(r: ActivityRow): { label: string; steps?: Step[] } | null {
  const states = STEPS.map((s) => r.steps[s]);
  if (states.includes('run') || states.includes('queued') || r.state.kind === 'queued' || r.state.kind === 'run') return null;
  const failed = STEPS.filter((s) => r.steps[s] === 'failed');
  if (failed.length) return { label: failed.length === 1 ? 'Rerun ' + failed[0] : `Rerun ${failed.length} steps`, steps: failed };
  const rerun = STEPS.filter((s) => r.steps[s] === 'rerun');
  if (rerun.length) return { label: rerun.length === 1 ? 'Rerun ' + rerun[0] : `Rerun ${rerun.length} steps`, steps: rerun };
  const notrun = STEPS.filter((s) => r.steps[s] === 'notrun');
  if (notrun.length === STEPS.filter((s) => r.steps[s] !== 'none' && r.steps[s] !== 'off').length && notrun.length) return { label: 'Analyse' };
  if (notrun.length) return { label: notrun.length === 1 ? 'Run ' + notrun[0] : `Run ${notrun.length} steps`, steps: notrun };
  return null;
}

function stateColor(r: ActivityRow) {
  switch (r.state.kind) {
    case 'failed': return 'var(--bad)';
    case 'rerun': return 'var(--warn)';
    case 'run': return 'var(--text)';
    default: return 'var(--dim)';
  }
}

const LEGEND: StepState[] = ['done', 'run', 'rerun', 'failed', 'notrun', 'none', 'off'];

export default function Activity() {
  const toast = useToast();
  const [filter, setFilter] = useState<Filter>('all');
  const [open, setOpen] = useState('');
  const [did, setDid] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState('');
  const act = useApi(() => api.activity(filter === 'all' ? undefined : filter), [filter], 3000);
  const data = act.data;

  // A queued action shows "Queued" until fresh data arrives.
  useEffect(() => { setDid({}); }, [data]);

  const togglePause = async () => {
    if (!data) return;
    setBusy('pause');
    try { act.set(await (data.paused ? api.resume() : api.pause())); } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const analyseLeft = async () => {
    setBusy('left');
    try {
      const r = await api.analyseLeft();
      toast(r.queued ? `${plural(r.queued, 'video')} queued` : 'Nothing left to analyse');
      act.reload();
    } catch (e) { toast(errText(e), true); }
    setBusy('');
  };
  const run = async (video: string, steps?: Step[]) => {
    try {
      await api.runVideo(video, steps);
      setDid((d) => ({ ...d, [video]: true }));
      toast(steps && steps.length === 1 ? `${steps[0]} queued` : 'Queued');
    } catch (e) { toast(errText(e), true); }
  };

  if (!data) {
    return (
      <div className="pg-activity" style={{ display: 'contents' }}>
        <h1 className="h1">Activity</h1>
        {act.error ? <ErrorBox error={act.error} retry={act.reload} /> : <Loading />}
      </div>
    );
  }

  const running = data.running;
  const stepPct = running && running.progress != null ? Math.round(running.progress * 100) : 0;
  const m = data.month;
  const aiPct = m.ai_limit > 0 ? Math.min(100, Math.round((m.ai_cost / m.ai_limit) * 100)) : 0;
  const counts = data.counts || {};

  return (
    <div className="pg-activity" style={{ display: 'contents' }}>
      <header style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px 14px' }}>
        <h1 className="h1" style={{ flex: '1 1 200px' }}>Activity</h1>
        <button type="button" className="btn" disabled={busy === 'pause'} onClick={togglePause}>{data.paused ? 'Resume' : 'Pause'}</button>
        <button type="button" className="btn pri" disabled={busy === 'left'} onClick={analyseLeft}>Analyse what is left</button>
      </header>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
        <div className="box stat" style={{ flexGrow: 2 }}>
          <div className="lab">Running now</div>
          {running ? (
            <>
              <div className="big" style={{ marginTop: 6 }}>{running.title_name}</div>
              <div style={{ marginTop: 4, fontSize: 13, color: 'var(--dim)' }}>
                <span className="mono">{running.step}</span>, step {STEPS.indexOf(running.step) + 1} of 7
                {running.eta_seconds ? ` · about ${took(running.eta_seconds)} left on this step` : ''}
              </div>
              <div role="progressbar" aria-label="Progress of the running step" aria-valuemin={0} aria-valuemax={100} aria-valuenow={stepPct} style={{ marginTop: 10, height: 8, borderRadius: 4, background: 'var(--raised)', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: stepPct + '%', background: 'var(--accent)' }} />
              </div>
            </>
          ) : (
            <>
              <div className="big" style={{ marginTop: 6 }}>{data.paused ? 'Paused' : 'Nothing'}</div>
              <div style={{ marginTop: 4, fontSize: 13, color: 'var(--dim)' }}>{data.paused ? 'Resume to carry on with the queue' : data.left.videos ? 'Waiting for the next video' : 'Everything is analysed'}</div>
            </>
          )}
        </div>
        <div className="box stat">
          <div className="lab">Time left</div>
          <div className="big" style={{ marginTop: 6 }}>{data.left.eta_seconds ? 'about ' + length(data.left.eta_seconds) : data.left.videos ? 'Unknown yet' : 'None'}</div>
          <div style={{ marginTop: 4, fontSize: 13, color: 'var(--dim)' }}>{plural(data.left.videos, 'video')} still to finish</div>
        </div>
        <div className="box stat">
          <div className="lab">Time spent this month</div>
          <div className="big" style={{ marginTop: 6 }}>{length(m.seconds) || '0m'}</div>
          <div style={{ marginTop: 4, fontSize: 13, color: 'var(--dim)' }}>{m.per_film_seconds ? `about ${took(m.per_film_seconds)} a film` : 'No film finished yet'}</div>
        </div>
        <div className="box stat">
          <div className="lab">AI cost this month</div>
          <div className="big" style={{ marginTop: 6 }}>{money(m.ai_cost)} <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--dim)' }}>of {money(m.ai_limit)}</span></div>
          <div role="progressbar" aria-label="Monthly AI limit used" aria-valuemin={0} aria-valuemax={100} aria-valuenow={aiPct} style={{ marginTop: 10, height: 8, borderRadius: 4, background: 'var(--raised)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: aiPct + '%', background: aiPct >= 100 ? 'var(--bad)' : 'var(--text)' }} />
          </div>
          <div style={{ marginTop: 6, fontSize: 13, color: 'var(--dim)' }}>{m.per_film_cost != null ? `about ${money(m.per_film_cost)} a film · ` : ''}<Link to="/settings?tab=ai">change the limit</Link></div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <Pills value={filter} onChange={(f) => { setFilter(f); setOpen(''); }} options={FILTERS.map(([key, name]) => ({ key, name, n: counts[key] ?? (key === 'failed' ? counts.look : undefined) ?? 0 }))} />
        {counts.not_analysed ? <span style={{ fontSize: 12.5, color: 'var(--dim)' }}>{plural(counts.not_analysed, 'more video')} not analysed yet: start one from its page in the <Link to="/">Library</Link>.</span> : null}
      </div>

      <div className="box" style={{ padding: '14px 10px 4px', overflowX: 'auto' }}>
        <div style={{ minWidth: 1100 }}>
          <div className="ar h">
            <span className="lab">Video</span>
            {STEPS.map((s) => <span key={s} className="th">{s}</span>)}
            <span className="lab" style={{ textAlign: 'right' }}>Time</span><span className="lab" style={{ textAlign: 'right' }}>AI cost</span><span className="lab">State</span><span />
          </div>
          {data.rows.length === 0 ? <div style={{ padding: '18px 8px', borderTop: '1px solid var(--line)', fontSize: 13, color: 'var(--dim)' }}>No videos here.</div> : null}
          {data.rows.map((r) => {
            const isOpen = open === r.video;
            const queued = !!did[r.video];
            const a = queued ? null : action(r);
            const untouched = !r.seconds && !r.ai_cost && STEPS.every((s) => r.steps[s] !== 'done');
            return (
              <div key={r.video}>
                <div className="ar">
                  <span style={{ minWidth: 0 }}>
                    <button type="button" className="rowb" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? '' : r.video)}>{r.title_name}</button>
                    <span className="mono" style={{ display: 'block', fontSize: 11, color: 'var(--faint)' }}>{r.meta}</span>
                  </span>
                  {STEPS.map((s) => <span key={s} style={{ textAlign: 'center' }}><StepCell step={s} state={r.steps[s]} progress={r.step_info?.[s]?.progress} /></span>)}
                  <span className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{untouched ? '' : took(r.seconds)}</span>
                  <span className="mono" style={{ textAlign: 'right', fontSize: 13 }}>{untouched ? '' : money(r.ai_cost)}</span>
                  <span style={{ fontSize: 12.5, fontWeight: r.state.kind === 'done' ? 500 : 600, color: queued ? 'var(--dim)' : stateColor(r) }}>{queued ? 'Queued' : r.state.text}</span>
                  <span style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    {a ? <button type="button" className="btn sm" onClick={() => run(r.video, a.steps)}>{a.label}</button> : null}
                  </span>
                </div>
                {isOpen ? (
                  <div style={{ padding: '4px 8px 14px 24px', borderTop: '1px dashed var(--line)' }}>
                    {STEPS.map((s) => {
                      const info = r.step_info?.[s];
                      const st = info?.state || r.steps[s];
                      const cost = info && info.ai_cost > 0 ? money(info.ai_cost) : '';
                      return (
                        <div className="st" key={s} title={info?.detail || undefined}>
                          <span className="mono" style={{ fontWeight: 500 }}>{s}</span>
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}><StepCell step={s} state={st} progress={info?.progress} />{STATE_TEXT[st]}</span>
                          <span className="mono" style={{ textAlign: 'right' }}>{info?.seconds != null && st !== 'notrun' ? took(info.seconds) : ''}</span>
                          <span className="mono" style={{ color: 'var(--dim)' }}>{cost}{cost && info?.detail ? ': ' : ''}{info?.detail || ''}</span>
                          <span>{st !== 'none' && st !== 'off' && st !== 'run' && st !== 'queued' ? <button type="button" className="btn sm ghost" onClick={() => run(r.video, [s])}>Rerun</button> : null}</span>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 20px', fontSize: 12, color: 'var(--dim)' }}>
        {LEGEND.map((k) => <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}><span aria-hidden="true" style={{ display: 'inline-flex' }}><StepCell step="shots" state={k} /></span>{STATE_TEXT[k]}</span>)}
      </div>
    </div>
  );
}
