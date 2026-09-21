/** Katman anahtarları — binalar, bölge sınırları, ısı sütunları, yollar, ofis bağlantıları. */
import type { KatmanAdi, Katmanlar } from './durum';
import { Ikon, type IkonAdi } from './ikonlar';
import { boy, renk, u } from '../ui/tema';

const CIPLER: { ad: KatmanAdi; etiket: string; ikon: IkonAdi; ipucu: string }[] = [
  { ad: 'binalar', etiket: 'Binalar', ikon: 'bina', ipucu: 'Binaların 3B gövdesi' },
  { ad: 'sinirlar', etiket: 'Sınırlar', ikon: 'sinir', ipucu: 'Bölge sınırı ve dolgusu' },
  { ad: 'yollar', etiket: 'Yollar', ikon: 'yol', ipucu: 'Yol ağı (OpenStreetMap)' },
  { ad: 'sutun', etiket: 'Isı sütunları', ikon: 'sutun', ipucu: 'Altıgen ızgarada yoğunluk' },
  { ad: 'ofis', etiket: 'Ofis & yaylar', ikon: 'ofis', ipucu: 'Ofis işaretçisi ve bölgelere bağlantı' },
];

export interface KatmanKartiProps {
  katman: Katmanlar;
  onDegis: (ad: KatmanAdi) => void;
}

export default function KatmanKarti({ katman, onDegis }: KatmanKartiProps) {
  return (
    <div className="ks-cam" style={{ padding: u(16), flex: '0 0 auto' }}>
      <div
        style={{
          fontSize: u(boy.not),
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          color: renk.metin3,
          marginBottom: u(10),
        }}
      >
        Katmanlar
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: u(8) }}>
        {CIPLER.map((c) => (
          <button
            key={c.ad}
            className="ks-dugme"
            data-secili={katman[c.ad] ? '1' : '0'}
            onClick={() => onDegis(c.ad)}
            title={c.ipucu}
            style={{
              height: u(44),
              padding: `0 ${u(12)}`,
              fontSize: u(19),
              borderRadius: u(11),
              opacity: katman[c.ad] ? 1 : 0.55,
            }}
          >
            <Ikon ad={c.ikon} boyut={21} />
            {c.etiket}
          </button>
        ))}
      </div>
    </div>
  );
}
