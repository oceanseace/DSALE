/**
 * Kişi seçici (§7.3): yazdıkça daralan liste; her satır "A. K. · öbeğin ·
 * bugün 9/15" gibi kararı verdiren bilgiyi taşır. Ok tuşları + Enter ile
 * klavyeden, dokunarak telefondan seçilir.
 */

import { useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { eslesir } from './ara';
import './bilesen.css';

export interface SecilecekKisi {
  id: number;
  ad: string;
  /** Satırın ikinci parçası: "öbeğin · bugün 9/15". */
  bilgi?: ReactNode;
  /** Sağdaki rozet ("Önerilen", "Girişsiz"). */
  rozet?: ReactNode;
  /** Aranacak ek metin (öbek adları, BOSS ekip adı…). */
  anahtar?: string;
  kapali?: boolean;
}

export function KisiSecici({
  kisiler,
  deger,
  degisti,
  yerTutucu = 'Ad yazın…',
  bosMetin = 'Bu adla kimse yok.',
  enCok = 8,
}: {
  kisiler: SecilecekKisi[];
  deger: number | null;
  degisti: (id: number) => void;
  yerTutucu?: string;
  bosMetin?: string;
  enCok?: number;
}) {
  const [sorgu, setSorgu] = useState('');
  const [imlec, setImlec] = useState(0);
  const liste = useRef<HTMLDivElement>(null);

  const suzulmus = useMemo(
    () => kisiler.filter((k) => eslesir(`${k.ad} ${k.anahtar ?? ''}`, sorgu)).slice(0, sorgu ? 50 : enCok),
    [kisiler, sorgu, enCok],
  );

  const tus = (o: KeyboardEvent<HTMLInputElement>) => {
    if (o.key === 'ArrowDown') {
      o.preventDefault();
      setImlec((i) => Math.min(suzulmus.length - 1, i + 1));
    } else if (o.key === 'ArrowUp') {
      o.preventDefault();
      setImlec((i) => Math.max(0, i - 1));
    } else if (o.key === 'Enter') {
      const k = suzulmus[imlec];
      if (k && !k.kapali) {
        o.preventDefault();
        degisti(k.id);
      }
    }
  };

  return (
    <div className="o-kisi-secici">
      <input
        className="o-girdi"
        type="search"
        value={sorgu}
        placeholder={yerTutucu}
        onChange={(o) => {
          setSorgu(o.target.value);
          setImlec(0);
        }}
        onKeyDown={tus}
        aria-label="Kişi ara"
      />
      <div ref={liste} className="o-kisi-liste" role="listbox" aria-label="Kişiler">
        {suzulmus.length ? (
          suzulmus.map((k, i) => (
            <button
              key={k.id}
              type="button"
              role="option"
              aria-selected={k.id === deger}
              className={`${k.id === deger ? 'secili' : ''}${i === imlec ? ' imlec' : ''}`}
              disabled={k.kapali}
              onClick={() => degisti(k.id)}
              onMouseEnter={() => setImlec(i)}
            >
              <span className="ad">{k.ad}</span>
              {k.bilgi ? <span className="bilgi">{k.bilgi}</span> : null}
              {k.rozet ? <span className="rozet">{k.rozet}</span> : null}
            </button>
          ))
        ) : (
          <p className="o-kisi-bos">{bosMetin}</p>
        )}
      </div>
    </div>
  );
}
