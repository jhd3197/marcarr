// Tags (docs/design/tags): every tag by family, how many kept scenes use it, and
// which ones are written to Plex as labels (the bookmark toggles that).
import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { api } from '../api/client';
import type { Vocab, VocabTag } from '../api/types';
import { ErrorBox, Loading } from '../components/kit';
import { useApi } from '../lib/hooks';
import { plural } from '../lib/format';
import { useToast } from '../lib/toast';
import { errText } from './settings/util';
import './Tags.css';

const searchHref = (t: VocabTag) => `/search?tags=${encodeURIComponent(t.id)}`;

export default function Tags() {
  const toast = useToast();
  const nav = useNavigate();
  const [used, setUsed] = useState(false);
  const vocab = useApi(() => api.vocab(), []);

  const toggleLabel = async (t: VocabTag) => {
    const v = vocab.data;
    if (!v) return;
    const flip = (doc: Vocab, label: boolean): Vocab => ({
      ...doc,
      families: doc.families.map((f) => ({ ...f, tags: f.tags.map((x) => (x.id === t.id ? { ...x, label } : x)) })),
    });
    vocab.set(flip(v, !t.label));
    try {
      const r = await api.setTagLabel(t.id, !t.label);
      toast(r.label ? `${t.name} is written to Plex as a label` : `${t.name} is no longer written to Plex`);
    } catch (e) {
      vocab.set(flip(v, t.label));
      toast(errText(e), true);
    }
  };

  const head = (
    <header style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px 16px' }}>
      <h1 className="h1" style={{ flex: '1 1 200px' }}>Tags</h1>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: 12.5, color: 'var(--dim)' }}><span className="bm" />Written to Plex as a label</span>
      <button type="button" role="switch" className="sw" aria-checked={used} aria-label="Only tags in use" onClick={() => setUsed(!used)}><i /></button>
      <span style={{ fontSize: 13 }}>Only tags in use</span>
    </header>
  );

  if (!vocab.data) {
    return <div className="pg-tags" style={{ display: 'contents' }}>{head}{vocab.error ? <ErrorBox error={vocab.error} retry={vocab.reload} /> : <Loading />}</div>;
  }
  const v = vocab.data;

  return (
    <div className="pg-tags" style={{ display: 'contents' }}>
      {head}

      {v.families.map((f) => {
        const tags = f.tags.filter((t) => !used || t.counts.accepted > 0);
        if (used && !tags.length) return null;
        return (
          <section key={f.family} className="box" aria-label={f.name} style={{ padding: '14px 16px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px 14px', padding: '0 2px 10px' }}>
              <span style={{ flex: 'none', width: 6, height: 22, borderRadius: 3, background: `var(--f-${f.family})` }} />
              <h2 className="h2">{f.name}</h2>
              <span className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>{plural(f.tags.length, 'tag')}</span>
              {f.subjective ? <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 10, border: '1px solid var(--border)', color: 'var(--dim)' }}>Subjective</span> : null}
              <div style={{ flex: 1 }} />
              {f.off ? <Link to="/settings?tab=tags" style={{ fontSize: 12.5 }}>Off in Settings</Link> : null}
            </div>
            <div className="tgrid" style={f.off ? { opacity: 0.45 } : undefined}>
              {tags.map((t) => {
                const n = t.counts.accepted;
                const extra = t.counts.proposed ? `, ${t.counts.proposed} waiting for review` : '';
                return (
                  <div key={t.id} className="tl" title={t.hint || undefined} onClick={() => nav(searchHref(t))}>
                    <Link to={searchHref(t)} onClick={(e) => e.stopPropagation()} style={n ? { fontWeight: 600 } : { color: 'var(--dim)' }}>{t.name}</Link>
                    <button type="button" className={'bm' + (t.label ? ' on' : '')} aria-pressed={t.label}
                      aria-label={t.label ? `Stop writing ${t.name} to Plex` : `Write ${t.name} to Plex as a label`}
                      title={t.label ? 'Written to Plex as a label' : 'Write to Plex as a label'}
                      onClick={(e) => { e.stopPropagation(); toggleLabel(t); }} />
                    <span className="c" title={`${plural(n, 'kept scene')}${extra}`}>{n}</span>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(360px, 100%), 1fr))', gap: 18 }}>
        <section className="box" aria-label="Marcarr's own tags" style={{ padding: '14px 18px 16px' }}>
          <h2 className="h2" style={{ paddingBottom: 8 }}>Marcarr&apos;s own</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {v.own.map((o) => (
              <span key={o.id} title={o.hint || undefined} style={{ display: 'inline-flex', alignItems: 'center', height: 24, padding: '0 9px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'var(--raised)', borderLeft: '4px solid var(--accent)' }}>{o.name}</span>
            ))}
          </div>
        </section>
        <section className="box" aria-label="Signals" style={{ padding: '14px 18px 16px' }}>
          <h2 className="h2" style={{ paddingBottom: 8 }}>Signals</h2>
          <div className="mono" style={{ fontSize: 12.5, lineHeight: 1.9, color: 'var(--dim)' }}>{v.signals.map((s) => s.name).join(' · ')}</div>
        </section>
      </div>
    </div>
  );
}
