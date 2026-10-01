/**
 * S7 · Yalova — körfezin karşı kıyısı da ilk günden planda.
 *
 * Kamera Mudanya üstünden kalkar, körfezi geçer, Yalova'ya iner. Yalova binaları altın sarısı,
 * ofisten gelen yay ve nabız halkaları noktayı işaretler. Bütün rakamlar meta.yalova'dan gelir.
 */
import { veri } from '../../data/load';
import { onlukOran, sayi } from '../../data/selectors';
import type { RGBA } from '../../data/selectors';
import { altlik, binaIsiklari, binalar3D, bolgeSinirlari, katmanlar as kat, ofisIsaretcisi } from '../../map/katmanlar';
import type { Meta, Plan } from '../../data/types';
import { boy, renk, u, uPx, yazi } from '../../ui/tema';
import { kolay, nabizHalkalari, ofisCagrisi, oran, ozelArk, pinler, sigdirEgik } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import { duzen } from './duzen';

const ALTIN: RGBA = [255, 196, 0, 255];
const SONUK: RGBA = [24, 36, 60, 255];
/** toplamsal karışımda görünmeyen renk (maskeleme için) */
const KARA: RGBA = [0, 0, 0, 0];

function yalovaBolgesi(plan: Plan, meta: Meta) {
  return plan.bolgeler.find((b) => b.yalova_bina > 0) ?? plan.bolgeler.find((b) => b.bolge === meta.yalova.bolgeler[0]);
}

function merkez(meta: Meta): [number, number] {
  return (meta.yalova.merkez ?? [29.26, 40.64]) as [number, number];
}

/**
 * Kadraj kutusu: ofisten Yalova'ya kadar — yani körfezin İKİ kıyısı da karede.
 *
 * Eskiden kamera doğrudan Yalova'ya z=14 ile iniyordu; kare Marmara'nın ortasında küçük bir altın
 * lekeydi ve "karşı kıyı" cümlesinin işaret ettiği su hiç görünmüyordu. Şimdi Bursa kıyısı altta,
 * körfez ortada, Yalova üstte duruyor ve ofisten çıkan yay ikisini birbirine bağlıyor.
 */
function kutu(meta: Meta): [[number, number], [number, number]] {
  const [ylon, ylat] = merkez(meta);
  const olon = meta.ofis.lon;
  const olat = meta.ofis.lat;
  return [
    [Math.min(olon, ylon) - 0.05, Math.min(olat, ylat) - 0.03],
    [Math.max(olon, ylon) + 0.06, Math.max(olat, ylat) + 0.06],
  ];
}

/** Metin bloğu solda duruyor: içerik sağ yarıya sığdırılır. */
const DOLGU = { left: uPx(920), right: uPx(90), top: uPx(140), bottom: uPx(170) };

export const s07Yalova: SahneTanimi = {
  id: 'yalova',
  ad: 'Yalova',
  filmMs: () => 10000,
  girisMs: 5400,
  kamera: (d) => ({
    // Ofis→Yalova ekseni ekranda çapraz dursun diye bearing −31: Bursa sol altta, Yalova sağ üstte.
    bas: ({ api }) => {
      const k = sigdirEgik(api, kutu(d.meta), { padding: DOLGU, pitch: 40, bearing: -31, maksZoom: 12, donme: true });
      return { ...k, zoom: k.zoom - 0.55 };
    },
    adimlar: [
      {
        durum: ({ api }) =>
          sigdirEgik(api, kutu(d.meta), { padding: DOLGU, pitch: 56, bearing: -24, maksZoom: 12, donme: true }),
        sureMs: 4600,
        tur: 'linear',
      },
    ],
    orbit: 0.4,
  }),
  katmanlar: ({ plan, meta, t }) => {
    const y = veri().binalar.yalova;
    const bolge = yalovaBolgesi(plan, meta);
    const arkIlerleme = kolay(oran(t, 0.2, 3.2));
    const renkModu = {
      tur: 'ozel' as const,
      anahtar: 'yalova-altin',
      renk: (i: number): RGBA => (y[i] ? ALTIN : SONUK),
    };
    return kat(
      altlik({ gorunurluk: 0.9, etiketBoyutu: 20 }),
      bolge && bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 30, bolgeler: [bolge.bolge] }),
      binalar3D({ plan, renkModu, yukseklikOlcegi: 1.6, renkGecisMs: 700, pickable: false }),
      binaIsiklari({ plan, renkModu, alfa: 110, yaricap: 26 }),
      // Altın Yalova binaları için ayrı, GENİŞ ışık lekesi: bu ölçekte 266 bina birkaç piksel
      // kalıyordu. Yalova dışı [0,0,0] döner ve toplamsal karışımda hiç görünmez.
      binaIsiklari({
        plan,
        id: 'yalova-parlak',
        renkModu: { tur: 'ozel', anahtar: 'yalova-parlak', renk: (i: number): RGBA => (y[i] ? ALTIN : KARA) },
        alfa: 250,
        yaricap: 170,
        minPiksel: 5,
      }),
      bolge && bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: 2, bolgeler: [bolge.bolge] }),
      // Yay artık SÖNMÜYOR: iki kıyıyı birbirine bağlayan tek görsel bağ o.
      ozelArk({
        id: 'yalova-ark',
        a: [meta.ofis.lon, meta.ofis.lat],
        b: merkez(meta),
        renk: ALTIN,
        ilerleme: arkIlerleme,
        genislik: 3,
        yukseklikOrani: 0.24,
      }),
      nabizHalkalari({ id: 'yalova-nabiz', konum: merkez(meta), t, renk: ALTIN, maksYaricap: 2600, periyot: 2.8 }),
      // Pinin "YALOVA" yazısı altlığın kendi YALOVA ilçe etiketinin üstüne basıyordu → yazı HTML'e alındı.
      pinler({
        id: 'yalova-pin',
        pinler: [{ konum: merkez(meta), metin: 'YALOVA', renk: ALTIN }],
        yukseklik: 1700,
        ilerleme: kolay(oran(t, 2.6, 3.8)),
        etiket: false,
        direkYaricapi: 40,
      }),
      ofisIsaretcisi({ t, olcek: 0.9, yukseklik: 2600, etiket: false }),
    );
  },
  cagrilar: ({ meta }) => [
    ofisCagrisi(meta, { sap: 78 }),
    {
      anahtar: 'yalova',
      konum: [merkez(meta)[0], merkez(meta)[1], 1700] as [number, number, number],
      baslik: 'Yalova Merkez',
      alt: `${sayi(veri().meta.yalova.bina)} bina`,
      renk: '#FFC400',
      sap: 40,
    },
  ],
  Katman: ({ b }) => {
    const ya = b.meta.yalova;
    const bolge = yalovaBolgesi(b.plan, b.meta);
    return (
      <div style={{ ...duzen.solAlt, maxWidth: u(1080) }}>
        <div
          className="s-gir s-g1"
          style={{
            fontFamily: yazi.govde,
            fontSize: u(boy.kucuk),
            letterSpacing: '0.24em',
            textTransform: 'uppercase',
            color: renk.sari,
            marginBottom: u(10),
          }}
        >
          Körfezin karşı kıyısı
        </div>
        <div
          className="s-gir s-g2"
          style={{
            fontFamily: yazi.baslik,
            fontWeight: 700,
            fontSize: u(boy.baslik),
            lineHeight: 1.02,
            color: renk.metin,
            textShadow: '0 4px 28px rgba(0,0,0,0.75)',
          }}
        >
          Yalova ilk günden haritada
        </div>
        <div className="s-gir s-g3" style={{ display: 'flex', alignItems: 'baseline', gap: u(20), marginTop: u(18) }}>
          <span
            style={{
              fontFamily: yazi.baslik,
              fontWeight: 700,
              fontSize: u(boy.dev),
              lineHeight: 0.95,
              color: renk.sari,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {sayi(ya.firsat)}
          </span>
          <span style={{ fontFamily: yazi.govde, fontSize: u(boy.alt), color: renk.metin2 }}>kapı</span>
        </div>
        <div
          className="s-gir s-g4"
          style={{ fontFamily: yazi.govde, fontSize: u(boy.buyuk), color: renk.metin, marginTop: u(10) }}
        >
          <span style={{ color: renk.sari }}>Yalova Merkez</span> · {onlukOran(ya.firsat, ya.res_hp)} bizi bekliyor
        </div>
        <div
          className="s-gir s-g5"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: u(18),
            marginTop: u(18),
            fontFamily: yazi.govde,
            fontSize: u(boy.govde),
            color: renk.metin2,
            textShadow: '0 2px 16px rgba(0,0,0,0.85)',
          }}
        >
          <span>
            {sayi(ya.bina)} bina · {sayi(ya.res_hp)} hane
          </span>
          {bolge && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: u(10),
                padding: `${u(8)} ${u(18)}`,
                borderRadius: u(999),
                border: `1px solid ${bolge.renk}`,
                background: 'rgba(4,9,20,0.75)',
                color: renk.metin,
              }}
            >
              <span
                style={{
                  width: u(14),
                  height: u(14),
                  borderRadius: u(4),
                  background: bolge.renk,
                  boxShadow: `0 0 ${u(14)} ${bolge.renk}`,
                }}
              />
              {bolge.kod} · {bolge.ad}
            </span>
          )}
        </div>
      </div>
    );
  },
};

export default s07Yalova;
