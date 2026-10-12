/** Sayfa iskeleti: üst başlık + gövde. Her ekran aynı görünsün diye tek yerde. */

import type { ReactNode } from 'react';
import { Geri } from './Ikon';
import { cizgiSimge } from './CizgiSimge';
import { AramaDugmesi } from '../arama/AramaDugmesi';
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
        {sag ?? (geriyeGit && ortala ? <span style={{ width: 34 }} /> : !geriyeGit ? <AramaDugmesi bicim="simge" /> : null)}
      </div>
      {altYazi ? <div className="ust-alt">{altYazi}</div> : null}
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
        {cizgiSimge(simge, 36)}
      </div>
      <h2>{baslik}</h2>
      {aciklama ? <p>{aciklama}</p> : null}
      {children}
    </div>
  );
}
