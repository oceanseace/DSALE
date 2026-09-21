/**
 * Üst çubuk: marka · N seçici · renk (metrik) seçici · arama · araç düğmeleri.
 * 1366×768'de de aynı kompozisyon (tüm ölçüler tasarım pikseli).
 */
import { forwardRef } from 'react';

import type { Plan } from '../data/types';
import Marka from '../ui/Marka';
import { boy, renk, u } from '../ui/tema';
import AramaKutusu from './AramaKutusu';
import type { AramaSonucu } from './arama';
import type { Gorunum, Metrik } from './durum';
import { Ikon, type IkonAdi } from './ikonlar';
import NSecici from './NSecici';

const METRIKLER: { deger: Metrik; etiket: string; ipucu: string }[] = [
  { deger: 'bolge', etiket: 'Bölge', ipucu: 'Binaları bölge rengine boyar' },
  { deger: 'firsat', etiket: 'Fırsat', ipucu: 'Boş konut HP yoğunluğu' },
  { deger: 'penetrasyon', etiket: 'Penetrasyon', ipucu: 'Aktif abone / RES HP' },
];

export interface UstBarProps {
  plan: Plan;
  n: number;
  metrik: Metrik;
  gorunum: Gorunum;
  arama: string;
  aramaAcik: boolean;
  onN: (n: number) => void;
  onMetrik: (m: Metrik) => void;
  onGorunum: (g: Gorunum) => void;
  onArama: (metin: string) => void;
  onAramaAcik: (acik: boolean) => void;
  onAramaSec: (s: AramaSonucu) => void;
  onBasaDon: () => void;
  onPlanAc: () => void;
  onTamEkran: () => void;
  onSunum: () => void;
}

function AracDugme({
  ikon,
  etiket,
  ipucu,
  secili,
  onTikla,
}: {
  ikon: IkonAdi;
  etiket: string;
  ipucu: string;
  secili?: boolean;
  onTikla: () => void;
}) {
  return (
    <button className="ks-dugme ks-arac" data-secili={secili ? '1' : '0'} onClick={onTikla} title={ipucu}>
      <Ikon ad={ikon} boyut={26} />
      <span>{etiket}</span>
    </button>
  );
}

const UstBar = forwardRef<HTMLInputElement, UstBarProps>(function UstBar(p, aramaRef) {
  const ikiBoyut = p.gorunum === '2b';
  return (
    <div className="ks-ust">
      <Marka alt="Keşif" boyut={26} />

      <div className="ks-ayirac" />
      <NSecici plan={p.plan} n={p.n} onDegis={p.onN} />

      <div className="ks-ayirac" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: u(5) }}>
        <span style={{ fontSize: u(boy.not), color: renk.metin3, letterSpacing: '0.14em', textTransform: 'uppercase' }}>
          Renk
        </span>
        <div className="ks-segment">
          {METRIKLER.map((m) => (
            <button
              key={m.deger}
              data-secili={p.metrik === m.deger ? '1' : '0'}
              onClick={() => p.onMetrik(m.deger)}
              title={m.ipucu}
            >
              {m.etiket}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex: 1 }} />

      <AramaKutusu
        ref={aramaRef}
        plan={p.plan}
        metin={p.arama}
        acik={p.aramaAcik}
        onMetin={p.onArama}
        onAcik={p.onAramaAcik}
        onSec={p.onAramaSec}
      />

      <div style={{ display: 'flex', gap: u(8) }}>
        <AracDugme
          ikon={ikiBoyut ? 'kup' : 'duz'}
          etiket={ikiBoyut ? '3B' : '2B'}
          ipucu={ikiBoyut ? '3B görünüme dön (3)' : 'Kuşbakışı 2B görünüm (2)'}
          onTikla={() => p.onGorunum(ikiBoyut ? '3b' : '2b')}
        />
        <AracDugme ikon="basaDon" etiket="Başa dön" ipucu="Tüm bölgeler (Home)" onTikla={p.onBasaDon} />
        <AracDugme ikon="dosya" etiket="Plan aç" ipucu="Dosyadan plan yükle (O)" onTikla={p.onPlanAc} />
        <AracDugme ikon="tamEkran" etiket="Tam ekran" ipucu="Tam ekran (F)" onTikla={p.onTamEkran} />
        <AracDugme ikon="sunum" etiket="Sunum" ipucu="Sunuma dön (K)" onTikla={p.onSunum} />
      </div>
    </div>
  );
});

export default UstBar;
