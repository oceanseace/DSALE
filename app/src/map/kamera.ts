/**
 * Kamera yardımcıları: hazır açılar, uçuş (flyTo) ve doğrusal geçiş ara-değerleri, sınıra sığdırma,
 * ve controller'dan bağımsız çalışan rAF tabanlı kamera sürücüsü (sunumda etkileşim kapalıyken de çalışır).
 */
import { FlyToInterpolator, LinearInterpolator, WebMercatorViewport } from '@deck.gl/core';
import { easeCubicInOut } from 'd3-ease';
import type { LonLat } from '../data/types';

/** deck.gl MapView görünüm durumu (yalın). */
export interface KameraDurumu {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

export type GecisTuru = 'fly' | 'linear';
export type Yumusatma = (t: number) => number;

export interface GecisSecenekleri {
  /** 'fly' = van Wijk-Nuij uçuşu (uzak noktalar arası, zoom-out-in), 'linear' = doğrusal (yakın açılar, yörünge) */
  tur?: GecisTuru;
  /** 0..1 → 0..1 eğrisi (varsayılan easeCubicInOut) */
  yumusatma?: Yumusatma;
  /** FlyTo eğriliği (varsayılan 1.414) */
  egri?: number;
}

/* ================================================================== hazır açılar */

/** Ofis (Nilüfer) — meta.ofis ile aynı */
export const OFIS_KONUM: LonLat = [28.953528321918512, 40.22043814320989];

export const KAMERA = {
  /** Bursa + Yalova tümü, kuşbakışı */
  genel: { longitude: 29.19, latitude: 40.36, zoom: 9.35, pitch: 0, bearing: 0 },
  /** Bursa + Yalova, eğik (3B) */
  genelEgik: { longitude: 29.12, latitude: 40.30, zoom: 9.7, pitch: 45, bearing: -12 },
  /** Bursa kent merkezi (Nilüfer–Osmangazi–Yıldırım), eğik */
  bursa: { longitude: 28.985, latitude: 40.205, zoom: 11.6, pitch: 55, bearing: -18 },
  /** Nilüfer yakın plan */
  nilufer: { longitude: 28.92, latitude: 40.215, zoom: 12.6, pitch: 60, bearing: -25 },
  /** Ofis çevresi yakın plan */
  ofis: { longitude: OFIS_KONUM[0], latitude: OFIS_KONUM[1] - 0.004, zoom: 14.2, pitch: 62, bearing: -20 },
  /** Yalova */
  yalova: { longitude: 29.265, latitude: 40.635, zoom: 12.4, pitch: 50, bearing: 0 },
} as const satisfies Record<string, KameraDurumu>;

/* ================================================================== saf fonksiyonlar */

const _fly = new FlyToInterpolator();
const _flyEgri = new Map<number, FlyToInterpolator>();
const _lin = new LinearInterpolator({ transitionProps: ['longitude', 'latitude', 'zoom', 'pitch', 'bearing'] });

/** Açıyı (-180, 180] aralığına indirger. */
export function aciNormalize(a: number): number {
  let x = ((a + 180) % 360 + 360) % 360 - 180;
  if (x === -180) x = 180;
  return x;
}

/** Kısa yoldan dönecek şekilde hedef açıyı başlangıca göre ayarlar. */
function kisaYolAci(bas: number, hedef: number): number {
  return bas + aciNormalize(hedef - bas);
}

/**
 * İki kamera durumu arasında t (0..1) anındaki durum. width/height fly için gerekir.
 */
export function kameraAraDeger(
  a: KameraDurumu,
  b: KameraDurumu,
  t: number,
  boyut: { width: number; height: number },
  secenek: GecisSecenekleri = {},
): KameraDurumu {
  const hedef = { ...b, bearing: kisaYolAci(a.bearing, b.bearing) };
  if (secenek.tur === 'linear') {
    const r = _lin.interpolateProps(a as never, hedef as never, t) as unknown as KameraDurumu;
    return { ...r };
  }
  let fly = _fly;
  if (secenek.egri) {
    fly = _flyEgri.get(secenek.egri) ?? new FlyToInterpolator({ curve: secenek.egri });
    _flyEgri.set(secenek.egri, fly);
  }
  const r = fly.interpolateProps({ ...a, ...boyut } as never, { ...hedef, ...boyut } as never, t) as unknown as KameraDurumu;
  return { longitude: r.longitude, latitude: r.latitude, zoom: r.zoom, pitch: r.pitch, bearing: r.bearing };
}

export interface SigdirSecenekleri {
  width: number;
  height: number;
  /** piksel; sayı ya da {top,bottom,left,right} */
  padding?: number | { top: number; bottom: number; left: number; right: number };
  pitch?: number;
  bearing?: number;
  maxZoom?: number;
}

/**
 * Sınır kutusunu [[minLon,minLat],[maxLon,maxLat]] ekrana sığdıran kamera.
 * Not: sığdırma kuşbakışı hesaplanır; pitch/bearing sonradan eklenir (eğik görünümde biraz daha geniş görünür).
 */
export function fitBounds(kutu: [LonLat, LonLat], s: SigdirSecenekleri): KameraDurumu {
  const vp = new WebMercatorViewport({ width: s.width, height: s.height });
  const { longitude, latitude, zoom } = vp.fitBounds(kutu, {
    padding: s.padding ?? 80,
    maxZoom: s.maxZoom ?? 16,
  });
  return { longitude, latitude, zoom, pitch: s.pitch ?? 0, bearing: s.bearing ?? 0 };
}

/* ================================================================== kamera sürücüsü */

interface Ucus {
  bas: KameraDurumu;
  hedef: KameraDurumu;
  baslangic: number;
  sure: number;
  secenek: GecisSecenekleri;
  bitti: (tamamlandi: boolean) => void;
}

/**
 * rAF tabanlı kamera sürücüsü. HaritaSahnesi tarafından oluşturulur; dışarıya HaritaApi ile açılır.
 *  - flyTo: hedefe animasyonlu geçiş (Promise<boolean>: true = tamamlandı, false = kesildi)
 *  - orbit: sabit hızda yörünge (bearing artışı); uçuş sırasında durur, sonra devam eder
 */
export class KameraSurucusu {
  private ucus: Ucus | null = null;
  private orbitHiz = 0; // derece / saniye
  private raf = 0;
  private sonZaman = 0;

  constructor(
    private oku: () => KameraDurumu,
    private yaz: (vs: KameraDurumu) => void,
    private boyut: () => { width: number; height: number },
  ) {}

  flyTo(hedef: Partial<KameraDurumu>, sureMs = 2500, secenek: GecisSecenekleri = {}): Promise<boolean> {
    this.ucusuKes();
    const bas = this.oku();
    const tam: KameraDurumu = { ...bas, ...hedef };
    if (sureMs <= 0) {
      this.yaz(tam);
      return Promise.resolve(true);
    }
    return new Promise<boolean>((bitti) => {
      this.ucus = { bas, hedef: tam, baslangic: performance.now(), sure: sureMs, secenek, bitti };
      this.baslat();
    });
  }

  /** derece/saniye; 0 = durdur. Pozitif = saat yönünün tersine dönen harita. */
  orbit(dereceSaniye = 3): void {
    this.orbitHiz = dereceSaniye;
    if (dereceSaniye) this.baslat();
  }

  orbitHizi(): number {
    return this.orbitHiz;
  }

  /** Kamera hareket hâlinde mi (uçuş ya da yörünge)? */
  mesgulMu(): boolean {
    return this.ucus != null || this.orbitHiz !== 0;
  }

  /** Uçuşu ve yörüngeyi durdurur. */
  durdur(): void {
    this.orbitHiz = 0;
    this.ucusuKes();
  }

  /** Kullanıcı etkileşimi başladığında: her şeyi bırak. */
  etkilesim(): void {
    this.durdur();
  }

  yokEt(): void {
    this.durdur();
    cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private ucusuKes(): void {
    if (this.ucus) {
      const b = this.ucus.bitti;
      this.ucus = null;
      b(false);
    }
  }

  private baslat(): void {
    if (this.raf) return;
    this.sonZaman = performance.now();
    this.raf = requestAnimationFrame(this.kare);
  }

  private kare = (simdi: number): void => {
    this.raf = 0;
    const dt = Math.min(0.1, (simdi - this.sonZaman) / 1000);
    this.sonZaman = simdi;
    let vs: KameraDurumu | null = null;
    if (this.ucus) {
      const u = this.ucus;
      const ham = Math.min(1, (simdi - u.baslangic) / u.sure);
      const t = (u.secenek.yumusatma ?? easeCubicInOut)(ham);
      vs = kameraAraDeger(u.bas, u.hedef, t, this.boyut(), u.secenek);
      if (ham >= 1) {
        vs = { ...u.hedef, bearing: kisaYolAci(u.bas.bearing, u.hedef.bearing) };
        this.ucus = null;
        this.yaz(vs);
        u.bitti(true);
        vs = null;
      }
    } else if (this.orbitHiz) {
      const o = this.oku();
      vs = { ...o, bearing: o.bearing + this.orbitHiz * dt };
    }
    if (vs) this.yaz(vs);
    if (this.ucus || this.orbitHiz) this.raf = requestAnimationFrame(this.kare);
  };
}
