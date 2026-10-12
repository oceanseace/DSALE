/**
 * Arayüzün saf fonksiyonları için regresyon testleri (çalışanı bozmadan geliştir): MAP durum → renk eşlemesi
 * (5 renk, Administrator değiştirebilir), sütun süzgecinin "Yalnız seçilenleri göster / Seçilenleri gizle" mantığı
 * (MAP "İş türü" ile aynı), hücre düzeyi dolgu rengi, Sütunlar menüsünde sıra, askı hızlı bitiş seçimleri.
 * Çalıştırma: `node scripts/saf_test.mjs` (esbuild ile paketlenir; `npm run build` önce bunu koşar).
 */
import assert from 'node:assert/strict';
import type { IsSatir } from '../src/cekirdek/is/tipler';
import { DURUM_RENK_VARSAYILAN, durumRenkleriniKur, durumRenkleriOku, renkEtiketi } from '../src/cekirdek/is/durumRenk';
import { katOf, durumKati, durumAnahtari, randevuVar, KATLAR, yerelKatYaz, yerelTemizle } from '../src/birimler/operasyon/isler/map/noktalar';
import { birlestir, EYLEMDE } from '../src/birimler/operasyon/isler/durum';
import { ilkSekme, islemSekmeleri, uygulamaEylemleri } from '../src/birimler/operasyon/isler/IsCekmecesi';
import type { IsAyrinti } from '../src/cekirdek/is/tipler';
import {
  cipMetni,
  degerAra,
  degerUyar,
  gorunenleriBirak,
  gorunenleriSec,
  govdeBaslangic,
  suzgecEtkin,
  suzgecKur,
} from '../src/birimler/operasyon/isler/tabloSuzgec';
import { hucreBoya, hucreRengi, satirRenkleri } from '../src/birimler/operasyon/isler/sutunlar';
import { COKLU_AYRAC, uyariMetni, uyariSuzgec } from '../src/birimler/operasyon/isler/sutunlar';
import { cokluAc, cokluUyar } from '../src/birimler/operasyon/isler/tabloSuzgec';
import { alanHucreleri } from '../src/birimler/operasyon/isler/secim';
import { yeniSira } from '../src/birimler/operasyon/isler/sutunDuzeni';
import { askiHizliSecimler } from '../src/birimler/operasyon/isler/TopluAski';
import { ekleriAyikla, haricDegistir, topluIsaret } from '../src/birimler/operasyon/isler/IliskiliSecim';
import { hizalaSecimi } from '../src/birimler/operasyon/isler/IliskiliHizala';
import { VARSAYILAN_CIFT } from '../src/birimler/operasyon/isler/TopluAski';
import { hataRaporu } from '../src/birimler/operasyon/isler/BossYazmaKuyrugu';
import { panoSuzgeci } from '../src/birimler/operasyon/isler/panoSuzgeci';
import { TASKS_SUZ, tasksAdresiOku, tasksSuzYolu } from '../src/cekirdek/yol/tasks';
import type { IliskiliIs } from '../src/cekirdek/is/tipler';
import { degerGoster, degerListesi } from '../src/birimler/operasyon/isler/tabloSuzgec';
import { turDegerleri, turEtiketi, turUyar } from '../src/birimler/operasyon/isler/isTuru';
import { suzgecOku } from '../src/birimler/operasyon/isler/tercihDeposu';

let gecen = 0;
function test(ad: string, f: () => void) {
  try {
    f();
    gecen += 1;
  } catch (e) {
    console.error(`✗ ${ad}`);
    throw e;
  }
}

/* Gerçekçi BOSS satırları (canlı 08.10 dağılımı: "Açık" 1.856 işin 817'sinde BOSS randevusu var). */
const satir = (ek: Partial<IsSatir> & { boss_randevu_durumu?: string | null }): IsSatir =>
  ({ is_no: String(Math.random()), durum: 'bekliyor', randevu: null, boss_durum: null, ...ek }) as unknown as IsSatir;
const BOSS_RV = { bas: '2026-10-09 10:00:00', bit: '2026-10-09 12:00:00', teyitli: false, kaynak: 'boss' as const };

/* ------------------------------ MAP durum renkleri (kullanıcının tarifi 08.10) ------------------------------ */
test('Lejant 5 renk: gri · sarı · mavi · kırmızı · mor', () => {
  assert.deepEqual(KATLAR.map((k) => k.kat), ['gri', 'sari', 'mavi', 'kirmizi', 'mor']);
});
test('BOSS "Açık" + randevu → sarı', () => {
  assert.equal(katOf(satir({ boss_durum: 'Açık', randevu: BOSS_RV, boss_randevu_durumu: 'Randevulu' })), 'sari');
  assert.equal(katOf(satir({ boss_durum: 'Açık', boss_randevu_durumu: 'Randevulu' })), 'sari');
  assert.equal(katOf(satir({ boss_durum: 'Açık', durum: 'randevulu' })), 'sari');
});
test('BOSS "Açık" randevusuz → gri', () => {
  assert.equal(katOf(satir({ boss_durum: 'Açık', boss_randevu_durumu: 'Randevusuz' })), 'gri');
  assert.equal(katOf(satir({ boss_durum: 'Randevusuz' })), 'gri');
});
test('BOSS "Randevu alındı" → sarı', () => assert.equal(katOf(satir({ boss_durum: 'Randevu alındı' })), 'sari'));
test('Başlandı / Konum paylaşıldı → mavi (randevu olsa da)', () => {
  assert.equal(katOf(satir({ boss_durum: 'Başlandı', randevu: BOSS_RV })), 'mavi');
  assert.equal(katOf(satir({ boss_durum: 'Konum paylaşıldı', randevu: BOSS_RV })), 'mavi');
});
test('Mor YALNIZ Askıya alındı; Ertelendi / Merkeze gönderildi → kırmızı', () => {
  assert.equal(katOf(satir({ boss_durum: 'Askıya alındı', randevu: BOSS_RV })), 'mor');
  assert.equal(katOf(satir({ boss_durum: 'Ertelendi' })), 'kirmizi');
  assert.equal(katOf(satir({ boss_durum: 'Merkeze gönderildi', randevu: BOSS_RV })), 'kirmizi');
});
test('BOSS statüsü yok/tanınmıyor → uygulamanın durumu', () => {
  assert.equal(katOf(satir({ durum: 'yolda' })), 'mavi');
  assert.equal(katOf(satir({ durum: 'askida' })), 'mor');
  assert.equal(katOf(satir({ durum: 'merkeze' })), 'kirmizi');
  assert.equal(katOf(satir({ durum: 'atandi', randevu: { ...BOSS_RV, kaynak: 'biz' } })), 'sari');
  assert.equal(katOf(satir({ boss_durum: 'Bilinmeyen', durum: 'bekliyor' })), 'gri');
  assert.equal(durumKati({ durum: 'merkeze', randevu: null }), 'merkeze_gonderildi');
  assert.equal(durumAnahtari(satir({ boss_durum: 'Ertelendi' })), 'ertelendi');
  assert.equal(randevuVar({ durum: 'bekliyor', randevu: null, boss_randevu_durumu: 'RANDEVULU' }), true);
});
test('Administrator eşlemeyi değiştirir → renk hemen değişir; bozuk değer varsayılana düşer', () => {
  durumRenkleriniKur({ ertelendi: 'mor', acik: 'pembe', uydurma: 'mor' });
  assert.equal(katOf(satir({ boss_durum: 'Ertelendi' })), 'mor');
  assert.equal(katOf(satir({ boss_durum: 'Açık' })), 'gri', 'tanınmayan renk yok sayılır');
  assert.equal(renkEtiketi('mor'), 'Askıda · Ertelendi');
  durumRenkleriniKur(null);
  assert.equal(katOf(satir({ boss_durum: 'Ertelendi' })), 'kirmizi');
  assert.deepEqual(durumRenkleriOku(undefined), DURUM_RENK_VARSAYILAN);
  assert.equal(renkEtiketi('kirmizi'), 'Ertelendi · Merkeze');
  assert.equal(renkEtiketi('sari'), 'Randevulu');
});

/* ------------------------------ sütun süzgeci (MAP "İş türü" ile aynı) ------------------------------ */
const GOREVLER: Array<[string, number]> = [
  ['Fiber Kurulum', 5],
  ['TV Kurulum', 3],
  ['KURULUM (Dönüşüm)', 1],
  ['Bağlantı Problemi', 7],
  ['Hız Problemi', 2],
];
test('Varsayılan: hiçbir şey seçili değil → hiçbir şey gizlenmez', () => {
  const b = govdeBaslangic(undefined);
  assert.equal(b.kip, 'dahil');
  assert.equal(b.secim.size, 0);
  const f = suzgecKur(b.kip, [...b.secim], '');
  assert.equal(suzgecEtkin(f), false);
  assert.equal(degerUyar(f, 'Fiber Kurulum'), true);
  assert.equal(degerUyar({ degerler: [], kip: 'haric' }, 'x'), true);
  assert.equal(degerUyar({ degerler: [] }, 'x'), true);
});
test('"Yalnız seçilenleri göster": yalnız işaretliler', () => {
  const f = suzgecKur('dahil', ['Bağlantı Problemi'], '');
  assert.deepEqual(f, { degerler: ['Bağlantı Problemi'], metin: '' });
  assert.equal(degerUyar(f, 'Bağlantı Problemi'), true);
  assert.equal(degerUyar(f, 'TV Kurulum'), false);
  assert.equal(cipMetni('Task adı', f), 'Task adı: Bağlantı Problemi');
});
test('"Seçilenleri gizle": işaretliler gizli, geri kalan hepsi görünür', () => {
  const f = suzgecKur('haric', ['TV Kurulum', 'Fiber Kurulum'], '');
  assert.deepEqual(f, { degerler: ['TV Kurulum', 'Fiber Kurulum'], metin: '', kip: 'haric' });
  assert.equal(degerUyar(f, 'TV Kurulum'), false);
  assert.equal(degerUyar(f, 'Bağlantı Problemi'), true);
  assert.equal(degerUyar(f, ''), true);
});
test('Kip değişince işaretler DEĞİŞMEZ (pencere yeniden açılınca da aynı)', () => {
  const sec = new Set(['TV Kurulum', 'Fiber Kurulum']);
  const gizle = suzgecKur('haric', [...sec], '');
  const goster = suzgecKur('dahil', [...sec], '');
  assert.deepEqual(gizle.degerler, goster.degerler);
  const b = govdeBaslangic(gizle);
  assert.equal(b.kip, 'haric');
  assert.deepEqual([...b.secim], ['TV Kurulum', 'Fiber Kurulum']);
});
test('Arama + Görünenleri seç: "kurulum" → kurulumlar seçilir → Seçilenleri gizle → kurulumlar dışı', () => {
  const gorunen = degerAra(GOREVLER, 'kurulum').map(([v]) => v);
  assert.deepEqual(gorunen, ['Fiber Kurulum', 'TV Kurulum', 'KURULUM (Dönüşüm)']);
  const sec = gorunenleriSec(new Set(), gorunen);
  const f = suzgecKur('haric', [...sec], '');
  const kalan = GOREVLER.map(([v]) => v).filter((v) => degerUyar(f, v));
  assert.deepEqual(kalan, ['Bağlantı Problemi', 'Hız Problemi']);
  assert.equal(cipMetni('Task adı', f), 'Task adı: gizli 3 değer');
  // önceki seçim korunur; "(Tümünü seç)" kaldırınca yalnız görünenler çıkar
  const iki = gorunenleriSec(new Set(['Hız Problemi']), gorunen);
  assert.equal(iki.size, 4);
  assert.deepEqual([...gorunenleriBirak(iki, gorunen)], ['Hız Problemi']);
});
test('Değer araması içerir + Türkçe harf duyarsız ("ku" → Kurt, KUBİLAY, Okutan; "ış" → Işık)', () => {
  const adlar: Array<[string, number]> = [['Oğuz Kurt', 1], ['KUBİLAY ÇELİK', 1], ['Ayşe Okutan', 1], ['Elif Işık', 1], ['Mehmet Sarı', 1], ['', 2]];
  assert.deepEqual(degerAra(adlar, 'ku').map(([v]) => v), ['Oğuz Kurt', 'KUBİLAY ÇELİK', 'Ayşe Okutan']);
  assert.deepEqual(degerAra(adlar, 'KU').map(([v]) => v), ['Oğuz Kurt', 'KUBİLAY ÇELİK', 'Ayşe Okutan']);
  assert.deepEqual(degerAra(adlar, 'isik').map(([v]) => v), ['Elif Işık']);
  assert.deepEqual(degerAra(adlar, 'boş').map(([v]) => v), ['']);
  assert.equal(degerAra(adlar, '  ').length, adlar.length);
});
test('Çip: 15 değer / gizli 15 değer', () => {
  const on5 = Array.from({ length: 15 }, (_, i) => `T${i}`);
  assert.equal(cipMetni('Task adı', suzgecKur('dahil', on5, '')), 'Task adı: 15 değer');
  assert.equal(cipMetni('Task adı', suzgecKur('haric', on5, '')), 'Task adı: gizli 15 değer');
});

/* ------------------------------ hücre düzeyi dolgu rengi ------------------------------ */
test('Dolgu yalnız boyanan hücrede; eski satır rengi bütün hücrelerde', () => {
  const yeni = { isaret: null, hucre_renk: { ad: 'sari' as const } };
  assert.equal(hucreRengi(yeni, 'ad'), 'sari');
  assert.equal(hucreRengi(yeni, 'tel'), null);
  const eski = { isaret: 'mavi' as const, hucre_renk: undefined };
  assert.equal(hucreRengi(eski, 'ad'), 'mavi');
  assert.equal(hucreRengi(eski, 'ek:city'), 'mavi');
});
test('Boya / dolgu yok: satır rengi varken "yok", satır rengiyle aynı renk kayıt tutmaz', () => {
  const s = { isaret: 'mavi' as const, hucre_renk: {} };
  const y = hucreBoya(s, ['ad', 'tel'], null);
  assert.deepEqual(y, { ad: 'yok', tel: 'yok' });
  assert.equal(hucreRengi({ ...s, hucre_renk: y }, 'ad'), null);
  assert.equal(hucreRengi({ ...s, hucre_renk: y }, 'ilce'), 'mavi');
  assert.deepEqual(hucreBoya({ ...s, hucre_renk: y }, ['ad'], 'mavi'), { tel: 'yok' });
  assert.deepEqual(hucreBoya({ isaret: null, hucre_renk: { ad: 'sari' } }, ['ad'], null), {});
  assert.deepEqual(hucreBoya({ isaret: null }, ['ad', 'tel'], 'kirmizi'), { ad: 'kirmizi', tel: 'kirmizi' });
  assert.equal(satirRenkleri({ isaret: 'mavi', hucre_renk: { ad: 'sari', tel: 'yok' } }), 'Mavi, Sarı');
});
test('Seçili dikdörtgenin hücreleri (B2:C3)', () => {
  const satirlar = [{ is_no: '1' }, { is_no: '2' }, { is_no: '3' }];
  const sutunlar = [{ id: 'task' }, { id: 'ad' }, { id: 'tel' }];
  assert.deepEqual(alanHucreleri(satirlar, sutunlar, { r1: 1, r2: 2, c1: 1, c2: 2 }), [
    { is_no: '2', sutun: 'ad' },
    { is_no: '2', sutun: 'tel' },
    { is_no: '3', sutun: 'ad' },
    { is_no: '3', sutun: 'tel' },
  ]);
});

/* ------------------------------ Sütunlar menüsünde sıra ------------------------------ */
test('Sıra: yukarı / aşağı / sürükle-bırak', () => {
  const l = ['a', 'b', 'c', 'd'];
  assert.deepEqual(yeniSira(l, 'c', 1), ['a', 'c', 'b', 'd']); // c ↑
  assert.deepEqual(yeniSira(l, 'b', 3), ['a', 'c', 'b', 'd']); // b ↓ (c'nin arkasına)
  assert.deepEqual(yeniSira(l, 'a', 4), ['b', 'c', 'd', 'a']); // en sona
  assert.deepEqual(yeniSira(l, 'd', 0), ['d', 'a', 'b', 'c']); // en başa
  assert.deepEqual(yeniSira(l, 'b', 1), l); // yerinde
  assert.deepEqual(yeniSira(l, 'x', 0), l);
});

test('Askı hızlı seçimleri: 1 hafta sonra en çok 7 gün, hepsi ileride', () => {
  const simdi = new Date(2026, 9, 8, 14, 37, 12);
  const s = askiHizliSecimler(simdi);
  assert.deepEqual(s.map((x) => x.etiket), ['2 saat sonra', 'Yarın 10:00', '2 gün sonra', '3 gün sonra', '1 hafta sonra']);
  for (const x of s) {
    assert.ok(x.an > simdi);
    assert.ok(x.an.getTime() <= simdi.getTime() + 7 * 86400_000);
  }
});

/* ------------------------------ İş türü = sütun süzgeci (tek bileşen, tek semantik; 08.10) ------------------------------ */
const KURULUMLAR = ['Fiber Kurulum', 'TV+ Kurulum', 'Superbox Kurulum', 'KURULUM (Dönüşüm)'];
const ACIK_ADLAR = [...KURULUMLAR, 'Fiber Kurulum', 'Bağlantı Problemi', 'Bağlantı Problemi', 'TV+ Arıza', 'Hız Problemi'];
test('Değer listesi diğer süzgeçlerden BAĞIMSIZ: "kuru" → bütün kurulumlar (başka süzgeç kurulumları gizlese de)', () => {
  // başka bir süzgeç (ör. İş türü "yalnız Bağlantı Problemi") yalnız arızaları bırakmış
  const gorunur = ACIK_ADLAR.filter((v) => !/kurulum/i.test(v));
  const l = degerListesi(ACIK_ADLAR, gorunur, null);
  const kuru = degerAra(l, 'kuru');
  assert.deepEqual(kuru.map(([v]) => v).sort(), [...KURULUMLAR].sort());
  assert.ok(kuru.every(([, , g]) => g === 0), 'diğer süzgeç yüzünden görünmeyenler soluk (0)');
  assert.equal(l.find(([v]) => v === 'Fiber Kurulum')?.[1], 2, 'sayı bütün açık işlerden');
  assert.equal(l.find(([v]) => v === 'Bağlantı Problemi')?.[2], 2);
  // seçili ama hiçbir işte kalmayan değer kaybolmaz
  assert.deepEqual(degerListesi(['a'], ['a'], ['eski']).map(([v, t, g]) => [v, t, g]), [['a', 1, 1], ['eski', 0, 0]]);
  // boşlar en sonda
  assert.equal(degerListesi(['', 'b', 'a'], [], null).map(([v]) => v).join(','), 'a,b,');
});
/* Değer listesinde diğer süzgeçlerle gizlenen değerler (09.10): varsayılan GİZLİ, Ayarlar'daki anahtarla soluk. */
const ARIZA_GORUNUR = ACIK_ADLAR.filter((v) => !/kurulum/i.test(v));
const ARIZA_LISTESI = degerListesi(ACIK_ADLAR, ARIZA_GORUNUR, null);
const SECIM_YOK = new Set<string>();
const adlar = (l: [string, ...number[]][]) => l.map(([v]) => v).sort();
test('Değer listesi: anahtar KAPALI (varsayılan) → diğer süzgeçlerle gizlenen değerler listede yok', () => {
  const l = degerGoster(ARIZA_LISTESI, '', SECIM_YOK, false);
  assert.deepEqual(adlar(l), ['Bağlantı Problemi', 'Hız Problemi', 'TV+ Arıza']);
  assert.ok(l.every(([, , g]) => g > 0));
  assert.equal(degerGoster(ARIZA_LISTESI, '   ', SECIM_YOK, false).length, 3, 'boşluk arama sayılmaz');
});
test('Değer listesi: anahtar AÇIK → hepsi listede, gizlenenler soluk (görünür = 0)', () => {
  const l = degerGoster(ARIZA_LISTESI, '', SECIM_YOK, true);
  assert.equal(l.length, ARIZA_LISTESI.length);
  assert.deepEqual(adlar(l.filter(([, , g]) => g === 0)), [...KURULUMLAR].sort());
});
test('Değer listesi: arama anahtar kapalıyken de BÜTÜN değerlerde arar ("kuru" → kurulumlar soluk, liste kurumaz)', () => {
  for (const soluk of [false, true]) {
    const kuru = degerGoster(ARIZA_LISTESI, 'kuru', SECIM_YOK, soluk);
    assert.deepEqual(adlar(kuru), [...KURULUMLAR].sort());
    assert.ok(kuru.every(([, , g]) => g === 0), 'gizlenen eşleşmeler soluk çizilir');
  }
  assert.deepEqual(adlar(degerGoster(ARIZA_LISTESI, 'tv', SECIM_YOK, false)), ['TV+ Arıza', 'TV+ Kurulum']);
});
test('Değer listesi: seçili (işaretli) değer anahtar kapalıyken de kaybolmaz', () => {
  const secili = new Set(['Fiber Kurulum']);
  const l = degerGoster(ARIZA_LISTESI, '', secili, false);
  assert.deepEqual(adlar(l), ['Bağlantı Problemi', 'Fiber Kurulum', 'Hız Problemi', 'TV+ Arıza']);
  assert.equal(l.find(([v]) => v === 'Fiber Kurulum')?.[2], 0, 'yine soluk çizilir');
  // seçili olup hiçbir işte kalmayan değer (degerListesi 0/0) de kalır
  const eski = degerListesi(['a'], ['a'], ['eski']);
  assert.deepEqual(adlar(degerGoster(eski, '', new Set(['eski']), false)), ['a', 'eski']);
  assert.deepEqual(adlar(degerGoster(eski, '', SECIM_YOK, false)), ['a']);
});
test('İş türü "Yalnız: 15 tür" TASKS ve MAP’te aynı: yalnız seçilenler görünür; "Seçilenleri gizle" tersi', () => {
  const on5 = [...KURULUMLAR, ...Array.from({ length: 11 }, (_, i) => `Kurulum ${i}`)];
  const yalniz = { kip: 'dahil' as const, degerler: on5 };
  assert.equal(turUyar({ task_adi: 'TV+ Kurulum' }, yalniz), true);
  assert.equal(turUyar({ task_adi: 'Bağlantı Problemi' }, yalniz), false);
  assert.equal(turUyar({ task_adi: 'TV+ Arıza' }, yalniz), false);
  const gizle = { kip: 'haric' as const, degerler: on5 };
  assert.equal(turUyar({ task_adi: 'TV+ Kurulum' }, gizle), false);
  assert.equal(turUyar({ task_adi: 'Bağlantı Problemi' }, gizle), true);
  assert.equal(turUyar({ task_adi: 'x' }, { kip: 'haric', degerler: [] }), true, 'seçim yoksa süzgeç yok');
  assert.equal(turEtiketi(yalniz), 'İş türü: yalnız 15 tür');
  assert.equal(turEtiketi(gizle), 'İş türü: gizli 15 tür');
  assert.equal(turEtiketi({ kip: 'dahil', degerler: ['TV+ Kurulum'] }), 'İş türü: yalnız TV+ Kurulum');
  assert.equal(turEtiketi({ kip: 'dahil', degerler: [] }), null);
  // sunucudan/öteki pencereden gelen durum kipini korur
  assert.deepEqual(suzgecOku({ tur: yalniz }).tur, yalniz);
  // İş türü değer listesi de aynı bileşenin biçiminde (çoktan aza)
  const td = turDegerleri(ACIK_ADLAR.map((task_adi) => ({ task_adi })), ['Eski tür']);
  assert.deepEqual(td.slice(0, 2).map(([v]) => v), ['Bağlantı Problemi', 'Fiber Kurulum']);
  assert.ok(td.some(([v, t]) => v === 'Eski tür' && t === 0));
});

/* ------------------------------ MAP deposu: BOSS'tan gelen değişiklik noktayı hemen boyar (08.10) ------------------------------ */
const sari = () => satir({ is_no: 'm1', boss_durum: 'Açık', boss_randevu_durumu: 'Randevulu', durum: 'atandi' });
test('Değişim yoklaması BOSS durumunu/randevuyu/ekibi satıra işler → renk hemen değişir', () => {
  const eski = [sari(), satir({ is_no: 'm2', boss_durum: 'Açık' })];
  assert.equal(katOf(eski[0]), 'sari');
  const gelen = { ...eski[0], boss_durum: 'Askıya alındı', durum: 'askida' } as IsSatir;
  const y = birlestir(eski, [gelen], []);
  assert.equal(y.length, 2);
  assert.equal(y[0].boss_durum, 'Askıya alındı');
  assert.equal(katOf(y[0]), 'mor');
  assert.equal(y[1], eski[1], 'değişmeyen satır aynı nesne');
  // BOSS'ta askıdan çıktı: randevulu açık → sarı
  const geri = birlestir(y, [{ ...y[0], boss_durum: 'Açık', durum: 'atandi' } as IsSatir], []);
  assert.equal(katOf(geri[0]), 'sari');
});
test('Eylem yanıtı BOSS alanı taşımıyorsa eskisi korunur (renk kaybolmaz); değişimde sunucu kesin', () => {
  const eski = [sari()];
  const ayrinti = { ...eski[0] } as Partial<IsSatir>;
  delete ayrinti.boss_durum;
  const y = birlestir(eski, [ayrinti as IsSatir], [], EYLEMDE);
  assert.equal(y[0].boss_durum, 'Açık');
  const d = birlestir(eski, [{ ...eski[0], boss_durum: null } as IsSatir], []);
  assert.equal(d[0].boss_durum, null);
});
test('İyimser renk: uygulamadan askı hemen mor; BOSS imzası değişince ya da ⟳ ile BOSS kazanır', () => {
  yerelTemizle();
  const s = sari();
  yerelKatYaz([s], 'askiya_alindi');
  assert.equal(katOf(s), 'mor', 'askı → hemen mor (BOSS beklemeden)');
  // BOSS henüz eski hâlde: mor kalır
  assert.equal(katOf({ ...s } as IsSatir), 'mor');
  // BOSS askıyı onayladı: BOSS'tan mor
  assert.equal(katOf({ ...s, boss_durum: 'Askıya alındı' } as IsSatir), 'mor');
  // BOSS'ta randevu durumu değişti (askı BOSS'a gitmedi, başka şey oldu): iyimser renk düşer
  yerelKatYaz([s], 'askiya_alindi');
  assert.equal(katOf({ ...s, boss_randevu_durumu: 'Randevusuz' } as IsSatir), 'gri');
  // ⟳ tam tazeleme: iyimser renk düşer
  yerelKatYaz([s], 'askiya_alindi');
  yerelTemizle();
  assert.equal(katOf(s), 'sari');
  // atama sonrası sarı iyimser renk; BOSS'ta askıya alınınca mor
  yerelKatYaz([satir({ is_no: 'm3', boss_durum: 'Açık' })], 'randevu_alindi');
  assert.equal(katOf(satir({ is_no: 'm3', boss_durum: 'Açık' })), 'sari');
  assert.equal(katOf(satir({ is_no: 'm3', boss_durum: 'Askıya alındı' })), 'mor');
  yerelTemizle();
});

/* ------------------------------ İş çekmecesi: İşlem sekmeleri ve "yalnız uygulamada" eylemler ------------------------------ */
const ayr = (ek: Partial<IsAyrinti>): IsAyrinti =>
  ({
    is_no: 'c1', durum: 'bekliyor', randevu: null, ticket: null, atanan: null,
    izinler: { ata: true, randevu: true, obek: true, ticket: true, durumlar: ['askida', 'ulasilamadi', 'merkeze', 'bekliyor'], ofisten_kapat: true, yeniden_ac: false, boss_bagla: false },
    ...ek,
  }) as unknown as IsAyrinti;
test('İşlem sekmeleri: açık iş Ata · Askıya al · Not; askıdaki iş Askı ile açılır; kapalı iş yalnız Not', () => {
  assert.deepEqual(islemSekmeleri(ayr({})), ['ata', 'aski', 'not']);
  assert.equal(ilkSekme(ayr({})), 'ata');
  assert.equal(ilkSekme(ayr({ durum: 'askida' })), 'aski');
  assert.deepEqual(islemSekmeleri(ayr({ durum: 'kapandi' })), ['not']);
  const izinsiz = ayr({});
  izinsiz.izinler = { ...izinsiz.izinler, ata: false, durumlar: [] };
  assert.deepEqual(islemSekmeleri(izinsiz), ['not']);
});
test('⋯ menüsü yalnız BOSS’a YAZMAYAN eylemleri içerir (Ata / Askı / Not orada yok)', () => {
  const adlar = uygulamaEylemleri(ayr({ durum: 'atandi' })).map((x) => x.ad);
  assert.ok(adlar.includes('Evde yok') && adlar.includes('Ofisten kapat') && adlar.includes('Atamayı kaldır'));
  assert.ok(!adlar.some((a) => /^(Ata|Askıya al|Not)$/.test(a)));
  assert.ok(uygulamaEylemleri(ayr({ durum: 'askida' })).some((x) => x.ozel === 'uyandir'));
});

test('İlişkili işler: seçimdekiler ve tekrarlar eklenmez; Pano suz/iliskili TASKS’ta ilişkili işi olanları süzer', () => {
  const x = (no: string) => ({ is_no: no, task_no: no, task_adi: 'Fiber Kurulum', kategori: 'yeni', durum: 'bekliyor',
    boss_durum: null, surum: 1, atanan_id: null, atanan: null }) as IliskiliIs;
  assert.deepEqual(ekleriAyikla(['1', '2'], [x('2'), x('3'), x('3'), x('4')]).map((y) => y.is_no), ['3', '4']);
  assert.deepEqual(ekleriAyikla([], []), []);
  assert.equal(tasksAdresiOku(`#${tasksSuzYolu(TASKS_SUZ.iliskili)}`.slice(1)).suz, 'iliskili');
  const s = panoSuzgeci('iliskili', []);
  assert.ok(s && s.uyar({ iliskili_isler: ['5'] } as unknown as IsSatir) && !s.uyar({ iliskili_isler: [] } as unknown as IsSatir));
});

test('İlişkili işler: her işin kendi kutusu (varsayılan işaretli); kaldırılan eklenmez, sayı yalnız işaretlileri sayar', () => {
  const x = (no: string) => ({ is_no: no, task_no: no, task_adi: 'Fiber Kurulum', kategori: 'yeni', durum: 'bekliyor',
    boss_durum: null, surum: 1, atanan_id: null, atanan: null }) as IliskiliIs;
  const liste = [x('3'), x('4'), x('5')];
  let haric: Set<string> = new Set();
  assert.equal(ekleriAyikla(['1'], liste, haric).length, 3, 'varsayılan: hepsi işaretli');
  assert.equal(topluIsaret(['3', '4', '5'], haric), 'hepsi');
  haric = haricDegistir(haric, '4', false);                     // "onu atamayalım"
  assert.deepEqual(ekleriAyikla(['1'], liste, haric).map((y) => y.is_no), ['3', '5']);
  assert.equal(topluIsaret(['3', '4', '5'], haric), 'kismi');
  const once = haric;
  haric = haricDegistir(haric, '4', true);
  assert.ok(once.has('4') && !haric.has('4'), 'değişmez küme: eski durum bozulmaz');
  assert.equal(topluIsaret(['3', '4', '5'], new Set(['3', '4', '5'])), 'hic');
  assert.equal(topluIsaret([], new Set()), 'hic');
  // TopluAski/TopluAta düğmesi: seçili + işaretli ilişkililer
  const dugme = (h: Set<string>) => ['1', '2'].length + ekleriAyikla(['1', '2'], liste, h).length;
  assert.equal(dugme(new Set()), 5);
  assert.equal(dugme(new Set(['4', '5'])), 3);
  // "Hepsini aynı ekibe ata": yalnız işaretliler gider; hepsi kaldırılınca boş (düğme kapalı, sunucuya gitmez)
  const veri = { gruplar: [
    { isler: [x('3'), x('4')] }, { isler: [x('5')] }] } as unknown as Parameters<typeof hizalaSecimi>[0];
  assert.deepEqual(hizalaSecimi(veri, new Set()), ['3', '4', '5']);
  assert.deepEqual(hizalaSecimi(veri, new Set(['4'])), ['3', '5']);
  assert.deepEqual(hizalaSecimi(veri, new Set(['3', '4', '5'])), []);
  assert.deepEqual(hizalaSecimi(null, new Set()), []);
});

test('Askı: bütün askıların önceden seçili nedeni ABONE > Ulaşılamadı (sunucu eşi boss_yazma.VARSAYILAN_ASKI)', () => {
  assert.deepEqual({ ...VARSAYILAN_CIFT }, { neden: 'ABONE', alt: 'Ulaşılamadı' });
});

test('BOSS kuyruğu: hata raporu düz metin; task no, eylem, durum, mesaj, eksik alan (kişisel alan yok)', () => {
  const m = hataRaporu(
    [
      { id: 7, zaman: '2026-10-09 11:47:38', guncelleme: null, tur: 'aski', eylem: 'Askıya al', task_no: '201269372', is_no: '201269372',
        durum: 'hata', mesaj: 'Task is suspended', eksik: [], http: 500, return_kodu: null, yeniden: true },
      { id: 8, zaman: '2026-10-09 12:00:00', guncelleme: null, tur: 'aski', eylem: 'Askıya al', task_no: '201269373', is_no: '201269373',
        durum: 'eksik', mesaj: null, eksik: ['BOSS alt neden listesi bekleniyor (işin kategorisi)'], http: null, return_kodu: null, yeniden: true },
    ],
    new Date(2026, 9, 9, 18, 0),
  ).split(String.fromCharCode(10));
  assert.equal(m.length, 3);
  assert.equal(m[1], '#7 · 2026-10-09 11:47:38 · Askı · Task 201269372 · Hata · HTTP 500 · Task is suspended');
  assert.equal(m[2], '#8 · 2026-10-09 12:00:00 · Askı · Task 201269373 · Eksik alan · Eksik: BOSS alt neden listesi bekleniyor (işin kategorisi)');
});

test('Uyarı sütunu: ↻ tekrar simgesi; ▾ değerleri ayrı ayrı "Altyapı", "Kanal şikâyeti", "Tekrar" (çok değerli)', () => {
  const s = {
    uyarilar: [
      { tur: 'tekrar', metin: '30 gün içinde tekrar · önceki 200000001 kapanış 01.10' },
      { tur: 'altyapi', metin: "Bu binada açık altyapı ticket'ı var" },
    ],
  } as unknown as IsSatir;
  assert.equal(uyariMetni(s), ['↻', '⛔'].sort().join(' '));
  assert.deepEqual(cokluAc(uyariSuzgec(s)), ['Altyapı', 'Tekrar']);
  assert.deepEqual(cokluAc(uyariSuzgec({ uyarilar: [] } as unknown as IsSatir)), ['']);
  const v = ['Altyapı', 'Tekrar'].join(COKLU_AYRAC);
  assert.equal(cokluUyar({ degerler: ['Tekrar'], kip: undefined }, v), true, 'dahil: biri yeter');
  assert.equal(cokluUyar({ degerler: ['Kanal şikâyeti'], kip: undefined }, v), false);
  assert.equal(cokluUyar({ degerler: ['Tekrar'], kip: 'haric' }, v), false, 'hariç: biri varsa gizli');
  assert.equal(cokluUyar({ degerler: ['Kanal şikâyeti'], kip: 'haric' }, v), true);
  assert.equal(cokluUyar({ degerler: [''], kip: undefined }, ''), true, '(Boşlar)');
  assert.equal(cokluUyar({ degerler: null, kip: undefined }, v), true, 'süzgeç yok');
});

console.log(`saf testler: ${gecen} geçti`);
