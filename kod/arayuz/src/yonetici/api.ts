/**
 * Yönetici uçları — sözleşme §3 "Yönetici".
 *
 * Satışçı tarafındaki `src/api/istemci.ts` (jeton, hata biçimi, 401 → giriş)
 * aynen kullanılır; burada yalnız yöneticiye açık yollar tanımlanır.
 */

import { istek, jetonuAl, SahaHatasi } from '../api/istemci';
import { gunMetni } from '../ortak/bicim';
import type { Rol, Ticket } from '../api/tipler';
import type {
  KullaniciIliskileri,
  RehberSonucu,
  UnvanKurali,
  AtamaIstegi,
  AtamaYaniti,
  BekleyenListesi,
  BinaDegisimleri,
  BinaListesiYaniti,
  BolgelemeDurumu,
  GeriAlmaYaniti,
  GorevYaniti,
  GunOzetiYaniti,
  HesapIsi,
  KaliteListesi,
  KaliteOzeti,
  KapsamaYaniti,
  KullaniciKaydiYaniti,
  OneMapYaniti,
  PinSifirlamaYaniti,
  PlanHesaplaniyor,
  PlanOlcusu,
  PlanOnizlemesi,
  PlanUygulamaYaniti,
  TicketAyrintisi,
  TicketGirdisi,
  TicketGuncelleme,
  TicketListesi,
  TurListesi,
  TurOnizlemesi,
  TurUygulamaYaniti,
  YoneticiHaritaVerisi,
  YoneticiKullanici,
} from './tipler';

function sorgu(alanlar: Record<string, string | number | null | undefined>): string {
  const parcalar = Object.entries(alanlar)
    .filter(([, d]) => d !== null && d !== undefined && d !== '')
    .map(([a, d]) => `${a}=${encodeURIComponent(String(d))}`);
  return parcalar.length ? `?${parcalar.join('&')}` : '';
}

export interface YardimAyari {
  yardim_telefon?: string | null;
  yardim_ad?: string | null;
}

/** Giriş ekranında görünecek "Yöneticini ara" numarası. */
export function yardimOku(): Promise<YardimAyari> {
  return istek<YardimAyari>('/api/ayar');
}

export function yardimYaz(deger: YardimAyari): Promise<YardimAyari> {
  return istek<YardimAyari>('/api/ayar', { yontem: 'POST', govde: deger });
}

/** Gün özeti: satışçı bazında ziyaret/satış/ret/randevu/kalan. */
export function gunOzeti(tarih?: string): Promise<GunOzetiYaniti> {
  return istek<GunOzetiYaniti>(`/api/ozet/gun${sorgu({ tarih })}`, { zamanAsimiMs: 20000 });
}

/** Kapsama: bölge / mahalle / ilçe kırılımında dokunulan–kalan. */
export function kapsama(
  kirilim: 'bolge' | 'mahalle' | 'ilce' = 'bolge',
  bolge?: number | null,
): Promise<KapsamaYaniti> {
  return istek<KapsamaYaniti>(`/api/ozet/kapsama${sorgu({ kirilim, bolge })}`, {
    zamanAsimiMs: 30000,
  });
}

/** Bütün şehrin harita noktaları (bolge verilmezse 19.706 bina). */
export function harita(bolge?: number | null): Promise<YoneticiHaritaVerisi> {
  return istek<YoneticiHaritaVerisi>(`/api/harita${sorgu({ bolge })}`, { zamanAsimiMs: 60000 });
}

/** Bina listesi / arama. Aday havuzu için `limit` yükseltilir. */
export function binalar(secenek: {
  bolge?: number | null;
  durum?: string;
  mahalle?: string;
  q?: string;
  limit?: number;
  offset?: number;
}): Promise<BinaListesiYaniti> {
  return istek<BinaListesiYaniti>(`/api/bina${sorgu(secenek)}`, { zamanAsimiMs: 45000 });
}

/** Bir satışçının o günkü listesi (yönetici başkasınınkini de görebilir). */
export async function gorev(kullanici_id: number, tarih?: string): Promise<GorevYaniti | null> {
  try {
    return await istek<GorevYaniti>(`/api/gorev/bugun${sorgu({ kullanici_id, tarih })}`);
  } catch (h) {
    if (h instanceof SahaHatasi && h.durum === 404) return null;
    throw h;
  }
}

/** Görev atama — "Trendyol Go'ya paket düşer gibi". */
export function gorevAta(istekGovdesi: AtamaIstegi): Promise<AtamaYaniti> {
  return istek<AtamaYaniti>('/api/gorev/ata', {
    yontem: 'POST',
    govde: istekGovdesi,
    zamanAsimiMs: 45000,
  });
}

/* ------------------------------ Ekip ------------------------------ */

export async function kullanicilar(): Promise<YoneticiKullanici[]> {
  const yanit = await istek<{ kullanicilar: YoneticiKullanici[] }>('/api/kullanici');
  return yanit.kullanicilar;
}

/** Tek kişi: tam telefon yalnız burada gelir (listede maskeli). */
export async function kullaniciGetir(id: number): Promise<YoneticiKullanici> {
  const yanit = await istek<{ kullanici: YoneticiKullanici }>(`/api/kullanici/${id}`);
  return yanit.kullanici;
}

export interface KullaniciGirdisi {
  id?: number;
  ad: string;
  /** Boş/null → girişsiz kişi (EK-2: BOSS Mobil ile çalışan teknisyen). */
  telefon: string | null;
  /** ANA görev (girişte açılan ekran). */
  rol: Rol;
  /** EK-1: görev kümesi (ana görev dahil). */
  gorevler?: Rol[];
  bolge?: number | null;
  etiket?: string[] | null;
  boss_ekip?: string | null;
  kapasite?: number | null;
  unvan?: string | null;
  aktif?: boolean;
}

export function kullaniciKaydet(girdi: KullaniciGirdisi): Promise<KullaniciKaydiYaniti> {
  return istek<KullaniciKaydiYaniti>('/api/kullanici', { yontem: 'POST', govde: girdi });
}

/** "Görevleri gözden geçirin" kartı: toplu görev değişikliği, tek işlem. */
export function gorevleriKaydet(girdi: {
  degisiklikler: Array<{ id: number; rol: Rol; gorevler?: Rol[]; bolge?: number | null }>;
  tamam: boolean;
}): Promise<{ degisen: number }> {
  return istek('/api/kullanici/gorevler', { yontem: 'POST', govde: girdi });
}

export function pinSifirla(id: number): Promise<PinSifirlamaYaniti> {
  return istek<PinSifirlamaYaniti>(`/api/kullanici/${id}/pin-sifirla`, { yontem: 'POST' });
}

/** Yeni 6 haneli davet kodu (48 saat geçerli); YALNIZ bu yanıtta görünür. */
export function davetKoduVer(id: number): Promise<{ davet_kodu: string; gecerlilik: string; gecerlilik_bitis?: string }> {
  return istek(`/api/kullanici/${id}/davet`, { yontem: 'POST' });
}

/** Bütün cihazlarından çıkış (PIN değişmez). */
export function cihazCikis(id: number): Promise<{ mesaj: string }> {
  return istek(`/api/kullanici/${id}/cihaz-cikis`, { yontem: 'POST' });
}

export function kullaniciIliskileri(id: number): Promise<KullaniciIliskileri> {
  return istek<KullaniciIliskileri>(`/api/kullanici/${id}/iliskiler`);
}

/**
 * Kişiyi siler (yalnız kaydı olmayan). `istek` DELETE bilmediği için burada
 * yazıldı; hata biçimi aynıdır (409 `iliskili_kayit` + sayılar).
 */
export async function kullaniciSil(id: number, obekleriBirak = false): Promise<void> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch(`/api/kullanici/${id}?obekleri_birak=${obekleriBirak ? 1 : 0}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${jeton}`, Accept: 'application/json' },
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok', 'ag_yok', 0);
  }
  if (yanit.ok) return;
  let govde: { hata?: string; kod?: string } = {};
  try {
    govde = await yanit.json();
  } catch {
    /* gövdesiz hata */
  }
  throw new SahaHatasi(govde.hata || 'Silinemedi.', govde.kod || 'sunucu', yanit.status);
}

/** Açık işleri başka bir teknik kişiye aktarır (her iş kendi olayıyla). */
export function isAktar(id: number, hedefId: number): Promise<{ toplu_id: string; aktarilan: number }> {
  return istek(`/api/kullanici/${id}/is-aktar`, { yontem: 'POST', govde: { hedef_id: hedefId } });
}

/** Personel rehberi (Atmosfer/Pusula "Çalışanlar" listesi): önce önizleme, sonra uygula. */
export function rehberAktar(metin: string, uygula: boolean): Promise<RehberSonucu> {
  return istek<RehberSonucu>('/api/kullanici/rehber', {
    yontem: 'POST',
    govde: { metin, uygula },
    zamanAsimiMs: 30000,
  });
}

/** Bugün "çalışmıyor" işaretli teknik kişiler (GET /api/isler/teknikler → bugun_yok; spec §6.10). */
export async function bugunCalismayanlar(): Promise<Set<number>> {
  const y = await istek<Array<{ id: number; bugun_yok: boolean }>>('/api/isler/teknikler');
  return new Set(y.filter((t) => t.bugun_yok).map((t) => t.id));
}

/** "Bugün çalışmıyor" anahtarı — yalnız bugünü etkiler; ertesi gün kendiliğinden kalkar. */
export function bugunCalismiyorYaz(id: number, yok: boolean): Promise<{ teknik_id: number; tarih: string; bugun_yok: boolean }> {
  return istek(`/api/isler/teknikler/${id}/bugun-yok`, { yontem: 'PUT', govde: { yok } });
}

export async function unvanEslemeOku(): Promise<UnvanKurali[]> {
  const y = await istek<{ esleme: UnvanKurali[] }>('/api/kullanici/rehber/esleme');
  return y.esleme;
}

export async function unvanEslemeYaz(esleme: UnvanKurali[]): Promise<UnvanKurali[]> {
  const y = await istek<{ esleme: UnvanKurali[] }>('/api/kullanici/rehber/esleme', {
    yontem: 'PUT',
    govde: { esleme },
  });
  return y.esleme;
}

/* ------------------------------ Rapor dosyası ------------------------------ */

/**
 * Günlük Excel'i indirir.
 *
 * `istek()` yalnız JSON okuduğu için dosya burada elle çekilir: jeton başlığı
 * gerektiğinden düz `<a download>` bağlantısı iş görmez.
 */
export async function raporIndir(tarih?: string): Promise<string> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);

  let yanit: Response;
  try {
    yanit = await fetch(`/api/dosya/rapor.xlsx${sorgu({ tarih })}`, {
      headers: { Authorization: `Bearer ${jeton}` },
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok', 'ag_yok', 0);
  }
  if (!yanit.ok) {
    throw new SahaHatasi('Rapor indirilemedi.', 'rapor_yok', yanit.status);
  }

  const veri = await yanit.blob();
  const ad = `Saha_Gun_Raporu_${tarih ?? bugunMetni()}.xlsx`;
  const adres = URL.createObjectURL(veri);
  const bag = document.createElement('a');
  bag.href = adres;
  bag.download = ad;
  document.body.appendChild(bag);
  bag.click();
  bag.remove();
  // Tarayıcı indirmeyi başlatana kadar adres yaşamalı.
  setTimeout(() => URL.revokeObjectURL(adres), 30000);
  return ad;
}

export function bugunMetni(gun: Date = new Date()): string {
  return gunMetni(gun);
}

/** `2026-09-21` → `2026-09-22` (gün ekle/çıkar). */
export function gunEkle(tarih: string, adim: number): string {
  const [y, a, g] = tarih.split('-').map(Number);
  const t = new Date(y, a - 1, g);
  t.setDate(t.getDate() + adim);
  return bugunMetni(t);
}

/* =========================================================================
   Faz 2 uçları (sözleşme §7) — hepsi yönetici; satışçı 403 alır.
   ========================================================================= */

/**
 * Jetonlu dosya indirme. `<a download>` jeton başlığı gönderemediği için dosya
 * burada çekilir; ad önce sunucunun `Content-Disposition` başlığından alınır.
 */
async function dosyaIndir(yol: string, yedekAd: string, zamanAsimiMs = 120000): Promise<string> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  const denetleyici = new AbortController();
  const sayac = setTimeout(() => denetleyici.abort(), zamanAsimiMs);
  let yanit: Response;
  try {
    yanit = await fetch(yol, {
      headers: { Authorization: `Bearer ${jeton}` },
      credentials: 'same-origin',
      cache: 'no-store',
      signal: denetleyici.signal,
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok ya da sunucu yanıt vermedi.', 'ag_yok', 0);
  } finally {
    clearTimeout(sayac);
  }
  if (!yanit.ok) {
    const govde = await yanit.json().catch(() => null);
    throw new SahaHatasi(govde?.hata || 'Dosya indirilemedi.', govde?.kod || 'dosya_yok', yanit.status);
  }
  const baslik = yanit.headers.get('content-disposition') ?? '';
  const eslesme = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(baslik);
  const ad = eslesme ? decodeURIComponent(eslesme[1] ?? eslesme[2]) : yedekAd;
  const adres = URL.createObjectURL(await yanit.blob());
  const bag = document.createElement('a');
  bag.href = adres;
  bag.download = ad;
  document.body.appendChild(bag);
  bag.click();
  bag.remove();
  setTimeout(() => URL.revokeObjectURL(adres), 30000);
  return ad;
}

/**
 * Dosyayı olduğu gibi (ham gövde) gönderir; sunucu hem multipart hem ham gövde
 * kabul ediyor. Ham gövde 80 MB'lık raporu belleğe iki kez almaz.
 */
async function dosyaGonder<T>(yol: string, dosya: File, zamanAsimiMs = 180000): Promise<T> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  const denetleyici = new AbortController();
  const sayac = setTimeout(() => denetleyici.abort(), zamanAsimiMs);
  let yanit: Response;
  try {
    yanit = await fetch(yol, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${jeton}`,
        Accept: 'application/json',
        'Content-Type': 'application/octet-stream',
        'X-Dosya-Adi': encodeURIComponent(dosya.name),
      },
      body: dosya,
      credentials: 'same-origin',
      cache: 'no-store',
      signal: denetleyici.signal,
    });
  } catch {
    throw new SahaHatasi('Dosya gönderilemedi: bağlantı yok ya da sunucu yanıt vermedi.', 'ag_yok', 0);
  } finally {
    clearTimeout(sayac);
  }
  const veri = await yanit.json().catch(() => null);
  if (!yanit.ok) {
    throw new SahaHatasi(veri?.hata || 'Dosya işlenemedi.', veri?.kod || 'sunucu', yanit.status);
  }
  return veri as T;
}

/* ------------------------------ Sağlık (bölge sayısı) ------------------------------ */

/** Etkin bölge sayısı: plan uygulanınca 8'den farklı olabilir (§7.7). */
export async function bolgeSayisiOku(): Promise<number> {
  const s = await istek<{ bolge_sayisi?: number }>('/api/saglik', { acik: true, zamanAsimiMs: 8000 });
  return Math.max(1, Number(s?.bolge_sayisi) || 8);
}

/* ------------------------------ Veri kalitesi ------------------------------ */

export function kaliteOzeti(bolge?: number | null): Promise<KaliteOzeti> {
  return istek<KaliteOzeti>(`/api/kalite/ozet${sorgu({ bolge })}`, { zamanAsimiMs: 30000 });
}

export function kaliteListesi(secenek: {
  kural?: string | null;
  bolge?: number | null;
  seviye?: 'bilgi' | 'uyari' | null;
  limit?: number;
  offset?: number;
}): Promise<KaliteListesi> {
  return istek<KaliteListesi>(`/api/kalite/liste${sorgu(secenek)}`, { zamanAsimiMs: 30000 });
}

export function kaliteYenile(): Promise<{ bina: number; bayrakli: number; duzeltilen: number; mesaj: string }> {
  return istek('/api/kalite/yenile', { yontem: 'POST', zamanAsimiMs: 120000 });
}

export function binaDegisimleri(serial: string): Promise<BinaDegisimleri> {
  return istek<BinaDegisimleri>(`/api/bina/${encodeURIComponent(serial)}/degisim`);
}

/* ------------------------------ Bölge planlayıcı ------------------------------ */

export function bolgelemeDurumu(): Promise<BolgelemeDurumu> {
  return istek<BolgelemeDurumu>('/api/bolgeleme/durum', { zamanAsimiMs: 30000 });
}

/** Plan hazırsa önizleme (200), yoksa arka planda hesap başlar (202 → `hazir:false`). */
export function bolgelemeOnizle(
  n: number,
  olcu: PlanOlcusu = 'res_hp',
  hesapla = false,
): Promise<PlanOnizlemesi | PlanHesaplaniyor> {
  return istek<PlanOnizlemesi | PlanHesaplaniyor>(
    `/api/bolgeleme/onizleme${sorgu({ n, olcu, hesapla: hesapla ? 1 : null })}`,
    { zamanAsimiMs: 60000 },
  );
}

export function hesapIsi(isId: string): Promise<HesapIsi> {
  return istek<HesapIsi>(`/api/bolgeleme/is/${encodeURIComponent(isId)}`);
}

export function planUygula(girdi: {
  n: number;
  plan_ref: string;
  pasiflestir?: boolean;
  notu?: string;
}): Promise<PlanUygulamaYaniti> {
  return istek<PlanUygulamaYaniti>('/api/bolgeleme/uygula', {
    yontem: 'POST',
    govde: girdi,
    zamanAsimiMs: 120000,
  });
}

export function planGeriAl(): Promise<GeriAlmaYaniti> {
  return istek<GeriAlmaYaniti>('/api/bolgeleme/geri-al', { yontem: 'POST', zamanAsimiMs: 120000 });
}

/** Etkin planın açıklayıcı Excel'i. İlk üretim 15-30 sn sürer. */
export function planExceliIndir(n: number, planId?: number | null): Promise<string> {
  return dosyaIndir(
    `/api/bolgeleme/excel${sorgu({ plan_id: planId })}`,
    `Bursa_${n}_Satisci_Bolgeleme.xlsx`,
    180000,
  );
}

/* ------------------------------ Tur raporu / OneMap ------------------------------ */

export function turRaporuYukle(dosya: File): Promise<TurOnizlemesi> {
  return dosyaGonder<TurOnizlemesi>('/api/veri/tur-raporu', dosya);
}

export function turRaporlari(): Promise<TurListesi> {
  return istek<TurListesi>('/api/veri/tur-raporu');
}

export function turRaporu(turId: number): Promise<TurOnizlemesi> {
  return istek<TurOnizlemesi>(`/api/veri/tur-raporu/${turId}`);
}

export function turRaporuUygula(girdi: {
  tur_id: number;
  pasif_onay?: boolean;
  iller?: string[] | null;
}): Promise<TurUygulamaYaniti> {
  return istek<TurUygulamaYaniti>('/api/veri/tur-raporu/uygula', {
    yontem: 'POST',
    govde: girdi,
    zamanAsimiMs: 180000,
  });
}

export function bekleyenBinalar(
  durum: 'konum_bekliyor' | 'eklendi' | 'rapordan_cikti' = 'konum_bekliyor',
): Promise<BekleyenListesi> {
  return istek<BekleyenListesi>(`/api/veri/bekleyen${sorgu({ durum })}`);
}

/** OneMap aracına verilecek kimlik dosyası (satır başına bir kimlik). */
export function bekleyenKimlikleriIndir(): Promise<string> {
  return dosyaIndir('/api/veri/bekleyen.txt', 'bekleyen_idler.txt');
}

/** OneMap aracının metni — panoya kopyalanıp tarayıcı konsoluna yapıştırılır. */
export async function oneMapAraciMetni(): Promise<string> {
  const jeton = jetonuAl();
  if (!jeton) throw new SahaHatasi('Oturum kapalı', 'yetkisiz', 401);
  let yanit: Response;
  try {
    yanit = await fetch('/api/veri/onemap-araci.js', {
      headers: { Authorization: `Bearer ${jeton}` },
      credentials: 'same-origin',
      cache: 'no-store',
    });
  } catch {
    throw new SahaHatasi('Bağlantı yok', 'ag_yok', 0);
  }
  if (!yanit.ok) throw new SahaHatasi('OneMap aracı bulunamadı.', 'arac_yok', yanit.status);
  return yanit.text();
}

export function oneMapAraciIndir(): Promise<string> {
  return dosyaIndir('/api/veri/onemap-araci.js', 'onemap_cek.js');
}

export function oneMapYukle(dosya: File): Promise<OneMapYaniti> {
  return dosyaGonder<OneMapYaniti>('/api/veri/onemap', dosya);
}

/* ------------------------------ Ticket defteri ------------------------------ */

export function ticketListesi(secenek: {
  durum?: string | null;
  konu?: string | null;
  kanal?: string | null;
  q?: string | null;
  bina_serial?: string | null;
  acik?: boolean | null;
  bolge?: number | null;
  limit?: number;
  offset?: number;
}): Promise<TicketListesi> {
  const { acik, ...kalan } = secenek;
  return istek<TicketListesi>(
    `/api/ticket${sorgu({ ...kalan, acik: acik == null ? null : String(acik) })}`,
    { zamanAsimiMs: 30000 },
  );
}

/**
 * Bütün defter (500'lük sayfalarla). Defter birkaç yüz satır; süzgeçler ekranda
 * anında çalışsın diye hepsi bir kez indirilir.
 */
export async function tumTicketlar(): Promise<TicketListesi> {
  const ilk = await ticketListesi({ limit: 500, offset: 0 });
  const hepsi = [...ilk.ticketlar];
  let offset = hepsi.length;
  for (let tur = 0; tur < 40 && offset < ilk.toplam; tur++) {
    const sonraki = await ticketListesi({ limit: 500, offset });
    if (!sonraki.ticketlar.length) break;
    hepsi.push(...sonraki.ticketlar);
    offset += sonraki.ticketlar.length;
  }
  return { ...ilk, ticketlar: hepsi, limit: hepsi.length };
}

/** EK-5: OneDesk ekipleri ve başlıkları (ayar'dan; yoksa varsayılan). */
export interface TicketKategorileri {
  ekipler: string[];
  varsayilan_ekip: string;
  kategoriler: Array<{ ad: string; konu_onerisi: string | null }>;
  /** EK-12.7: OneDesk ticket'ında olması gereken bilgiler (ayar `ticket_zorunlu_alanlar`). */
  zorunlu_alanlar?: Array<{ anahtar: string; etiket: string }>;
  /** BÇO'da bu kadar saati geçen ticket → "TL'ye mail" hatırlatması (ayar; varsayılan 24). */
  bco_hatirlatma_saat?: number;
  /** Kırmızı hat mail konusu şablonu: "{task_no} / {task_adi} / Kırmızı Hat". */
  kirmizi_hat_konu_sablonu?: string;
}

export function ticketKategorileri(): Promise<TicketKategorileri> {
  return istek<TicketKategorileri>('/api/ticket/kategoriler');
}

/** Excel'deki TICKET sayfasını aktarır (§5.3.8): `kuru` = yalnız önizleme. */
export interface TicketAktarimSonucu {
  okunan: number;
  eklenen: number;
  zaten_var: number;
  guncellenen: number;
  binaya_baglanan: number;
  binasiz: number;
  baglanamayan: Array<{ satir: number; lokasyon_var: boolean }>;
  kuru: boolean;
  yedek: string | null;
  bekliyora_donen_is: number;
}

export function ticketExcelAktar(dosya: File, kuru: boolean): Promise<TicketAktarimSonucu> {
  return dosyaGonder<TicketAktarimSonucu>(`/api/ticket/aktar?kuru=${kuru ? 'true' : 'false'}`, dosya);
}

export function ticketAyrintisi(id: number): Promise<TicketAyrintisi> {
  return istek<TicketAyrintisi>(`/api/ticket/${id}`);
}

export function ticketOlustur(
  girdi: TicketGirdisi,
): Promise<{ ticket: Ticket; sablon_taslak: boolean; mesaj: string }> {
  return istek('/api/ticket', { yontem: 'POST', govde: girdi, zamanAsimiMs: 20000 });
}

export function ticketGuncelle(id: number, girdi: TicketGuncelleme): Promise<TicketAyrintisi> {
  return istek<TicketAyrintisi>(`/api/ticket/${id}`, {
    yontem: 'PATCH',
    govde: girdi,
    zamanAsimiMs: 20000,
  });
}
