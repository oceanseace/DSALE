/**
 * Akış şeridi: bir işin adımlarını soldan sağa (telefonda yukarıdan aşağı) çizer.
 * Her adımın simgesi, adı, kısa cümlesi ve isteğe bağlı sayısı vardır; altında
 * "değilse" dalları durur (ör. altyapı uygun değil → ticket).
 */

import type { ReactNode } from 'react';
import './akisSeridi.css';

export interface AkisAdimi {
  simge: ReactNode;
  ad: string;
  cumle: string;
  /** Bu adımda bekleyen iş sayısı; bilinmiyorsa gösterilmez. */
  sayi?: number | null;
}

export interface AkisDali {
  kosul: string;
  sonuc: string;
}

export function AkisSeridi({ adimlar, dallar = [] }: { adimlar: AkisAdimi[]; dallar?: AkisDali[] }) {
  return (
    <div className="akis">
      <ol className="akis-adimlar">
        {adimlar.map((a, i) => (
          <li key={a.ad} className="akis-adim">
            <span className="akis-simge" aria-hidden="true">
              {a.simge}
            </span>
            <span className="akis-metin">
              <b>
                {i + 1}. {a.ad}
              </b>
              <span>{a.cumle}</span>
            </span>
            {a.sayi != null ? <span className="akis-sayi">{a.sayi.toLocaleString('tr-TR')}</span> : null}
          </li>
        ))}
      </ol>
      {dallar.length ? (
        <ul className="akis-dallar">
          {dallar.map((d) => (
            <li key={d.kosul}>
              <span className="kosul">{d.kosul}</span>
              <span className="ok" aria-hidden="true">
                →
              </span>
              <span className="sonuc">{d.sonuc}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
