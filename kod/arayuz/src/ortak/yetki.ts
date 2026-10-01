/**
 * İstemci tarafında izin: menü, sekmeler ve adres kapıları buradan çizilir.
 *
 * Asıl kapı SUNUCUDADIR (`saha/yetki.py`, varsayılan YASAK). Sunucu
 * `/api/ben.izinler` gönderir; burada o liste kullanılır. Yalnız eski bir
 * sunucuyla konuşurken (alan yoksa) aşağıdaki tablo — OPERASYON_V2_SPEC §2.2'nin
 * birebir kopyası — görev kümesinden izin türetir. Ekranda bir düğmeyi
 * göstermek hiçbir şeye izin vermez; yalnız kapalı kapıya yürümeyi önler.
 */

import type { AnaEkran, BenYaniti, Rol } from '../api/tipler';

export const ROLLER: Rol[] = ['satisci', 'operasyon', 'teknik', 'yonetici'];

export const GOREV_ETIKET: Record<Rol, string> = {
  satisci: 'Satış',
  operasyon: 'Operasyon',
  teknik: 'Teknik',
  yonetici: 'Yönetici',
};

/** Ekip çekmecesinde her görevin altındaki tek cümle (§6.10). */
export const GOREV_ACIKLAMA: Record<Rol, string> = {
  satisci: 'Bina listesi ve satış ziyaretleri. Kendi bölgesini görür.',
  operasyon: 'İş emirlerini dağıtır, randevu verir, müşteri bilgisini görür.',
  teknik: 'Yalnız kendisine atanan işleri görür ve durumunu işler.',
  yonetici: 'Her şeyi görür; ekip ve ayarları yönetir.',
};

/** §2.2 izin tablosu: eylem → hangi görevler. */
const TABLO: Record<string, Rol[]> = {
  'satis.kendi': ['satisci', 'yonetici'],
  'satis.izle': ['yonetici'],
  'bina.oku': ['satisci', 'operasyon', 'teknik', 'yonetici'],
  'geometri.oku': ['satisci', 'operasyon', 'yonetici'],
  'altlik.oku': ['satisci', 'operasyon', 'teknik', 'yonetici'],
  'ticket.sablon': ['satisci', 'operasyon', 'teknik', 'yonetici'],
  'is.liste': ['operasyon', 'teknik', 'yonetici'],
  'is.musteri': ['operasyon', 'teknik', 'yonetici'],
  'is.yukle': ['operasyon', 'yonetici'],
  'is.ata': ['operasyon', 'yonetici'],
  'is.duzenle': ['operasyon', 'yonetici'],
  'is.saha': ['operasyon', 'teknik', 'yonetici'],
  'is.olustur': ['operasyon', 'yonetici'],
  'is.excel': ['operasyon', 'yonetici'],
  'obek.oku': ['operasyon', 'yonetici'],
  'obek.duzenle': ['operasyon', 'yonetici'],
  'mahalle.ekle': ['operasyon', 'yonetici'],
  'mahalle.yukle': ['yonetici'],
  'ticket.defter': ['operasyon', 'yonetici'],
  'takip.oku': ['operasyon', 'yonetici'],
  'takip.tam': ['yonetici'],
  'kapasite.yaz': ['operasyon', 'yonetici'],
  'ekip.teknikler': ['operasyon', 'yonetici'],
  'ekip.yonet': ['yonetici'],
  'veri.yonet': ['yonetici'],
};

export function izinListesi(gorevler: Rol[]): string[] {
  return Object.entries(TABLO)
    .filter(([, roller]) => roller.some((r) => gorevler.includes(r)))
    .map(([eylem]) => eylem);
}

/** Görev kümesi: sunucu gönderdiyse o, yoksa ana görev. Ana görev hep içindedir. */
export function gorevleriCoz(ozet: Pick<BenYaniti, 'kullanici'> | null | undefined): Rol[] {
  const k = ozet?.kullanici;
  if (!k) return [];
  const kume = new Set<Rol>((k.gorevler ?? []).filter((r): r is Rol => ROLLER.includes(r)));
  if (ROLLER.includes(k.rol)) kume.add(k.rol);
  return ROLLER.filter((r) => kume.has(r));
}

export function izinleriCoz(ozet: BenYaniti | null | undefined): Set<string> {
  if (!ozet) return new Set();
  if (Array.isArray(ozet.izinler)) return new Set(ozet.izinler);
  return new Set(izinListesi(gorevleriCoz(ozet)));
}

/** Ana görevin ekranı (§2.1): satış → Bugün, teknik → İşlerim, diğerleri → İşler. */
export function anaEkranCoz(ozet: BenYaniti | null | undefined): AnaEkran {
  if (ozet?.ana_ekran) return ozet.ana_ekran;
  const rol = ozet?.kullanici?.rol;
  if (rol === 'teknik') return 'islerim';
  if (rol === 'operasyon' || rol === 'yonetici') return 'isler';
  return 'bugun';
}

export function anaEkranYolu(ekran: AnaEkran): string {
  return ekran === 'islerim' ? '/islerim' : ekran === 'isler' ? '/yonetici/isler' : '/bugun';
}

/** "Operasyon + Yönetici" — ekranda yazılan görev adı. */
export function gorevEtiketi(ozet: BenYaniti | null | undefined): string {
  if (ozet?.gorev_etiketi) return ozet.gorev_etiketi;
  const gorevler = gorevleriCoz(ozet);
  return gorevler.map((g) => GOREV_ETIKET[g]).join(' + ') || '—';
}
