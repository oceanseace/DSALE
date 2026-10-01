/**
 * İlk açılış ipucu (§6.13): kişi başına, cihazda BİR KEZ görünen küçük
 * numaralı balonlar — "1 Öbek seçin · 2 İşe dokunun · 3 Ata'ya basın".
 * "Anladım" ile kapanır ve bir daha gelmez. Hiçbir şeyi engellemez.
 *
 * Ayrıca `EkranCumlesi`: başlığın altındaki "Bu ekranda ne yaparım?" tek
 * cümlesi (§6.0); ✕ ile kapanır, cihaz hatırlar.
 */

import { useState } from 'react';
import { yerelOku, yerelYaz } from './yerel';
import './bilesen.css';

export function IlkIpucu({ anahtar, adimlar }: { anahtar: string; adimlar: string[] }) {
  const tamAnahtar = `saha.ipucu.${anahtar}`;
  const [acik, setAcik] = useState(() => yerelOku(tamAnahtar) !== '1');
  if (!acik || !adimlar.length) return null;
  return (
    <div className="o-ilk-ipucu" role="note">
      <ol>
        {adimlar.map((a, i) => (
          <li key={a}>
            <span className="no" aria-hidden="true">
              {i + 1}
            </span>
            {a}
          </li>
        ))}
      </ol>
      <button
        type="button"
        className="o-dugme kucuk"
        onClick={() => {
          yerelYaz(tamAnahtar, '1');
          setAcik(false);
        }}
      >
        Anladım
      </button>
    </div>
  );
}

export function EkranCumlesi({ anahtar, children }: { anahtar: string; children: string }) {
  const tamAnahtar = `saha.cumle.${anahtar}`;
  const [acik, setAcik] = useState(() => yerelOku(tamAnahtar) !== '0');
  if (!acik) return null;
  return (
    <p className="o-ekran-cumlesi">
      <span>{children}</span>
      <button
        type="button"
        aria-label="Bu açıklamayı gizle"
        title="Gizle"
        onClick={() => {
          yerelYaz(tamAnahtar, '0');
          setAcik(false);
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" aria-hidden="true">
          <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
        </svg>
      </button>
    </p>
  );
}
