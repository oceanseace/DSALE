/**
 * S4 · Nasıl böldük — algoritmanın kendisi.
 *
 * `plan.anlik_etiket[s]` kareleri boyunca binalar gerçek ara adım renklerine boyanır
 * (uydurma Voronoi değil: CCPD'nin kendi etiketleri), merkezler pin olarak iner,
 * son 1,5 saniyede gerçek `birim_bolge` renklerine geçilir ve sınırlar belirir.
 *
 * Eski veri paketlerinde `anlik_etiket` yoksa yedek yol: pinler iner, nihai renkler belirir.
 */
import { anlikEtiketVar, bolgeEtiketNoktasi } from '../../data/load';
import { bolgeRenkTablosu, hexRgba, sayi, tumSinirKutusu } from '../../data/selectors';
import {
  altlik,
  binaIsiklari,
  binalar3D,
  bolgeSinirlari,
  katmanlar as kat,
  ofisIsaretcisi,
  type BinaRenkModu,
} from '../../map/katmanlar';
import type { Plan } from '../../data/types';
import { renk, u, uPx } from '../../ui/tema';
import { oran, pinler, sigdirEgik, sinir } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import AdimIkonlari, { IkonBina, IkonKilit, IkonRota, IkonTerazi } from '../bilesen/AdimIkonlari';
import Manset from '../bilesen/Manset';
import { duzen } from './duzen';

const AKIS_BAS = 0.6;
const AKIS_BIT = 7.8;
const SON_BAS = 8.2;
const SON_BIT = 9.5;

function kareIndeksi(plan: Plan, t: number): number {
  const k = plan.anlik_etiket?.length ?? 0;
  if (k <= 1) return 0;
  return Math.min(k - 1, Math.floor(oran(t, AKIS_BAS, AKIS_BIT) * (k - 1) + 1e-6));
}

/** Pin konumları: ara adımın merkezleri (yoksa nihai etiket noktaları). */
function pinNoktalari(plan: Plan, kare: number) {
  const anlik = plan.anlik?.[kare];
  return plan.bolgeler.map((b, i) => ({
    konum: (anlik?.[i] ?? bolgeEtiketNoktasi(b)) as [number, number],
    metin: b.kod,
    renk: hexRgba(b.renk),
  }));
}

export const s04NasilBolduk: SahneTanimi = {
  id: 'nasil',
  ad: 'Nasıl böldük',
  filmMs: () => 10000,
  girisMs: 9600,
  htmlSaati: true,
  htmlSaatiBitis: AKIS_BIT + 0.6,
  kamera: () => ({
    bas: ({ api }) =>
      sigdirEgik(api, tumSinirKutusu(), { padding: uPx(110), pitch: 30, bearing: 0, maksZoom: 12.5 }),
    adimlar: [
      {
        durum: ({ api }) => {
          const k = sigdirEgik(api, tumSinirKutusu(), { padding: uPx(110), pitch: 42, bearing: -8, maksZoom: 12.5 });
          return { ...k, zoom: k.zoom + 0.2 };
        },
        sureMs: 8600,
        tur: 'linear',
      },
    ],
  }),
  katmanlar: ({ plan, t }) => {
    const varAnlik = anlikEtiketVar(plan);
    const kare = varAnlik ? kareIndeksi(plan, t) : 0;
    const sonAsama = t >= SON_BAS || !varAnlik;
    const dizi = plan.anlik_etiket?.[kare];

    const renkModu: BinaRenkModu =
      sonAsama || !dizi
        ? { tur: 'bolge', plan }
        : { tur: 'etiketDizisi', dizi, tablo: bolgeRenkTablosu(plan), anahtar: `k${kare}` };

    const sinirGorunur = oran(t, SON_BAS + 0.3, SON_BIT);
    const pinIlerleme = sinir(oran(t, 0.05, 1.1));

    return kat(
      altlik({ gorunurluk: 0.78, etiketBoyutu: 19 }),
      sinirGorunur > 0 && bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 26 * sinirGorunur }),
      binalar3D({ plan, renkModu, yukseklikOlcegi: 0.55, renkGecisMs: 900, pickable: false }),
      binaIsiklari({ plan, renkModu, alfa: 120, yaricap: 40, minPiksel: 1.8 }),
      sinirGorunur > 0 &&
        bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: 2.2, gorunurluk: sinirGorunur, parlama: true }),
      ofisIsaretcisi({ t, olcek: 0.6, yukseklik: 5200, etiket: false }),
      pinler({ id: 'anlik-pin', pinler: pinNoktalari(plan, kare), yukseklik: 6200, ilerleme: pinIlerleme, etiketBoyutu: 24 }),
    );
  },
  Katman: ({ b }) => {
    const birim = Number(b.plan.parametreler?.birim_sayisi ?? 0);
    const etkin = Math.min(3, Math.floor(oran(b.t, 0.4, AKIS_BIT) * 4));
    // Başlık "dört kural" diyor: dördü de KURAL olmalı. "9.464 site grubu" bir sayımdı,
    // kurala çevrildi ve sayı alt satıra taşındı.
    const ogeler = [
      { ikon: IkonBina, metin: 'Bina değil, site grubu' },
      { ikon: IkonKilit, metin: 'Site bölünmez' },
      { ikon: IkonTerazi, metin: 'Hane yükü eşit' },
      { ikon: IkonRota, metin: 'Rota kısa' },
    ];
    return (
      <>
        <Manset
          style={duzen.solUst}
          ustluk="Nasıl böldük"
          genislik={1000}
          baslik={
            <>
              {sayi(b.plan.n)} bölge, <span style={{ color: renk.sari }}>dört kural</span>
            </>
          }
          alt={
            birim > 0
              ? `${sayi(birim)} site grubunu bilgisayar dengede buluşana kadar taşır.`
              : `Bilgisayar ${sayi(b.plan.n)} merkezi dengede buluşana kadar taşır.`
          }
        />
        <div
          style={{
            ...duzen.ortaAlt,
            background: 'rgba(4,9,20,0.78)',
            border: `1px solid ${renk.cizgi}`,
            borderRadius: u(18),
            padding: `${u(14)} ${u(30)}`,
            backdropFilter: 'blur(10px)',
          }}
        >
          <AdimIkonlari ogeler={ogeler} etkin={Math.max(0, etkin)} />
        </div>
      </>
    );
  },
};

export default s04NasilBolduk;
