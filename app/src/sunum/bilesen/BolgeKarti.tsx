/**
 * S6 bölge turu kartı: kod rozeti + tam ad + üç rakam (hane · büyüme payı · bina) + etiketler.
 *
 * Kurallar (denetim bulguları):
 *  - Ofise uzaklık kartta YOK; onun yerine uzak bölgeler "Araçlı bölge" etiketi alır.
 *  - Sapma renkli dolgu değil, nötr yazı + ✓/▲/▼ işareti.
 *  - Bölgenin TAM adı yazılır (kısaltma yok).
 */
import type { CSSProperties, ReactNode } from 'react';

import { onlukOran, sayi, isaretliYuzde } from '../../data/selectors';
import type { Bolge } from '../../data/types';
import { boy, bosluk, durumIsareti, golge, renk, u, yazi } from '../../ui/tema';

export interface BolgeKartiProps {
  bolge: Bolge;
  /** hedef ölçü değeri (plan.hedef) */
  hedef: number;
  /** kaçıncı bölge / toplam (mini noktalar) */
  sira: number;
  toplam: number;
  /** "Araçlı bölge" etiketi eşiği (km) */
  aracEsigi?: number;
  style?: CSSProperties;
}

function Etiket({ metin, renkKodu }: { metin: string; renkKodu: string }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: u(8),
        padding: `${u(7)} ${u(16)}`,
        borderRadius: u(999),
        background: 'rgba(255,255,255,0.06)',
        border: `1px solid ${renk.cizgi}`,
        fontFamily: yazi.govde,
        fontSize: u(boy.kucuk),
        color: renkKodu,
        whiteSpace: 'nowrap',
      }}
    >
      {metin}
    </span>
  );
}

function Satir({
  etiket,
  deger,
  alt,
  boyut,
  renkKodu,
}: {
  etiket: string;
  deger: string;
  alt?: ReactNode;
  boyut: number;
  renkKodu?: string;
}) {
  return (
    <div style={{ marginTop: u(bosluk.m) }}>
      <div
        style={{
          fontFamily: yazi.govde,
          fontSize: u(boy.not),
          letterSpacing: '0.2em',
          textTransform: 'uppercase',
          color: renk.metin3,
          marginBottom: u(4),
        }}
      >
        {etiket}
      </div>
      <div
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(boyut),
          lineHeight: 1,
          color: renkKodu ?? renk.metin,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {deger}
      </div>
      {alt != null && (
        <div style={{ fontFamily: yazi.govde, fontSize: u(boy.govde), color: renk.metin2, marginTop: u(6) }}>{alt}</div>
      )}
    </div>
  );
}

export default function BolgeKarti({ bolge, hedef, sira, toplam, aracEsigi = 15, style }: BolgeKartiProps) {
  const d = durumIsareti(bolge.sapma);
  const arac = bolge.ofis_km > aracEsigi;
  return (
    <div style={{ width: u(660), ...style }}>
      <div
        className="s-sag"
        style={{
          background: 'rgba(5,11,24,0.82)',
          border: `1px solid ${renk.cizgi}`,
          borderRadius: u(22),
          boxShadow: golge.panel,
          backdropFilter: 'blur(16px)',
          padding: u(bosluk.l),
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: u(8),
            background: bolge.renk,
            boxShadow: golge.parlama(bolge.renk),
          }}
        />
        <div style={{ display: 'flex', alignItems: 'baseline', gap: u(18) }}>
          <span
            style={{
              fontFamily: yazi.baslik,
              fontWeight: 800,
              fontSize: u(boy.baslik),
              lineHeight: 1,
              color: bolge.renk,
              textShadow: `0 0 ${u(26)} ${bolge.renk}66`,
            }}
          >
            {bolge.kod}
          </span>
          <span
            style={{
              fontFamily: yazi.baslik,
              fontWeight: 700,
              fontSize: u(boy.buyuk),
              lineHeight: 1.12,
              color: renk.metin,
            }}
          >
            {bolge.ad}
          </span>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: u(10), marginTop: u(bosluk.s) }}>
          <Etiket metin={`${sayi(bolge.mahalle_sayisi)} mahalle`} renkKodu={renk.metin2} />
          {arac && <Etiket metin="Araçlı bölge" renkKodu={renk.sari} />}
          {bolge.yalova_bina > 0 && (
            <Etiket metin={`Yalova · ${sayi(bolge.yalova_bina)} bina`} renkKodu={renk.sari} />
          )}
        </div>

        <Satir
          etiket="RES hane"
          deger={sayi(bolge.res_hp)}
          boyut={boy.dev * 0.62}
          alt={
            <span style={{ color: d.renk }}>
              {d.ikon} {d.seviye === 'iyi' ? 'hedefte' : 'hedef dışı'} · {isaretliYuzde(bolge.sapma)} · hedef{' '}
              {sayi(hedef)}
            </span>
          }
        />
        <Satir
          etiket="Büyüme payı (fırsat)"
          deger={sayi(bolge.firsat)}
          boyut={boy.alt}
          renkKodu={bolge.renk}
          alt={`${onlukOran(bolge.firsat, bolge.res_hp)} hâlâ boş`}
        />
        <Satir etiket="Bina" deger={sayi(bolge.bina)} boyut={boy.alt} />
      </div>

      <div style={{ display: 'flex', gap: u(8), marginTop: u(bosluk.s), justifyContent: 'flex-end' }}>
        {Array.from({ length: toplam }, (_, i) => (
          <span
            key={i}
            style={{
              width: i + 1 === sira ? u(28) : u(10),
              height: u(10),
              borderRadius: u(999),
              background: i + 1 === sira ? bolge.renk : 'rgba(244,247,255,0.25)',
              transition: 'width 300ms cubic-bezier(0.22,1,0.36,1)',
            }}
          />
        ))}
      </div>
    </div>
  );
}
