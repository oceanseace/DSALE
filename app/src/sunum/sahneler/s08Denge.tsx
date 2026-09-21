/**
 * S8 · Denge — "İlçeye göre bölseydik" → "Yeni plan".
 *
 * Adım 1 gerçek bir alternatifi gösterir: 11 ilçe, ilçe başına RES hane. Nilüfer tek başına
 * hedefin birkaç katı. Adım 2'de aynı grafik 8 eşit çubuğa dönüşür — y ekseni SABİT kalır,
 * böylece "eşitlik" gözle görülür. Bütün cümleler veriden türetilir.
 */
import { useMemo } from 'react';
import type { EChartsCoreOption } from 'echarts/core';

import { enBuyukFarkHane, kisaSayi, maksSapma, sayi, tumSinirKutusu, yuzde } from '../../data/selectors';
import { altlik, bolgeSinirlari, katmanlar as kat } from '../../map/katmanlar';
import type { Meta, Plan } from '../../data/types';
import Grafik from '../../ui/Grafik';
import { boy, renk, u, uPx, yazi } from '../../ui/tema';
import { sigdirEgik } from '../hesap/yardim';
import type { SahneTanimi } from '../motor/tipler';
import Manset from '../bilesen/Manset';
import { duzen } from './duzen';

/** y ekseni işaret aralığı (hane) — maks da bunun katına yuvarlanır */
const Y_ADIM = 30000;
const CUBUK_NOTR = '#4D6A9C';
const CUBUK_TASKIN = '#FFB35C';

function ilcePanosu(meta: Meta) {
  return [...meta.ilceler].sort((a, b) => b.res_hp - a.res_hp);
}

function secenek(plan: Plan, meta: Meta, adim: number, yMaks: number): EChartsCoreOption {
  const yaziBoyu = uPx(22);
  const ilceler = ilcePanosu(meta);
  const oncesi = adim === 1;
  const kategoriler = oncesi
    ? ilceler.map((x) => x.ilce)
    : plan.bolgeler.map((b) => `${b.kod}\n${b.kisa_ad}`);
  const enBuyuk = ilceler[0]?.res_hp ?? 0;
  const veriler = oncesi
    ? ilceler.map((x) => ({
        value: x.res_hp,
        itemStyle: { color: x.res_hp === enBuyuk ? CUBUK_TASKIN : CUBUK_NOTR, borderRadius: [4, 4, 0, 0] },
      }))
    : plan.bolgeler.map((b) => ({
        value: b.res_hp,
        itemStyle: { color: b.renk, borderRadius: [4, 4, 0, 0] },
      }));

  return {
    animationDuration: 800,
    animationDurationUpdate: 1100,
    animationEasingUpdate: 'cubicInOut',
    grid: { left: uPx(30), right: uPx(30), top: uPx(50), bottom: uPx(20), containLabel: true },
    xAxis: {
      type: 'category',
      data: kategoriler,
      axisLabel: {
        interval: 0,
        rotate: oncesi ? 26 : 0,
        lineHeight: yaziBoyu * 1.25,
        fontSize: yaziBoyu,
        color: renk.metin2,
      },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      max: yMaks,
      // maks da ızgaraya oturduğu için ECharts fazladan bir "165 bin" etiketi basmıyor:
      // eskiden üstteki iki işaret 15 binde bir, kalanlar 30 binde birdi.
      interval: Y_ADIM,
      axisLabel: { formatter: (v: number) => kisaSayi(v), fontSize: yaziBoyu * 0.92, color: renk.metin3 },
      splitLine: { lineStyle: { color: 'rgba(130,170,255,0.10)' } },
    },
    series: [
      {
        id: 'hane',
        type: 'bar',
        data: veriler,
        barMaxWidth: uPx(96),
        label: {
          show: true,
          position: 'top',
          formatter: (p: { value: number }) => sayi(p.value),
          fontFamily: "'Barlow Condensed', sans-serif",
          fontWeight: 700,
          fontSize: yaziBoyu * 1.15,
          color: renk.metin,
        },
        markLine: {
          silent: true,
          symbol: 'none',
          precision: 0,
          data: [{ yAxis: plan.hedef }],
          lineStyle: { color: renk.sari, type: 'dashed', width: uPx(2.4) },
          // etiket HTML tarafında: grafik içinde çubuk etiketleriyle çakışıyordu
          label: { show: false },
        },
      },
    ],
  };
}

export const s08Denge: SahneTanimi = {
  id: 'denge',
  ad: 'Denge',
  adimSayisi: () => 2,
  filmMs: (adim) => (adim === 1 ? 3400 : 5200),
  girisMs: 3000,
  kamera: () => ({
    bas: ({ api }) => sigdirEgik(api, tumSinirKutusu(), { padding: uPx(120), pitch: 34, bearing: -12, maksZoom: 12 }),
    orbit: 0.5,
  }),
  // Bu sahnede harita yalnız zemin dokusudur: grafiğin arkasında renkli bina kümeleri
  // "Gürsu" / "Gemlik" eksen etiketlerinin altında duruyordu. Binalar tümden kaldırıldı.
  katmanlar: ({ plan }) =>
    kat(
      altlik({ gorunurluk: 0.45, ilceEtiketleri: false, etiketBoyutu: 18 }),
      bolgeSinirlari({ plan, parca: 'dolgu', dolguAlfa: 30 }),
      bolgeSinirlari({ plan, parca: 'cizgi', cizgiGenislik: 1.8 }),
    ),
  Katman: ({ b }) => {
    const oncesi = b.adim === 1;
    const ilceler = ilcePanosu(b.meta);
    const yMaks = Math.ceil(((ilceler[0]?.res_hp ?? b.plan.hedef) * 1.04) / Y_ADIM) * Y_ADIM;
    const secenekler = useMemo(
      () => secenek(b.plan, b.meta, b.adim, yMaks),
      [b.plan, b.meta, b.adim, yMaks, b.boyut.width, b.boyut.height],
    );
    const katSayisi = ilceler[0] ? ilceler[0].res_hp / b.plan.hedef : 0;
    const fark = enBuyukFarkHane(b.plan);

    return (
      <>
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(3,6,13,0.88)' }} />
        <Manset
          style={duzen.solUst}
          genislik={1000}
          ustluk={oncesi ? 'Bir alternatif' : 'Yeni plan'}
          baslik={oncesi ? 'İlçeye göre bölseydik' : `${sayi(b.plan.n)} bölge, eşit yük`}
          alt={
            oncesi
              ? `${ilceler[0]?.ilce ?? 'En büyük ilçe'} tek başına hedefin ${sayi(katSayisi, 1)} katı olurdu.`
              : 'Hane eşit — fırsat mahalleye göre değişir.'
          }
        />
        <div style={{ ...duzen.sag, top: u(160), textAlign: 'right' }}>
          <div
            style={{
              display: 'inline-block',
              padding: `${u(14)} ${u(26)}`,
              borderRadius: u(14),
              border: `1px solid ${renk.cizgi}`,
              background: 'rgba(255,255,255,0.05)',
              fontFamily: yazi.govde,
              fontSize: u(boy.govde),
              color: renk.metin2,
            }}
          >
            {oncesi ? (
              <>
                En büyük ilçe:{' '}
                <span style={{ color: CUBUK_TASKIN, fontVariantNumeric: 'tabular-nums' }}>
                  {sayi(ilceler[0]?.res_hp ?? 0)} hane
                </span>
              </>
            ) : (
              <>
                Hedeften en büyük sapma:{' '}
                <span style={{ color: renk.metin, fontVariantNumeric: 'tabular-nums' }}>{sayi(fark)} hane</span> ·{' '}
                {yuzde(maksSapma(b.plan), 2)}
              </>
            )}
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: u(12),
              marginTop: u(14),
              fontFamily: yazi.govde,
              fontSize: u(boy.kucuk),
              color: renk.sari,
            }}
          >
            <span
              style={{
                width: u(46),
                height: 0,
                borderTop: `${u(3)} dashed ${renk.sari}`,
                display: 'inline-block',
              }}
            />
            Hedef {sayi(b.plan.hedef)} hane
          </div>
        </div>
        <div
          style={{
            position: 'absolute',
            left: u(72),
            right: u(72),
            top: u(330),
            bottom: u(132),
          }}
        >
          <Grafik secenek={secenekler} />
        </div>
      </>
    );
  },
};

export default s08Denge;
