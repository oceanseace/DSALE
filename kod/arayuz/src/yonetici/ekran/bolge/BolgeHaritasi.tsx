/**
 * Bölge planlayıcının haritası: her bina bölgesinin renginde, bölge sınırları
 * ince renkli çizgi, ortasında büyük bölge numarası.
 *
 * Harita altlığı (sokak / uydu / sade) ve atıf, yönetici haritasıyla aynı
 * modülden gelir (`src/harita/`); burada yalnız bölge boyaması yapılır. Aynı
 * tuval hem "bugünkü bölgeler"i hem "önizlenen plan"ı çizer — fark yalnız her
 * binanın hangi numarayı taşıdığıdır (`bolgeDizisi`).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { WebMercatorViewport, type MapViewState, type PickingInfo } from '@deck.gl/core';
import { yollar as yollarUcu } from '../../../api/uclar';
import { onbellektenOku } from '../../../depo/db';
import type { YolAgi } from '../../../api/tipler';
import { cizgileriAyikla, govdeSinirlari, kutuyuGenislet, type Kutu } from '../../../ortak/ayikla';
import { ALTLIK_KIPLERI, useAltlik, type AltlikKipi } from '../../../harita/altlik';
import { ipucu, ipucuYerlestir } from '../../../harita/ikiz';
import { useKaliciSecim } from '../../../harita/tercih';
import { AltlikSecici, Atif } from '../../../harita/HaritaDenetim';
import type { HaritaNoktasi } from '../../ortak/HaritaTuval';
import type { GeoCokgen } from '../../tipler';

type Rgb = [number, number, number];
type Konum = [number, number];

export interface HaritaBolgesi {
  bolge: number;
  ad: string;
  renk: string;
  poligon?: GeoCokgen | null;
  /** Etiketin yeri; yoksa bölgenin binalarının ortasına konur. */
  etiket?: [number, number] | null;
}

/** Yol çizgileri yönetici haritasının önbelleğinden (aynı anahtar) okunur. */
const ONBELLEK_YOL = 'yonetici.yollar';
const GRI: Rgb = [150, 160, 175];
const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;

export function renkCoz(hex: string | null | undefined): Rgb {
  const m = /^#?([0-9a-f]{6})$/i.exec((hex ?? '').trim());
  if (!m) return GRI;
  const s = parseInt(m[1], 16);
  return [(s >> 16) & 255, (s >> 8) & 255, s & 255];
}

/** Açık renkli bölgelerde (#6EFF3D gibi) beyaz yazı okunmaz: koyu yazıya geç. */
export function yaziRengi(hex: string): string {
  const [r, g, b] = renkCoz(hex);
  return 0.299 * r + 0.587 * g + 0.114 * b > 160 ? '#101828' : '#ffffff';
}

interface Ozellik {
  noktalar: HaritaNoktasi[];
  /** noktalar[i]'nin bölge numarası. Verilmezse noktanın bugünkü bölgesi. */
  bolgeDizisi?: ArrayLike<number> | null;
  bolgeler: HaritaBolgesi[];
  yukseklik?: number;
  /** Seçili bölge: öbürleri soluklaşır, görünüm ona yaklaşır. */
  odakBolge?: number | null;
  bolgeSecildi?: (bolge: number | null) => void;
  /** Değişince görünüm bütün binalara yeniden sığdırılır. */
  sigdirmaAnahtari?: string;
}

interface Etiket {
  bolge: number;
  konum: Konum;
  renk: Rgb;
}

interface Cokgen {
  bolge: number;
  halkalar: Konum[][];
  renk: Rgb;
}

export function BolgeHaritasi({
  noktalar,
  bolgeDizisi,
  bolgeler,
  yukseklik = 520,
  odakBolge = null,
  bolgeSecildi,
  sigdirmaAnahtari = '',
}: Ozellik) {
  const sarmalRef = useRef<HTMLDivElement | null>(null);
  const ipucuRef = useRef<HTMLDivElement | null>(null);
  const [gorunum, setGorunum] = useState<MapViewState | null>(null);
  const [boyut, setBoyut] = useState({ genislik: 0, yukseklik: 0 });
  const [yolAgi, setYolAgi] = useState<YolAgi | null>(null);
  const [altlikKipi, setAltlikKipi] = useKaliciSecim<AltlikKipi>('altlik', 'harita', ALTLIK_KIPLERI);
  const sigdirilan = useRef<string | null>(null);

  useEffect(() => {
    const kap = sarmalRef.current;
    if (!kap) return undefined;
    const olc = () => setBoyut({ genislik: kap.clientWidth, yukseklik: kap.clientHeight });
    olc();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const gozcu = new ResizeObserver(olc);
    gozcu.observe(kap);
    return () => gozcu.disconnect();
  }, []);

  /* Yollar: altlık gelmezse (çevrimdışı / engelli ağ) harita yine okunur. */
  useEffect(() => {
    let iptal = false;
    (async () => {
      const saklanan = await onbellektenOku<YolAgi>(ONBELLEK_YOL);
      if (!iptal && saklanan) setYolAgi(saklanan);
      if (saklanan) return;
      try {
        const yeni = await yollarUcu(null);
        if (!iptal && yeni) setYolAgi(yeni);
      } catch {
        /* yolsuz da çizilir */
      }
    })();
    return () => {
      iptal = true;
    };
  }, []);

  const bolgeNo = useCallback(
    (i: number) => {
      if (bolgeDizisi && i < bolgeDizisi.length) return bolgeDizisi[i] ?? 0;
      return noktalar[i]?.bolge ?? 0;
    },
    [bolgeDizisi, noktalar],
  );

  const renkler = useMemo(() => {
    const m = new Map<number, Rgb>();
    bolgeler.forEach((b) => m.set(b.bolge, renkCoz(b.renk)));
    return m;
  }, [bolgeler]);

  const bolgeAdi = useMemo(() => new Map(bolgeler.map((b) => [b.bolge, b.ad])), [bolgeler]);

  /* Her bina: konum + bölge (dizi indisiyle) — katmanlar bunu okur. */
  const veri = useMemo(
    () => noktalar.map((n, i) => ({ konum: n.konum, bolge: bolgeNo(i), i })),
    [noktalar, bolgeNo],
  );

  /* Etiket yeri: plan verdiyse o, yoksa bölgenin binalarının ortancası. */
  const etiketler = useMemo<Etiket[]>(() => {
    const toplam = new Map<number, { lon: number[]; lat: number[] }>();
    for (const v of veri) {
      if (!v.bolge) continue;
      let t = toplam.get(v.bolge);
      if (!t) {
        t = { lon: [], lat: [] };
        toplam.set(v.bolge, t);
      }
      t.lon.push(v.konum[0]);
      t.lat.push(v.konum[1]);
    }
    const ortanca = (d: number[]) => {
      const s = [...d].sort((a, b) => a - b);
      return s[Math.floor(s.length / 2)];
    };
    return bolgeler
      .map((b) => {
        const t = toplam.get(b.bolge);
        const konum: Konum | null = b.etiket
          ? [b.etiket[0], b.etiket[1]]
          : t && t.lon.length
            ? [ortanca(t.lon), ortanca(t.lat)]
            : null;
        return konum ? { bolge: b.bolge, konum, renk: renkler.get(b.bolge) ?? GRI } : null;
      })
      .filter((e): e is Etiket => e !== null);
  }, [veri, bolgeler, renkler]);

  const cokgenler = useMemo<Cokgen[]>(() => {
    const liste: Cokgen[] = [];
    for (const b of bolgeler) {
      const p = b.poligon;
      if (!p) continue;
      const renk = renkler.get(b.bolge) ?? GRI;
      if (p.type === 'Polygon') {
        liste.push({ bolge: b.bolge, halkalar: p.coordinates as Konum[][], renk });
      } else {
        for (const parca of p.coordinates as Konum[][][]) liste.push({ bolge: b.bolge, halkalar: parca, renk });
      }
    }
    return liste;
  }, [bolgeler, renkler]);

  /* Görünüm: bütün binalara (ya da odak bölgeye) sığdır. */
  const sigdir = useCallback((konumlar: Konum[]) => {
    const kutu = govdeSinirlari(konumlar);
    const kap = sarmalRef.current;
    if (!kutu || !kap || !kap.clientWidth || !kap.clientHeight) return;
    try {
      const g = new WebMercatorViewport({ width: kap.clientWidth, height: kap.clientHeight });
      const s = g.fitBounds(kutu, { padding: 40 });
      setGorunum({ longitude: s.longitude, latitude: s.latitude, zoom: Math.min(s.zoom, 15), pitch: 0, bearing: 0 });
    } catch {
      setGorunum({ longitude: kutu[0][0], latitude: kutu[0][1], zoom: 10, pitch: 0, bearing: 0 });
    }
  }, []);

  useEffect(() => {
    if (!veri.length || !boyut.genislik) return;
    const anahtar = `${sigdirmaAnahtari}|${odakBolge ?? 'hepsi'}`;
    if (sigdirilan.current === anahtar) return;
    sigdirilan.current = anahtar;
    const hedef = odakBolge ? veri.filter((v) => v.bolge === odakBolge) : veri;
    sigdir((hedef.length ? hedef : veri).map((v) => v.konum));
  }, [veri, odakBolge, sigdir, sigdirmaAnahtari, boyut.genislik]);

  const gorunenKutu = useMemo<Kutu | null>(() => {
    if (!gorunum || !boyut.genislik || !boyut.yukseklik) return null;
    try {
      const g = new WebMercatorViewport({ ...gorunum, width: boyut.genislik, height: boyut.yukseklik });
      return kutuyuGenislet(g.getBounds() as Kutu);
    } catch {
      return null;
    }
  }, [gorunum, boyut]);

  const yolCizgileri = useMemo(() => {
    if (!yolAgi) return [];
    const cikti: Array<{ yol: Konum[] }> = [];
    for (const o of yolAgi.features) {
      const g = o.geometry;
      if (g.type === 'LineString') cikti.push({ yol: g.coordinates as Konum[] });
      else g.coordinates.forEach((c) => cikti.push({ yol: c as Konum[] }));
    }
    return cikti;
  }, [yolAgi]);
  const cizilecekYollar = useMemo(
    () => cizgileriAyikla(yolCizgileri, gorunenKutu, 4000),
    [yolCizgileri, gorunenKutu],
  );

  const altlik = useAltlik(altlikKipi, gorunum, boyut.genislik, boyut.yukseklik);

  const soluk = useCallback((bolge: number) => odakBolge != null && bolge !== odakBolge, [odakBolge]);

  const katmanlar = useMemo(() => {
    const liste: unknown[] = [...altlik.katmanlar];
    if (cizilecekYollar.length && !altlik.ortulu) {
      liste.push(
        new PathLayer({
          id: 'bp-yollar',
          data: cizilecekYollar,
          getPath: (d: { yol: Konum[] }) => d.yol,
          getColor: [208, 216, 226],
          getWidth: 2,
          widthUnits: 'pixels',
          widthMinPixels: 1,
          parameters: USTTE,
        }),
      );
    }
    if (cokgenler.length) {
      liste.push(
        new PolygonLayer({
          id: 'bp-sinirlar',
          data: cokgenler,
          getPolygon: (d: Cokgen) => d.halkalar,
          getFillColor: (d: Cokgen) => [...d.renk, soluk(d.bolge) ? 10 : 34] as [number, number, number, number],
          getLineColor: (d: Cokgen) => [...d.renk, soluk(d.bolge) ? 70 : 230] as [number, number, number, number],
          getLineWidth: 2,
          lineWidthUnits: 'pixels',
          lineWidthMinPixels: 1.5,
          stroked: true,
          filled: true,
          pickable: Boolean(bolgeSecildi),
          onClick: (bilgi: PickingInfo) => {
            if (!bolgeSecildi) return false;
            const b = (bilgi.object as Cokgen | undefined)?.bolge ?? null;
            bolgeSecildi(b === odakBolge ? null : b);
            return true;
          },
          updateTriggers: { getFillColor: [odakBolge], getLineColor: [odakBolge] },
          parameters: USTTE,
        }),
      );
    }
    liste.push(
      new ScatterplotLayer({
        id: 'bp-binalar',
        data: veri,
        getPosition: (d: { konum: Konum }) => d.konum,
        getFillColor: (d: { bolge: number }) => {
          const r = renkler.get(d.bolge) ?? GRI;
          return [r[0], r[1], r[2], soluk(d.bolge) ? 45 : 235];
        },
        getRadius: 14,
        radiusUnits: 'meters',
        radiusMinPixels: 2.4,
        radiusMaxPixels: 9,
        stroked: altlikKipi !== 'sade',
        getLineColor: [255, 255, 255, 200],
        lineWidthMinPixels: 0.6,
        pickable: true,
        onClick: (bilgi: PickingInfo) => {
          if (!bolgeSecildi) return false;
          const b = (bilgi.object as { bolge: number } | undefined)?.bolge ?? null;
          bolgeSecildi(b === odakBolge ? null : b);
          return true;
        },
        updateTriggers: { getFillColor: [bolgeDizisi, renkler, odakBolge] },
        parameters: USTTE,
      }),
    );
    liste.push(
      new TextLayer({
        id: 'bp-etiketler',
        data: etiketler,
        getPosition: (d: Etiket) => d.konum,
        getText: (d: Etiket) => String(d.bolge),
        getSize: 15,
        sizeUnits: 'pixels',
        fontFamily: '-apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        fontWeight: 800,
        characterSet: '0123456789',
        getColor: (d: Etiket) => (soluk(d.bolge) ? [16, 24, 40, 110] : [16, 24, 40, 255]),
        background: true,
        backgroundPadding: [7, 4],
        getBackgroundColor: (d: Etiket) => (soluk(d.bolge) ? [255, 255, 255, 120] : [255, 255, 255, 245]),
        getBorderColor: (d: Etiket) => [...d.renk, soluk(d.bolge) ? 90 : 255] as [number, number, number, number],
        getBorderWidth: 2.5,
        pickable: Boolean(bolgeSecildi),
        onClick: (bilgi: PickingInfo) => {
          if (!bolgeSecildi) return false;
          const b = (bilgi.object as Etiket | undefined)?.bolge ?? null;
          bolgeSecildi(b === odakBolge ? null : b);
          return true;
        },
        updateTriggers: {
          getColor: [odakBolge],
          getBackgroundColor: [odakBolge],
          getBorderColor: [odakBolge],
        },
        parameters: USTTE,
      }),
    );
    return liste;
  }, [
    altlik.katmanlar,
    altlik.ortulu,
    altlikKipi,
    cizilecekYollar,
    cokgenler,
    veri,
    renkler,
    etiketler,
    bolgeDizisi,
    odakBolge,
    soluk,
    bolgeSecildi,
  ]);

  const ipucuGetir = useCallback(
    (bilgi: PickingInfo) => {
      if (bilgi.index < 0 || !bilgi.layer) return null;
      if (bilgi.layer.id === 'bp-binalar' && bilgi.object) {
        const v = bilgi.object as { bolge: number; i: number };
        const n = noktalar[v.i];
        if (!n) return null;
        return ipucu(n.ad || n.serial, n.loc, [
          v.bolge ? `${v.bolge}. bölge · ${bolgeAdi.get(v.bolge) ?? ''}` : 'Bölgesiz',
        ]);
      }
      if ((bilgi.layer.id === 'bp-sinirlar' || bilgi.layer.id === 'bp-etiketler') && bilgi.object) {
        const b = (bilgi.object as { bolge: number }).bolge;
        return ipucu(`${b}. bölge`, undefined, [bolgeAdi.get(b) ?? null, 'Tıklayın: bu bölgeye odaklan']);
      }
      return null;
    },
    [noktalar, bolgeAdi],
  );

  const haritaVar = Boolean(gorunum) && veri.length > 0;
  const atifMetni = altlikKipi === 'sade' ? 'Yollar © OpenStreetMap katkıcıları' : altlik.atif;

  return (
    <div className={`yon-harita bp-harita${haritaVar ? ' hr-atifli' : ''}`} ref={sarmalRef} style={{ height: yukseklik }}>
      {haritaVar ? (
        <DeckGL
          viewState={gorunum!}
          onViewStateChange={({ viewState }) => {
            ipucuYerlestir(ipucuRef.current, 0, 0, null);
            setGorunum(viewState as MapViewState);
          }}
          controller={{ dragRotate: false, touchRotate: false }}
          layers={katmanlar as never[]}
          style={{ position: 'absolute', inset: '0' }}
          onHover={(bilgi: PickingInfo) => ipucuYerlestir(ipucuRef.current, bilgi.x, bilgi.y, ipucuGetir(bilgi))}
          onClick={(bilgi: PickingInfo) => {
            if (bilgi.index < 0 && odakBolge != null) bolgeSecildi?.(null);
          }}
          getCursor={({ isHovering, isDragging }) => (isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab')}
        />
      ) : (
        <div className="yon-harita-bos">{veri.length ? 'Harita hazırlanıyor…' : 'Binalar yükleniyor…'}</div>
      )}

      {haritaVar ? (
        <div className="hr-panel">
          <div className="hr-satir">
            <AltlikSecici kip={altlikKipi} degisti={setAltlikKipi} />
          </div>
        </div>
      ) : null}

      {haritaVar && odakBolge != null ? (
        <button type="button" className="bp-odak-kapat" onClick={() => bolgeSecildi?.(null)}>
          {odakBolge}. bölge seçili · Bütün şehri göster
        </button>
      ) : null}

      {haritaVar ? <Atif metin={atifMetni} durum={altlik.durum} ortulu={altlik.ortulu} /> : null}
      <div className="hr-ipucu" ref={ipucuRef} role="tooltip" />
    </div>
  );
}
