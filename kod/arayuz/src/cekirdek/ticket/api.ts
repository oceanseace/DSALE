/**
 * Yeni ticket çağrıları: Loc ID (ya da Bina Serial) → doldurulacak bilgiler (`GET /api/ticket/lokasyon` →
 * `saha/ticket.py · lokasyon_bilgisi`) · Müşteri No → Loc ID, bina adı, Task adı (`GET /api/ticket/musteri` →
 * `musteri_bilgisi`; izin ticket.defter + is.musteri). Çağıranlar: `cekirdek/ticket/YeniTicket.tsx`,
 * Altyapı › Ticketlar yeni satırı.
 */

import { istek } from '../api/istemci';
import type { Ticket } from '../api/tipler';

export interface LokasyonBilgisi {
  location_id: string;
  /** Bina ya da o Loc ID'de açık iş bulundu mu. Bulunmasa da ticket kaydedilebilir. */
  bulundu: boolean;
  bina_serial: string | null;
  site: string;
  ilce: string;
  mahalle: string;
  bolge: number | null;
  /** Binadaki açık işlerin müşteri numaraları (kayıtta "Müşteri" sütununa yazılır). */
  musteriler: string[];
  acik_ticketlar: Ticket[];
}

export function lokasyonBilgisi(secim: { loc: string } | { bina_serial: string }): Promise<LokasyonBilgisi> {
  const sorgu = 'loc' in secim ? `loc=${encodeURIComponent(secim.loc)}` : `bina_serial=${encodeURIComponent(secim.bina_serial)}`;
  return istek<LokasyonBilgisi>(`/api/ticket/lokasyon?${sorgu}`);
}

export interface MusteriIsi {
  musteri_no: string;
  /** Müşterinin işi bulundu mu (açık yoksa en yeni iş; `acik` false). */
  bulundu: boolean;
  acik: boolean;
  lokasyon: string;
  bina_serial: string | null;
  bina_adi: string;
  task_adi: string;
  task_no: string;
}

/** Virgülle birden çok no: ilk bulunan üstte, hepsi `sonuclar`da. */
export function musteriBilgisi(no: string): Promise<MusteriIsi & { sonuclar: MusteriIsi[] }> {
  return istek(`/api/ticket/musteri?no=${encodeURIComponent(no)}`);
}

/* ------------------------------ Ticket'ın işleri (Task No · satış kanalı) ------------------------------ */

/** Seçicideki / ticket'taki bir iş (`saha/ticket.py · _is_satiri`). Adres ve müşteri no yalnız `is.musteri` izniyle. */
export interface TicketIsi {
  is_no: string;
  task_no: string;
  task_adi: string;
  satis_kanali: string;
  boss_durum: string;
  adres: string;
  musteri_no: string;
  lokasyon: string;
  bina_serial: string | null;
  acik: boolean;
  acilis: string | null;
  kurulum: boolean;
  kanal_sikayeti: boolean;
  /** TASKS'taki ⚠ ile aynı metin ("Bu müşterinin kanal şikâyeti var"); yoksa boş. */
  uyari: string;
  /** Yalnız ticket'taki işlerde: seçicide işaretlendi mi · kurulum engeliyle bağlı mı. */
  secildi?: boolean;
  bagli?: boolean;
}

/** Aynı lokasyonda son 180 günün (ya da açık) ticket'ı — engellemeyen uyarı. */
export interface BenzerTicket {
  id: number;
  ticket_no: string;
  durum: string;
  konu: string;
  acilis: string;
  acik: boolean;
}

export interface IsSecenekleri {
  isler: TicketIsi[];
  /** 500'den çok iş vardı (liste kesildi). */
  fazla: boolean;
  /** Varsayılan seçili task no'lar (kurulum işi; kanal şikâyeti asla). */
  varsayilan: string[];
  lokasyon: string;
  bina_serial: string | null;
  site: string;
  benzer: BenzerTicket[];
  /** Toptan müşteri (tek müşteri no çok abone): müşteri no ile aranınca varsayılan seçim yok; abone elle seçilir. */
  toptan?: boolean;
}

/** Liste satırı: sunucunun ticket'a eklediği iş alanlarıyla (`_task_bilgileri`). */
export type TicketSatiri = Ticket & {
  isler?: TicketIsi[];
  musteriler?: string[];
  satis_kanali?: string;
  uyari?: string;
  silindi?: boolean;
  bekleyen_is?: number;
  /** Bağlı işlerin HEPSİ BOSS'ta kapandı (Tamamlandı / İptal / FOX iptal): takip gerekmiyor (sunucu `isi_kapandi`). */
  isi_kapandi?: boolean;
};

export function isSecenekleri(secim: { musteri?: string; loc?: string; haric?: number }): Promise<IsSecenekleri> {
  const p = new URLSearchParams();
  if (secim.musteri?.trim()) p.set('musteri', secim.musteri.trim());
  if (secim.loc?.trim()) p.set('loc', secim.loc.trim());
  if (secim.haric != null) p.set('haric', String(secim.haric));
  return istek<IsSecenekleri>(`/api/ticket/isler?${p.toString()}`, { zamanAsimiMs: 20000 });
}

/** Yeni ticket (seçilen işlerle). `isler`: Task No'lar. */
export function ticketOlusturIsli(girdi: {
  konu: string;
  durum: string;
  location_id: string | null;
  musteri: string | null;
  site: string | null;
  ticket_no: string | null;
  detay: string | null;
  isler: string[];
}): Promise<{ ticket: TicketSatiri; bulunmayan_is: string[]; mesaj: string }> {
  return istek('/api/ticket', { yontem: 'POST', govde: girdi, zamanAsimiMs: 20000 });
}

/** "+ abone ekle": ticket'a iş(ler) ekler (işin kendisine dokunmaz). */
export function ticketIsEkle(id: number, isler: string[]): Promise<{ eklenen: string[]; bulunmayan: string[]; ticket: TicketSatiri }> {
  return istek(`/api/ticket/${id}/isler`, { yontem: 'POST', govde: { isler }, zamanAsimiMs: 20000 });
}

export function ticketIsCikar(id: number, isler: string[]): Promise<{ cikarildi: number; ticket: TicketSatiri }> {
  return istek(`/api/ticket/${id}/isler/cikar`, { yontem: 'POST', govde: { isler } });
}

/** Yumuşak silme: listeden düşer; açık ticket İPTAL olur, bağlı açık işler yalnız ayrılır. */
export function ticketSil(id: number): Promise<{ silindi: boolean; ayrilan_is: number; mesaj: string }> {
  return istek(`/api/ticket/${id}/sil`, { yontem: 'POST' });
}

export function temizlikOnizle(gun = 90): Promise<{ gun: number; sayi: number }> {
  return istek(`/api/ticket/temizlik?gun=${gun}`);
}

export function temizlikYap(gun = 90): Promise<{ silinen: number; ayrilan_is: number; mesaj: string }> {
  return istek('/api/ticket/temizlik', { yontem: 'POST', govde: { gun }, zamanAsimiMs: 60000 });
}
