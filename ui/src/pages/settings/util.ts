// Small helpers shared by the Settings, API and first-run pages.

/** Copy text to the clipboard; resolves false when the browser refuses. */
export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Plain http on a LAN address has no clipboard API: fall back to a hidden textarea.
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

/** "2 minutes ago", "yesterday", "Nov 3" */
export function ago(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (Number.isNaN(s)) return '';
  if (s < 60) return 'just now';
  if (s < 3600) {
    const m = Math.round(s / 60);
    return m === 1 ? 'a minute ago' : `${m} minutes ago`;
  }
  if (s < 86400) {
    const h = Math.round(s / 3600);
    return h === 1 ? 'an hour ago' : `${h} hours ago`;
  }
  if (s < 2 * 86400) return 'yesterday';
  if (s < 7 * 86400) return `${Math.round(s / 86400)} days ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));
