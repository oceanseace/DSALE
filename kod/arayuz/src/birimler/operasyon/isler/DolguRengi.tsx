/**
 * Hücre boyama (Excel'deki boya kovası): YALNIZ seçili hücreler boyanır. Renk paleti ve araç çubuğundaki "Dolgu rengi" düğmesi.
 * Düğmenin solu son rengi uygular, ▾ paleti açar; sağ tık menüsü de aynı `RenkPaleti`ni kullanır.
 * Kim: Isler.tsx (düğme), SagTikMenusu.tsx (palet). Renkler tablo.css'te (--xg-r-*), adlar sutunlar.ts'te.
 */

import { useCallback, useRef, useState } from 'react';
import type { IsaretRengi } from '../../../cekirdek/is/tipler';
import { useDisariKapat, useEkranaSigdir } from './acilir';
import { RENK_ADI } from './sutunlar';

export const RENKLER: IsaretRengi[] = ['sari', 'kirmizi', 'yesil', 'mavi', 'mor', 'turuncu'];

export function RenkPaleti({ sec }: { sec: (r: IsaretRengi | null) => void }) {
  return (
    <div className="xg-palet" role="group" aria-label="Dolgu rengi">
      {RENKLER.map((r) => (
        <button key={r} type="button" className={`xg-renk r-${r}`} title={RENK_ADI[r]} aria-label={RENK_ADI[r]} onClick={() => sec(r)} />
      ))}
      <button type="button" className="o-dugme kucuk" onClick={() => sec(null)}>
        Dolgu yok
      </button>
    </div>
  );
}

function KovaSimgesi({ renk }: { renk: IsaretRengi }) {
  return (
    <span className="xg-kova" aria-hidden="true">
      <svg width="16" height="14" viewBox="0 0 24 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round">
        <path d="M4 9 11 2l7 7-7 7z" />
        <path d="M20 12s2 2.4 2 3.6a2 2 0 0 1-4 0C18 14.4 20 12 20 12z" fill="currentColor" stroke="none" />
      </svg>
      <span className={`xg-kova-cizgi r-${renk}`} />
    </span>
  );
}

export function DolguRengiDugmesi({ etkin, uygula }: { etkin: boolean; uygula: (r: IsaretRengi | null) => void }) {
  const [son, setSon] = useState<IsaretRengi>('sari');
  const [acik, setAcik] = useState(false);
  const kok = useRef<HTMLDivElement>(null);

  const kapat = useCallback(() => setAcik(false), []);
  useDisariKapat(kok, kapat, acik);
  const acilirRef = useRef<HTMLDivElement>(null);
  useEkranaSigdir(acilirRef, acik);

  const ipucu = etkin ? undefined : 'Önce tabloda hücre seçin';
  return (
    // mousedown'da odak tabloda kalsın: boyadıktan sonra ok tuşları çalışmaya devam eder.
    <div className="xg-bolunmus" ref={kok} onMouseDown={(o) => o.preventDefault()}>
      <button
        type="button"
        className="xg-arac-dugme"
        disabled={!etkin}
        title={ipucu ?? `Seçili hücreleri ${RENK_ADI[son].toLocaleLowerCase('tr-TR')} boya`}
        onClick={() => uygula(son)}
      >
        <KovaSimgesi renk={son} /> Dolgu rengi
      </button>
      <button
        type="button"
        className="xg-arac-dugme ok"
        disabled={!etkin}
        title={ipucu}
        aria-label="Dolgu rengi seç"
        aria-expanded={acik}
        onClick={() => setAcik((a) => !a)}
      >
        ▾
      </button>
      {acik ? (
        <div ref={acilirRef} className="xg-acilir">
          <RenkPaleti
            sec={(r) => {
              if (r) setSon(r);
              setAcik(false);
              uygula(r);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
