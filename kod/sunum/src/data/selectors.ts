/**
 * Seçiciler (türetilmiş değerler), renk yardımcıları ve Türkçe sayı biçimlendiriciler.
 */
import { binaBolgeleri, planGetir, planNleri, planVeyaVarsayilan, veri } from './load';
import type { Bolge, LonLat, Plan, Toplamlar } from './types';

/* ================================================================== renk */

export type RGB = [number, number, number];
export type RGBA = [number, number, number, number];

/** "#FFC400" | "#FC0" → [255,196,0,a] (a 0..255) */
export function hexRgba(hex: string, alfa = 255): RGBA {
  let h = hex.replace('#', '').trim();
  if (h.length === 3) h = h.split('').map((c) => c + c).join('');
  const v = parseInt(h.slice(0, 6), 16);
  const a = h.length === 8 ? parseInt(h.slice(6, 8), 16) : alfa;
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255, a];
}

/** "#FFC400" → [255,196,0] */
export function hexRgb(hex: string): RGB {
  const [r, g, b] = hexRgba(hex);
  return [r, g, b];
}

/** CSS rgba() dizesi: rgbaCss("#FFC400", 0.4) → "rgba(255,196,0,0.4)" */
export function rgbaCss(hex: string, alfa = 1): string {
  const [r, g, b] = hexRgba(hex);
  return `rgba(${r},${g},${b},${alfa})`;
}

/** Rengi beyaza (t>0) ya da siyaha (t<0) doğru karıştırır. */
export function tonla([r, g, b, a = 255]: number[], t: number): RGBA {
  const k = t >= 0 ? 255 : 0;
  const u = Math.abs(t);
  return [r + (k - r) * u, g + (k - g) * u, b + (k - b) * u, a] as RGBA;
}

/** İki renk arası doğrusal karışım (0..1). */
export function karistir(a: number[], b: number[], t: number): RGBA {
  return [0, 1, 2, 3].map((i) => (a[i] ?? 255) + ((b[i] ?? 255) - (a[i] ?? 255)) * t) as RGBA;
}

/** Plan bölgelerinin renkleri; indeks = bölge no (0. eleman nötr gri). */
export function bolgeRenkTablosu(plan: Plan, alfa = 255): RGBA[] {
  const t: RGBA[] = [[90, 100, 120, alfa]];
  for (const b of plan.bolgeler) t[b.bolge] = hexRgba(b.renk, alfa);
  for (let i = 1; i < t.length; i++) if (!t[i]) t[i] = [90, 100, 120, alfa];
  return t;
}

/* ================================================================== toplamlar & bölgeler */

/** Genel toplamlar (meta.toplam): bina 19.706, res_hp 296.778, aktif_res 108.491, firsat 189.272 … */
export function toplamlar(): Toplamlar {
  return veri().meta.toplam;
}

/** Plan bölgesini numarasıyla bulur. */
export function bolgeBul(plan: Plan, no: number): Bolge | undefined {
  return plan.bolgeler.find((b) => b.bolge === no);
}

/** i. binanın bölge numarası (1..N). */
export function binaBolgesi(plan: Plan, i: number): number {
  return binaBolgeleri(plan)[i];
}

/** i. binanın okunur bilgisi (ipucu/tooltip için). */
export interface BinaBilgisi {
  i: number;
  serial: string;
  ad: string;
  ilce: string;
  il: string;
  mahalle: string;
  kat: number;
  toplamHp: number;
  resHp: number;
  aktif: number;
  firsat: number;
  konum: LonLat;
  bolge: number;
}

/** Veri paketindeki yer tutucu adları ('Null', boş) temizler. */
export function temizAd(s: string | undefined | null): string {
  const t = (s ?? '').trim();
  return !t || t.toLowerCase() === 'null' ? '' : t;
}

export function binaBilgisi(i: number, plan?: Plan): BinaBilgisi {
  const b = veri().binalar;
  const p = b.paket;
  const pl = plan ?? planVeyaVarsayilan(null);
  return {
    i,
    serial: p.serial[i],
    ad: temizAd(p.sozluk.ad[p.ad[i]]),
    ilce: p.sozluk.ilce[p.ilce[i]] ?? '',
    il: p.sozluk.il[p.il[i]] ?? '',
    mahalle: p.sozluk.mahalle[p.mahalle[i]] ?? '',
    kat: b.kat[i],
    toplamHp: b.toplamHp[i],
    resHp: b.resHp[i],
    aktif: b.aktif[i],
    firsat: b.firsat[i],
    konum: [b.lon[i], b.lat[i]],
    bolge: binaBolgeleri(pl)[i],
  };
}

/** Bina metrikleri (renk ölçekleri ve sütunlar için). */
export type BinaMetrigi = 'res_hp' | 'firsat' | 'aktif' | 'toplam_hp' | 'kat' | 'penetrasyon';

/** i. binanın metrik değeri. */
export function binaMetrigi(m: BinaMetrigi): (i: number) => number {
  const b = veri().binalar;
  switch (m) {
    case 'res_hp':
      return (i) => b.resHp[i];
    case 'firsat':
      return (i) => b.firsat[i];
    case 'aktif':
      return (i) => b.aktif[i];
    case 'toplam_hp':
      return (i) => b.toplamHp[i];
    case 'kat':
      return (i) => b.kat[i];
    case 'penetrasyon':
      return (i) => (b.resHp[i] > 0 ? Math.min(1, b.aktif[i] / b.resHp[i]) : 0);
  }
}

/** Plan bölgelerinin sınır kutusu [[minLon,minLat],[maxLon,maxLat]] (seçili bölgeler ya da tümü). */
export function bolgeSinirKutusu(plan: Plan, bolgeler?: number[]): [LonLat, LonLat] {
  const b = veri().binalar;
  const bb = binaBolgeleri(plan);
  const sec = bolgeler ? new Set(bolgeler) : null;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (let i = 0; i < b.n; i++) {
    if (sec && !sec.has(bb[i])) continue;
    const x = b.lon[i], y = b.lat[i];
    if (x < x0) x0 = x;
    if (x > x1) x1 = x;
    if (y < y0) y0 = y;
    if (y > y1) y1 = y;
  }
  return [[x0, y0], [x1, y1]];
}

/** Tüm binaların sınır kutusu (meta.sinir). */
export function tumSinirKutusu(): [LonLat, LonLat] {
  const s = veri().meta.sinir;
  return [[s.lon[0], s.lat[0]], [s.lon[1], s.lat[1]]];
}

/* ================================================================== biçimlendiriciler (Türkçe) */

const _tamsayi = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 });
const _ondalik = new Map<number, Intl.NumberFormat>();
function ondalikFmt(b: number): Intl.NumberFormat {
  let f = _ondalik.get(b);
  if (!f) {
    f = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: b, maximumFractionDigits: b });
    _ondalik.set(b, f);
  }
  return f;
}

/** 19706 → "19.706";  sayi(3.14159, 2) → "3,14" */
export function sayi(x: number, basamak = 0): string {
  if (!Number.isFinite(x)) return '–';
  return basamak === 0 ? _tamsayi.format(Math.round(x)) : ondalikFmt(basamak).format(x);
}

/**
 * 0.0045 → "%0,45";  yuzde(0.3656, 1) → "%36,6" (oran 0..1 girilir).
 * Türkçe yazımda işaret yüzde imininin ÖNÜNE gelir: −%0,35 (U+2212).
 */
export function yuzde(oran: number, basamak = 1): string {
  if (!Number.isFinite(oran)) return '–';
  const isaret = oran < 0 ? '−' : '';
  return isaret + '%' + ondalikFmt(basamak).format(Math.abs(oran) * 100);
}

/**
 * İşaretli yüzde: 0.0051 → "+%0,51", −0.0035 → "−%0,35".
 * Yuvarlandığında sıfır kalan değer işaretsiz yazılır: isaretliYuzde(0.00002) → "%0,00".
 */
export function isaretliYuzde(oran: number, basamak = 2): string {
  if (!Number.isFinite(oran)) return '–';
  const v = oran * 100;
  const esik = 0.5 * Math.pow(10, -basamak); // yuvarlamada sıfır kalıyor mu
  if (Math.abs(v) < esik) return '%' + ondalikFmt(basamak).format(0);
  return (v > 0 ? '+' : '−') + '%' + ondalikFmt(basamak).format(Math.abs(v));
}

/** 189272 → "189 bin";  1250000 → "1,25 milyon";  950 → "950" */
export function kisaSayi(x: number): string {
  const a = Math.abs(x);
  if (a >= 1e6) return ondalikFmt(a >= 1e7 ? 1 : 2).format(x / 1e6).replace(/,0+$/, '') + ' milyon';
  if (a >= 1e4) return _tamsayi.format(Math.round(x / 1e3)) + ' bin';
  return _tamsayi.format(Math.round(x));
}

/** 12.345 → "12,3 km" */
export function km(x: number, basamak = 1): string {
  return ondalikFmt(basamak).format(x) + ' km';
}

/** 42.1 → "42 km²" */
export function km2(x: number): string {
  return _tamsayi.format(Math.round(x)) + ' km²';
}

/** Türkçe büyük harf: "istanbul" → "İSTANBUL" */
export function buyukHarf(s: string): string {
  return s.toLocaleUpperCase('tr-TR');
}

/* ================================================================== denge (türetilmiş, sabit sayı yok) */

/** Plandaki en büyük |sapma| (0..1). Bölge özetlerinden hesaplanır. */
export function maksSapma(plan: Plan): number {
  let m = 0;
  for (const b of plan.bolgeler) m = Math.max(m, Math.abs(b.sapma ?? 0));
  return m;
}

/** Plandaki sapma aralığı [min, maks] (işaretli). */
export function sapmaAraligi(plan: Plan): [number, number] {
  let a = Infinity;
  let b = -Infinity;
  for (const x of plan.bolgeler) {
    const s = x.sapma ?? 0;
    if (s < a) a = s;
    if (s > b) b = s;
  }
  if (!Number.isFinite(a)) return [0, 0];
  return [a, b];
}

/**
 * Hedeften en büyük sapmanın hane (RES HP) karşılığı — yukarı yuvarlanır.
 * "Hedeften en büyük sapma: 190 hane" cümlesi bundan türetilir. DİKKAT: bu, bölgeler ARASI
 * açıklık (maks − min) değildir; hedefe olan en büyük uzaklıktır. Excel, README ve S8 aynı sözü kullanır.
 */
export function enBuyukFarkHane(plan: Plan): number {
  const hedef = plan.hedef || 0;
  let m = 0;
  for (const b of plan.bolgeler) m = Math.max(m, Math.abs((b.olcu_deger ?? b.res_hp) - hedef));
  return Math.ceil(m);
}

/**
 * Dengeli plan N'leri: en büyük |sapma| ≤ esik olanlar (varsayılan %1).
 * Sunum kaydırıcısı ve Keşif N seçici yalnız bunlarda durur.
 */
export function dengeliPlanlar(esik = 0.01): number[] {
  const out: number[] = [];
  for (const n of planNleri()) {
    const p = planGetir(n);
    if (p && maksSapma(p) <= esik) out.push(n);
  }
  return out.length ? out : planNleri();
}

const ONLUK_EK = ["1'i", "2'si", "3'ü", "4'ü", "5'i", "6'sı", "7'si", "8'i", "9'u", "10'u"];

/**
 * Oranı "10 haneden 9'u" biçiminde anlatır (payda 10). 0 → "10 haneden 1'i"nin altı için "10 haneden 1'i".
 * onlukOran(189272, 296778) → "10 haneden 6'sı";  onlukOran(1745, 1971) → "10 haneden 9'u"
 */
export function onlukOran(pay: number, payda: number, birim = 'hane'): string {
  if (!(payda > 0)) return '–';
  const k = Math.min(10, Math.max(1, Math.round((pay / payda) * 10)));
  return `10 ${birim}den ${ONLUK_EK[k - 1]}`;
}
