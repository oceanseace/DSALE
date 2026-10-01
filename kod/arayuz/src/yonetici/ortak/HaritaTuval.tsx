/**
 * Yönetici haritası — bütün şehir tek tuvalde.
 *
 * Altlık üç türlü: "Harita" (sokak karoları), "Uydu" ve "Sade" (yalnız
 * sunucudaki OSM yol çizgileri — dışarıya hiç istek gitmez). Karo gelmezse
 * (çevrimdışı / engelli ağ) harita sessizce sade yollara düşer; boş kalmaz.
 * Seçim cihazda hatırlanır. Dışarı giden tek şey karo isteğidir (z/x/y).
 *
 * Üstünde binalar. Her bina bir nokta; rengi durumudur: yeşil dokunuldu,
 * gri bekliyor, sarı tekrar gel, kırmızı altyapı. "3B" açılınca noktaların
 * yerini gerçek taban çizgileriyle kat kat yükselen binalar alır; rengi
 * seçilen mercekten gelir (durum · fırsat · doluluk · açık iş emri).
 *
 * `secimKipi` açıkken tuvalin üstüne şeffaf bir katman gelir: yönetici fareyle
 * (ya da parmağıyla) dikdörtgen çizer, içindeki binalar seçilir.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PathLayer, ScatterplotLayer } from '@deck.gl/layers';
import { WebMercatorViewport, type MapViewState, type PickingInfo } from '@deck.gl/core';
import { yollar as yollarUcu } from '../../api/uclar';
import { onbellegeYaz, onbellektenOku } from '../../depo/db';
import type { BinaDurumu, YolAgi } from '../../api/tipler';
import {
  ayikla,
  cizgileriAyikla,
  govdeSinirlari,
  kutuyuGenislet,
  type Kutu,
} from '../../ortak/ayikla';
import { ALTLIK_KIPLERI, useAltlik, type AltlikKipi } from '../../harita/altlik';
import {
  boya,
  ikizKatmani,
  ipucu,
  ipucuYerlestir,
  mercekSatiri,
  MERCEKLER,
  useIkiz,
  type Mercek,
} from '../../harita/ikiz';
import {
  cokgenIcinde,
  duzGorunum,
  ekrandanCokgen,
  fareVar,
  kucukEkran,
  ucBGorunumu,
  UC_B_EGIM,
} from '../../harita/kamera';
import { useKaliciSecim } from '../../harita/tercih';
import { AltlikSecici, Atif, MercekLejanti, MercekSecici, UcBDugmesi } from '../../harita/HaritaDenetim';

export type Konum = [number, number];

export interface HaritaNoktasi {
  serial: string;
  /** Bina adı; yoksa seri numarası gösterilir. */
  ad?: string;
  /** Location Id */
  loc?: string;
  konum: Konum;
  durum: BinaDurumu;
  firsat: number;
  bolge: number | null;
}

export const DURUM_RENKLERI: Record<BinaDurumu, [number, number, number]> = {
  bekliyor: [163, 174, 189],
  planli: [11, 99, 229],
  ziyaret_edildi: [15, 138, 74],
  tekrar_gel: [224, 138, 30],
  girilemedi: [176, 106, 20],
  altyapi_sorunu: [192, 42, 42],
};

const LEJANT: Array<{ durum: BinaDurumu; etiket: string }> = [
  { durum: 'bekliyor', etiket: 'Bekliyor' },
  { durum: 'ziyaret_edildi', etiket: 'Dokunuldu' },
  { durum: 'tekrar_gel', etiket: 'Tekrar gel' },
  { durum: 'girilemedi', etiket: 'Girilemedi' },
  { durum: 'altyapi_sorunu', etiket: 'Altyapı' },
  { durum: 'planli', etiket: 'Bugün planlı' },
];

const DURUM_ADI = Object.fromEntries(LEJANT.map((l) => [l.durum, l.etiket])) as Record<
  BinaDurumu,
  string
>;

const ONBELLEK_YOL = 'yonetici.yollar';

/** Derinliğe bakmadan en üste çizilen katmanlar (3B'de binaların arkasında kalmasın). */
const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;

interface Ozellik {
  noktalar: HaritaNoktasi[];
  yukseklik?: number;
  /** Kutu çizerek seçim açık mı? */
  secimKipi?: boolean;
  /** Kutu tamamlandığında: içindeki binalar + coğrafi sınırlar. */
  secimBitti?: (seriler: string[], kutu: [number, number, number, number]) => void;
  /** Vurgulanan (seçili) binalar. */
  vurgulanan?: Set<string>;
  /** Seçilen binaları gezilecek sırayla bağlayan çizgi. */
  rota?: Konum[];
  /** Bir noktaya tıklandığında. */
  noktaSecildi?: (nokta: HaritaNoktasi | null) => void;
  secili?: HaritaNoktasi | null;
  /** Sağ üstteki araçlar (düğmeler). */
  araclar?: React.ReactNode;
  /** Seçili noktanın altında açılan kart. */
  kart?: React.ReactNode;
  lejant?: boolean;
  /** Görünümü bu binalara sığdır (değişince yeniden sığdırılır). */
  sigdirmaAnahtari?: string;
  /** Elle odaklama: anahtar değişince görünüm `odakNoktalari`na sığdırılır. */
  odakAnahtari?: string;
  odakNoktalari?: HaritaNoktasi[];
}

export function HaritaTuval({
  noktalar,
  yukseklik = 460,
  secimKipi = false,
  secimBitti,
  vurgulanan,
  rota,
  noktaSecildi,
  secili,
  araclar,
  kart,
  lejant = true,
  sigdirmaAnahtari = '',
  odakAnahtari,
  odakNoktalari,
}: Ozellik) {
  const sarmalRef = useRef<HTMLDivElement | null>(null);
  const ipucuRef = useRef<HTMLDivElement | null>(null);
  const [gorunum, setGorunum] = useState<MapViewState | null>(null);
  const [yolAgi, setYolAgi] = useState<YolAgi | null>(null);
  const [webglVar] = useState(() => webglDestekli());
  const [kutu, setKutu] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const sigdirilan = useRef<string | null>(null);
  const odaklanan = useRef<string | null>(null);
  const [boyut, setBoyut] = useState({ genislik: 0, yukseklik: 0 });

  /* Altlık ve 3B tercihleri — altlık ve mercek cihazda hatırlanır. */
  const [altlikKipi, setAltlikKipi] = useKaliciSecim<AltlikKipi>('altlik', 'harita', ALTLIK_KIPLERI);
  const [mercek, setMercek] = useKaliciSecim<Mercek>('mercek', 'durum', MERCEKLER);
  const [ucB, setUcB] = useState(false);
  const ucBRef = useRef(false);
  ucBRef.current = ucB;
  const [kucuk] = useState(() => kucukEkran());
  const [fare] = useState(() => fareVar());

  /* Tuvalin boyu: karolar ve 3B kapsamı buna göre seçilir. */
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

  /* Arka plan yolları — yoksa harita yine çizilir. */
  useEffect(() => {
    let iptal = false;
    (async () => {
      const saklanan = await onbellektenOku<YolAgi>(ONBELLEK_YOL);
      if (!iptal && saklanan) setYolAgi(saklanan);
      try {
        const yeni = await yollarUcu(null);
        if (iptal || !yeni) return;
        setYolAgi(yeni);
        void onbellegeYaz(ONBELLEK_YOL, yeni);
      } catch {
        /* yollar olmadan da okunur */
      }
    })();
    return () => {
      iptal = true;
    };
  }, []);

  /* Görünümü veriye sığdır. */
  const sigdir = useCallback(
    (hedef: HaritaNoktasi[]) => {
      const kutuSinir = govdeSinirlari(hedef.map((n) => n.konum));
      const kap = sarmalRef.current;
      if (!kutuSinir || !kap || !kap.clientWidth || !kap.clientHeight) return;
      // 3B açıksa kamera eğik kalır; yalnız yer ve yakınlık değişir.
      const egim = ucBRef.current ? UC_B_EGIM : 0;
      const aci = ucBRef.current ? -20 : 0;
      try {
        const gorus = new WebMercatorViewport({ width: kap.clientWidth, height: kap.clientHeight });
        const s = gorus.fitBounds(kutuSinir, { padding: 48 });
        setGorunum({
          longitude: s.longitude,
          latitude: s.latitude,
          zoom: Math.min(s.zoom, 16),
          pitch: egim,
          bearing: aci,
        });
      } catch {
        setGorunum({
          longitude: kutuSinir[0][0],
          latitude: kutuSinir[0][1],
          zoom: 11,
          pitch: egim,
          bearing: aci,
        });
      }
    },
    [],
  );

  useEffect(() => {
    if (!noktalar.length) return;
    const anahtar = sigdirmaAnahtari || String(noktalar.length);
    if (sigdirilan.current === anahtar) return;
    sigdirilan.current = anahtar;
    sigdir(noktalar);
  }, [noktalar, sigdir, sigdirmaAnahtari]);

  /* Elle odaklama ("seçime yakınlaş" gibi düğmeler). */
  useEffect(() => {
    if (!odakAnahtari || odaklanan.current === odakAnahtari) return;
    odaklanan.current = odakAnahtari;
    if (odakNoktalari?.length) sigdir(odakNoktalari);
  }, [odakAnahtari, odakNoktalari, sigdir]);

  /* 3B aç/kapat: kamera yumuşakça eğilir ya da tepeye döner. */
  const ucBDegistir = useCallback(
    (acik: boolean) => {
      setUcB(acik);
      setGorunum((g) =>
        g ? (acik ? ucBGorunumu(g, kucuk ? 15 : 14.5, secili?.konum ?? null) : duzGorunum(g)) : g,
      );
    },
    [kucuk, secili],
  );

  /* Kutu çizimi eğik haritada kafa karıştırır: çizim başlarken harita düzleşir. */
  useEffect(() => {
    if (secimKipi && ucBRef.current) ucBDegistir(false);
  }, [secimKipi, ucBDegistir]);

  const yolCizgileri = useMemo(() => {
    if (!yolAgi) return [];
    const cikti: Array<{ yol: Konum[] }> = [];
    for (const ozellik of yolAgi.features) {
      const g = ozellik.geometry;
      if (g.type === 'LineString') cikti.push({ yol: g.coordinates as Konum[] });
      else if (g.type === 'MultiLineString')
        g.coordinates.forEach((c) => cikti.push({ yol: c as Konum[] }));
    }
    return cikti;
  }, [yolAgi]);

  /**
   * Yalnız görünen alanı çiz. Şehir geneli 19.706 nokta; dizüstünde de,
   * yöneticinin tabletinde de her karede hepsini çizmenin bir faydası yok
   * (uzakta noktalar üst üste biniyor). Yakınlaştıkça hepsi geri geliyor.
   */
  const gorunenKutu = useMemo<Kutu | null>(() => {
    if (!gorunum || !sarmalRef.current) return null;
    const { clientWidth, clientHeight } = sarmalRef.current;
    if (!clientWidth || !clientHeight) return null;
    try {
      const g = new WebMercatorViewport({ ...gorunum, width: clientWidth, height: clientHeight });
      return kutuyuGenislet(g.getBounds() as Kutu);
    } catch {
      return null;
    }
  }, [gorunum]);

  const cizilecekNoktalar = useMemo(
    () => ayikla(noktalar, { kutu: gorunenKutu, konum: (n) => n.konum, enFazla: 25000 }),
    [noktalar, gorunenKutu],
  );

  const cizilecekYollar = useMemo(
    () => cizgileriAyikla(yolCizgileri, gorunenKutu, 4000),
    [yolCizgileri, gorunenKutu],
  );

  /* ---------------- Altlık ve 3B ---------------- */

  const altlik = useAltlik(altlikKipi, gorunum, boyut.genislik, boyut.yukseklik);
  const ikiz = useIkiz(ucB, noktalar, null, gorunum, boyut.genislik, boyut.yukseklik, kucuk);

  const boyama = useMemo(
    () =>
      ikiz.veri ? boya(mercek, ikiz.veri, ikiz.ogeler, DURUM_RENKLERI, DURUM_ADI, vurgulanan) : null,
    [mercek, ikiz.veri, ikiz.ogeler, vurgulanan],
  );

  const seciliIndis = useMemo(() => {
    if (!secili || !ikiz.veri) return -1;
    return ikiz.ogeler.findIndex((o) => o.serial === secili.serial);
  }, [secili, ikiz.veri, ikiz.ogeler]);

  const binaTiklandi = useCallback(
    (indis: number) => noktaSecildi?.(ikiz.ogeler[indis] ?? null),
    [noktaSecildi, ikiz.ogeler],
  );

  const katmanlar = useMemo(() => {
    const liste: unknown[] = [...altlik.katmanlar];

    // Sade yollar karoların ALTINDA değil, karo yoksa YERİNE: altlık görünen
    // alanı tam örtünce çizilmez (hem boşuna iş, hem çift yol görüntüsü).
    if (cizilecekYollar.length && !altlik.ortulu) {
      liste.push(
        new PathLayer({
          id: 'yon-yollar',
          data: cizilecekYollar,
          getPath: (d: { yol: Konum[] }) => d.yol,
          getColor: [208, 216, 226],
          getWidth: 2,
          widthUnits: 'pixels',
          widthMinPixels: 1,
          pickable: false,
          parameters: USTTE,
        }),
      );
    }

    if (ucB && ikiz.veri && boyama) {
      liste.push(
        ikizKatmani({
          id: 'yon-ikiz',
          veri: ikiz.veri,
          boyama,
          boyamaAnahtari: boyama,
          seciliIndis,
          tiklandi: noktaSecildi ? binaTiklandi : undefined,
        }),
      );
    } else {
      liste.push(
        new ScatterplotLayer({
          id: 'yon-binalar',
          data: cizilecekNoktalar,
          getPosition: (d: HaritaNoktasi) => d.konum,
          getFillColor: (d: HaritaNoktasi) => DURUM_RENKLERI[d.durum] ?? DURUM_RENKLERI.bekliyor,
          getRadius: (d: HaritaNoktasi) => 8 + Math.min(16, Math.sqrt(Math.max(0, d.firsat)) * 1.8),
          radiusUnits: 'meters',
          radiusMinPixels: 2.6,
          radiusMaxPixels: 12,
          // Sokak/uydu altlığında gri nokta zeminde kaybolmasın: ince beyaz çerçeve
          // (satışçı haritasındakiyle aynı). Koyu çerçeve şehir ölçeğinde 2-3 px'lik
          // noktaları siyah lekeye çeviriyordu.
          stroked: altlikKipi !== 'sade',
          getLineColor: [255, 255, 255, 230],
          lineWidthMinPixels: 1,
          pickable: Boolean(noktaSecildi) || fare,
          onClick: (bilgi: PickingInfo) => {
            if (!noktaSecildi) return false;
            noktaSecildi((bilgi.object as HaritaNoktasi | undefined) ?? null);
            return true;
          },
          updateTriggers: { getFillColor: cizilecekNoktalar },
        }),
      );
    }

    if (rota && rota.length > 1) {
      liste.push(
        new PathLayer({
          id: 'yon-rota',
          data: [{ yol: rota }],
          getPath: (d: { yol: Konum[] }) => d.yol,
          getColor: [11, 99, 229, 150],
          getWidth: 4,
          widthUnits: 'pixels',
          widthMinPixels: 2,
          capRounded: true,
          jointRounded: true,
          pickable: false,
          parameters: USTTE,
        }),
      );
    }

    // 3B'de seçim binanın kendisini boyar; noktalar yalnız düz haritada.
    if (!ucB && vurgulanan && vurgulanan.size) {
      const isaretli = noktalar.filter((n) => vurgulanan.has(n.serial));
      liste.push(
        new ScatterplotLayer({
          id: 'yon-secim',
          data: isaretli,
          getPosition: (d: HaritaNoktasi) => d.konum,
          getFillColor: [11, 99, 229],
          getLineColor: [255, 255, 255],
          lineWidthMinPixels: 1.5,
          getRadius: 16,
          radiusUnits: 'meters',
          radiusMinPixels: 5,
          radiusMaxPixels: 16,
          stroked: true,
          pickable: false,
          updateTriggers: { getPosition: isaretli },
        }),
      );
    }

    if (secili && (!ucB || seciliIndis < 0)) {
      liste.push(
        new ScatterplotLayer({
          id: 'yon-odak',
          data: [secili],
          getPosition: (d: HaritaNoktasi) => d.konum,
          getFillColor: [255, 201, 0],
          getLineColor: [16, 24, 40],
          lineWidthMinPixels: 2,
          getRadius: 20,
          radiusUnits: 'meters',
          radiusMinPixels: 7,
          radiusMaxPixels: 20,
          stroked: true,
          pickable: false,
          parameters: USTTE,
        }),
      );
    }

    return liste;
  }, [
    altlik.katmanlar,
    altlik.ortulu,
    altlikKipi,
    cizilecekNoktalar,
    noktalar,
    cizilecekYollar,
    vurgulanan,
    rota,
    secili,
    noktaSecildi,
    ucB,
    ikiz.veri,
    boyama,
    seciliIndis,
    binaTiklandi,
    fare,
  ]);

  /* Farenin üstündeki bina: adı + Location Id (+ merceğin söylediği). */
  const ipucuGetir = useCallback(
    (bilgi: PickingInfo) => {
      if (!fare || kutu || bilgi.index < 0 || !bilgi.layer) return null;
      if (bilgi.layer.id === 'yon-ikiz' && ikiz.veri) {
        const n = ikiz.ogeler[bilgi.index];
        if (!n) return null;
        return ipucu(n.ad || n.serial, n.loc, [
          mercekSatiri(mercek, ikiz.veri, bilgi.index, n, DURUM_ADI[n.durum] ?? n.durum),
        ]);
      }
      if (bilgi.layer.id === 'yon-binalar' && bilgi.object) {
        const n = bilgi.object as HaritaNoktasi;
        return ipucu(n.ad || n.serial, n.loc, [
          `${DURUM_ADI[n.durum] ?? n.durum}` +
            (n.firsat ? ` · ${n.firsat.toLocaleString('tr-TR')} boş kapı` : ''),
        ]);
      }
      return null;
    },
    [fare, kutu, ikiz.veri, ikiz.ogeler, mercek],
  );

  /* ---------------- Kutu ile seçim ---------------- */

  const yerelKonum = (olay: React.PointerEvent) => {
    const kap = sarmalRef.current;
    if (!kap) return { x: 0, y: 0 };
    const k = kap.getBoundingClientRect();
    return { x: olay.clientX - k.left, y: olay.clientY - k.top };
  };

  const kutuBasladi = (olay: React.PointerEvent) => {
    if (!secimKipi) return;
    const { x, y } = yerelKonum(olay);
    (olay.target as HTMLElement).setPointerCapture?.(olay.pointerId);
    setKutu({ x1: x, y1: y, x2: x, y2: y });
  };

  const kutuSuruklendi = (olay: React.PointerEvent) => {
    if (!secimKipi || !kutu) return;
    const { x, y } = yerelKonum(olay);
    setKutu((o) => (o ? { ...o, x2: x, y2: y } : o));
  };

  const kutuBitti = () => {
    if (!secimKipi || !kutu || !gorunum || !sarmalRef.current) {
      setKutu(null);
      return;
    }
    const { clientWidth, clientHeight } = sarmalRef.current;
    const genislik = Math.abs(kutu.x2 - kutu.x1);
    const yukseklikPx = Math.abs(kutu.y2 - kutu.y1);
    setKutu(null);
    if (genislik < 8 || yukseklikPx < 8) return; // kazara tıklama

    try {
      // Harita döndürülmüş/eğikse ekrandaki dikdörtgen yerde yamuktur:
      // dört köşe ayrı çevrilir, seçim o dörtgenin içidir.
      const cokgen = ekrandanCokgen(
        gorunum,
        clientWidth,
        clientHeight,
        kutu.x1,
        kutu.y1,
        kutu.x2,
        kutu.y2,
      );
      const lonlar = cokgen.map((p) => p[0]);
      const latlar = cokgen.map((p) => p[1]);
      const secilen = noktalar
        .filter((n) => cokgenIcinde(cokgen, n.konum[0], n.konum[1]))
        .map((n) => n.serial);
      secimBitti?.(secilen, [
        Math.min(...latlar),
        Math.min(...lonlar),
        Math.max(...latlar),
        Math.max(...lonlar),
      ]);
    } catch {
      /* görünüm hesaplanamadıysa seçim yapılmaz */
    }
  };

  const sayilar = useMemo(() => {
    const t = new Map<BinaDurumu, number>();
    for (const n of noktalar) t.set(n.durum, (t.get(n.durum) ?? 0) + 1);
    return t;
  }, [noktalar]);

  const haritaVar = webglVar && Boolean(gorunum) && noktalar.length > 0;
  const atifMetni =
    altlikKipi === 'sade' ? 'Yollar © OpenStreetMap katkıcıları' : altlik.atif;

  return (
    <div
      className={`yon-harita${secimKipi ? ' secim-kipi' : ''}${haritaVar ? ' hr-atifli' : ''}`}
      ref={sarmalRef}
      style={{ height: yukseklik }}
    >
      {!webglVar ? (
        <div className="yon-harita-bos">
          Harita bu tarayıcıda açılamıyor (WebGL kapalı). Tablolar çalışmaya devam ediyor.
        </div>
      ) : gorunum && noktalar.length ? (
        <DeckGL
          viewState={gorunum}
          onViewStateChange={({ viewState }) => {
            ipucuYerlestir(ipucuRef.current, 0, 0, null);
            setGorunum(viewState as MapViewState);
          }}
          controller={secimKipi ? false : { dragRotate: ucB, touchRotate: ucB }}
          layers={katmanlar as never[]}
          style={{ position: 'absolute', inset: '0' }}
          onHover={(bilgi: PickingInfo) =>
            ipucuYerlestir(ipucuRef.current, bilgi.x, bilgi.y, ipucuGetir(bilgi))
          }
          onClick={(bilgi: PickingInfo) => {
            if (bilgi.index < 0) noktaSecildi?.(null);
          }}
        />
      ) : (
        <div className="yon-harita-bos">
          {noktalar.length ? 'Harita hazırlanıyor…' : 'Bu seçimde gösterilecek bina yok.'}
        </div>
      )}

      {secimKipi ? (
        <div
          className="yon-harita-ortu"
          onPointerDown={kutuBasladi}
          onPointerMove={kutuSuruklendi}
          onPointerUp={kutuBitti}
          onPointerCancel={() => setKutu(null)}
          role="application"
          aria-label="Haritada dikdörtgen çizerek bina seçin"
        >
          {kutu ? (
            <div
              className="yon-secim-kutu"
              style={{
                left: Math.min(kutu.x1, kutu.x2),
                top: Math.min(kutu.y1, kutu.y2),
                width: Math.abs(kutu.x2 - kutu.x1),
                height: Math.abs(kutu.y2 - kutu.y1),
              }}
            />
          ) : null}
        </div>
      ) : null}

      {haritaVar ? (
        <div className="hr-panel">
          <div className="hr-satir">
            <AltlikSecici kip={altlikKipi} degisti={setAltlikKipi} />
            <UcBDugmesi
              acik={ucB}
              degisti={ucBDegistir}
              hazirlaniyor={ikiz.durum === 'yukleniyor'}
              devreDisi={secimKipi}
            />
          </div>
        </div>
      ) : null}

      {araclar ? <div className="yon-harita-arac">{araclar}</div> : null}

      {haritaVar && ucB && boyama && ikiz.veri ? (
        <div className="hr-alt-sol" style={kart ? { maxWidth: 'calc(100% - 336px)' } : undefined}>
          {/* Kart açıkken lejant yalnız mercek seçicisine iner; kartın altında kalmaz. */}
          <MercekLejanti
            mercek={mercek}
            boyama={boyama}
            temsili={ikiz.veri.temsili}
            secici={<MercekSecici mercek={mercek} degisti={setMercek} />}
            yalnizSecici={Boolean(kart)}
          />
        </div>
      ) : lejant && noktalar.length ? (
        <div className="yon-lejant">
          {LEJANT.filter((l) => (sayilar.get(l.durum) ?? 0) > 0).map((l) => (
            <span key={l.durum} className="oge">
              <span
                className="nokta"
                style={{ background: `rgb(${DURUM_RENKLERI[l.durum].join(',')})` }}
              />
              {l.etiket}
              <b style={{ fontVariantNumeric: 'tabular-nums' }}>
                {(sayilar.get(l.durum) ?? 0).toLocaleString('tr-TR')}
              </b>
            </span>
          ))}
        </div>
      ) : null}

      {haritaVar ? <Atif metin={atifMetni} durum={altlik.durum} ortulu={altlik.ortulu} /> : null}

      <div className="hr-ipucu" ref={ipucuRef} role="tooltip" />

      {kart}
    </div>
  );
}

/* ------------------------------ Yardımcılar ------------------------------ */

function webglDestekli(): boolean {
  try {
    const tuval = document.createElement('canvas');
    return Boolean(tuval.getContext('webgl2') || tuval.getContext('webgl'));
  } catch {
    return false;
  }
}
