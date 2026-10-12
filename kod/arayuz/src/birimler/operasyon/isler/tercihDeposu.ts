/**
 * TASKS ve MAP'in kişisel tercihleri — TEK depo, SUNUCUDA saklanır (kişiyi bilgisayardan bilgisayara izler):
 *   · `etkin`    Excel düzeni: görünen sütunlar + sıra, genişlik, yakınlaştırma, A B C satırı, sıralama,
 *                uygulanan adlı düzenin adı (`ad`, değiştiyse `degisti`).
 *   · `duzenler` kişinin adlı düzenleri ("TV ekibi", "Superbox" …); kaydederken süzgeç de eklenebilir.
 *   · `suzgec`   TASKS ↔ MAP ORTAK süzgeci: sütun süzgeçleri, arama, Özel filtre, Gizli/Yalnız tür, geliş tarihi.
 * Sunucu: GET/PUT /api/isler/tercih (kod/operasyon/v2/tasks_tercih.py). Yazma 0,8 sn sakinleşince gider;
 * cihazdaki kopya (localStorage) yalnız anında açılış için. Kişinin düzeni yoksa unvanının varsayılanı
 * (Administrator verir), o da yoksa fabrika varsayılanı. Eski cihaz kayıtları (isler.tablo.<id>.*) ilk açılışta
 * sunucuya taşınır.
 * Kim: tabloSuzgec.ts, sutunDuzeni.ts, isTuru.tsx, Gorunumler.tsx, map/tarihSuzgeci.tsx, DuzenMenusu.tsx, Isler.tsx.
 */

import { useEffect, useSyncExternalStore } from 'react';
import { tercihGetir, tercihYaz, unvanDuzeniYaz, type AdliDuzen as AdliHam, type TasksTercih } from '../../../cekirdek/is/api';
import { yerelJsonOku, yerelJsonYaz, yerelOku } from '../../../cekirdek/ortak/yerel';
import { useOturum } from '../../../cekirdek/yerel/oturum';
import type { IsaretRengi } from '../../../cekirdek/is/tipler';
import { VARSAYILAN_GORUNEN } from './sutunlar';

const RENK_KODLARI: IsaretRengi[] = ['sari', 'kirmizi', 'yesil', 'mavi', 'mor', 'turuncu'];

/* ------------------------------ tipler ------------------------------ */

export interface SutunSuzgeci {
  /** Seçili değerler; null → hepsi. */
  degerler: string[] | null;
  /** "Metin içerir" (boş → yok). */
  metin: string;
  /** "dahil" (varsayılan): yalnız `degerler` gösterilir · "haric": `degerler` gizlenir (İş türündeki gibi). */
  kip?: 'dahil' | 'haric';
  /** Renge göre süz (Excel): bu sütundaki hücresi bu dolgu renginde olan satırlar. */
  renk?: IsaretRengi;
}
export type Siralama = { id: string; yon: 1 | -1 } | null;
export interface TurSuzgeci {
  kip: 'dahil' | 'haric';
  degerler: string[];
}
export type TarihKipi = 'hepsi' | 'once' | 'sonra' | 'aralik';
export interface TarihSuzgeci {
  kip: TarihKipi;
  gun: string;
  bas: string;
  bit: string;
  hazir: 'bugun' | 'son7' | 'eski30' | null;
}
export interface OrtakSuzgec {
  sutunlar: Record<string, SutunSuzgeci>;
  arama: string;
  gorunum_id: number | null;
  tur: TurSuzgeci;
  tarih: TarihSuzgeci;
}
export interface Duzen {
  /** Uygulanan adlı düzen (yoksa null) ve sonradan değişip değişmediği. */
  ad?: string | null;
  degisti?: boolean;
  gorunen: string[];
  gen: Record<string, number>;
  /** Kayıt anındaki varsayılan sütunlar (sonradan eklenen varsayılan sütunu tanımak için). */
  bilinen?: string[];
  yakinlik?: number;
  harfler?: boolean;
  sira?: Siralama;
  /** Yalnız adlı/hazır düzende: uygulanınca ortak süzgeç bununla değişir. */
  suzgec?: Partial<OrtakSuzgec>;
}
export interface AdliDuzen {
  ad: string;
  duzen: Duzen;
}

export const TARIH_BOS: TarihSuzgeci = { kip: 'hepsi', gun: '', bas: '', bit: '', hazir: null };
export const SUZGEC_BOS: OrtakSuzgec = { sutunlar: {}, arama: '', gorunum_id: null, tur: { kip: 'dahil', degerler: [] }, tarih: TARIH_BOS };
export const FABRIKA_DUZENI: Duzen = { ad: null, gorunen: VARSAYILAN_GORUNEN, gen: {}, yakinlik: 100, harfler: true, sira: null };

interface Durum {
  uid: number | null;
  sunucu: 'yok' | 'yukleniyor' | 'hazir' | 'hata';
  etkin: Duzen | null;
  duzenler: AdliDuzen[];
  suzgec: OrtakSuzgec;
  fabrika: AdliDuzen[];
  unvan: TasksTercih['unvan'];
  unvanlar: NonNullable<TasksTercih['unvanlar']>;
  administrator: boolean;
}

/* ------------------------------ biçim denetimi ------------------------------ */

const dizi = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []);

export function duzenOku(v: unknown): Duzen | null {
  if (!v || typeof v !== 'object') return null;
  const d = v as Record<string, unknown>;
  if (!Array.isArray(d.gorunen)) return null;
  const gen: Record<string, number> = {};
  if (d.gen && typeof d.gen === 'object')
    Object.entries(d.gen as Record<string, unknown>).forEach(([k, n]) => typeof n === 'number' && (gen[k] = n));
  const sira = d.sira as Siralama | undefined;
  return {
    ad: typeof d.ad === 'string' ? d.ad : null,
    degisti: d.degisti === true,
    gorunen: dizi(d.gorunen),
    gen,
    bilinen: Array.isArray(d.bilinen) ? dizi(d.bilinen) : undefined,
    yakinlik: typeof d.yakinlik === 'number' ? d.yakinlik : undefined,
    harfler: typeof d.harfler === 'boolean' ? d.harfler : undefined,
    sira: sira && typeof sira === 'object' && typeof sira.id === 'string' && (sira.yon === 1 || sira.yon === -1) ? sira : null,
    suzgec: d.suzgec && typeof d.suzgec === 'object' ? (d.suzgec as Partial<OrtakSuzgec>) : undefined,
  };
}

export function suzgecOku(v: unknown): OrtakSuzgec {
  if (!v || typeof v !== 'object') return SUZGEC_BOS;
  const s = v as Partial<OrtakSuzgec>;
  const sutunlar: Record<string, SutunSuzgeci> = {};
  if (s.sutunlar && typeof s.sutunlar === 'object')
    Object.entries(s.sutunlar).forEach(([id, f]) => {
      if (f && typeof f === 'object')
        sutunlar[id] = {
          degerler: Array.isArray(f.degerler) ? dizi(f.degerler) : null,
          metin: typeof f.metin === 'string' ? f.metin : '',
          ...(f.kip === 'haric' ? { kip: 'haric' as const } : {}),
          ...(typeof f.renk === 'string' && RENK_KODLARI.includes(f.renk as IsaretRengi) ? { renk: f.renk as IsaretRengi } : {}),
        };
    });
  const t = s.tur;
  const tr = s.tarih;
  return {
    sutunlar,
    arama: typeof s.arama === 'string' ? s.arama : '',
    gorunum_id: typeof s.gorunum_id === 'number' ? s.gorunum_id : null,
    tur: t && (t.kip === 'dahil' || t.kip === 'haric') ? { kip: t.kip, degerler: dizi(t.degerler) } : SUZGEC_BOS.tur,
    tarih:
      tr && ['hepsi', 'once', 'sonra', 'aralik'].includes(tr.kip)
        ? { kip: tr.kip, gun: String(tr.gun ?? ''), bas: String(tr.bas ?? ''), bit: String(tr.bit ?? ''), hazir: tr.hazir ?? null }
        : TARIH_BOS,
  };
}

const adliOku = (l: AdliHam[] | null | undefined): AdliDuzen[] =>
  (l ?? []).map((x) => ({ ad: x.ad, duzen: duzenOku(x.duzen) ?? { ...FABRIKA_DUZENI } }));

/* ------------------------------ depo ------------------------------ */

let durum: Durum = {
  uid: null,
  sunucu: 'yok',
  etkin: null,
  duzenler: [],
  suzgec: SUZGEC_BOS,
  fabrika: [],
  unvan: null,
  unvanlar: [],
  administrator: false,
};
const dinleyiciler = new Set<() => void>();
const yay = () => dinleyiciler.forEach((f) => f());
const kopyaAnahtari = (uid: number) => `isler.tercih.${uid}`;
type Anahtar = 'etkin' | 'duzenler' | 'suzgec';
const kirli = new Set<Anahtar>();
let zamanlayici = 0;

function guncelle(y: Partial<Durum>) {
  durum = { ...durum, ...y };
  yay();
}

function kopyaYaz() {
  if (durum.uid == null) return;
  yerelJsonYaz(kopyaAnahtari(durum.uid), { etkin: durum.etkin, duzenler: durum.duzenler, suzgec: durum.suzgec });
}

/** Eski cihaz kayıtları (2026-10 öncesi: isler.tablo.<id>.*, isler.turSuzgeci.<id>, isler.gorunum). */
function eskiKayit(uid: number): { etkin: Duzen | null; suzgec: OrtakSuzgec | null } {
  const on = `isler.tablo.${uid}`;
  const d = duzenOku(yerelJsonOku<unknown>(`${on}.duzen`, null));
  const yak = yerelJsonOku<number | null>(`${on}.yakinlik`, null);
  const harf = yerelJsonOku<boolean | null>(`${on}.harfler`, null);
  const sira = yerelJsonOku<Siralama>(`${on}.sira`, null);
  const etkin =
    d || yak != null || harf != null || sira
      ? { ...(d ?? FABRIKA_DUZENI), ad: null, yakinlik: yak ?? 100, harfler: harf ?? true, sira }
      : null;
  const sut = yerelJsonOku<Record<string, SutunSuzgeci> | null>(`${on}.suzgec`, null);
  const tur = yerelJsonOku<TurSuzgeci | null>(`isler.turSuzgeci.${uid}`, null);
  const gid = Number(yerelOku('isler.gorunum')) || null;
  const suzgec =
    (sut && Object.keys(sut).length) || tur?.degerler?.length || gid
      ? suzgecOku({ sutunlar: sut ?? {}, tur: tur ?? undefined, gorunum_id: gid })
      : null;
  return { etkin, suzgec };
}

async function gonder() {
  zamanlayici = 0;
  if (!kirli.size || durum.uid == null) return;
  const g: Parameters<typeof tercihYaz>[0] = {};
  const anahtarlar = [...kirli];
  kirli.clear();
  for (const a of anahtarlar) {
    if (a === 'etkin') g.etkin = durum.etkin as unknown as Record<string, unknown> | null;
    else if (a === 'duzenler') g.duzenler = durum.duzenler as unknown as AdliHam[];
    else g.suzgec = durum.suzgec as unknown as Record<string, unknown>;
  }
  try {
    await tercihYaz(g);
  } catch {
    anahtarlar.forEach((a) => kirli.add(a)); // bir sonraki değişiklikte yeniden denenir
  }
}

function kaydet(a: Anahtar) {
  kirli.add(a);
  kopyaYaz();
  if (zamanlayici) window.clearTimeout(zamanlayici);
  zamanlayici = window.setTimeout(() => void gonder(), 800);
}

if (typeof window !== 'undefined') window.addEventListener('pagehide', () => void gonder());

/**
 * Pencereler/sekmeler arası TEK süzgeç durumu: TASKS ve MAP ayrı pencerede açıkken biri süzgeci değiştirince
 * (cihaz kopyası localStorage'a yazılır → 'storage' olayı) öteki aynı durumu hemen alır; pencereye dönünce de
 * sunucudaki son hâl okunur. Eskiden her pencere kendi bellek kopyasını tutuyordu: MAP'te "yalnız 15 kurulum"
 * seçiliyken TASKS eski (gizle) kipini uyguluyor ve 0,8 sn sonra sunucuya geri yazıyordu (08.10).
 */
export function digerPenceredenAl(ham: string | null): boolean {
  if (durum.uid == null || !ham) return false;
  let k: { etkin?: unknown; duzenler?: AdliHam[]; suzgec?: unknown };
  try {
    k = JSON.parse(ham);
  } catch {
    return false;
  }
  if (!k || typeof k !== 'object') return false;
  const y: Partial<Durum> = {};
  if (!kirli.has('suzgec') && k.suzgec !== undefined) y.suzgec = suzgecOku(k.suzgec);
  if (!kirli.has('etkin') && k.etkin !== undefined) y.etkin = duzenOku(k.etkin);
  if (!kirli.has('duzenler') && Array.isArray(k.duzenler)) y.duzenler = adliOku(k.duzenler);
  if (!Object.keys(y).length) return false;
  guncelle(y);
  return true;
}
let sonTazeleme = 0;
function sunucudanTazele() {
  const uid = durum.uid;
  if (uid == null || kirli.size || Date.now() - sonTazeleme < 5000) return;
  sonTazeleme = Date.now();
  tercihGetir()
    .then((t) => {
      if (durum.uid === uid && !kirli.size) {
        guncelle(sunucudanAl(t));
        kopyaYaz();
      }
    })
    .catch(() => undefined);
}
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (o) => {
    if (durum.uid != null && o.key === kopyaAnahtari(durum.uid)) digerPenceredenAl(o.newValue);
  });
  window.addEventListener('focus', sunucudanTazele);
  document.addEventListener('visibilitychange', () => document.visibilityState === 'visible' && sunucudanTazele());
}

function sunucudanAl(t: TasksTercih) {
  const y: Partial<Durum> = {
    sunucu: 'hazir',
    fabrika: adliOku(t.fabrika),
    unvan: t.unvan ?? null,
    unvanlar: t.unvanlar ?? [],
    administrator: Boolean(t.administrator),
  };
  if (!kirli.has('etkin')) y.etkin = duzenOku(t.etkin);
  if (!kirli.has('duzenler')) y.duzenler = adliOku(t.duzenler);
  if (!kirli.has('suzgec')) y.suzgec = suzgecOku(t.suzgec);
  return y;
}

/** Kişi değişince (ya da ilk açılışta) cihaz kopyasından anında, sonra sunucudan. */
function baslat(uid: number | null) {
  if (uid === durum.uid) return;
  kirli.clear();
  if (uid == null) {
    durum = { ...durum, uid: null, sunucu: 'yok', etkin: null, duzenler: [], suzgec: SUZGEC_BOS };
    return;
  }
  const kopya = yerelJsonOku<{ etkin?: unknown; duzenler?: AdliHam[]; suzgec?: unknown } | null>(kopyaAnahtari(uid), null);
  const eski = kopya ? null : eskiKayit(uid);
  durum = {
    ...durum,
    uid,
    sunucu: 'yukleniyor',
    etkin: kopya ? duzenOku(kopya.etkin) : eski?.etkin ?? null,
    duzenler: kopya ? adliOku(kopya.duzenler) : [],
    suzgec: kopya ? suzgecOku(kopya.suzgec) : eski?.suzgec ?? SUZGEC_BOS,
  };
  tercihGetir()
    .then((t) => {
      if (durum.uid !== uid) return;
      const sunucuBos = !t.etkin && !t.suzgec && !(t.duzenler ?? []).length;
      if (sunucuBos && (durum.etkin || durum.suzgec !== SUZGEC_BOS)) {
        // İlk kez: bu cihazdaki düzen ve süzgeç sunucuya taşınır.
        if (durum.etkin) kirli.add('etkin');
        if (durum.suzgec !== SUZGEC_BOS) kirli.add('suzgec');
        guncelle(sunucudanAl(t));
        void gonder();
      } else guncelle(sunucudanAl(t));
      kopyaYaz();
    })
    .catch(() => {
      if (durum.uid === uid) guncelle({ sunucu: 'hata' });
    });
}

/* ------------------------------ yazıcılar ------------------------------ */

/** Kişinin düzeni yoksa başladığı düzen: unvan varsayılanı, yoksa fabrika. */
export function baslangicDuzeni(d: Durum = durum): Duzen {
  const u = duzenOku(d.unvan?.duzen);
  return u ? { ...u, ad: null, degisti: false, suzgec: undefined } : FABRIKA_DUZENI;
}
export const etkinDuzen = (d: Durum = durum): Duzen => d.etkin ?? baslangicDuzeni(d);

/** Etkin düzeni değiştir (adlı düzenden geliyorsa "değişti" işaretlenir). */
export function etkinYaz(f: (d: Duzen) => Duzen) {
  const o = etkinDuzen();
  const y = f(o);
  durum = { ...durum, etkin: { ...y, degisti: Boolean(y.ad) && (y.degisti || y !== o) } };
  yay();
  kaydet('etkin');
}

export function suzgecYaz(f: (s: OrtakSuzgec) => OrtakSuzgec) {
  durum = { ...durum, suzgec: f(durum.suzgec) };
  yay();
  kaydet('suzgec');
}

/** Adlı ya da hazır düzeni uygula; düzende süzgeç varsa ortak süzgeç onunla değişir. */
export function duzenUygula(ad: string | null, d: Duzen) {
  const { suzgec, ...geri } = d;
  durum = { ...durum, etkin: { ...geri, ad, degisti: false } };
  if (suzgec) durum = { ...durum, suzgec: suzgecOku({ ...SUZGEC_BOS, ...suzgec }) };
  yay();
  kaydet('etkin');
  if (suzgec) kaydet('suzgec');
}

/** Şu anki düzeni adla kaydet (aynı adlı varsa üzerine yazar). `suzgecle`: o anki ortak süzgeç de düzene girer. */
export function duzenKaydet(ad: string, suzgecle: boolean) {
  const { degisti: _d, ad: _a, suzgec: _s, ...d } = etkinDuzen();
  void _d;
  void _a;
  void _s;
  const yeni: AdliDuzen = { ad, duzen: { ...d, ...(suzgecle ? { suzgec: durum.suzgec } : {}) } };
  const l = durum.duzenler.filter((x) => x.ad.toLocaleLowerCase('tr-TR') !== ad.toLocaleLowerCase('tr-TR'));
  durum = { ...durum, duzenler: [...l, yeni], etkin: { ...etkinDuzen(), ad, degisti: false } };
  yay();
  kaydet('duzenler');
  kaydet('etkin');
}

export function duzenSil(ad: string) {
  durum = {
    ...durum,
    duzenler: durum.duzenler.filter((x) => x.ad !== ad),
    etkin: durum.etkin?.ad === ad ? { ...durum.etkin, ad: null, degisti: false } : durum.etkin,
  };
  yay();
  kaydet('duzenler');
  kaydet('etkin');
}

/** Administrator: şu anki düzen (süzgeçsiz) bir unvanın varsayılanı olur; null → kaldırılır. */
export async function unvanVarsayilaniYaz(unvanId: number, kaldir = false): Promise<void> {
  const { degisti: _d, ad: _a, suzgec: _s, ...d } = etkinDuzen();
  void _d;
  void _a;
  void _s;
  const t = await unvanDuzeniYaz(unvanId, kaldir ? null : (d as unknown as Record<string, unknown>));
  guncelle({ unvan: t.unvan ?? null, unvanlar: t.unvanlar ?? [] });
}

/* ------------------------------ kanca ------------------------------ */

export function useTercih(): Durum {
  const { kullanici } = useOturum();
  const uid = kullanici?.id ?? null;
  /* Kişi değişince depo yüklenir; çizim sırasında değil (useSyncExternalStore yırtılmasın). */
  useEffect(() => {
    if (uid !== durum.uid) {
      baslat(uid);
      yay();
    }
  }, [uid]);
  return useSyncExternalStore(
    (f) => {
      dinleyiciler.add(f);
      return () => dinleyiciler.delete(f);
    },
    () => durum,
  );
}
