/**
 * Rozet: satırda küçük, sakin bir işaret (§7.3). Metin hep yazılır; renk yalnız
 * destekler. Kelimeler §6.15 sözlüğündendir (ekranda iç jargon yok).
 */

import type { ReactNode } from 'react';
import './bilesen.css';

export type RozetTuru =
  | 'btk'
  | 'ticket'
  | 'tekrar'
  | 'bayi'
  | 'global'
  | 'konum'
  | 'boss_islenecek'
  | 'boss_acik'
  | 'yeniden'
  | 'elle'
  | 'kontrol'
  | 'girissiz'
  | 'demo';

type Renk = 'mor' | 'amber' | 'kirmizi' | 'gri' | 'mavi' | 'yesil';

const TANIM: Record<RozetTuru, { etiket: string; renk: Renk; aciklama: string }> = {
  btk: { etiket: 'BTK', renk: 'mor', aciklama: 'BTK şikâyeti: kısa hedef süresi var' },
  ticket: { etiket: 'Ticket', renk: 'amber', aciklama: 'Binada açık altyapı ticket’ı var' },
  tekrar: { etiket: 'Tekrar arıza', renk: 'kirmizi', aciklama: 'Bu müşteride 7 gün içinde yine arıza' },
  bayi: { etiket: 'Bayi', renk: 'gri', aciklama: 'Bayi tarafından açılan iş' },
  global: { etiket: 'Global', renk: 'gri', aciklama: 'Global Bilgi kanalından gelen iş' },
  konum: { etiket: 'Konum yaklaşık', renk: 'amber', aciklama: 'Adres bina düzeyinde bulunamadı' },
  boss_islenecek: { etiket: 'BOSS’a işlenecek', renk: 'mavi', aciklama: 'Bizdeki değişiklik BOSS’a elle yazılacak' },
  boss_acik: { etiket: 'BOSS’ta açık', renk: 'amber', aciklama: 'Bizde çözüldü, BOSS’ta hâlâ açık' },
  yeniden: { etiket: 'Yeniden açıldı', renk: 'kirmizi', aciklama: 'Kapanmıştı, raporda yeniden göründü' },
  elle: { etiket: 'Elle öbek', renk: 'gri', aciklama: 'Öbeği elle seçildi' },
  kontrol: { etiket: 'Kontrol gerekli', renk: 'amber', aciklama: 'Öbeği ya da mahallesi bulunamadı' },
  girissiz: { etiket: 'Girişsiz · BOSS Mobil', renk: 'gri', aciklama: 'Telefonu yok; işini BOSS Mobil ile yapar' },
  demo: { etiket: 'Gösterim verisi', renk: 'amber', aciklama: 'Bu sayılar gerçek saha kaydı değildir' },
};

export function Rozet({ tur, children }: { tur: RozetTuru; children?: ReactNode }) {
  const t = TANIM[tur];
  if (!t) return null;
  return (
    <span className={`o-rozet ${t.renk}`} title={t.aciklama}>
      {children ?? t.etiket}
    </span>
  );
}

/** Serbest metinli rozet (renk seçilerek). */
export function Hap({ renk = 'gri', children, baslik }: { renk?: Renk; children: ReactNode; baslik?: string }) {
  return (
    <span className={`o-rozet ${renk}`} title={baslik}>
      {children}
    </span>
  );
}
