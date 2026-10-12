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
export const IZIN_TABLOSU: Record<string, Rol[]> = {
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
  'ticket.oku': ['operasyon', 'yonetici'],
  'ticket.defter': ['operasyon', 'yonetici'],
  'takip.oku': ['operasyon', 'yonetici'],
  'takip.tam': ['yonetici'],
  'kapasite.yaz': ['operasyon', 'yonetici'],
  'ekip.teknikler': ['operasyon', 'yonetici'],
  'ekip.yonet': ['yonetici'],
  'veri.yonet': ['yonetici'],
  'tablolar.oku': ['operasyon', 'yonetici'],
  'is.randevu': ['operasyon', 'yonetici'],
  /* Görevden gelmez: Depo yetkinliği / yalnız Administrator. */
  'depo.yonet': [],
  'yetkinlik.yonet': [],
};

export function izinListesi(gorevler: Rol[]): string[] {
  return Object.entries(IZIN_TABLOSU)
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

/**
 * Yetkinlik → türettiği görev (sunucu saha/yetki.py _PAKET_GOREVI ile aynı). Kişiler ekranı İK'nın seçtiği
 * unvandan görevi (bölge / teknik alanları) göstermek için kullanır; asıl hesap sunucudadır.
 */
const YETKINLIK_GOREVI: Record<string, Rol> = {
  saha_satis: 'satisci',
  satis_izleme: 'yonetici',
  randevu_arama: 'operasyon',
  operasyon_planlama: 'operasyon',
  ticket_defteri: 'operasyon',
  ticket_izleme: 'operasyon',
  teknik_saha: 'teknik',
  pano: 'yonetici',
  kisi_yonetimi: 'yonetici',
  veri_yonetimi: 'yonetici',
};

export function yetkinlikGorevleri(kodlar: string[]): Rol[] {
  const kume = new Set(kodlar.map((k) => YETKINLIK_GOREVI[k]).filter(Boolean));
  return ROLLER.filter((r) => kume.has(r));
}

/** Uygulamanın tek Administrator'ı mı (sunucu söyler; istemci türetmez). */
export function administratorMu(ozet: BenYaniti | null | undefined): boolean {
  return Boolean(ozet?.administrator ?? ozet?.kullanici?.administrator);
}

/** "Operasyon + Yönetici" — ekranda yazılan görev adı. */
export function gorevEtiketi(ozet: BenYaniti | null | undefined): string {
  if (administratorMu(ozet)) return 'Administrator';
  const unvan = ozet?.unvan?.ad ?? ozet?.kullanici?.unvan;
  if (unvan) return unvan;
  if (ozet?.gorev_etiketi) return ozet.gorev_etiketi;
  const gorevler = gorevleriCoz(ozet);
  return gorevler.map((g) => GOREV_ETIKET[g]).join(' + ') || '—';
}
