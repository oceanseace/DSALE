/**
 * İş emri haritası — her daire bir yer (bina / site / mahalle merkezi); büyüklüğü
 * oradaki iş sayısı, rengi öbeği (ya da bölme önizlemesinde parçası).
 *
 * Konumu kaba olan işler (yalnız ilçe merkezi bilinen) içi boş halka olarak çizilir:
 * "burada bir yerde" demektir, tam yeri değil. Altlık yönetici haritasıyla aynı
 * (Harita · Uydu · Sade); seçim cihazda hatırlanır.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { WebMercatorViewport, type MapViewState, type PickingInfo } from '@deck.gl/core';
import { ALTLIK_KIPLERI, useAltlik, type AltlikKipi } from '../../harita/altlik';
import { useKaliciSecim } from '../../harita/tercih';
import { AltlikSecici, Atif } from '../../harita/HaritaDenetim';
import { govdeSinirlari } from '../../ortak/ayikla';

export type Renk = [number, number, number];

export interface IsNoktasi {
  id: number;
  lat: number;
  lon: number;
  renk: Renk;
  /** ilçe merkezi gibi kaba konum */
  kaba: boolean;
  /** Önizlemede soluk (seçim dışı) */
  soluk?: boolean;
  baslik: string;
  alt: string;
}

export interface HaritaEtiketi {
  lat: number;
  lon: number;
  metin: string;
  renk: Renk;
}

interface Yer {
  anahtar: string;
  lat: number;
  lon: number;
  renk: Renk;
  kaba: boolean;
  soluk: boolean;
  sayi: number;
  ids: number[];
  satirlar: string[];
}

const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;

export function IsHaritasi({
  noktalar,
  etiketler = [],
  sigdirmaAnahtari,
  odak,
  yerTiklandi,
  yukseklik = 560,
}: {
  noktalar: IsNoktasi[];
  etiketler?: HaritaEtiketi[];
  /** Değişince görünüm noktalara yeniden sığdırılır. */
  sigdirmaAnahtari: string;
  /** Verilirse görünüm yalnız bu işlere sığdırılır (ör. bölünen öbek). */
  odak?: number[];
  yerTiklandi?: (ids: number[]) => void;
  yukseklik?: number | string;
}) {
  const sarmal = useRef<HTMLDivElement | null>(null);
  const [gorunum, setGorunum] = useState<MapViewState | null>(null);
  const [boyut, setBoyut] = useState({ genislik: 0, yukseklik: 0 });
  const [altlikKipi, setAltlikKipi] = useKaliciSecim<AltlikKipi>('altlik', 'harita', ALTLIK_KIPLERI);
  const sigdirilan = useRef<string | null>(null);

  useEffect(() => {
    const kap = sarmal.current;
    if (!kap) return undefined;
    const olc = () => setBoyut({ genislik: kap.clientWidth, yukseklik: kap.clientHeight });
    olc();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const gozcu = new ResizeObserver(olc);
    gozcu.observe(kap);
    return () => gozcu.disconnect();
  }, []);

  /* Aynı yerdeki işler tek daire: sayısı yarıçapı, çoğunluk rengi daireyi belirler. */
  const yerler = useMemo<Yer[]>(() => {
    const harita = new Map<string, Yer & { renkSay: Map<string, number> }>();
    for (const n of noktalar) {
      const anahtar = `${n.lat.toFixed(5)},${n.lon.toFixed(5)}`;
      let y = harita.get(anahtar);
      if (!y) {
        y = {
          anahtar,
          lat: n.lat,
          lon: n.lon,
          renk: n.renk,
          kaba: n.kaba,
          soluk: true,
          sayi: 0,
          ids: [],
          satirlar: [],
          renkSay: new Map(),
        };
        harita.set(anahtar, y);
      }
      y.sayi += 1;
      y.ids.push(n.id);
      y.soluk = y.soluk && Boolean(n.soluk);
      if (y.satirlar.length < 6) y.satirlar.push(`${n.baslik} — ${n.alt}`);
      const rk = n.renk.join(',');
      y.renkSay.set(rk, (y.renkSay.get(rk) ?? 0) + 1);
    }
    return [...harita.values()].map((y) => {
      let enCok = '';
      let say = -1;
      y.renkSay.forEach((v, k) => {
        if (v > say) {
          say = v;
          enCok = k;
        }
      });
      return { ...y, renk: enCok.split(',').map(Number) as Renk };
    });
  }, [noktalar]);

  const sigdir = useCallback(() => {
    const kap = sarmal.current;
    if (!kap || !kap.clientWidth || !kap.clientHeight) return;
    // Odak verilmişse (bölme önizlemesi) yalnız ona; uçtaki az sayıdaki iş (Yalova, İnegöl…)
    // yoğun merkezi avuç içine çevirmesin diye %8–%92 aralığı.
    const odakKumesi = odak?.length ? new Set(odak) : null;
    const hedef = odakKumesi ? noktalar.filter((n) => odakKumesi.has(n.id)) : noktalar;
    const kesin = hedef.filter((n) => !n.kaba).map((n) => [n.lon, n.lat] as [number, number]);
    const sinir = govdeSinirlari(kesin, 0.08) ?? govdeSinirlari(hedef.map((n) => [n.lon, n.lat]));
    if (!sinir) {
      setGorunum({ longitude: 29.02, latitude: 40.2, zoom: 10.5, pitch: 0, bearing: 0 });
      return;
    }
    try {
      const g = new WebMercatorViewport({ width: kap.clientWidth, height: kap.clientHeight })
        .fitBounds(sinir, { padding: 56 });
      setGorunum({ longitude: g.longitude, latitude: g.latitude, zoom: Math.min(g.zoom, 15.5), pitch: 0, bearing: 0 });
    } catch {
      setGorunum({ longitude: sinir[0][0], latitude: sinir[0][1], zoom: 12, pitch: 0, bearing: 0 });
    }
  }, [noktalar, odak]);

  useEffect(() => {
    if (!boyut.genislik || sigdirilan.current === sigdirmaAnahtari) return;
    sigdirilan.current = sigdirmaAnahtari;
    sigdir();
  }, [sigdirmaAnahtari, boyut.genislik, sigdir]);

  const altlik = useAltlik(altlikKipi, gorunum, boyut.genislik, boyut.yukseklik);

  const katmanlar = useMemo(() => {
    const liste: unknown[] = [...altlik.katmanlar];
    liste.push(
      new ScatterplotLayer<Yer>({
        id: 'is-yerleri',
        data: yerler,
        getPosition: (y) => [y.lon, y.lat],
        getRadius: (y) => 5 + Math.sqrt(y.sayi) * 3.2,
        radiusUnits: 'pixels',
        getFillColor: (y) => (y.kaba ? [0, 0, 0, 0] : [...y.renk, y.soluk ? 60 : 220]) as never,
        getLineColor: (y) => (y.kaba ? [...y.renk, y.soluk ? 90 : 255] : [255, 255, 255, y.soluk ? 90 : 230]) as never,
        getLineWidth: (y) => (y.kaba ? 3 : 1.5),
        lineWidthUnits: 'pixels',
        stroked: true,
        filled: true,
        pickable: true,
        updateTriggers: { getFillColor: yerler, getLineColor: yerler },
        parameters: USTTE,
      }),
    );
    liste.push(
      new TextLayer<Yer>({
        id: 'is-sayilari',
        data: yerler.filter((y) => y.sayi > 1 && !y.soluk),
        getPosition: (y) => [y.lon, y.lat],
        getText: (y) => String(y.sayi),
        getSize: 11,
        getColor: (y) => (y.kaba ? [...y.renk, 255] : [255, 255, 255, 255]) as never,
        fontWeight: 800,
        fontFamily: 'system-ui, sans-serif',
        characterSet: '0123456789',
        pickable: false,
        parameters: USTTE,
      }),
    );
    if (etiketler.length) {
      liste.push(
        new TextLayer<HaritaEtiketi>({
          id: 'is-etiketler',
          data: etiketler,
          getPosition: (e) => [e.lon, e.lat],
          getText: (e) => e.metin,
          getSize: 14,
          getColor: (e) => [...e.renk, 255] as never,
          fontWeight: 800,
          fontFamily: 'system-ui, sans-serif',
          characterSet: 'auto',
          outlineWidth: 4,
          outlineColor: [255, 255, 255, 235],
          fontSettings: { sdf: true },
          getTextAnchor: 'middle',
          getAlignmentBaseline: 'center',
          pickable: false,
          parameters: USTTE,
        }),
      );
    }
    return liste;
  }, [altlik.katmanlar, yerler, etiketler]);

  const ipucu = useCallback((bilgi: PickingInfo) => {
    const y = bilgi.object as Yer | undefined;
    if (!y) return null;
    const ek = y.sayi > y.satirlar.length ? `<div class="ie-ipucu-ek">+${y.sayi - y.satirlar.length} iş daha</div>` : '';
    return {
      html: `<div class="ie-ipucu"><b>${y.sayi} iş</b>${y.kaba ? ' · yalnız ilçe merkezi biliniyor' : ''}<br>${y.satirlar
        .map(kacis)
        .join('<br>')}${ek}</div>`,
      style: { background: 'transparent', padding: '0' },
    };
  }, []);

  const atif = altlikKipi === 'sade' ? null : altlik.atif;

  return (
    <div className="yon-harita ie-harita hr-atifli" ref={sarmal} style={{ height: yukseklik }}>
      {gorunum ? (
        <DeckGL
          viewState={gorunum}
          onViewStateChange={({ viewState }) => setGorunum(viewState as MapViewState)}
          controller={{ dragRotate: false, touchRotate: false }}
          layers={katmanlar as never[]}
          style={{ position: 'absolute', inset: '0' }}
          getTooltip={ipucu as never}
          onClick={(bilgi: PickingInfo) => {
            const y = bilgi.object as Yer | undefined;
            if (y) yerTiklandi?.(y.ids);
          }}
        />
      ) : (
        <div className="yon-harita-bos">Harita hazırlanıyor…</div>
      )}
      <div className="hr-panel">
        <div className="hr-satir">
          <AltlikSecici kip={altlikKipi} degisti={setAltlikKipi} />
          <button type="button" className="ie-sigdir" onClick={sigdir} title="Bütün işleri ekrana sığdır">
            Sığdır
          </button>
        </div>
      </div>
      <Atif metin={atif} durum={altlik.durum} />
    </div>
  );
}

function kacis(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}
