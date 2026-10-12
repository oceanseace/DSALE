/**
 * Tek marka işareti: Turkcell logosu (kod/marka/turkcell-kaynak.png'den
 * scripts/ikon.py ile üretilen public/ikon/isaret.png). Girişte, menüde,
 * açılış perdesinde (index.html) ve PWA simgesinde AYNI işaret.
 *
 * Küçük sevinç: işarete art arda 5 kez dokununca ekibin küçük bir notu
 * görünür. İş akışını bekletmez; not kendiliğinden kaybolur.
 */

import { useRef, useState } from 'react';
import './bilesen.css';

const NOT =
  'Bu uygulamayı ekip için, ekiple birlikte yaptık. Her atama, her ziyaret, her “bitti” bir müşterinin evinde yanan ışık. Teşekkürler.';

export function Marka({ boyut = 36, gizliNot = true }: { boyut?: number; gizliNot?: boolean }) {
  const dokunuslar = useRef<number[]>([]);
  const [not, setNot] = useState(false);

  const dokun = () => {
    if (!gizliNot) return;
    const simdi = Date.now();
    dokunuslar.current = [...dokunuslar.current.filter((t) => simdi - t < 2500), simdi];
    if (dokunuslar.current.length >= 5) {
      dokunuslar.current = [];
      setNot(true);
      window.setTimeout(() => setNot(false), 7000);
    }
  };

  return (
    <span className="o-marka-sarmal">
      <span className="o-marka" style={{ width: boyut, height: boyut }} onClick={dokun} aria-hidden="true">
        <img src="/ikon/isaret.png" alt="" width={boyut} height={boyut} draggable={false} decoding="async" />
      </span>
      {not ? (
        <span className="o-gizli-not" role="status" onClick={() => setNot(false)}>
          {NOT}
        </span>
      ) : null}
    </span>
  );
}
