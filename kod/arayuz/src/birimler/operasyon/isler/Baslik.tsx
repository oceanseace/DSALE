/**
 * TASKS başlık satırı (Excel'deki sütun başlıkları). İsteğe bağlı üstte harf satırı (A, B, C…; tıkla → sütunu seç).
 * Alan adları satırı: ada tıkla → bütün sütunu seç (Shift ile genişlet), adı YA DA harfi basılı tutup sürükle →
 * sütun ARALIĞI seçilir (Excel gibi; sütun taşınmaz — sıra "Sütunlar" menüsünde), sağ kenarı sürükle → genişlik,
 * kenara çift tık → içeriğe sığdır, ▾ → otomatik süzgeç.
 * Sol üst köşe: tümünü seç. Giriş: <Baslik …/>. Kim: Tablo.tsx. Sıra/genişlik: sutunDuzeni.ts.
 */

import type { RefObject } from 'react';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import { DONUK, sutunBul, sutunHarfi, type Geometri } from './geometri';
import type { Alan } from './secim';
import type { SutunDuzeni } from './sutunDuzeni';
import type { Sutun } from './sutunlar';
import { suzgecEtkin, type TabloSuzgec } from './tabloSuzgec';

let tuval: CanvasRenderingContext2D | null = null;
/** Metnin ızgara yazı tipindeki genişliği (içeriğe sığdır). `yazi`: "15px Calibri, …". */
function olc(metin: string, kalin: boolean, yazi: string): number {
  tuval ??= document.createElement('canvas').getContext('2d');
  if (!tuval) return metin.length * 7;
  tuval.font = `${kalin ? '600 ' : ''}${yazi}`;
  return tuval.measureText(metin).width;
}

function Huni() {
  return (
    <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
      <path d="M1 1.5h10L7.2 6.3V11L4.8 9.6V6.3z" fill="currentColor" />
    </svg>
  );
}

export function Baslik({
  sutunlar,
  g,
  t,
  alan,
  kap,
  duzen,
  satirlar,
  harfler,
  canliGen,
  sutunSec,
  sutunAralik,
  hepsiniSec,
  menuAc,
  olcek,
}: {
  sutunlar: Sutun[];
  g: Geometri;
  t: TabloSuzgec;
  alan: Alan | null;
  kap: RefObject<HTMLDivElement>;
  duzen: SutunDuzeni;
  satirlar: IsSatir[];
  /** Üstte Excel sütun harfleri satırı. */
  harfler: boolean;
  canliGen: (d: { id: string; px: number } | null) => void;
  sutunSec: (j: number, genislet: boolean) => void;
  /** Sütun aralığı seç (çapa a, etkin b): başlıkta sürüklerken. */
  sutunAralik: (a: number, b: number) => void;
  hepsiniSec: () => void;
  menuAc: (id: string, x: number, y: number) => void;
  /** Izgara yakınlaştırması (1 = %100): ekrandaki piksel farkı ızgara pikseline bölünür. */
  olcek?: number;
}) {
  const z = olcek && olcek > 0 ? olcek : 1;

  /** Ekrandaki x → içerikteki x (donuk bölüm kaymaz). */
  const icerikX = (clientX: number) => {
    const el = kap.current;
    if (!el) return clientX;
    const x = (clientX - el.getBoundingClientRect().left) / z;
    return x < g.donukGen ? x : x + el.scrollLeft;
  };

  /**
   * Ad ya da harf hücresine basış — Excel gibi: tık → sütunu seç (Shift: etkin sütundan buraya), basılı tutup
   * sağa/sola sürükle → başlangıç sütunundan imlecin altındaki sütuna kadar ARALIK seçilir (B..E). Sütun TAŞINMAZ;
   * sıra "Sütunlar" menüsünden değişir. Kenara gelince yatay kayar.
   */
  const adBas = (o: React.PointerEvent, j: number) => {
    if (o.button !== 0) return;
    o.preventDefault();
    const el0 = o.currentTarget as HTMLElement;
    try {
      el0.setPointerCapture(o.pointerId); // ızgara dışına çıkınca da olaylar gelsin
    } catch {
      /* eski motor */
    }
    kap.current?.focus({ preventScroll: true });
    sutunSec(j, o.shiftKey);
    const capa = o.shiftKey ? null : j; // Shift+tık: çapa etkin sütunda kalır (sutunSec genişletti)
    let sonX = o.clientX;
    let son = j;
    let kare = 0;
    const izle = () => {
      const k = Math.max(0, Math.min(sutunlar.length - 1, sutunBul(g, icerikX(sonX))));
      if (k !== son && capa !== null) {
        son = k;
        sutunAralik(capa, k);
      }
    };
    const dongu = () => {
      const el = kap.current;
      if (!el) return;
      const k = el.getBoundingClientRect();
      const sag = k.right - 30;
      const sol = k.left + g.donukGen * z + 30;
      const dx = sonX > sag ? sonX - sag : sonX < sol ? sonX - sol : 0;
      if (dx) {
        el.scrollLeft += Math.max(-30, Math.min(30, dx));
        izle();
      }
      kare = window.requestAnimationFrame(dongu);
    };
    const hareket = (e: PointerEvent) => {
      sonX = e.clientX;
      izle();
    };
    const bitir = () => {
      window.removeEventListener('pointermove', hareket);
      window.removeEventListener('pointerup', bitir);
      window.removeEventListener('pointercancel', bitir);
      window.cancelAnimationFrame(kare);
    };
    window.addEventListener('pointermove', hareket);
    window.addEventListener('pointerup', bitir);
    window.addEventListener('pointercancel', bitir);
    kare = window.requestAnimationFrame(dongu);
  };

  const genislet = (o: React.PointerEvent, j: number) => {
    if (o.button !== 0) return;
    o.preventDefault();
    o.stopPropagation();
    const x0 = o.clientX;
    const g0 = g.gen[j];
    const id = sutunlar[j].id;
    let son = g0;
    const hareket = (e: PointerEvent) => {
      son = Math.max(40, Math.round(g0 + (e.clientX - x0) / z));
      canliGen({ id, px: son });
    };
    const bitir = () => {
      window.removeEventListener('pointermove', hareket);
      window.removeEventListener('pointerup', bitir);
      canliGen(null);
      if (son !== g0) duzen.genislikYaz(id, son);
    };
    window.addEventListener('pointermove', hareket);
    window.addEventListener('pointerup', bitir);
  };

  /** Excel'deki gibi kenara çift tık: en uzun değere göre genişlik (ilk 3.000 satır). */
  const sigdir = (j: number) => {
    const c = sutunlar[j];
    const st = kap.current ? getComputedStyle(kap.current) : null;
    const yazi = st ? `${st.fontSize} ${st.fontFamily}` : '15px sans-serif';
    let en = olc(c.baslik, true, yazi) + 40;
    for (let i = 0; i < Math.min(satirlar.length, 3000); i++) en = Math.max(en, olc(c.deger(satirlar[i]), false, yazi) + 20);
    duzen.genislikYaz(c.id, Math.min(600, Math.ceil(en)));
  };

  const kose = <div className="xg-kose" role="columnheader" title="Tümünü seç (Ctrl+A)" onPointerDown={(o) => (o.preventDefault(), hepsiniSec())} />;

  return (
    <div className="xg-bas-kap" style={{ width: g.toplam }}>
      {harfler ? (
        <div className="xg-harfler" style={{ gridTemplateColumns: g.sablon, width: g.toplam }} aria-hidden="true">
          {kose}
          {sutunlar.map((c, j) => {
            const secili = alan && j >= alan.c1 && j <= alan.c2;
            return (
              <div
                key={c.id}
                className={`xg-harf${secili ? ' secili' : ''}${j < DONUK ? ' donuk' : ''}${j === DONUK - 1 ? ' donuk-son' : ''}`}
                style={j < DONUK ? { left: g.sol[j] } : undefined}
                title="Tıkla: sütunu seç · sürükle: sütun aralığı seç"
                onPointerDown={(o) => adBas(o, j)}
              >
                {sutunHarfi(j)}
              </div>
            );
          })}
        </div>
      ) : null}
      <div className="xg-bas" style={{ gridTemplateColumns: g.sablon, width: g.toplam }} role="row">
        {harfler ? <div className="xg-kose xg-kose-alt" role="columnheader" /> : kose}
        {sutunlar.map((c, j) => {
          const f = t.suzgec[c.id];
          const suzuk = suzgecEtkin(f);
          const sira = t.siralama?.id === c.id ? (t.siralama.yon === 1 ? ' ▲' : ' ▼') : '';
          const secili = alan && j >= alan.c1 && j <= alan.c2;
          const sinif = `xg-bh${suzuk ? ' suzuk' : ''}${secili ? ' secili' : ''}${j < DONUK ? ' donuk' : ''}${j === DONUK - 1 ? ' donuk-son' : ''}`;
          return (
            <div key={c.id} className={sinif} style={j < DONUK ? { left: g.sol[j] } : undefined} role="columnheader" aria-sort={sira ? (t.siralama?.yon === 1 ? 'ascending' : 'descending') : undefined}>
              <span className="xg-bh-ad" title={`${c.baslik} — tıkla: sütunu seç · sürükle: sütun aralığı seç`} onPointerDown={(o) => adBas(o, j)}>
                {c.baslik}
                {sira}
              </span>
              <button
                type="button"
                tabIndex={-1}
                className="xg-ok"
                aria-label={`${c.baslik} süzgeci`}
                title={suzuk ? 'Süzgeç uygulandı' : 'Süz ve sırala'}
                onMouseDown={(o) => o.stopPropagation()}
                onClick={(o) => {
                  const r = o.currentTarget.getBoundingClientRect();
                  menuAc(c.id, r.right, r.bottom);
                }}
              >
                {suzuk ? <Huni /> : '▾'}
              </button>
              <span className="xg-tutamak" title="Genişlik — çift tık: sığdır" onPointerDown={(o) => genislet(o, j)} onDoubleClick={() => sigdir(j)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
