/**
 * TASKS adres sözleşmesi (tek yer): #/yonetici/isler[/kontrol|/giden|/boss-ekip|/suz/<kod>][/is/<no>].
 * Pano (administrator/takip), Öbek çekmecesi ve arama paleti TASKS'ı hazır süzgeçle `tasksSuzYolu` ile açar;
 * TASKS (birimler/operasyon/isler/Isler.tsx) adresi `tasksAdresiOku` ile çözer, süzgeci panoSuzgeci.ts uygular.
 */

/** TASKS'ın tablo dışı bölümleri (araç çubuğundaki bağlantılarla açılır). */
export type TasksBolum = 'tumu' | 'kontrol' | 'boss-ekip' | 'giden';
const OZEL_BOLUM: TasksBolum[] = ['kontrol', 'boss-ekip', 'giden'];

/** Hazır süzgeç kodları; `teknik-<id>` ve `obek-<id>` kişi/öbek süzgecidir. */
export const TASKS_SUZ = {
  asan24: 'asan24',
  atanmamis: 'atanmamis',
  btk48: 'btk48',
  askidaUyanmasiz: 'askida_uyanmasiz',
  askidaBtkDurdu: 'askida_btk_durdu',
  btkAlarm: 'btk_alarm',
  genelAriza: 'genel_ariza',
  oncelikli: 'oncelikli',
  /** İlişkili iş farklı ekipte/atanmamış: TASKS "hepsini aynı ekibe ata" panelini açar. */
  iliskili: 'iliskili',
  teknik: (id: number | string) => `teknik-${id}`,
  obek: (id: number | string) => `obek-${id}`,
} as const;

export const tasksBolumYolu = (b: TasksBolum) => (b === 'tumu' ? '/yonetici/isler' : `/yonetici/isler/${b}`);
export const tasksSuzYolu = (kod: string) => `/yonetici/isler/suz/${encodeURIComponent(kod)}`;

/** Adresi çözer: bölüm, hazır süzgeç kodu (yoksa null) ve açık iş no. Eski `obek/<id>` yer imleri de okunur. */
export function tasksAdresiOku(adres: string): { bolum: TasksBolum; suz: string | null; isNo: string | null } {
  let p = adres.split('?')[0].split('/').filter(Boolean).slice(2);
  let isNo: string | null = null;
  const i = p.indexOf('is');
  if (i >= 0) {
    isNo = p[i + 1] ? decodeURIComponent(p[i + 1]) : null;
    p = p.slice(0, i);
  }
  if (p[0] === 'suz' && p[1]) return { bolum: 'tumu', suz: decodeURIComponent(p[1]), isNo };
  if (p[0] === 'obek' && p[1]) return { bolum: 'tumu', suz: TASKS_SUZ.obek(decodeURIComponent(p[1])), isNo };
  const t = p[0] as TasksBolum | undefined;
  return { bolum: t && OZEL_BOLUM.includes(t) ? t : 'tumu', suz: null, isNo };
}

/** Bulunulan bölüm/süzgeç korunarak gidilecek kök adres (iş açılıp kapanınca süzgeç kaybolmasın). */
export const tasksKokYolu = (bolum: TasksBolum, suz: string | null) => (suz ? tasksSuzYolu(suz) : tasksBolumYolu(bolum));
