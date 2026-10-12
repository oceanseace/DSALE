/**
 * Harita altlığı — "yakınlaştırınca Google Maps gibi olsun".
 *
 * Karo (tile) adresleri sunucudan gelir (`GET /api/ayar/altlik`); uç yoksa
 * ya da cevap bozuksa varsayılan OSM sokak + Esri uydu kullanılır.
 *
 * Güven kuralı: harita HİÇBİR koşulda boş görünmez. Karolar görünen alanı
 * tam örtene kadar sunucudaki sade yol çizgileri de çizilir. Çevrimdışıyken
 * ya da kurum ağı karo sunucusunu engellediğinde karo gelmez, yol çizgileri
 * kalır — kullanıcı bir şeyin bozulduğunu değil, sade haritayı görür.
 *
 * Dışarı giden tek şey karo isteğidir: yalnız z/x/y numarası. Bina, kişi,
 * konum bilgisi karo sunucusuna gitmez.
 *
 * deck.gl'in TileLayer'ı ayrı bir paket (@deck.gl/geo-layers, onlarca alt
 * bağımlılık) istiyor; bize gereken küçük kısmı burada: görünen karoları seç,
 * sırayla indir, hazır olanı BitmapLayer ile yere ser.
 */

import { BitmapLayer } from '@deck.gl/layers';
import { WebMercatorViewport, type MapViewState } from '@deck.gl/core';
import { useEffect, useMemo, useRef, useState } from 'react';
import { istek, SahaHatasi, SAHTE_IZIN, sahteMod } from '../api/istemci';

export type AltlikKipi = 'harita' | 'uydu' | 'sade';
export const ALTLIK_KIPLERI: readonly AltlikKipi[] = ['harita', 'uydu', 'sade'];

/** `GET /api/ayar/altlik` yanıtı (sunucu: `saha/altlik.py`). */
export interface AltlikAyari {
  sokak_url?: string | null;
  uydu_url?: string | null;
  /** Katman başına atıf; yoksa ortak `atif` kullanılır. */
  sokak_atif?: string | null;
  uydu_atif?: string | null;
  /** İki katmanın atfı tek satırda (ya da eski biçimde katman başına nesne). */
  atif?: string | { sokak?: string | null; uydu?: string | null } | null;
  sokak_en_fazla_zoom?: number | null;
  uydu_en_fazla_zoom?: number | null;
}

interface Kaynak {
  ad: 'sokak' | 'uydu';
  sablon: string;
  atif: string;
  /** Kaynağın en ayrıntılı karo seviyesi; ötesinde bu seviye büyütülür. */
  enFazlaZ: number;
}

interface Kaynaklar {
  sokak: Kaynak;
  uydu: Kaynak;
}

const VARSAYILAN: Kaynaklar = {
  sokak: {
    ad: 'sokak',
    sablon: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    atif: '© OpenStreetMap katkıcıları',
    enFazlaZ: 19,
  },
  uydu: {
    ad: 'uydu',
    sablon:
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    atif: 'Uydu: Esri, Maxar, Earthstar Geographics',
    enFazlaZ: 19,
  },
};

/* ------------------------------ Ayar ------------------------------ */

let ayarSozu: Promise<Kaynaklar> | null = null;

function sablonGecerli(deger: unknown): deger is string {
  return (
    typeof deger === 'string' &&
    /^https?:\/\//i.test(deger) &&
    deger.includes('{z}') &&
    deger.includes('{x}') &&
    (deger.includes('{y}') || deger.includes('{-y}'))
  );
}

function zoomGecerli(deger: unknown, varsayilan: number) {
  const z = Number(deger);
  return Number.isInteger(z) && z >= 1 && z <= 22 ? z : varsayilan;
}

function kaynaklariKur(ayar: AltlikAyari | null): Kaynaklar {
  if (!ayar || typeof ayar !== 'object') return VARSAYILAN;
  const atif = ayar.atif;
  const ortak = typeof atif === 'string' ? atif : null;
  const nesne = atif && typeof atif === 'object' ? atif : null;
  const sokakAtif = ayar.sokak_atif || nesne?.sokak || ortak || VARSAYILAN.sokak.atif;
  const uyduAtif = ayar.uydu_atif || nesne?.uydu || ortak || VARSAYILAN.uydu.atif;
  const kur = (ad: 'sokak' | 'uydu', url: unknown, metin: string, z: unknown): Kaynak =>
    sablonGecerli(url)
      ? { ad, sablon: url, atif: metin, enFazlaZ: zoomGecerli(z, VARSAYILAN[ad].enFazlaZ) }
      : { ...VARSAYILAN[ad], atif: metin };
  return {
    sokak: kur('sokak', ayar.sokak_url, sokakAtif, ayar.sokak_en_fazla_zoom),
    uydu: kur('uydu', ayar.uydu_url, uyduAtif, ayar.uydu_en_fazla_zoom),
  };
}

/** Karo adresleri bir kez sorulur; uç yoksa (404) varsayılanlar geçerlidir. */
function kaynaklariAl(): Promise<Kaynaklar> {
  if (!ayarSozu) {
    ayarSozu = (async () => {
      if (SAHTE_IZIN && sahteMod) return VARSAYILAN;
      try {
        return kaynaklariKur(await istek<AltlikAyari>('/api/ayar/altlik', { zamanAsimiMs: 8000 }));
      } catch (h) {
        // Uç yoksa (404) ya da bu kullanıcıya kapalıysa varsayılanlar bu oturumda
        // geçerli kalır; bağlantı yoksa bir sonraki seçimde yeniden sorulur.
        const kalici = h instanceof SahaHatasi && [403, 404, 405].includes(h.durum);
        if (!kalici) ayarSozu = null;
        return VARSAYILAN;
      }
    })();
  }
  return ayarSozu;
}

/* ------------------------------ Karo matematiği ------------------------------ */

type Sinir = [number, number, number, number]; // [batı, güney, doğu, kuzey]

function karoLon(x: number, z: number) {
  return (x / 2 ** z) * 360 - 180;
}

function karoLat(y: number, z: number) {
  const n = Math.PI * (1 - (2 * y) / 2 ** z);
  return (Math.atan(Math.sinh(n)) * 180) / Math.PI;
}

function lonKaro(lon: number, z: number) {
  return Math.floor(((lon + 180) / 360) * 2 ** z);
}

function latKaro(lat: number, z: number) {
  const r = (Math.max(-85.05, Math.min(85.05, lat)) * Math.PI) / 180;
  return Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z);
}

interface KaroNo {
  z: number;
  x: number;
  y: number;
}

/**
 * Ekranda görünen karolar.
 *
 * Düz haritada hepsi aynı seviyededir (256 px karo ekranda 181–362 px).
 * 3B'de kamera eğikken uzaktaki karolar ekranda küçülür; orada daha kaba bir
 * seviye yeter (Google Maps'te de ufka doğru harita bulanıklaşır). Seçim
 * aşağıdan yukarı yapılır: görünen alanın hedef seviyedeki karoları ekrana
 * izdüşürülür, ekranda küçük kalanın yerine atası alınır.
 *
 * (Büyük karolardan başlayıp bölmek eğik kamerada ÇALIŞMAZ: kameranın
 * arkasına düşen köşelerin izdüşümü anlamsız çıkıyor ve bütün karolar
 * "görünmüyor" sayılıyordu — 3B'de altlık boş kalıyordu.)
 */
export function karolariSec(
  gorunum: MapViewState,
  genislik: number,
  yukseklik: number,
  enFazlaZ: number,
): KaroNo[] {
  if (!genislik || !yukseklik) return [];
  let gorus: WebMercatorViewport;
  try {
    gorus = new WebMercatorViewport({ ...gorunum, width: genislik, height: yukseklik });
  } catch {
    return [];
  }
  const [bati, guney, dogu, kuzey] = gorus.getBounds() as Sinir;
  let hedefZ = Math.max(1, Math.min(enFazlaZ, Math.round(gorunum.zoom + 1)));
  const egik = (gorunum.pitch ?? 0) > 1;

  // Eğik kamerada görünen alanın kutusu büyür; karo sayısı taşarsa seviye düşer.
  let x1 = 0;
  let x2 = 0;
  let y1 = 0;
  let y2 = 0;
  for (;;) {
    const ust = 2 ** hedefZ - 1;
    x1 = Math.max(0, lonKaro(bati, hedefZ));
    x2 = Math.min(ust, lonKaro(dogu, hedefZ));
    y1 = Math.max(0, latKaro(kuzey, hedefZ));
    y2 = Math.min(ust, latKaro(guney, hedefZ));
    if ((x2 - x1 + 1) * (y2 - y1 + 1) <= 900 || hedefZ <= 1) break;
    hedefZ -= 1;
  }

  if (!egik) {
    const duz: KaroNo[] = [];
    for (let x = x1; x <= x2; x++) for (let y = y1; y <= y2; y++) duz.push({ z: hedefZ, x, y });
    return duz;
  }

  const ESIK = 256 * Math.SQRT2;
  const secilen = new Map<string, KaroNo>();
  const kose = (x: number, y: number) =>
    gorus.project([karoLon(x, hedefZ), karoLat(y, hedefZ)]) as number[];
  for (let x = x1; x <= x2; x++) {
    for (let y = y1; y <= y2; y++) {
      const a = kose(x, y);
      const b = kose(x + 1, y);
      const c = kose(x + 1, y + 1);
      const d = kose(x, y + 1);
      // Dört köşe de ekranın aynı dışında ise karo görünmez.
      if (
        Math.max(a[0], b[0], c[0], d[0]) < 0 ||
        Math.min(a[0], b[0], c[0], d[0]) > genislik ||
        Math.max(a[1], b[1], c[1], d[1]) < 0 ||
        Math.min(a[1], b[1], c[1], d[1]) > yukseklik
      ) {
        continue;
      }
      const boy =
        Math.max(Math.hypot(c[0] - a[0], c[1] - a[1]), Math.hypot(d[0] - b[0], d[1] - b[1])) /
        Math.SQRT2;
      // Ekranda küçük kalan karo için atası: her üst seviye iki kat büyük görünür.
      let dz = boy > 0 ? Math.floor(Math.log2(ESIK / boy)) : 0;
      dz = Math.max(0, Math.min(6, dz, hedefZ - 1));
      const z = hedefZ - dz;
      const anahtar = `${z}/${x >> dz}/${y >> dz}`;
      if (!secilen.has(anahtar)) secilen.set(anahtar, { z, x: x >> dz, y: y >> dz });
    }
  }
  // Kaba karolar önce çizilir; üstlerine ince ayrıntılı olanlar biner.
  return [...secilen.values()].sort((p, q) => p.z - q.z);
}

/* ------------------------------ Karo deposu ------------------------------ */

interface Karo {
  anahtar: string;
  z: number;
  x: number;
  y: number;
  url: string;
  sinir: Sinir;
  durum: 'bos' | 'yukleniyor' | 'hazir' | 'hata';
  resim: HTMLImageElement | null;
  hataZamani: number;
}

/** Kaynak sağlığı: hiç karo gelmiyorsa boşuna istek atılmaz. */
interface Saglik {
  basari: number;
  ardisikHata: number;
  /** Bu zamana kadar istek atılmaz (ms). */
  bekle: number;
}

const EN_FAZLA_ESZAMANLI = 8;
/**
 * Bellekte tutulan en fazla karo. Her karo çözülmüş hâliyle ~256 kB yer
 * kaplar: telefonda 150 karo ≈ 40 MB, dizüstünde 400 karo ≈ 100 MB.
 */
const DEPO_SINIRI = (() => {
  try {
    return window.matchMedia('(max-width: 760px), (pointer: coarse)').matches ? 150 : 400;
  } catch {
    return 300;
  }
})();
const TEKRAR_DENE_MS = 30000;

const depo = new Map<string, Karo>();
const saglik: Record<Kaynak['ad'], Saglik> = {
  sokak: { basari: 0, ardisikHata: 0, bekle: 0 },
  uydu: { basari: 0, ardisikHata: 0, bekle: 0 },
};
const dinleyiciler = new Set<() => void>();
let ucusta = 0;
let kuyruk: Array<{ karo: Karo; kaynak: Kaynak }> = [];

function haberVer() {
  dinleyiciler.forEach((d) => d());
}

function karoUrl(sablon: string, k: KaroNo) {
  return sablon
    .replace('{z}', String(k.z))
    .replace('{x}', String(k.x))
    .replace('{y}', String(k.y))
    .replace('{-y}', String(2 ** k.z - 1 - k.y)) // TMS düzeni (y aşağıdan yukarı)
    .replace('{s}', 'abc'[(k.x + k.y) % 3])
    .replace('{r}', '');
}

function karoAl(kaynak: Kaynak, no: KaroNo): Karo {
  const anahtar = `${kaynak.ad}/${no.z}/${no.x}/${no.y}`;
  let karo = depo.get(anahtar);
  if (karo) {
    // En son kullanılan sona gider: taşınca en eski ve görünmeyen silinir.
    depo.delete(anahtar);
    depo.set(anahtar, karo);
    return karo;
  }
  karo = {
    anahtar,
    ...no,
    url: karoUrl(kaynak.sablon, no),
    sinir: [karoLon(no.x, no.z), karoLat(no.y + 1, no.z), karoLon(no.x + 1, no.z), karoLat(no.y, no.z)],
    durum: 'bos',
    resim: null,
    hataZamani: 0,
  };
  depo.set(anahtar, karo);
  return karo;
}

/**
 * Depo taşınca en eski karolar atılır — ama şu an ekranda gereken ya da
 * inmekte olan hiçbir karo atılmaz (yoksa görünen karo silinip yeniden
 * indirilir, harita yanıp söner).
 */
function depoyuBuda(gereken: ReadonlySet<Karo>) {
  if (depo.size <= DEPO_SINIRI) return;
  for (const [anahtar, karo] of depo) {
    if (depo.size <= DEPO_SINIRI * 0.8) break;
    if (karo.durum === 'yukleniyor' || gereken.has(karo)) continue;
    depo.delete(anahtar);
  }
}

function cevrimdisi() {
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

function kuyruguIsle() {
  while (ucusta < EN_FAZLA_ESZAMANLI && kuyruk.length) {
    const { karo, kaynak } = kuyruk.shift()!;
    if (karo.durum !== 'bos') continue;
    const s = saglik[kaynak.ad];
    if (cevrimdisi() || Date.now() < s.bekle) continue;
    indir(karo, s);
  }
}

function indir(karo: Karo, s: Saglik) {
  karo.durum = 'yukleniyor';
  ucusta += 1;
  const resim = new Image();
  resim.crossOrigin = 'anonymous'; // WebGL dokusu için şart (karo sunucusu CORS açık)
  resim.referrerPolicy = 'origin'; // karo sunucusu yalnız sitenin adını görür, sayfa yolunu değil
  resim.decoding = 'async';
  let bitti = false;
  const tamam = (basarili: boolean) => {
    if (bitti) return;
    bitti = true;
    ucusta -= 1;
    if (basarili) {
      karo.durum = 'hazir';
      karo.resim = resim;
      s.basari += 1;
      s.ardisikHata = 0;
    } else {
      karo.durum = 'hata';
      karo.hataZamani = Date.now();
      s.ardisikHata += 1;
      // Hiç karo gelmediyse (engelli ağ, CSP, sunucu kapalı) bir dakika sus.
      if (s.ardisikHata >= 8) s.bekle = Date.now() + 60000;
    }
    haberVer();
    kuyruguIsle();
  };
  resim.onload = () => {
    // Çözmeyi arka planda bitir; doku yüklenirken ana iş parçacığı takılmasın.
    if (typeof resim.decode === 'function') {
      resim.decode().then(
        () => tamam(true),
        () => tamam(true),
      );
    } else {
      tamam(true);
    }
  };
  resim.onerror = () => tamam(false);
  resim.src = karo.url;
}

/** Görünen karoları istek sırasına koyar: ekranın ortasına yakın olan önce. */
function istekleriGuncelle(kaynak: Kaynak, karolar: Karo[], merkez: [number, number]) {
  const simdi = Date.now();
  const bekleyen = karolar.filter((k) => {
    if (k.durum === 'hata' && simdi - k.hataZamani > TEKRAR_DENE_MS) k.durum = 'bos';
    return k.durum === 'bos';
  });
  const uzaklik = (k: Karo) => {
    const lon = (k.sinir[0] + k.sinir[2]) / 2;
    const lat = (k.sinir[1] + k.sinir[3]) / 2;
    return (lon - merkez[0]) ** 2 + (lat - merkez[1]) ** 2;
  };
  bekleyen.sort((a, b) => b.z - a.z || uzaklik(a) - uzaklik(b));
  // Eski sıra atılır: hızlı kaydırmada artık görünmeyen karo beklenmez.
  kuyruk = bekleyen.map((karo) => ({ karo, kaynak }));
  kuyruguIsle();
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    for (const s of Object.values(saglik)) {
      s.ardisikHata = 0;
      s.bekle = 0;
    }
    for (const k of depo.values()) if (k.durum === 'hata') k.durum = 'bos';
    haberVer();
  });
  window.addEventListener('offline', haberVer);
}

/* ------------------------------ Kanca ------------------------------ */

export type AltlikDurumu = 'kapali' | 'yukleniyor' | 'tamam' | 'cevrimdisi' | 'ulasilamiyor';

export interface AltlikSonucu {
  /** Yere serilecek karo katmanları (en altta çizilir). */
  katmanlar: BitmapLayer[];
  /** Görünen alanın tamamı karoyla örtülü mü? Değilse yol çizgileri de çizilmeli. */
  ortulu: boolean;
  durum: AltlikDurumu;
  atif: string | null;
}

const DERINLIK_YOK = { depthWriteEnabled: false, depthCompare: 'always' } as const;

/**
 * Haritanın altlığı. `gorunum` her karede değişir; iş yalnız görünen
 * karoların listesini çıkarmaktır (birkaç düzine), resimler depoda kalır.
 */
export function useAltlik(
  kip: AltlikKipi,
  gorunum: MapViewState | null,
  genislik: number,
  yukseklik: number,
): AltlikSonucu {
  const [kaynaklar, setKaynaklar] = useState<Kaynaklar>(VARSAYILAN);
  const [, setSurum] = useState(0);
  const kare = useRef<number | null>(null);

  useEffect(() => {
    if (kip === 'sade') return undefined;
    let iptal = false;
    void kaynaklariAl().then((k) => {
      if (!iptal) setKaynaklar(k);
    });
    return () => {
      iptal = true;
    };
  }, [kip]);

  /* Karo geldikçe yeniden çiz — aynı karede gelen onlarca karo tek çizimde. */
  useEffect(() => {
    const dinle = () => {
      if (kare.current != null) return;
      kare.current = requestAnimationFrame(() => {
        kare.current = null;
        setSurum((s) => s + 1);
      });
    };
    dinleyiciler.add(dinle);
    return () => {
      dinleyiciler.delete(dinle);
      if (kare.current != null) cancelAnimationFrame(kare.current);
      kare.current = null;
    };
  }, []);

  const kaynak = kip === 'sade' ? null : kip === 'uydu' ? kaynaklar.uydu : kaynaklar.sokak;

  const gereken = useMemo<Karo[]>(() => {
    if (!kaynak || !gorunum) return [];
    const liste = karolariSec(gorunum, genislik, yukseklik, kaynak.enFazlaZ).map((no) =>
      karoAl(kaynak, no),
    );
    depoyuBuda(new Set(liste));
    return liste;
  }, [kaynak, gorunum, genislik, yukseklik]);

  useEffect(() => {
    if (!kaynak || !gorunum) return;
    istekleriGuncelle(kaynak, gereken, [gorunum.longitude, gorunum.latitude]);
  }, [kaynak, gereken, gorunum]);

  // Her çizimde yeniden kurulur (karo geldikçe liste büyür); katman nesneleri
  // hafiftir, deck.gl aynı kimlikli katmanın dokusunu yeniden yüklemez.
  const hazir: Karo[] = [];
  const yedek = new Map<string, Karo>();
  const enFazlaAta = cevrimdisi() || (kaynak && Date.now() < saglik[kaynak.ad].bekle) ? 1 : 4;
  let eksik = 0;
  for (const k of gereken) {
    if (k.durum === 'hazir') {
      hazir.push(k);
      continue;
    }
    eksik += 1;
    // Yakınlaşırken yeni karo gelene kadar bir üst seviyedeki (bulanık ama
    // doğru yerdeki) karo gösterilir — Google Maps'teki gibi, boşluk olmaz.
    // Çevrimdışıyken yeni karo hiç gelmeyecek: 16 kat büyütülmüş, okunmaz bir
    // karo yerine sade yollar daha iyidir; en fazla bir üst seviye kullanılır.
    if (!kaynak) continue;
    for (let dz = 1; dz <= enFazlaAta && k.z - dz >= 0; dz++) {
      const ata = depo.get(`${kaynak.ad}/${k.z - dz}/${k.x >> dz}/${k.y >> dz}`);
      if (ata?.durum === 'hazir') {
        yedek.set(ata.anahtar, ata);
        break;
      }
    }
  }
  // Kaba (üst seviye) karolar önce, ayrıntılı olanlar üstüne; aynı karo iki kez çizilmez.
  for (const k of hazir) yedek.set(k.anahtar, k);
  const sirali = [...yedek.values()].sort((a, b) => a.z - b.z);
  const katmanlar = sirali.map(
    (k) =>
      new BitmapLayer({
        id: `altlik-${k.anahtar}`,
        image: k.resim,
        bounds: k.sinir,
        // Sokak haritası biraz soldurulur: veri renkleri (yeşil/gri/sarı) öne çıksın.
        desaturate: kip === 'harita' ? 0.3 : 0,
        pickable: false,
        parameters: DERINLIK_YOK,
      }),
  );

  let durum: AltlikDurumu = 'kapali';
  if (kaynak) {
    const s = saglik[kaynak.ad];
    // Hiç karo gelmedi ve istenenlerin hepsi hata verdi: ağ/kurum engeli ya da
    // güvenlik başlığı (CSP) karo sunucusunu kapatıyor. Sade haritadayız.
    const hepsiHata =
      s.basari === 0 &&
      s.ardisikHata > 0 &&
      gereken.length > 0 &&
      gereken.every((k) => k.durum === 'hata');
    if (cevrimdisi()) durum = 'cevrimdisi';
    else if (hepsiHata || (s.basari === 0 && Date.now() < s.bekle)) durum = 'ulasilamiyor';
    else durum = eksik ? 'yukleniyor' : 'tamam';
  }

  return {
    katmanlar,
    ortulu: Boolean(kaynak) && gereken.length > 0 && eksik === 0,
    durum,
    atif: kaynak ? kaynak.atif : null,
  };
}
