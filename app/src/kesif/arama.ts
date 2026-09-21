/**
 * Keşif araması — Türkçe duyarsız, mahalle / site / bina girdileri.
 *
 * Dizin ilk odaklanmada bir kez kurulur (~20 ms, 19.706 bina üzerinde tek geçiş):
 *  - **Mahalle** girdileri (ilçe, mahalle) ÇİFTİ ile anahtarlanır — aynı mahalle adı
 *    birden çok ilçede geçebilir (meta.mahalle_sayisi = 165 bu çiftleri sayar).
 *  - **Birim** girdileri site-grubu (`S:İlçe|Mahalle|SITE#k`) ya da tek bina (`B:<serial>`).
 *    Aynı "A BLOK" adı şehrin her yerinde geçtiği için gruplama ada göre değil birime göredir.
 *  - Adsız binalar dizine girmez; onlara mahalle girdisinden ya da seri no ile ulaşılır.
 */
import { veri } from '../data/load';
import { temizAd } from '../data/selectors';
import type { LonLat } from '../data/types';

export type SonucTuru = 'mahalle' | 'site' | 'bina';

export interface AramaSonucu {
  anahtar: string;
  tur: SonucTuru;
  /** görünen ad */
  ad: string;
  /** alt satır: "Görükle · Nilüfer · 12 bina" */
  yer: string;
  bina: number;
  resHp: number;
  firsat: number;
  indeksler: number[];
  /** temsil eden bina (renk noktası, uçuş) */
  ilkIndeks: number;
  merkez: LonLat;
  puan: number;
}

interface Girdi {
  anahtar: string;
  tur: SonucTuru;
  ad: string;
  yer: string;
  /** sadeleştirilmiş ad */
  adSade: string;
  /** sadeleştirilmiş ad + mahalle + ilçe */
  saman: string;
  bina: number;
  resHp: number;
  firsat: number;
  indeksler: number[];
  merkez: LonLat;
}

/**
 * Türkçe duyarsız sadeleştirme:
 * "IŞIK" / "ışık" / "Işık" → "isik";  "Güzelyalı Eğitim" → "guzelyali egitim"
 */
export function sadelestir(s: string): string {
  return s
    .toLocaleLowerCase('tr-TR')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/ı/g, 'i')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

let _dizin: Girdi[] | null = null;

function dizin(): Girdi[] {
  if (_dizin) return _dizin;
  const v = veri();
  const b = v.binalar;
  const p = b.paket;
  const { mahalle: sMahalle, ilce: sIlce, ad: sAd, birim: sBirim } = p.sozluk;

  interface Yigin {
    ad: string;
    ilce: string;
    mahalle: string;
    resHp: number;
    firsat: number;
    lon: number;
    lat: number;
    indeksler: number[];
  }
  const yeni = (): Yigin => ({ ad: '', ilce: '', mahalle: '', resHp: 0, firsat: 0, lon: 0, lat: 0, indeksler: [] });

  const mahalleler = new Map<number, Yigin>();
  const birimler = new Map<number, Yigin>();

  for (let i = 0; i < b.n; i++) {
    const mi = b.mahalle[i];
    const ii = b.ilce[i];
    // (ilçe, mahalle) çifti — aynı mahalle adı birden çok ilçede olabilir
    const mAnahtar = ii * 100000 + mi;
    let m = mahalleler.get(mAnahtar);
    if (!m) {
      m = yeni();
      m.mahalle = sMahalle[mi] ?? '';
      m.ilce = sIlce[ii] ?? '';
      mahalleler.set(mAnahtar, m);
    }
    const bi = b.birim[i];
    let g = birimler.get(bi);
    if (!g) {
      g = yeni();
      g.mahalle = sMahalle[mi] ?? '';
      g.ilce = sIlce[ii] ?? '';
      birimler.set(bi, g);
    }
    const ad = temizAd(sAd[p.ad[i]]);
    if (ad && !g.ad) g.ad = ad;
    for (const y of [m, g]) {
      y.resHp += b.resHp[i];
      y.firsat += b.firsat[i];
      y.lon += b.lon[i];
      y.lat += b.lat[i];
      y.indeksler.push(i);
    }
  }

  const out: Girdi[] = [];
  const girdiYap = (anahtar: string, tur: SonucTuru, ad: string, y: Yigin, yer: string): Girdi => ({
    anahtar,
    tur,
    ad,
    yer,
    adSade: sadelestir(ad),
    saman: sadelestir(`${ad} ${y.mahalle} ${y.ilce}`),
    bina: y.indeksler.length,
    resHp: y.resHp,
    firsat: y.firsat,
    indeksler: y.indeksler,
    merkez: [y.lon / y.indeksler.length, y.lat / y.indeksler.length],
  });

  for (const [k, y] of mahalleler) {
    out.push(girdiYap(`m${k}`, 'mahalle', y.mahalle, y, `${y.ilce} · ${y.indeksler.length} bina`));
  }
  for (const [k, y] of birimler) {
    if (!y.ad) continue; // adsız birim: mahalle ya da seri no ile bulunur
    const site = (sBirim[k] ?? '').startsWith('S:') && y.indeksler.length > 1;
    out.push(
      girdiYap(
        `b${k}`,
        site ? 'site' : 'bina',
        y.ad,
        y,
        site ? `${y.mahalle} · ${y.ilce} · ${y.indeksler.length} bina` : `${y.mahalle} · ${y.ilce}`,
      ),
    );
  }
  _dizin = out;
  return out;
}

/** Dizini önceden kurar (arama kutusuna ilk odaklanmada çağrılır). */
export function dizinHazirla(): void {
  dizin();
}

function puanla(g: Girdi, sorgu: string, parcalar: string[]): number {
  let p = 0;
  if (g.adSade.startsWith(sorgu)) p += 100;
  else if (g.adSade.includes(' ' + sorgu)) p += 55;
  for (const t of parcalar) {
    if (g.saman.startsWith(t) || g.saman.includes(' ' + t)) p += 40;
    else if (g.saman.includes(t)) p += 10;
    else return -1; // her parça eşleşmeli (VE)
  }
  if (g.tur === 'mahalle') p += 15;
  return p;
}

/** Seri no araması: sorguda 4+ rakam varsa bina seri numaralarında arar. */
function seriAra(sorgu: string, limit: number): AramaSonucu[] {
  const rakam = sorgu.replace(/\D+/g, '');
  if (rakam.length < 4) return [];
  const v = veri();
  const b = v.binalar;
  const p = b.paket;
  const out: AramaSonucu[] = [];
  for (let i = 0; i < b.n && out.length < limit; i++) {
    const s = p.serial[i];
    if (!s.includes(rakam)) continue;
    const ad = temizAd(p.sozluk.ad[p.ad[i]]);
    out.push({
      anahtar: `s${i}`,
      tur: 'bina',
      ad: ad || `Adsız bina · ${s}`,
      yer: `${p.sozluk.mahalle[b.mahalle[i]]} · ${p.sozluk.ilce[b.ilce[i]]} · ${s}`,
      bina: 1,
      resHp: b.resHp[i],
      firsat: b.firsat[i],
      indeksler: [i],
      ilkIndeks: i,
      merkez: [b.lon[i], b.lat[i]],
      puan: 90,
    });
  }
  return out;
}

/** En iyi `limit` sonucu döndürür (puan, sonra RES HP). */
export function ara(metin: string, limit = 8): AramaSonucu[] {
  const sorgu = sadelestir(metin);
  if (sorgu.length < 2) return [];
  const parcalar = sorgu.split(' ').filter(Boolean);
  const seri = seriAra(metin, limit);
  const bulunan: { g: Girdi; puan: number }[] = [];
  for (const g of dizin()) {
    const p = puanla(g, sorgu, parcalar);
    if (p >= 0) bulunan.push({ g, puan: p });
  }
  bulunan.sort((a, z) => z.puan - a.puan || z.g.resHp - a.g.resHp);
  const out: AramaSonucu[] = seri.slice(0, 2);
  const gorulen = new Set(out.map((o) => o.anahtar));
  for (const { g, puan } of bulunan) {
    if (out.length >= limit) break;
    if (gorulen.has(g.anahtar)) continue;
    gorulen.add(g.anahtar);
    out.push({
      anahtar: g.anahtar,
      tur: g.tur,
      ad: g.ad,
      yer: g.yer,
      bina: g.bina,
      resHp: g.resHp,
      firsat: g.firsat,
      indeksler: g.indeksler,
      ilkIndeks: g.indeksler[0],
      merkez: g.merkez,
      puan,
    });
  }
  return out;
}

/** `?bina=` parametresi: seri no ya da 0 tabanlı indeks → bina indeksi. */
export function binaCoz(anahtar: string): number | null {
  const v = veri();
  const b = v.binalar;
  const t = anahtar.trim();
  if (/^\d+$/.test(t)) {
    const i = Number(t);
    if (i >= 0 && i < b.n) return i;
  }
  const seri = b.paket.serial;
  const sade = t.toUpperCase();
  for (let i = 0; i < b.n; i++) if (seri[i].toUpperCase() === sade) return i;
  for (let i = 0; i < b.n; i++) if (seri[i].includes(t)) return i;
  return null;
}
