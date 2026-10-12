/**
 * Sunucu ile konuşan tek yer.
 *
 * Uygulama HER ZAMAN gerçek API ile konuşur (`/api/...`, aynı sunucudan).
 *
 * Örnek (sahte) veri yalnız iki yerde vardır: `npm run dev` ile geliştirirken ve
 * `npm run build:sahte` ile alınan DEMO derlemesinde. Ofise kurulan normal
 * derlemede (`npm run build`) sahte veri koda hiç girmez — saha ekibinin
 * uydurma bir listeyi gerçek sanması mümkün değildir.
 */

import type { ApiHatasi } from './tipler';

const JETON_ANAHTARI = 'saha.jeton';
const SAHTE_ANAHTARI = 'saha.sahte';

export class SahaHatasi extends Error {
  kod: string;
  durum: number;
  constructor(mesaj: string, kod = 'bilinmeyen', durum = 0) {
    super(mesaj);
    this.name = 'SahaHatasi';
    this.kod = kod;
    this.durum = durum;
  }
  /** Ağ kaynaklı mı? (kuyruk bunu yeniden denemeli) */
  get agHatasi() {
    return this.kod === 'ag_yok' || this.durum === 0 || this.durum >= 500;
  }
}

function yerelOku(anahtar: string): string | null {
  try {
    return localStorage.getItem(anahtar);
  } catch {
    return null;
  }
}

function yerelYaz(anahtar: string, deger: string | null) {
  try {
    if (deger === null) localStorage.removeItem(anahtar);
    else localStorage.setItem(anahtar, deger);
  } catch {
    /* gizli sekmede yazılamayabilir — uygulama yine çalışır */
  }
}

/* ------------------------------ Sahte veri anahtarı ------------------------------ */

function sahteModuCoz(): boolean {
  try {
    const adres = new URL(window.location.href);
    const istek = adres.searchParams.get('sahte');
    if (istek === '1') {
      yerelYaz(SAHTE_ANAHTARI, '1');
      return true;
    }
    if (istek === '0') {
      yerelYaz(SAHTE_ANAHTARI, null);
      return false;
    }
  } catch {
    /* adres okunamazsa saklanan tercihe bak */
  }
  return yerelOku(SAHTE_ANAHTARI) === '1';
}

/**
 * Sahte veri kipi. `import.meta.env` değerleri derleme sırasında sabite
 * çevrildiği için normal derlemede bu ifade düz `false` olur ve `sahte.ts`
 * pakete hiç girmez.
 */
export const SAHTE_IZIN = import.meta.env.DEV || import.meta.env.VITE_SAHTE === '1';

export const sahteMod = SAHTE_IZIN ? sahteModuCoz() : false;

/* ------------------------------ Oturum jetonu ------------------------------ */

let jeton: string | null = yerelOku(JETON_ANAHTARI);

export function jetonuAl() {
  return jeton;
}

export function jetonuYaz(yeni: string | null) {
  jeton = yeni;
  yerelYaz(JETON_ANAHTARI, yeni);
}

/** 401 geldiğinde uygulamanın giriş ekranına dönmesi için. */
type OturumBittiDinleyici = () => void;
const oturumBittiDinleyiciler = new Set<OturumBittiDinleyici>();

export function oturumBitinceDinle(dinleyici: OturumBittiDinleyici) {
  oturumBittiDinleyiciler.add(dinleyici);
  return () => oturumBittiDinleyiciler.delete(dinleyici);
}

function oturumBitti() {
  jetonuYaz(null);
  oturumBittiDinleyiciler.forEach((d) => d());
}

/* ------------------------------ İstek ------------------------------ */

interface IstekSecenekleri {
  /** PATCH/PUT yalnız yönetici uçlarında (ticket güncelleme, altlık ayarı). */
  yontem?: 'GET' | 'POST' | 'PATCH' | 'PUT';
  govde?: unknown;
  /** Jeton gerekmiyor (giriş uçları). */
  acik?: boolean;
  zamanAsimiMs?: number;
  isaret?: AbortSignal;
}

export async function istek<T>(yol: string, secenek: IstekSecenekleri = {}): Promise<T> {
  const { yontem = 'GET', govde, acik = false, zamanAsimiMs = 15000, isaret } = secenek;

  if (!acik && !jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);

  const basliklar: Record<string, string> = { Accept: 'application/json' };
  if (govde !== undefined) basliklar['Content-Type'] = 'application/json';
  if (!acik && jeton) basliklar.Authorization = `Bearer ${jeton}`;

  const denetleyici = new AbortController();
  const sayac = setTimeout(() => denetleyici.abort(), zamanAsimiMs);
  if (isaret) isaret.addEventListener('abort', () => denetleyici.abort(), { once: true });

  let yanit: Response;
  try {
    yanit = await fetch(yol, {
      method: yontem,
      headers: basliklar,
      body: govde === undefined ? undefined : JSON.stringify(govde),
      signal: denetleyici.signal,
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok', 'ag_yok', 0);
  } finally {
    clearTimeout(sayac);
  }

  // 401 iki ayrı şey demek olabilir ve ikisi ÇOK farklı:
  //   · giriş uçlarında: "PIN hatalı" — kullanıcı ekranda zaten duruyor.
  //   · diğer uçlarda: oturum gerçekten düştü, giriş ekranına dönmeli.
  // Eskiden ikisi de "Oturum süresi doldu, tekrar giriş yapın." yazıyordu;
  // yanlış PIN giren kişi ne olduğunu anlamıyor, tekrar deniyor ve hesabını
  // kilitletiyordu.
  const girisUcu = yol.startsWith('/api/giris') || yol.startsWith('/api/pin');
  if (yanit.status === 401 && !girisUcu) {
    oturumBitti();
    throw new SahaHatasi('Güvenlik için çıkış yapıldı. Tekrar giriş yapın.', 'oturum_bitti', 401);
  }

  const metin = await yanit.text();
  let veri: unknown = null;
  if (metin) {
    try {
      veri = JSON.parse(metin);
    } catch {
      veri = null;
    }
  }

  if (!yanit.ok) {
    const hata = (veri ?? {}) as ApiHatasi;
    throw new SahaHatasi(hata.hata || 'Bir şeyler ters gitti.', hata.kod || 'sunucu', yanit.status);
  }

  return veri as T;
}
