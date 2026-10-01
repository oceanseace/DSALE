/**
 * `saha/rota.py` içindeki öncelik formülünün birebir kopyası.
 *
 *     oncelik = firsat × yeni_site_carpani × tekrar_carpani × doygunluk_carpani
 *
 * Neden burada da var: "Algoritma seçsin" düğmesi yöneticiye, göndermeden ÖNCE,
 * algoritmanın hangi binaları seçeceğini gösterir. Sunucuya yazan bir uç
 * çağrılmadan önizleme yapılabilsin diye aynı kural burada da çalışır.
 * Gönderim anında sıralamayı yine sunucu kurar (2-opt turu ordadır).
 */

import type { BinaKart } from './tipler';

const SOGUMA_GUN = 30;
/** `saha/ayarlar.py` TABAN_ONCELIK — fırsatı sıfır bina da listeye girebilmeli. */
const TABAN_ONCELIK = 0.01;
/** `saha/ayarlar.py` YAKINLIK_KM — bu kadar uzaklık puanı yarıya indirir. */
const YAKINLIK_KM = 2.0;
/** `saha/ayarlar.py` LISTE_TASMA — site bütünlüğü için izin verilen taşma. */
const LISTE_TASMA = 5;
/** `saha/rota.py` SINIF_AGIRLIK. */
const SINIF_AGIRLIK: Record<number, number> = { 0: 2.5, 1: 1.0, 2: 0.4 };
/** `saha/rota.py` TOHUM_DENEME. */
const TOHUM_DENEME = 6;

/** Ofis konumu — `saha/ayarlar.py` OFIS ile aynı nokta (Dehanet EÇM, Nilüfer). */
export const OFIS_VARSAYILAN: [number, number] = [40.22043814320989, 28.953528321918512];

function tarih(deger?: string | null): Date | null {
  if (!deger) return null;
  const metin = String(deger).slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(metin)) return null;
  const [y, a, g] = metin.split('-').map(Number);
  const t = new Date(y, a - 1, g);
  return Number.isNaN(t.getTime()) ? null : t;
}

function gunFarki(sonra: Date, once: Date): number {
  return Math.floor((sonra.getTime() - once.getTime()) / 86400000);
}

/** Satışa yeni açılan siteler daha yüksek potansiyel taşır. */
export function yeniSiteCarpani(salesReady: string | null | undefined, bugun: Date): number {
  const acilis = tarih(salesReady);
  if (!acilis) return 1.0;
  let ay = (bugun.getFullYear() - acilis.getFullYear()) * 12 + (bugun.getMonth() - acilis.getMonth());
  if (acilis.getDate() > bugun.getDate()) ay -= 1;
  if (ay < 12) return 1.6;
  if (ay < 24) return 1.3;
  return 1.0;
}

/** Sözü olan bina öne, kapısı kapalı bina geriye. */
export function tekrarCarpani(
  durum: string,
  tekrarTarih: string | null | undefined,
  bugun: Date,
): number {
  if (durum === 'tekrar_gel') {
    const gun = tarih(tekrarTarih);
    return !gun || gun <= bugun ? 1.4 : 1.0;
  }
  if (durum === 'girilemedi') return 0.4;
  if (durum === 'altyapi_sorunu') return 0.2;
  return 1.0;
}

/** Penetrasyon %60 üstü doygun (0,7) · %30 altı bakir (1,2). */
export function doygunlukCarpani(aktifRes: number, resHp: number): number {
  if (!resHp || resHp <= 0) return 1.0;
  const pen = aktifRes / resHp;
  if (pen > 0.6) return 0.7;
  if (pen < 0.3) return 1.2;
  return 1.0;
}

export function oncelikPuani(b: BinaKart, bugun: Date): number {
  const puan =
    (b.firsat || 0) *
    yeniSiteCarpani(b.sales_ready, bugun) *
    tekrarCarpani(b.durum || 'bekliyor', b.tekrar_tarih, bugun) *
    doygunlukCarpani(b.aktif_res || 0, b.res_hp || 0);
  // Taban: fırsatı sıfır olan 666 bina eskiden hiçbir rotaya giremiyordu ve
  // kapsama %96,6'da takılıyordu.
  return Math.max(puan, TABAN_ONCELIK);
}

/**
 * 0 = sözü olan · 1 = hiç dokunulmamış · 2 = tekrar ziyaret.
 * `saha/rota.py oncelik_sinifi` ile aynı.
 */
export function oncelikSinifi(b: BinaKart): number {
  if ((b.durum || 'bekliyor') === 'tekrar_gel') return 0;
  return b.son_ziyaret ? 2 : 1;
}

/** Bina bugünün listesine girebilir mi? (bekliyor · süresi gelmiş tekrar_gel · 30 gün soğuma) */
export function uygunMu(b: BinaKart, bugun: Date): boolean {
  const durum = b.durum || 'bekliyor';
  if (durum === 'bekliyor') return true;
  if (durum === 'planli') return false;
  if (durum === 'tekrar_gel') {
    const gun = tarih(b.tekrar_tarih);
    return !gun || gun <= bugun;
  }
  const son = tarih(b.son_ziyaret);
  if (!son) return true;
  return gunFarki(bugun, son) >= SOGUMA_GUN;
}

/** Neden listeye giremez? Yöneticiye tek cümleyle anlatmak için. */
export function uygunsuzlukNedeni(b: BinaKart, bugun: Date): string | null {
  if (uygunMu(b, bugun)) return null;
  const durum = b.durum || 'bekliyor';
  if (durum === 'planli') return 'Bugün başka bir listede';
  if (durum === 'tekrar_gel') return `${b.tekrar_tarih ?? 'ileri'} tarihinde tekrar gidilecek`;
  return 'Son 30 gün içinde gezildi';
}

/**
 * Algoritmanın seçeceği binalar — `saha/rota.py` `_grup_sec` aynası.
 *
 * Üç kural birlikte çalışır:
 *  1. SINIF: sözü olan → hiç dokunulmamış → tekrar ziyaret. Bölgede yeterince
 *     dokunulmamış bina varken tekrar ziyaret havuza hiç girmez; yoksa sistemin
 *     ana vaadi ("boşlukları doldurmak") çalışmıyor.
 *  2. YAKINLIK: aday puanı, seçilmiş duraklara uzaklığın karesiyle bölünür.
 *     Yalnız puana bakan eski seçim 8. bölgede 78 km'lik turlar kuruyordu.
 *  3. SİTE BÜTÜNLÜĞÜ: bir site ya tamamen girer ya hiç girmez.
 *
 * Gönderim anında sırayı yine sunucu kurar (2-opt turu ordadır); buradaki
 * önizleme aynı binaları, biraz farklı sırayla gösterir.
 */
export function algoritmaSecimi(
  havuz: BinaKart[],
  adet: number,
  bugun: Date,
  baslangic: [number, number] = OFIS_VARSAYILAN,
): BinaKart[] {
  const uygun = havuz
    .filter((b) => uygunMu(b, bugun))
    .map((b) => ({
      ...b,
      oncelik: Math.round(oncelikPuani(b, bugun) * 1000) / 1000,
      sinif: oncelikSinifi(b),
    }));

  // Sınıf güvencesi: yeterince "dokunulmamış / sözü olan" varsa tekrar
  // ziyaretler havuza hiç konmaz.
  const oncelikli = uygun.filter((b) => (b.sinif ?? 1) <= 1);
  const kaynak = oncelikli.length >= Math.max(1, adet) ? oncelikli : uygun;

  const sirali = kaynak.sort(
    (a, b) =>
      (a.sinif ?? 1) - (b.sinif ?? 1) ||
      (b.oncelik ?? 0) - (a.oncelik ?? 0) ||
      a.bina_serial.localeCompare(b.bina_serial),
  );
  if (!sirali.length) return [];

  const gruplar = new Map<string, BinaKart[]>();
  for (const b of sirali) {
    const anahtar = (b.site_grup || '').trim() || `tek:${b.bina_serial}`;
    const liste = gruplar.get(anahtar);
    if (liste) liste.push(b);
    else gruplar.set(anahtar, [b]);
  }

  const bilgi = new Map<
    string,
    { lat: number; lon: number; puan: number; sinif: number; uyeler: BinaKart[] }
  >();
  for (const [anahtar, uyeler] of gruplar) {
    bilgi.set(anahtar, {
      lat: uyeler.reduce((t, u) => t + u.lat, 0) / uyeler.length,
      lon: uyeler.reduce((t, u) => t + u.lon, 0) / uyeler.length,
      puan: uyeler.reduce((t, u) => t + (u.oncelik ?? 0), 0) / uyeler.length,
      sinif: Math.min(...uyeler.map((u) => u.sinif ?? 1)),
      uyeler,
    });
  }

  const tasma = Math.max(1, Math.min(LISTE_TASMA, Math.floor(adet / 5)));

  function zincir(tohum: string | null) {
    const kalan = Array.from(bilgi.keys());
    const secim: BinaKart[] = [];
    const noktalar: Array<[number, number]> = [baslangic];
    let maliyet = 0;
    let ilkKm = 0;
    let puan = 0;

    while (kalan.length && secim.length < adet) {
      const yer = adet - secim.length;
      let enIyi: { i: number; anahtar: number; alinacak: number; km: number } | null = null;
      for (let i = 0; i < kalan.length; i += 1) {
        const g = bilgi.get(kalan[i])!;
        const n = g.uyeler.length;
        let alinacak: number;
        if (n > adet) {
          if (secim.length) continue; // bir günden büyük site yalnız listenin başında bölünür
          alinacak = adet;
        } else if (n > yer + tasma) {
          continue;
        } else {
          alinacak = n;
        }
        const km =
          Math.min(...noktalar.map((n0) => mesafeM(n0[0], n0[1], g.lat, g.lon))) / 1000;
        let anahtar: number;
        if (tohum !== null && !secim.length) {
          if (kalan[i] !== tohum) continue;
          anahtar = 0;
        } else {
          const oran = km / YAKINLIK_KM;
          anahtar = -(
            (g.puan * (SINIF_AGIRLIK[g.sinif] ?? 1)) /
            (1 + oran * oran)
          );
        }
        if (!enIyi || anahtar < enIyi.anahtar) enIyi = { i, anahtar, alinacak, km };
      }
      if (!enIyi) break;
      const anahtar = kalan.splice(enIyi.i, 1)[0];
      const g = bilgi.get(anahtar)!;
      const alinan = g.uyeler.slice(0, enIyi.alinacak);
      if (!secim.length) ilkKm = enIyi.km;
      else maliyet += enIyi.km;
      secim.push(...alinan);
      puan += alinan.reduce((t, u) => t + (u.oncelik ?? 0), 0);
      noktalar.push([g.lat, g.lon]);
    }
    return { secim, maliyet, ilkKm, puan };
  }

  // Birkaç makul tohum denenir; "çok bina, az yol" ölçütüyle en iyisi seçilir.
  const tohumlar = Array.from(bilgi.keys())
    .map((anahtar) => {
      const g = bilgi.get(anahtar)!;
      const km = mesafeM(baslangic[0], baslangic[1], g.lat, g.lon) / 1000;
      const oran = km / (YAKINLIK_KM * 5);
      return { anahtar, skor: (g.puan * (SINIF_AGIRLIK[g.sinif] ?? 1)) / (1 + oran * oran) };
    })
    .sort((a, b) => b.skor - a.skor || a.anahtar.localeCompare(b.anahtar))
    .slice(0, TOHUM_DENEME)
    .map((t) => t.anahtar);

  let enIyiSecim: BinaKart[] = [];
  let enIyiSkor = -Infinity;
  for (const tohum of tohumlar) {
    const { secim, maliyet, ilkKm, puan } = zincir(tohum);
    if (!secim.length) continue;
    const skor = ((puan * secim.length) / adet) / (1 + maliyet / 5 + ilkKm / 25);
    if (skor > enIyiSkor) {
      enIyiSkor = skor;
      enIyiSecim = secim;
    }
  }
  return enIyiSecim.length ? enIyiSecim : zincir(null).secim;
}

/* ------------------------------ Tur sırası ------------------------------ */

const DUNYA_YARICAP_M = 6_371_000;

export function mesafeM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const d = Math.PI / 180;
  const f1 = lat1 * d;
  const f2 = lat2 * d;
  const dlat = f2 - f1;
  const dlon = (lon2 - lon1) * d;
  const a =
    Math.sin(dlat / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dlon / 2) ** 2;
  return 2 * DUNYA_YARICAP_M * Math.asin(Math.sqrt(a));
}

/**
 * Seçilen binaları gezilecek sıraya dizer (`rota.tur_kur` ikinci–üçüncü adımı):
 * siteler başlangıç noktasından en yakın komşu ile sıralanır, site içindeki
 * bloklar da öyle. Sunucu göndermede 2-opt ile biraz daha iyileştirir; burada
 * amaç yöneticinin günü kafasında canlandırabilmesi.
 */
export function turaDiz(
  binalar: BinaKart[],
  baslangic: [number, number],
): Array<BinaKart & { sira: number; mesafe_m: number }> {
  if (!binalar.length) return [];

  const gruplar = new Map<string, BinaKart[]>();
  for (const b of binalar) {
    const anahtar = (b.site_grup || '').trim() || `tek:${b.bina_serial}`;
    const liste = gruplar.get(anahtar);
    if (liste) liste.push(b);
    else gruplar.set(anahtar, [b]);
  }

  const duraklar = Array.from(gruplar.values()).map((uyeler) => ({
    uyeler,
    lat: uyeler.reduce((t, u) => t + u.lat, 0) / uyeler.length,
    lon: uyeler.reduce((t, u) => t + u.lon, 0) / uyeler.length,
  }));

  const cikti: Array<BinaKart & { sira: number; mesafe_m: number }> = [];
  let konum = baslangic;
  const kalan = new Set(duraklar.keys());

  while (kalan.size) {
    let enIyi = -1;
    let enKisa = Infinity;
    for (const i of kalan) {
      const d = mesafeM(konum[0], konum[1], duraklar[i].lat, duraklar[i].lon);
      if (d < enKisa) {
        enKisa = d;
        enIyi = i;
      }
    }
    kalan.delete(enIyi);

    const uyeler = [...duraklar[enIyi].uyeler];
    while (uyeler.length) {
      let yakinIndeks = 0;
      let yakinMesafe = Infinity;
      for (let j = 0; j < uyeler.length; j++) {
        const d = mesafeM(konum[0], konum[1], uyeler[j].lat, uyeler[j].lon);
        if (d < yakinMesafe) {
          yakinMesafe = d;
          yakinIndeks = j;
        }
      }
      const [bina] = uyeler.splice(yakinIndeks, 1);
      cikti.push({ ...bina, sira: cikti.length + 1, mesafe_m: Math.round(yakinMesafe) });
      konum = [bina.lat, bina.lon];
    }
  }
  return cikti;
}
