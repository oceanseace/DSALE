/**
 * Çip, süzgeç düğmesi ve etkin süzgeç çipleri (§7.3).
 *
 * Ekranda tek bir "Süz" düğmesi olur; seçilen süzgeçler altında çip olarak
 * görünür ve ✕ ile tek dokunuşta kalkar. Böylece "neden liste kısa?"
 * sorusunun cevabı hep gözün önündedir.
 */

import type { ReactNode } from 'react';
import './bilesen.css';

export function Cip({
  children,
  secili = false,
  sayi,
  onClick,
  baslik,
}: {
  children: ReactNode;
  secili?: boolean;
  sayi?: number;
  onClick?: () => void;
  baslik?: string;
}) {
  return (
    <button
      type="button"
      className={`o-cip${secili ? ' secili' : ''}`}
      aria-pressed={onClick ? secili : undefined}
      onClick={onClick}
      title={baslik}
    >
      <span>{children}</span>
      {sayi !== undefined ? <span className="sayi">{sayi.toLocaleString('tr-TR')}</span> : null}
    </button>
  );
}

/** Seçenekler çip sırası olarak (kayar, taşmaz). */
export function CipSirasi({ children, etiket }: { children: ReactNode; etiket?: string }) {
  return (
    <div className="o-cip-sira" role="group" aria-label={etiket}>
      {children}
    </div>
  );
}

export function SuzDugmesi({ etkinSayi = 0, onClick }: { etkinSayi?: number; onClick: () => void }) {
  return (
    <button type="button" className={`o-suz${etkinSayi ? ' etkin' : ''}`} onClick={onClick}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
        <path d="M4 6h16M7 12h10M10 18h4" strokeLinecap="round" />
      </svg>
      Süz
      {etkinSayi ? <span className="sayi">{etkinSayi}</span> : null}
    </button>
  );
}

/** Etkin bir süzgeç: "Görükle ✕". */
export function SuzCipi({ children, kaldir }: { children: ReactNode; kaldir: () => void }) {
  return (
    <span className="o-suz-cip">
      <span>{children}</span>
      <button type="button" onClick={kaldir} aria-label="Süzgeci kaldır">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
        </svg>
      </button>
    </span>
  );
}
