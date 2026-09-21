/**
 * Seçim kartı — tek bina ya da site/mahalle grubu.
 * Tıklanan binanın künyesi, bölgesi ve "Bölgeye git" kısayolu.
 */
import { useMemo } from 'react';
import type { ReactNode } from 'react';

import { binaBolgeleri, veri } from '../data/load';
import { binaBilgisi, bolgeBul, sayi, temizAd, yuzde } from '../data/selectors';
import type { Plan } from '../data/types';
import IlerlemeCubugu from '../ui/IlerlemeCubugu';
import { boy, bosluk, renk, u, yazi } from '../ui/tema';
import type { Secim } from './durum';
import { Ikon } from './ikonlar';

export interface BinaKartiProps {
  plan: Plan;
  secim: Exclude<Secim, null>;
  onKapat: () => void;
  onBolgeyeGit: (no: number) => void;
}

function Satir({ etiket, deger }: { etiket: string; deger: ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: u(12) }}>
      <span style={{ fontSize: u(20), color: renk.metin3 }}>{etiket}</span>
      <span
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(28),
          color: renk.metin,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {deger}
      </span>
    </div>
  );
}

export default function BinaKarti({ plan, secim, onKapat, onBolgeyeGit }: BinaKartiProps) {
  const ozet = useMemo(() => {
    const b = veri().binalar;
    const bb = binaBolgeleri(plan);
    if (secim.tur === 'bina') {
      const i = secim.i;
      const bi = binaBilgisi(i, plan);
      return {
        baslik: temizAd(bi.ad) || 'Adsız bina',
        alt: [bi.mahalle, bi.ilce].filter(Boolean).join(' · ') + (bi.il && bi.il !== 'Bursa' ? ` · ${bi.il}` : ''),
        rozet: `Bina · ${bi.serial}`,
        bina: 1,
        kat: bi.kat,
        resHp: bi.resHp,
        aktif: bi.aktif,
        firsat: bi.firsat,
        bolge: bi.bolge,
      };
    }
    let resHp = 0;
    let aktif = 0;
    let firsat = 0;
    let kat = 0;
    const bolgeSayaci = new Map<number, number>();
    for (const i of secim.indeksler) {
      resHp += b.resHp[i];
      aktif += b.aktif[i];
      firsat += b.firsat[i];
      kat = Math.max(kat, b.kat[i]);
      const no = bb[i];
      bolgeSayaci.set(no, (bolgeSayaci.get(no) ?? 0) + 1);
    }
    let enCok = 0;
    let bolge = 0;
    for (const [no, c] of bolgeSayaci) {
      if (c > enCok) {
        enCok = c;
        bolge = no;
      }
    }
    return {
      baslik: secim.baslik,
      alt: secim.alt,
      rozet: `${secim.tip === 'site' ? 'Site' : 'Mahalle'} · ${sayi(secim.indeksler.length)} bina`,
      bina: secim.indeksler.length,
      kat,
      resHp,
      aktif,
      firsat,
      bolge,
    };
  }, [plan, secim]);

  const b = bolgeBul(plan, ozet.bolge);
  const pen = ozet.resHp > 0 ? Math.min(1, ozet.aktif / ozet.resHp) : 0;

  return (
    <div className="ks-cam ks-yanas" style={{ padding: u(20), flex: '0 0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: u(12) }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: u(boy.not), color: renk.metin3, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            {ozet.rozet}
          </div>
          <div
            style={{
              fontFamily: yazi.baslik,
              fontWeight: 700,
              fontSize: u(38),
              lineHeight: 1.05,
              color: renk.metin,
              marginTop: u(2),
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {ozet.baslik}
          </div>
          <div style={{ fontSize: u(boy.kucuk), color: renk.metin2, marginTop: u(2) }}>{ozet.alt}</div>
        </div>
        <button
          className="ks-dugme"
          style={{ width: u(38), height: u(38), borderRadius: u(10), flex: '0 0 auto' }}
          onClick={onKapat}
          title="Kapat (Esc)"
          aria-label="Kapat"
        >
          <Ikon ad="kapat" boyut={18} />
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: u(6), marginTop: u(bosluk.s) }}>
        {secim.tur === 'bina' ? (
          <Satir etiket="Kat" deger={sayi(ozet.kat)} />
        ) : (
          <Satir etiket="Bina" deger={sayi(ozet.bina)} />
        )}
        <Satir etiket="RES HP (hane)" deger={sayi(ozet.resHp)} />
        <Satir etiket="Aktif abone" deger={sayi(ozet.aktif)} />
        <Satir etiket="Fırsat" deger={sayi(ozet.firsat)} />
      </div>

      <div style={{ marginTop: u(10) }}>
        <Satir etiket="Penetrasyon" deger={ozet.resHp > 0 ? yuzde(pen) : '–'} />
        <div style={{ marginTop: u(6) }}>
          <IlerlemeCubugu oran={pen} kalinlik={8} renkKodu={b?.renk ?? renk.sari} gecisMs={500} />
        </div>
        {/*
          Kart RES HP / Aktif abone / Fırsat'ı HAM, penetrasyonu ise %100'e kırpılmış gösteriyor.
          Aboneyi HP'sini aşan 181 binada "3 hane · 6 abone · %100" kendi içinde çelişkili okunuyordu;
          Excel bunu BINA_ATAMA'nın "Not" sütunuyla açıklıyor, uygulama açıklamıyordu.
        */}
        {ozet.aktif > ozet.resHp && (
          <div style={{ fontSize: u(boy.not), color: renk.metin3, marginTop: u(6), lineHeight: 1.3 }}>
            {ozet.resHp > 0
              ? "Kaynak veride abone sayısı HP'yi aşıyor — penetrasyon %100 kabul edildi."
              : 'Konut HP kaydı yok, abone var — penetrasyon hesaplanamıyor.'}
          </div>
        )}
      </div>

      {b && (
        <button
          className="ks-dugme"
          onClick={() => onBolgeyeGit(b.bolge)}
          title={b.ad}
          style={{
            marginTop: u(bosluk.s),
            width: '100%',
            height: u(52),
            borderRadius: u(12),
            justifyContent: 'flex-start',
            padding: `0 ${u(14)}`,
            gap: u(12),
          }}
        >
          <span
            style={{
              width: u(12),
              height: u(12),
              borderRadius: '50%',
              background: b.renk,
              boxShadow: `0 0 ${u(12)} ${b.renk}aa`,
              flex: '0 0 auto',
            }}
          />
          <span style={{ fontSize: u(22), color: renk.metin, flex: 1, textAlign: 'left', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {b.kod} · {b.kisa_ad}
          </span>
          <span style={{ fontSize: u(boy.not), color: renk.metin3 }}>Bölgeye git</span>
          <Ikon ad="ok" boyut={18} />
        </button>
      )}
    </div>
  );
}
