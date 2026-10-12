/**
 * Haritada gerçekten çizilecek noktaları seçer.
 *
 * Neden: bölge haritasında ~2.400, şehir genelinde 19.706 bina var. Hepsini her
 * karede telefona çizdirmek orta sınıf bir Android'i ısıtır ve kaydırma takılır.
 * Ayrıca uzaklaşınca noktalar zaten üst üste biner — ekranda görünen bilgi
 * artmaz, yalnız iş artar.
 *
 * Yaptığı iş iki adım:
 *   1. Görünen alanın (biraz payla) dışında kalanları at. Asıl kazanç budur:
 *      yakınlaşmış bir haritada 19.706 noktanın 200'ü çizilir.
 *   2. Kalan hâlâ bütçeden fazlaysa ekranı ızgaraya böl, her gözden bir nokta
 *      bırak. Bugünkü veride (bölgede ~3.000, şehirde 19.706 bina) bu adım hiç
 *      çalışmaz; v2'deki 180 bin kapı için emniyet supabıdır.
 *
 * SEYRELTME AYRIM YAPMAZ. "Dokunulmuş noktayı tercih et" gibi bir kural
 * konulursa yöneticinin kapsama haritası olduğundan yeşil görünür — yani
 * "nereye gitmedik" sorusuna yanlış cevap verir. Renk oranları korunmalı.
 *
 * Yakınlaşınca eksik hiçbir şey olmaz: göz küçüldükçe bütçe rahatlar, bütün
 * binalar geri gelir.
 */

export type Kutu = [number, number, number, number]; // [lon1, lat1, lon2, lat2]

/** Görünen alanı biraz payla genişletir; kaydırırken kenarda boşluk olmasın. */
export function kutuyuGenislet(kutu: Kutu, oran = 0.25): Kutu {
  const [lon1, lat1, lon2, lat2] = kutu;
  const px = (lon2 - lon1) * oran;
  const py = (lat2 - lat1) * oran;
  return [lon1 - px, lat1 - py, lon2 + px, lat2 + py];
}

interface AyiklaSecenekleri<T> {
  /** Noktanın [lon, lat] konumu. */
  konum: (n: T) => readonly [number, number];
  /** Görünen alan; verilmezse hiçbir şey elenmez. */
  kutu?: Kutu | null;
  /** Aynı anda çizilecek en fazla nokta (emniyet supabı). */
  enFazla?: number;
}

/** Görünen ve bütçeye sığan noktaları döndürür. */
export function ayikla<T>(noktalar: readonly T[], secenek: AyiklaSecenekleri<T>): T[] {
  const { konum, kutu, enFazla = 25000 } = secenek;

  let gorunen: T[];
  if (!kutu) {
    gorunen = noktalar as T[];
  } else {
    const [lon1, lat1, lon2, lat2] = kutu;
    gorunen = [];
    for (const n of noktalar) {
      const [lon, lat] = konum(n);
      if (lon >= lon1 && lon <= lon2 && lat >= lat1 && lat <= lat2) gorunen.push(n);
    }
  }
  if (gorunen.length <= enFazla) return gorunen;

  // Izgara: hedef sayı kadar göz. Her gözde ilk gelen nokta kalır — durum,
  // fırsat gibi hiçbir ölçüte bakılmaz ki renk dağılımı bozulmasın.
  const [lon1, lat1, lon2, lat2] = kutu ?? sinirlariBul(gorunen, konum);
  const genislik = Math.max(lon2 - lon1, 1e-9);
  const yukseklik = Math.max(lat2 - lat1, 1e-9);
  const bolme = Math.max(1, Math.ceil(Math.sqrt(enFazla)));

  const gozler = new Map<number, T>();
  for (const n of gorunen) {
    const [lon, lat] = konum(n);
    const gx = Math.min(bolme - 1, Math.max(0, Math.floor(((lon - lon1) / genislik) * bolme)));
    const gy = Math.min(bolme - 1, Math.max(0, Math.floor(((lat - lat1) / yukseklik) * bolme)));
    const anahtar = gy * bolme + gx;
    if (!gozler.has(anahtar)) gozler.set(anahtar, n);
  }
  return [...gozler.values()];
}

function sinirlariBul<T>(liste: readonly T[], konum: (n: T) => readonly [number, number]): Kutu {
  let lon1 = Infinity;
  let lat1 = Infinity;
  let lon2 = -Infinity;
  let lat2 = -Infinity;
  for (const n of liste) {
    const [lon, lat] = konum(n);
    if (lon < lon1) lon1 = lon;
    if (lon > lon2) lon2 = lon;
    if (lat < lat1) lat1 = lat;
    if (lat > lat2) lat2 = lat;
  }
  return [lon1, lat1, lon2, lat2];
}

/** Yol çizgilerinden görünen alana değmeyenleri atar (arka plan da pahalıdır). */
export function cizgileriAyikla<T extends { yol: Array<readonly [number, number]> }>(
  cizgiler: readonly T[],
  kutu: Kutu | null,
  enFazla = 4000,
): T[] {
  if (!kutu) return (cizgiler as T[]).slice(0, enFazla);
  const [lon1, lat1, lon2, lat2] = kutu;
  const kalan: T[] = [];
  for (const c of cizgiler) {
    let ax = Infinity;
    let ay = Infinity;
    let bx = -Infinity;
    let by = -Infinity;
    for (const [lon, lat] of c.yol) {
      if (lon < ax) ax = lon;
      if (lon > bx) bx = lon;
      if (lat < ay) ay = lat;
      if (lat > by) by = lat;
    }
    if (bx < lon1 || ax > lon2 || by < lat1 || ay > lat2) continue;
    kalan.push(c);
    if (kalan.length >= enFazla) break;
  }
  return kalan;
}

/* ---------------------------- Sınırlar ---------------------------- */

export type NoktaKonum = [number, number]; // [lon, lat]

/** Noktaların tam kapsayan kutusu: [[enKüçükLon, enKüçükLat], [enBüyük…]]. */
export function sinirlar(konumlar: readonly NoktaKonum[]): [NoktaKonum, NoktaKonum] | null {
  if (!konumlar.length) return null;
  let kLon = Infinity;
  let kLat = Infinity;
  let bLon = -Infinity;
  let bLat = -Infinity;
  for (const [lon, lat] of konumlar) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    if (lon < kLon) kLon = lon;
    if (lat < kLat) kLat = lat;
    if (lon > bLon) bLon = lon;
    if (lat > bLat) bLat = lat;
  }
  if (!Number.isFinite(kLon)) return null;
  return [
    [kLon, kLat],
    [bLon, bLat],
  ];
}

/**
 * Uçtaki birkaç noktayı DIŞARIDA bırakan sınırlar (%2–%98).
 *
 * Bursa'nın uçlarında (Yalova, İnegöl, Orhangazi) birkaç yüz bina var; bir
 * bölgenin birkaç uzak binası da olabiliyor. Düz min–max alınırsa harita o
 * kadar uzaklaşır ki yoğun merkez avuç içi bir lekeye döner — ekranın çoğu boş
 * kalır. %2–%98 aralığı ekranı binaların çoğunluğuna ayırır; uçtakiler yine
 * haritada durur, kaydırınca görünür.
 */
export function govdeSinirlari(
  konumlar: readonly NoktaKonum[],
  pay = 0.02,
): [NoktaKonum, NoktaKonum] | null {
  const lonlar: number[] = [];
  const latlar: number[] = [];
  for (const [lon, lat] of konumlar) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    lonlar.push(lon);
    latlar.push(lat);
  }
  if (!lonlar.length) return null;
  // Az sayıda nokta varsa kırpmak bilgi kaybı olur; hepsi sığsın.
  if (lonlar.length < 40) return sinirlar(konumlar);

  lonlar.sort((a, b) => a - b);
  latlar.sort((a, b) => a - b);
  const alt = Math.floor(lonlar.length * pay);
  const ust = Math.min(lonlar.length - 1, Math.ceil(lonlar.length * (1 - pay)));
  return [
    [lonlar[alt], latlar[alt]],
    [lonlar[ust], latlar[ust]],
  ];
}
