/**
 * Liste ve liste satırı (§7.3): 2–3 satırlık metin, solda küçük ek (hap,
 * simge, baş harf), sağda rozet/ok/eylem. Bütün satır tıklanır; hedef
 * telefonda ≥ 44 px. Uzun listelerde `content-visibility:auto` ekranda
 * olmayan satırların çizimini atlar.
 */

import type { KeyboardEvent, ReactNode } from 'react';
import './bilesen.css';

export function Liste({ children, etiket }: { children: ReactNode; etiket?: string }) {
  return (
    <div className="o-liste" role="list" aria-label={etiket}>
      {children}
    </div>
  );
}

export function ListeSatiri({
  sol,
  baslik,
  alt,
  ucuncu,
  sag,
  onClick,
  secili = false,
  ok = true,
  soluk = false,
}: {
  sol?: ReactNode;
  baslik: ReactNode;
  alt?: ReactNode;
  ucuncu?: ReactNode;
  sag?: ReactNode;
  onClick?: () => void;
  secili?: boolean;
  /** Sağda "›" (tıklanan satırda varsayılan). */
  ok?: boolean;
  /** Pasif kişi, kapanmış iş… */
  soluk?: boolean;
}) {
  const tus = (o: KeyboardEvent<HTMLDivElement>) => {
    if (!onClick) return;
    if (o.key === 'Enter' || o.key === ' ') {
      o.preventDefault();
      onClick();
    }
  };
  return (
    <div
      role="listitem"
      className={`o-satir${onClick ? ' tiklanir' : ''}${secili ? ' secili' : ''}${soluk ? ' soluk' : ''}`}
      onClick={onClick}
      onKeyDown={tus}
      tabIndex={onClick ? 0 : undefined}
      aria-current={secili ? 'true' : undefined}
    >
      {sol ? <div className="sol">{sol}</div> : null}
      <div className="govde">
        <div className="baslik">{baslik}</div>
        {alt ? <div className="alt">{alt}</div> : null}
        {ucuncu ? <div className="ucuncu">{ucuncu}</div> : null}
      </div>
      {sag ? <div className="sag">{sag}</div> : null}
      {onClick && ok ? (
        <svg className="ok" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" aria-hidden="true">
          <path d="m9 6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : null}
    </div>
  );
}
