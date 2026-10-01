/**
 * Boş, yükleniyor ve hata durumları (§6.13) — her listede aynı dil.
 *
 * Boş durum ne olduğunu ve NE YAPILACAĞINI söyler; en çok bir düğme.
 * Hata kutusu suçlamaz, "Tekrar dene" verir. İskelet, gerçek satırların
 * yerini tutar ki ekran veri gelince zıplamasın.
 */

import type { ReactNode } from 'react';
import './bilesen.css';

export function BosDurum({
  simge,
  baslik,
  aciklama,
  children,
  kucuk = false,
}: {
  /** Emoji ya da SVG. */
  simge?: ReactNode;
  baslik: ReactNode;
  aciklama?: ReactNode;
  /** Tek eylem düğmesi. */
  children?: ReactNode;
  kucuk?: boolean;
}) {
  return (
    <div className={`o-bos${kucuk ? ' kucuk' : ''}`}>
      {simge ? (
        <div className="simge" aria-hidden="true">
          {simge}
        </div>
      ) : null}
      <h3>{baslik}</h3>
      {aciklama ? <p>{aciklama}</p> : null}
      {children ? <div className="eylem">{children}</div> : null}
    </div>
  );
}

export function Iskelet({ satir = 5, yukseklik = 56 }: { satir?: number; yukseklik?: number }) {
  return (
    <div className="o-iskelet" aria-hidden="true">
      {Array.from({ length: satir }, (_, i) => (
        <span key={i} style={{ height: yukseklik }} />
      ))}
    </div>
  );
}

export function HataKutusu({ mesaj, tekrar }: { mesaj: ReactNode; tekrar?: () => void }) {
  return (
    <div className="o-hata" role="alert">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7.5v5.5M12 16.5h.01" strokeLinecap="round" />
      </svg>
      <span className="mesaj">{mesaj}</span>
      {tekrar ? (
        <button type="button" className="o-dugme kucuk" onClick={tekrar}>
          Tekrar dene
        </button>
      ) : null}
    </div>
  );
}

/** 403 ekranı (§6.13): "Bu bölüm görevinize kapalı." + [Ana ekrana dön]. */
export function KapaliBolum({ anaEkranaDon }: { anaEkranaDon: () => void }) {
  return (
    <BosDurum
      simge="🔒"
      baslik="Bu bölüm görevinize kapalı."
      aciklama="Göreviniz değiştiyse yöneticiniz Ekip ekranından açabilir."
    >
      <button type="button" className="o-dugme birincil" onClick={anaEkranaDon}>
        Ana ekrana dön
      </button>
    </BosDurum>
  );
}
