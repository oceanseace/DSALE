/**
 * Hazır süzgeç: Pano / Öbek çekmecesi / arama paleti TASKS'ı `#/yonetici/isler/suz/<kod>` ile açınca
 * hangi satırların kalacağı ve çipte ne yazacağı. Kodlar cekirdek/yol/tasks.ts TASKS_SUZ'da;
 * koşullar sunucudaki sayılarla aynı (operasyon/v2/gorunum.py sayac, takip.py _ek12_hijyen). Çağıran: Isler.tsx.
 */

import type { IsSatir } from '../../../cekirdek/is/tipler';

export interface PanoSuzgeci {
  ad: string;
  uyar: (x: IsSatir) => boolean;
}

const zamanMs = (t: string | null | undefined) => (t ? Date.parse(t.replace(' ', 'T')) : NaN);
const ATANMAMIS = new Set(['triyaj', 'bekliyor', 'randevulu']);

/** Kod tanınmazsa null (TASKS süzgeçsiz açılır, çip çıkmaz). `isler` yalnız kişi/öbek adını bulmak için. */
export function panoSuzgeci(kod: string | null, isler: IsSatir[], simdi = Date.now()): PanoSuzgeci | null {
  if (!kod) return null;
  const kisi = /^teknik-(\d+)$/.exec(kod);
  if (kisi) {
    const id = Number(kisi[1]);
    const ad = isler.find((x) => x.atanan?.id === id)?.atanan?.ad;
    return { ad: `Teknisyen: ${ad ?? `#${id}`}`, uyar: (x) => x.atanan?.id === id };
  }
  const obek = /^obek-(\d+)$/.exec(kod);
  if (obek) {
    const id = Number(obek[1]);
    const ad = isler.find((x) => x.obek?.id === id)?.obek?.ad;
    return { ad: `Öbek: ${ad ?? `#${id}`}`, uyar: (x) => x.obek?.id === id };
  }
  switch (kod) {
    case 'asan24':
      return { ad: '24 saati aşan', uyar: (x) => zamanMs(x.son24) < simdi };
    case 'atanmamis':
      return { ad: 'Atanmamış', uyar: (x) => ATANMAMIS.has(x.durum) };
    case 'iliskili':
      return { ad: 'İlişkili işi olan', uyar: (x) => Boolean(x.iliskili_isler?.length) };
    case 'btk48':
      return { ad: '48 saati aşan BTK', uyar: (x) => x.serit === 'BTK' && zamanMs(x.acilis) < simdi - 48 * 3600e3 };
    case 'askida_uyanmasiz':
      return { ad: 'Askıda, uyanma yok', uyar: (x) => x.rozetler.includes('uyanmasiz') };
    case 'askida_btk_durdu':
      return { ad: 'Askıda (BTK saati durdu)', uyar: (x) => x.btk_durdu };
    case 'btk_alarm':
      return { ad: 'Şikâyeti alarm gününde', uyar: (x) => Boolean(x.btk_sikayet?.alarm) };
    case 'genel_ariza':
      return { ad: 'Genel arıza', uyar: (x) => x.genel_ariza };
    case 'oncelikli':
      return { ad: 'Kanal şikâyeti (öncelikli)', uyar: (x) => Boolean(x.oncelik) };
    default:
      return null;
  }
}
