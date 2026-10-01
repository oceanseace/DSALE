/**
 * S10 · Kapanış — bütün saha, sekiz renk, akan yaylar ve tek kelime: "Hazırız."
 */
import { bolgeEtiketNoktasi } from '../../data/load';
import { kisaSayi, sayi, tumSinirKutusu } from '../../data/selectors';
import {
  altlik,
  arklar,
  binaIsiklari,
  binalar3D,
  bolgeSinirlari,
  katmanlar as kat,
  ofisIsaretcisi,
} from '../../map/katmanlar';
import { boy, renk, u, uPx, yazi } from '../../ui/tema';
import { kolay, ofisCagrisi, oran, sigdirEgik } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import { duzen } from './duzen';

export const s10Kapanis: SahneTanimi = {
  id: 'kapanis',
  ad: 'Kapanış',
  filmMs: () => 6000,
  girisMs: 2800,
  kamera: () => ({
    bas: ({ api }) =>
      sigdirEgik(api, tumSinirKutusu(), {
        padding: { left: uPx(560), right: uPx(80), top: uPx(120), bottom: uPx(240) },
        pitch: 40,
        bearing: -22,
        maksZoom: 12.5,
      }),
    orbit: 0.8,
  }),
  katmanlar: ({ plan, t }) =>
    kat(
      altlik({ gorunurluk: 0.85, etiketBoyutu: 19 }),
      bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 46 }),
      binalar3D({ plan, yukseklikOlcegi: 0.95, pickable: false }),
      binaIsiklari({ plan, alfa: 175, yaricap: 46, minPiksel: 2 }),
      bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: 2.4 }),
      arklar({ plan, ilerleme: kolay(oran(t, 0.2, 1.8)), t: t > 1.8 ? t : null, genislik: 2.8 }),
      // Kapanış karesi patronun en uzun baktığı kare: ofis rozeti ile bölge çipleri aynı
      // çakışma çözücüden geçsin diye ikisi de HTML çağrı katmanında.
      ofisIsaretcisi({ t, olcek: 1, yukseklik: 5200, etiket: false }),
    ),
  cagrilar: ({ plan, meta }) => [
    ofisCagrisi(meta, { sap: 132 }),
    ...plan.bolgeler.map((b) => ({
      anahtar: b.kod,
      konum: bolgeEtiketNoktasi(b),
      baslik: b.kod,
      renk: b.renk,
      kucuk: true,
      sap: 46,
    })),
  ],
  Katman: ({ b }) => (
    <div style={{ ...duzen.solAlt }}>
      <div
        className="s-gir s-g2"
        style={{
          fontFamily: yazi.baslik,
          fontWeight: 700,
          fontSize: u(boy.mega),
          lineHeight: 0.95,
          color: renk.metin,
          textShadow: '0 8px 44px rgba(0,0,0,0.85)',
        }}
      >
        Hazırız.
      </div>
      <div
        className="s-gir s-g4"
        style={{
          fontFamily: yazi.govde,
          fontSize: u(boy.buyuk),
          color: renk.metin2,
          marginTop: u(14),
        }}
      >
        {sayi(b.plan.n)} bölge · {kisaSayi(b.meta.toplam.res_hp)} hane · {kisaSayi(b.meta.toplam.firsat)} boş kapı
      </div>
    </div>
  ),
};

export default s10Kapanis;
