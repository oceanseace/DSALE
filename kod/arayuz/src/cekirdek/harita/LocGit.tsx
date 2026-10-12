/**
 * "Location ID ile git" — haritanın üstünde yüzen arama kutusu.
 *
 * Location ID, BN (bina seri no) ya da site adı yazılır; yazarken haritadaki
 * binalardan öneriler çıkar (Türkçe harf duyarsız). Enter ya da öneri seçilince
 * kamera uçar, bina iğne + halka ile vurgulanır. Haritada yoksa sunucuya
 * sorulur (yetki süzgeci orada); yine yoksa nazik uyarı.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { noktaAra, type AranirNokta, type HedefDurumu } from './hedefKatman';
import { SimgeDugme } from '../ortak/Ilkel';
import { Buyutec, Kapat } from '../ortak/Ikon';
import './harita.css';

export function LocGit<T extends AranirNokta>({
  noktalar,
  hedef,
  yuzen = true,
}: {
  noktalar: readonly T[];
  hedef: HedefDurumu;
  /** Kendi kutusunu (cam zemin) çizsin mi; panel içindeyse false. */
  yuzen?: boolean;
}) {
  const [metin, setMetin] = useState('');
  const [odak, setOdak] = useState(false);
  const [imlec, setImlec] = useState(0);
  const girdi = useRef<HTMLInputElement | null>(null);
  const oneriler = useMemo(() => (metin.trim().length >= 2 ? noktaAra(noktalar, metin, 6) : []), [noktalar, metin]);
  useEffect(() => setImlec(0), [metin]);

  const git = (n?: T) => {
    const q = metin.trim();
    if (n) {
      hedef.git({ serial: n.serial, lat: n.konum[1], lon: n.konum[0], etiket: n.ad });
    } else if (q.length >= 2) {
      hedef.git({ sorgu: q });
    } else return;
    girdi.current?.blur();
    setOdak(false);
  };

  const acik = odak && oneriler.length > 0;

  return (
    <div className={`hr-locgit${yuzen ? ' yuzen' : ''}${hedef.uyari ? ' uyarili' : ''}`}>
      <form
        className="hr-locgit-kutu"
        role="search"
        onSubmit={(o) => {
          o.preventDefault();
          git(oneriler[imlec]);
        }}
      >
        <Buyutec boyut={16} className="hr-locgit-simge" />
        <input
          ref={girdi}
          value={metin}
          onChange={(o) => setMetin(o.target.value)}
          onFocus={() => setOdak(true)}
          onBlur={() => setTimeout(() => setOdak(false), 120)}
          onKeyDown={(o) => {
            if (o.key === 'ArrowDown' && oneriler.length) {
              o.preventDefault();
              setImlec((i) => (i + 1) % oneriler.length);
            } else if (o.key === 'ArrowUp' && oneriler.length) {
              o.preventDefault();
              setImlec((i) => (i - 1 + oneriler.length) % oneriler.length);
            } else if (o.key === 'Escape') {
              setMetin('');
              hedef.temizle();
              girdi.current?.blur();
            }
          }}
          placeholder="Location ID ile git"
          aria-label="Location ID, BN ya da site adı ile haritada git"
          inputMode="search"
          enterKeyHint="go"
          autoComplete="off"
          spellCheck={false}
          data-palet-disi="1"
        />
        {metin ? (
          <SimgeDugme
            kucuk
            etiket="Temizle"
            onMouseDown={(o) => o.preventDefault()}
            onClick={() => {
              setMetin('');
              hedef.temizle();
              girdi.current?.focus();
            }}
          >
            <Kapat boyut={14} kalinlik={2} />
          </SimgeDugme>
        ) : null}
      </form>
      {acik ? (
        <ul className="hr-locgit-oneri" role="listbox" aria-label="Haritadaki eşleşmeler">
          {oneriler.map((n, i) => (
            <li key={n.serial} role="option" aria-selected={i === imlec}>
              <button
                type="button"
                className={i === imlec ? 'etkin' : undefined}
                onMouseDown={(o) => o.preventDefault()}
                onMouseEnter={() => setImlec(i)}
                onClick={() => git(n)}
              >
                <span className="ad">{n.ad || n.serial}</span>
                <span className="kimlik">{n.loc ? `LOC ${n.loc}` : n.serial}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {hedef.uyari ? (
        <div className="hr-locgit-uyari" role="status">
          {hedef.uyari}
        </div>
      ) : null}
    </div>
  );
}
