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
