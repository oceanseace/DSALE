/**
 * S3 · Fırsat — boş kapılar. Altıgen sütunlar bu kez fırsatı (boş RES hane) gösterir,
 * en yüksek dört mahalle çağrı balonuyla işaretlenir.
 */
import {
  altlik,
  binaIsiklari,
  hpSutunlari,
  ilceEtiketKatmani,
  katmanlar as kat,
  ofisIsaretcisi,
} from '../../map/katmanlar';
import { kisaSayi, onlukOran, sayi, yuzde } from '../../data/selectors';
import { boy, renk, u, yazi } from '../../ui/tema';
import { kolay, oran } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import Manset from '../bilesen/Manset';
import { duzen } from './duzen';

const TEMEL: [number, number, number, number] = [80, 110, 165, 255];
/** koyu bordo → kızıl → kehribar: "boş kapı" ısısı */
const PALET = ['#1A0A20', '#5B1748', '#A52A4E', '#E4553A', '#FFA52E', '#FFE08A'];
const VURGU = '#FFC400';

function ustMahalleler(meta: { ust_mahalleler: { ilce: string; mahalle: string; firsat: number; lon: number; lat: number }[] }) {
  return [...meta.ust_mahalleler].sort((a, b) => b.firsat - a.firsat).slice(0, 4);
}

export const s03Firsat: SahneTanimi = {
  id: 'firsat',
  ad: 'Fırsat',
  filmMs: () => 7500,
  girisMs: 3000,
  kamera: () => ({
    bas: { longitude: 28.935, latitude: 40.168, zoom: 11.2, pitch: 56, bearing: -30 },
    adimlar: [
      { durum: { longitude: 28.95, latitude: 40.178, zoom: 11.3, pitch: 54, bearing: -10 }, sureMs: 6500, tur: 'linear' },
    ],
  }),
  katmanlar: ({ t }) => {
    const buyume = kolay(oran(t, 0.2, 2.5));
    return kat(
      // ilçe adları en sonda: altıgen sütunlar yazıların üstüne biniyordu
      altlik({ gorunurluk: 0.8, ilceEtiketleri: false }),
      binaIsiklari({ renkModu: { tur: 'tek', renk: TEMEL }, alfa: 60, yaricap: 24 }),
      hpSutunlari({
        olcu: 'firsat',
        mod: 'hex',
        yaricap: 380,
        yukseklikOlcegi: 3.4,
        ilerleme: buyume,
        renkAraligi: PALET,
        pickable: false,
      }),
      // ofis etiketi burada kapalı: mahalle çağrı balonlarıyla çakışıyor, fener yeterli
      ofisIsaretcisi({ t, olcek: 0.7, yukseklik: 2600, etiket: false }),
      ilceEtiketKatmani({ etiketBoyutu: 20, gorunurluk: 0.8 }),
    );
  },
  cagrilar: ({ meta }) =>
    ustMahalleler(meta).map((m) => ({
      anahtar: `${m.ilce}|${m.mahalle}`,
      konum: [m.lon, m.lat] as [number, number],
      baslik: m.mahalle,
      alt: `${sayi(m.firsat)} boş kapı`,
      renk: VURGU,
    })),
  Katman: ({ b }) => {
    const top = b.meta.toplam;
    return (
      <Manset
        style={duzen.solAlt}
        ustluk="Fırsat"
        genislik={1100}
        baslik={
          <>
            <span style={{ color: renk.sari }}>{kisaSayi(top.firsat)} kapı</span> bizi bekliyor
          </>
        }
        alt={
          <span>
            Penetrasyon {yuzde(b.meta.penetrasyon, 1)} ·{' '}
            <span style={{ color: renk.metin, fontFamily: yazi.baslik, fontSize: u(boy.alt) }}>
              {onlukOran(top.firsat, top.res_hp)}
            </span>{' '}
            hâlâ boş
          </span>
        }
      />
    );
  },
};

export default s03Firsat;
