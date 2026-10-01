/**
 * Panel: ayrıntının açıldığı yer (§7.3, §7.4).
 *
 *   ≥ 1024 px  sağdan 440 px çekmece; listenin ÜSTÜNE biner, sayfa yeniden akmaz
 *   768–1023   alttan yarım ekran
 *   < 768      tam ekran (iç içe kaydırma yok; yalnız panelin gövdesi kayar)
 *
 * Esc, ✕, perdeye dokunmak ve (dokunmatikte) tutamaçtan aşağı çekmek kapatır.
 * `kilitli` iken (kaydediliyor) hiçbiri kapatmaz. `alt` panelin altına yapışan
 * eylem alanıdır — birincil düğme orada, başparmak bölgesinde durur.
 *
 * `perdesiz`: masaüstünde liste açık kalır ve başka satıra tıklanabilir
 * (İşler panosundaki iş çekmecesi gibi). Telefonda panel yine tam ekrandır.
 */

import { useEffect, useId, useRef, useState, type ReactNode, type TouchEvent } from 'react';
import { createPortal } from 'react-dom';
import './bilesen.css';

export function Panel({
  acik,
  kapat,
  baslik,
  altBaslik,
  children,
  alt,
  kilitli = false,
  perdesiz = false,
  genislik = 440,
  basSag,
}: {
  acik: boolean;
  kapat: () => void;
  baslik: ReactNode;
  altBaslik?: ReactNode;
  children: ReactNode;
  /** Alta yapışan eylem alanı (Kaydet · Vazgeç). */
  alt?: ReactNode;
  kilitli?: boolean;
  perdesiz?: boolean;
  /** Masaüstü genişliği (px). */
  genislik?: number;
  /** Başlığın sağında ✕'ten önce duran küçük eylem ("…" menüsü gibi). */
  basSag?: ReactNode;
}) {
  const kimlik = useId();
  const kutu = useRef<HTMLDivElement>(null);
  const [cekme, setCekme] = useState(0);
  const cekmeBas = useRef<number | null>(null);

  /* Esc ile kapanır; açıkken arka sayfa kaymaz; kapanınca odak geri döner. */
  useEffect(() => {
    if (!acik) return;
    const onceki = document.activeElement as HTMLElement | null;
    const esc = (o: KeyboardEvent) => {
      if (o.key === 'Escape' && !kilitli) {
        o.stopPropagation();
        kapat();
      }
    };
    document.addEventListener('keydown', esc);
    const tasma = document.body.style.overflow;
    if (!perdesiz || window.innerWidth < 1024) document.body.style.overflow = 'hidden';
    window.setTimeout(() => kutu.current?.focus({ preventScroll: true }), 30);
    return () => {
      document.removeEventListener('keydown', esc);
      document.body.style.overflow = tasma;
      onceki?.focus?.({ preventScroll: true });
    };
  }, [acik, kapat, kilitli, perdesiz]);

  if (!acik) return null;

  const dokunBasladi = (o: TouchEvent) => {
    cekmeBas.current = o.touches[0]?.clientY ?? null;
  };
  const dokunKaydi = (o: TouchEvent) => {
    if (cekmeBas.current === null || kilitli) return;
    const fark = (o.touches[0]?.clientY ?? 0) - cekmeBas.current;
    setCekme(Math.max(0, fark));
  };
  const dokunBitti = () => {
    if (cekme > 90 && !kilitli) kapat();
    cekmeBas.current = null;
    setCekme(0);
  };

  return createPortal(
    <>
      <div
        className={`o-panel-perde${perdesiz ? ' perdesiz' : ''}`}
        onClick={kilitli ? undefined : kapat}
        aria-hidden="true"
      />
      <div
        ref={kutu}
        className={`o-panel${perdesiz ? ' perdesiz' : ''}`}
        role="dialog"
        aria-modal={perdesiz ? undefined : true}
        aria-labelledby={`${kimlik}-b`}
        tabIndex={-1}
        style={{
          ['--panel-genislik' as string]: `${genislik}px`,
          ...(cekme ? { transform: `translateY(${cekme}px)`, transition: 'none' } : null),
        }}
      >
        <div
          className="o-panel-tutamac"
          onTouchStart={dokunBasladi}
          onTouchMove={dokunKaydi}
          onTouchEnd={dokunBitti}
          aria-hidden="true"
        >
          <span />
        </div>
        <header className="o-panel-bas">
          <div className="metin">
            <h2 id={`${kimlik}-b`}>{baslik}</h2>
            {altBaslik ? <p>{altBaslik}</p> : null}
          </div>
          {basSag}
          <button type="button" className="o-panel-kapat" onClick={kapat} disabled={kilitli} aria-label="Kapat">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            </svg>
          </button>
        </header>
        <div className="o-panel-govde">{children}</div>
        {alt ? <footer className="o-panel-alt">{alt}</footer> : null}
      </div>
    </>,
    document.body,
  );
}
