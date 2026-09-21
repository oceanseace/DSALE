/**
 * S6 · Bölge turu — her bölge için bir durak (adım sayısı = plan.n).
 *
 * Kamera bölgenin sınır kutusuna oturur, kart sağda durur; diğer bölgeler söner.
 * Kartta ofise uzaklık YOK — uzak bölgeler "Araçlı bölge" etiketiyle anlatılır.
 */
import {
  altlik,
  arklar,
  binaIsiklari,
  binalar3D,
  bolgeEtiketleri,
  bolgeSinirlari,
  ilceEtiketKatmani,
  katmanlar as kat,
  ofisIsaretcisi,
} from '../../map/katmanlar';
import { binaBolgeleri, veri } from '../../data/load';
import { bolgeSinirKutusu, hexRgba } from '../../data/selectors';
import type { RGBA } from '../../data/selectors';
import type { LonLat, Plan } from '../../data/types';
import { uPx } from '../../ui/tema';
import { kolay, oran, sigdirEgik } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import BolgeKarti from '../bilesen/BolgeKarti';
import { duzen } from './duzen';

const ACILAR = [-28, 22, -42, 34, -14, 40, -22, 16];

/**
 * `sigdirEgik`in eğimden türettiği değerler bu sahnede kutuyu kadrajdan taşırıyordu: B8'in
 * Yıldırım Doğu kolu ekranın solundan kesiliyordu. Asıl suçlu `kaydir`dı — kamera merkezini
 * bakış yönünün tersine kaydırınca içerik ekranda karşı yöne gidiyor ve geniş bölgelerin uzak
 * ucu dışarıda kalıyordu. `ek` ise düşürülünce (donme telafisiyle birlikte eksiye geçip) kadrajı
 * gereğinden fazla açıyor ve küçük kümeleri (B4'ün Yalova'sı) görünmez kılıyor.
 */
const TELAFI = { ek: 0.05, kaydir: 0.04 } as const;

function bolgeSec(plan: Plan, adim: number) {
  return plan.bolgeler[Math.min(plan.bolgeler.length - 1, Math.max(0, adim - 1))];
}

/**
 * Bölgenin ÇEKİRDEK sınır kutusu: RES HP ile AĞIRLIKLANDIRILMIŞ uç %3 kırpılır.
 *
 * Tam sınır kutusu B4 gibi bölgelerde (Nilüfer'den Yalova'ya) neredeyse tamamı deniz olan dev bir
 * kare üretiyordu. Eski çözüm bina SAYISININ uç %8'ini atıyordu; bu, yoğun kümelerin kenarını da
 * kesiyordu (B8'in Yıldırım Doğu kolu ekranın solundan taşıyordu). Ağırlıklı kırpma hane yükünün
 * %97'sini kutuda tutar: dışarıda yalnız seyrek kırsal uçlar kalır, gövde tamamen karede olur.
 */
function cekirdekKutusu(plan: Plan, bolgeNo: number, kirp = 0.03): [LonLat, LonLat] {
  const b = veri().binalar;
  const bb = binaBolgeleri(plan);
  const nk: { lon: number; lat: number; w: number }[] = [];
  let toplam = 0;
  for (let i = 0; i < b.n; i++) {
    if (bb[i] !== bolgeNo) continue;
    const w = Math.max(1, b.resHp[i]); // hanesiz bina da bir ziyaret yüküdür
    nk.push({ lon: b.lon[i], lat: b.lat[i], w });
    toplam += w;
  }
  if (nk.length < 40) return bolgeSinirKutusu(plan, [bolgeNo]);
  const q = (alan: 'lon' | 'lat', p: number) => {
    const sirali = [...nk].sort((x, y) => x[alan] - y[alan]);
    const hedef = toplam * p;
    let biriken = 0;
    for (const d of sirali) {
      biriken += d.w;
      if (biriken >= hedef) return d[alan];
    }
    return sirali[sirali.length - 1][alan];
  };
  return [
    [q('lon', kirp), q('lat', kirp)],
    [q('lon', 1 - kirp), q('lat', 1 - kirp)],
  ];
}

function cerceve(plan: Plan, adim: number) {
  const b = bolgeSec(plan, adim);
  return {
    kutu: cekirdekKutusu(plan, b.bolge),
    padding: { left: uPx(60), right: uPx(750), top: uPx(150), bottom: uPx(180) },
    bearing: ACILAR[(adim - 1) % ACILAR.length],
  };
}

export const s06BolgeTuru: SahneTanimi = {
  id: 'tur',
  ad: 'Bölge turu',
  adimSayisi: (plan) => plan.bolgeler.length,
  filmMs: () => 2100,
  girisMs: 2500,
  kamera: (d) => ({
    bas: ({ api }) => {
      const c = cerceve(d.plan, d.adim);
      const k = sigdirEgik(api, c.kutu, {
        padding: c.padding,
        pitch: 38,
        bearing: c.bearing - 10,
        maksZoom: 14.8,
        donme: true,
        ...TELAFI,
      });
      return { ...k, zoom: k.zoom - 0.3 };
    },
    adimlar: [
      {
        durum: ({ api }) => {
          const c = cerceve(d.plan, d.adim);
          // dönme telafisi açık: kart yanında dururken bölge kadrajdan taşmamalı
          return sigdirEgik(api, c.kutu, {
            padding: c.padding,
            pitch: 48,
            bearing: c.bearing,
            maksZoom: 14.8,
            donme: true,
            ...TELAFI,
          });
        },
        sureMs: 2100,
        tur: 'linear',
      },
    ],
  }),
  katmanlar: ({ plan, adim, t }) => {
    const b = bolgeSec(plan, adim);
    const vurgu = [b.bolge];
    const gir = kolay(oran(t, 0, 1.2));
    // yalnız turdaki bölge parlar: uzak/geniş bölgelerde (B4, B8) şekli okunur kılan şey bu
    const bb = binaBolgeleri(plan);
    const bolgeRengi = hexRgba(b.renk);
    const sonuk: RGBA = [10, 18, 34, 255];
    const parlakModu = {
      tur: 'ozel' as const,
      anahtar: `tur${b.bolge}`,
      renk: (i: number): RGBA => (bb[i] === b.bolge ? bolgeRengi : sonuk),
    };
    return kat(
      altlik({ gorunurluk: 0.8, ilceEtiketleri: false }),
      bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 40, vurguBolgeler: vurgu }),
      binalar3D({ plan, vurguBolgeler: vurgu, sonukluk: 0.9, yukseklikOlcegi: 2.2, renkGecisMs: 600, pickable: false }),
      // Küçük kümeler (B4'ün 266 Yalova binası) altlığın "YALOVA" yazısının altında kayboluyordu:
      // vurgulu bölgenin ışık lekesi büyütüldü, artık yazının altında parlayan bir kütle var.
      binaIsiklari({ plan, renkModu: parlakModu, alfa: 230, yaricap: 130, minPiksel: 4.2 }),
      bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: 2.2, vurguBolgeler: vurgu }),
      arklar({ plan, bolgeler: vurgu, ilerleme: gir, t: t > 1.2 ? t : null, genislik: 3 }),
      // Bu sahnede ofis SIK SIK kadrajın kenarında kalıyor ve sarı rozet yarım kesiliyordu
      // ("DEHANET EÇ|"). Fener + ofisten gelen yay zaten mesafeyi anlatıyor; yazı kapatıldı.
      ofisIsaretcisi({ t, olcek: 0.8, yukseklik: 1600, etiket: false }),
      // ilçe adları EN SONDA: vurgulu bölgenin ışık lekesi "YALOVA" yazısının üstüne biniyordu
      ilceEtiketKatmani({ etiketBoyutu: 22, gorunurluk: 0.8 }),
      bolgeEtiketleri({ plan, bicim: 'kod', boyut: 34, bolgeler: vurgu, gorunurluk: gir }),
    );
  },
  Katman: ({ b }) => {
    const bolge = bolgeSec(b.plan, b.adim);
    return (
      <BolgeKarti
        key={bolge.bolge}
        bolge={bolge}
        hedef={b.plan.hedef}
        sira={b.adim}
        toplam={b.adimSayisi}
        style={duzen.sag}
      />
    );
  },
};

export default s06BolgeTuru;
