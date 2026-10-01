/**
 * Tek marka işareti (§6.12, §6.14 P2): mavi kare, sarı "S". Girişte, menüde,
 * açılış perdesinde (index.html) ve PWA simgesinde (public/ikon) AYNI işaret.
 *
 * EK-6 küçük sevinç: işarete art arda 5 kez dokununca ekibin küçük bir notu
 * görünür. İş akışını bekletmez; not kendiliğinden kaybolur.
 */

import { useRef, useState } from 'react';
import './bilesen.css';

const NOT =
  'Bu sistemi sahadaki ekip için, sahadaki ekiple birlikte yaptık. Her atama, her ziyaret, her “bitti” bir müşterinin evinde yanan ışık. Teşekkürler. — Dehanet EÇM Bursa';

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
      {/* "S" CSS ile çizilir (::before): işaret bir logodur, metin değil. */}
      <span
        className="o-marka"
        style={{ width: boyut, height: boyut, fontSize: boyut * 0.5, borderRadius: boyut * 0.29 }}
        onClick={dokun}
        aria-hidden="true"
      />
      {not ? (
        <span className="o-gizli-not" role="status" onClick={() => setNot(false)}>
          {NOT}
        </span>
      ) : null}
    </span>
  );
}
