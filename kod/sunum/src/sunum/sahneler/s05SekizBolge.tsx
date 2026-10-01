/**
 * S5 · Sekiz bölge — iki vuruş.
 *   Adım 1: bütün saha (Yalova'dan İnegöl'e) + 8 renk + lejant şeridi.
 *   Adım 2: Nilüfer çekirdeğine giriş + HTML çağrı balonları (itmeli yerleşim, bağlantı çizgili).
 *
 * "Eşit pay" değil, "eşit yük": her bölgeye yaklaşık aynı hane sayısı düşer.
 */
import { bolgeEtiketNoktasi } from '../../data/load';
import { bolgeSinirKutusu, kisaSayi, sayi, tumSinirKutusu } from '../../data/selectors';
import {
  altlik,
  arklar,
  binaIsiklari,
  binalar3D,
  bolgeSinirlari,
  katmanlar as kat,
  ofisIsaretcisi,
} from '../../map/katmanlar';
import type { Plan } from '../../data/types';
import { boy, renk, u, uPx, yazi } from '../../ui/tema';
import { kolay, ofisCagrisi, oran, sigdirEgik } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import LejantSerit from '../bilesen/LejantSerit';
import Manset from '../bilesen/Manset';
import { duzen } from './duzen';

/** Ofise yakın (yürüme/kısa mesafe) bölgeler — çekirdek çerçevesi bunlardan türetilir. */
function cekirdek(plan: Plan): number[] {
  const yakin = plan.bolgeler.filter((b) => b.ofis_km <= 15).map((b) => b.bolge);
  return yakin.length >= 2 ? yakin : plan.bolgeler.map((b) => b.bolge);
}

export const s05SekizBolge: SahneTanimi = {
  id: 'bolgeler',
  ad: 'Bölgeler',
  adimSayisi: () => 2,
  filmMs: (adim) => (adim === 1 ? 5000 : 6000),
  girisMs: 3000,
  kamera: (d) =>
    d.adim === 1
      ? {
          // manşete yer açmak için içerik sağa kaydırılır (sol dolgu büyük)
          bas: ({ api }) =>
            sigdirEgik(api, tumSinirKutusu(), {
              padding: { left: uPx(560), right: uPx(70), top: uPx(130), bottom: uPx(210) },
              pitch: 24,
              bearing: 0,
              maksZoom: 12.5,
            }),
          adimlar: [
            {
              durum: ({ api }) => {
                const k = sigdirEgik(api, tumSinirKutusu(), {
                  padding: { left: uPx(560), right: uPx(70), top: uPx(130), bottom: uPx(210) },
                  pitch: 34,
                  bearing: -6,
                  maksZoom: 12.5,
                });
                return k;
              },
              sureMs: 4200,
              tur: 'linear',
            },
          ],
        }
      : {
          bas: ({ api, durum }) => {
            const k = sigdirEgik(api, bolgeSinirKutusu(durum.plan, cekirdek(durum.plan)), {
              padding: { left: uPx(120), right: uPx(120), top: uPx(230), bottom: uPx(320) },
              pitch: 46,
              bearing: -18,
              maksZoom: 13,
            });
            return { ...k, zoom: k.zoom - 0.4 };
          },
          adimlar: [
            {
              durum: ({ api, durum }) =>
                sigdirEgik(api, bolgeSinirKutusu(durum.plan, cekirdek(durum.plan)), {
                  padding: { left: uPx(120), right: uPx(120), top: uPx(230), bottom: uPx(320) },
                  pitch: 52,
                  bearing: -12,
                  maksZoom: 13,
                }),
              sureMs: 5200,
              tur: 'linear',
            },
          ],
          orbit: 0.7,
        },
  katmanlar: ({ plan, t, adim }) => {
    const gir = kolay(oran(t, 0, 1.6));
    const arkIlerleme = kolay(oran(t, 0.4, 2.4));
    return kat(
      altlik({ gorunurluk: 0.85, etiketBoyutu: adim === 1 ? 20 : 24 }),
      bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 40 * gir }),
      binalar3D({ plan, yukseklikOlcegi: adim === 1 ? 0.8 : 1, pickable: false }),
      binaIsiklari({ plan, alfa: adim === 1 ? 170 : 80, yaricap: adim === 1 ? 46 : 26, minPiksel: adim === 1 ? 2 : 1.3 }),
      // yakın bölgelerde parlama daraltılır (çekirdekte hale birbirine karışmasın)
      bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: adim === 1 ? 2.4 : 1.8, gorunurluk: gir }),
      arklar({ plan, ilerleme: arkIlerleme, t: t > 2.4 ? t : null, genislik: 2.6 }),
      // Ofis rozeti de bölge çipleri de artık HTML çağrı katmanında (ortak çakışma çözücü):
      // haritada yalnız sarı fener ve nabız halkaları kalır.
      ofisIsaretcisi({ t, olcek: 0.9, yukseklik: adim === 1 ? 4200 : 1800, etiket: false }),
    );
  },
  cagrilar: ({ plan, meta, adim }) => [
    ofisCagrisi(meta, { sap: adim === 1 ? 74 : 96 }),
    ...plan.bolgeler.map((b) => ({
      anahtar: b.kod,
      konum: bolgeEtiketNoktasi(b),
      baslik: adim === 2 ? `${b.kod} · ${b.kisa_ad}` : b.kod,
      alt: adim === 2 ? `${sayi(b.res_hp)} hane` : undefined,
      renk: b.renk,
      kucuk: adim === 1,
      sap: adim === 1 ? 44 : 64,
    })),
  ],
  Katman: ({ b }) => (
    <>
      <Manset
        style={duzen.solAlt}
        ustluk="Yeni plan"
        genislik={1050}
        baslik={
          <>
            {sayi(b.plan.n)} sorumlu · <span style={{ color: renk.sari }}>{sayi(b.plan.n)} eşit bölge</span>
          </>
        }
        rakam={
          <div style={{ display: 'flex', alignItems: 'baseline', gap: u(18) }}>
            <span
              style={{
                fontFamily: yazi.baslik,
                fontWeight: 700,
                fontSize: u(boy.dev),
                lineHeight: 0.95,
                color: renk.metin,
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              ≈{kisaSayi(b.plan.hedef)}
            </span>
            <span style={{ fontFamily: yazi.govde, fontSize: u(boy.buyuk), color: renk.metin2 }}>
              hane · her bölgeye
            </span>
          </div>
        }
      />
      <LejantSerit plan={b.plan} style={duzen.serit} />
    </>
  ),
};

export default s05SekizBolge;
