/**
 * S1 · Açılış — "Bursa Fiber Satış Haritası".
 *
 * Fiber ofisten dalga hâlinde yayılır: binalar ofis mesafesine göre açılır, şehir yükselir,
 * sarı fener yanar. Tek cümle, tek başlık; rakamlar S2'de.
 */
import { altlik, binaIsiklari, binalar3D, katmanlar as kat, ofisIsaretcisi } from '../../map/katmanlar';
import { sayi } from '../../data/selectors';
import { boy, renk, u, yazi } from '../../ui/tema';
import { kolay, oran } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import Manset from '../bilesen/Manset';
import { duzen } from './duzen';

/** şehir rengi — bölge paletinden ve marka sarısından uzak, soğuk buz mavisi */
const SEHIR: [number, number, number, number] = [104, 164, 235, 255];
const ISIK: [number, number, number, number] = [150, 205, 255, 255];

const GIRIS_SN = 3.4;

export const s01Acilis: SahneTanimi = {
  id: 'acilis',
  ad: 'Açılış',
  filmMs: () => 8000,
  girisMs: 3600,
  kamera: () => ({
    bas: { longitude: 29.02, latitude: 40.16, zoom: 10.7, pitch: 38, bearing: -44 },
    adimlar: [
      {
        durum: { longitude: 29.005, latitude: 40.185, zoom: 11.85, pitch: 58, bearing: -26 },
        sureMs: 3300,
        tur: 'linear',
      },
    ],
    orbit: 1.1,
  }),
  katmanlar: ({ t }) => {
    const gorunur = kolay(oran(t, 0, 1.5));
    const dalga = 3 + 95 * kolay(oran(t, 0.15, 3.1));
    const yukseklik = 0.2 + 2.2 * kolay(oran(t, 0.3, 2.9));
    const acildi = t > GIRIS_SN;
    return kat(
      altlik({ gorunurluk: gorunur }),
      binalar3D({
        renkModu: { tur: 'tek', renk: SEHIR },
        yukseklikOlcegi: yukseklik,
        gorunurYaricapKm: acildi ? null : dalga,
        pickable: false,
      }),
      binaIsiklari({
        renkModu: { tur: 'tek', renk: ISIK },
        alfa: Math.round(85 * gorunur),
        yaricap: 22,
        gorunurYaricapKm: acildi ? null : dalga,
      }),
      ofisIsaretcisi({ t, olcek: kolay(oran(t, 0.1, 1.3)) * 1.35, yukseklik: 2400, halkaYaricapi: 2400 }),
    );
  },
  Katman: ({ b }) => (
    <Manset
      style={duzen.solAlt}
      baslik={b.meta.baslik}
      baslikBoyu={boy.dev}
      alt={
        <span style={{ fontFamily: yazi.govde }}>
          {b.meta.organizasyon}
          <span style={{ display: 'block', marginTop: u(10), color: renk.metin3, fontSize: u(boy.govde) }}>
            {sayi(b.meta.ilce_sayisi)} ilçe · {sayi(b.meta.mahalle_sayisi)} mahalle ·{' '}
            {sayi(b.meta.ekip.sorumlu_sayisi)} satış sorumlusu
          </span>
        </span>
      }
    />
  ),
};

export default s01Acilis;
