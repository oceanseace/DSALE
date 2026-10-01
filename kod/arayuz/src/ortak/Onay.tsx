/**
 * Onay: `window.confirm` yerine (§6.10 "window.confirm hiçbir yerde kalmaz").
 *
 * Başlık, tek cümle, iki düğme. Yıkıcı olan kırmızı ve SAĞDA; Enter onaylar,
 * Esc vazgeçer. Masaüstünde ortada küçük pencere, telefonda alttan çekmece.
 *
 *   const [onayPenceresi, sor] = useOnay();
 *   if (await sor({ baslik: 'Silinsin mi?', metin: '…', onay: 'Sil', yikici: true })) …
 *   return <>{…}{onayPenceresi}</>;
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import './bilesen.css';

export interface OnaySorusu {
  baslik: ReactNode;
  metin?: ReactNode;
  /** Onay düğmesinin yazısı (fiil: "Sil", "Pasife al", "Gönder"). */
  onay: string;
  vazgec?: string;
  yikici?: boolean;
}

export function Onay({
  acik,
  soru,
  cevap,
  bekliyor = false,
  children,
}: {
  acik: boolean;
  soru: OnaySorusu | null;
  cevap: (evet: boolean) => void;
  bekliyor?: boolean;
  /** Metnin altına ek içerik (sayılar listesi gibi). */
  children?: ReactNode;
}) {
  const onayDugmesi = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!acik) return;
    const tus = (o: KeyboardEvent) => {
      if (o.key === 'Escape' && !bekliyor) {
        o.stopPropagation();
        cevap(false);
      }
    };
    document.addEventListener('keydown', tus, true);
    // Yıkıcı eylemde odak "Vazgeç"te durur: yanlışlıkla Enter silmesin.
    window.setTimeout(() => {
      if (!soru?.yikici) onayDugmesi.current?.focus();
    }, 20);
    return () => document.removeEventListener('keydown', tus, true);
  }, [acik, cevap, bekliyor, soru?.yikici]);

  if (!acik || !soru) return null;

  return createPortal(
    <>
      <div className="o-onay-perde" onClick={bekliyor ? undefined : () => cevap(false)} aria-hidden="true" />
      <div className="o-onay" role="alertdialog" aria-modal="true" aria-label={typeof soru.baslik === 'string' ? soru.baslik : undefined}>
        <h2>{soru.baslik}</h2>
        {soru.metin ? <p>{soru.metin}</p> : null}
        {children}
        <div className="o-onay-dugmeler">
          <button type="button" className="o-dugme" onClick={() => cevap(false)} disabled={bekliyor} autoFocus={soru.yikici}>
            {soru.vazgec ?? 'Vazgeç'}
          </button>
          <button
            ref={onayDugmesi}
            type="button"
            className={`o-dugme ${soru.yikici ? 'yikici' : 'birincil'}`}
            onClick={() => cevap(true)}
            disabled={bekliyor}
          >
            {bekliyor ? 'Bekleyin…' : soru.onay}
          </button>
        </div>
      </div>
    </>,
    document.body,
  );
}

/** Söz veren onay: `await sor(...)` → true/false. */
export function useOnay(): [ReactNode, (soru: OnaySorusu) => Promise<boolean>] {
  const [soru, setSoru] = useState<OnaySorusu | null>(null);
  const cozucu = useRef<((evet: boolean) => void) | null>(null);

  const sor = useCallback((yeni: OnaySorusu) => {
    cozucu.current?.(false);
    setSoru(yeni);
    return new Promise<boolean>((coz) => {
      cozucu.current = coz;
    });
  }, []);

  const cevap = useCallback((evet: boolean) => {
    cozucu.current?.(evet);
    cozucu.current = null;
    setSoru(null);
  }, []);

  return [<Onay key="onay" acik={Boolean(soru)} soru={soru} cevap={cevap} />, sor];
}
