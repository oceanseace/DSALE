/**
 * Arama kutusu ve sonuç listesi.
 * Mahalle girdileri (ilçe, mahalle) çiftiyle anahtarlanır; site grupları birim bazlıdır.
 * `/` ya da Ctrl+F odaklar, ↑ ↓ gezinir, Enter seçer, Esc kapatır.
 */
import { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as TepkiTusOlayi } from 'react';

import { binaBolgeleri } from '../data/load';
import { bolgeBul, sayi } from '../data/selectors';
import type { Plan } from '../data/types';
import { boy, renk, u, yazi } from '../ui/tema';
import { ara, dizinHazirla, type AramaSonucu } from './arama';
import { Ikon } from './ikonlar';

const TUR_ADI: Record<AramaSonucu['tur'], string> = { mahalle: 'Mahalle', site: 'Site', bina: 'Bina' };
const TUR_IKON = { mahalle: 'mahalle', site: 'site', bina: 'bina' } as const;

export interface AramaKutusuProps {
  plan: Plan;
  metin: string;
  acik: boolean;
  onMetin: (metin: string) => void;
  onAcik: (acik: boolean) => void;
  onSec: (s: AramaSonucu) => void;
}

/** Eşleşen parçayı kalınlaştırır (birebir bulunamazsa düz yazar). */
function Vurgulu({ ad, sorgu }: { ad: string; sorgu: string }) {
  const q = sorgu.trim();
  if (q.length < 2) return <>{ad}</>;
  const i = ad.toLocaleLowerCase('tr-TR').indexOf(q.toLocaleLowerCase('tr-TR'));
  if (i < 0) return <>{ad}</>;
  return (
    <>
      {ad.slice(0, i)}
      <span style={{ color: renk.sari }}>{ad.slice(i, i + q.length)}</span>
      {ad.slice(i + q.length)}
    </>
  );
}

const AramaKutusu = forwardRef<HTMLInputElement, AramaKutusuProps>(function AramaKutusu(
  { plan, metin, acik, onMetin, onAcik, onSec },
  ref,
) {
  const [etkin, setEtkin] = useState(0);
  const kapsayici = useRef<HTMLDivElement>(null);
  const sonuclar = useMemo(() => (metin.trim().length >= 2 ? ara(metin, 8) : []), [metin]);
  const bb = useMemo(() => binaBolgeleri(plan), [plan]);

  useEffect(() => setEtkin(0), [metin]);

  // dışarı tıklayınca kapan
  useEffect(() => {
    if (!acik) return;
    const tikla = (e: MouseEvent) => {
      if (!kapsayici.current?.contains(e.target as Node)) onAcik(false);
    };
    window.addEventListener('mousedown', tikla);
    return () => window.removeEventListener('mousedown', tikla);
  }, [acik, onAcik]);

  const tus = (e: TepkiTusOlayi<HTMLInputElement>) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!sonuclar.length) return;
      setEtkin((k) => (k + (e.key === 'ArrowDown' ? 1 : sonuclar.length - 1)) % sonuclar.length);
      onAcik(true);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const s = sonuclar[etkin];
      if (s) onSec(s);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (acik && sonuclar.length) onAcik(false);
      else {
        onMetin('');
        (e.target as HTMLInputElement).blur();
      }
    }
  };

  return (
    <div ref={kapsayici} style={{ position: 'relative', width: u(400) }}>
      <div className="ks-arama-kutu">
        <Ikon ad="ara" boyut={24} style={{ color: renk.metin3 }} />
        <input
          ref={ref}
          value={metin}
          placeholder="Mahalle, site ya da bina ara…"
          onChange={(e) => onMetin(e.target.value)}
          onFocus={() => {
            dizinHazirla();
            if (metin.trim()) onAcik(true);
          }}
          onKeyDown={tus}
          spellCheck={false}
          aria-label="Ara"
        />
        {metin && (
          <button
            className="ks-dugme"
            style={{ width: u(30), height: u(30), borderRadius: u(8), border: 'none', background: 'transparent' }}
            onClick={() => {
              onMetin('');
              onAcik(false);
            }}
            title="Temizle"
            aria-label="Temizle"
          >
            <Ikon ad="kapat" boyut={16} />
          </button>
        )}
      </div>

      {acik && sonuclar.length > 0 && (
        <div
          className="ks-cam ks-belir ks-kaydir"
          style={{
            position: 'absolute',
            top: u(66),
            right: 0,
            width: u(520),
            maxHeight: u(604),
            padding: u(8),
            zIndex: 30,
          }}
        >
          {sonuclar.map((s, k) => {
            const b = bolgeBul(plan, bb[s.ilkIndeks]);
            return (
              <button
                key={s.anahtar}
                className="ks-sonuc"
                data-etkin={k === etkin ? '1' : '0'}
                onMouseEnter={() => setEtkin(k)}
                onClick={() => onSec(s)}
              >
                <span style={{ color: renk.metin3, display: 'flex' }}>
                  <Ikon ad={TUR_IKON[s.tur]} boyut={22} />
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span
                    style={{
                      display: 'block',
                      fontFamily: yazi.baslik,
                      fontWeight: 600,
                      fontSize: u(26),
                      color: renk.metin,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      lineHeight: 1.15,
                    }}
                  >
                    <Vurgulu ad={s.ad} sorgu={metin} />
                  </span>
                  <span
                    style={{
                      display: 'block',
                      fontSize: u(boy.not),
                      color: renk.metin3,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {TUR_ADI[s.tur]} · {s.yer}
                  </span>
                </span>
                <span
                  style={{
                    fontSize: u(boy.kucuk),
                    color: renk.metin2,
                    fontVariantNumeric: 'tabular-nums',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {sayi(s.resHp)} hane
                </span>
                {b && (
                  <span
                    title={`${b.kod} · ${b.kisa_ad}`}
                    style={{
                      width: u(12),
                      height: u(12),
                      borderRadius: '50%',
                      background: b.renk,
                      boxShadow: `0 0 ${u(10)} ${b.renk}aa`,
                      flex: '0 0 auto',
                    }}
                  />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
});

export default AramaKutusu;
