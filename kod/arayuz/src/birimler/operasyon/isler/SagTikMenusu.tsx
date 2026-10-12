/**
 * TASKS hücresine sağ tık: Ayrıntı (i), Kopyala (Ctrl+C), Dolgu rengi paleti — Excel'in sağ tık menüsü gibi.
 * Dolgu rengi yalnız SEÇİLİ HÜCRELERE (Excel gibi); "Ata…" / "Askıya al…" seçili satırlara. Giriş: <SagTikMenusu …/>. Kim: Tablo.tsx.
 */

import { useRef } from 'react';
import { createPortal } from 'react-dom';
import type { IsaretRengi } from '../../../cekirdek/is/tipler';
import { useDisariKapat, useEkranaSigdir } from './acilir';
import { RenkPaleti } from './DolguRengi';

export function SagTikMenusu({
  x,
  y,
  satirSayisi,
  hucreSayisi = 1,
  boyanabilir,
  ac,
  kopyala,
  boya,
  ata,
  aski,
  kapat,
}: {
  x: number;
  y: number;
  satirSayisi: number;
  /** Seçili hücre sayısı (dolgu yalnız onlara). */
  hucreSayisi?: number;
  boyanabilir: boolean;
  ac: () => void;
  kopyala: () => void;
  boya: (r: IsaretRengi | null) => void;
  ata?: () => void;
  /** Toplu "Askıya al…" (seçili satırlar); yoksa görünmez. */
  aski?: () => void;
  kapat: () => void;
}) {
  const kok = useRef<HTMLDivElement>(null);
  useDisariKapat(kok, kapat);
  useEkranaSigdir(kok);
  const yap = (f: () => void) => () => {
    kapat();
    f();
  };
  return createPortal(
    <div
      className="xg-menu xg-sagtik"
      ref={kok}
      role="menu"
      style={{ left: Math.min(x, window.innerWidth - 250), top: Math.min(y, window.innerHeight - 240) }}
      onMouseDown={(o) => o.preventDefault()}
      onContextMenu={(o) => o.preventDefault()}
    >
      <button type="button" role="menuitem" className="xg-menu-satir" onClick={yap(ac)}>
        <span className="xg-menu-simge">ⓘ</span> Ayrıntıyı aç <kbd>Enter</kbd>
      </button>
      <button type="button" role="menuitem" className="xg-menu-satir" onClick={yap(kopyala)}>
        <span className="xg-menu-simge">⧉</span> Kopyala <kbd>Ctrl+C</kbd>
      </button>
      {ata ? (
        <button type="button" role="menuitem" className="xg-menu-satir" onClick={yap(ata)}>
          <span className="xg-menu-simge">⇢</span> Ata…{satirSayisi > 1 ? ` (${satirSayisi.toLocaleString('tr-TR')} iş)` : ''}
        </button>
      ) : null}
      {aski ? (
        <button type="button" role="menuitem" className="xg-menu-satir" onClick={yap(aski)}>
          <span className="xg-menu-simge">⏸</span> Askıya al…{satirSayisi > 1 ? ` (${satirSayisi.toLocaleString('tr-TR')} iş)` : ''}
        </button>
      ) : null}
      {boyanabilir ? (
        <>
          <hr />
          <div className="xg-menu-etiket">Dolgu rengi · {hucreSayisi > 1 ? `seçili ${hucreSayisi.toLocaleString('tr-TR')} hücre` : 'bu hücre'}</div>
          <RenkPaleti sec={(r) => yap(() => boya(r))()} />
        </>
      ) : null}
    </div>,
    document.body,
  );
}
