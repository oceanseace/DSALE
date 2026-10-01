/**
 * HaritaSahnesi — uygulamadaki TEK deck.gl yüzeyi.
 *
 * Sunum ve Keşif bu bileşeni kullanır; ikisi de katman üretimini `katmanlar.ts` fabrikasından yapar.
 * Kamera iki şekilde sürülür:
 *   1. Bildirimsel (declarative): `kamera={{ durum, sureMs, tur }}` — prop değişince oraya uçar.
 *   2. Buyurgan (imperative): ref üzerinden `flyTo / orbit / fitBounds / kameraAyarla / durdur`.
 * Her ikisi de `KameraSurucusu` (rAF) üzerinden çalışır; controller kapalıyken (sunum) de akar.
 *
 * `katmanlar` bir fonksiyon verilirse (t: saniye) rAF saati çalışır ve her karede katmanlar
 * yeniden üretilir (deck.gl yalnız değişen prop'ları işler). Dizi verilirse saat durur — sunum
 * sahnesi durduğunda GPU boşta kalır.
 */
import { forwardRef, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import DeckGL from '@deck.gl/react';
import { WebMercatorViewport } from '@deck.gl/core';
import type { Deck, LayersList, PickingInfo } from '@deck.gl/core';

import { KAMERA, KameraSurucusu, fitBounds, type GecisSecenekleri, type KameraDurumu } from './kamera';
import { isikEfekti, type IsikOnAyari } from './isik';
import type { LonLat } from '../data/types';

/* ================================================================== tipler */

export interface Boyut {
  width: number;
  height: number;
}

/** Bildirimsel kamera hedefi. Nesne kimliği değil, içeriği değişince uçuş başlar. */
export interface KameraHedefi extends GecisSecenekleri {
  durum: Partial<KameraDurumu>;
  /** 0 = anında ata */
  sureMs?: number;
}

/** Ref ile dışarıya açılan kamera/sahne API'si. */
export interface HaritaApi {
  /** Hedefe uçar. Promise: true = tamamlandı, false = kesildi (yeni uçuş ya da kullanıcı). */
  flyTo(hedef: Partial<KameraDurumu>, sureMs?: number, secenek?: GecisSecenekleri): Promise<boolean>;
  /** Sabit hızda yörünge (derece/saniye); 0 = durdur. */
  orbit(dereceSaniye?: number): void;
  /** Uçuşu ve yörüngeyi durdurur. */
  durdur(): void;
  /** Sınır kutusunu ekrana sığdırır (uçarak). */
  fitBounds(
    kutu: [LonLat, LonLat],
    o?: { padding?: number | { top: number; bottom: number; left: number; right: number }; pitch?: number; bearing?: number; maksZoom?: number; sureMs?: number; secenek?: GecisSecenekleri },
  ): Promise<boolean>;
  /** Sınır kutusunun kamera karşılığı (uçmadan hesap). */
  sigdirHesapla(
    kutu: [LonLat, LonLat],
    o?: { padding?: number | { top: number; bottom: number; left: number; right: number }; pitch?: number; bearing?: number; maksZoom?: number },
  ): KameraDurumu;
  /** Anlık kamera durumu. */
  kamera(): KameraDurumu;
  /** Kamerayı anında ayarlar (animasyonsuz). */
  kameraAyarla(k: Partial<KameraDurumu>): void;
  /** Tuval boyutu (CSS pikseli). */
  boyut(): Boyut;
  /** lon/lat (ve isteğe bağlı yükseklik) → ekran pikseli; HTML çağrı balonları için. */
  yansit(konum: LonLat | [number, number, number]): [number, number];
  /** Kamera hareket hâlinde mi (uçuş/yörünge) — QA `mesgul` bunu kullanır. */
  mesgulMu(): boolean;
  /** Alttaki Deck örneği (nadiren gerekir). */
  deck(): Deck<never> | null;
}

export interface HaritaSahnesiProps {
  /** Katman listesi ya da (t saniye) → katman listesi (rAF saatini açar). */
  katmanlar: LayersList | ((t: number) => LayersList);
  /** İlk kamera (varsayılan KAMERA.bursa). */
  baslangicKamera?: Partial<KameraDurumu>;
  /** Bildirimsel kamera hedefi; içeriği değişince uçar. */
  kamera?: KameraHedefi | null;
  /** Kullanıcı etkileşimi (varsayılan kapalı — sunum). true ya da deck.gl controller seçenekleri. */
  etkilesim?: boolean | Record<string, unknown>;
  /** Işık ön ayarı; false = ışıksız (düz renkler). */
  isik?: IsikOnAyari | false;
  pickingRadius?: number;
  onHover?: (bilgi: PickingInfo) => void;
  onClick?: (bilgi: PickingInfo) => void;
  getTooltip?: (bilgi: PickingInfo) => string | null;
  getCursor?: (durum: { isHovering: boolean; isDragging: boolean }) => string;
  /** İlk gerçek kare çizildikten sonra bir kez (fontlar + veri hazır demektir). */
  onIlkKare?: () => void;
  /** Her kamera değişiminde (uçuş kareleri dahil). */
  onKameraDegisti?: (k: KameraDurumu) => void;
  /** Kamera meşgulken true (QA `__DSALE__.mesgul`). */
  onMesgul?: (mesgul: boolean) => void;
  /** Boyut değişiminde. */
  onBoyut?: (b: Boyut) => void;
  /** Saati zorla çalıştır (katmanlar dizi olsa bile). */
  saat?: boolean;
  /** Harita üstüne konan HTML (sunum katmanı, paneller). */
  children?: ReactNode;
  style?: CSSProperties;
}

/* ================================================================== bileşen */

const VARSAYILAN_KAMERA: KameraDurumu = { ...KAMERA.bursa };

const HaritaSahnesi = forwardRef<HaritaApi, HaritaSahnesiProps>(function HaritaSahnesi({
  katmanlar,
  baslangicKamera,
  kamera = null,
  etkilesim = false,
  isik = 'gece',
  pickingRadius = 6,
  onHover,
  onClick,
  getTooltip,
  getCursor,
  onIlkKare,
  onKameraDegisti,
  onMesgul,
  onBoyut,
  saat = false,
  children,
  style,
}, ref) {
  const kapsayici = useRef<HTMLDivElement>(null);
  const [boyut, setBoyut] = useState<Boyut>(() => ({
    width: typeof window === 'undefined' ? 1920 : window.innerWidth,
    height: typeof window === 'undefined' ? 1080 : window.innerHeight,
  }));
  const boyutRef = useRef(boyut);
  boyutRef.current = boyut;

  const [gorunum, setGorunum] = useState<KameraDurumu>(() => ({ ...VARSAYILAN_KAMERA, ...baslangicKamera }));
  const gorunumRef = useRef(gorunum);
  const deckRef = useRef<{ deck?: Deck<never> } | null>(null);
  const kareSayaci = useRef(0);
  const ilkKareBildirildi = useRef(false);
  const mesgulRef = useRef(false);

  const onIlkKareRef = useRef(onIlkKare);
  onIlkKareRef.current = onIlkKare;
  const onKameraRef = useRef(onKameraDegisti);
  onKameraRef.current = onKameraDegisti;
  const onMesgulRef = useRef(onMesgul);
  onMesgulRef.current = onMesgul;

  const mesgulBildir = useCallback((m: boolean) => {
    if (mesgulRef.current === m) return;
    mesgulRef.current = m;
    onMesgulRef.current?.(m);
  }, []);

  const kameraYaz = useCallback(
    (vs: KameraDurumu) => {
      gorunumRef.current = vs;
      setGorunum(vs);
      onKameraRef.current?.(vs);
    },
    [],
  );

  /* ---------------------------------------------------------------- kamera sürücüsü */
  const surucu = useMemo(
    () => new KameraSurucusu(() => gorunumRef.current, kameraYaz, () => boyutRef.current),
    [kameraYaz],
  );
  useEffect(() => () => surucu.yokEt(), [surucu]);

  const ucus = useCallback(
    async (hedef: Partial<KameraDurumu>, sureMs = 2000, secenek: GecisSecenekleri = {}) => {
      mesgulBildir(true);
      const tamam = await surucu.flyTo(hedef, sureMs, secenek);
      // yalnız son uçuş bitti bildirir (kesilen uçuşun ardından yenisi meşgul kalır)
      if (tamam || !surucu.mesgulMu()) mesgulBildir(surucu.mesgulMu());
      return tamam;
    },
    [surucu, mesgulBildir],
  );

  /* ---------------------------------------------------------------- boyut takibi */
  useLayoutEffect(() => {
    const el = kapsayici.current;
    if (!el) return;
    const olc = () => {
      const r = el.getBoundingClientRect();
      const b = { width: Math.max(1, Math.round(r.width)), height: Math.max(1, Math.round(r.height)) };
      if (b.width === boyutRef.current.width && b.height === boyutRef.current.height) return;
      boyutRef.current = b;
      setBoyut(b);
      onBoyut?.(b);
    };
    olc();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', olc);
      return () => window.removeEventListener('resize', olc);
    }
    const go = new ResizeObserver(olc);
    go.observe(el);
    return () => go.disconnect();
    // onBoyut kasıtlı olarak bağımlılıkta değil (her render'da yeniden gözlemlemeyelim)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------------------------------------------------------------- rAF saati */
  const saatGerekli = typeof katmanlar === 'function' || saat;
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!saatGerekli) return;
    let raf = 0;
    const t0 = performance.now();
    const kare = (simdi: number) => {
      setT((simdi - t0) / 1000);
      raf = requestAnimationFrame(kare);
    };
    raf = requestAnimationFrame(kare);
    return () => cancelAnimationFrame(raf);
  }, [saatGerekli]);

  /* ---------------------------------------------------------------- bildirimsel kamera */
  const kameraImzasi = kamera
    ? JSON.stringify([kamera.durum, kamera.sureMs ?? 2000, kamera.tur ?? 'fly', kamera.egri ?? 0])
    : '';
  useEffect(() => {
    if (!kamera) return;
    void ucus(kamera.durum, kamera.sureMs ?? 2000, { tur: kamera.tur, yumusatma: kamera.yumusatma, egri: kamera.egri });
    // kameraImzasi içerik değişimini yakalar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kameraImzasi]);

  /* ---------------------------------------------------------------- ref API */
  useImperativeHandle(
    ref,
    (): HaritaApi => ({
      flyTo: (hedef, sureMs, secenek) => ucus(hedef, sureMs, secenek),
      orbit: (d = 3) => {
        surucu.orbit(d);
        mesgulBildir(surucu.mesgulMu());
      },
      durdur: () => {
        surucu.durdur();
        mesgulBildir(false);
      },
      sigdirHesapla: (kutu, o = {}) =>
        fitBounds(kutu, {
          ...boyutRef.current,
          padding: o.padding,
          pitch: o.pitch ?? gorunumRef.current.pitch,
          bearing: o.bearing ?? gorunumRef.current.bearing,
          maxZoom: o.maksZoom,
        }),
      fitBounds: (kutu, o = {}) =>
        ucus(
          fitBounds(kutu, {
            ...boyutRef.current,
            padding: o.padding,
            pitch: o.pitch ?? gorunumRef.current.pitch,
            bearing: o.bearing ?? gorunumRef.current.bearing,
            maxZoom: o.maksZoom,
          }),
          o.sureMs ?? 2000,
          o.secenek ?? {},
        ),
      kamera: () => ({ ...gorunumRef.current }),
      kameraAyarla: (k) => {
        surucu.durdur();
        mesgulBildir(false);
        kameraYaz({ ...gorunumRef.current, ...k });
      },
      boyut: () => ({ ...boyutRef.current }),
      yansit: (konum) => {
        const vp = new WebMercatorViewport({ ...gorunumRef.current, ...boyutRef.current });
        const p = vp.project(konum as number[]);
        return [p[0], p[1]];
      },
      mesgulMu: () => surucu.mesgulMu(),
      deck: () => deckRef.current?.deck ?? null,
    }),
    [surucu, ucus, kameraYaz, mesgulBildir],
  );

  /* ---------------------------------------------------------------- deck props */
  const efektler = useMemo(() => (isik ? [isikEfekti(isik)] : []), [isik]);
  const katmanListesi = typeof katmanlar === 'function' ? katmanlar(t) : katmanlar;

  const gorunumDegisti = useCallback(
    ({ viewState, interactionState }: { viewState: Record<string, number>; interactionState?: { isDragging?: boolean; isZooming?: boolean; isRotating?: boolean } }) => {
      if (interactionState && (interactionState.isDragging || interactionState.isZooming || interactionState.isRotating)) {
        surucu.etkilesim();
        mesgulBildir(false);
      }
      const vs: KameraDurumu = {
        longitude: viewState.longitude,
        latitude: viewState.latitude,
        zoom: viewState.zoom,
        pitch: viewState.pitch ?? 0,
        bearing: viewState.bearing ?? 0,
      };
      gorunumRef.current = vs;
      setGorunum(vs);
      onKameraRef.current?.(vs);
    },
    [surucu, mesgulBildir],
  );

  const ilkKareBildir = useCallback(() => {
    if (ilkKareBildirildi.current) return;
    ilkKareBildirildi.current = true;
    onIlkKareRef.current?.();
  }, []);

  const kareBitti = useCallback(() => {
    if (ilkKareBildirildi.current) return;
    if (++kareSayaci.current < 2) return;
    ilkKareBildir();
  }, [ilkKareBildir]);

  // Emniyet ağı: deck.gl tek kare çizip durursa (tamamen durağan sahne) QA sonsuza kadar bekler.
  useEffect(() => {
    const t1 = setTimeout(() => {
      if (kareSayaci.current >= 1) ilkKareBildir();
    }, 3000);
    const t2 = setTimeout(ilkKareBildir, 8000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [ilkKareBildir]);

  // Tanımsız (undefined) prop'lar deck.gl'in kendi varsayılanını EZER (getCursor undefined → çizim hatası),
  // bu yüzden yalnız gerçekten verilen geri çağrılar aktarılır.
  const secmeliPropslar: Record<string, unknown> = {};
  if (onHover) secmeliPropslar.onHover = onHover;
  if (onClick) secmeliPropslar.onClick = onClick;
  if (getTooltip) secmeliPropslar.getTooltip = getTooltip;
  if (getCursor) secmeliPropslar.getCursor = getCursor;

  return (
    <div ref={kapsayici} style={{ position: 'absolute', inset: 0, background: '#03060D', ...style }}>
      <DeckGL
        ref={deckRef as never}
        layers={katmanListesi}
        effects={efektler}
        viewState={gorunum as never}
        onViewStateChange={gorunumDegisti as never}
        controller={(etkilesim === true ? { dragRotate: true, inertia: 300, maxPitch: 70 } : etkilesim) as never}
        width={boyut.width}
        height={boyut.height}
        pickingRadius={pickingRadius}
        useDevicePixels={1}
        deviceProps={{ type: 'webgl', webgl: { preserveDrawingBuffer: true } } as never}
        {...secmeliPropslar}
        onAfterRender={kareBitti}
        onError={(e: Error) => console.error('[deck]', e)}
      />
      {children}
    </div>
  );
});

export default HaritaSahnesi;
