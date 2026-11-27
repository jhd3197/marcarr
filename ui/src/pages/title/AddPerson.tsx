// Add a person to a title by hand: a home video has no Plex or TMDB cast, and a
// catalogue can miss someone. The photo is what Marcarr matches faces against.
import { useRef, useState } from 'react';
import { api } from '../../api/client';
import { css } from '../../components/kit';
import { useToast } from '../../lib/toast';

const FIELD = 'display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--dim)';

export function AddPerson({ title, empty, onDone }: { title: string; empty: boolean; onDone: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [photo, setPhoto] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const file = useRef<HTMLInputElement>(null);

  if (!open) {
    return (
      <button type="button" className="linkish" onClick={() => setOpen(true)}>
        {empty ? 'No cast for this title. Add the people in it' : 'Add a person'}
      </button>
    );
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    try {
      const p = await api.addCast(title, { name: name.trim() });
      if (photo) await api.setPersonPhoto(p.id, photo);
      toast(photo ? `${p.character} added` : `${p.character} added. Without a photo their face cannot be found`);
      setName('');
      setPhoto(null);
      if (file.current) file.current.value = '';
      onDone();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} style={css('display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px')}>
      <label style={css(FIELD)}>Name
        <input className="inp" autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Maria" style={{ width: 170 }} />
      </label>
      <label style={css(FIELD)}>Photo of their face
        <input ref={file} type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] || null)} style={{ fontSize: 12, width: 230 }} />
      </label>
      <button type="submit" className="btn" disabled={!name.trim() || saving}>{saving ? 'Adding' : 'Add'}</button>
      <button type="button" className="linkish" onClick={() => setOpen(false)}>Done</button>
    </form>
  );
}
