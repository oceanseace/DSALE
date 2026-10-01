/**
 * "…" menüsü: ikincil eylemler burada durur (§0.4 ilke 1 — ekranda tek
 * birincil eylem). Masaüstünde düğmenin altında küçük liste, telefonda alttan
 * eylem çekmecesi. Esc ve dışarı dokunmak kapatır; ok tuşlarıyla gezilir.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './bilesen.css';

export interface MenuOgesi {
  etiket: ReactNode;
  calistir: () => void;
  yikici?: boolean;
  kapali?: boolean;
  simge?: ReactNode;
}

export function DahaMenusu({
  ogeler,
  etiket = 'Diğer eylemler',
  dugme,
}: {
  ogeler: MenuOgesi[];
  etiket?: string;
  /** Varsayılan "…" yerine düğme içeriği. */
  dugme?: ReactNode;
}) {
  const [acik, setAcik] = useState(false);
  const [yer, setYer] = useState({ top: 0, right: 0 });
  const dugmeRef = useRef<HTMLButtonElement>(null);
  const liste = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!acik) return;
    const kapat = (o: MouseEvent | TouchEvent) => {
      const h = o.target as Node;
      if (liste.current?.contains(h) || dugmeRef.current?.contains(h)) return;
      setAcik(false);
    };
    const esc = (o: KeyboardEvent) => {
      if (o.key === 'Escape') {
        o.stopPropagation();
        setAcik(false);
        dugmeRef.current?.focus();
      }
      if (o.key === 'ArrowDown' || o.key === 'ArrowUp') {
        const dugmeler = [...(liste.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])];
        const i = dugmeler.indexOf(document.activeElement as HTMLButtonElement);
        const j = o.key === 'ArrowDown' ? (i + 1) % dugmeler.length : (i - 1 + dugmeler.length) % dugmeler.length;
        dugmeler[j]?.focus();
        o.preventDefault();
      }
    };
    document.addEventListener('mousedown', kapat);
    document.addEventListener('touchstart', kapat);
    document.addEventListener('keydown', esc, true);
    window.setTimeout(() => liste.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus(), 20);
    return () => {
      document.removeEventListener('mousedown', kapat);
      document.removeEventListener('touchstart', kapat);
      document.removeEventListener('keydown', esc, true);
    };
  }, [acik]);

  if (!ogeler.length) return null;

  const ac = () => {
    const r = dugmeRef.current?.getBoundingClientRect();
    if (r) setYer({ top: r.bottom + 6, right: Math.max(8, window.innerWidth - r.right) });
    setAcik((a) => !a);
  };

  return (
    <>
      <button
        ref={dugmeRef}
        type="button"
        className="o-daha"
        aria-label={etiket}
        aria-haspopup="menu"
        aria-expanded={acik}
        onClick={ac}
        title={etiket}
      >
        {dugme ?? (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <circle cx="5" cy="12" r="1.9" />
            <circle cx="12" cy="12" r="1.9" />
            <circle cx="19" cy="12" r="1.9" />
          </svg>
        )}
      </button>
      {acik
        ? createPortal(
            <>
              <div className="o-menu-perde" aria-hidden="true" />
              <div ref={liste} className="o-menu" role="menu" aria-label={etiket} style={{ top: yer.top, right: yer.right }}>
                {ogeler.map((o, i) => (
                  <button
                    key={i}
                    type="button"
                    role="menuitem"
                    className={o.yikici ? 'yikici' : undefined}
                    disabled={o.kapali}
                    onClick={() => {
                      setAcik(false);
                      o.calistir();
                    }}
                  >
                    {o.simge ? <span className="simge">{o.simge}</span> : null}
                    <span>{o.etiket}</span>
                  </button>
                ))}
                <button type="button" className="o-menu-vazgec" onClick={() => setAcik(false)}>
                  Vazgeç
                </button>
              </div>
            </>,
            document.body,
          )
        : null}
    </>
  );
}
