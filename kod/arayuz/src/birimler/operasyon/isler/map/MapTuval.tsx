/**
 * MAP tuvali (deck.gl): işler bina koordinatında ışıyan nokta; kümeleme yok, aynı binadakiler halka
 * şeklinde yana kayar. Rengi değişen nokta kısa süre nabız atar, çıkan nokta solar. Aramadan gelen
 * `vurgu` kamerayı oraya uçurur ve iğne + halka bırakır. Altlık Harita · Uydu · Sade (cekirdek/harita) ve Sığdır.
 * Giriş: <MapTuval>. Çağıran: IsHaritasiEkrani. Noktaya basınca `sec(isNo)` (ekran İş çekmecesini açar).
 * Çoklu seçim (toplu "Ata…", Photoshop gibi): araç "Kement" (serbest çizim) ya da "Dikdörtgen" seçiliyken
 * sürüklemek seçimi YENİDEN kurar; Shift ile ekler, Alt ile çıkarır. Araç seçili değilken Shift+sürükle kementle
 * ekler; Shift+tık tek noktayı ekler/çıkarır. Seçili noktalar beyaz halkalı çizilir.
 * `ekKatmanlar` iş noktalarının üstüne çizilir (MAP "Ekipler" katmanı, map/ekipKatmani.ts); `ekDugmeler` alt paneldeki
 * Sığdır satırına eklenir.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import DeckGL, { type DeckGLRef } from '@deck.gl/react';
import { ScatterplotLayer } from '@deck.gl/layers';
import { WebMercatorViewport, type MapViewState, type PickingInfo } from '@deck.gl/core';
import { ALTLIK_KIPLERI, useAltlik, type AltlikKipi } from '../../../../cekirdek/harita/altlik';
import { useKaliciSecim } from '../../../../cekirdek/harita/tercih';
import { AltlikSecici, Atif } from '../../../../cekirdek/harita/HaritaDenetim';
import { hedefKatmanlari, ucusGorunumu, useNabiz } from '../../../../cekirdek/harita/hedefKatman';
import { govdeSinirlari } from '../../../../cekirdek/ortak/ayikla';
import { kayma, RENK, type Konum, type Nokta } from './noktalar';
import { SOLMA_MS } from './noktaGecisi';

/** Aramadan seçilen yer. `kimlik` her seçimde artar: aynı yer yeniden seçilince de uçulur. */
export interface Vurgu {
  konum: Konum;
  /** Seçilen iş haritada nokta olarak varsa iğne o noktanın üstüne oturur. */
  isNo?: string;
  kimlik: number;
}

const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;
const NABIZ_MS = 6000;
const BURSA: MapViewState = { longitude: 29.02, latitude: 40.2, zoom: 10.5, pitch: 0, bearing: 0 };

function azHareket(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

function kacis(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}

/** Seçim değişikliği: ekle (kement), çıkar (Alt), tek noktayı aç/kapa (Shift+tık). */
export type SecimKipi = 'ekle' | 'cikar' | 'degistir' | 'yerine';
export type SecimAraci = 'kement' | 'dikdortgen';

/** Nokta (x, y) çokgenin içinde mi (ışın sayma). */
export function cokgendeMi(x: number, y: number, c: ReadonlyArray<readonly [number, number]>): boolean {
  let ic = false;
  for (let i = 0, j = c.length - 1; i < c.length; j = i++) {
    const [xi, yi] = c[i];
    const [xj, yj] = c[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi || 1e-9) + xi) ic = !ic;
  }
  return ic;
}

export function MapTuval({
  noktalar,
  sigdirmaAnahtari,
  sec,
  vurgu,
  secili,
  secimDegisti,
  ekKatmanlar,
  ekDugmeler,
}: {
  noktalar: Nokta[];
  /** Değişince (süzgeç değişti) bütün noktalar ekrana sığdırılır; boşsa henüz sığdırılmaz. */
  sigdirmaAnahtari: string;
  sec: (no: string) => void;
  vurgu: Vurgu | null;
  /** Toplu seçim (Shift+tık / kement); verilmezse seçim kapalı. */
  secili?: ReadonlySet<string>;
  secimDegisti?: (nolar: string[], kip: SecimKipi) => void;
  /** İş noktalarının üstüne çizilen ek deck.gl katmanları (ör. ekip GPS konumları). */
  ekKatmanlar?: unknown[];
  /** Alt paneldeki düğme satırına ek düğmeler (ör. "Ekipler" aç/kapa). */
  ekDugmeler?: ReactNode;
}) {
  const sarmal = useRef<HTMLDivElement | null>(null);
  const deckRef = useRef<DeckGLRef>(null);
  const [arac, setArac] = useState<SecimAraci | null>(null);
  const kementKipi = arac !== null;
  const [kement, setKement] = useState<Array<[number, number]> | null>(null);
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

  const sigdir = useCallback(() => {
    const kap = sarmal.current;
    if (!kap || !kap.clientWidth || !kap.clientHeight) return;
    const sinir = govdeSinirlari(
      noktalar.filter((n) => !n.cikis).map((n) => [n.lon, n.lat] as [number, number]),
      0.04,
    );
    if (!sinir) {
      setGorunum(BURSA);
      return;
    }
    try {
      const g = new WebMercatorViewport({ width: kap.clientWidth, height: kap.clientHeight }).fitBounds(sinir, {
        padding: 80,
      });
      setGorunum({ longitude: g.longitude, latitude: g.latitude, zoom: Math.min(g.zoom, 15), pitch: 0, bearing: 0 });
    } catch {
      setGorunum({ longitude: sinir[0][0], latitude: sinir[0][1], zoom: 12, pitch: 0, bearing: 0 });
    }
  }, [noktalar]);

  useEffect(() => {
    if (!boyut.genislik || !sigdirmaAnahtari || sigdirilan.current === sigdirmaAnahtari) return;
    sigdirilan.current = sigdirmaAnahtari;
    sigdir();
  }, [sigdirmaAnahtari, boyut.genislik, sigdir]);

  /* Aramadan seçilen yere uç. */
  useEffect(() => {
    if (!vurgu) return;
    setGorunum((g) => ucusGorunumu(g, vurgu.konum));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vurgu?.kimlik]);

  const altlik = useAltlik(altlikKipi, gorunum, boyut.genislik, boyut.yukseklik);

  /* Nabız: yalnız yeni değişen nokta varken ve hareket azaltılmamışsa kare kare çizilir. */
  const [an, setAn] = useState(() => Date.now());
  useEffect(() => {
    if (azHareket() || !noktalar.some((n) => n.degisti && Date.now() - n.degisti < NABIZ_MS)) return undefined;
    let id = 0;
    const adim = () => {
      setAn(Date.now());
      id = window.requestAnimationFrame(adim);
    };
    id = window.requestAnimationFrame(adim);
    const dur = window.setTimeout(() => {
      window.cancelAnimationFrame(id);
      setAn(Date.now());
    }, NABIZ_MS);
    return () => {
      window.cancelAnimationFrame(id);
      window.clearTimeout(dur);
    };
  }, [noktalar]);

  const katmanlar = useMemo(() => {
    const nabiz = (n: Nokta) => {
      if (!n.degisti || n.cikis) return 0;
      const g = an - n.degisti;
      if (g >= NABIZ_MS || g < 0) return 0;
      return (0.5 + 0.5 * Math.sin((g / 1000) * Math.PI * 2)) * (1 - g / NABIZ_MS);
    };
    const gecis = {
      getFillColor: { duration: SOLMA_MS - 100 },
      getLineColor: { duration: SOLMA_MS - 100 },
    };
    const liste: unknown[] = [...altlik.katmanlar];
    /* 1) Işıma (halo): geniş, saydam, renkli; içten dışa iki kat. */
    for (const [id, yaricap, alfa] of [
      ['ih-isima-dis', 20, 28],
      ['ih-isima', 12, 70],
    ] as const) {
      liste.push(
        new ScatterplotLayer<Nokta>({
          id,
          data: noktalar,
          getPosition: (n) => [n.lon, n.lat],
          getPixelOffset: kayma,
          getRadius: (n) => (n.cikis ? 3 : yaricap + nabiz(n) * 10),
          radiusUnits: 'pixels',
          getFillColor: (n) => [...RENK[n.kat], n.cikis ? 0 : Math.round(alfa + nabiz(n) * 90)] as [number, number, number, number],
          stroked: false,
          filled: true,
          pickable: false,
          transitions: gecis,
          updateTriggers: { getFillColor: [noktalar, an], getRadius: [noktalar, an], getPixelOffset: noktalar },
          parameters: USTTE,
        }),
      );
    }
    /* 2) Çekirdek: renkli dolgu + parlak renkli halka. */
    liste.push(
      new ScatterplotLayer<Nokta>({
        id: 'ih-noktalar',
        data: noktalar,
        getPosition: (n) => [n.lon, n.lat],
        getPixelOffset: kayma,
        getRadius: (n) => (n.cikis ? 2 : 7),
        radiusUnits: 'pixels',
        getFillColor: (n) => [...RENK[n.kat], n.cikis ? 0 : 240] as [number, number, number, number],
        getLineColor: (n) =>
          [...RENK[n.kat].map((c) => Math.min(255, c + 70)), n.cikis ? 0 : 255] as [number, number, number, number],
        getLineWidth: 2.5,
        lineWidthUnits: 'pixels',
        stroked: true,
        filled: true,
        pickable: true,
        transitions: gecis,
        updateTriggers: { getFillColor: noktalar, getLineColor: noktalar, getPixelOffset: noktalar },
        parameters: USTTE,
      }),
    );
    /* 3) Seçili noktalar: beyaz kalın halka (toplu "Ata…"). */
    if (secili && secili.size) {
      liste.push(
        new ScatterplotLayer<Nokta>({
          id: 'ih-secili',
          data: noktalar.filter((n) => !n.cikis && secili.has(n.no)),
          getPosition: (n) => [n.lon, n.lat],
          getPixelOffset: kayma,
          getRadius: 10,
          radiusUnits: 'pixels',
          getLineColor: [255, 255, 255, 255],
          getLineWidth: 3,
          lineWidthUnits: 'pixels',
          stroked: true,
          filled: false,
          pickable: false,
          updateTriggers: { getPixelOffset: noktalar },
          parameters: USTTE,
        }),
      );
    }
    return liste;
  }, [altlik.katmanlar, noktalar, an, secili]);

  /* Esc: önce Kement/Dikdörtgen aracından çıkar (seçim kalır); ikinci Esc seçimi temizler (IsHaritasiEkrani). */
  useEffect(() => {
    if (!arac) return undefined;
    const tus = (o: KeyboardEvent) => {
      if (o.key !== 'Escape') return;
      const h = o.target instanceof HTMLElement ? o.target : null;
      if (h && (h.closest('input, textarea, select, [contenteditable="true"]') || h.closest('[role="dialog"]'))) return;
      o.preventDefault();
      o.stopImmediatePropagation();
      setKement(null);
      setArac(null);
    };
    window.addEventListener('keydown', tus, true);
    return () => window.removeEventListener('keydown', tus, true);
  }, [arac]);

  /* Shift+tık / Shift+sürükle / Kement: yakalama evresinde deck'ten önce alınır (harita kaymaz). */
  const secimAcik = Boolean(secimDegisti);
  const noktaRef = useRef(noktalar);
  noktaRef.current = noktalar;
  const gorunumRef = useRef(gorunum);
  gorunumRef.current = gorunum;
  const kipRef = useRef(arac);
  kipRef.current = arac;
  const degistiRef = useRef(secimDegisti);
  degistiRef.current = secimDegisti;
  useEffect(() => {
    const kap = sarmal.current;
    if (!kap || !secimAcik) return undefined;
    const bas = (o: PointerEvent) => {
      if (o.button !== 0 || !(o.shiftKey || kipRef.current)) return;
      if (!(o.target instanceof HTMLCanvasElement)) return; // panel düğmeleri değil, harita
      o.preventDefault();
      o.stopPropagation();
      const r = kap.getBoundingClientRect();
      const yol: Array<[number, number]> = [[o.clientX - r.left, o.clientY - r.top]];
      const cikar = o.altKey;
      const aracSecili = kipRef.current;
      const dikdortgen = aracSecili === 'dikdortgen';
      const kip: SecimKipi = o.altKey ? 'cikar' : o.shiftKey || !aracSecili ? 'ekle' : 'yerine';
      const sekil = (): Array<[number, number]> => {
        if (!dikdortgen || yol.length < 2) return yol;
        const [x0, y0] = yol[0];
        const [x1, y1] = yol[yol.length - 1];
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
      };
      setKement([...yol]);
      const tasi = (e: PointerEvent) => {
        e.preventDefault();
        e.stopPropagation();
        const son = yol[yol.length - 1];
        const p: [number, number] = [e.clientX - r.left, e.clientY - r.top];
        if (Math.hypot(p[0] - son[0], p[1] - son[1]) < 3) return;
        if (dikdortgen && yol.length > 1) yol[1] = p;
        else yol.push(p);
        setKement([...sekil()]);
      };
      const birak = (e: PointerEvent) => {
        e.preventDefault();
        e.stopPropagation();
        window.removeEventListener('pointermove', tasi, true);
        window.removeEventListener('pointerup', birak, true);
        setKement(null);
        const f = degistiRef.current;
        const g = gorunumRef.current;
        if (!f || !g) return;
        const [x0, y0] = yol[0];
        const uzak = yol.some(([x, y]) => Math.hypot(x - x0, y - y0) > 6);
        if (!uzak) {
          const b = deckRef.current?.pickObject({ x: x0, y: y0, radius: 6, layerIds: ['ih-noktalar'] });
          const n = b?.object as Nokta | undefined;
          if (n && !n.cikis) f([n.no], cikar ? 'cikar' : 'degistir');
          return;
        }
        const alan = sekil();
        if (alan.length < 3) return;
        const vp = new WebMercatorViewport({ ...g, width: kap.clientWidth, height: kap.clientHeight });
        const icerdekiler = noktaRef.current
          .filter((n) => {
            if (n.cikis) return false;
            const [px, py] = vp.project([n.lon, n.lat]);
            const [dx, dy] = kayma(n);
            return cokgendeMi(px + dx, py + dy, alan);
          })
          .map((n) => n.no);
        if (icerdekiler.length || kip === 'yerine') f(icerdekiler, kip);
      };
      window.addEventListener('pointermove', tasi, true);
      window.addEventListener('pointerup', birak, true);
    };
    kap.addEventListener('pointerdown', bas, true);
    return () => kap.removeEventListener('pointerdown', bas, true);
  }, [secimAcik]);

  /* Vurgu: seçilen iş haritadaysa kendi noktasının (kaydırılmış) üstüne, değilse bulunan yere iğne. */
  const faz = useNabiz(vurgu ? String(vurgu.kimlik) : null);
  const vurguKatmanlari = useMemo(() => {
    if (!vurgu) return [];
    const n = vurgu.isNo ? noktalar.find((x) => x.no === vurgu.isNo && !x.cikis) : undefined;
    return n
      ? hedefKatmanlari([n.lon, n.lat], faz, 'mp-vurgu', kayma(n))
      : hedefKatmanlari(vurgu.konum, faz, 'mp-vurgu');
  }, [vurgu, noktalar, faz]);

  const ipucu = useCallback((bilgi: PickingInfo) => {
    const n = bilgi.object as Nokta | undefined;
    if (!n || n.cikis) return null;
    return {
      html: `<div class="ih-ipucu"><b>${kacis(n.baslik)}</b>${n.alt ? `<br>${kacis(n.alt)}` : ''}</div>`,
      style: { background: 'transparent', padding: '0' },
    };
  }, []);

  const tikla = (bilgi: PickingInfo, olay?: { srcEvent?: { shiftKey?: boolean } }) => {
    if (olay?.srcEvent?.shiftKey || kementKipi) return; // seçim hareketi (yakalama evresinde işlendi)
    const n = bilgi.object as Nokta | undefined;
    if (n && !n.cikis) sec(n.no);
  };

  return (
    <div className="yon-harita hr-atifli" ref={sarmal}>
      {gorunum ? (
        <DeckGL
          ref={deckRef}
          viewState={gorunum}
          onViewStateChange={({ viewState }) => setGorunum(viewState as MapViewState)}
          controller={{ dragRotate: false, touchRotate: false }}
          layers={[...katmanlar, ...(ekKatmanlar ?? []), ...vurguKatmanlari] as never[]}
          style={{ position: 'absolute', inset: '0' }}
          getTooltip={ipucu as never}
          getCursor={({ isHovering }) => (kementKipi ? 'crosshair' : isHovering ? 'pointer' : 'grab')}
          onClick={tikla}
        />
      ) : (
        <div className="yon-harita-bos">Harita hazırlanıyor…</div>
      )}
      <div className="hr-panel" style={{ top: 'auto', bottom: 28 }}>
        <div className="hr-satir">
          <AltlikSecici kip={altlikKipi} degisti={setAltlikKipi} />
          <button type="button" className="ie-sigdir" onClick={sigdir} title="Gösterilen bütün işleri ekrana sığdır">
            Sığdır
          </button>
          {secimAcik
            ? (
                [
                  ['kement', 'Kement', 'Serbest çizerek seç'],
                  ['dikdortgen', 'Dikdörtgen', 'Dikdörtgen çizerek seç'],
                ] as const
              ).map(([a, ad, ipucu]) => (
                <button
                  key={a}
                  type="button"
                  className={`ie-sigdir${arac === a ? ' etkin' : ''}`}
                  aria-pressed={arac === a}
                  onClick={() => setArac((o) => (o === a ? null : a))}
                  title={`${ipucu}: sürüklemek seçimi yeniden kurar, Shift ile ekler, Alt ile çıkarır. Esc araçtan çıkar, ikinci Esc seçimi temizler. Kapalıyken Shift+sürükle kementle ekler; Shift+tık tek işi seçer.`}
                >
                  {ad}
                </button>
              ))
            : null}
          {ekDugmeler}
        </div>
      </div>
      {kement && kement.length > 1 ? (
        <svg className="mp-kement" aria-hidden="true">
          <polygon points={kement.map(([x, y]) => `${x},${y}`).join(' ')} />
        </svg>
      ) : null}
      <Atif metin={altlikKipi === 'sade' ? null : altlik.atif} durum={altlik.durum} />
    </div>
  );
}
