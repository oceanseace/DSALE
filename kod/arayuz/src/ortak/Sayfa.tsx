/** Sayfa iskeleti: üst başlık + gövde. Her ekran aynı görünsün diye tek yerde. */

import type { ReactNode } from 'react';
import { Geri } from './Ikon';
import { EkranCumlesi } from './IlkIpucu';
import { DahaMenusu, type MenuOgesi } from './Menu';
import './bilesen.css';

interface UstOzellik {
  baslik: string;
  altYazi?: string | null;
  geriyeGit?: () => void;
  sag?: ReactNode;
  /** Geri düğmesi olan ekranlarda başlık ortalanır (iOS alışkanlığı). */
  ortala?: boolean;
}

export function Ust({ baslik, altYazi, geriyeGit, sag, ortala = false }: UstOzellik) {
  return (
    <header className="ust">
      <div className="ust-satir">
        {geriyeGit ? (
          <button className="geri" onClick={geriyeGit} aria-label="Geri">
            <Geri boyut={26} />
          </button>
        ) : null}
        <h1 className={`ust-baslik${ortala ? ' kucuk' : ''}`}>{baslik}</h1>
        {sag ?? (geriyeGit && ortala ? <span style={{ width: 34 }} /> : null)}
      </div>
      {altYazi ? <div className="ust-alt">{altYazi}</div> : null}
    </header>
  );
}

/**
 * Başlık çubuğu (§7.3): 44 px, geri oku, ortada başlık, sağda EN ÇOK bir eylem
 * ya da "…". Altında isteğe bağlı "Bu ekranda ne yaparım?" cümlesi (kapatılır,
 * cihaz hatırlar). Teknik ve telefon ekranlarının ortak başlığı.
 */
export function BaslikCubugu({
  baslik,
  geri,
  eylem,
  digerleri,
  cumle,
}: {
  baslik: ReactNode;
  geri?: () => void;
  /** Tek görünür eylem (ör. "+" düğmesi). */
  eylem?: ReactNode;
  /** "…" menüsündeki ikincil eylemler. */
  digerleri?: MenuOgesi[];
  /** Başlığın altındaki tek cümle: { anahtar: 'islerim', metin: '…' }. */
  cumle?: { anahtar: string; metin: string };
}) {
  return (
    <header className="o-baslik">
      <div className="o-baslik-satir">
        <span className="sol">
          {geri ? (
            <button type="button" className="o-baslik-geri" onClick={geri} aria-label="Geri">
              <Geri boyut={24} />
            </button>
          ) : null}
        </span>
        <h1>{baslik}</h1>
        <span className="sag">
          {eylem}
          {digerleri?.length ? <DahaMenusu ogeler={digerleri} /> : null}
        </span>
      </div>
      {cumle ? <EkranCumlesi anahtar={cumle.anahtar}>{cumle.metin}</EkranCumlesi> : null}
    </header>
  );
}

/** Ekranın dış kabuğu. İçine `Ust` ve `SayfaGovde` konur. */
export function Sayfa({ children, sabit = false }: { children: ReactNode; sabit?: boolean }) {
  return <div className={`sayfa${sabit ? ' sabit' : ''}`}>{children}</div>;
}

/** Kaydırılan içerik alanı. `tam` = kenar boşluğu yok (harita). */
export function SayfaGovde({
  children,
  tam = false,
  sekmesiz = false,
}: {
  children: ReactNode;
  tam?: boolean;
  sekmesiz?: boolean;
}) {
  return (
    <main className={`sayfa-govde${tam ? ' tam' : ''}${sekmesiz ? ' sekmesiz' : ''}`}>{children}</main>
  );
}

/** Boş ekran anlatımı: büyük simge, tek cümle, tek düğme. */
export function BosDurum({
  simge,
  baslik,
  aciklama,
  children,
}: {
  simge: string;
  baslik: string;
  aciklama?: string;
  children?: ReactNode;
}) {
  return (
    <div className="bos">
      <div className="simge" aria-hidden="true">
        {simge}
      </div>
      <h2>{baslik}</h2>
      {aciklama ? <p>{aciklama}</p> : null}
      {children}
    </div>
  );
}
