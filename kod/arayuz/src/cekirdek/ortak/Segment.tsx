/**
 * Segment: 2–5 seçenekten biri (iOS "segmented control").
 *
 * Sayaçlı olabilir ("Satış 2"). Dar ekranda sayfayı taşırmaz, kendi içinde
 * yatay kayar (§7.3, §6.14 P2). Ok tuşlarıyla seçenekler arasında gezilir.
 *
 * Seçili zemin tek bir "başparmak"tır: seçim değişince yaylı kayar (iOS).
 * Konumu ölçülür (--bp-x / --bp-g); ölçü gelene kadar seçili düğmenin kendi
 * zemini görünür, hareket istemeyen kullanıcıda kayma CSS ile kapanır.
 */

import { useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type ReactNode } from 'react';
import './bilesen.css';

export interface SegmentSecenegi<T extends string> {
  deger: T;
  etiket: ReactNode;
  /** Etiketin yanındaki küçük sayı (0 da yazılır; undefined yazılmaz). */
  sayi?: number;
  kapali?: boolean;
}

export function Segment<T extends string>({
  secenekler,
  deger,
  degisti,
  etiket,
  kucuk = false,
  tam = false,
}: {
  secenekler: Array<SegmentSecenegi<T>>;
  deger: T;
  degisti: (yeni: T) => void;
  /** Ekran okuyucu için grubun adı. */
  etiket: string;
  kucuk?: boolean;
  /** Bütün genişliği eşit paylaşır (çekmece içindeki görev seçimi gibi). */
  tam?: boolean;
}) {
  const kutu = useRef<HTMLDivElement>(null);
  const [olcu, setOlcu] = useState<{ x: number; g: number } | null>(null);
  const ilk = useRef(true);

  useLayoutEffect(() => {
    const el = kutu.current;
    if (!el) return;
    const olc = () => {
      const d = el.querySelector<HTMLButtonElement>('button.secili');
      if (!d) {
        setOlcu(null);
        return;
      }
      setOlcu((o) => (o && o.x === d.offsetLeft && o.g === d.offsetWidth ? o : { x: d.offsetLeft, g: d.offsetWidth }));
    };
    olc();
    if (typeof ResizeObserver === 'undefined') return;
    const g = new ResizeObserver(olc);
    g.observe(el);
    return () => g.disconnect();
  }, [deger, secenekler.length]);

  useLayoutEffect(() => {
    if (olcu && ilk.current) {
      const id = requestAnimationFrame(() => {
        ilk.current = false;
        kutu.current?.classList.remove('ilk');
      });
      return () => cancelAnimationFrame(id);
    }
  }, [olcu]);

  const tus = (olay: KeyboardEvent<HTMLDivElement>) => {
    if (olay.key !== 'ArrowRight' && olay.key !== 'ArrowLeft') return;
    const acik = secenekler.filter((s) => !s.kapali);
    const i = acik.findIndex((s) => s.deger === deger);
    const yeni = acik[(i + (olay.key === 'ArrowRight' ? 1 : -1) + acik.length) % acik.length];
    if (!yeni) return;
    olay.preventDefault();
    degisti(yeni.deger);
    const dugme = kutu.current?.querySelector<HTMLButtonElement>(`[data-deger="${yeni.deger}"]`);
    dugme?.focus();
    dugme?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  };

  return (
    <div
      ref={kutu}
      className={`o-segment${kucuk ? ' kucuk' : ''}${tam ? ' tam' : ''}${olcu ? ' olculdu' : ''}${ilk.current ? ' ilk' : ''}`}
      style={olcu ? ({ '--bp-x': `${olcu.x}px`, '--bp-g': `${olcu.g}px` } as CSSProperties) : undefined}
      role="radiogroup"
      aria-label={etiket}
      onKeyDown={tus}
    >
      <span className="o-segment-basparmak" aria-hidden="true" />
      {secenekler.map((s) => {
        const secili = s.deger === deger;
        return (
          <button
            key={s.deger}
            type="button"
            role="radio"
            aria-checked={secili}
            tabIndex={secili ? 0 : -1}
            data-deger={s.deger}
            className={secili ? 'secili' : undefined}
            disabled={s.kapali}
            onClick={() => degisti(s.deger)}
          >
            <span className="etiket">{s.etiket}</span>
            {s.sayi !== undefined ? <span className="sayi">{s.sayi.toLocaleString('tr-TR')}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
