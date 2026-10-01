/**
 * Segment: 2–5 seçenekten biri (iOS "segmented control").
 *
 * Sayaçlı olabilir ("Satış 2"). Dar ekranda sayfayı taşırmaz, kendi içinde
 * yatay kayar (§7.3, §6.14 P2). Ok tuşlarıyla seçenekler arasında gezilir.
 */

import { useRef, type KeyboardEvent, type ReactNode } from 'react';
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
      className={`o-segment${kucuk ? ' kucuk' : ''}${tam ? ' tam' : ''}`}
      role="radiogroup"
      aria-label={etiket}
      onKeyDown={tus}
    >
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
