/**
 * S9 · Büyüme — ekip büyüdükçe harita saniyeler içinde yeniden bölünür.
 *
 * Kaydırıcı YALNIZ dengeli planlarda durur (`dengeliPlanlar`), N listesi çalışma anında okunur.
 * Adım 2 "tam ekip" vuruşudur: meta.ekip.sorumlu_sayisi'na en yakın dengeli plan.
 * Film modunda adım 1 bugünkü N'den birkaç basamak yukarı süzülür, adım 2 tam ekibe atlar.
 */
import { useEffect, useMemo, useRef } from 'react';

import { useUygulama } from '../../core/uygulama';
import { dengeliPlanlar, enBuyukFarkHane, maksSapma, sayi, tumSinirKutusu, yuzde } from '../../data/selectors';
import { varsayilanN } from '../../data/load';
import {
  altlik,
  binaIsiklari,
  binalar3D,
  bolgeSinirlari,
  katmanlar as kat,
  ofisIsaretcisi,
} from '../../map/katmanlar';
import { boy, renk, u, uPx, yazi } from '../../ui/tema';
import { ofisCagrisi, oran, sigdirEgik } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import Manset from '../bilesen/Manset';
import NKaydirici from '../bilesen/NKaydirici';
import { duzen } from './duzen';

/** listedeki, hedefe en yakın N */
function enYakin(liste: number[], hedef: number): number {
  let en = liste[0] ?? hedef;
  for (const x of liste) if (Math.abs(x - hedef) < Math.abs(en - hedef)) en = x;
  return en;
}

function Katman({ b }: { b: import('../motor/tipler').SahneBaglami }) {
  const { setN } = useUygulama();
  const liste = useMemo(() => dengeliPlanlar(0.01), []);
  const girisN = useRef(b.n);
  const ekipN = useMemo(() => enYakin(liste, b.meta.ekip.sorumlu_sayisi), [liste, b.meta.ekip.sorumlu_sayisi]);
  const tamEkip = b.adim === 2;

  // sahne çıkışında bölge sayısını girişteki hâline döndür
  useEffect(() => {
    const ilk = girisN.current;
    return () => setN(ilk);
  }, [setN]);

  useEffect(() => {
    setN(tamEkip ? ekipN : girisN.current);
    // adım değişiminde çalışır
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tamEkip, ekipN]);

  // film süzülmesi: bugünkü N'den dört basamak yukarı
  const filmIndeksi = useRef(0);
  filmIndeksi.current = Math.max(0, liste.indexOf(girisN.current));
  const filmHedefi =
    b.film && !tamEkip ? liste[Math.min(liste.length - 1, filmIndeksi.current + Math.floor(oran(b.t, 1.2, 4.2) * 4))] : null;
  useEffect(() => {
    if (filmHedefi != null) setN(filmHedefi);
  }, [filmHedefi, setN]);

  const fark = enBuyukFarkHane(b.plan);

  return (
    <>
      <Manset
        style={duzen.solUst}
        genislik={1000}
        ustluk={tamEkip ? 'Tam ekip' : 'Büyüme'}
        baslik={
          <>
            <span style={{ color: renk.sari, fontVariantNumeric: 'tabular-nums' }}>{sayi(b.plan.n)}</span>{' '}
            {tamEkip ? 'kişilik ekip' : 'satışçı, ' + sayi(b.plan.n) + ' bölge'}
          </>
        }
        alt={
          tamEkip
            ? 'Aynı denge, daha küçük bölgeler.'
            : 'Ekip büyüdükçe harita saniyeler içinde yeniden çizilir.'
        }
      />

      <div style={{ ...duzen.sag, top: u(170), textAlign: 'right' }}>
        <div
          style={{
            fontFamily: yazi.govde,
            fontSize: u(boy.kucuk),
            letterSpacing: '0.2em',
            textTransform: 'uppercase',
            color: renk.metin3,
          }}
        >
          Kişi başı
        </div>
        <div
          style={{
            fontFamily: yazi.baslik,
            fontWeight: 700,
            fontSize: u(boy.dev),
            lineHeight: 0.95,
            color: renk.metin,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {sayi(b.plan.hedef)}
        </div>
        <div style={{ fontFamily: yazi.govde, fontSize: u(boy.buyuk), color: renk.metin2, marginTop: u(4) }}>hane</div>
        <div style={{ fontFamily: yazi.govde, fontSize: u(boy.govde), color: renk.metin3, marginTop: u(16) }}>
          hedeften en çok {sayi(fark)} hane · {yuzde(maksSapma(b.plan), 2)}
        </div>
      </div>

      <NKaydirici
        nler={liste}
        n={b.n}
        setN={setN}
        // "bugün" HER ZAMAN varsayılan plandır (8). Eskiden sahneye girilen N etiketleniyordu:
        // kaydırıcı 14'e çekilince deck patrona "bugünkü ekip 14 kişi" diyordu.
        isaretler={{
          [liste[0] ?? 2]: 'en az',
          [ekipN]: 'tam ekip',
          [varsayilanN()]: 'bugün',
          [liste[liste.length - 1] ?? 50]: 'en çok',
        }}
        style={{ position: 'absolute', left: '50%', bottom: u(132), transform: 'translateX(-50%)' }}
      />
    </>
  );
}

export const s09Buyume: SahneTanimi = {
  id: 'buyume',
  ad: 'Büyüme',
  adimSayisi: () => 2,
  filmMs: (adim) => (adim === 1 ? 5000 : 5200),
  girisMs: 2600,
  htmlSaati: true,
  htmlSaatiBitis: 5,
  kamera: () => ({
    bas: ({ api }) =>
      sigdirEgik(api, tumSinirKutusu(), {
        padding: { left: uPx(90), right: uPx(520), top: uPx(150), bottom: uPx(300) },
        pitch: 36,
        bearing: -10,
        maksZoom: 12.5,
      }),
    orbit: 0.5,
  }),
  katmanlar: ({ plan, t }) =>
    kat(
      altlik({ gorunurluk: 0.7, etiketBoyutu: 18 }),
      bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 44 }),
      binalar3D({ plan, yukseklikOlcegi: 0.85, renkGecisMs: 450, pickable: false }),
      binaIsiklari({ plan, alfa: 175, yaricap: 48, minPiksel: 2 }),
      bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: plan.n <= 16 ? 2 : 1.4, parlama: plan.n <= 16 }),
      // ofis rozeti + bölge çipleri HTML çağrı katmanında (ortak çakışma çözücü)
      ofisIsaretcisi({ t, olcek: 0.7, yukseklik: 4200, etiket: false }),
    ),
  // Yalnız ofis rozeti: bu sahnenin konusu bölge KİMLİĞİ değil, haritanın yeniden çizilmesi.
  // Bölge çipleri hem manşetin alt satırıyla çakışıyor hem N büyüdükçe okunmaz hâle geliyordu;
  // bölgeler S5'te adlarıyla, S6'da tek tek tanıtıldı.
  cagrilar: ({ meta }) => [ofisCagrisi(meta, { sap: 96 })],
  Katman,
};

export default s09Buyume;
