/**
 * "Bizim durum" hücresinin açılır listesi — Excel'deki veri doğrulama listesi gibi: hücre seçiliyken ▾,
 * Alt+↓ ya da çift tık açar; ok tuşları + Enter seçer. Seçim Bizim durum sütununda birden çok satırı
 * kapsıyorsa değer hepsine yazılır. Giriş: <BizimListesi …/>. Kim: Tablo.tsx. Değerler: cekirdek/is/api.ts.
 */

import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { BIZIM_DURUMLAR } from '../../../cekirdek/is/api';
import { useDisariKapat, useEkranaSigdir } from './acilir';

const SECENEKLER: Array<string | null> = [null, ...BIZIM_DURUMLAR];

export function BizimListesi({
  x,
  y,
  deger,
  satirSayisi,
  sec,
  kapat,
}: {
  x: number;
  y: number;
  deger: string | null;
  satirSayisi: number;
  sec: (v: string | null) => void;
  kapat: () => void;
}) {
  const kok = useRef<HTMLDivElement>(null);
  const [imlec, setImlec] = useState(() => Math.max(0, SECENEKLER.indexOf(deger)));
  useDisariKapat(kok, kapat);
  useEkranaSigdir(kok);
  useEffect(() => kok.current?.focus(), []);

  const tus = (o: React.KeyboardEvent) => {
    if (o.key === 'ArrowDown' || o.key === 'ArrowUp') {
      o.preventDefault();
      setImlec((i) => (i + (o.key === 'ArrowDown' ? 1 : -1) + SECENEKLER.length) % SECENEKLER.length);
    } else if (o.key === 'Enter' || o.key === 'Tab') {
      o.preventDefault();
      sec(SECENEKLER[imlec]);
    }
  };

  return createPortal(
    <div
      className="xg-menu xg-bizim"
      ref={kok}
      tabIndex={-1}
      role="listbox"
      aria-label="Bizim durum"
      style={{ left: Math.min(x, window.innerWidth - 220), top: Math.min(y, window.innerHeight - 320) }}
      onKeyDown={tus}
      onMouseDown={(o) => o.preventDefault()}
    >
      {satirSayisi > 1 ? <div className="xg-menu-etiket">{satirSayisi.toLocaleString('tr-TR')} satıra yazılır</div> : null}
      {SECENEKLER.map((v, i) => (
        <button
          key={v ?? '-'}
          type="button"
          role="option"
          aria-selected={v === deger}
          className={`xg-menu-satir${i === imlec ? ' imlec' : ''}${v === deger ? ' secili' : ''}`}
          onMouseEnter={() => setImlec(i)}
          onClick={() => sec(v)}
        >
          {v ?? '(boş)'}
        </button>
      ))}
    </div>,
    document.body,
  );
}
