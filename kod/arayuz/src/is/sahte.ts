/**
 * İş emri v2 — örnek (sahte) veri ve bellekte çalışan küçük sahte sunucu.
 *
 * Arayüz paketleri (WP-C, WP-D, WP-E) sunucu hazır olana kadar
 * `import.meta.env.MODE === 'sahte'` ile bunu kullanır. Bütün adlar UYDURMADIR,
 * numaralar gerçek olmayan 555… biçimindedir (belgeler/OPERASYON_V2_SPEC.md §8.4).
 * Mahalle ve ilçe adları coğrafyadır (kişisel veri değil).
 *
 * Veri tohumlu rastgele sayılarla üretilir: her açılışta aynı 40 iş, yalnız
 * saatler "şimdi"ye göre kayar. `sahteIstek()` sözleşmedeki uçların çoğunu
 * bellekte canlandırır (ata, randevu, durum, öbek…) — iyimser arayüz gerçekten
 * denenebilsin diye. Üretim derlemesinde bu modül koda girmez.
 */

import type {
  AktarimKaydi, AktarimOnay, AktarimSonucu, AramaKaydi, AramaMerdiveni, AramaSonucu, AranacakYanit, AskiAraligi,
  BossEkipYanit, BossGiden, BtkSikayet, DegisimYanit, Durum, IsAyarlari, IsAyrinti, IslerimYanit, IslerSayac, IslerYanit,
  IsSatir, IzlemeDurumu, Kesinti, KesintiAdaylari, KesintiEkleYanit, KesintiListesi, Kisi, Kova, KurallarYanit,
  MahallelerYanit, Obek, ObeklerYanit, Olay, Renk, Rozet, Serit, TakipSatisYanit, TakipYanit, TeknikOzet,
  TopluGeriAlSonuc, TopluSonuc, DagitOnizleme, YeniIsYanit, IlceKaydi, HataYaniti,
} from './tipler';
import { DURUM_KOVA, DURUM_ETIKET } from './tipler';

// ----------------------------------------------------------------------------- yardımcılar
function tohumlu(tohum: number) {
  let a = tohum >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rnd = tohumlu(20260930);
const sec = <T,>(dizi: readonly T[]): T => dizi[Math.floor(rnd() * dizi.length)];

const DK = 60_000;
/** Türkiye saati (UTC+3) ile "AAAA-AA-GG SS:DD:ss" — sunucunun zaman_metni() biçimi. */
export function zamanMetni(an: Date): string {
  return new Date(an.getTime() + 3 * 60 * DK).toISOString().slice(0, 19).replace('T', ' ');
}
/** zaman_metni → Date (Türkiye saati). */
export function zamanOku(metin: string): Date {
  return new Date(metin.replace(' ', 'T') + '+03:00');
}
const simdi = () => new Date();
const eklenmis = (an: Date, dk: number) => new Date(an.getTime() + dk * DK);

// ----------------------------------------------------------------------------- sözlük
export const SAHTE_TEKNIKLER: TeknikOzet[] = [
  { id: 101, ad: 'Ali Kaya', gorevler: ['teknik'], unvan: 'Teknik - Sorumlu', giris_var: true, etiket: [], boss_ekip: 'ALI KAYA EKIBI', kapasite: 15, bugun: { atanan: 0, biten: 0, btk: 0 }, obekler: [], bugun_yok: false },
  { id: 102, ad: 'Veli Demir', gorevler: ['teknik'], unvan: 'Teknik - Sorumlu', giris_var: true, etiket: [], boss_ekip: 'VELI DEMIR', kapasite: 15, bugun: { atanan: 0, biten: 0, btk: 0 }, obekler: [], bugun_yok: false },
  { id: 103, ad: 'Can Yıldız', gorevler: ['teknik'], unvan: 'Teknik - Sorumlu', giris_var: false, etiket: [], boss_ekip: null, kapasite: 12, bugun: { atanan: 0, biten: 0, btk: 0 }, obekler: [], bugun_yok: false },
  { id: 104, ad: 'Emre Şahin', gorevler: ['teknik', 'yonetici'], unvan: 'Teknik - Müdür', giris_var: true, etiket: ['lider'], boss_ekip: null, kapasite: 10, bugun: { atanan: 0, biten: 0, btk: 0 }, obekler: [], bugun_yok: false },
  { id: 105, ad: 'Deniz Öztürk', gorevler: ['teknik'], unvan: 'Teknik - Sorumlu', giris_var: false, etiket: [], boss_ekip: 'DENIZ OZTURK', kapasite: 15, bugun: { atanan: 0, biten: 0, btk: 0 }, obekler: [], bugun_yok: true },
];
const kisi = (t: TeknikOzet): Kisi => ({ id: t.id, ad: t.ad, gorevler: t.gorevler, unvan: t.unvan, giris_var: t.giris_var });

interface SahteObekTanim { id: number; ad: string; renk: number; sahip: number | null; yedek: number | null; mahalleler: Array<[string, string, string]>; }
const OBEK_TANIMLARI: SahteObekTanim[] = [
  { id: 1, ad: 'Görükle', renk: 0, sahip: 101, yedek: 102, mahalleler: [['Bursa', 'Nilüfer', 'Görükle'], ['Bursa', 'Nilüfer', 'Kayapa']] },
  { id: 2, ad: 'Özlüce', renk: 1, sahip: 102, yedek: null, mahalleler: [['Bursa', 'Nilüfer', 'Özlüce'], ['Bursa', 'Nilüfer', 'Ertuğrul']] },
  { id: 3, ad: 'Dumlupınar', renk: 2, sahip: 103, yedek: 101, mahalleler: [['Bursa', 'Nilüfer', 'Dumlupınar']] },
  { id: 4, ad: 'Beşevler', renk: 3, sahip: 104, yedek: null, mahalleler: [['Bursa', 'Nilüfer', 'Beşevler'], ['Bursa', 'Nilüfer', 'Ataevler']] },
  { id: 5, ad: 'Yıldırım', renk: 4, sahip: 105, yedek: 103, mahalleler: [['Bursa', 'Yıldırım', 'Yiğitler'], ['Bursa', 'Yıldırım', 'Mimarsinan']] },
  { id: 6, ad: 'Mudanya', renk: 5, sahip: null, yedek: null, mahalleler: [['Bursa', 'Mudanya', '*']] },
  { id: 7, ad: 'Yalova', renk: 6, sahip: 101, yedek: null, mahalleler: [['Yalova', 'Merkez', '*'], ['Yalova', 'Çiftlikköy', '*']] },
  { id: 8, ad: 'Gürsu', renk: 7, sahip: null, yedek: null, mahalleler: [['Bursa', 'Gürsu', '*']] },
];

const YERLER: Array<[string, string, string, number, number]> = [
  ['Bursa', 'Nilüfer', 'Görükle', 40.2268, 28.8710], ['Bursa', 'Nilüfer', 'Kayapa', 40.2415, 28.8452],
  ['Bursa', 'Nilüfer', 'Özlüce', 40.2201, 28.9588], ['Bursa', 'Nilüfer', 'Ertuğrul', 40.2152, 28.9731],
  ['Bursa', 'Nilüfer', 'Dumlupınar', 40.2210, 28.9950], ['Bursa', 'Nilüfer', 'Beşevler', 40.2185, 28.9885],
  ['Bursa', 'Nilüfer', 'Ataevler', 40.2239, 28.9760], ['Bursa', 'Yıldırım', 'Yiğitler', 40.1893, 29.1142],
  ['Bursa', 'Yıldırım', 'Mimarsinan', 40.1970, 29.1011], ['Bursa', 'Mudanya', 'Güzelyalı', 40.3647, 28.9151],
  ['Yalova', 'Merkez', 'Bahçelievler', 40.6540, 29.2742], ['Yalova', 'Çiftlikköy', 'Siteler', 40.6612, 29.3211],
  ['Bursa', 'Kestel', 'Kurtul', 40.1981, 29.2102],                                 // öbeksiz
  ['İzmir', 'Karşıyaka', 'Bostanlı', 38.4600, 27.0950],                              // il dışı
];
const TASKLAR: Array<[string, Serit, number | null]> = [
  ['Bağlantı Problemi', 'BTK', 12], ['Bağlantı Problemi', 'BTK', 12], ['Bağlantı Problemi', 'BTK', 12],
  ['Modem Değişikliği', 'SAHA', null], ['TV+ Arıza', 'BTK', 6], ['Doping Arıza Bildirimi', 'BTK', 24],
  ['STB Cihaz Değişikliği', 'SAHA', null], ['Teknik Servis Ücretlendirme', 'MASA', null],
  ['Sosyal Destek Evrak Toplama', 'LOJISTIK', null], ['Arama Problemi', 'BTK', 12],
];
const ADLAR = ['Ayşe', 'Fatma', 'Mehmet', 'Mustafa', 'Zeynep', 'Hüseyin', 'Elif', 'Hakan', 'Selin', 'Burak', 'Gül', 'Oğuz'];
const SOYADLAR = ['Aksoy', 'Balcı', 'Çelik', 'Doğan', 'Erdem', 'Günay', 'Işık', 'Kurt', 'Özkan', 'Polat', 'Sarı', 'Tekin'];
const SITELER = ['Çınar Sitesi', 'Park Evleri', 'Lale Apartmanı', 'Göl Konutları', '12. Sokak No 4', 'Menekşe Sitesi', 'Vadi Evleri'];
const DURUM_DAGILIMI: Durum[] = [
  'triyaj', 'triyaj', 'bekliyor', 'bekliyor', 'bekliyor', 'bekliyor', 'bekliyor', 'bekliyor', 'randevulu', 'randevulu',
  'atandi', 'atandi', 'atandi', 'atandi', 'atandi', 'atandi', 'yolda', 'yolda', 'sahada', 'sahada',
  'ulasilamadi', 'ulasilamadi', 'askida', 'askida', 'askida', 'altyapi', 'merkeze', 'cozuldu', 'cozuldu', 'kapandi',
  'bekliyor', 'bekliyor', 'atandi', 'atandi', 'bekliyor', 'randevulu', 'atandi', 'askida', 'bekliyor', 'triyaj',
];

// ----------------------------------------------------------------------------- iş deposu (bellek)
interface SahteIs {
  is_no: string; boss_task_no: string | null; kaynak: 'boss' | 'bayi'; kanal_grubu: IsSatir['kanal_grubu'];
  task_adi: string; serit: Serit; btk_hedef_saat: number | null;
  durum: Durum; durum_zamani: Date;
  yer: [string, string, string, number, number]; obek_id: number | null; obek_elle_id: number | null;
  triyaj_nedeni: IsSatir['triyaj_nedeni']; konum_yaklasik: boolean;
  acilis: Date; gorulme: Date;
  musteri_adi: string; musteri_no: string; adres: string;
  atanan_id: number | null; randevu: { bas: Date; bit: Date; teyitli: boolean; kaynak: 'biz' | 'boss' } | null;
  oneri_id: number | null; boss_ekip: string | null; boss_bekleyen: string | null; boss_islendi: Date | null;
  ticket: IsSatir['ticket']; binada_acik_ticket: number; tekrar: boolean; yeniden: number; kotu_gecmis: boolean;
  sira: number | null; surum: number; aski: AskiAraligi[]; uyanma: Date | null; askida_neden: string | null;
  evde_yok: number; teshis: string | null; olaylar: Olay[];
  // EK-12
  btk_sikayet: { tarih: Date; reopen: boolean; tcs: Date | null } | null;
  aramalar: AramaKaydi[];
}

let IMLEC = 1000;
let OBEK_SURUMU = 7;
const ISLER: SahteIs[] = [];
const obekBul = (il: string, ilce: string, mh: string): number | null => {
  for (const o of OBEK_TANIMLARI) {
    if (o.mahalleler.some(([a, b, c]) => a === il && b === ilce && c === mh)) return o.id;
  }
  for (const o of OBEK_TANIMLARI) {
    if (o.mahalleler.some(([a, b, c]) => a === il && b === ilce && c === '*')) return o.id;
  }
  return null;
};

function isleriUret(): void {
  const t0 = simdi();
  for (let i = 0; i < 40; i++) {
    const durum = DURUM_DAGILIMI[i];
    const [task, serit, btkSaat] = sec(TASKLAR);
    let yer = sec(YERLER.slice(0, 12));
    let triyaj: IsSatir['triyaj_nedeni'] = null;
    if (durum === 'triyaj') {
      const n = i % 3;
      yer = n === 0 ? YERLER[13] : YERLER[12];
      triyaj = n === 0 ? 'il_disi' : 'obeksiz';
    }
    const acilisDk = -Math.floor(rnd() * 60 * 40) - 20;                  // 20 dk – 40 saat önce
    const acilis = eklenmis(t0, acilisDk);
    const gorulme = eklenmis(acilis, Math.floor(rnd() * 40) + 5);
    const obek = durum === 'triyaj' ? null : obekBul(yer[0], yer[1], yer[2]);
    const teknik = obek ? OBEK_TANIMLARI.find((o) => o.id === obek)?.sahip ?? null : null;
    const atanmis = ['atandi', 'yolda', 'sahada', 'ulasilamadi', 'cozuldu', 'kapandi'].includes(durum);
    const atananId = atanmis ? (teknik ?? SAHTE_TEKNIKLER[i % 4].id) : null;
    const randevuBas = eklenmis(t0, (Math.floor(rnd() * 6) - 1) * 120);
    randevuBas.setMinutes(0, 0, 0);
    const bayi = i === 33 || i === 34;
    const no = bayi ? `B-${zamanMetni(t0).slice(2, 10).replace(/-/g, '')}-00${i - 32}` : String(412000000 + i * 7919);
    const ad = `${ADLAR[i % ADLAR.length]} ${SOYADLAR[(i * 5) % SOYADLAR.length]}`;
    const is: SahteIs = {
      is_no: no, boss_task_no: bayi ? null : no, kaynak: bayi ? 'bayi' : 'boss',
      kanal_grubu: bayi ? 'dehanet' : sec(['global', 'global', 'global', 'dehanet', 'bos', 'diger_bayi'] as const),
      task_adi: task, serit, btk_hedef_saat: btkSaat,
      durum, durum_zamani: eklenmis(gorulme, 10),
      yer, obek_id: obek, obek_elle_id: durum === 'triyaj' || i !== 7 ? null : 3, triyaj_nedeni: triyaj,
      konum_yaklasik: i % 6 === 0,
      acilis, gorulme,
      musteri_adi: ad, musteri_no: String(5550000000 + i * 1111).slice(0, 10), adres: `${sec(SITELER)} ${yer[2]} Mah. ${yer[1]}/${yer[0]}`,
      atanan_id: atananId,
      randevu: durum === 'randevulu' || (atanmis && i % 2 === 0)
        ? { bas: randevuBas, bit: eklenmis(randevuBas, 120), teyitli: i % 4 === 0, kaynak: i % 5 === 0 ? 'boss' : 'biz' } : null,
      oneri_id: !atanmis && durum !== 'triyaj' && durum !== 'altyapi' ? teknik : null,
      boss_ekip: i % 9 === 1 ? 'MERKEZ EKIP 3' : (atanmis && i % 3 === 0 ? 'ALI KAYA EKIBI' : null),
      boss_bekleyen: atanmis && i % 4 === 1 ? 'ekip' : (atanmis && i % 7 === 2 ? 'ekip,randevu' : null),
      boss_islendi: null,
      ticket: durum === 'altyapi' ? { id: 12, konu: 'SİNYAL YOK', durum: 'AÇIK', gun: 3 } : null,
      binada_acik_ticket: durum === 'altyapi' || i === 5 ? 1 : 0,
      tekrar: i % 13 === 4, yeniden: i % 17 === 3 ? 2 : 1, kotu_gecmis: i % 19 === 6,
      sira: atanmis ? (i % 6) + 1 : null, surum: 1 + (i % 3),
      aski: [], uyanma: null, askida_neden: null, evde_yok: durum === 'ulasilamadi' ? 1 + (i % 2) : 0,
      teshis: null, olaylar: [],
      btk_sikayet: serit === 'BTK' && i % 10 === 3
        ? { tarih: eklenmis(t0, -60 * 24 * (6 + (i % 4))), reopen: i % 20 === 13, tcs: null } : null,
      aramalar: [],
    };
    if (i === 11) {       // EK-12.5: bayiye düşmüş 40 Kanal Şikâyeti — süresi kaçmış, en üstte
      is.task_adi = 'Kanal Şikayeti'; is.serit = 'MASA'; is.btk_hedef_saat = null;
    }
    if (durum === 'ulasilamadi') {   // EK-12.4: 1. günün iki araması yapılmış, SMS'i BOSS'a işlenecek
      const a1 = eklenmis(t0, -300); a1.setMinutes(0, 0, 0);
      is.aramalar = [
        { zaman: zamanMetni(a1), sonuc: 'ulasilamadi', sure_sn: 35, webphone: true, sms: true, yeni_numara: false, kisi: 'Selin Aksoy' },
        { zaman: zamanMetni(eklenmis(a1, 190)), sonuc: 'mesgul_kapali', sure_sn: null, webphone: true, sms: false, yeni_numara: false, kisi: 'Selin Aksoy' },
      ];
      is.boss_bekleyen = 'sms';
    }
    if (durum === 'askida') {
      const bas = eklenmis(t0, -180 - i * 7);
      const durdurur = i % 2 === 0;
      is.aski.push({ id: 500 + i, baslama: zamanMetni(bas), bitis: null, neden: durdurur ? 'Abone kaynaklı' : 'Malzeme bekleniyor',
                     kaynak: i % 3 === 0 ? 'elle' : 'boss', durdurur, yaklasik: i % 3 !== 0, sure_dk: 180 + i * 7 });
      is.askida_neden = is.aski[0].neden;
      is.uyanma = i % 4 === 1 ? null : eklenmis(t0, 90 + i);
    }
    if (i === 37) {       // EK-12.6: kesinti bülteni yüzünden askıda ("Genel arıza — sevk etme")
      is.aski = [{ id: 537, baslama: zamanMetni(eklenmis(t0, -95)), bitis: null, neden: 'Genel arıza (SOL kaynaklı) · bülten 123456',
                   kaynak: 'elle', durdurur: true, yaklasik: false, sure_dk: 95 }];
      is.askida_neden = is.aski[0].neden; is.uyanma = eklenmis(t0, 24 * 60 - 95);
    }
    if (i === 24) {       // kapanmış eski bir askı: BTK saati 1 s 20 dk durmuş
      is.aski.unshift({ id: 480, baslama: zamanMetni(eklenmis(t0, -900)), bitis: zamanMetni(eklenmis(t0, -820)), neden: 'Abone kaynaklı',
                        kaynak: 'boss', durdurur: true, yaklasik: true, sure_dk: 80 });
    }
    is.olaylar = olaylariUret(is);
    ISLER.push(is);
  }
}

function olaylariUret(is: SahteIs): Olay[] {
  const o: Olay[] = [{ id: ++IMLEC, zaman: zamanMetni(is.gorulme), kisi: null, tur: 'olustu', ozet: 'Rapordan geldi', notu: null }];
  if (is.atanan_id) {
    const t = SAHTE_TEKNIKLER.find((x) => x.id === is.atanan_id);
    o.push({ id: ++IMLEC, zaman: zamanMetni(eklenmis(is.gorulme, 9)), kisi: 'Selin Aksoy', tur: 'atama',
             ozet: `${t ? kisaAd(t.ad) : '—'}'ya atadı · 9 dk içinde`, notu: null });
  }
  if (is.durum === 'yolda' || is.durum === 'sahada') {
    o.push({ id: ++IMLEC, zaman: zamanMetni(eklenmis(is.gorulme, 40)), kisi: null, tur: 'durum', ozet: 'Yola çıktı', notu: null });
  }
  return o.reverse();
}

function kisaAd(ad: string): string {
  const p = ad.trim().split(/\s+/);
  return p.length > 1 ? `${p[0]} ${p[p.length - 1][0]}.` : ad;
}

// ----------------------------------------------------------------------------- satır üretimi
const ACIK = (d: Durum) => d !== 'cozuldu' && d !== 'kapandi';
function renkHesap(acilis: Date, hedef: Date, an: Date): { renk: Renk; gecikti: boolean } {
  const oran = (an.getTime() - acilis.getTime()) / Math.max(1, hedef.getTime() - acilis.getTime());
  if (oran >= 1) return { renk: 'kirmizi', gecikti: true };
  return { renk: oran < 0.5 ? 'yesil' : oran < 0.8 ? 'amber' : 'kirmizi', gecikti: false };
}
function durduDk(is: SahteIs, an: Date): number {
  return is.aski.filter((a) => a.durdurur).reduce((t, a) => {
    const bas = zamanOku(a.baslama).getTime();
    const bit = a.bitis ? zamanOku(a.bitis).getTime() : an.getTime();
    return t + Math.max(0, Math.round((bit - bas) / DK));
  }, 0);
}

/** EK-12.1 varsayılanı: iş tipine göre hedef (SL) saati; eşleşmeyen 24 s. */
function hedefSaat(task: string): number {
  const k = sadeHarf(task);
  if (k.includes('MODEMDEGISIKLIGI')) return 168;
  if (k.includes('CIHAZIADEBEKLENIYOR')) return 360;
  return 24;
}
const ISGUNU = (bas: Date, n: number): Date => {
  const d = new Date(bas.getTime());
  let kalan = n;
  while (kalan > 0) { d.setDate(d.getDate() + 1); if (d.getDay() !== 0 && d.getDay() !== 6) kalan--; }
  d.setHours(23, 59, 59, 0);
  return d;
};
function btkSikayet(is: SahteIs, an: Date): BtkSikayet | null {
  const b = is.btk_sikayet;
  if (!b) return null;
  const sure = b.reopen ? 5 : 10;
  let gecen = 0;
  const d = new Date(b.tarih.getTime());
  while (d.toDateString() !== an.toDateString() && d < an) { d.setDate(d.getDate() + 1); if (d.getDay() !== 0 && d.getDay() !== 6) gecen++; }
  const son = ISGUNU(b.tarih, sure);
  const alarmlar = b.reopen ? [3, 5] : [8, 10];
  const alarm = alarmlar.filter((x) => gecen >= x).pop();
  return { baslama: zamanMetni(b.tarih), reopen: b.reopen, sure_is_gunu: sure, gecen_is_gunu: gecen, kalan_is_gunu: Math.max(0, sure - gecen),
           son_gun: zamanMetni(son), alarm: alarm ? `${alarm}. iş günü` : null, gecikti: an > son,
           tcs: b.tcs ? zamanMetni(b.tcs) : null, btk_kapali: !!b.tcs };
}
function merdiven(is: SahteIs, an: Date): AramaMerdiveni | null {
  if (!ACIK(is.durum)) return null;
  const son = [...is.aramalar].reverse().findIndex((a) => a.yeni_numara);
  const liste = son < 0 ? is.aramalar : is.aramalar.slice(is.aramalar.length - 1 - son);
  const basarisiz = liste.filter((a) => ['ulasilamadi', 'mesgul_kapali', 'dit'].includes(a.sonuc) && a.webphone);
  const gunler = new Map<string, number>();
  basarisiz.forEach((a) => gunler.set(a.zaman.slice(0, 10), (gunler.get(a.zaman.slice(0, 10)) ?? 0) + 1));
  const ulasildi = liste.some((a) => a.sonuc === 'ulasildi');
  const gecerli = basarisiz.length;
  const tamam = !ulasildi && gecerli >= 4 && gunler.size >= 2;
  const sonZaman = basarisiz.length ? zamanOku(basarisiz[basarisiz.length - 1].zaman) : null;
  let sonraki: Date | null = null;
  if (!ulasildi && !tamam) {
    sonraki = sonZaman ? eklenmis(sonZaman, 180) : an;
    if (gunler.size === 1 && (gunler.values().next().value ?? 0) >= 2 && sonZaman) {
      sonraki = new Date(sonZaman.getTime()); sonraki.setDate(sonraki.getDate() + 1); sonraki.setHours(10, 0, 0, 0);
    }
    if (sonraki < an) sonraki = an;
  }
  return { deneme: basarisiz.length, gecerli, gerekli: 4, gunler: [...gunler.values()], son: sonZaman ? zamanMetni(sonZaman) : null,
           sonraki: sonraki ? zamanMetni(sonraki) : null, tamam, eksik: tamam || ulasildi ? null : `${4 - gecerli} arama daha gerekli (${gecerli}/4)`,
           sms_eksik: basarisiz.filter((a) => !a.sms).length, ulasildi,
           ata_havuzu: liste.length > 0 && liste[liste.length - 1].sonuc === 'yanlis_no' };
}

function satir(is: SahteIs, an = simdi()): IsSatir {
  const son24 = eklenmis(is.acilis, hedefSaat(is.task_adi) * 60);
  const btkHedef = is.btk_hedef_saat ? eklenmis(is.acilis, is.btk_hedef_saat * 60) : null;
  const durdu = durduDk(is, an);
  const btkNet = btkHedef ? eklenmis(btkHedef, durdu) : null;
  const btkDurdu = is.aski.some((a) => a.durdurur && !a.bitis);
  const hedef = btkNet ?? son24;
  const { renk, gecikti } = ACIK(is.durum) ? renkHesap(is.acilis, hedef, an) : { renk: 'yesil' as Renk, gecikti: false };
  const obekId = is.obek_elle_id ?? is.obek_id;
  const obek = obekId ? OBEK_TANIMLARI.find((o) => o.id === obekId) ?? null : null;
  const atanan = is.atanan_id ? SAHTE_TEKNIKLER.find((t) => t.id === is.atanan_id) ?? null : null;
  const oneri = is.oneri_id && !is.atanan_id ? SAHTE_TEKNIKLER.find((t) => t.id === is.oneri_id) ?? null : null;
  const rozetler: Rozet[] = [];
  if (is.serit === 'BTK') rozetler.push('btk');
  if (is.ticket || is.binada_acik_ticket) rozetler.push('ticket');
  if (is.tekrar) rozetler.push('tekrar');
  if (is.kaynak === 'bayi' || is.kanal_grubu === 'dehanet') rozetler.push('bayi');
  if (is.kanal_grubu === 'global') rozetler.push('global');
  if (is.konum_yaklasik) rozetler.push('konum');
  if (is.boss_bekleyen && !is.boss_islendi) rozetler.push('boss_islenecek');
  if (is.durum === 'cozuldu' && is.is_no.endsWith('3')) rozetler.push('boss_acik');
  if (is.yeniden > 1) rozetler.push('yeniden');
  if (is.obek_elle_id) rozetler.push('elle');
  const kova: Kova = DURUM_KOVA[is.durum];
  const oneriBas = eklenmis(an, 60); oneriBas.setMinutes(0, 0, 0);
  return {
    is_no: is.is_no, boss_task_no: is.boss_task_no, kaynak: is.kaynak, kanal_grubu: is.kanal_grubu,
    task_adi: is.task_adi, serit: is.serit, btk_hedef_saat: is.btk_hedef_saat,
    durum: is.durum, kova, durum_zamani: zamanMetni(is.durum_zamani),
    il: is.yer[0], ilce: is.yer[1], mahalle: is.triyaj_nedeni === 'il_disi' ? is.yer[2] : is.yer[2],
    musteri_adi: is.musteri_adi, musteri_no: is.musteri_no, kisa_adres: `${is.yer[2]} · ${is.adres.split(' ').slice(0, 2).join(' ')}`,
    obek: obek ? { id: obek.id, ad: obek.ad, renk: obek.renk } : null, obek_elle: !!is.obek_elle_id,
    triyaj_nedeni: is.triyaj_nedeni,
    triyaj_metni: is.triyaj_nedeni === 'il_disi' ? `Adres ${is.yer[0]} yazıyor; bölgemiz Bursa ve Yalova.`
      : is.triyaj_nedeni === 'obeksiz' ? `Mahallesi hiçbir öbekte değil: ${is.yer[2]} · ${is.yer[1]}.` : null,
    konum_yaklasik: is.konum_yaklasik, lat: is.yer[3] + (rnd() - 0.5) * 0.004, lon: is.yer[4] + (rnd() - 0.5) * 0.004,
    acilis: zamanMetni(is.acilis), son24: zamanMetni(son24), btk_hedef: btkHedef ? zamanMetni(btkHedef) : null,
    kalan_dk: Math.round((son24.getTime() - an.getTime()) / DK), renk, gecikti,
    bekleme_dk: kova === 'atanmadi' ? Math.round((an.getTime() - Math.max(is.gorulme.getTime(), an.getTime() - 40 * DK)) / DK) : null,
    randevu: is.randevu ? { bas: zamanMetni(is.randevu.bas), bit: zamanMetni(is.randevu.bit), teyitli: is.randevu.teyitli, kaynak: is.randevu.kaynak } : null,
    atanan: atanan ? kisi(atanan) : null,
    oneri: oneri ? { teknik: kisi(oneri), bas: zamanMetni(oneriBas), bit: zamanMetni(eklenmis(oneriBas, 120)),
                     neden: `${obek?.ad ?? ''} öbeğinin teknisyeni · bugün ${bugunYuk(oneri.id)}/${oneri.kapasite}` } : null,
    boss_ekip: is.boss_ekip,
    ticket: is.ticket, binada_acik_ticket: is.binada_acik_ticket,
    rozetler, kotu_gecmis: is.kotu_gecmis, sira: is.sira, surum: is.surum,
    btk_durdu: btkDurdu,
    btk_hedef_net: btkNet ? zamanMetni(btkNet) : null,
    btk_kalan_dk: btkNet ? Math.round((btkNet.getTime() - an.getTime()) / DK) : null,
    oncelik: ACIK(is.durum) && sadeHarf(is.task_adi).includes('KANALSIKAYET') ? 'Kanal şikâyeti: süre zaten kaçmış — önce bu' : null,
    btk_sikayet: btkSikayet(is, an),
    genel_ariza: is.durum === 'askida' && (is.askida_neden ?? '').startsWith('Genel arıza'),
  };
}

function bugunYuk(teknikId: number): number {
  return ISLER.filter((i) => i.atanan_id === teknikId && ACIK(i.durum)).length;
}

function birincil(is: SahteIs): IsAyrinti['birincil'] {
  switch (is.durum) {
    case 'triyaj': return 'obege_ata';
    case 'bekliyor': return is.binada_acik_ticket ? 'ticketa_bagla' : 'ata';
    case 'randevulu': return 'ata';
    case 'ulasilamadi': return 'yeniden_ata';
    case 'askida': return 'uyandir';
    case 'altyapi': return 'ticketi_ac';
    case 'merkeze': return 'sahaya_al';
    default: return null;
  }
}

function ayrinti(is: SahteIs, an = simdi()): IsAyrinti {
  const s = satir(is, an);
  const durdu = durduDk(is, an);
  const giden: BossGiden | null = is.boss_bekleyen && !is.boss_islendi ? {
    is_no: is.is_no, boss_task_no: is.boss_task_no,
    alanlar: {
      ekip: is.atanan_id ? SAHTE_TEKNIKLER.find((t) => t.id === is.atanan_id)?.boss_ekip ?? SAHTE_TEKNIKLER.find((t) => t.id === is.atanan_id)?.ad ?? null : null,
      randevu_baslangic: is.randevu ? zamanMetni(is.randevu.bas) : null,
      randevu_bitis: is.randevu ? zamanMetni(is.randevu.bit) : null,
      ...(is.boss_bekleyen.split(',').includes('sms') ? { talep_ulasamama_sms: true } : {}),
    },
    neden: is.boss_bekleyen, olusma: zamanMetni(eklenmis(is.gorulme, 9)),
  } : null;
  const soz = `Müşteriye söz: ${is.acilis.getHours() < 12 ? 'bugün 17:00\'ye' : 'yarın 12:00\'ye'} kadar`;
  return {
    ...s,
    adres: is.adres,                         // musteri_tel yalnız ayar 'acik' iken gelir
    lokasyon: is.konum_yaklasik ? null : String(10000000 + ISLER.indexOf(is) * 37),
    mahalle_kaynak: is.konum_yaklasik ? 'adres' : 'lokasyon',
    konum_kaynak: is.konum_yaklasik ? 'mahalle_merkezi' : 'bina',
    bina: is.konum_yaklasik ? null : { serial: `BN-${String(900000 + ISLER.indexOf(is))}`, ad: is.adres.split(' ').slice(0, 2).join(' '),
                                      location_id: String(10000000 + ISLER.indexOf(is) * 37), lat: s.lat ?? 40.2, lon: s.lon ?? 29 },
    boss: { durum: is.durum === 'askida' ? 'Askıya alındı' : 'Açık', randevu_durumu: is.randevu?.kaynak === 'boss' ? 'Randevulu' : 'Randevusuz',
            randevu_bas: is.randevu?.kaynak === 'boss' ? zamanMetni(is.randevu.bas) : null,
            randevu_bit: is.randevu?.kaynak === 'boss' ? zamanMetni(is.randevu.bit) : null,
            ekip: is.boss_ekip, aski_nedeni: is.aski.find((a) => a.kaynak === 'boss')?.neden ?? null,
            sl: 'SL Geçmedi', sl_saat: 14.5, son_aciklama: null, bekleyen: is.boss_bekleyen,
            islendi: is.boss_islendi ? zamanMetni(is.boss_islendi) : null },
    uyanma: is.uyanma ? zamanMetni(is.uyanma) : null, askida_neden: is.askida_neden, evde_yok_sayisi: is.evde_yok,
    masa_vade: is.serit === 'BTK' && !is.kotu_gecmis ? zamanMetni(eklenmis(is.gorulme, 45)) : null,
    teshis_sonucu: is.teshis,
    soz, birincil: birincil(is),
    izinler: { ata: ACIK(is.durum), randevu: ACIK(is.durum), ticket: true, obek: true, iletisim: false,
               durumlar: ['askida', 'merkeze', 'cozuldu'], ofisten_kapat: ACIK(is.durum), yeniden_ac: is.durum === 'cozuldu',
               boss_bagla: is.kaynak === 'bayi' && !is.boss_task_no },
    boss_url: null,
    bayi_oneri: is.kaynak === 'bayi' && !is.boss_task_no ? { boss_task_no: '412999999' } : null,
    olaylar: is.olaylar.slice(0, 50),
    aski: is.aski.map((a) => ({ ...a, sure_dk: a.bitis ? a.sure_dk : Math.round((an.getTime() - zamanOku(a.baslama).getTime()) / DK) })),
    aski_durdu_dk: durdu,
    btk_net_gecen_dk: is.serit === 'BTK' ? Math.round((an.getTime() - is.acilis.getTime()) / DK) - durdu : null,
    boss_giden: giden,
    kapanis: is.durum === 'kapandi' ? zamanMetni(eklenmis(an, -60)) : null,
    kapanis_nedeni: is.durum === 'kapandi' ? 'cozuldu_dogrulandi' : null,
    acilma_sayisi: is.yeniden, ilk_gorulme: zamanMetni(is.gorulme), gorulme_zamani: zamanMetni(is.gorulme),
    aski_uyari: is.aski.some((a) => !a.bitis && a.kaynak === 'elle' && /abone/i.test(a.neden ?? '') && !a.durdurur)
      ? "Geçersiz askı: Ulaşılamadı SMS'i gönderilmemiş. Süre BTK saatine eklenmiyor." : null,
    aramalar: is.aramalar.slice(-20),
    merdiven: merdiven(is, an),
  };
}

// ----------------------------------------------------------------------------- dışa açılan örnekler
isleriUret();

function sayac(satirlar: IsSatir[]): IslerSayac {
  const acik = satirlar.filter((s) => ACIK(s.durum));
  const atanmamis = acik.filter((s) => s.kova === 'atanmadi');
  const an = simdi();
  return {
    acik: acik.length,
    asan24: acik.filter((s) => zamanOku(s.son24) < an).length,
    atanmamis: atanmamis.length,
    en_eski_atanmamis_dk: atanmamis.length ? Math.max(...atanmamis.map((s) => s.bekleme_dk ?? 0)) : null,
    btk48: acik.filter((s) => s.serit === 'BTK' && an.getTime() - zamanOku(s.acilis).getTime() > 48 * 60 * DK).length,
    kontrol: acik.filter((s) => s.durum === 'triyaj').length,
    boss_bekleyen: acik.filter((s) => s.rozetler.includes('boss_islenecek')).length,
    konum_yaklasik: acik.filter((s) => s.konum_yaklasik).length,
    aranacak: acik.filter((s) => s.durum === 'ulasilamadi' || (s.serit === 'BTK' && s.kova === 'atanmadi')).length,
    eslesmemis_ekip: 1,
    askida_btk_durdu: acik.filter((s) => s.btk_durdu).length,
    askida_uyanmasiz: ISLER.filter((i) => i.durum === 'askida' && !i.uyanma).length,
  };
}

function hikaye(sy: IslerSayac, satirlar: IsSatir[]): string {
  const yakin = satirlar.filter((s) => ACIK(s.durum) && s.kalan_dk > 0 && s.kalan_dk < 120).length;
  if (!sy.acik) return 'Açık iş yok. Yeni rapor gelince burada olur.';
  const ilk = `Bugün ${sy.acik.toLocaleString('tr-TR')} açık iş var.`;
  if (yakin) return `${ilk} ${yakin}'${yakin === 1 ? 'inin' : 'sinin'} 24 saatine 2 saatten az kaldı — önce onlar.`;
  if (sy.atanmamis) return `${ilk} ${sy.atanmamis} iş atanmayı bekliyor.`;
  return `${ilk} Atanmamış iş kalmadı.`;
}

function sonAktarim(): IslerYanit['son_aktarim'] {
  const zaman = eklenmis(simdi(), -12);
  return { id: 41, zaman: zamanMetni(zaman), dosya_adi: 'TeknikTaskDetayRaporu.xlsx', is_sayisi: ISLER.length, yas_dk: 12, renk: 'yesil',
           yontem: 'klasor', fark: { yeni: 4, degisen: 9, kaybolan: 2, yeniden_acilan: 1, degismeyen: 24 } };
}

export function sahteIslerYanit(kova: 'acik' | 'biten' = 'acik'): IslerYanit {
  const an = simdi();
  const hepsi = ISLER.map((i) => satir(i, an));
  const isler = hepsi.filter((s) => (kova === 'acik' ? ACIK(s.durum) : !ACIK(s.durum)));
  const sy = sayac(hepsi);
  return { sunucu_zamani: zamanMetni(an), imlec: IMLEC, obek_surumu: OBEK_SURUMU, mod: 'normal',
           son_aktarim: sonAktarim(), sayac: sy, isler, hikaye: hikaye(sy, hepsi), onay_bekleyen: [] };
}

export function sahteDegisim(imlec: number): DegisimYanit {
  const an = simdi();
  const degisen = ISLER.filter((i) => i.olaylar.some((o) => o.id > imlec)).map((i) => satir(i, an));
  const hepsi = ISLER.map((i) => satir(i, an));
  return { imlec: IMLEC, isler: degisen, gorunmez: [], obek_surumu: OBEK_SURUMU, son_aktarim: sonAktarim(),
           sayac: sayac(hepsi), sunucu_zamani: zamanMetni(an), onay_bekleyen: [] };
}

export function sahteIsAyrinti(isNo: string): IsAyrinti | null {
  const is = ISLER.find((i) => i.is_no === isNo);
  return is ? ayrinti(is) : null;
}

export function sahteObekler(): ObeklerYanit {
  const an = simdi();
  const satirlar = ISLER.filter((i) => ACIK(i.durum)).map((i) => satir(i, an));
  const obekler: Obek[] = OBEK_TANIMLARI.map((o) => {
    const oi = satirlar.filter((s) => s.obek?.id === o.id);
    const sahip = SAHTE_TEKNIKLER.find((t) => t.id === o.sahip);
    const yedek = SAHTE_TEKNIKLER.find((t) => t.id === o.yedek);
    return {
      id: o.id, ad: o.ad, renk: o.renk, sahip: sahip ? kisi(sahip) : null, yedek: yedek ? kisi(yedek) : null,
      mahalleler: o.mahalleler.map(([il, ilce, mh]) => ({
        ref: `${il}/${ilce}/${mh}`, il, ilce, mahalle: mh === '*' ? 'İlçenin tamamı' : mh, tum_ilce: mh === '*',
        acik: oi.filter((s) => s.ilce === ilce && (mh === '*' || s.mahalle === mh)).length,
      })),
      acik: oi.length, geciken: oi.filter((s) => s.gecikti).length, btk: oi.filter((s) => s.serit === 'BTK').length,
      atanmamis: oi.filter((s) => s.kova === 'atanmadi').length,
    };
  });
  return { surum: OBEK_SURUMU, obekler,
           obeksiz: [{ il: 'Bursa', ilce: 'Kestel', mahalle: 'Kurtul', mahalle_id: 612, acik: satirlar.filter((s) => s.mahalle === 'Kurtul').length }] };
}

const ILCELER: Array<[string, string]> = [
  ['Bursa', 'Büyükorhan'], ['Bursa', 'Gemlik'], ['Bursa', 'Gürsu'], ['Bursa', 'Harmancık'], ['Bursa', 'İnegöl'], ['Bursa', 'İznik'],
  ['Bursa', 'Karacabey'], ['Bursa', 'Keles'], ['Bursa', 'Kestel'], ['Bursa', 'Mudanya'], ['Bursa', 'Mustafakemalpaşa'],
  ['Bursa', 'Nilüfer'], ['Bursa', 'Orhaneli'], ['Bursa', 'Orhangazi'], ['Bursa', 'Osmangazi'], ['Bursa', 'Yenişehir'],
  ['Bursa', 'Yıldırım'], ['Yalova', 'Altınova'], ['Yalova', 'Armutlu'], ['Yalova', 'Çınarcık'], ['Yalova', 'Çiftlikköy'],
  ['Yalova', 'Merkez'], ['Yalova', 'Termal'],
];
const sadeHarf = (s: string) => s.toLocaleUpperCase('tr-TR').replace(/[ÇĞİÖŞÜÂÎÛ]/g, (h) => ({ Ç: 'C', Ğ: 'G', İ: 'I', Ö: 'O', Ş: 'S', Ü: 'U', Â: 'A', Î: 'I', Û: 'U' }[h] ?? h)).replace(/[^A-Z0-9]/g, '');

export function sahteIlceler(): IlceKaydi[] {
  return ILCELER.map(([il, ilce]) => {
    const tum = OBEK_TANIMLARI.find((o) => o.mahalleler.some(([a, b, c]) => a === il && b === ilce && c === '*'));
    return { il, ilce, il_k: sadeHarf(il), ilce_k: sadeHarf(ilce), mahalle_sayisi: YERLER.filter((y) => y[1] === ilce).length * 12,
             tum_ilce_obek: tum ? { id: tum.id, ad: tum.ad } : null };
  });
}

export function sahteMahalleler(q = ''): MahallelerYanit {
  const k = sadeHarf(q);
  const mahalleler = YERLER.slice(0, 13).map(([il, ilce, ad], j) => {
    const ob = obekBul(il, ilce, ad);
    const o = OBEK_TANIMLARI.find((x) => x.id === ob);
    return { id: 600 + j, il, ilce, ad, ref: `${il}/${ilce}/${ad}`, kaynak: j % 4 === 0 ? 'bina' : 'liste',
             obek: o ? { id: o.id, ad: o.ad } : null, acik: ISLER.filter((i) => ACIK(i.durum) && i.yer[2] === ad).length };
  }).filter((m) => !k || sadeHarf(m.ad).includes(k) || sadeHarf(m.ilce).includes(k));
  const ilceler = sahteIlceler().filter((i) => !k || sadeHarf(i.ilce).includes(k) || mahalleler.some((m) => m.ilce === i.ilce));
  return { ilceler, mahalleler, oneriler: k && !mahalleler.length ? [{ id: 603, ad: 'Ertuğrul', ilce: 'Nilüfer', benzerlik: 0.72 }] : [] };
}

export function sahteTeknikler(): TeknikOzet[] {
  return SAHTE_TEKNIKLER.map((t) => ({
    ...t,
    bugun: { atanan: bugunYuk(t.id), biten: ISLER.filter((i) => i.atanan_id === t.id && !ACIK(i.durum)).length,
             btk: ISLER.filter((i) => i.atanan_id === t.id && ACIK(i.durum) && i.serit === 'BTK').length },
    obekler: OBEK_TANIMLARI.filter((o) => o.sahip === t.id).map((o) => ({ id: o.id, ad: o.ad })),
  }));
}

export function sahteBossEkip(): BossEkipYanit {
  return { eslesmemis: [{ boss_ekip: 'MERKEZ EKIP 3', is: ISLER.filter((i) => i.boss_ekip === 'MERKEZ EKIP 3' && !i.atanan_id).length || 3 }],
           eslesmis: [{ boss_ekip: 'ALI KAYA EKIBI', kisi: kisi(SAHTE_TEKNIKLER[0]) }, { boss_ekip: 'VELI DEMIR', kisi: kisi(SAHTE_TEKNIKLER[1]) }] };
}

export function sahteBossGiden(): BossGiden[] {
  return ISLER.filter((i) => i.boss_bekleyen && !i.boss_islendi).map((i) => ayrinti(i).boss_giden!).filter(Boolean);
}

export function sahteAranacaklar(): AranacakYanit {
  const an = simdi();
  const s = ISLER.filter((i) => ACIK(i.durum)).map((i) => satir(i, an));
  return {
    sunucu_zamani: zamanMetni(an),
    bantlar: [
      { bant: 'btk_teshis', isler: s.filter((x) => x.serit === 'BTK' && x.kova === 'atanmadi' && !x.kotu_gecmis).slice(0, 5) },
      { bant: 'ulasilamadi', isler: s.filter((x) => x.durum === 'ulasilamadi') },
      { bant: 'uyanan', isler: s.filter((x) => x.durum === 'askida').slice(0, 2) },
      { bant: 'masa', isler: s.filter((x) => x.serit === 'MASA') },
    ],
  };
}

export function sahteIslerim(teknikId = 101): IslerimYanit {
  const an = simdi();
  const kendi = ISLER.filter((i) => i.atanan_id === teknikId);
  return {
    sunucu_zamani: zamanMetni(an), imlec: IMLEC,
    isler: kendi.filter((i) => ACIK(i.durum)).sort((a, b) => (a.sira ?? 99) - (b.sira ?? 99)).map((i) => {
      const a = ayrinti(i, an);
      // teknikte kısa ad; BOSS ekip adı ve bekleyen bilgisi gösterilmez
      return { ...a, musteri_adi: kisaAd(i.musteri_adi), boss_ekip: undefined };
    }),
    bitenler: kendi.filter((i) => !ACIK(i.durum)).map((i) => satir(i, an)),
  };
}

export function sahteAktarimSonucu(): AktarimSonucu {
  return { aktarim_id: 42, fark: { yeni: 12, degisen: 30, kaybolan: 30, yeniden_acilan: 3, degismeyen: 392 },
           cikarilan: { kurulum: 1072, ikinci_donanim: 119, istisna_tutulan: 2, satir: 1628, adlar: { 'Kurulum': 1072, '2. Donanım': 119 } },
           kontrol: 3, boss_atamasi: 5, sure_sn: 1.4, yedek: 'saha-aktarim-20260930-113812.db', tam_kapsam: true,
           aski: { acilan: 4, kapanan: 2 } };
}

export function sahteAktarimOnay(): AktarimOnay {
  return { hata: 'Bu raporda 180 açık iş yok (açık işlerin %41\'i). Rapor süzgeçli ya da tek ilçe indirilmiş olabilir.',
           kod: 'onay_gerekli', aktarim_id: 43, fark: { yeni: 0, degisen: 12, kaybolan: 180, yeniden_acilan: 0, degismeyen: 245 },
           nedenler: ['cok_kaybolan'], acik: 437, kaybolan_oran: 0.41, son_rapor_zamani: zamanMetni(eklenmis(simdi(), -12)) };
}

export function sahteAktarimGecmisi(): AktarimKaydi[] {
  const an = simdi();
  return Array.from({ length: 6 }, (_, j) => ({
    id: 41 - j, zaman: zamanMetni(eklenmis(an, -12 - j * 95)), yukleyen: j % 2 ? 'Selin Aksoy' : null,
    dosya_adi: 'TeknikTaskDetayRaporu.xlsx', yontem: (j % 2 ? 'surukle' : 'klasor') as AktarimKaydi['yontem'],
    is_sayisi: 437 - j * 3, yeni: 12 - j, degisen: 30, kaybolan: 8, yeniden_acilan: j % 3, degismeyen: 390, cikarilan: 1191,
    durum: (j === 3 ? 'vazgecildi' : 'uygulandi') as AktarimKaydi['durum'], tam_kapsam: j !== 4,
    yedek: `saha-aktarim-2026093${j}.db`, hata: null,
  }));
}

export function sahteIzleme(): IzlemeDurumu {
  return { acik: true, klasorler: ['C:\\Users\\kullanici\\Downloads', 'C:\\Users\\kullanici\\Desktop'],
           desenler: ['TeknikTaskDetayRaporu*.xlsx'], yoklama_sn: 15, sabit_sn: 5,
           son_bakis: zamanMetni(eklenmis(simdi(), -0.2)),
           son_alinan: { aktarim_id: 41, zaman: zamanMetni(eklenmis(simdi(), -12)), dosya_adi: 'TeknikTaskDetayRaporu.xlsx',
                         sonuc: 'Yeni rapor alındı · 12 yeni iş, 3 kapandı' },
           onay_bekleyen: [] };
}

export function sahteIsAyarlari(): IsAyarlari {
  return {
    dilimler: ['08', '10', '12', '14', '16', '18'].map((b) => ({ bas: `${b}:00`, bit: `${String(Number(b) + 2).padStart(2, '0')}:00` })),
    mesai: { bas: '08:00', bit: '20:00' }, musteri_tel: 'kapali', boss_task_url: null,
    aski_nedenleri: [
      { kod: 'abone', metin: 'Abone kaynaklı (müşteriye ulaşılamadı / müşteri istedi)', durdurur: true },
      { kod: 'abone_aksam', metin: 'Abone kaynaklı (akşam araması)', durdurur: true },
      { kod: 'malzeme', metin: 'Malzeme bekleniyor', durdurur: false },
      { kod: 'genel_ariza', metin: 'Genel arıza (SOL kaynaklı)', durdurur: true },
      { kod: 'bilgi_belge', metin: 'BTK süreci kaynaklı (Bilgi & Belge)', durdurur: true },
      { kod: 'tt', metin: 'TT kaynaklı', durdurur: false },
      { kod: 'altyapi', metin: 'Altyapı / şebeke kaynaklı', durdurur: false },
      { kod: 'ata', metin: 'İrtibat hatalı (ATA havuzu)', durdurur: false },
      { kod: 'diger', metin: 'Diğer', durdurur: false },
    ],
    son24_askida_durur: false, btk_durduran_aski: ['abone', 'bilgi belge', 'btk sureci', 'genel ariza'], kutlamalar: true,
    kapanis_nedenleri: [
      { kod: 'telefonda_cozuldu', metin: 'Telefonda çözüldü (canlı test yapıldı)' },
      { kod: 'iptal', metin: 'İptal' }, { kod: 'mukerrer', metin: 'Mükerrer kayıt' }, { kod: 'musteri_vazgecti', metin: 'Müşteri vazgeçti' },
      { kod: 'musteriye_ulasilamadi', metin: 'Müşteriye ulaşılamadı (arama merdiveni tamam)' },
    ],
    teknik_kapasite: 15,
  };
}

// ----------------------------------------------------------------------------- EK-12: kurallar ve kesinti
export function sahteKurallar(): KurallarYanit {
  const k = <T,>(deger: T, aciklama: string, teyit: string | null = null) =>
    ({ deger, varsayilan: deger, aciklama, teyit_bekliyor: teyit, degisti: false });
  return {
    hedef_saatleri: k({ varsayilan: 24, kurallar: [{ desen: 'MODEM DEGISIKLIGI', saat: 168, not: 'Modem değişim SL 7 gün' },
      { desen: 'CIHAZ IADE BEKLENIYOR', saat: 360, not: 'Cihaz İade Bekleniyor 15 gün' }, { desen: 'TT FIBER', saat: 48, not: 'TT fiber 48 s' },
      { desen: 'ATA', saat: 168, not: 'ATA 7 gün' }] }, 'İş tipine göre hedef süre (saat). Eşleşmeyen iş 24 saat.',
      "BOSS 'Modem Değişikliği' işinin 7 günlük modem değişim SL'ine girdiği teyit edilmeli."),
    serit_kurallari: k([{ desen: 'TV ARIZA', serit: 'BTK', btk_saat: 6 }, { desen: 'BAGLANTI PROBLEM', serit: 'BTK', btk_saat: 12 },
      { desen: 'ARAMA PROBLEM', serit: 'BTK', btk_saat: 12 }, { desen: 'DOPING', serit: 'BTK', btk_saat: 24 },
      { desen: 'KANAL SIKAYET', serit: 'MASA', btk_saat: null }], 'İş tipine göre şerit ve BTK hedefi.',
      "TV 6 s / Bağlantı 12 s belgede bulunamadı; FOX 'Hedef SL' değerinden geliyor."),
    oncelikli_isler: k([{ desen: 'KANAL SIKAYET', neden: 'Kanal şikâyeti: süre zaten kaçmış — önce bu' }], 'Listede en üste çıkan iş tipleri.'),
    btk_durduran_aski: k(['abone', 'bilgi belge', 'btk sureci', 'genel ariza'], 'Nedeninde bu sözcükler geçen askı BTK saatini durdurur.',
      'TT kaynaklı askının BTK saatini durdurup durdurmadığı belirsiz (varsayılan: durdurmaz).'),
    aski_sinirlari: k({ abone: 96, abone_uyari: 72, malzeme: 8, malzeme_btk: 2, genel_ariza: 168, bilgi_belge: 240, diger: 72, diger_btk: 24 },
      'Askının en uzun süresi (saat).'),
    aski_gecerlilik: k({ acik: true, webphone: true, sms: true, farkli_gun: 2, boss_askisina_guven: true },
      'Abone kaynaklı askının saati durdurması için gereken aramalar.'),
    arama_merdiveni: k({ pencere: '10:00-18:00', son_saat: '22:00', ara_saat: 3, gun1: 2, gun2: 2, min_sure_sn: 30, sms_zorunlu: true },
      'Ulaşılamayan müşteriyi arama kuralları.'),
    btk_sikayet: k({ ilk_is_gunu: 10, reopen_is_gunu: 5, alarm_ilk: [8, 10], alarm_reopen: [3, 5] }, 'BTK şikâyet süresi (iş günü) ve alarm günleri.'),
    resmi_tatiller: k(['01-01', '04-23', '05-01', '05-19', '07-15', '08-30', '10-29'], 'İş günü hesabında atlanan günler.'),
    kesinti_etkilenen: k(['BAGLANTI PROBLEM', 'TV ARIZA', 'ARAMA PROBLEM', 'DOPING'], 'Genel arızada sevk edilmeyen iş tipleri.'),
    kesinti_ornek_esigi: k(5, 'Bülten yokken verimlilik ekibine gönderilecek en az örnek.'),
    kesinti_ornek_saat: k(12, 'Örnek toplarken bakılan son saat.'),
  };
}

const KESINTILER: Kesinti[] = [{
  id: 1, no: '123456', tur: 'GPON', durum: 'devam', durum_metni: 'Devam ediyor', baslama: zamanMetni(eklenmis(simdi(), -95)),
  baslama_saat: '09:40', bitis: null, etki_musteri: 420, ekleyen: 'Selin Aksoy',
  ilceler: [{ il_k: 'BURSA', ilce_k: 'NILUFER', il: 'Bursa', ilce: 'Nilüfer' }], ilce_metni: 'Bursa/Nilüfer',
  ozet: 'TCELL SOC - NT ARIZA · ARIZA Başladı 09.40 – BURSA-NİLÜFER GPON KESİNTİSİ ETKİ: 3 SWITCH – 420 MÜŞTERİ', askida_is: 1,
}];
export function sahteKesintiler(): KesintiListesi { return { kesintiler: KESINTILER }; }
export function sahteKesintiAday(): KesintiAdaylari {
  return { esik: 5, saat: 12, gruplar: [{ il: 'Bursa', ilce: 'Yıldırım', adet: 6, is_nolar: ISLER.slice(0, 6).map((i) => i.is_no),
    paket: 'Toplu arıza şüphesi · Bursa/Yıldırım · son 12 saatte 6 iş\nTask No\tTask Adı\tMahalle\tAçılış\tMüşteri No\n'
      + ISLER.slice(0, 6).map((i) => `${i.is_no}\t${i.task_adi}\t${i.yer[2]}\t${zamanMetni(i.acilis).slice(0, 16)}\t${i.musteri_no}`).join('\n')
      + "\nHizmet ID ve seri no BOSS'tan eklenmeli." }] };
}

export function sahteTakip(): TakipYanit {
  const y = sahteIslerYanit();
  const an = simdi();
  return {
    sunucu_zamani: zamanMetni(an), hikaye: y.hikaye,
    manset: { acik: y.sayac.acik, asan24: y.sayac.asan24, atanmamis: y.sayac.atanmamis, en_eski_atanmamis_dk: y.sayac.en_eski_atanmamis_dk,
              btk48: y.sayac.btk48, en_yasli_btk_s: 51, kontrol: y.sayac.kontrol },
    uyum24: { oran: 0.62, n: 180, yaklasik: true, egim: Array.from({ length: 7 }, (_, j) => ({ gun: zamanMetni(eklenmis(an, -(6 - j) * 1440)).slice(0, 10), oran: 0.5 + j * 0.02 })) },
    btk: { tv6: 0.4, baglanti12: 0.55, teshis45: 0.3 },
    birikim: { asan24: y.sayac.asan24, egim_gun: -4, seri: Array.from({ length: 7 }, (_, j) => ({ zaman: zamanMetni(eklenmis(an, -(6 - j) * 1440)), acik: 450 - j * 3, asan24: 300 - j * 4 })) },
    kapasite: { talep: 62, aktif: 4, kapasite: 55, mod: 'asiri_yuk', esnek_oneri: 1, elle: false, mesaj: null },
    hiz_hatti: [
      { adim: 'boss_sistem', medyan_dk: 34, p90_dk: 80, n: 120, hedef_dk: 30, hedefte_oran: 0.45 },
      { adim: 'atama', medyan_dk: 9, p90_dk: 22, n: 64, hedef_dk: 15, hedefte_oran: 0.78 },
      { adim: 'teknik_gordu', medyan_dk: 4, p90_dk: 12, n: 40, hedef_dk: 5, hedefte_oran: 0.6 },
      { adim: 'boss_islendi', medyan_dk: 11, p90_dk: 35, n: 30, hedef_dk: 15, hedefte_oran: 0.66 },
      { adim: 'yol', medyan_dk: 38, p90_dk: 70, n: 25, hedef_dk: 60, hedefte_oran: 0.82 },
      { adim: 'saha', medyan_dk: 55, p90_dk: 130, n: 22, hedef_dk: 120, hedefte_oran: 0.86 },
      { adim: 'uctan_uca', medyan_dk: 1260, p90_dk: 2900, n: 90, hedef_dk: 1440, hedefte_oran: 0.58 },
    ],
    hijyen: { cozuldu_boss_acik: 1, askida_uyanmasiz: y.sayac.askida_uyanmasiz, boss_islenecek: y.sayac.boss_bekleyen, rapor_yas_dk: 12,
              askida_btk_durdu: y.sayac.askida_btk_durdu,
              btk_alarm: y.isler.filter((s) => s.btk_sikayet?.alarm && !s.btk_sikayet.tcs).length,
              genel_ariza: y.isler.filter((s) => s.genel_ariza).length,
              oncelikli: y.isler.filter((s) => s.oncelik).length },
    obekler: sahteObekler().obekler.map((o) => ({ id: o.id, ad: o.ad, acik: o.acik, geciken: o.geciken, btk: o.btk, atanmamis: o.atanmamis, sahip: o.sahip })),
    teknikler: sahteTeknikler().map((t) => ({ id: t.id, ad: t.ad, atanan: t.bugun.atanan, biten: t.bugun.biten, evde_yok: t.id === 102 ? 1 : 0,
                                              yolda_sahada: t.id === 101 ? 1 : 0, ilk_is: t.bugun_yok ? null : zamanMetni(eklenmis(an, -200)) })),
    sistem: { son_rapor: zamanMetni(eklenmis(an, -12)), son_yedek: zamanMetni(eklenmis(an, -900)), son_goc: '2026-09-30 19:40:12',
              saklama_metni: 'Müşteri bilgisi kapanıştan 30 gün sonra silinir; ham rapor 7 gün, yedekler 30 gün tutulur.' },
  };
}

export function sahteTakipSatis(): TakipSatisYanit {
  return {
    demo_dahil: true,
    bugun: { ziyaret: 41, temas: 22, satis: 3, aktif_satisci: 2, toplam_satisci: 2 },
    hafta: { ziyaret: 198, temas: 104, satis: 14, hedef: null, ilerleme: null },
    huni: { ziyaret: 198, temas: 104, satis: 14 },
    satiscilar: [
      { id: 201, ad: 'Oğuz Tekin', bolge: 3, bugun_ziyaret: 23, bugun_satis: 2, hafta_ziyaret: 110, hafta_satis: 9, donusum: 0.082 },
      { id: 202, ad: 'Gül Sarı', bolge: 5, bugun_ziyaret: 18, bugun_satis: 1, hafta_ziyaret: 88, hafta_satis: 5, donusum: 0.057 },
    ],
    altyapisi_cozulen_bina: 2,
  };
}

// ----------------------------------------------------------------------------- bellekte sahte sunucu
export class SahteHata extends Error {
  constructor(public durum: number, public govde: HataYaniti) { super(govde.hata); }
}
function hata(durum: number, kod: string, metin: string, ek: Partial<HataYaniti> = {}): never {
  throw new SahteHata(durum, { hata: metin, kod, ...ek });
}
function isAl(isNo: string): SahteIs {
  const is = ISLER.find((i) => i.is_no === isNo);
  if (!is) hata(404, 'is_yok', 'Bu iş bulunamadı ya da size ait değil.');
  return is;
}
function surumDenetle(is: SahteIs, surum: unknown): void {
  if (typeof surum === 'number' && surum !== is.surum) {
    const son = is.olaylar[0];
    hata(409, 'guncel_degil', `Bu iş siz bakarken değişti: ${son?.zaman.slice(11, 16) ?? ''}'de ${son?.kisi ?? 'sistem'} ${son?.ozet ?? 'değiştirdi'}.`,
         { guncel: ayrinti(is), degistiren: son?.kisi ?? null, zaman: son?.zaman ?? null });
  }
}
function olayYaz(is: SahteIs, tur: string, ozet: string, notu: string | null = null): void {
  is.olaylar.unshift({ id: ++IMLEC, zaman: zamanMetni(simdi()), kisi: 'Sahte Kullanıcı', tur, ozet, notu });
  is.surum += 1;
}
function randevuOku(r: unknown): SahteIs['randevu'] {
  if (!r || typeof r !== 'object') return null;
  const x = r as { bas?: string | null; bit?: string | null; teyitli?: boolean };
  if (!x.bas || !x.bit) return null;
  const bas = zamanOku(x.bas), bit = zamanOku(x.bit);
  if (bit <= bas) hata(422, 'randevu_gecersiz', 'Bitiş başlangıçtan sonra olmalı.');
  if (bit.getTime() - bas.getTime() > 4 * 60 * DK) hata(422, 'randevu_gecersiz', 'En çok 4 saatlik aralık.');
  return { bas, bit, teyitli: !!x.teyitli, kaynak: 'biz' };
}

const TOPLU: Record<string, Array<{ is_no: string; once: Partial<SahteIs> }>> = {};

/**
 * Sözleşmedeki uçları bellekte canlandırır. Hata durumunda `SahteHata` atar
 * (durum kodu + sunucunun hata gövdesi). Tanınmayan yol için 404.
 */
export async function sahteIstek<T = unknown>(yontem: string, yol: string, govde?: unknown): Promise<T> {
  await new Promise((r) => setTimeout(r, 120 + Math.floor(Math.random() * 120)));
  const [yalin, sorgu = ''] = yol.split('?');
  const q = new URLSearchParams(sorgu);
  const g = (govde ?? {}) as Record<string, unknown>;
  const y = yontem.toUpperCase();
  const m = (desen: RegExp) => yalin.match(desen);
  let e: RegExpMatchArray | null;

  if (y === 'GET' && yalin === '/api/isler') return sahteIslerYanit((q.get('kova') as 'acik' | 'biten') || 'acik') as T;
  if (y === 'GET' && yalin === '/api/isler/degisim') return sahteDegisim(Number(q.get('imlec') || 0)) as T;
  if (y === 'GET' && yalin === '/api/isler/teknikler') return sahteTeknikler() as T;
  if (y === 'GET' && yalin === '/api/isler/boss-ekip') return sahteBossEkip() as T;
  if (y === 'GET' && yalin === '/api/isler/ayarlar') return sahteIsAyarlari() as T;
  if (y === 'GET' && yalin === '/api/isler/kurallar') return sahteKurallar() as T;
  if (y === 'GET' && yalin === '/api/kesinti') return sahteKesintiler() as T;
  if (y === 'GET' && yalin === '/api/kesinti/aday') return sahteKesintiAday() as T;
  if (y === 'POST' && yalin === '/api/kesinti') {
    const k: Kesinti = { ...KESINTILER[0], id: KESINTILER.length + 1, no: null, baslama: zamanMetni(simdi()), ozet: String(g.metin ?? '').slice(0, 300), askida_is: 0 };
    KESINTILER.unshift(k);
    const yanit: KesintiEkleYanit = { kesinti: k, askiya_alinan: [], atlanan: [] };
    return yanit as T;
  }
  if (y === 'GET' && yalin === '/api/boss/giden') return sahteBossGiden() as T;
  if (y === 'GET' && yalin === '/api/aranacaklar') return sahteAranacaklar() as T;
  if (y === 'GET' && yalin === '/api/islerim') return sahteIslerim() as T;
  if (y === 'GET' && yalin === '/api/obekler') return sahteObekler() as T;
  if (y === 'GET' && yalin === '/api/mahalleler') return sahteMahalleler(q.get('q') || '') as T;
  if (y === 'GET' && yalin === '/api/ilceler') return sahteIlceler() as T;
  if (y === 'GET' && yalin === '/api/aktarim') return sahteAktarimGecmisi() as T;
  if (y === 'GET' && yalin === '/api/aktarim/izleme') return sahteIzleme() as T;
  if (y === 'GET' && yalin === '/api/takip') return sahteTakip() as T;
  if (y === 'GET' && yalin === '/api/takip/satis') return sahteTakipSatis() as T;
  if (y === 'POST' && yalin === '/api/aktarim') return sahteAktarimSonucu() as T;
  if (y === 'POST' && yalin === '/api/islerim/gordu') return undefined as T;

  if (y === 'POST' && yalin === '/api/isler/oneri-onayla') {
    const toplu_id = `t${Date.now().toString(36)}`;
    const sonuc: TopluSonuc = { toplu_id, atanan: [], atlanan: [] };
    TOPLU[toplu_id] = [];
    for (const [isNo, surum] of Object.entries((g.isler ?? {}) as Record<string, number>)) {
      const is = ISLER.find((i) => i.is_no === isNo);
      if (!is) { sonuc.atlanan.push({ is_no: isNo, kod: 'is_yok', hata: 'Bu iş bulunamadı.' }); continue; }
      if (is.surum !== surum) { sonuc.atlanan.push({ is_no: isNo, kod: 'guncel_degil', hata: 'Bu iş siz bakarken değişti.' }); continue; }
      if (!is.oneri_id || is.binada_acik_ticket) { sonuc.atlanan.push({ is_no: isNo, kod: 'oneri_yok', hata: 'Önerisi yok.' }); continue; }
      TOPLU[toplu_id].push({ is_no: isNo, once: { durum: is.durum, atanan_id: is.atanan_id, randevu: is.randevu } });
      is.atanan_id = is.oneri_id; is.durum = 'atandi'; is.durum_zamani = simdi();
      olayYaz(is, 'atama', 'Öneriyi onayladı');
      sonuc.atanan.push(isNo);
    }
    return sonuc as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/toplu\/([^/]+)\/geri-al$/))) {
    const kayit = TOPLU[e[1]] ?? [];
    const s: TopluGeriAlSonuc = { geri_alinan: [], atlanan: [] };
    for (const k of kayit) {
      const is = ISLER.find((i) => i.is_no === k.is_no);
      if (!is) continue;
      Object.assign(is, k.once);
      olayYaz(is, 'geri_al', 'Toplu atamayı geri aldı');
      s.geri_alinan.push(k.is_no);
    }
    delete TOPLU[e[1]];
    return s as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/dagit\/onizle$/))) {
    const ids = (g.teknik_idler as number[]) ?? [];
    const onz: DagitOnizleme = { gruplar: ids.map((id, j) => ({ teknik_id: id, is_nolar: ISLER.filter((_, k) => k % ids.length === j).slice(0, 4).map((i) => i.is_no), btk: j + 1, km: 6.5 + j })) };
    return onz as T;
  }
  if (y === 'GET' && (e = m(/^\/api\/isler\/([^/]+)$/))) return ayrinti(isAl(decodeURIComponent(e[1]))) as T;
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/ata$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    surumDenetle(is, g.surum);
    const t = SAHTE_TEKNIKLER.find((x) => x.id === g.teknik_id);
    if (!t) hata(422, 'teknik_gecersiz', 'Seçilen kişi aktif bir teknik görevli değil.');
    if (is.binada_acik_ticket && !is.ticket && !g.yine_de) hata(409, 'altyapi_engeli', 'Bu binada açık SİNYAL ticket\'ı var (#12, 3 gündür). Teknisyen gönderilmez.');
    if (is.durum === 'ulasilamadi' && !(g.randevu as { teyitli?: boolean } | undefined)?.teyitli)
      hata(422, 'teyit_gerekli', 'Müşteriye ulaşılmadan aynı işe ikinci kez teknisyen gönderilmez. "Saat teyitli" işaretleyin.');
    if (!ACIK(is.durum)) hata(409, 'gecersiz_gecis', `Bu iş '${DURUM_ETIKET[is.durum]}' durumunda; 'Atandı' yapılamaz.`);
    is.atanan_id = t.id; is.durum = 'atandi'; is.durum_zamani = simdi();
    is.randevu = randevuOku(g.randevu) ?? is.randevu;
    is.boss_bekleyen = 'ekip'; is.boss_islendi = null;
    olayYaz(is, 'atama', `${kisaAd(t.ad)}'ya atadı`);
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/randevu$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    surumDenetle(is, g.surum);
    is.randevu = randevuOku(g);
    if (is.randevu && (is.durum === 'bekliyor' || is.durum === 'triyaj')) is.durum = 'randevulu';
    olayYaz(is, 'randevu', is.randevu ? 'Randevu verdi' : 'Randevuyu kaldırdı');
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/durum$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    surumDenetle(is, g.surum);
    const yeni = g.yeni as Durum;
    if (yeni === 'cozuldu' && ['atandi', 'yolda', 'sahada'].includes(is.durum) && typeof g.evde_miydi !== 'boolean')
      hata(422, 'alan_eksik', 'Müşteri evde miydi?');
    if (is.durum === 'askida' && yeni !== 'askida') {
      const acik = is.aski.find((a) => !a.bitis);
      if (acik) acik.bitis = zamanMetni(simdi());
    }
    if (yeni === 'askida') {
      const neden = String(g.neden ?? 'Abone kaynaklı');
      is.aski.push({ id: ++IMLEC, baslama: zamanMetni(simdi()), bitis: null, neden, kaynak: 'elle',
                     durdurur: /abone/i.test(neden), yaklasik: false, sure_dk: 0 });
      is.askida_neden = neden; is.uyanma = g.uyanma ? zamanOku(String(g.uyanma)) : null;
    }
    is.durum = yeni; is.durum_zamani = simdi();
    olayYaz(is, 'durum', DURUM_ETIKET[yeni], (g.notu as string) ?? null);
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/obek$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    surumDenetle(is, g.surum);
    is.obek_elle_id = (g.obek_id as number | null) ?? null;
    if (is.durum === 'triyaj' && is.obek_elle_id) { is.durum = 'bekliyor'; is.triyaj_nedeni = null; }
    olayYaz(is, 'obek', is.obek_elle_id ? 'Öbeğe elle atadı' : 'Elle öbeği kaldırdı');
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/arama$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    const saat = simdi().getHours();
    if (saat >= 22 || saat < 10) hata(422, 'arama_saati', saat >= 22 ? "22:00'den sonra müşteri aranmaz." : "Müşteri 10:00'dan önce aranmaz.");
    const sonuc = String(g.sonuc) as AramaSonucu;
    if (sonuc === 'yanlis_no' && !g.notu) hata(422, 'alan_eksik', 'Hatalı iletişim bilgisini yazın (ATA havuzu açıklaması).');
    is.aramalar.push({ zaman: zamanMetni(simdi()), sonuc, sure_sn: (g.sure_sn as number) ?? null, webphone: g.webphone !== false,
                       sms: !!g.sms, yeni_numara: !!g.yeni_numara, kisi: 'Sahte Kullanıcı' });
    if (['ulasilamadi', 'mesgul_kapali', 'dit'].includes(sonuc) && !g.sms) { is.boss_bekleyen = 'sms'; is.boss_islendi = null; }
    is.olaylar.unshift({ id: ++IMLEC, zaman: zamanMetni(simdi()), kisi: 'Sahte Kullanıcı', tur: 'arama', ozet: 'Müşteri arandı', notu: (g.notu as string) ?? null });
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/btk-sikayet$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    surumDenetle(is, g.surum);
    is.btk_sikayet = g.kaldir ? null : { tarih: g.tarih ? zamanOku(String(g.tarih)) : simdi(), reopen: !!g.reopen, tcs: null };
    olayYaz(is, 'btk_sikayet', g.kaldir ? 'BTK şikâyet işareti kaldırıldı' : 'BTK şikâyeti işaretlendi');
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/tcs$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    surumDenetle(is, g.surum);
    if (!g.teyitli) hata(422, 'alan_eksik', 'TÇS bir kez girilir ve değişmez: çözüm beklenen ekipten teyitli, gerçekçi tarih mi?');
    if (!is.btk_sikayet) hata(409, 'btk_sikayet_yok', 'TÇS yalnız BTK şikâyeti işaretli işte girilir.');
    if (is.btk_sikayet.tcs) hata(409, 'tcs_var', 'TÇS zaten girilmiş; değiştirilemez.');
    is.btk_sikayet.tcs = zamanOku(String(g.tarih));
    olayYaz(is, 'tcs', 'TÇS girildi');
    return ayrinti(is) as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/isler\/([^/]+)\/not$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    is.olaylar.unshift({ id: ++IMLEC, zaman: zamanMetni(simdi()), kisi: 'Sahte Kullanıcı', tur: 'not', ozet: 'Not ekledi', notu: String(g.metin ?? '') });
    return { olay_id: IMLEC } as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/(?:isler|boss\/giden)\/([^/]+)\/(?:boss-islendi|islendi)$/))) {
    const is = isAl(decodeURIComponent(e[1]));
    is.boss_islendi = g.islendi === false ? null : simdi();
    olayYaz(is, 'boss_islendi', is.boss_islendi ? "BOSS'a işlendi" : "BOSS işaretini kaldırdı");
    return ayrinti(is) as T;
  }
  if (y === 'POST' && yalin === '/api/isler') {
    const no = `B-${zamanMetni(simdi()).slice(2, 10).replace(/-/g, '')}-${String(ISLER.filter((i) => i.kaynak === 'bayi').length + 1).padStart(3, '0')}`;
    const yer = YERLER[0];
    const is: SahteIs = { ...ISLER[0], is_no: no, boss_task_no: null, kaynak: 'bayi', kanal_grubu: 'dehanet',
                          task_adi: String(g.task_adi ?? 'Bağlantı Problemi'), durum: 'bekliyor', durum_zamani: simdi(), yer,
                          acilis: simdi(), gorulme: simdi(), atanan_id: null, randevu: null, surum: 1, aski: [], olaylar: [] };
    olayYaz(is, 'olustu', 'Bayi işi açtı');
    ISLER.unshift(is);
    const yanit: YeniIsYanit = { is_no: no, is: ayrinti(is) };
    return yanit as T;
  }
  if (y === 'POST' && (e = m(/^\/api\/obekler\/(\d+)\/mahalle\/cikar$/))) {
    const o = OBEK_TANIMLARI.find((x) => x.id === Number(e![1]));
    if (!o) hata(404, 'is_yok', 'Öbek bulunamadı.');
    const refler = new Set((g.refler as string[]) ?? []);
    o.mahalleler = o.mahalleler.filter(([a, b, c]) => !refler.has(`${a}/${b}/${c}`));
    OBEK_SURUMU += 1;
    return { surum: OBEK_SURUMU, etkilenen_is: 1, obekler: sahteObekler().obekler, geri_al_olay_id: ++IMLEC } as T;
  }
  hata(404, 'is_yok', `Sahte sunucuda bu uç yok: ${y} ${yalin}`);
}

/** Sözleşme testi ve operasyon/v2/ornek/*.json için uç → örnek yanıt eşlemesi. */
export function sahteOrnekler(): Record<string, unknown> {
  const ilk = ISLER.find((i) => i.durum === 'askida') ?? ISLER[0];
  return {
    'GET /api/isler': sahteIslerYanit(),
    'GET /api/isler/degisim': sahteDegisim(IMLEC - 3),
    'GET /api/isler/{is_no}': ayrinti(ilk),
    'GET /api/isler/teknikler': sahteTeknikler(),
    'GET /api/isler/boss-ekip': sahteBossEkip(),
    'GET /api/isler/ayarlar': sahteIsAyarlari(),
    'GET /api/boss/giden': sahteBossGiden(),
    'GET /api/aranacaklar': sahteAranacaklar(),
    'GET /api/islerim': sahteIslerim(),
    'GET /api/obekler': sahteObekler(),
    'GET /api/mahalleler': sahteMahalleler('gur'),
    'GET /api/ilceler': sahteIlceler(),
    'GET /api/aktarim': sahteAktarimGecmisi(),
    'GET /api/aktarim/izleme': sahteIzleme(),
    'POST /api/aktarim': sahteAktarimSonucu(),
    'POST /api/aktarim#onay_gerekli': sahteAktarimOnay(),
    'GET /api/takip': sahteTakip(),
    'GET /api/takip/satis': sahteTakipSatis(),
    'GET /api/isler/kurallar': sahteKurallar(),
    'GET /api/kesinti': sahteKesintiler(),
    'GET /api/kesinti/aday': sahteKesintiAday(),
  };
}
