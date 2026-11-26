// The sidebar and page frame from the design (every board shares it).
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { NavLink, Outlet } from 'react-router';
import { api } from '../api/client';
import type { Status } from '../api/types';

const ICONS: Record<string, ReactNode> = {
  library: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M8 4v16M16 4v16M3 9h5M3 15h5M16 9h5M16 15h5" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-4-4" /></>,
  review: <><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></>,
  tags: <><path d="M3 12V4h8l10 10-8 8z" /><circle cx="7.5" cy="8.5" r="1.2" /></>,
  activity: <path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5" />,
  api: <path d="M8 8l-5 4 5 4M16 8l5 4-5 4M13.5 5l-3 14" />,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" /></>,
};

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name]}
    </svg>
  );
}

export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={(size * 19) / 26} height={size} viewBox="0 0 22 31" aria-hidden="true">
      <path fill="#f5d547" d="M5 0h11.2c.5 0 1 .2 1.3.5l4 4c.3.4.5.8.5 1.3v22.5c0 1.5-1.8 2.3-2.9 1.3L11 22.2l-8.1 7.4C1.8 30.6 0 29.8 0 28.3V5a5 5 0 0 1 5-5z" />
    </svg>
  );
}

type Theme = 'dark' | 'light';
interface AppCtx {
  status: Status | null;
  refreshStatus: () => void;
  theme: Theme;
  themePref: Theme | 'system';
  setTheme: (t: Theme | 'system') => void;
}
const Ctx = createContext<AppCtx>({ status: null, refreshStatus: () => undefined, theme: 'dark', themePref: 'dark', setTheme: () => undefined });
/** Status (review count, Plex, setup), refreshed every 15 s, and the theme. */
export const useApp = () => useContext(Ctx);

function systemTheme(): Theme {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function AppFrame({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [pref, setPref] = useState<Theme | 'system'>(() => (localStorage.getItem('marcarr.theme') as Theme | 'system') || 'dark');
  const theme: Theme = pref === 'system' ? systemTheme() : pref;
  const refreshStatus = () => { api.status().then(setStatus, () => undefined); };
  useEffect(() => {
    refreshStatus();
    const id = setInterval(refreshStatus, 15000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => { document.body.style.background = theme === 'dark' ? '#171b20' : '#f7f6ef'; }, [theme]);
  const setTheme = (t: Theme | 'system') => { localStorage.setItem('marcarr.theme', t); setPref(t); };
  return <Ctx.Provider value={{ status, refreshStatus, theme, themePref: pref, setTheme }}>{children}</Ctx.Provider>;
}

const NAV: [string, string, string][] = [
  ['/', 'library', 'Library'],
  ['/search', 'search', 'Search'],
  ['/review', 'review', 'Review'],
  ['/tags', 'tags', 'Tags'],
  ['/activity', 'activity', 'Activity'],
  ['/api', 'api', 'API'],
  ['/settings', 'settings', 'Settings'],
];

export function Shell() {
  const { status, theme } = useApp();
  const plex = status?.plex || 'not set';
  return (
    <div className={'app t-' + theme}>
      <nav className="side" aria-label="Marcarr">
        <NavLink to="/" aria-label="Marcarr" style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 10px 20px', textDecoration: 'none', color: '#f7f6ef' }}>
          <Logo /><span className="hd word" style={{ fontSize: 22, fontWeight: 700 }}>Marcarr</span>
        </NavLink>
        {NAV.map(([to, icon, name]) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => 'nav' + (isActive ? ' on' : '')}>
            <Icon name={icon} /><span className="t">{name}</span>
            {icon === 'review' && status && status.review > 0 ? <span className="n">{status.review}</span> : null}
          </NavLink>
        ))}
        <div className="foot" style={{ marginTop: 'auto', padding: '24px 12px 0', display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12, color: '#929a9d' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, color: '#bcc2c5' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: plex === 'connected' ? '#5ec26a' : plex === 'failing' ? '#f0706a' : '#929a9d' }} />
            {plex === 'connected' ? 'Plex connected' : plex === 'failing' ? 'Plex not answering' : 'Plex not set up'}
          </span>
          <span>Know what&apos;s in every scene.</span>
        </div>
      </nav>
      <main className="main">
        <div className="wrap">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

/** Pages with no sidebar (first run). */
export function Bare({ children }: { children: ReactNode }) {
  const { theme } = useApp();
  return <div className={'app t-' + theme} style={{ display: 'block' }}>{children}</div>;
}
