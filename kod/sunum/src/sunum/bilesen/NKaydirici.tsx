/**
 * S9 büyüme kaydırıcısı: ekip büyüdükçe harita yeniden bölünür.
 *
 * Yalnız DENGELİ planlarda durur (`dengeliPlanlar`) — listeyi çağıran verir, burada sabit yok.
 * ↑/↓ ile bir adım, sürükleyerek serbest. Kaydırıcı `data-etkilesim="1"` taşıdığı için
 * üzerindeki tıklama sahneyi ilerletmez.
 */
import { useCallback, useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';

import { sayi } from '../../data/selectors';
import { boy, renk, u, yazi } from '../../ui/tema';

export interface NKaydiriciProps {
  /** seçilebilir N listesi (artan) */
  nler: number[];
  n: number;
  setN: (n: number) => void;
  /** işaretlenecek N'ler: { N: etiket } */
  isaretler?: Record<number, string>;
  /** klavye (↑/↓) açık mı */
  klavye?: boolean;
  style?: CSSProperties;
}

export default function NKaydirici({ nler, n, setN, isaretler = {}, klavye = true, style }: NKaydiriciProps) {
  const ray = useRef<HTMLDivElement>(null);
  const basili = useRef(false);
  const durum = useRef({ nler, n, setN });
  durum.current = { nler, n, setN };

  const indeks = Math.max(0, nler.indexOf(n));
  const oran = nler.length > 1 ? indeks / (nler.length - 1) : 0;

  const konumdanSec = useCallback((clientX: number) => {
    const el = ray.current;
    const { nler: liste, setN: ata } = durum.current;
    if (!el || liste.length === 0) return;
    const r = el.getBoundingClientRect();
    const o = Math.max(0, Math.min(1, (clientX - r.left) / Math.max(1, r.width)));
    const yeni = liste[Math.round(o * (liste.length - 1))];
    if (yeni != null && yeni !== durum.current.n) ata(yeni);
  }, []);

  useEffect(() => {
    const hareket = (e: PointerEvent) => basili.current && konumdanSec(e.clientX);
    const birak = () => {
      basili.current = false;
    };
    window.addEventListener('pointermove', hareket);
    window.addEventListener('pointerup', birak);
    return () => {
      window.removeEventListener('pointermove', hareket);
      window.removeEventListener('pointerup', birak);
    };
  }, [konumdanSec]);

  useEffect(() => {
    if (!klavye) return;
    const tus = (e: KeyboardEvent) => {
      if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
      const { nler: liste, n: simdi, setN: ata } = durum.current;
      const i = Math.max(0, liste.indexOf(simdi));
      const yeni = liste[Math.max(0, Math.min(liste.length - 1, i + (e.key === 'ArrowUp' ? 1 : -1)))];
      if (yeni != null && yeni !== simdi) {
        e.preventDefault();
        ata(yeni);
      }
    };
    window.addEventListener('keydown', tus);
    return () => window.removeEventListener('keydown', tus);
  }, [klavye]);

  return (
    <div
      data-etkilesim="1"
      style={{ pointerEvents: 'auto', width: u(1120), fontFamily: yazi.govde, ...style }}
      onPointerDown={(e) => {
        basili.current = true;
        konumdanSec(e.clientX);
      }}
    >
      <div
        ref={ray}
        style={{
          position: 'relative',
          height: u(16),
          borderRadius: u(999),
          background: 'rgba(244,247,255,0.12)',
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${oran * 100}%`,
            borderRadius: u(999),
            background: `linear-gradient(90deg, ${renk.mavi}, ${renk.sari})`,
            transition: 'width 320ms cubic-bezier(0.22,1,0.36,1)',
          }}
        />
        {nler.map((x, i) => (
          <span
            key={x}
            style={{
              position: 'absolute',
              left: `${(i / Math.max(1, nler.length - 1)) * 100}%`,
              top: '50%',
              width: u(2),
              height: isaretler[x] ? u(26) : u(8),
              marginTop: isaretler[x] ? u(-13) : u(-4),
              background: isaretler[x] ? 'rgba(244,247,255,0.7)' : 'rgba(244,247,255,0.22)',
            }}
          />
        ))}
        <span
          style={{
            position: 'absolute',
            left: `${oran * 100}%`,
            top: '50%',
            width: u(34),
            height: u(34),
            marginLeft: u(-17),
            marginTop: u(-17),
            borderRadius: '50%',
            background: renk.sari,
            boxShadow: `0 0 ${u(26)} ${renk.sari}aa, 0 4px 14px rgba(0,0,0,0.6)`,
            transition: 'left 320ms cubic-bezier(0.22,1,0.36,1)',
          }}
        />
      </div>
      <div style={{ position: 'relative', height: u(46), marginTop: u(12) }}>
        {nler.map((x, i) =>
          isaretler[x] ? (
            <span
              key={x}
              style={{
                position: 'absolute',
                left: `${(i / Math.max(1, nler.length - 1)) * 100}%`,
                transform: 'translateX(-50%)',
                textAlign: 'center',
                fontSize: u(boy.kucuk),
                color: x === n ? renk.sari : renk.metin3,
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{ display: 'block', fontFamily: yazi.baslik, fontWeight: 700, fontSize: u(boy.govde) }}>
                {sayi(x)}
              </span>
              {isaretler[x]}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}
