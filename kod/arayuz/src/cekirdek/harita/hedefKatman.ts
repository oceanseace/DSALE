/**
 * Haritada hedef: eşleştirme, sunucuya sorma, kamera uçuşu, iğne + halka.
 * Yalnız haritalar içe aktarır (deck.gl burada; ana pakete girmez).
 */

import { useEffect, useState } from 'react';
import { FlyToInterpolator, type MapViewState } from '@deck.gl/core';
import { ScatterplotLayer } from '@deck.gl/layers';
import { katla } from '../ortak/ara';
import { istek } from '../api/istemci';
import type { HaritaHedefi } from './hedef';

/* ------------------------------ Eşleştirme ------------------------------ */

export interface AranirNokta {
  serial: string;
  ad?: string;
  loc?: string;
  konum: [number, number];
}

const sik = (s: unknown) => katla(s).replace(/[^a-z0-9]+/g, '');

/**
 * Haritadaki noktalar içinde sorguya en iyi uyan(lar): Location ID tam > seri tam >
 * Location ID önek > seri önek > ad kelime başı > ad içerir. Türkçe harf duyarsız.
 */
export function noktaAra<T extends AranirNokta>(noktalar: readonly T[], sorgu: string, enFazla = 6): T[] {
  const q = sik(sorgu);
  if (q.length < 2) return [];
  const qa = katla(sorgu).trim();
  const puanli: Array<[number, T]> = [];
  for (const n of noktalar) {
    const loc = sik(n.loc);
    const ser = sik(n.serial);
    let p = 0;
    if (loc && loc === q) p = 100;
    else if (ser === q) p = 95;
    else if (loc && loc.startsWith(q)) p = 80;
    else if (ser.startsWith(q)) p = 75;
    else if (n.ad) {
      const ad = katla(n.ad);
      if (ad.startsWith(qa) || ad.includes(' ' + qa)) p = 60;
      else if (q.length >= 3 && sik(n.ad).includes(q)) p = 40;
    }
    if (p) puanli.push([p, n]);
  }
  puanli.sort((a, b) => b[0] - a[0] || String(a[1].ad ?? '').localeCompare(String(b[1].ad ?? ''), 'tr'));
  return puanli.slice(0, enFazla).map((x) => x[1]);
}

/** Haritada bulunamazsa sunucuya sor (yetki süzgeci orada): ilk bina sonucu. */
export async function sunucudaBul(sorgu: string, isaret?: AbortSignal): Promise<HaritaHedefi | null> {
  const y = await istek<{ gruplar: Array<{ tur: string; sonuclar: Array<Record<string, unknown>> }> }>(
    `/api/ara?tur=bina&q=${encodeURIComponent(sorgu)}`,
    { isaret, zamanAsimiMs: 8000 },
  );
  const s = y.gruplar.find((g) => g.tur === 'bina')?.sonuclar[0];
  if (!s || typeof s.lat !== 'number' || typeof s.lon !== 'number') return null;
  return {
    serial: String(s.serial ?? s.id ?? ''),
    loc: (s.location_id as string) || undefined,
    lat: s.lat,
    lon: s.lon,
    etiket: String(s.baslik ?? ''),
  };
}

/* ------------------------------ Kamera ve vurgu ------------------------------ */

/** Kameranın hedefe yumuşak uçuşu (deck.gl FlyTo). Eğik/döndürülmüş kamera korunur. */
export function ucusGorunumu(g: MapViewState | null, konum: [number, number], zoom = 17): MapViewState {
  return {
    ...(g ?? { pitch: 0, bearing: 0 }),
    longitude: konum[0],
    latitude: konum[1],
    zoom: Math.max(zoom, Math.min(g?.zoom ?? zoom, 19)),
    transitionDuration: 'auto',
    transitionInterpolator: new FlyToInterpolator({ speed: 1.6 }),
  } as MapViewState;
}

/**
 * Vurgu için kısa ömürlü nabız: 0→1 (≈2,4 s, üç atım), sonra 1'de durur.
 * `anahtar` değişince yeniden başlar. Hareket azaltma tercihinde hiç atmaz.
 */
export function useNabiz(anahtar: string | null): number {
  const [faz, setFaz] = useState(1);
  useEffect(() => {
    if (!anahtar) return undefined;
    let azalt = false;
    try {
      azalt = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
      /* yok sayılır */
    }
    if (azalt) {
      setFaz(1);
      return undefined;
    }
    const bas = performance.now();
    const SURE = 2400;
    let kare = 0;
    const adim = (t: number) => {
      const f = Math.min(1, (t - bas) / SURE);
      setFaz(f);
      if (f < 1) kare = requestAnimationFrame(adim);
    };
    kare = requestAnimationFrame(adim);
    return () => cancelAnimationFrame(kare);
  }, [anahtar]);
  return faz;
}

const USTTE = { depthCompare: 'always', depthWriteEnabled: false } as const;

/**
 * İğne (sarı, koyu çerçeve) + genişleyip sönen halka. `faz` = useNabiz.
 * `kayma` (piksel): nokta ekranda yana kaydırılmışsa (aynı binadaki işler) iğne de onun üstüne oturur.
 */
export function hedefKatmanlari(
  konum: [number, number] | null,
  faz: number,
  kimlik = 'arama-hedef',
  kayma: [number, number] = [0, 0],
): unknown[] {
  if (!konum) return [];
  const atim = (faz * 3) % 1; // üç atım
  const halkaAlfa = faz >= 1 ? 110 : Math.round(230 * (1 - atim));
  const halkaYaricap = faz >= 1 ? 26 : 14 + atim * 46;
  return [
    new ScatterplotLayer({
      id: `${kimlik}-halka`,
      data: [{ konum }],
      getPosition: (d: { konum: [number, number] }) => d.konum,
      getPixelOffset: kayma,
      filled: faz < 1,
      getFillColor: [254, 198, 0, Math.round(halkaAlfa * 0.25)],
      stroked: true,
      getLineColor: [254, 198, 0, halkaAlfa],
      lineWidthMinPixels: 3,
      getRadius: halkaYaricap,
      radiusUnits: 'pixels',
      pickable: false,
      parameters: USTTE,
      updateTriggers: { getRadius: halkaYaricap, getLineColor: halkaAlfa, getFillColor: halkaAlfa },
    }),
    new ScatterplotLayer({
      id: `${kimlik}-igne`,
      data: [{ konum }],
      getPosition: (d: { konum: [number, number] }) => d.konum,
      getPixelOffset: kayma,
      getFillColor: [254, 198, 0, 255],
      stroked: true,
      getLineColor: [16, 24, 40, 255],
      lineWidthMinPixels: 3,
      getRadius: 9,
      radiusUnits: 'pixels',
      pickable: false,
      parameters: USTTE,
    }),
  ];
}

/* ------------------------------ Haritaya bağlama ------------------------------ */

export interface HedefDurumu {
  /** Vurgulanan nokta (iğne + halka); yoksa null. */
  konum: [number, number] | null;
  /** Nabız fazı (hedefKatmanlari'na verilir). */
  faz: number;
  /** "… bulunamadı" — birkaç saniye görünür. */
  uyari: string | null;
  /** Kutudan ya da paletten gelen yeni hedef. */
  git: (h: HaritaHedefi) => void;
  temizle: () => void;
}

/**
 * Hedefi haritaya uygular: noktayı bulur (önce haritadaki noktalar, yoksa sunucu),
 * kamerayı uçurur, varsa noktayı seçer (kart açılır), iğne + halka bırakır.
 * Bulunamazsa nazik uyarı. Paletten/adresten gelen hedef `gelen` ile verilir.
 */
export function useHedefeUc<T extends AranirNokta>({
  gelen,
  tuket,
  noktalar,
  sec,
  setGorunum,
}: {
  gelen: HaritaHedefi | null;
  tuket: () => void;
  noktalar: readonly T[];
  sec?: (n: T) => void;
  setGorunum: (f: (g: MapViewState | null) => MapViewState | null) => void;
}): HedefDurumu {
  const [konum, setKonum] = useState<[number, number] | null>(null);
  const [uyari, setUyari] = useState<string | null>(null);
  const [istek_, setIstek] = useState<{ h: HaritaHedefi; no: number } | null>(null);
  const faz = useNabiz(konum ? `${konum[0]},${konum[1]},${istek_?.no ?? 0}` : null);
  const hazir = noktalar.length > 0;

  /* Paletten / adresten gelen hedef. */
  useEffect(() => {
    if (!gelen) return;
    setIstek((o) => ({ h: gelen, no: (o?.no ?? 0) + 1 }));
    tuket();
  }, [gelen, tuket]);

  useEffect(() => {
    if (!istek_) return undefined;
    const { h } = istek_;
    // Konumu belli olmayan aramada noktalar gelmeden karar verilmez.
    if (!hazir && (h.lat == null || h.lon == null)) return undefined;
    let iptal = false;
    const denetleyici = new AbortController();
    const uygula = (k: [number, number], nokta: T | undefined) => {
      if (iptal) return;
      setUyari(null);
      setKonum(k);
      if (nokta && sec) sec(nokta);
      setGorunum((g) => ucusGorunumu(g, k));
    };
    const bySerial = h.serial ? noktalar.find((n) => n.serial === h.serial) : undefined;
    if (h.lat != null && h.lon != null) {
      uygula(bySerial?.konum ?? [h.lon, h.lat], bySerial);
    } else if (bySerial) {
      uygula(bySerial.konum, bySerial);
    } else {
      const sorgu = (h.sorgu ?? h.loc ?? '').trim();
      const yerel = sorgu ? noktaAra(noktalar, sorgu, 1)[0] : undefined;
      if (yerel) uygula(yerel.konum, yerel);
      else if (sorgu) {
        sunucudaBul(sorgu, denetleyici.signal)
          .then((s) => {
            if (iptal) return;
            if (s && s.lat != null && s.lon != null) {
              const n = s.serial ? noktalar.find((x) => x.serial === s.serial) : undefined;
              uygula(n?.konum ?? [s.lon, s.lat], n);
            } else setUyari(`“${sorgu}” bulunamadı. Location ID’yi, BN’yi ya da site adını kontrol edin.`);
          })
          .catch(() => {
            if (!iptal) setUyari(`“${sorgu}” bu haritada yok; bağlantı olmadığı için sunucuya da sorulamadı.`);
          });
      }
    }
    return () => {
      iptal = true;
      denetleyici.abort();
    };
    // noktalar yalnız ilk gelişte önemli (hazir); her filtrede yeniden uçmasın.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [istek_, hazir]);

  /* Uyarı kendiliğinden söner. */
  useEffect(() => {
    if (!uyari) return undefined;
    const z = setTimeout(() => setUyari(null), 4200);
    return () => clearTimeout(z);
  }, [uyari]);

  return {
    konum,
    faz,
    uyari,
    git: (h) => setIstek((o) => ({ h, no: (o?.no ?? 0) + 1 })),
    temizle: () => {
      setKonum(null);
      setUyari(null);
    },
  };
}
