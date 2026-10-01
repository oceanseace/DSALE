/** Teknisyen ekranlarının küçük metin yardımcıları (Türkçe biçim, §6.15 sözlüğü). */

import type { Durum, IsAyrinti, IsSatir } from '../is/tipler';
import type { SureRengi } from '../ortak/SureHapi';

const GUN_KISA = ['Paz', 'Pzt', 'Sal', 'Çar', 'Per', 'Cum', 'Cmt'];
const GUN_UZUN = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];

const iki = (n: number) => String(n).padStart(2, '0');

/** "AAAA-AA-GG SS:DD:ss" → Date (Türkiye saati, cihazın yerel saati olarak). */
export function anOku(metin: string | null | undefined): Date | null {
  if (!metin) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(metin);
  if (!m) return null;
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0));
}

function ayniGun(a: Date, b: Date) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

/** "Salı 30.09" */
export function gunBasligi(simdi = new Date()): string {
  return `${GUN_UZUN[simdi.getDay()]} ${iki(simdi.getDate())}.${iki(simdi.getMonth() + 1)}`;
}

/** "14:05" */
export function saatMetni(metin: string | null | undefined): string {
  const d = anOku(metin);
  return d ? `${iki(d.getHours())}:${iki(d.getMinutes())}` : '—';
}

/**
 * Randevu dilimi: bugünse "08–10", yarınsa "Yarın 10–12", sonrası "Per 2.10 · 10–12".
 * Saat tam değilse dakikası yazılır ("08:30–10").
 */
export function dilimMetni(bas: string | null | undefined, bit: string | null | undefined, simdi = new Date()): string {
  const b = anOku(bas);
  const s = anOku(bit);
  if (!b) return 'Randevusuz';
  const hs = (d: Date) => (d.getMinutes() ? `${iki(d.getHours())}:${iki(d.getMinutes())}` : iki(d.getHours()));
  const aralik = s ? `${hs(b)}–${hs(s)}` : hs(b);
  if (ayniGun(b, simdi)) return aralik;
  const yarin = new Date(simdi);
  yarin.setDate(yarin.getDate() + 1);
  if (ayniGun(b, yarin)) return `Yarın ${aralik}`;
  return `${GUN_KISA[b.getDay()]} ${b.getDate()}.${iki(b.getMonth() + 1)} · ${aralik}`;
}

/**
 * Süre hapı girdisi. BTK işinde BTK hedefi (askıda duran saat düşülmüş, EK-3);
 * diğerlerinde 24 saat sözü. Renk ve "Gecikti" sunucudan gelir.
 */
export function kalanBilgisi(is: IsSatir): { kalan_dk: number; renk: SureRengi; gecikti: boolean; btk: boolean } {
  const btk = is.serit === 'BTK' && is.btk_kalan_dk != null;
  return { kalan_dk: btk ? (is.btk_kalan_dk as number) : is.kalan_dk, renk: is.renk, gecikti: is.gecikti, btk };
}

/** Kartın yer satırı: "Görükle · X Sitesi" (yoksa mahalle · ilçe). */
export function yerMetni(is: IsSatir): string {
  if (is.kisa_adres) return is.kisa_adres;
  return [is.mahalle, is.ilce].filter(Boolean).join(' · ') || 'Adres bilgisi yok';
}

/** Müşteri no maskesi: son 4 hane görünür. */
export function maskeliNo(no: string | null | undefined): string {
  if (!no) return '—';
  const s = String(no);
  return s.length <= 4 ? s : `••• ${s.slice(-4)}`;
}

/** Büyük düğme: durum → etiket + hedef durum (§6.9). */
export const BUYUK_DUGME: Partial<Record<Durum, { etiket: string; hedef: Durum | 'bitti' }>> = {
  atandi: { etiket: 'Yola çıktım', hedef: 'yolda' },
  yolda: { etiket: 'İşe başladım', hedef: 'sahada' },
  sahada: { etiket: 'Bitti', hedef: 'bitti' },
};

/** Adım çizgisi: Atandı → Yolda → Sahada → Bitti. */
export const ADIMLAR = ['Atandı', 'Yolda', 'Sahada', 'Bitti'];
export function adimNo(durum: Durum): number {
  return durum === 'yolda' ? 1 : durum === 'sahada' ? 2 : durum === 'cozuldu' || durum === 'kapandi' ? 3 : 0;
}

/** "Yolda · 12 dk'dır" gibi: durumun ne zamandır sürdüğü. */
export function durumSuresi(is: IsSatir, simdiMs = Date.now()): string | null {
  const d = anOku(is.durum_zamani);
  if (!d) return null;
  const dk = Math.max(0, Math.round((simdiMs - d.getTime()) / 60000));
  if (dk < 1) return 'az önce';
  if (dk < 60) return `${dk} dk'dır`;
  const s = Math.floor(dk / 60);
  return `${s} s ${dk % 60 ? `${dk % 60} dk` : ''}`.trim() + "'dir";
}

/** Operasyonun ve BOSS'un notları (yeniden eskiye): teknisyene gösterilen tek bilgi. */
export function notlar(is: IsAyrinti): Array<{ id: number; kisi: string | null; zaman: string; metin: string }> {
  return (is.olaylar ?? [])
    .filter((o) => o.tur === 'not' && o.notu)
    .map((o) => ({ id: o.id, kisi: o.kisi, zaman: o.zaman, metin: o.notu as string }));
}

/** Panoya kopyalar (izin yoksa eski yol). */
export async function panoyaKopyala(metin: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(metin);
      return true;
    }
  } catch {
    /* aşağıdaki yedek yol */
  }
  try {
    const alan = document.createElement('textarea');
    alan.value = metin;
    alan.setAttribute('readonly', '');
    alan.style.position = 'fixed';
    alan.style.opacity = '0';
    document.body.appendChild(alan);
    alan.select();
    const tamam = document.execCommand('copy');
    alan.remove();
    return tamam;
  } catch {
    return false;
  }
}
