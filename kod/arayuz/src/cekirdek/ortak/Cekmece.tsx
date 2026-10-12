/**
 * Alttan açılan panel (bottom sheet).
 * Telefonda alışılmış davranış: aşağıdan kayarak gelir, dışına dokununca kapanır,
 * geri tuşu da kapatır.
 */

import { useEffect, type ReactNode } from 'react';

interface Ozellik {
  acik: boolean;
  kapat: () => void;
  baslik?: string;
  altBaslik?: string;
  children: ReactNode;
  /** Yanlışlıkla kapanmaması gereken paneller (kaydetme sırasında). */
  kilitli?: boolean;
}

export function Cekmece({ acik, kapat, baslik, altBaslik, children, kilitli = false }: Ozellik) {
  useEffect(() => {
    if (!acik) return;
    const escBasildi = (olay: KeyboardEvent) => {
      if (olay.key === 'Escape' && !kilitli) kapat();
    };
    document.addEventListener('keydown', escBasildi);
    const oncekiTasma = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', escBasildi);
      document.body.style.overflow = oncekiTasma;
    };
  }, [acik, kapat, kilitli]);

  if (!acik) return null;

  return (
    <>
      {/* Perdeye dokunmak `kapat`ı çağırır; içeriğinde yazılmış bir şey varsa
          çağıran taraf ONAY sorar (bkz. SonucCekmecesi.kapatmaIstegi). Eskiden
          yanlış bir dokunuş seçilen sonucu, satış adedini ve notu sessizce
          siliyordu. */}
      <div className="perde" onClick={kilitli ? undefined : kapat} aria-hidden="true" />
      <div className="cekmece" role="dialog" aria-modal="true" aria-label={baslik}>
        <div className="cekmece-tutamac" />
        {baslik ? <h2 className="cekmece-baslik">{baslik}</h2> : null}
        {altBaslik ? <p className="cekmece-alt">{altBaslik}</p> : null}
        {children}
      </div>
    </>
  );
}
