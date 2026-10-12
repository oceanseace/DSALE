/**
 * MAP ▸ "Ekipler" katmanı: BOSS GPS Takip'ten gelen ekip son konumları (sunucu: `GET /api/isler/ekip-konumlari`,
 * kaynak eklentinin okuduğu BOSS ucu — kod/operasyon/v2/ekip_konum.py). Katman açıkken 60 sn'de bir (ve sekmeye
 * dönünce) yoklanır; kapalıyken hiç istek yok. 30 dk'dan eski konum soluk çizilir.
 * Giriş: useEkipKonumlari (veri), ekipKatmanlari (deck.gl katmanları), ekipZamanEtiketi ("14:32 · 5 dk önce").
 */

import { useEffect, useState } from 'react';
import { ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { ekipKonumlari, type EkipKonum, type EkipKonumYanit } from '../../../../cekirdek/is/api';

export const EKIP_ESKI_DK = 30;
export const EKIP_YOKLAMA_MS = 60_000;

const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;
const KOYU: [number, number, number] = [17, 24, 39];

/** "14:32 · 5 dk önce" (zaman sunucuda Türkiye saati metni). */
export function ekipZamanEtiketi(e: Pick<EkipKonum, 'zaman' | 'yas_dk'>): string {
  const saat = /\d{2}:\d{2}/.exec(String(e.zaman || '').slice(10))?.[0] ?? '';
  const y = e.yas_dk;
  if (y == null) return saat;
  const once = y < 1 ? 'şimdi' : y < 60 ? `${y} dk önce` : y < 48 * 60 ? `${Math.floor(y / 60)} sa önce` : `${Math.floor(y / 1440)} gün önce`;
  return saat ? `${saat} · ${once}` : once;
}

export const ekipEskiMi = (e: Pick<EkipKonum, 'yas_dk'>) => e.yas_dk != null && e.yas_dk > EKIP_ESKI_DK;

/** Katman açıkken sunucudan ekip konumları (görünürken 60 sn'de bir). Kapalıyken null. */
export function useEkipKonumlari(acik: boolean): EkipKonumYanit | null {
  const [yanit, setYanit] = useState<EkipKonumYanit | null>(null);
  useEffect(() => {
    if (!acik) return undefined;
    let iptal = false;
    const getir = () => {
      if (document.visibilityState !== 'visible') return;
      ekipKonumlari()
        .then((y) => {
          if (!iptal) setYanit(y);
        })
        .catch(() => undefined);
    };
    getir();
    const t = window.setInterval(getir, EKIP_YOKLAMA_MS);
    document.addEventListener('visibilitychange', getir);
    return () => {
      iptal = true;
      window.clearInterval(t);
      document.removeEventListener('visibilitychange', getir);
    };
  }, [acik]);
  return acik ? yanit : null;
}

/** Ekip noktaları (koyu dolgu, beyaz halka) + ad ve "14:32 · 5 dk önce" etiketi; eskiler soluk. Tıklanmaz. */
export function ekipKatmanlari(konumlar: EkipKonum[]): unknown[] {
  if (!konumlar.length) return [];
  const a = (e: EkipKonum, taze: number, eski: number) => (ekipEskiMi(e) ? eski : taze);
  return [
    new ScatterplotLayer<EkipKonum>({
      id: 'ih-ekip-nokta',
      data: konumlar,
      getPosition: (e) => [e.lon, e.lat],
      getRadius: 8,
      radiusUnits: 'pixels',
      getFillColor: (e) => [...KOYU, a(e, 240, 90)] as [number, number, number, number],
      getLineColor: (e) => [255, 255, 255, a(e, 255, 120)] as [number, number, number, number],
      getLineWidth: 3,
      lineWidthUnits: 'pixels',
      stroked: true,
      filled: true,
      pickable: false,
      updateTriggers: { getFillColor: konumlar, getLineColor: konumlar },
      parameters: USTTE,
    }),
    new TextLayer<EkipKonum>({
      id: 'ih-ekip-etiket',
      data: konumlar,
      getPosition: (e) => [e.lon, e.lat],
      getText: (e) => `${e.ad}\n${ekipZamanEtiketi(e)}`,
      getSize: 12,
      sizeUnits: 'pixels',
      getPixelOffset: [0, -14],
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'bottom',
      fontFamily: '-apple-system, "Segoe UI", Roboto, Arial, sans-serif',
      fontWeight: 700,
      lineHeight: 1.15,
      characterSet: 'auto',
      getColor: (e) => [...KOYU, a(e, 255, 130)] as [number, number, number, number],
      background: true,
      backgroundPadding: [6, 3],
      getBackgroundColor: (e) => [255, 255, 255, a(e, 235, 130)] as [number, number, number, number],
      getBorderColor: (e) => [...KOYU, a(e, 200, 70)] as [number, number, number, number],
      getBorderWidth: 1,
      pickable: false,
      updateTriggers: { getText: konumlar, getColor: konumlar, getBackgroundColor: konumlar, getBorderColor: konumlar },
      parameters: USTTE,
    }),
  ];
}
