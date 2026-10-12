/**
 * Manşet: ekranın başında tek satır sakin sayılar (§7.3). Her sayı tıklanır
 * (o süzgeçle liste açılır). Renk yalnız hedef aşılınca girer; varsayılan
 * nötrdür. Telefonda sayılar alt alta satır olur, değer sağa yaslanır.
 */

import type { ReactNode } from 'react';
import './bilesen.css';

export interface MansetOgesi {
  etiket: ReactNode;
  deger: ReactNode;
  /** "(en eskisi 9 dk)" gibi küçük ek. */
  ek?: ReactNode;
  renk?: 'kirmizi' | 'amber' | 'yesil';
  onClick?: () => void;
  baslik?: string;
}

export function Manset({ ogeler, etiket }: { ogeler: MansetOgesi[]; etiket?: string }) {
  return (
    <div className="o-manset" role="list" aria-label={etiket}>
      {ogeler.map((o, i) => {
        const ic = (
          <>
            <span className="etiket">{o.etiket}</span>
            <span className={`deger${o.renk ? ' ' + o.renk : ''}`}>{o.deger}</span>
            {o.ek ? <span className="ek">{o.ek}</span> : null}
          </>
        );
        return o.onClick ? (
          <button key={i} type="button" role="listitem" className="oge" onClick={o.onClick} title={o.baslik}>
            {ic}
          </button>
        ) : (
          <span key={i} role="listitem" className="oge" title={o.baslik}>
            {ic}
          </span>
        );
      })}
    </div>
  );
}
