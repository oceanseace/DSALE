/**
 * Harita — satışçının kendi bölgesi.
 *
 * Yeşil = gidildi, gri = bekliyor, sarı = tekrar gel, kırmızı = altyapı sorunu.
 * Bugünün rotası mavi çizgiyle bağlanır.
 *
 * Altlık: "Harita" (sokak karoları, Google Maps gibi), "Uydu" ya da "Sade"
 * (yalnız sunucudaki OSM yolları). Karo yalnız internet varken indirilir;
 * gelmezse harita sessizce sade yollara düşer — çevrimdışı da boş kalmaz.
 * "3B" binaları gerçek taban çizgisi ve kat sayısıyla yükseltir.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { PathLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';
import { WebMercatorViewport, type MapViewState, type PickingInfo } from '@deck.gl/core';
import { haritaVerisi, yollar as yollarUcu } from '../api/uclar';
import { ALTLIK_KIPLERI, useAltlik, type AltlikKipi } from '../harita/altlik';
import { boya, ikizKatmani, MERCEKLER, useIkiz, type Mercek } from '../harita/ikiz';
import { duzGorunum, kucukEkran, ucBGorunumu, UC_B_EGIM } from '../harita/kamera';
import { useKaliciSecim } from '../harita/tercih';
import { AltlikSecici, Atif, MercekLejanti, MercekSecici, UcBDugmesi } from '../harita/HaritaDenetim';
import { onbellegeYaz, onbellektenOku } from '../depo/db';
import { useBugun } from '../depo/bugun';
import { useOturum } from '../depo/oturum';
import { Ileri, Kapat, Pusula } from '../ortak/Ikon';
import { Sayfa, SayfaGovde, Ust } from '../ortak/Sayfa';
import { DURUM_ETIKETLERI, sayi } from '../ortak/bicim';
import {
  ayikla,
  cizgileriAyikla,
  govdeSinirlari,
  kutuyuGenislet,
  sinirlar,
  type Kutu,
} from '../ortak/ayikla';
import { git } from '../yol/rota';
import type { BinaDurumu, HaritaVerisi, YolAgi } from '../api/tipler';

type Renk = [number, number, number];
type Konum = [number, number];
interface Cizgi {
  yol: Konum[];
}

const RENKLER: Record<BinaDurumu, Renk> = {
  bekliyor: [168, 178, 191],
  planli: [11, 99, 229],
  ziyaret_edildi: [15, 138, 74],
  tekrar_gel: [224, 138, 30],
  girilemedi: [193, 120, 26],
  altyapi_sorunu: [192, 42, 42],
};

const LEJANT: Array<{ durum: BinaDurumu; etiket: string }> = [
  { durum: 'ziyaret_edildi', etiket: 'Gidildi' },
  { durum: 'bekliyor', etiket: 'Bekliyor' },
  { durum: 'tekrar_gel', etiket: 'Tekrar gel' },
  { durum: 'planli', etiket: 'Bugün' },
];

interface Nokta {
  serial: string;
  ad: string;
  /** Location Id — sunucu `/api/harita` yanıtında `loc[]` olarak gönderir. */
  loc?: string;
  konum: Konum;
  durum: BinaDurumu;
  firsat: number;
}

const ONBELLEK_HARITA = 'harita.veri';
const ONBELLEK_YOL = 'harita.yollar';

/** Derinliğe bakmadan en üste çizilen katmanlar (3B'de binaların arkasında kalmasın). */
const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;

export function Harita() {
  const { kullanici } = useOturum();
  const { gorev } = useBugun();
  const [veri, setVeri] = useState<HaritaVerisi | null>(null);
  const [yolAgi, setYolAgi] = useState<YolAgi | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [secili, setSecili] = useState<Nokta | null>(null);
  const [gorunum, setGorunum] = useState<MapViewState | null>(null);
  const [webglVar] = useState(() => webglDestekli());
  const [kapsam, setKapsam] = useState<'rota' | 'bolge'>('rota');
  /** Satışçının kendi konumu — "buradan nasıl giderim" sorusunun yarısı. */
  const [benimKonum, setBenimKonum] = useState<Konum | null>(null);
  const sarmalRef = useRef<HTMLDivElement | null>(null);
  const [boyut, setBoyut] = useState({ genislik: 0, yukseklik: 0 });

  /* Altlık ve mercek bu telefonda hatırlanır; 3B her açılışta düz başlar. */
  const [altlikKipi, setAltlikKipi] = useKaliciSecim<AltlikKipi>('altlik', 'harita', ALTLIK_KIPLERI);
  const [mercek, setMercek] = useKaliciSecim<Mercek>('mercek', 'durum', MERCEKLER);
  const [ucB, setUcB] = useState(false);
  const ucBRef = useRef(false);
  ucBRef.current = ucB;
  const [kucuk] = useState(() => kucukEkran());

  const bolge = kullanici?.bolge ?? null;

  /* Tuvalin boyu: karolar buna göre seçilir. */
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

  /* Veri: önce telefondaki kopya, sonra sunucu. */
  useEffect(() => {
    let iptal = false;
    (async () => {
      const saklananVeri = await onbellektenOku<HaritaVerisi>(ONBELLEK_HARITA);
      if (!iptal && saklananVeri) {
        setVeri(saklananVeri);
        setYukleniyor(false);
      }
      const saklananYol = await onbellektenOku<YolAgi>(ONBELLEK_YOL);
      if (!iptal && saklananYol) setYolAgi(saklananYol);

      try {
        const yeni = await haritaVerisi(bolge);
        if (iptal) return;
        setVeri(yeni);
        void onbellegeYaz(ONBELLEK_HARITA, yeni);
      } catch {
        /* çevrimdışı: elimizdeki kopya kalır */
      } finally {
        if (!iptal) setYukleniyor(false);
      }

      try {
        const yeniYol = await yollarUcu(bolge);
        if (iptal || !yeniYol) return;
        setYolAgi(yeniYol);
        void onbellegeYaz(ONBELLEK_YOL, yeniYol);
      } catch {
        /* yollar olmadan da harita okunur */
      }
    })();
    return () => {
      iptal = true;
    };
  }, [bolge]);

  const noktalar = useMemo<Nokta[]>(() => {
    if (!veri) return [];
    const uzunluk = Math.min(veri.serial.length, veri.lat.length, veri.lon.length);
    const liste: Nokta[] = new Array(uzunluk);
    const loc = (veri as HaritaVerisi & { loc?: string[] }).loc;
    for (let i = 0; i < uzunluk; i++) {
      liste[i] = {
        serial: veri.serial[i],
        ad: veri.ad?.[i] ?? veri.serial[i],
        loc: loc?.[i] || undefined,
        konum: [veri.lon[i], veri.lat[i]],
        durum: veri.durum[i] ?? 'bekliyor',
        firsat: veri.firsat?.[i] ?? 0,
      };
    }
    return liste;
  }, [veri]);

  /* Bugünün rotası: sıraya göre bağlanmış çizgi. */
  const rotaYolu = useMemo<Cizgi[] | null>(() => {
    const binalar = gorev?.binalar ?? [];
    if (binalar.length < 2) return null;
    const sirali = [...binalar].sort((a, b) => a.sira - b.sira);
    return [{ yol: sirali.map((b) => [b.lon, b.lat] as Konum) }];
  }, [gorev]);

  const rotaNoktalari = useMemo(() => {
    const binalar = gorev?.binalar ?? [];
    // Sıradaki durak = bekleyenler içinde en küçük sıra numarası.
    const siradaki = binalar
      .filter((b) => b.gorev_durum === 'bekliyor')
      .reduce<number | null>((en, b) => (en == null || b.sira < en ? b.sira : en), null);
    return binalar.map((b) => ({
      konum: [b.lon, b.lat] as [number, number],
      bitti: b.gorev_durum !== 'bekliyor',
      sira: b.sira,
      siradaki: b.sira === siradaki,
    }));
  }, [gorev]);

  /**
   * Durak numaraları için ETİKETLER — noktaların kendisinden ayrı hesaplanır.
   *
   * Aynı sitenin blokları neredeyse aynı koordinatta duruyor; her birine ayrı
   * numara yazılınca rakamlar üst üste binip okunaksız bir leke oluyordu.
   * Ekranda birbirine değecek kadar yakın duraklar tek etikette toplanır:
   * "12-16". Yakınlaştıkça öbekler kendiliğinden çözülür.
   */
  const rotaEtiketleri = useMemo(() => {
    if (!rotaNoktalari.length) return [];
    /*
     * Eşik EKRANDA ölçülür, haritada değil: uzaklaşınca kilometrelerce ayrı
     * duraklar da aynı piksele düşüyor. Yakınlaşınca öbekler kendiliğinden
     * çözülür ve numaralar tek tek görünür.
     */
    const zoom = gorunum?.zoom ?? 12;
    const enlem = ((gorunum?.latitude ?? 40) * Math.PI) / 180;
    const PIKSEL = 58; // en geniş etiket yuvarlağı ~48 px; üstüne pay bırakılır
    const esikLon = (PIKSEL * 360) / (512 * Math.pow(2, zoom));
    const esikLat = Math.max(esikLon * Math.cos(enlem), 1e-9);

    /*
     * Izgara kovalama YETMİYOR: eşikten yakın iki nokta komşu hücrelere
     * düşebiliyor ve öbekler yine üst üste biniyordu. Onun yerine sırayla
     * gezip her noktayı yakınındaki öbeğe katıyoruz (25 durak, maliyeti yok).
     */
    const obekler: Array<{
      uyeler: typeof rotaNoktalari;
      lon: number;
      lat: number;
    }> = [];
    for (const n of rotaNoktalari) {
      const yakin = obekler.find(
        (o) => Math.abs(n.konum[0] - o.lon) < esikLon && Math.abs(n.konum[1] - o.lat) < esikLat,
      );
      if (yakin) {
        yakin.uyeler.push(n);
        // Merkez ortalamayla kayar: öbek büyüdükçe etiket ortasında durur.
        yakin.lon = yakin.uyeler.reduce((t, u) => t + u.konum[0], 0) / yakin.uyeler.length;
        yakin.lat = yakin.uyeler.reduce((t, u) => t + u.konum[1], 0) / yakin.uyeler.length;
      } else {
        obekler.push({ uyeler: [n], lon: n.konum[0], lat: n.konum[1] });
      }
    }

    return obekler.map(({ uyeler }) => {
      const siralar = uyeler.map((u) => u.sira).sort((a, b) => a - b);
      const enKucuk = siralar[0];
      const enBuyuk = siralar[siralar.length - 1];
      return {
        // Etiket öbeğin ortasına konur, ilk üyenin üstüne değil.
        konum: [
          uyeler.reduce((t, u) => t + u.konum[0], 0) / uyeler.length,
          uyeler.reduce((t, u) => t + u.konum[1], 0) / uyeler.length,
        ] as Konum,
        /*
         * Peş peşe duraklar "7-8" diye okunur. Ama uzaklaşınca bir öbeğe
         * birbiriyle ilgisiz duraklar da düşebiliyor; orada "7-19" yalan olur
         * (aradakilerin hepsi orada değil), onun yerine "7 +2" yazılır.
         */
        yazi:
          siralar.length === 1
            ? String(enKucuk)
            : enBuyuk - enKucuk === siralar.length - 1
              ? `${enKucuk}-${enBuyuk}`
              : `${enKucuk} +${siralar.length - 1}`,
        siradaki: uyeler.some((u) => u.siradaki),
      };
    });
  }, [rotaNoktalari, gorunum?.zoom, gorunum?.latitude]);

  const yolCizgileri = useMemo<Cizgi[]>(() => {
    if (!yolAgi) return [];
    const cikti: Cizgi[] = [];
    for (const ozellik of yolAgi.features) {
      const g = ozellik.geometry;
      if (g.type === 'LineString') cikti.push({ yol: g.coordinates as Konum[] });
      else if (g.type === 'MultiLineString')
        g.coordinates.forEach((c) => cikti.push({ yol: c as Konum[] }));
    }
    return cikti;
  }, [yolAgi]);

  const rotaVar = rotaNoktalari.length >= 2;

  /**
   * Görünümü seçilen kapsama sığdır.
   *
   * Varsayılan "Bugünün rotası"dır: satışçı haritayı açtığında bugün gideceği
   * yerleri görmek ister; tüm bölgeye bakınca rota tek bir noktaya dönüşür.
   */
  const sigdir = useCallback(
    (hedef: 'rota' | 'bolge') => {
      if (!sarmalRef.current) return;
      const rotaKipi = hedef === 'rota' && rotaVar;
      const konumlar = rotaKipi ? rotaNoktalari.map((r) => r.konum) : noktalar.map((n) => n.konum);
      /*
       * Rotada 25 durak var, her biri önemli: tam kutu kullanılır. Bölgede ise
       * birkaç uzak bina bütün haritayı uzaklaştırıp yoğun kısmı avuç içi bir
       * lekeye çeviriyordu; orada %2–%98 gövdesi alınır.
       */
      const kutu = rotaKipi ? sinirlar(konumlar) : govdeSinirlari(konumlar);
      if (!kutu) return;
      const { clientWidth, clientHeight } = sarmalRef.current;
      if (!clientWidth || !clientHeight) return;
      // 3B açıksa kamera eğik kalır; yalnız yer ve yakınlık değişir.
      const egim = ucBRef.current ? UC_B_EGIM : 0;
      const aci = ucBRef.current ? -20 : 0;
      try {
        const gorus = new WebMercatorViewport({
          width: clientWidth,
          height: clientHeight,
        });
        const sigdirilmis = gorus.fitBounds(kutu, { padding: 56 });
        setGorunum({
          longitude: sigdirilmis.longitude,
          latitude: sigdirilmis.latitude,
          zoom: Math.min(sigdirilmis.zoom, hedef === 'rota' ? 16.5 : 15),
          pitch: egim,
          bearing: aci,
        });
      } catch {
        setGorunum({
          longitude: kutu[0][0],
          latitude: kutu[0][1],
          zoom: 12,
          pitch: egim,
          bearing: aci,
        });
      }
    },
    [noktalar, rotaNoktalari, rotaVar],
  );

  /* İlk açılış: rota varsa rotaya, yoksa bölgeye sığdır. */
  useEffect(() => {
    if (gorunum || !noktalar.length) return;
    const baslangic = rotaVar ? 'rota' : 'bolge';
    setKapsam(baslangic);
    sigdir(baslangic);
  }, [noktalar, gorunum, rotaVar, sigdir]);

  const kapsamDegistir = useCallback(
    (hedef: 'rota' | 'bolge') => {
      setKapsam(hedef);
      setSecili(null);
      sigdir(hedef);
    },
    [sigdir],
  );

  /**
   * Konum sürekli izlenir: haritada mavi bir nokta olarak durur.
   * "Nereye gideceğim" sorusunun cevabı ancak "buradayım" bilindiğinde işe yarar.
   */
  useEffect(() => {
    if (!('geolocation' in navigator)) return undefined;
    const izleme = navigator.geolocation.watchPosition(
      (k) => setBenimKonum([k.coords.longitude, k.coords.latitude]),
      () => undefined,
      { enableHighAccuracy: true, maximumAge: 15000, timeout: 20000 },
    );
    return () => navigator.geolocation.clearWatch(izleme);
  }, []);

  const konumaGit = useCallback(() => {
    if (!('geolocation' in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      (k) => {
        setBenimKonum([k.coords.longitude, k.coords.latitude]);
        setGorunum((o) => ({
          ...(o ?? { pitch: 0, bearing: 0 }),
          longitude: k.coords.longitude,
          latitude: k.coords.latitude,
          zoom: 16,
        }));
      },
      () => undefined,
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }, []);

  /**
   * Telefonu yormamak için yalnız EKRANDA GÖRÜNENİ çiziyoruz.
   *
   * Bölgede ~2.400, şehir genelinde 19.706 bina var; uzaklaşınca noktalar
   * üst üste bindiği için hepsini çizmek ekrana bilgi katmaz, sadece kareyi
   * düşürür. Yakınlaştıkça bütçe rahatlar ve bütün binalar geri gelir.
   */
  const gorunenKutu = useMemo<Kutu | null>(() => {
    if (!gorunum || !sarmalRef.current) return null;
    const { clientWidth, clientHeight } = sarmalRef.current;
    if (!clientWidth || !clientHeight) return null;
    try {
      const g = new WebMercatorViewport({
        ...gorunum,
        width: clientWidth,
        height: clientHeight,
      });
      return kutuyuGenislet(g.getBounds() as Kutu);
    } catch {
      return null;
    }
  }, [gorunum]);

  const cizilecekNoktalar = useMemo(
    () =>
      ayikla(noktalar, {
        kutu: gorunenKutu,
        konum: (n) => n.konum,
        enFazla: 12000,
      }),
    [noktalar, gorunenKutu],
  );

  const cizilecekYollar = useMemo(
    () => cizgileriAyikla(yolCizgileri, gorunenKutu, 3000),
    [yolCizgileri, gorunenKutu],
  );

  /* ---------------- Altlık ve 3B ---------------- */

  const altlik = useAltlik(altlikKipi, gorunum, boyut.genislik, boyut.yukseklik);
  const ikiz = useIkiz(ucB, noktalar, bolge, gorunum, boyut.genislik, boyut.yukseklik, kucuk);

  const boyama = useMemo(
    () => (ikiz.veri ? boya(mercek, ikiz.veri, ikiz.ogeler, RENKLER, DURUM_ETIKETLERI) : null),
    [mercek, ikiz.veri, ikiz.ogeler],
  );

  const seciliIndis = useMemo(() => {
    if (!secili || !ikiz.veri) return -1;
    return ikiz.ogeler.findIndex((o) => o.serial === secili.serial);
  }, [secili, ikiz.veri, ikiz.ogeler]);

  const binaTiklandi = useCallback(
    (indis: number) => setSecili(ikiz.ogeler[indis] ?? null),
    [ikiz.ogeler],
  );

  /*
   * 3B aç/kapat: kamera yumuşakça eğilir ya da tepeye döner. Açılırken seçili
   * binaya, yoksa (rota görünümünde) SIRADAKİ durağa yaklaşılır: satışçının
   * 3B'de ilk görmek istediği, gideceği binanın çevresidir.
   */
  const ucBDegistir = useCallback(
    (acik: boolean) => {
      setUcB(acik);
      const siradaki = kapsam === 'rota' ? rotaNoktalari.find((r) => r.siradaki)?.konum : null;
      setGorunum((g) =>
        g ? (acik ? ucBGorunumu(g, 15.5, secili?.konum ?? siradaki ?? null) : duzGorunum(g)) : g,
      );
    },
    [secili, kapsam, rotaNoktalari],
  );

  const katmanlar = useMemo(() => {
    const liste: unknown[] = [...altlik.katmanlar];

    // Sade yollar: altlık görünen alanı tam örtmüyorsa (yükleniyor, çevrimdışı,
    // "Sade" seçili) çizilir. Karo gelince altında kalmak yerine hiç çizilmez.
    if (cizilecekYollar.length && !altlik.ortulu) {
      liste.push(
        new PathLayer({
          id: 'yollar',
          data: cizilecekYollar,
          getPath: (d: Cizgi) => d.yol,
          getColor: [205, 213, 223],
          getWidth: 3,
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
          id: 'ikiz',
          veri: ikiz.veri,
          boyama,
          boyamaAnahtari: boyama,
          seciliIndis,
          tiklandi: binaTiklandi,
        }),
      );
    }

    if (rotaYolu) {
      liste.push(
        new PathLayer({
          id: 'rota',
          data: rotaYolu,
          getPath: (d: Cizgi) => d.yol,
          getColor: [11, 99, 229, 140],
          getWidth: 5,
          widthUnits: 'pixels',
          widthMinPixels: 3,
          capRounded: true,
          jointRounded: true,
          pickable: false,
          parameters: USTTE,
        }),
      );
    }

    // 3B'de binaların kendisi çizilir; noktalar yalnız düz haritada.
    if (!ucB || !ikiz.veri) {
      liste.push(
        new ScatterplotLayer({
          id: 'binalar',
          data: cizilecekNoktalar,
          getPosition: (d: Nokta) => d.konum,
          getFillColor: (d: Nokta) => RENKLER[d.durum] ?? RENKLER.bekliyor,
          getRadius: (d: Nokta) => 8 + Math.min(18, Math.sqrt(Math.max(0, d.firsat)) * 2),
          radiusUnits: 'meters',
          radiusMinPixels: 4.5,
          radiusMaxPixels: 16,
          stroked: true,
          getLineColor: [255, 255, 255, 220],
          lineWidthMinPixels: 1,
          pickable: true,
          onClick: (bilgi: PickingInfo) => {
            setSecili((bilgi.object as Nokta | undefined) ?? null);
            return true;
          },
          updateTriggers: { getFillColor: cizilecekNoktalar },
        }),
      );
    }

    /*
     * "Tüm bölgem" görünümünde durak NUMARASI yazılmaz: o kadar uzaktan 25
     * durak tek öbeğe düşüp "1-25" diye kocaman bir leke oluyor ve tam da
     * görülmek istenen bölgeyi kapatıyor. O ekranın sorusu "nereye gitmedim",
     * "hangi sırayla" değil.
     */
    const numaraCiz = kapsam === 'rota';

    if (rotaNoktalari.length) {
      liste.push(
        new ScatterplotLayer({
          id: 'rota-duraklari',
          data: rotaNoktalari,
          getPosition: (d: { konum: Konum }) => d.konum,
          getFillColor: (d: { bitti: boolean; siradaki: boolean }) =>
            d.bitti
              ? ([15, 138, 74] as Renk)
              : d.siradaki
                ? ([255, 201, 0] as Renk)
                : ([11, 99, 229] as Renk),
          // Sıradaki durak belirgin şekilde daha büyük: gözün ilk gittiği yer o olmalı.
          getRadius: (d: { siradaki: boolean }) => (d.siradaki ? 20 : 13),
          radiusUnits: 'meters',
          radiusMinPixels: 10,
          radiusMaxPixels: 26,
          // 3B'de yere yatık elips değil, kameraya dönük yuvarlak rozet.
          billboard: ucB,
          stroked: true,
          getLineColor: (d: { siradaki: boolean }) =>
            d.siradaki ? ([17, 24, 39] as Renk) : ([255, 255, 255] as Renk),
          lineWidthMinPixels: 2.5,
          pickable: false,
          parameters: USTTE,
          updateTriggers: {
            getFillColor: rotaNoktalari,
            getRadius: rotaNoktalari,
          },
        }),
      );
      // Öbek etiketleri ("12-16") altlarındaki noktadan geniştir; rakam beyaz
      // zeminde kaybolmasın diye altlarına kendi zeminleri çizilir.
      const genisEtiketler = numaraCiz ? rotaEtiketleri.filter((e) => e.yazi.length > 2) : [];
      if (genisEtiketler.length) {
        liste.push(
          new ScatterplotLayer({
            id: 'rota-etiket-zemin',
            data: genisEtiketler,
            getPosition: (d: { konum: Konum }) => d.konum,
            getFillColor: (d: { siradaki: boolean }) =>
              d.siradaki ? ([255, 201, 0] as Renk) : ([11, 99, 229] as Renk),
            getRadius: (d: { yazi: string }) => 4 + d.yazi.length * 4,
            radiusUnits: 'pixels',
            billboard: ucB,
            stroked: true,
            getLineColor: (d: { siradaki: boolean }) =>
              d.siradaki ? ([17, 24, 39] as Renk) : ([255, 255, 255] as Renk),
            lineWidthMinPixels: 2.5,
            pickable: false,
            parameters: USTTE,
            updateTriggers: {
              getFillColor: genisEtiketler,
              getRadius: genisEtiketler,
            },
          }),
        );
      }
      // Durak SIRA NUMARALARI: "önce nereye, sonra nereye" haritadan okunmalı.
      if (numaraCiz) {
        liste.push(
          new TextLayer({
            id: 'rota-numaralari',
            data: rotaEtiketleri,
            getPosition: (d: { konum: Konum }) => d.konum,
            getText: (d: { yazi: string }) => d.yazi,
            getSize: (d: { siradaki: boolean }) => (d.siradaki ? 15 : 12),
            sizeUnits: 'pixels',
            getColor: (d: { siradaki: boolean }) =>
              d.siradaki ? ([17, 24, 39] as Renk) : ([255, 255, 255] as Renk),
            fontWeight: 600,
            getTextAnchor: 'middle',
            getAlignmentBaseline: 'center',
            pickable: false,
            parameters: USTTE,
            updateTriggers: {
              getColor: rotaEtiketleri,
              getSize: rotaEtiketleri,
            },
          }),
        );
      }
    }

    if (benimKonum) {
      liste.push(
        new ScatterplotLayer({
          id: 'benim-konum',
          data: [{ konum: benimKonum }],
          getPosition: (d: { konum: Konum }) => d.konum,
          getFillColor: [11, 99, 229, 60],
          getRadius: 60,
          radiusUnits: 'meters',
          radiusMinPixels: 18,
          radiusMaxPixels: 60,
          pickable: false,
          parameters: USTTE,
        }),
        new ScatterplotLayer({
          id: 'benim-konum-nokta',
          data: [{ konum: benimKonum }],
          getPosition: (d: { konum: Konum }) => d.konum,
          getFillColor: [11, 99, 229, 255],
          getRadius: 9,
          radiusUnits: 'meters',
          radiusMinPixels: 7,
          radiusMaxPixels: 12,
          billboard: ucB,
          stroked: true,
          getLineColor: [255, 255, 255, 255],
          lineWidthMinPixels: 3,
          pickable: false,
          parameters: USTTE,
        }),
      );
    }

    return liste;
  }, [
    cizilecekNoktalar,
    rotaYolu,
    rotaNoktalari,
    cizilecekYollar,
    benimKonum,
    altlik.katmanlar,
    altlik.ortulu,
    ucB,
    ikiz.veri,
    boyama,
    seciliIndis,
    binaTiklandi,
    kapsam,
  ]);

  const dokunulan = useMemo(
    () => noktalar.filter((n) => n.durum !== 'bekliyor' && n.durum !== 'planli').length,
    [noktalar],
  );

  return (
    <Sayfa sabit>
      <Ust
        baslik="Harita"
        altYazi={
          noktalar.length
            ? `${sayi(noktalar.length)} bina · ${sayi(dokunulan)} dokunuldu`
            : (kullanici?.bolge_adi ?? null)
        }
      />
      <SayfaGovde tam>
        {rotaVar ? (
          <div className="segment" role="group" aria-label="Harita kapsamı">
            <button
              className={kapsam === 'rota' ? 'secili' : undefined}
              onClick={() => kapsamDegistir('rota')}
              aria-pressed={kapsam === 'rota'}
            >
              Bugünün rotası
            </button>
            <button
              className={kapsam === 'bolge' ? 'secili' : undefined}
              onClick={() => kapsamDegistir('bolge')}
              aria-pressed={kapsam === 'bolge'}
            >
              Tüm bölgem
            </button>
          </div>
        ) : null}
        <div className="harita-sarmal" ref={sarmalRef}>
          {!webglVar ? (
            <div className="harita-uyari">
              <div>
                <p
                  style={{
                    fontSize: 18,
                    fontWeight: 600,
                    color: 'var(--metin)',
                  }}
                >
                  Harita bu telefonda açılamıyor
                </p>
                <p>Listeyi “Bugün” sekmesinden kullanabilirsin; hiçbir şey kaybolmaz.</p>
              </div>
            </div>
          ) : gorunum && noktalar.length ? (
            <DeckGL
              viewState={gorunum}
              onViewStateChange={({ viewState }) => setGorunum(viewState as MapViewState)}
              controller={{ dragRotate: ucB, touchRotate: ucB }}
              layers={katmanlar as never[]}
              style={{ position: 'absolute', inset: '0' }}
              onClick={(bilgi: PickingInfo) => {
                if (bilgi.index < 0) setSecili(null);
              }}
            />
          ) : (
            <div className="harita-uyari">
              <div>
                <span className="donen" style={{ margin: '0 auto 12px', display: 'block' }} />
                {yukleniyor ? 'Harita hazırlanıyor…' : 'Gösterilecek bina yok.'}
              </div>
            </div>
          )}

          {webglVar && noktalar.length && ucB && boyama && ikiz.veri ? (
            <div className="hr-ust">
              <MercekSecici mercek={mercek} degisti={setMercek} buyuk />
              <MercekLejanti mercek={mercek} boyama={boyama} temsili={ikiz.veri.temsili} sikisik />
            </div>
          ) : webglVar && noktalar.length ? (
            <div className="harita-lejant">
              {LEJANT.map((l) => (
                <span key={l.durum} className="rozet">
                  <span
                    className="nokta"
                    style={{ background: `rgb(${RENKLER[l.durum].join(',')})` }}
                  />
                  {l.etiket}
                </span>
              ))}
              {/*
                Sıradaki durak sarı ve siyah çerçeveli çiziliyor; lejantta sarı
                zaten "Tekrar gel" demek. Adı konmazsa satışçı haritadaki en
                önemli işareti yanlış okur.
              */}
              {kapsam === 'rota' && rotaVar ? (
                <span className="rozet">
                  <span
                    className="nokta"
                    style={{ background: 'rgb(255,201,0)', border: '2px solid #111827' }}
                  />
                  Sıradaki
                </span>
              ) : null}
            </div>
          ) : null}

          {/* Kart açıkken alttaki denetimler kartın altında kalır; hiç çizilmez. */}
          {webglVar && gorunum && noktalar.length && !secili ? (
            <div className="hr-telefon-alt">
              <AltlikSecici kip={altlikKipi} degisti={setAltlikKipi} buyuk />
              <Atif
                metin={altlikKipi === 'sade' ? 'Yollar © OpenStreetMap katkıcıları' : altlik.atif}
                durum={altlik.durum}
                ortulu={altlik.ortulu}
              />
            </div>
          ) : null}

          <div className="harita-dugmeler">
            {webglVar && gorunum && noktalar.length ? (
              <UcBDugmesi
                acik={ucB}
                degisti={ucBDegistir}
                hazirlaniyor={ikiz.durum === 'yukleniyor'}
                yuvarlak
              />
            ) : null}
            <button className="harita-yuvarlak" onClick={konumaGit} aria-label="Konumuma git">
              <Pusula boyut={26} />
            </button>
          </div>

          {secili ? (
            <div className="harita-kart">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span
                  className="nokta"
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: 999,
                    background: `rgb(${(RENKLER[secili.durum] ?? RENKLER.bekliyor).join(',')})`,
                    flex: '0 0 auto',
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="kart-ad">{secili.ad}</div>
                  {secili.loc ? (
                    <div
                      className="kart-adres"
                      style={{
                        margin: 0,
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
                        userSelect: 'all',
                      }}
                    >
                      Location Id {secili.loc}
                    </div>
                  ) : null}
                  <div className="kart-adres" style={{ margin: 0 }}>
                    {DURUM_ETIKETLERI[secili.durum]}
                    {secili.firsat ? ` · ${sayi(secili.firsat)} boş kapı` : ''}
                  </div>
                </div>
                {/* 3B'de binalar sık; kartı kapatmak için boş yer aramak zorunda kalınmasın. */}
                <button
                  type="button"
                  className="hr-kart-kapat"
                  onClick={() => setSecili(null)}
                  aria-label="Kartı kapat"
                >
                  <Kapat boyut={20} />
                </button>
              </div>
              <button
                className="dugme birincil"
                style={{ marginTop: 12 }}
                onClick={() => git(`/bina/${encodeURIComponent(secili.serial)}`)}
              >
                Binayı aç
                <Ileri boyut={20} />
              </button>
            </div>
          ) : null}
        </div>
      </SayfaGovde>
    </Sayfa>
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
