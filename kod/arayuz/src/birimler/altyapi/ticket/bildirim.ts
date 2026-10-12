/**
 * Ticket çözülünce bağlı/seçilen işler için kısa bildirim: "201285062 · altyapı çözüldü, yeniden aranacak"
 * (sunucu `PATCH /api/ticket/{id}` → `donen_tasklar`; işlerin Bizim durumu "Aranacak" olur, TASKS'ta yeni sütun yok).
 * Kullananlar: Ticketlar.tsx (hücreden durum), TicketAyrinti.tsx (çekmece).
 * `benzerMetni`: aynı lokasyonda ticket uyarısı (YeniSatir.tsx, TicketAyrinti.tsx '+ abone ekle').
 */
import type { TicketDurumu } from '../../../cekirdek/api/tipler';
import { durumBilgisi, tarihKisa } from '../../../cekirdek/ortak/ticketBilgi';
import type { IsSecenekleri } from '../../../cekirdek/ticket/api';

export function cozulduMetni(tasklar: string[] | undefined, sayi = 0): string | null {
  const l = tasklar ?? [];
  if (!l.length) return sayi ? `${sayi.toLocaleString('tr-TR')} iş · altyapı çözüldü, yeniden aranacak` : null;
  const ek = l.length > 1 ? ` (+${(l.length - 1).toLocaleString('tr-TR')} iş)` : '';
  return `${l[0]}${ek} · altyapı çözüldü, yeniden aranacak`;
}

/** "Bu lokasyonda 12.09'da açılmış (Çözüldü) ticket var" */
export function benzerMetni(b: IsSecenekleri['benzer']): string {
  if (!b.length) return '';
  const ilk = b[0];
  const ek = b.length > 1 ? ` (+${b.length - 1} ticket daha)` : '';
  const no = ilk.ticket_no ? ` #${ilk.ticket_no}` : '';
  const tam = tarihKisa(ilk.acilis);
  const tarih = tam.endsWith(`.${new Date().getFullYear()}`) ? tam.slice(0, 5) : tam; // bu yıl: "12.09"
  return `Bu lokasyonda ${tarih}'da açılmış (${durumBilgisi(ilk.durum as TicketDurumu).etiket})${no} ticket var${ek}. Yine de eklenebilir.`;
}
