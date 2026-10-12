/**
 * MAP arama motoru: tek kutudaki metin (Task No, müşteri no, müşteri adı, Location ID, BN/bina/site adı)
 * önce yüklü açık işlerde (anında), sonra sunucuda (GET /api/ara: iş + bina grubu) aranır ve birleştirilir.
 * Location ID ve BN yalnız sunucuda var (iş satırında yok); izin süzgeci sunucudadır.
 * Giriş: useKonumArama(sorgu, isler, harita) · yakinIsler(isler, konum). Çağıranlar: map/KonumAra.tsx, map/SecimKarti.tsx.
 */

import { useEffect, useMemo, useState } from 'react';
import { ara, type AramaSonucu } from '../../../../cekirdek/arama/api';
import { katla } from '../../../../cekirdek/ortak/ara';
import { DURUM_ETIKET, type IsSatir } from '../../../../cekirdek/is/tipler';
import { KAPALI_DURUM, type Konum } from './noktalar';

export interface BulunanIs {
  tur: 'is';
  anahtar: string;
  isNo: string;
  baslik: string;
  alt: string;
  konum: Konum | null;
  /** Açık iş mi (kapalı işler yalnız sunucudan gelir; konum tespiti için). */
  acik: boolean;
  /** Haritaya yüklü açık işlerden mi (nokta olarak çizilebilir). */
  yuklu: boolean;
}

export interface BulunanBina {
  tur: 'bina';
  anahtar: string;
  serial: string;
  ad: string;
  loc: string | null;
  alt: string;
  konum: Konum;
}

export type Bulunan = BulunanIs | BulunanBina;

export interface AramaSonuclari {
  isler: BulunanIs[];
  binalar: BulunanBina[];
  /** Location ID / BN birebir tuttu: binalar listede önce gelir. */
  binaOnce: boolean;
  /** Yüklü işlerde Task No / müşteri no birebir tuttu: Enter sunucuyu beklemeden ilk sonuca gider. */
  kesin: boolean;
  /** Sunucu yanıtı bekleniyor. */
  bekliyor: boolean;
  /** Sunucuya sorulamadı (yalnız yüklü işlerde arandı). */
  uyari: string | null;
}

const EN_KISA = 2;
const EN_FAZLA = 40;
const BEKLEME_MS = 300;

const sik = (s: unknown) => katla(s).replace(/[^a-z0-9]+/g, '');

/** Yüklü işte puan: no tam > müşteri no tam > no önek > müşteri no önek > ad kelime başı > ad/adres içerir. */
function puanla(s: IsSatir, q: string, qa: string): number {
  const nolar = [sik(s.boss_task_no), sik(s.is_no)].filter(Boolean);
  const mno = sik(s.musteri_no);
  if (nolar.includes(q)) return 100;
  if (mno && mno === q) return 95;
  if (q.length >= 3 && nolar.some((n) => n.startsWith(q))) return 80;
  if (q.length >= 3 && mno.startsWith(q)) return 75;
  const ad = katla(s.musteri_adi).trim();
  if (ad && (ad.startsWith(qa) || ad.includes(` ${qa}`))) return 60;
  if (q.length >= 3 && ad && sik(ad).includes(q)) return 45;
  if (q.length >= 3 && sik(s.kisa_adres).includes(q)) return 40;
  if (q.length >= 4 && nolar.some((n) => n.includes(q))) return 35;
  return 0;
}

function konumOf(lat: unknown, lon: unknown): Konum | null {
  return typeof lat === 'number' && typeof lon === 'number' ? [lon, lat] : null;
}

/** Yüklü iş satırından liste öğesi. Müşteri adı yalnız izinliyse satırda gelir. */
function satirdan(s: IsSatir): BulunanIs {
  const no = s.boss_task_no || s.is_no;
  const ad = s.musteri_adi?.trim();
  return {
    tur: 'is',
    anahtar: `is:${s.is_no}`,
    isNo: s.is_no,
    baslik: ad || s.task_adi || no,
    alt: [ad ? s.task_adi : null, no, DURUM_ETIKET[s.durum], s.kisa_adres || s.mahalle].filter(Boolean).join(' · '),
    konum: konumOf(s.lat, s.lon),
    acik: !KAPALI_DURUM.has(s.durum),
    yuklu: true,
  };
}

function sunucuIsi(r: AramaSonucu): BulunanIs | null {
  const no = String(r.is_no ?? r.id ?? '');
  if (!no) return null;
  return {
    tur: 'is',
    anahtar: `is:${no}`,
    isNo: no,
    baslik: r.baslik || no,
    alt: r.alt ?? '',
    konum: konumOf(r.lat, r.lon),
    acik: r.acik !== false,
    yuklu: false,
  };
}

function sunucuBinasi(r: AramaSonucu): BulunanBina | null {
  const konum = konumOf(r.lat, r.lon);
  const serial = String(r.serial ?? r.id ?? '');
  if (!konum || !serial) return null;
  return {
    tur: 'bina',
    anahtar: `bina:${serial}`,
    serial,
    ad: r.baslik || serial,
    loc: r.location_id ? String(r.location_id) : null,
    alt: r.alt ?? '',
    konum,
  };
}

/** Yüklü işlerde arama (anında, sunucusuz): en iyi eşleşme önce, eşitlikte eski iş önce. */
function yerelIsAra(isler: readonly IsSatir[], sorgu: string): Array<{ puan: number; satir: IsSatir }> {
  const q = sik(sorgu);
  if (q.length < EN_KISA) return [];
  const qa = katla(sorgu).trim().replace(/\s+/g, ' ');
  const puanli: Array<{ puan: number; satir: IsSatir }> = [];
  for (const satir of isler) {
    const puan = puanla(satir, q, qa);
    if (puan) puanli.push({ puan, satir });
  }
  puanli.sort((a, b) => b.puan - a.puan || String(a.satir.acilis).localeCompare(String(b.satir.acilis)));
  return puanli.slice(0, EN_FAZLA);
}

/** Bir konuma `metre` içindeki yüklü işler (bina kartında "Bu binadaki işler"). */
export function yakinIsler(isler: readonly IsSatir[], konum: Konum, metre = 30): IsSatir[] {
  const kos = Math.cos((konum[1] * Math.PI) / 180);
  return isler.filter((s) => {
    if (s.lat === null || s.lon === null || KAPALI_DURUM.has(s.durum)) return false;
    const dx = (s.lon - konum[0]) * 111320 * kos;
    const dy = (s.lat - konum[1]) * 111320;
    return dx * dx + dy * dy <= metre * metre;
  });
}

interface SunucuYaniti {
  q: string;
  isler: AramaSonucu[];
  binalar: AramaSonucu[];
  uyari: string | null;
}

/**
 * Kutudaki metin için sonuçlar. Yüklü işler anında; sunucu (iş + bina) kısa beklemeyle sorulur.
 * Sunucudan gelen iş yüklüyse yüklü satırla gösterilir (haritadaki noktası vurgulanabilsin).
 */
export function useKonumArama(sorgu: string, isler: readonly IsSatir[], harita: ReadonlyMap<string, IsSatir>): AramaSonuclari {
  const q = sorgu.trim();
  const yeterli = sik(q).length >= EN_KISA;
  const yerel = useMemo(() => (yeterli ? yerelIsAra(isler, q) : []), [isler, q, yeterli]);
  const [sunucu, setSunucu] = useState<SunucuYaniti | null>(null);

  useEffect(() => {
    if (!yeterli) return undefined;
    const denetim = new AbortController();
    const zaman = window.setTimeout(() => {
      void Promise.allSettled([ara(q, 'is', denetim.signal), ara(q, 'bina', denetim.signal)]).then(([i, b]) => {
        if (denetim.signal.aborted) return;
        const grup = (r: typeof i, tur: 'is' | 'bina') =>
          r.status === 'fulfilled' ? (r.value.gruplar.find((g) => g.tur === tur)?.sonuclar ?? []) : [];
        setSunucu({
          q,
          isler: grup(i, 'is'),
          binalar: grup(b, 'bina'),
          uyari:
            i.status === 'rejected' && b.status === 'rejected'
              ? 'Sunucuya sorulamadı; yalnız haritadaki işlerde arandı.'
              : null,
        });
      });
    }, BEKLEME_MS);
    return () => {
      window.clearTimeout(zaman);
      denetim.abort();
    };
  }, [q, yeterli]);

  const guncel = sunucu && sunucu.q === q ? sunucu : null;

  return useMemo(() => {
    const isSonuc: BulunanIs[] = yerel.map((y) => satirdan(y.satir));
    const gorulen = new Set(isSonuc.map((b) => b.isNo));
    for (const r of guncel?.isler ?? []) {
      const b = sunucuIsi(r);
      if (!b || gorulen.has(b.isNo)) continue;
      gorulen.add(b.isNo);
      const satir = harita.get(b.isNo);
      isSonuc.push(satir ? satirdan(satir) : b);
    }
    const binalar: BulunanBina[] = [];
    const binaGorulen = new Set<string>();
    for (const r of guncel?.binalar ?? []) {
      const b = sunucuBinasi(r);
      if (!b || binaGorulen.has(b.serial)) continue;
      binaGorulen.add(b.serial);
      binalar.push(b);
    }
    const qs = sik(q);
    const binaOnce = binalar.some((b) => sik(b.loc) === qs || sik(b.serial) === qs);
    return {
      isler: isSonuc.slice(0, EN_FAZLA),
      binalar,
      binaOnce,
      kesin: (yerel[0]?.puan ?? 0) >= 95,
      bekliyor: yeterli && !guncel,
      uyari: guncel?.uyari ?? null,
    };
  }, [yerel, guncel, harita, q, yeterli]);
}
