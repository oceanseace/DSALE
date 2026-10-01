/**
 * "İşlerim" deposu (OPERASYON_V2_SPEC §6.9).
 *
 * Modül düzeyinde tek depo: teknisyen "Ben" sekmesine geçip dönünce liste,
 * "Yeni" işaretleri ve bugün ofise dönen işler kaybolmaz. React ekranları
 * `useIslerim()` ile abone olur; abone varken 15 sn'de bir (sekme görünürken)
 * sunucuya sorar.
 *
 * Akış:
 *   1. Açılışta telefondaki kopya (aynı kişi, 24 saatten yeni) hemen çizilir.
 *   2. `/api/islerim` gelince yerine geçer ve telefona yazılır.
 *   3. `/api/isler/degisim?imlec=` bu kişinin işlerinden birinde değişiklik
 *      söylerse liste yeniden çekilir. Yeni iş gelince telefon titrer (200 ms),
 *      üstte "1 yeni iş" yazar, satırda "Yeni" rozeti çıkar.
 *   4. Düğmeler kuyruğa yazılır (`kuyruk.ts`); kuyruktaki eylemler listeye
 *      YEREL olarak uygulanır (sunucu henüz bilmese de ekran doğruyu gösterir).
 */

import { useEffect, useSyncExternalStore } from 'react';
import { SahaHatasi } from '../api/istemci';
import {
  aktifIsKisisiYaz,
  isKayitlariniOku,
  isKayitlariniYaz,
  IS_KAYDI_OMRU_MS,
} from '../depo/db';
import type { Durum, IsAyrinti, IsSatir, IslerimYanit } from '../is/tipler';
import { degisimGetir, gorduBildir, islerimGetir } from './api';
import {
  basisAni,
  bekleyenleriOku,
  istemciKimligi,
  isKuyrugunaEkle,
  isKuyrugunuDinle,
  isKuyrugunuGonder,
  sunucuFarkiniYaz,
  type IsKuyrukKaydi,
} from './kuyruk';

/** Yoklama aralığı (teknik: 15 sn, §5.3.2). */
const YOKLAMA_MS = 15_000;

/** "Bitti" deyip ofise dönen iş (malzeme, altyapı, evde yok): bugün Bitenler'de görünür. */
export interface OfiseDonen {
  is_no: string;
  task_adi: string;
  yer: string | null;
  sonuc: string;
  zaman: number;
}

export type Duyuru =
  | { tur: 'yeni'; sayi: number }
  | { tur: 'dustu'; mesaj: string }
  | { tur: 'gitti'; etiket: string };

interface Durumu {
  kullaniciId: number | null;
  asama: 'bos' | 'yukleniyor' | 'hazir';
  yanit: IslerimYanit | null;
  /** Ekrandaki liste telefondaki kopyadan mı (ağ yok)? */
  onbellekten: boolean;
  /** Son BAŞARILI sunucu yanıtının anı (ms); telefon kopyasında kopyanın anı. */
  guncelleme: number | null;
  /** Son yoklama/çekme ağ hatasıyla mı bitti? */
  baglantiYok: boolean;
  hata: string | null;
  bekleyenler: IsKuyrukKaydi[];
  /**
   * Gönderilmiş ama liste henüz yeniden çekilmemiş eylemler: yeni liste gelene
   * kadar yerel olarak uygulanmaya devam eder (kart bir an eski yerine sıçramasın).
   */
  gonderilenler: Array<{ kayit: IsKuyrukKaydi; an: number }>;
  yeniler: Set<string>;
  ofiseDonenler: OfiseDonen[];
  sunucuFarkMs: number;
}

let durum: Durumu = {
  kullaniciId: null,
  asama: 'bos',
  yanit: null,
  onbellekten: false,
  guncelleme: null,
  baglantiYok: false,
  hata: null,
  bekleyenler: [],
  gonderilenler: [],
  yeniler: new Set(),
  ofiseDonenler: [],
  sunucuFarkMs: 0,
};

const aboneler = new Set<() => void>();
const duyuruDinleyicileri = new Set<(d: Duyuru) => void>();

function degistir(yama: Partial<Durumu>) {
  durum = { ...durum, ...yama };
  aboneler.forEach((f) => f());
}

function duyur(d: Duyuru) {
  duyuruDinleyicileri.forEach((f) => f(d));
}

export function duyurulariDinle(f: (d: Duyuru) => void): () => void {
  duyuruDinleyicileri.add(f);
  return () => {
    duyuruDinleyicileri.delete(f);
  };
}

/* ------------------------------ Yardımcılar ------------------------------ */

function sunucuAn(metin: string | null | undefined): number | null {
  if (!metin) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(metin);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0)).getTime();
}

/**
 * Teknisyen bu işi gördü mü? Sunucu alanı (`gordu`) varsa o; yoksa olay
 * defterinden: en son atamadan SONRA "teknik_gordu" olayı var mı.
 */
export function gorduMu(is: IsAyrinti): boolean {
  const alan = (is as IsAyrinti & { gordu?: boolean }).gordu;
  if (typeof alan === 'boolean') return alan;
  for (const o of is.olaylar ?? []) {
    if (o.tur === 'teknik_gordu') return true;
    if (o.tur === 'atama') return false;
  }
  return false;
}

const ILERI: Partial<Record<Durum, number>> = { atandi: 0, yolda: 1, sahada: 2 };

/** Kuyruktaki eylemleri sunucu listesine yerel olarak uygular. */
function yerelUygula(yanit: IslerimYanit, bekleyenler: IsKuyrukKaydi[]) {
  let acik: IsAyrinti[] = [...yanit.isler];
  let bitenler: IsSatir[] = [...yanit.bitenler];
  for (const k of bekleyenler) {
    const i = acik.findIndex((x) => x.is_no === k.is_no);
    if (i < 0) continue;
    const is = acik[i];
    const zaman = String(k.govde.zaman ?? '');
    if (k.tur === 'durum') {
      const yeni = k.govde.yeni as Durum;
      if (yeni === 'yolda' || yeni === 'sahada') {
        if ((ILERI[is.durum] ?? 9) < (ILERI[yeni] ?? 0)) acik[i] = { ...is, durum: yeni, durum_zamani: zaman };
      } else if (yeni === 'cozuldu') {
        acik = acik.filter((x) => x.is_no !== k.is_no);
        bitenler = [{ ...is, durum: 'cozuldu', kova: 'biten', durum_zamani: zaman }, ...bitenler];
      } else if (yeni === 'atandi') {
        const rv = k.govde.randevu as { bas: string; bit: string } | undefined;
        if (rv) acik[i] = { ...is, randevu: { bas: rv.bas, bit: rv.bit, teyitli: true, kaynak: 'biz' }, sira: null };
      } else {
        acik = acik.filter((x) => x.is_no !== k.is_no); // askıda, altyapı, evde yok: ofise döndü
      }
    } else if (k.tur === 'sira') {
      const hedef = Math.max(0, Number(k.govde.yeni_sira ?? 1) - 1);
      const kalan = acik.filter((x) => x.is_no !== k.is_no);
      kalan.splice(Math.min(hedef, kalan.length), 0, is);
      acik = kalan;
    }
  }
  return { acik, bitenler };
}

export function bugunMu(metin: string | null | undefined, farkMs = 0): boolean {
  const an = sunucuAn(metin);
  if (an == null) return true;
  const bugun = new Date(Date.now() + farkMs);
  const d = new Date(an);
  return d.getFullYear() === bugun.getFullYear() && d.getMonth() === bugun.getMonth() && d.getDate() === bugun.getDate();
}

function gelecekGunMu(metin: string | null | undefined, farkMs = 0): boolean {
  const an = sunucuAn(metin);
  if (an == null) return false;
  const yarin = new Date(Date.now() + farkMs);
  yarin.setHours(0, 0, 0, 0);
  yarin.setDate(yarin.getDate() + 1);
  return an >= yarin.getTime();
}

/* ------------------------------ Görünüm ------------------------------ */

export interface IslerimGorunumu {
  /** Yolda / sahada (şu an üzerinde çalışılan). */
  simdiki: IsAyrinti[];
  /** Bugün yapılacaklar (randevusuz ya da randevusu bugün/geçmiş), sırayla. */
  bugun: IsAyrinti[];
  /** Randevusu yarın ve sonrasında olanlar. */
  sonraki: IsAyrinti[];
  bitenler: IsSatir[];
  ofiseDonenler: OfiseDonen[];
}

let sonGorunum: { anahtar: unknown[]; deger: IslerimGorunumu } | null = null;

function gorunumHesapla(): IslerimGorunumu {
  const anahtar = [durum.yanit, durum.bekleyenler, durum.gonderilenler, durum.ofiseDonenler, durum.sunucuFarkMs];
  if (sonGorunum && sonGorunum.anahtar.every((x, i) => x === anahtar[i])) return sonGorunum.deger;
  let deger: IslerimGorunumu = { simdiki: [], bugun: [], sonraki: [], bitenler: [], ofiseDonenler: durum.ofiseDonenler };
  if (durum.yanit) {
    const eylemler = [...durum.gonderilenler.map((g) => g.kayit), ...durum.bekleyenler];
    const { acik, bitenler } = yerelUygula(durum.yanit, eylemler);
    const simdiki = acik.filter((x) => x.durum === 'yolda' || x.durum === 'sahada');
    const kalan = acik.filter((x) => x.durum !== 'yolda' && x.durum !== 'sahada');
    deger = {
      simdiki,
      bugun: kalan.filter((x) => !x.randevu || !gelecekGunMu(x.randevu.bas, durum.sunucuFarkMs)),
      sonraki: kalan.filter((x) => x.randevu && gelecekGunMu(x.randevu.bas, durum.sunucuFarkMs)),
      bitenler,
      ofiseDonenler: durum.ofiseDonenler.filter((o) => !acik.some((x) => x.is_no === o.is_no)),
    };
  }
  sonGorunum = { anahtar, deger };
  return deger;
}

/* ------------------------------ Sunucu ------------------------------ */

let cekiliyor: Promise<void> | null = null;

/** Listeyi sunucudan çeker; yeni gelen işleri işaretler ve telefona yazar. */
export function yenile(): Promise<void> {
  if (cekiliyor) return cekiliyor;
  const kisi = durum.kullaniciId;
  if (kisi == null) return Promise.resolve();
  cekiliyor = (async () => {
    if (!durum.yanit) degistir({ asama: 'yukleniyor' });
    const baslangic = Date.now();
    try {
      const y = await islerimGetir();
      if (durum.kullaniciId !== kisi) return;
      const fark = (sunucuAn(y.sunucu_zamani) ?? Date.now()) - Date.now();
      sunucuFarkiniYaz(fark);
      const onceki = durum.yanit && !durum.onbellekten ? new Set(durum.yanit.isler.map((x) => x.is_no)) : null;
      const yeniler = new Set(durum.yeniler);
      const gelen: string[] = [];
      for (const is of y.isler) {
        if (onceki ? !onceki.has(is.is_no) : !gorduMu(is)) {
          if (!yeniler.has(is.is_no)) gelen.push(is.is_no);
          yeniler.add(is.is_no);
        }
      }
      // Artık listede olmayanın "Yeni" işareti kalmaz.
      for (const no of [...yeniler]) if (!y.isler.some((x) => x.is_no === no)) yeniler.delete(no);
      degistir({
        yanit: y,
        asama: 'hazir',
        onbellekten: false,
        guncelleme: Date.now(),
        baglantiYok: false,
        hata: null,
        yeniler,
        sunucuFarkMs: fark,
        gonderilenler: durum.gonderilenler.filter((g) => g.an >= baslangic),
      });
      imlec = y.imlec;
      void isKayitlariniYaz(kisi, { yanit: y, ofiseDonenler: durum.ofiseDonenler });
      // Liste açıkken gelen iş titretir ve kısa bildirim çıkarır; ilk açılışta
      // görülmemiş işler yalnız "Yeni" ile işaretlenir (üstteki şerit söyler).
      if (gelen.length && onceki) {
        try {
          navigator.vibrate?.(200);
        } catch {
          /* titreşim yoksa sorun değil */
        }
        duyur({ tur: 'yeni', sayi: gelen.length });
      }
    } catch (h) {
      if (h instanceof SahaHatasi && h.durum === 401) return; // oturum ekranı devralır
      const ag = !(h instanceof SahaHatasi) || h.agHatasi;
      degistir({
        asama: durum.yanit ? 'hazir' : 'bos',
        baglantiYok: ag,
        hata: ag ? null : h instanceof Error ? h.message : 'Liste alınamadı.',
      });
    } finally {
      cekiliyor = null;
    }
  })();
  return cekiliyor;
}

let imlec = 0;

/** Canlı yoklama: yalnız bu kişinin işlerinden biri değiştiyse listeyi yeniden çeker. */
async function yokla() {
  if (document.visibilityState !== 'visible' || durum.kullaniciId == null) return;
  if (!durum.yanit || durum.onbellekten) {
    await yenile();
    return;
  }
  try {
    const d = await degisimGetir(imlec);
    const benim = new Set(durum.yanit.isler.map((x) => x.is_no));
    const degisti = d.isler.length > 0 || d.gorunmez.some((no) => benim.has(no));
    imlec = d.imlec;
    if (durum.baglantiYok) degistir({ baglantiYok: false });
    if (degisti) await yenile();
  } catch (h) {
    if (h instanceof SahaHatasi && h.durum === 401) return;
    degistir({ baglantiYok: true });
  }
}

/* ------------------------------ Görüldü ------------------------------ */

const gorduGonderilen = new Set<string>();
let gorduBekleyen: string[] = [];
let gorduSayac: number | null = null;

/** Ekrana giren işler: 1,5 sn görünür kalınca sunucuya "gördü" denir (bir kez). */
export function gorulduIsaretle(isler: IsAyrinti[]) {
  const yeni = isler.filter((x) => !gorduMu(x) && !gorduGonderilen.has(x.is_no)).map((x) => x.is_no);
  if (!yeni.length) return;
  gorduBekleyen = [...new Set([...gorduBekleyen, ...yeni])];
  if (gorduSayac) return;
  gorduSayac = window.setTimeout(async () => {
    gorduSayac = null;
    if (document.visibilityState !== 'visible') return;
    const nolar = gorduBekleyen;
    gorduBekleyen = [];
    try {
      await gorduBildir(nolar);
      nolar.forEach((n) => gorduGonderilen.add(n));
    } catch {
      /* bir sonraki çizimde yeniden denenir */
    }
  }, 1500);
}

/** İş açılınca "Yeni" işareti kalkar. */
export function yeniyiKaldir(isNo: string) {
  if (!durum.yeniler.has(isNo)) return;
  const yeniler = new Set(durum.yeniler);
  yeniler.delete(isNo);
  degistir({ yeniler });
}

/* ------------------------------ Eylemler ------------------------------ */

function kisiGerekli(): number {
  if (durum.kullaniciId == null) throw new Error('Oturum açık değil.');
  return durum.kullaniciId;
}

/**
 * Durum düğmesi: kuyruğa yazar (ekran hemen güncellenir), sonra gönderir.
 * `ek`: evde_miydi, sonuc_kodu, randevu, notu.
 */
export async function durumDegistir(
  is: IsAyrinti,
  yeni: Durum,
  etiket: string,
  ek: Record<string, unknown> = {},
  ofiseDonenSonuc?: string,
) {
  const kisi = kisiGerekli();
  const istemci_id = istemciKimligi();
  if (ofiseDonenSonuc) {
    const kayit: OfiseDonen = {
      is_no: is.is_no,
      task_adi: is.task_adi,
      yer: is.kisa_adres ?? is.mahalle ?? null,
      sonuc: ofiseDonenSonuc,
      zaman: Date.now(),
    };
    degistir({ ofiseDonenler: [kayit, ...durum.ofiseDonenler.filter((o) => o.is_no !== is.is_no)] });
  }
  await isKuyrugunaEkle({
    istemci_id,
    kullanici_id: kisi,
    is_no: is.is_no,
    tur: 'durum',
    etiket,
    govde: { yeni, istemci_id, zaman: basisAni(), ...ek },
  });
}

export async function notEkle(is: IsAyrinti, metin: string) {
  const kisi = kisiGerekli();
  const istemci_id = istemciKimligi();
  await isKuyrugunaEkle({
    istemci_id,
    kullanici_id: kisi,
    is_no: is.is_no,
    tur: 'not',
    etiket: 'Not',
    govde: { metin: metin.slice(0, 1000), istemci_id },
  });
}

export async function onceBunu(is: IsAyrinti, neden: 'yakindaydim' | 'musteri_aradi' | 'diger') {
  const kisi = kisiGerekli();
  const istemci_id = istemciKimligi();
  await isKuyrugunaEkle({
    istemci_id,
    kullanici_id: kisi,
    is_no: is.is_no,
    tur: 'sira',
    etiket: 'Sıra değişikliği',
    govde: { is_no: is.is_no, yeni_sira: 1, neden, istemci_id },
  });
}

/* ------------------------------ Başlat / bırak ------------------------------ */

let yoklamaSayaci: number | null = null;
let kuyrukBirak: (() => void) | null = null;
let yenileSayaci: number | null = null;

function yakindaYenile() {
  if (yenileSayaci) window.clearTimeout(yenileSayaci);
  yenileSayaci = window.setTimeout(() => {
    yenileSayaci = null;
    void yenile();
  }, 700);
}

async function kisiyiKur(kullaniciId: number) {
  aktifIsKisisiYaz(kullaniciId);
  const bekleyenler = await bekleyenleriOku();
  const kopya = await isKayitlariniOku<{ yanit: IslerimYanit; ofiseDonenler?: OfiseDonen[] }>(kullaniciId);
  if (durum.kullaniciId !== kullaniciId) return;
  const bugun = new Date().toDateString();
  const bugunkuler = (kopya?.veri.ofiseDonenler ?? []).filter(
    (o) => Date.now() - o.zaman < IS_KAYDI_OMRU_MS && new Date(o.zaman).toDateString() === bugun,
  );
  degistir({
    bekleyenler,
    ...(kopya && !durum.yanit
      ? { yanit: kopya.veri.yanit, onbellekten: true, guncelleme: kopya.zaman, asama: 'hazir' as const, ofiseDonenler: bugunkuler }
      : {}),
  });
  void yenile();
  void isKuyrugunuGonder();
}

function baslat() {
  const gorunur = () => {
    if (document.visibilityState === 'visible') void yenile();
  };
  const cevrimici = () => void yenile();
  document.addEventListener('visibilitychange', gorunur);
  window.addEventListener('online', cevrimici);
  yoklamaSayaci = window.setInterval(() => void yokla(), YOKLAMA_MS);
  kuyrukBirak = isKuyrugunuDinle((o) => {
    if (o.tur === 'degisti') {
      degistir({ bekleyenler: o.bekleyen });
    } else if (o.tur === 'gitti') {
      degistir({ gonderilenler: [...durum.gonderilenler, { kayit: o.kayit, an: Date.now() }] });
      duyur({ tur: 'gitti', etiket: o.kayit.etiket });
      yakindaYenile();
    } else if (o.tur === 'dustu') {
      // Reddedilen eylem listeden kalkar; ofise dönen işareti de geri alınır.
      degistir({ ofiseDonenler: durum.ofiseDonenler.filter((x) => x.is_no !== o.kayit.is_no) });
      duyur({ tur: 'dustu', mesaj: o.mesaj });
      yakindaYenile();
    }
  });
  return () => {
    document.removeEventListener('visibilitychange', gorunur);
    window.removeEventListener('online', cevrimici);
    if (yoklamaSayaci) window.clearInterval(yoklamaSayaci);
    yoklamaSayaci = null;
    kuyrukBirak?.();
    kuyrukBirak = null;
  };
}

let birak: (() => void) | null = null;

function abone(f: () => void) {
  aboneler.add(f);
  if (aboneler.size === 1) birak = baslat();
  return () => {
    aboneler.delete(f);
    if (aboneler.size === 0) {
      birak?.();
      birak = null;
    }
  };
}

/** Oturumdaki kişi değişti (ya da ilk açılış): depo o kişiye göre kurulur. */
export function kisiAyarla(kullaniciId: number | null) {
  if (durum.kullaniciId === kullaniciId) return;
  sonGorunum = null;
  durum = {
    ...durum,
    kullaniciId,
    asama: kullaniciId == null ? 'bos' : 'yukleniyor',
    yanit: null,
    onbellekten: false,
    guncelleme: null,
    baglantiYok: false,
    hata: null,
    bekleyenler: [],
    gonderilenler: [],
    yeniler: new Set(),
    ofiseDonenler: [],
  };
  imlec = 0;
  aboneler.forEach((f) => f());
  if (kullaniciId != null) void kisiyiKur(kullaniciId);
}

export interface IslerimDeposu extends Durumu {
  gorunum: IslerimGorunumu;
}

let sonAnlik: { durum: Durumu; deger: IslerimDeposu } | null = null;

function anlik(): IslerimDeposu {
  if (sonAnlik && sonAnlik.durum === durum) return sonAnlik.deger;
  const deger = { ...durum, gorunum: gorunumHesapla() };
  sonAnlik = { durum, deger };
  return deger;
}

/** Ekranların kancası: kişiyi kurar, depoya abone olur. */
export function useIslerim(kullaniciId: number | null): IslerimDeposu {
  useEffect(() => {
    kisiAyarla(kullaniciId);
  }, [kullaniciId]);
  return useSyncExternalStore(abone, anlik, anlik);
}
