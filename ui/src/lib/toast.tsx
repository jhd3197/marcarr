import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

type Toast = { id: number; text: string; bad: boolean };
const Ctx = createContext<(text: string, bad?: boolean) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, bad = false) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, text, bad }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), bad ? 6000 : 3000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toast-wrap" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={'toast' + (t.bad ? ' bad' : '')}>{t.text}</div>)}
      </div>
    </Ctx.Provider>
  );
}

/** toast('Saved'), toast('Could not save', true) */
export const useToast = () => useContext(Ctx);
