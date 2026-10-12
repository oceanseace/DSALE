// Eklentiyi tarayıcısız sınar: sahte BOSS sunucusu (fetch), sahte sayfa ve sahte chrome API'si.
//   node kod/eklenti/test.mjs
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';

const oku = (ad) => readFileSync(fileURLToPath(new URL(`./${ad}`, import.meta.url)), 'utf8');
const bekle = (ms) => new Promise((r) => setTimeout(r, ms));
const GIZLI = 'Bearer GIZLI-OTURUM-123';
const B = 'https://boss.turkcell.com.tr/boss-gateway-service';

// ------------------------------------------------------------------ 1) eşleme (eslem.js)
const ekok = { console };
vm.runInNewContext(oku('eslem.js'), ekok);
const E = ekok.DehanetEslem;

// ------------------------------------------------------------------ 1b) kişisel veri maskesi (maske.js)
{
  const mk = {};
  vm.runInNewContext(oku('maske.js'), mk);
  const M = mk.DehanetMaske;
  const sizmaz = (o, ...degerler) => {
    const j = JSON.stringify(M.maskele(o));
    for (const d of degerler) assert.ok(!j.includes(d), `maske sızdırdı: ${d} → ${j}`);
  };
  sizmaz({ phones: ['5551112233'], customer: { gsmList: ['5559998877'] } }, '5551112233', '5559998877');
  sizmaz({ a: { b: { c: { d: { e: { contacts: [{ phone: '5551234567', fullName: 'Ayşe Yılmaz' }] } } } } } }, '5551234567', 'Ayşe');
  sizmaz({ x: { y: { z: { w: { v: { u: { phone: '5550001122' } } } } } } }, '5550001122');
  sizmaz({ tckn: '12345678901', identityNo: '98765432109', birthDate: '01.01.1960', subscriberNo: '7001234' }, '12345678901', '98765432109', '1960', '7001234');
  sizmaz({ deger: '0532 111 22 33', liste: [{ value: '+905321112233' }] }, '0532 111 22 33', '905321112233');
  // biçim görünür kalır: Task No (9 hane), tarih, kod
  assert.deepEqual(JSON.parse(JSON.stringify(M.maskele({ crmTaskId: '400000001', createDate: '2026-10-01', status: 'OPEN' }))), { crmTaskId: '400000001', createDate: '2026-10-01', status: 'OPEN' });
  // eslem.js'in müşteri alanı saydığı adlar maskede de kişisel (sunucu: test_boss_ham_kisisel.py aynı adlar)
  for (const ad of ['customerName', 'customerNo', 'fullName', 'nameSurname', 'firstName', 'subscriberNo', 'contactNo', 'mobileNo', 'gsm', 'msisdn', 'address', 'tckn', 'identityNo', 'birthDate']) {
    assert.ok(M.KISISEL.test(ad), `maske kişisel saymıyor: ${ad}`);
  }
}
const uuidOf = (i) => `0a1b2c3d-1111-2222-3333-${String(i).padStart(12, '0')}`;
const hamGorev = (i, durum = 'Randevusuz') => ({
  id: uuidOf(i), taskNo: 400000000 + i, taskType: { name: 'Bağlantı Problemi' }, status: { name: durum },
  customer: { customerNo: `9${i}`, name: 'Deneme Müşteri', phone: '0532 111 22 33' }, team: { id: 5, name: 'ALI EKIBI' },
  createDate: '28.09.2026 09:00', address: 'DENEME APT. Görükle Mh. Test Sk. No:1 NİLÜFER/BURSA', locationId: '12345',
  appointment: { startDate: '2026-10-01T10:00:00', endDate: '2026-10-01T12:00:00' }, segment: 'Bireysel', salesChannel: 'GLOBAL CC',
});
{
  const { sade, harita } = E.cevir(hamGorev(1));
  assert.equal(sade.task_no, '400000001');
  assert.equal(sade.musteri_no, '91');
  assert.equal(sade.musteri_adi, 'Deneme Müşteri');
  assert.equal(sade.task_adi, 'Bağlantı Problemi');
  assert.equal(sade.durum, 'Randevusuz');
  assert.equal(sade.ekip, 'ALI EKIBI');
  assert.equal(sade.acilis, '2026-09-28 09:00:00');
  assert.equal(sade.randevu_bas, '2026-10-01 10:00:00');
  assert.equal(sade.lokasyon, '12345');
  assert.equal(sade.segment, 'Bireysel');
  assert.equal(sade.satis_kanali, 'GLOBAL CC');
  assert.deepEqual([...sade.telefonlar], ['0532 111 22 33']);
  const h = JSON.stringify(harita);
  assert.ok(!h.includes('Deneme') && !h.includes('0532') && !h.includes('4000'), 'alan haritası değer içermemeli');
  assert.equal(harita.musteri_adi, 'customer.name');
  assert.equal(sade.boss_uuid, uuidOf(1));
  assert.equal(harita.boss_uuid, 'id');
}

{
  // Gerçek BOSS liste alanları (06.10 canlı akış, gorev_yapisi): crmTaskId, saleChannel, taskCategory, productInfo …
  const gercek = {
    slaDefinition: true, slaHourValue: 12, id: uuidOf(50), crmTaskId: '412345678', customerName: 'Deneme Müşteri',
    customerNo: '12345678', city: 'BURSA', district: 'NİLÜFER', dealer: 'DEHANET', team: { id: 9, name: 'EKIP A' },
    segment: 'Bireysel', saleChannel: 'DEHANET MAĞAZA', taskCategory: 'TV+ Kurulum', taskCategoryType: 101,
    taskStatus: 'OPEN', taskStatusDesc: 'Açık', productInfo: 'Fiber 100', locationId: null, parentCrmTaskId: null,
    createDate: '2026-10-01T09:00:00', isComplaint: null, etiketler: ['a', 'b'], liste: [{ x: 1 }],
  };
  const { sade, harita } = E.cevir(gercek);
  assert.equal(sade.task_no, '412345678');
  assert.equal(harita.task_no, 'crmTaskId');
  assert.equal(sade.satis_kanali, 'DEHANET MAĞAZA', 'satış kanalı BOSS\'un saleChannel alanından');
  assert.equal(harita.satis_kanali, 'saleChannel');
  assert.equal(sade.urun, 'Fiber 100');
  assert.equal(sade.kategori, 'TV+ Kurulum');
  assert.equal(sade.durum, 'Açık');
  // ham: BOSS'un bütün alanları, düzleştirilmiş, değerler sade (metin/sayı/bool/null)
  assert.equal(sade.ham.saleChannel, 'DEHANET MAĞAZA');
  assert.equal(sade.ham['team.name'], 'EKIP A');
  assert.equal(sade.ham.taskCategoryType, 101);
  assert.equal(sade.ham.locationId, null);
  assert.equal(sade.ham.etiketler, 'a, b');
  assert.equal(typeof sade.ham.liste, 'string');
  assert.ok(Object.values(sade.ham).every((v) => v === null || ['string', 'number', 'boolean'].includes(typeof v)));
  assert.ok(!JSON.stringify(harita).includes('DEHANET'), 'alan haritası değer içermemeli');
}

{
  // Task No: 9 haneli BOSS numarası; uuid rakamlarına indirgenmez
  const u = uuidOf(7);
  assert.equal(E.cevir({ id: u, foxFlowNo: '205123456', customer: { customerNo: '13496616' } }).sade.task_no, '205123456');
  assert.equal(E.cevir({ id: u, akisNo: 205123457, customer: { customerNo: '13496616' } }).sade.task_no, '205123457');
  const y = E.cevir({ id: u, customer: { customerNo: '13496616' } }).sade;
  assert.equal(y.task_no_gecici, true);
}

// ------------------------------------------------------------------ 2) kanca: sayfanın isteğini yakala, tekrarla
const DURUMLAR = [['Açık', 1], ['Başlandı', 2], ['Ertelendi', 3], ['Merkeze gönderildi', 4], ['Konum paylaşıldı', 5],
  ['Randevu alındı', 6], ['Askıya alındı', 7], ['Randevusuz', 8], ['Tamamlandı', 9], ['FOX tarafından iptal edildi', 10], ['İptal edildi', 11]];
const ACIK = Array.from({ length: 450 }, (_, i) => hamGorev(i + 1, i % 3 ? 'Randevusuz' : 'Başlandı'));
const KAPALI = Array.from({ length: 5 }, (_, i) => hamGorev(900 + i, 'Tamamlandı'));
const kodu = (ad) => { const d = DURUMLAR.find(([n]) => n === ad); return d[1] === 1 ? 'OPEN' : `S${d[1]}`; };
const bossIstekleri = [];
const listeIstekGovdeleri = [];
const yazAnlik = { suren: 0, enCok: 0, sira: [], gecikme: 25, red: new Map() };   // red: açıklama → [HTTP kodları] (sırayla)
const NEDEN_YOLU = '/boss-gateway-service/task-service/api/v1/task/reasons/task-category/106/record-type/SUSPEND_REASONS/product-code/Tell_FiberInternetProduct';
async function sahteBoss(url, ayar = {}) {
  const u = new URL(url);
  bossIstekleri.push({ yol: u.pathname, yetki: (ayar.headers || {}).Authorization, yontem: ayar.method || 'GET', basliklar: { ...(ayar.headers || {}) }, sorgu: u.search, govde: ayar.body });
  const json = (o) => ({ ok: true, status: 200, json: async () => o, text: async () => JSON.stringify(o), clone() { return this; } });
  if (u.pathname.endsWith('/task/statuses')) return json(DURUMLAR.map(([name, id]) => ({ id, name, code: kodu(name) })));
  if (u.pathname.endsWith('/task/list')) {
    // gerçek biçim: gövde {searchTerm, taskStatus:[kod], runQuery, skipTotalCount}; sayfa + boy adreste
    const g = JSON.parse(ayar.body);
    listeIstekGovdeleri.push({ govde: g, sorgu: u.search, basliklar: { ...(ayar.headers || {}) } });
    const kume = new Set(g.taskStatus);
    let hepsi = [...ACIK, ...KAPALI].filter((t) => kume.has(kodu(t.status.name)));
    if (g.searchTerm) hepsi = hepsi.filter((t) => String(t.taskNo).includes(g.searchTerm));
    if (Array.isArray(g.teamIds)) hepsi = [];
    const page = Number(u.searchParams.get('page') || 0);
    const size = Number(u.searchParams.get('size') || 20);
    return json({ content: hepsi.slice(page * size, (page + 1) * size), totalElements: hepsi.length });
  }
  if (/\/task\/note$|\/appointment$|\/task\/suspend$/.test(u.pathname) && ayar.method === 'POST') {
    yazAnlik.suren++;
    yazAnlik.enCok = Math.max(yazAnlik.enCok, yazAnlik.suren);
    const g = JSON.parse(ayar.body);
    yazAnlik.sira.push(g.description);
    await bekle(yazAnlik.gecikme);
    yazAnlik.suren--;
    const kodlar = yazAnlik.red.get(g.description);
    if (kodlar && kodlar.length) {
      const kod = kodlar.shift();
      return { ok: false, status: kod, headers: { get: () => null }, json: async () => ({}), text: async () => JSON.stringify({ message: `kod ${kod}` }) };
    }
    if (g.description === 'PATLA') {
      return { ok: false, status: 500, json: async () => ({}), text: async () => JSON.stringify({ message: 'Internal error', customerName: 'SIZMAMALI', gsm: '05321234567' }) };
    }
    if (g.description === 'RED') return json({ returnCode: 12, returnMessage: 'Görev bulunamadı 05321234567' });
    return json({ returnCode: 0, returnMessage: 'Success', content: { gizli: 'SIZMAMALI' } });
  }
  if (u.pathname === NEDEN_YOLU) {
    return json({ content: [{ reasonId: '26CDE1BE-1B03-8A0A-5384-F0273F623CE7', code: 'ABONE', description: 'Abone kaynaklı', customerName: 'SIZMAMALI' }] });
  }
  if (u.pathname.endsWith('/user/location/TECH')) {
    return json({ returnCode: 0, data: [{ teamId: 5, teamName: 'ALI EKIBI', location: { latitude: '40.19', longitude: '29.06', locationDate: 1759303500000 } }] });
  }
  if (u.pathname.endsWith('/teams/type/TECH')) return json([{ id: 5, name: 'ALI EKIBI', active: true }, { id: 6, name: 'ESKI', active: false }]);
  if (u.pathname.endsWith('/task/suspend-reasons')) {
    return json({ content: [{ id: 1, name: 'Abone kaynaklı', customerName: 'SIZMAMALI', subReasons: [{ id: 11, name: 'Ulaşılamadı', gsm: '05320000000' }] }] });
  }
  if (u.pathname.includes('/device/list')) return { ok: false, status: 500, json: async () => ({}) };
  if (u.pathname.includes(uuidOf(777))) return { ok: false, status: 401, json: async () => ({}) };   // oturum düşmüş
  if (/\/task\/(task-id\/)?[0-9a-f-]{36}\//.test(u.pathname)) {
    const kayit = bossIstekleri[bossIstekleri.length - 1];
    kayit.bas = performance.now();
    await bekle(30);                                     // BOSS yanıt süresi (paralellik ölçülebilsin)
    kayit.bit = performance.now();
    return json({ content: [{ name: 'x', gsm: '0532 000 00 00' }] });
  }
  return json({});
}

const giden = [];
const dinleyiciler = [];
const sayfa = {
  location: { origin: 'https://boss.turkcell.com.tr' }, console, URL, setTimeout, Promise, JSON,
  fetch: sahteBoss,
  postMessage(m, origin) {
    assert.equal(origin, 'https://boss.turkcell.com.tr');
    const kopya = structuredClone(m);
    if (kopya.kaynak === 'dehanet-kanca') giden.push(kopya);
    setTimeout(() => sayfa.__dagit(kopya), 0);
  },
  addEventListener(t, f) { if (t === 'message') dinleyiciler.push(f); },
  XMLHttpRequest: class { open() {} send() {} setRequestHeader() {} addEventListener() {} },
};
sayfa.dinleyiciler = dinleyiciler;
vm.createContext(sayfa);
// vm'de genel nesne içeride 'window' olarak görünür: mesaj kaynağı o olmalı
vm.runInContext('var window = globalThis; window.__dagit = (m) => dinleyiciler.forEach((f) => f({ source: window, origin: location.origin, data: m }));', sayfa);
vm.runInContext(oku('maske.js'), sayfa);
vm.runInContext(oku('kanca.js'), sayfa);

// eşitleme isteği gelmeden önce: istek yok
sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'esitle', istek_id: 'yok' }, sayfa.location.origin);
await bekle(20);
assert.equal(giden.find((m) => m.istek_id === 'yok').hata, 'istek_yok');

// sayfa kendi listesini çeker (kullanıcının süzgeciyle: yalnız Açık, 20'şer)
await sayfa.fetch(`${B}/task-service/api/v1/task/list?size=20&sort=createDate,asc`, {
  method: 'POST', headers: { Authorization: GIZLI, 'Content-Type': 'application/json' },
  body: JSON.stringify({ searchTerm: '', taskStatus: ['OPEN'], runQuery: true, skipTotalCount: true }),
});
await bekle(10);
assert.ok(giden.some((m) => m.tur === 'liste-yakalandi'));
const t0 = Date.now();
sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'esitle', istek_id: 't1', acik: DURUMLAR.slice(0, 8).map((d) => d[0]),
  kapali: DURUMLAR.slice(8).map((d) => d[0]), kapaliSayfa: 2 }, sayfa.location.origin);
while (!giden.some((m) => m.tur === 'esitle-bitti' && m.istek_id === 't1')) {
  await bekle(50);
  assert.ok(Date.now() - t0 < 15000, 'eşitleme bitmedi');
}
const bitti = giden.find((m) => m.tur === 'esitle-bitti' && m.istek_id === 't1');
assert.equal(bitti.tam, true, 'bütün açık durumlar okunmalı');
assert.equal(bitti.okunan, 455);
assert.deepEqual(bitti.ekipler, [{ ad: 'ALI EKIBI', id: 5, aktif: true }, { ad: 'ESKI', id: 6, aktif: false }]);
const parcalar = giden.filter((m) => m.tur === 'esitle-parca' && m.istek_id === 't1');
assert.equal(parcalar.filter((p) => p.etiket === 'acik').length, 3, '200\'lük 3 sayfa');
const listeIstekleri = bossIstekleri.filter((i) => i.yol.endsWith('/task/list')).slice(1);
assert.ok(listeIstekleri.every((i) => i.yetki === GIZLI), 'tekrar istekleri sayfanın başlığıyla gitmeli');
assert.ok(!JSON.stringify(giden).includes('GIZLI'), 'oturum bilgisi hiçbir mesaja girmemeli');
// Kullanıcı BOSS'ta arar / süzer / başka sıralama seçer: eşitleme etkilenmez. Yakalanan istekten yalnız başlıklar
// tazelenir; gövde KANONİK (searchTerm boş, kullanıcı süzgeci yok, durumlar eşitlemenin), adres şablondan.
{
  await sayfa.fetch(`${B}/task-service/api/v1/task/list?size=20&sort=priority,desc&teamId=5`, {
    method: 'POST', headers: { Authorization: GIZLI, 'Content-Type': 'application/json', 'X-Tazelik': 'yeni' },
    body: JSON.stringify({ searchTerm: '400000001', taskStatus: ['S8'], runQuery: true, skipTotalCount: true, teamIds: [5], dateFrom: '2026-10-01' }),
  });
  await bekle(10);
  const once = listeIstekGovdeleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'esitle', istek_id: 't2', acik: DURUMLAR.slice(0, 8).map((d) => d[0]),
    kapali: DURUMLAR.slice(8).map((d) => d[0]), kapaliSayfa: 2 }, sayfa.location.origin);
  const t2 = Date.now();
  while (!giden.some((m) => m.tur === 'esitle-bitti' && m.istek_id === 't2')) {
    await bekle(50);
    assert.ok(Date.now() - t2 < 15000, 'ikinci eşitleme bitmedi');
  }
  const b2 = giden.find((m) => m.tur === 'esitle-bitti' && m.istek_id === 't2');
  assert.deepEqual([b2.tam, b2.okunan], [true, 455], 'kullanıcının araması/süzgeci eşitlemeye sızmamalı');
  const sonraki = listeIstekGovdeleri.slice(once);
  assert.ok(sonraki.length >= 4);
  for (const x of sonraki) {
    assert.deepEqual(Object.keys(x.govde).sort(), ['runQuery', 'searchTerm', 'skipTotalCount', 'taskStatus']);
    assert.equal(x.govde.searchTerm, '');
    assert.ok(!/teamId|priority/.test(x.sorgu), `kullanıcının adres süzgeci sızdı: ${x.sorgu}`);
    assert.equal(x.basliklar['X-Tazelik'], 'yeni', 'başlıklar son yakalanan istekten tazelenmeli');
  }
  assert.deepEqual(sonraki[0].govde.taskStatus, DURUMLAR.slice(0, 8).map(([n]) => kodu(n)), '8 açık durum, kod biçiminde');
  const yk = giden.filter((m) => m.adim === 'liste_yakalandi').pop();
  assert.deepEqual([yk.ek.ilk, [...yk.ek.atilan].sort()], [false, ['dateFrom', 'teamIds']]);
  assert.ok(!JSON.stringify(yk).includes('400000001'), 'yakalama tanısında arama değeri');
}
// iş ayrıntısı: bütün sekme uçları sırayla, sayfanın başlığıyla, yalnız GET ve yalnız BOSS kökü
const onceDetay = bossIstekleri.length;
sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'detay', istek_id: 'd1', is_no: '400000001', uuid: uuidOf(1) }, sayfa.location.origin);
while (!giden.some((m) => m.tur === 'detay-bitti' && m.istek_id === 'd1')) {
  await bekle(50);
  assert.ok(Date.now() - t0 < 30000, 'ayrıntı bitmedi');
}
const detayBitti = giden.find((m) => m.tur === 'detay-bitti' && m.istek_id === 'd1');
const detayIstekleri = bossIstekleri.slice(onceDetay);
assert.equal(detayIstekleri.length, 9);
assert.ok(detayIstekleri.every((i) => i.yontem === 'GET' && i.yetki === GIZLI && i.yol.includes(uuidOf(1))));
assert.deepEqual(Object.keys(detayBitti.sekmeler).sort(), ['aciklama', 'adres_teyidi', 'ariza_nedeni', 'cihaz', 'evraklar',
  'fotograflar', 'iletisim', 'tarihce', 'urunler']);
assert.ok(detayBitti.sekmeler.cihaz.hata.startsWith('http_500'));
assert.equal(detayBitti.sekmeler.urunler.veri.content[0].name, 'x');
assert.ok(!JSON.stringify(giden).includes('GIZLI'), 'ayrıntıda oturum bilgisi mesaja girmemeli');
sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'detay', istek_id: 'd2', is_no: '1', uuid: '../x' }, sayfa.location.origin);
await bekle(20);
assert.equal(giden.find((m) => m.istek_id === 'd2').hata, 'uuid_gecersiz');

// BOSS'a yazma yürütücüsü: yaz/dogrulandi ikisi birden true değilse HİÇBİR istek gitmez (önizleme)
{
  const NOT = '/boss-gateway-service/task-service/api/v1/task/note';
  const sonucu = async (id) => {
    const t = Date.now();
    for (;;) {
      const r = giden.filter((m) => m.tur === 'yaz-sonuc' && m.istek_id === id && m.durum !== 'alindi').pop();
      if (r) return r;
      assert.ok(Date.now() - t < 3000, `yazma sonucu gelmedi: ${id}`);
      await bekle(10);
    }
  };
  const yazSonuc = async (istek) => {
    sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'yaz', istek }, sayfa.location.origin);
    return sonucu(istek.istek_id);
  };
  const once = bossIstekleri.length;
  const g = { description: 'not', taskId: uuidOf(1) };
  let r = await yazSonuc({ istek_id: 'y1', kayitlar: [1], yontem: 'POST', yol: NOT, govde: g, yaz: false, dogrulandi: false });
  assert.deepEqual({ ...r, kayitlar: [...r.kayitlar] }, { kaynak: 'dehanet-kanca', tur: 'yaz-sonuc', istek_id: 'y1', kayitlar: [1], durum: 'onizleme', hazir: true });
  r = await yazSonuc({ istek_id: 'y2', kayitlar: [2], yontem: 'POST', yol: NOT, govde: g, yaz: true, dogrulandi: false });
  assert.equal(r.durum, 'onizleme', 'doğrulanmamış şablon gönderilmez');
  r = await yazSonuc({ istek_id: 'y3', kayitlar: [3], yontem: 'POST', yol: '/boss-gateway-service/task-service/api/v1/task/close', govde: g, yaz: true, dogrulandi: true });
  assert.deepEqual([r.durum, r.hata], ['hata', 'uc_izinsiz']);
  assert.equal(bossIstekleri.length, once, 'önizlemede BOSS\'a hiçbir istek gitmemeli');
  // (yalnız sahte BOSS'ta) ikisi de true: sayfanın başlığıyla aynı köke POST; başlık mesaja girmez
  r = await yazSonuc({ istek_id: 'y4', kayitlar: [4], yontem: 'POST', yol: NOT, govde: g, yaz: true, dogrulandi: true });
  assert.deepEqual([r.durum, r.http, r.return_kodu, r.return_mesaji], ['gonderildi', 200, 0, 'Success']);
  // teslim onayı (KANCA_SURUMU 9): gerçek istek kuyruğa alınınca sonuçtan ÖNCE "alindi" iletilir
  {
    const y4 = giden.filter((m) => m.tur === 'yaz-sonuc' && m.istek_id === 'y4').map((m) => m.durum);
    assert.deepEqual(y4, ['alindi', 'gonderildi']);
    assert.ok(!giden.some((m) => m.tur === 'yaz-sonuc' && m.istek_id === 'y1' && m.durum === 'alindi'), 'önizlemede onay yok');
  }
  const giden1 = bossIstekleri.slice(once);
  assert.deepEqual(giden1.map((i) => [i.yontem, i.yol, i.yetki]), [['POST', NOT, GIZLI]]);
  assert.deepEqual(JSON.parse(giden1[0].govde), g, 'gövde sunucunun verdiği gibi, birebir');
  assert.ok(!JSON.stringify(giden).includes('GIZLI'));
  assert.ok(!JSON.stringify(giden).includes('SIZMAMALI'), 'BOSS yanıtının geri kalanı iletilmez');
  // tek iş denemesi: şablon doğrulanmamış olsa da (deneme: true) gönderilir
  r = await yazSonuc({ istek_id: 'd5', kayitlar: [5], yontem: 'POST', yol: NOT, govde: g, yaz: true, dogrulandi: false, deneme: true });
  assert.equal(r.durum, 'gonderildi');
  r = await yazSonuc({ istek_id: 'y6', kayitlar: [6], yontem: 'POST', yol: NOT, govde: g, yaz: false, dogrulandi: true, deneme: true });
  assert.equal(r.durum, 'onizleme', 'yaz:false iken deneme bayrağı tek başına göndermez');
  // BOSS returnCode ≠ 0 → hata; mesajdaki uzun sayı maskeli
  r = await yazSonuc({ istek_id: 'y7', kayitlar: [7], yontem: 'POST', yol: NOT, govde: { description: 'RED', taskId: uuidOf(1) }, yaz: true, dogrulandi: true });
  assert.deepEqual([r.durum, r.return_kodu, r.hata], ['hata', 12, 'boss_12']);
  assert.ok(r.return_mesaji.startsWith('Görev bulunamadı') && !r.return_mesaji.includes('05321234567'));
  // HTTP 500: yanıt metni maskeli iletilir (kişisel alan ve uzun sayı gizli)
  r = await yazSonuc({ istek_id: 'y8', kayitlar: [8], yontem: 'POST', yol: NOT, govde: { description: 'PATLA', taskId: uuidOf(1) }, yaz: true, dogrulandi: true });
  assert.deepEqual([r.durum, r.http, r.hata], ['hata', 500, 'http_500']);
  assert.ok(r.yanit_metni.includes('Internal error') && !r.yanit_metni.includes('SIZMAMALI') && !r.yanit_metni.includes('05321234567'));
  // sayfanın kendi randevu (yazma) isteğinin başlıkları o servise yazarken kullanılır; Content-Type tek
  {
    const RANDEVU = '/boss-gateway-service/appointment-service/api/v1/appointment';
    await sayfa.fetch(`https://boss.turkcell.com.tr${RANDEVU}`, { method: 'POST', headers: { Authorization: GIZLI, 'content-type': 'application/json;charset=UTF-8', 'X-Kanal': 'randevu' }, body: JSON.stringify([{ description: 'elle' }]) });
    await bekle(40);
    const o2 = bossIstekleri.length;
    r = await yazSonuc({ istek_id: 'y9', kayitlar: [9], yontem: 'POST', yol: RANDEVU, govde: [{ description: 'biz' }], yaz: true, dogrulandi: true });
    assert.equal(r.durum, 'gonderildi');
    const b = bossIstekleri[o2].basliklar;
    assert.equal(b['X-Kanal'], 'randevu', 'randevu servisine sayfanın kendi randevu başlıkları');
    assert.deepEqual(Object.keys(b).filter((k) => /content-type/i.test(k)), ['Content-Type']);
    assert.equal(b['Content-Type'], 'application/json');
  }
  // paralel: 1 → SIRAYLA (aynı anda en çok bir), geliş sırasıyla
  await bekle(1300);                                 // PATLA (500) havuzu ~1 sn geri çekti; bitsin
  yazAnlik.enCok = 0;
  yazAnlik.sira.length = 0;
  for (const n of ['a', 'b', 'c']) {
    sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'yaz', istek: { istek_id: `s${n}`, kayitlar: [n], yontem: 'POST', yol: NOT,
      govde: { description: n, taskId: uuidOf(1) }, yaz: true, dogrulandi: true, paralel: 1 } }, sayfa.location.origin);
  }
  for (const n of ['a', 'b', 'c']) assert.equal((await sonucu(`s${n}`)).durum, 'gonderildi');
  assert.deepEqual([yazAnlik.enCok, [...yazAnlik.sira]], [1, ['a', 'b', 'c']]);

  // 100 askı, paralel 6 (varsayılan): aynı anda EN ÇOK 6, her isteğin sonucu ayrı (100 yaz-sonuc, 100 'alindi'),
  // başlama sırası = geliş sırası; süre ≈ 100/6 ≈ 17 tur (sıralı yürütücüde 100 tur)
  const ASKI = '/boss-gateway-service/task-service/api/v1/task/suspend';
  const asakiGonder = (onEk, n, ek = {}) => {
    for (let k = 0; k < n; k++) {
      sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'yaz', istek: { istek_id: `${onEk}${k}`, kayitlar: [k], yontem: 'POST', yol: ASKI,
        govde: { taskId: uuidOf(k + 1), suspendStatusEndDate: '10.10.2026 18:00', suspendReasonId: 'R', suspendSubReasonId: 'A',
          description: `${onEk}${k}` }, yaz: true, dogrulandi: true, ...ek } }, sayfa.location.origin);
    }
  };
  const hepsiniBekle = async (onEk, n) => {
    const t = Date.now();
    for (;;) {
      const bitti = new Set(giden.filter((m) => m.tur === 'yaz-sonuc' && String(m.istek_id).startsWith(onEk) && m.durum !== 'alindi').map((m) => m.istek_id));
      if (bitti.size >= n) return;
      assert.ok(Date.now() - t < 20000, `${onEk}: ${bitti.size}/${n} sonuç`);
      await bekle(10);
    }
  };
  {
    const TUR_MS = 100;                               // sahte BOSS yanıt süresi (bir "tur")
    yazAnlik.gecikme = TUR_MS;
    yazAnlik.enCok = 0;
    yazAnlik.sira.length = 0;
    const once100 = bossIstekleri.length;
    const t0 = performance.now();
    asakiGonder('p', 100, { paralel: 6 });
    await hepsiniBekle('p', 100);
    const sure = performance.now() - t0;
    const sonuclar = giden.filter((m) => m.tur === 'yaz-sonuc' && String(m.istek_id).startsWith('p'));
    assert.equal(sonuclar.filter((m) => m.durum === 'alindi').length, 100, 'her istek için teslim onayı');
    assert.equal(sonuclar.filter((m) => m.durum === 'gonderildi').length, 100, 'her istek için ayrı sonuç');
    assert.ok(sonuclar.filter((m) => m.durum === 'gonderildi').every((m) => m.kayitlar.length === 1 && m.http === 200 && m.return_kodu === 0));
    assert.equal(bossIstekleri.length - once100, 100, 'her askı tek istek (yeniden gönderim yok)');
    assert.equal(yazAnlik.enCok, 6, 'aynı anda en çok 6 istek');
    assert.deepEqual([...yazAnlik.sira], Array.from({ length: 100 }, (_, k) => `p${k}`), 'başlama sırası = geliş sırası');
    const tur = sure / (TUR_MS + 150);              // işçi başına: yanıt + 150 ms ara
    console.log(`  100 askı / paralel 6: ${Math.round(sure)} ms ≈ ${tur.toFixed(1)} tur (sıralıda ~100 tur)`);
    assert.ok(tur >= 16 && tur <= 24, `100/6 ≈ 17 tur beklenirdi, ${tur.toFixed(1)}`);
  }
  // üst sınır 10: sunucu 50 dese de aynı anda en çok 10
  {
    yazAnlik.gecikme = 40;
    yazAnlik.enCok = 0;
    asakiGonder('q', 30, { paralel: 50 });
    await hepsiniBekle('q', 30);
    assert.equal(yazAnlik.enCok, 10, 'paralel 10\'u aşamaz');
  }
  // 429 / 503: aynı istek üstel geri çekilmeyle yeniden denenir (sonuç tek, başarılı); 500 yeniden DENENMEZ
  {
    yazAnlik.gecikme = 5;
    yazAnlik.red.set('r0', [429, 503]);
    yazAnlik.red.set('r1', [500]);
    const onceR = bossIstekleri.length;
    const t0 = Date.now();
    asakiGonder('r', 2, { paralel: 6 });
    await hepsiniBekle('r', 2);
    const son = (id) => giden.filter((m) => m.tur === 'yaz-sonuc' && m.istek_id === id && m.durum !== 'alindi');
    assert.equal(son('r0').length, 1, 'yeniden denemede tek sonuç');
    assert.deepEqual([son('r0')[0].durum, son('r0')[0].http], ['gonderildi', 200]);
    assert.deepEqual([son('r1')[0].durum, son('r1')[0].http, son('r1')[0].hata], ['hata', 500, 'http_500']);
    const yollar = bossIstekleri.slice(onceR).map((i) => JSON.parse(i.govde).description);
    assert.equal(yollar.filter((d) => d === 'r0').length, 3, '429 + 503 + başarı = 3 deneme');
    assert.equal(yollar.filter((d) => d === 'r1').length, 1, '500 yeniden gönderilmez (çift yazma olmasın)');
    assert.ok(Date.now() - t0 >= 1500, 'geri çekilme: 1 sn + 2 sn (±%20) beklendi');
    yazAnlik.gecikme = 25;
  }
  // yazma sürerken eşitleme taraması BAŞLAMAZ (kuyruk boşalınca başlar)
  {
    await bekle(3000);                                // önceki 500'ün geri çekilmesi bitsin
    yazAnlik.gecikme = 60;
    asakiGonder('e', 12, { paralel: 6 });
    await bekle(5);
    const listeOnce = listeIstekGovdeleri.length;
    sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'esitle', istek_id: 'esY', acik: ['Açık'], kapali: [] }, sayfa.location.origin);
    await bekle(60);
    assert.equal(listeIstekGovdeleri.length, listeOnce, 'yazma sürerken liste taranmaz');
    await hepsiniBekle('e', 12);
    for (let k = 0; k < 300 && !giden.some((m) => m.tur === 'esitle-bitti' && m.istek_id === 'esY'); k++) await bekle(20);
    assert.ok(listeIstekGovdeleri.length > listeOnce, 'yazma bitince eşitleme yapılır');
    assert.ok(!giden.find((m) => m.tur === 'esitle-bitti' && m.istek_id === 'esY').hata);
    yazAnlik.gecikme = 25;
  }
}
// kanca durumu: yeniden yüklenen köprü sorar, kanca listeyi tutuyor mu söyler
sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'durum' }, sayfa.location.origin);
await bekle(10);
assert.equal(giden.filter((m) => m.tur === 'kanca-durum').pop().liste, true);
// askı nedeni kataloğu: yalnız kimlik/ad alanları (kişisel alan düşer); işe özgü (taskId'li) uç yakalanmaz
await sayfa.fetch(`${B}/task-service/api/v1/task/suspend-reasons`, { method: 'GET', headers: { Authorization: GIZLI } });
await sayfa.fetch(`${B}/task-service/api/v1/task/trouble-reason?taskId=5`, { method: 'GET', headers: { Authorization: GIZLI } });
await bekle(20);
{
  const n = giden.filter((m) => m.tur === 'tani' && m.adim === 'aski_nedenleri');
  assert.equal(n.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(n[0].ek.veri)), { content: [{ id: 1, name: 'Abone kaynaklı', subReasons: [{ id: 11, name: 'Ulaşılamadı' }] }] });
  assert.equal(giden.filter((m) => m.adim === 'neden_listesi').length, 0, 'kayıt modu kapalıyken neden listesi gitmez');
}
// işe özgü askı nedeni kataloğu (sunucu ister): yalnız o kalıptaki GET, sayfanın başlığıyla; kişisel alan düşer
{
  const once = bossIstekleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'neden-oku', yol: '/boss-gateway-service/task-service/api/v1/task/close' }, sayfa.location.origin);
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'neden-oku', yol: `${NEDEN_YOLU}/../../x` }, sayfa.location.origin);
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'neden-oku', yol: NEDEN_YOLU }, sayfa.location.origin);
  await bekle(30);
  assert.deepEqual(bossIstekleri.slice(once).map((i) => [i.yontem, i.yol, i.yetki]), [['GET', NEDEN_YOLU, GIZLI]]);
  const t = giden.filter((m) => m.adim === 'aski_nedenleri').pop();
  assert.equal(t.yol, NEDEN_YOLU, 'katalog yolu kısaltılmadan (kategori + ürün kodu sunucuda anahtar)');
  assert.deepEqual(JSON.parse(JSON.stringify(t.ek.veri)), { content: [{ reasonId: '26CDE1BE-1B03-8A0A-5384-F0273F623CE7', code: 'ABONE', description: 'Abone kaynaklı' }] });
  // alt neden listesi (gerçek yol uzun: .../reason/id/{GUID}/sub/reasons/task-category/../product-code/..): NETWORK
  // gibi üst nedenlerin alt listesini sunucu bu kalıpla ister (KANCA_SURUMU 9; eskiden sonek 40 karakterle sınırlıydı)
  const ALT = '/boss-gateway-service/task-service/api/v1/task/reason/id/4697B3FA-0000-4000-8000-000000000001/sub/reasons/task-category/560/product-code/Tell_FiberInternetProduct';
  const o2 = bossIstekleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'neden-oku', yol: ALT }, sayfa.location.origin);
  await bekle(30);
  assert.deepEqual(bossIstekleri.slice(o2).map((i) => [i.yontem, i.yol]), [['GET', ALT]]);
}
// ekip GPS konumu (KANCA_SURUMU 11): uç görülmeden önce varsayılan yol (liste başlıklarıyla); sayfa ucu çağırınca
// yol + başlıklar tutulur, sayfanın yanıtı iletilir; yapısı tanıya bir kez, DEĞERSİZ; yalnız GET
{
  const KONUM_YOLU = '/boss-gateway-service/account-service/api/v1/user/location/TECH';
  const konumBitti = async (id) => {
    for (let k = 0; k < 100; k++) {
      const r = giden.find((m) => m.tur === 'konum-bitti' && m.istek_id === id);
      if (r) return r;
      await bekle(10);
    }
    throw new Error(`konum-bitti gelmedi: ${id}`);
  };
  let once = bossIstekleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'konum-oku', istek_id: 'k1' }, sayfa.location.origin);
  let r = await konumBitti('k1');
  assert.deepEqual(bossIstekleri.slice(once).map((i) => [i.yontem, i.yol, i.yetki]), [['GET', KONUM_YOLU, GIZLI]], 'varsayılan yol, liste başlığı');
  assert.deepEqual([r.yol, r.varsayilan, r.hata], [KONUM_YOLU, true, undefined]);
  assert.equal(r.veri.data[0].teamName, 'ALI EKIBI');
  const yapi = giden.filter((m) => m.adim === 'konum_yapisi');
  assert.equal(yapi.length, 1);
  assert.ok(!/ALI EKIBI|40\.19|1759303500000/.test(JSON.stringify(yapi[0])), 'konum yapısında değer olmamalı');
  assert.equal(yapi[0].ek.yapi.data[1].location.latitude, 'string');
  // sayfanın kendi GPS isteği (sorgulu, kendi başlığıyla): yanıt iletilir, sonraki okuma o yolu ve başlıkları kullanır
  await sayfa.fetch(`${B}/account-service/api/v1/user/location/TECH?aktif=1`, { method: 'GET', headers: { Authorization: GIZLI, 'X-Konum': 'sayfa' } });
  await bekle(20);
  const yanit = giden.filter((m) => m.tur === 'konum-yanit');
  assert.equal(yanit.length, 1);
  assert.deepEqual([yanit[0].yol, yanit[0].veri.data[0].teamId], [KONUM_YOLU, 5]);
  await sayfa.fetch(`${B}/account-service/api/v1/user/location/TECH?aktif=1`, { method: 'GET', headers: { Authorization: GIZLI } });
  await bekle(20);
  assert.equal(giden.filter((m) => m.tur === 'konum-yanit').length, 1, 'sayfa sık yoklarsa 20 sn içinde bir kez');
  assert.equal(giden.filter((m) => m.adim === 'konum_yapisi').length, 1, 'yapı tanısı bir kez');
  once = bossIstekleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'konum-oku', istek_id: 'k2' }, sayfa.location.origin);
  r = await konumBitti('k2');
  const k2 = bossIstekleri.slice(once);
  assert.deepEqual(k2.map((i) => [i.yontem, i.yol, i.sorgu]), [['GET', KONUM_YOLU, '?aktif=1']]);
  assert.equal(k2[0].basliklar['X-Konum'], undefined, 'son yakalanan isteğin başlıkları');
  assert.equal(k2[0].yetki, GIZLI);
  assert.equal(r.varsayilan, false);
  assert.ok(!JSON.stringify(giden).includes('GIZLI'), 'konum okumasında oturum bilgisi mesaja girmemeli');
  // hiçbir başlığı bilinmeyen sayfa: istek yok, "konum_yok"
  const bos = { location: { origin: 'https://boss.turkcell.com.tr' }, console, URL, setTimeout, Promise, JSON, giden: [], d: [] };
  bos.fetch = async () => { throw new Error('istek gitmemeli'); };
  bos.postMessage = (m) => { const k = structuredClone(m); if (k.kaynak === 'dehanet-kanca') bos.giden.push(k); setTimeout(() => bos.__dagit(k), 0); };
  bos.addEventListener = (t, f) => { if (t === 'message') bos.d.push(f); };
  bos.XMLHttpRequest = class { open() {} send() {} setRequestHeader() {} addEventListener() {} };
  vm.createContext(bos);
  vm.runInContext('var window = globalThis; window.__dagit = (m) => d.forEach((f) => f({ source: window, origin: location.origin, data: m }));', bos);
  vm.runInContext(oku('kanca.js'), bos);
  bos.postMessage({ kaynak: 'dehanet-komut', tur: 'konum-oku', istek_id: 'k3' }, bos.location.origin);
  await bekle(20);
  assert.equal(bos.giden.find((m) => m.tur === 'konum-bitti').hata, 'konum_yok');
}
// sayfa tanısı sorgunun yalnız ANAHTARLARINI taşır (değer yok)
for (const m of giden.filter((x) => x.tur === 'tani' && x.adim === 'sayfa')) assert.ok(Array.isArray(m.ek.sorgu), 'sayfa tanısında sorgu değeri');
// kayıt modu: yalnız yapı
sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'kayit-modu', acik: true }, sayfa.location.origin);
await bekle(10);
// kayıt modunda neden listesi maskeli gider; işe özgü adreste hiç gitmez
await sayfa.fetch(`${B}/task-service/api/v1/task/suspend-reasons`, { method: 'GET', headers: { Authorization: GIZLI } });
await sayfa.fetch(`${B}/task-service/api/v1/task/trouble-reason?taskId=5`, { method: 'GET', headers: { Authorization: GIZLI } });
await bekle(20);
{
  const n = giden.filter((m) => m.adim === 'neden_listesi');
  assert.equal(n.length, 1);
  assert.ok(!/SIZMAMALI|05320000000/.test(JSON.stringify(n[0])), 'neden listesinde kişisel değer');
}
await sayfa.fetch(`${B}/task-service/api/v1/task/123456789/appointment`, { method: 'POST', headers: { Authorization: GIZLI },
  body: JSON.stringify({ date: '01/10/2026', note: 'müşteri evde' }) });
await bekle(10);
const kayit = giden.find((m) => m.tur === 'kayit');
assert.equal(kayit.yol, '/boss-gateway-service/task-service/api/v1/task/#/appointment');
assert.deepEqual(kayit.govdeYapi, { date: 'string', note: 'string' });
assert.ok(!JSON.stringify(kayit).includes('evde'));

// sürüm: aynı sürüm ikinci kez yüklenince fetch yeniden sarılmaz; sayfada ESKİ kanca varsa yenisi kurulmaz, "eski" der
{
  const sarili = sayfa.fetch;
  vm.runInContext(oku('kanca.js'), sayfa);
  assert.equal(sayfa.fetch, sarili, 'aynı sürüm kanca fetch ikinci kez sarmamalı');
  const eskiSayfa = { ...sayfa, giden: [] };
  const eskiDinleyen = [];
  Object.assign(eskiSayfa, {
    __dehanetKanca: true, fetch: sahteBoss,
    postMessage(m) { eskiSayfa.giden.push(structuredClone(m)); },
    addEventListener(t, f) { if (t === 'message') eskiDinleyen.push(f); },
  });
  vm.createContext(eskiSayfa);
  vm.runInContext('var window = globalThis;', eskiSayfa);
  vm.runInContext(oku('kanca.js'), eskiSayfa);
  assert.equal(eskiSayfa.fetch, sahteBoss, 'eski kanca varken yenisi fetch sarmamalı');
  eskiSayfa.eskiDinleyen = eskiDinleyen;
  vm.runInContext("eskiDinleyen.forEach((f) => f({ source: window, data: { kaynak: 'dehanet-komut', tur: 'durum' } }))", eskiSayfa);
  assert.ok(eskiSayfa.giden.some((m) => m.tur === 'kanca-durum' && m.eski), 'eski kanca uyarısı');
}

// ------------------------------------------------------------------ 3) arka plan: topla, çevir, uygulamaya yolla
const depo = { session: {}, local: { eslesme: '1234-5678', port: 8080 } };
const alan = (ad) => ({
  get: async (k) => Object.fromEntries((k || Object.keys(depo[ad])).map((x) => [x, structuredClone(depo[ad][x])])),
  set: async (o) => Object.assign(depo[ad], structuredClone(o)),
});
let arkaDinleyici = null;
const sekmeMesajlari = [];
const uygulamaIstekleri = [];
const chrome = {
  sidePanel: { setPanelBehavior: () => Promise.resolve() },
  runtime: { onMessage: { addListener: (f) => (arkaDinleyici = f) }, getManifest: () => ({ version: 'test' }) },
  storage: { session: alan('session'), local: alan('local') },
  tabs: { query: async () => [{ id: 7, active: true }], sendMessage: async (id, m) => sekmeMesajlari.push([id, m]) },
  alarms: { create: () => {}, onAlarm: { addListener: () => {} } },
};
const arkaFetch = async (url, ayar) => {
  uygulamaIstekleri.push({ url, ayar });
  return { ok: true, status: 200, json: async () => ({ fark: { yeni: 450 }, uyari: null }) };
};
const arka = { chrome, console, URL, fetch: arkaFetch, structuredClone, setTimeout, Date, Math, JSON, Promise };
arka.self = arka;
arka.importScripts = () => vm.runInContext(oku('eslem.js'), arka);
vm.createContext(arka);
vm.runInContext(oku('arka.js'), arka);
const A = arka.__dehanetArka;
const bas = await A.esitleBaslat('test');
assert.equal(bas.durum, 'basladi');
assert.equal(sekmeMesajlari[0][1].tur, 'esitle-baslat');
const id = bas.istek_id;
for (const p of parcalar) await A.parcaIsle({ istek_id: id, gorevler: p.gorevler });
await A.bittiIsle({ istek_id: id, tam: true, okunan: 455, ekipler: bitti.ekipler });
assert.equal(uygulamaIstekleri.length, 1);
const u = uygulamaIstekleri[0];
assert.equal(u.url, 'http://127.0.0.1:8080/api/boss/esitle');
assert.equal(u.ayar.headers['X-Eslesme-Kodu'], '1234-5678');
const gonderilen = JSON.parse(u.ayar.body);
assert.equal(gonderilen.gorevler.length, 455);
assert.equal(gonderilen.tam, true);
assert.equal(gonderilen.ekipler.length, 2);
assert.equal(gonderilen.gorevler[0].boss_uuid, uuidOf(1));
assert.ok(gonderilen.gorevler.every((g) => /^\d{9}$/.test(g.task_no)));
assert.ok(!u.ayar.body.includes('GIZLI'), 'uygulamaya oturum bilgisi gitmemeli');
assert.equal(depo.session.esitleme.durum, 'tamam');
assert.equal(depo.session.esitleme.acik, 450);
assert.ok(!JSON.stringify(depo.local).includes('Deneme'), 'kalıcı depoda müşteri bilgisi olmamalı');
assert.ok(gonderilen.gorevler[0].ham && gonderilen.gorevler[0].ham.salesChannel === 'GLOBAL CC', 'ham alanlar uygulamaya gider');
assert.ok(!('isler' in depo.session), 'iş listesi (müşteri verisi) eklentinin deposuna girmez');
// yanlış kod
uygulamaIstekleri.length = 0;
arka.fetch = async () => ({ ok: false, status: 401, json: async () => ({}) });
vm.runInContext('fetch = self.fetch', arka);
const s401 = await A.sunucuyaGonder([], false);
assert.equal(s401.durum, 'kod_yanlis');
// BOSS sekmesine ulaşılamıyor (eklenti yenilendi): betikler yeniden yüklenir, kullanıcıdan F5 istenmez
{
  const yuklenen = [];
  let ilk = true;
  chrome.scripting = { executeScript: async (o) => { yuklenen.push([o.target.tabId, o.files.join(','), o.world || 'ISOLATED']); } };
  const asilGonder = chrome.tabs.sendMessage;
  chrome.tabs.sendMessage = async (id, m) => {
    if (ilk) { ilk = false; throw new Error('Could not establish connection. Receiving end does not exist.'); }
    return asilGonder(id, m);
  };
  sekmeMesajlari.length = 0;
  const b = await A.esitleBaslat('test');
  assert.equal(b.durum, 'basladi');
  assert.deepEqual(yuklenen, [[7, 'maske.js,kanca.js', 'MAIN'], [7, 'kopru.js', 'ISOLATED']]);
  assert.equal(sekmeMesajlari.length, 1, 'yeniden yüklemeden sonra bir kez gider');
  await A.bittiIsle({ istek_id: b.istek_id, hata: 'istek_yok' });
  // uyutulmuş sekme: yeniden yüklenir (betik yüklenmez)
  const yenilenen = [];
  chrome.tabs.reload = async (id) => { yenilenen.push(id); };
  const asilSorgu = chrome.tabs.query;
  chrome.tabs.query = async () => [{ id: 8, active: true, discarded: true }];
  chrome.tabs.sendMessage = async () => { throw new Error('yok'); };
  yuklenen.length = 0;
  assert.equal((await A.esitleBaslat('test')).durum, 'sayfa_yenile');
  assert.deepEqual(yenilenen, [8]);
  assert.deepEqual(yuklenen, []);
  chrome.tabs.query = asilSorgu;
  chrome.tabs.sendMessage = asilGonder;
}

// BOSS'a yazma yoklaması: sunucu "kapali" derse kancaya yaz:false gider; sonuç sunucuya döner
{
  const cagri = [];
  let yanit = { yazma: 'kapali', istekler: [{ istek_id: 'y9', kayitlar: [9], tur: 'not', yontem: 'POST',
    yol: '/boss-gateway-service/task-service/api/v1/task/note', govde: { description: 'x', taskId: uuidOf(1) }, dogrulandi: true, yaz: true }] };
  arka.fetch = async (url, ayar = {}) => {
    cagri.push({ url, ayar });
    if (url.endsWith('/api/boss/yazilacaklar')) return { ok: true, status: 200, json: async () => yanit };
    return { ok: true, status: 200, json: async () => ({ ok: true }) };
  };
  vm.runInContext('fetch = self.fetch', arka);
  sekmeMesajlari.length = 0;
  await A.yazilacaklariSor();
  assert.equal(cagri[0].ayar.headers['X-Eslesme-Kodu'], '1234-5678');
  const ym = sekmeMesajlari.map((x) => x[1]).find((m) => m.tur === 'yaz-baslat');
  assert.equal(ym.istek.yaz, false, 'ayar kapalıyken yaz hep false');
  await A.yazilacaklariSor();
  assert.equal(sekmeMesajlari.filter((x) => x[1].tur === 'yaz-baslat').length, 1, 'aynı istek iki kez gitmez');
  // eklentinin bilmediği (servis çalışanı uyuyup uyandı / 60 sn'den uzun beklemiş) istek_id'nin sonucu da sunucuya
  // gider — eskiden düşürülüyordu ve BOSS'a yazılmış iş "Sonuç gelmedi" oluyordu (08.10)
  assert.equal((await A.yazSonucIsle({ istek_id: 'y77', kayitlar: [77], durum: 'gonderildi', http: 200, return_kodu: 0 })).durum, 'tamam');
  assert.equal(JSON.parse(cagri.filter((c) => c.url.endsWith('/api/boss/yazma-sonucu')).pop().ayar.body).istek_id, 'y77');
  assert.equal((await A.yazSonucIsle({ durum: 'onizleme' })).durum, 'gecersiz');
  cagri.length = 0;
  await A.yazSonucIsle({ istek_id: 'y9', kayitlar: [9], durum: 'onizleme', hazir: true });
  const ys = cagri.find((c) => c.url.endsWith('/api/boss/yazma-sonucu'));
  assert.deepEqual(JSON.parse(ys.ayar.body), { istek_id: 'y9', kayitlar: [9], durum: 'onizleme', http: null, hata: null, hazir: true, return_kodu: null, return_mesaji: null, yanit_metni: null });
  // açık ama şablon doğrulanmamış → yine yaz:false
  yanit = { yazma: 'acik', istekler: [{ ...yanit.istekler[0], istek_id: 'y10', dogrulandi: false, yaz: false }] };
  sekmeMesajlari.length = 0;
  await A.yazilacaklariSor();
  assert.equal(sekmeMesajlari[0][1].istek.yaz, false);
  // anahtar kapalı + tek iş denemesi → yalnız o istek yaz:true; okunacak katalog sekmeye gider
  yanit = { yazma: 'kapali', paralel: 4, okunacaklar: [NEDEN_YOLU], istekler: [
    { ...yanit.istekler[0], istek_id: 'd11', dogrulandi: true, yaz: true, deneme: true },
    { ...yanit.istekler[0], istek_id: 'y12', dogrulandi: true, yaz: true }] };
  sekmeMesajlari.length = 0;
  await A.yazilacaklariSor();
  const ms = sekmeMesajlari.map((x) => x[1]);
  assert.deepEqual(ms.map((m) => m.tur), ['neden-oku-baslat', 'yaz-baslat', 'yaz-baslat']);
  assert.equal(ms[1].istek.paralel, 4, 'sunucunun paralel ayarı kancaya iletilir');
  assert.equal(ms[0].yol, NEDEN_YOLU);
  assert.deepEqual([ms[1].istek.yaz, ms[1].istek.deneme, ms[2].istek.yaz, ms[2].istek.deneme], [true, true, false, false]);
  cagri.length = 0;
  await A.yazSonucIsle({ istek_id: 'd11', kayitlar: [9], durum: 'gonderildi', http: 200, return_kodu: 0, return_mesaji: 'Success' });
  assert.deepEqual(JSON.parse(cagri[0].ayar.body), { istek_id: 'd11', kayitlar: [9], durum: 'gonderildi', http: 200, hata: null,
    hazir: false, return_kodu: 0, return_mesaji: 'Success', yanit_metni: null });
  // "alindi" sunucuya iletilir (kayıt teslim edildi sayılır)
  cagri.length = 0;
  await A.yazSonucIsle({ istek_id: 'y12', kayitlar: [12], durum: 'alindi' });
  assert.equal(JSON.parse(cagri[0].ayar.body).durum, 'alindi');
  // BOSS sekmesi yok: gerçek (yaz:true) istekler "ertelendi" olarak sunucuya döner (hiçbir şey gitmedi);
  // önizleme istekleri için bir şey denmez. Eskiden 5 dk sonra "Sonuç gelmedi" oluyordu (09.10).
  {
    const asilSorgu = chrome.tabs.query;
    chrome.tabs.query = async () => [];
    yanit = { yazma: 'acik', istekler: [{ ...yanit.istekler[1], istek_id: 'y13', kayitlar: [13], yaz: true },
      { ...yanit.istekler[1], istek_id: 'y14', kayitlar: [14], yaz: false }] };
    cagri.length = 0;
    assert.equal((await A.yazilacaklariSor()).durum, 'boss_kapali');
    const ert = cagri.filter((c) => c.url.endsWith('/api/boss/yazma-sonucu')).map((c) => JSON.parse(c.ayar.body));
    assert.deepEqual(ert.map((b) => [b.istek_id, b.durum, b.hata]), [['y13', 'ertelendi', 'sekme_yok']]);
    chrome.tabs.query = asilSorgu;
  }
}

// ayrıntı istekleri: uygulamadan sor → sekmeye ilet → sonucu uygulamaya yolla
const detayIstek = [];
arka.fetch = async (url, ayar = {}) => {
  detayIstek.push({ url, ayar });
  if (url.endsWith('/api/boss/istekler')) return { ok: true, status: 200, json: async () => ({ istekler: [{ istek_id: 'i1', is_no: '400000001', uuid: uuidOf(1) }] }) };
  return { ok: true, status: 200, json: async () => ({ ok: true }) };
};
vm.runInContext('fetch = self.fetch', arka);
sekmeMesajlari.length = 0;
assert.equal((await A.istekleriSor()).istek, 1);
assert.equal(detayIstek[0].ayar.headers['X-Eslesme-Kodu'], '1234-5678');
assert.deepEqual({ ...sekmeMesajlari[0][1] }, { tur: 'detay-baslat', istek_id: 'i1', is_no: '400000001', uuid: uuidOf(1) });
await A.istekleriSor();
assert.equal(sekmeMesajlari.length, 1, 'aynı istek iki kez sekmeye gitmemeli');
assert.equal((await A.detayBittiIsle({ istek_id: 'zz' })).durum, 'beklenmiyor');
await A.detayBittiIsle({ istek_id: 'i1', is_no: '400000001', uuid: uuidOf(1), sekmeler: detayBitti.sekmeler });
const dPost = detayIstek.find((i) => i.url.endsWith('/api/boss/detay'));
assert.equal(dPost.url, 'http://127.0.0.1:8080/api/boss/detay');
const dGovde = JSON.parse(dPost.ayar.body);
assert.equal(dGovde.istek_id, 'i1');
assert.equal(Object.keys(dGovde.sekmeler).length, 9);
assert.ok(!dPost.ayar.body.includes('GIZLI'));
// MAP/TASKS ⟳ "şimdi eşitle": yoklama yanıtında esitle:true → eklenti hemen eşitleme başlatır
{
  arka.fetch = async (url) => (url.endsWith('/api/boss/istekler')
    ? { ok: true, status: 200, json: async () => ({ istekler: [], esitle: true }) }
    : { ok: true, status: 200, json: async () => ({ ok: true }) });
  vm.runInContext('fetch = self.fetch', arka);
  sekmeMesajlari.length = 0;
  await A.istekleriSor();
  await bekle(20);
  const em = sekmeMesajlari.find((x) => x[1].tur === 'esitle-baslat');
  assert.ok(em, 'esitle:true eşitleme başlatmalı');
  await A.bittiIsle({ istek_id: em[1].istek_id, hata: 'test' });      // sonraki testler için eşitleme kapanır
}

// ------------------------------------------------------------------ 4) artımlı eşitleme + telefon önden okuma
{
  const g = E.cevir({ ...hamGorev(1), lastUpdateDate: '2026-10-02T10:00:00' }).sade;
  assert.equal(g.guncelleme, '2026-10-02 10:00:00');
  assert.equal(E.iz(g), 'Randevusuz|ALI EKIBI|2026-10-01 10:00:00|2026-10-01 12:00:00|2026-10-02 10:00:00');
  assert.equal(E.iz({ durum: 'Açık' }), 'Açık||||');
}
// kanca: yalnız customer/list, sıralı, sayfanın başlığıyla; bozuk uuid atlanır
{
  const once = bossIstekleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'iletisim', istek_id: 'c1',
    isler: [{ task_no: '400000001', uuid: uuidOf(1) }, { task_no: '9', uuid: '../x' }, { task_no: '400000002', uuid: uuidOf(2) }] }, sayfa.location.origin);
  const t1 = Date.now();
  while (!giden.some((m) => m.tur === 'iletisim-bitti' && m.istek_id === 'c1')) {
    await bekle(50);
    assert.ok(Date.now() - t1 < 10000, 'iletişim okuması bitmedi');
  }
  const ist = bossIstekleri.slice(once);
  assert.equal(ist.length, 2);
  assert.ok(ist.every((i) => i.yontem === 'GET' && i.yetki === GIZLI && i.yol.endsWith('/detail/customer/list')));
  const p = giden.filter((m) => m.tur === 'iletisim-parca' && m.istek_id === 'c1').flatMap((m) => m.sonuclar);
  assert.deepEqual(p.map((x) => x.task_no), ['400000001', '400000002']);
  assert.equal(p[0].veri.content[0].gsm, '0532 000 00 00');
  assert.equal(giden.find((m) => m.tur === 'iletisim-bitti' && m.istek_id === 'c1').okunan, 2);
  assert.ok(!JSON.stringify(giden).includes('GIZLI'));
}
// kanca: ayrıntı önden okuma — bir işin sekmeleri aynı anda EN ÇOK 3 istekle, yalnız GET, sayfanın başlığıyla;
// kullanıcının açtığı iş (9 sekme aynı anda) araya girince önden okuma yeni istek başlatmaz; her iş ayrı parça
{
  const once = bossIstekleri.length;
  const onden = [11, 12, 13, 14];
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'detay-onden', istek_id: 'o1',
    isler: [{ task_no: '400000011', uuid: uuidOf(11) }, { task_no: '9', uuid: '../x' },
      ...onden.slice(1).map((n) => ({ task_no: `4000000${n}`, uuid: uuidOf(n) }))] }, sayfa.location.origin);
  await bekle(120);
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'detay', istek_id: 'd5', is_no: '400000005', uuid: uuidOf(5) }, sayfa.location.origin);
  const t1 = Date.now();
  while (!giden.some((m) => m.tur === 'detay-onden-bitti' && m.istek_id === 'o1') || !giden.some((m) => m.tur === 'detay-bitti' && m.istek_id === 'd5')) {
    await bekle(20);
    assert.ok(Date.now() - t1 < 15000, 'önden okuma / ayrıntı bitmedi');
  }
  const ist = bossIstekleri.slice(once);
  assert.ok(ist.every((i) => i.yontem === 'GET' && i.yetki === GIZLI));
  const ondenHepsi = ist.filter((i) => onden.some((n) => i.yol.includes(uuidOf(n))));
  assert.equal(ondenHepsi.length, 36, '4 iş × 9 sekme');
  const ondenIst = ondenHepsi.filter((i) => i.bas != null);
  const enCok = (liste) => Math.max(...liste.map((a) => liste.filter((b) => b.bas <= a.bas && b.bit > a.bas).length));
  assert.ok(enCok(ondenIst) <= 3, `önden okuma aynı anda en çok 3 istek (${enCok(ondenIst)})`);
  assert.ok(enCok(ondenIst) >= 2, 'bir işin sekmeleri paralel okunur');
  const kul = ist.filter((i) => i.yol.includes(uuidOf(5)));
  assert.equal(kul.length, 9);
  const kulZ = kul.filter((i) => i.bas != null);            // cihaz sekmesi sahte BOSS'ta hemen 500 döner
  assert.equal(enCok(kulZ), kulZ.length, 'kullanıcının açtığı işin sekmeleri aynı anda');
  const kBas = Math.min(...kulZ.map((i) => i.bas)), kBit = Math.max(...kulZ.map((i) => i.bit));
  const araya = ondenIst.filter((i) => i.bas > kBas && i.bas < kBit).length;
  assert.equal(araya, 0, `kullanıcının ayrıntısı sürerken önden okuma yeni istek başlatmamalı (${araya})`);
  assert.ok(kBit - kBas < 200, 'kullanıcının ayrıntısı tek dalgada biter');
  const parcalarO = giden.filter((m) => m.tur === 'detay-onden-parca' && m.istek_id === 'o1');
  assert.ok(parcalarO.every((m) => m.sonuclar.length === 1), 'her iş okununca hemen ayrı parça');
  const p = parcalarO.flatMap((m) => m.sonuclar);
  assert.deepEqual(p.map((x) => x.task_no), ['400000011', '400000012', '400000013', '400000014']);
  assert.equal(p[0].uuid, uuidOf(11));
  assert.equal(Object.keys(p[0].sekmeler).length, 9);
  assert.equal(giden.find((m) => m.tur === 'detay-onden-bitti' && m.istek_id === 'o1').okunan, 4);
  assert.ok(!JSON.stringify(giden).includes('GIZLI'));
  // oturum düştü: ilk 401'de durur (yeni sekme/iş denenmez)
  const once2 = bossIstekleri.length;
  sayfa.postMessage({ kaynak: 'dehanet-komut', tur: 'detay-onden', istek_id: 'o2',
    isler: [{ task_no: '400000777', uuid: uuidOf(777) }, { task_no: '400000013', uuid: uuidOf(13) }] }, sayfa.location.origin);
  while (!giden.some((m) => m.tur === 'detay-onden-bitti' && m.istek_id === 'o2')) await bekle(50);
  assert.equal(giden.find((m) => m.tur === 'detay-onden-bitti' && m.istek_id === 'o2').hata, 'oturum');
  const sonra = bossIstekleri.slice(once2);
  assert.ok(sonra.length <= 3 && sonra.every((i) => i.yol.includes(uuidOf(777))), 'yalnız o anda uçuştaki istekler; sonraki iş denenmez');
}
// arka: sunucunun izleri → yalnız değişen/yeni + kaldirilan; yanıttaki iletişim listesi sekmeye gider
{
  const esit = [];
  const gorevlerA = parcalar.flatMap((p) => E.cevirHepsi(p.gorevler).gorevler);
  const izler = Object.fromEntries(gorevlerA.filter((g) => !/Tamamland/.test(g.durum)).map((g) => [g.task_no, E.iz(g)]));
  izler['400000002'] = 'eski|iz';
  izler['400000903'] = E.iz({ durum: 'Açık' });   // sunucu açık sanıyor, BOSS'ta Tamamlandı
  izler['499999999'] = '';                          // eski Excel kalıntısı: BOSS'ta yok
  delete izler['400000003'];                       // sunucuda yok → yeni
  arka.fetch = async (url, ayar = {}) => {
    esit.push({ url, ayar });
    if (url.endsWith('/api/boss/izler')) return { ok: true, status: 200, json: async () => ({ izler, tam_gerekli: false }) };
    if (url.endsWith('/api/boss/esitle')) return { ok: true, status: 200, json: async () => ({ ozet: { yeni: 1, degisen: 1, kapanan: 2 }, iletisim: [{ task_no: '400000003', uuid: uuidOf(3) }] }) };
    if (url.endsWith('/api/boss/iletisim')) return { ok: true, status: 200, json: async () => ({ iletisim: [], iletisim_tamam: 5, iletisim_toplam: 9 }) };
    return { ok: true, status: 200, json: async () => ({}) };
  };
  vm.runInContext('fetch = self.fetch', arka);
  depo.session.esitlemeTam = Date.now();
  sekmeMesajlari.length = 0;
  const b2 = await A.esitleBaslat('test');
  for (const p of parcalar) await A.parcaIsle({ istek_id: b2.istek_id, gorevler: p.gorevler });
  await A.bittiIsle({ istek_id: b2.istek_id, tam: true, okunan: 455, ekipler: bitti.ekipler });
  const post = esit.find((i) => i.url.endsWith('/api/boss/esitle'));
  const govde = JSON.parse(post.ayar.body);
  assert.equal(govde.mod, 'fark');
  assert.deepEqual(govde.gorevler.map((g) => g.task_no).sort(), ['400000002', '400000003', '400000903']);
  assert.ok(govde.gorevler.every((g) => typeof g.iz === 'string'));
  assert.deepEqual(govde.kaldirilan, ['499999999']);
  assert.equal(depo.session.esitleme.mod, 'fark');
  assert.equal(depo.session.esitleme.kapanan, 2);
  await bekle(10);
  const ilBas = sekmeMesajlari.map((x) => x[1]).find((m) => m.tur === 'iletisim-baslat');
  assert.deepEqual(ilBas.isler.map((x) => ({ ...x })), [{ task_no: '400000003', uuid: uuidOf(3) }]);
  await A.iletisimParcaIsle({ istek_id: ilBas.istek_id, sonuclar: [{ task_no: '400000003', veri: [] }] });
  const ilPost = esit.find((i) => i.url.endsWith('/api/boss/iletisim'));
  assert.equal(ilPost.ayar.headers['X-Eslesme-Kodu'], '1234-5678');
  assert.equal(JSON.parse(ilPost.ayar.body).sonuclar[0].task_no, '400000003');
  assert.equal((await A.iletisimBittiIsle({ istek_id: ilBas.istek_id, okunan: 1 })).durum, 'bitti');
  assert.equal(depo.session.esitleme.iletisimToplam, 9);
  // eksik görüntüde kaldirilan boş
  assert.deepEqual([...A.farkHesapla(gorevlerA.map((g) => ({ ...g, iz: E.iz(g) })), { izler: { '1': '' } }, false).kaldirilan], []);
  assert.equal(A.farkHesapla([], { izler: {}, tam_gerekli: true }, true), null);
}

// arka: eşitleme sürerken büyük sayı (acik) ve son eşitleme DURUR; yalnız suruyor işareti. Yanıttaki detay_onden
// sekmeye gider; parçalar /api/boss/detay-onden'e; yanıtın sıradaki işleri yeni tur başlatır.
{
  const cagri = [];
  let sonraki = [{ task_no: '400000022', uuid: uuidOf(22) }];
  arka.fetch = async (url, ayar = {}) => {
    cagri.push({ url, ayar });
    if (url.endsWith('/api/boss/izler')) return { ok: true, status: 200, json: async () => ({ izler: {}, tam_gerekli: true }) };
    if (url.endsWith('/api/boss/esitle')) return { ok: true, status: 200, json: async () => ({ ozet: { yeni: 0, degisen: 0, kapanan: 0 },
      detay_onden: [{ task_no: '400000021', uuid: uuidOf(21) }], detay_tamam: 0, detay_toplam: 3, detay_kalan_dk: 1 }) };
    if (url.endsWith('/api/boss/detay-onden')) {
      const j = { detay_onden: sonraki, detay_tamam: 1, detay_toplam: 3, detay_kalan_dk: 1 };
      sonraki = [];
      return { ok: true, status: 200, json: async () => j };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };
  vm.runInContext('fetch = self.fetch', arka);
  const onceAcik = depo.session.esitleme.acik;
  const onceSon = depo.session.esitleme.sonEsitleme;
  assert.ok(onceAcik > 0 && onceSon);
  sekmeMesajlari.length = 0;
  const b = await A.esitleBaslat('test');
  assert.equal(depo.session.esitleme.suruyor, true);
  assert.equal(depo.session.esitleme.acik, onceAcik, 'eşitleme başlarken sayı sıfırlanmamalı');
  assert.equal(depo.session.esitleme.sonEsitleme, onceSon);
  assert.notEqual(depo.session.esitleme.durum, 'okunuyor');
  // başarısız eşitleme de sayıyı silmez
  await A.bittiIsle({ istek_id: b.istek_id, hata: 'http_500 /task/list' });
  assert.deepEqual([depo.session.esitleme.suruyor, depo.session.esitleme.acik, depo.session.esitleme.durum], [false, onceAcik, 'okuma_hata']);
  const b2 = await A.esitleBaslat('test');
  for (const p of parcalar) await A.parcaIsle({ istek_id: b2.istek_id, gorevler: p.gorevler });
  await A.bittiIsle({ istek_id: b2.istek_id, tam: true, okunan: 455, ekipler: bitti.ekipler });
  assert.deepEqual([depo.session.esitleme.suruyor, depo.session.esitleme.acik, depo.session.esitleme.detayToplam], [false, 450, 3]);
  await bekle(10);
  const ob = sekmeMesajlari.map((x) => x[1]).find((m) => m.tur === 'detay-onden-baslat');
  assert.deepEqual(ob.isler.map((x) => ({ ...x })), [{ task_no: '400000021', uuid: uuidOf(21) }]);
  assert.equal((await A.detayOndenBaslat([{ task_no: '1', uuid: uuidOf(1) }])).durum, 'suruyor', 'aynı anda tek önden okuma');
  await A.detayOndenParcaIsle({ istek_id: ob.istek_id, sonuclar: [{ task_no: '400000021', uuid: uuidOf(21), sekmeler: {} }] });
  const dp = cagri.find((c) => c.url.endsWith('/api/boss/detay-onden'));
  assert.equal(dp.url, 'http://127.0.0.1:8080/api/boss/detay-onden');
  assert.equal(dp.ayar.headers['X-Eslesme-Kodu'], '1234-5678');
  assert.equal(JSON.parse(dp.ayar.body).sonuclar[0].task_no, '400000021');
  assert.equal(depo.session.esitleme.detayTamam, 1);
  sekmeMesajlari.length = 0;
  assert.equal((await A.detayOndenBittiIsle({ istek_id: ob.istek_id, okunan: 1 })).durum, 'basladi', 'sıradaki tur');
  const ob2 = sekmeMesajlari.map((x) => x[1]).find((m) => m.tur === 'detay-onden-baslat');
  assert.deepEqual(ob2.isler.map((x) => x.task_no), ['400000022']);
  await A.detayOndenParcaIsle({ istek_id: ob2.istek_id, sonuclar: [] });
  assert.equal((await A.detayOndenBittiIsle({ istek_id: ob2.istek_id, okunan: 0 })).durum, 'bitti');
  assert.equal((await A.detayOndenBittiIsle({ istek_id: 'yok' })).durum, 'beklenmiyor');

  // servis çalışanı uyuyup uyandı: kancanın eski okumasından gelen parça yine sunucuya gider (düşmez)
  cagri.length = 0;
  await A.detayOndenParcaIsle({ istek_id: 'eski-okuma', sonuclar: [{ task_no: '400000023', uuid: uuidOf(23), sekmeler: {} }] });
  assert.equal(JSON.parse(cagri.find((c) => c.url.endsWith('/api/boss/detay-onden')).ayar.body).sonuclar[0].task_no, '400000023');

  // kesintiden sonra kaldığı yerden: okuma yokken yoklama sunucudan sıradakileri ister ve başlatır
  sonraki = [{ task_no: '400000031', uuid: uuidOf(31) }];
  depo.session.yakalanan = { 7: Date.now() };
  vm.runInContext('ondenSon = 0; ondenBekle = 0; onden = null;', arka);
  cagri.length = 0;
  sekmeMesajlari.length = 0;
  assert.equal((await A.ondenDevam()).durum, 'basladi');
  assert.deepEqual(JSON.parse(cagri[0].ayar.body), { sonuclar: [] }, 'yalnız sıradakiler sorulur');
  assert.deepEqual(sekmeMesajlari.map((x) => x[1]).find((m) => m.tur === 'detay-onden-baslat').isler.map((x) => x.task_no), ['400000031']);
  assert.equal((await A.ondenDevam()).durum, 'suruyor', 'okuma sürerken yeniden başlatılmaz');
  // sunucuda okunacak iş kalmadı → bir dakika sorulmaz
  vm.runInContext('ondenSon = 0; ondenBekle = 0; onden = null;', arka);
  assert.equal((await A.ondenDevam()).durum, 'bos');
  assert.equal((await A.ondenDevam()).durum, 'bekliyor');
}
// arka: genel anahtar kapalı ama eylemin kendi anahtarı açık (not) → yaz:true; atama → yaz:false
{
  const yanit = { yazma: 'kapali', istekler: [
    { istek_id: 'y31', kayitlar: [31], tur: 'not', yontem: 'POST', yol: '/boss-gateway-service/task-service/api/v1/task/note',
      govde: { description: 'x', taskId: uuidOf(1) }, dogrulandi: true, yaz: true, eylem_acik: true },
    { istek_id: 'y32', kayitlar: [32], tur: 'atama', yontem: 'POST', yol: '/boss-gateway-service/appointment-service/api/v1/appointment',
      govde: [{}], dogrulandi: true, yaz: true, eylem_acik: false },
    { istek_id: 'y33', kayitlar: [33], tur: 'not', yontem: 'POST', yol: '/boss-gateway-service/task-service/api/v1/task/note',
      govde: { description: 'y', taskId: uuidOf(1) }, dogrulandi: false, yaz: true, eylem_acik: true }] };
  arka.fetch = async (url) => (url.endsWith('/api/boss/yazilacaklar')
    ? { ok: true, status: 200, json: async () => yanit } : { ok: true, status: 200, json: async () => ({}) });
  vm.runInContext('fetch = self.fetch', arka);
  sekmeMesajlari.length = 0;
  await A.yazilacaklariSor();
  const y = Object.fromEntries(sekmeMesajlari.map((x) => x[1]).filter((m) => m.tur === 'yaz-baslat').map((m) => [m.istek.istek_id, m.istek.yaz]));
  assert.deepEqual(y, { y31: true, y32: false, y33: false });
}

// ------------------------------------------------------------------ 4b) panel: büyük sayı son başarılı eşitlemede kalır
{
  const ogeler = {};
  const oge = (ad) => (ogeler[ad] ||= { textContent: '', className: '', hidden: false, value: '', checked: false, disabled: false,
    innerHTML: '', addEventListener: () => {}, focus: () => {} });
  const simdi = Date.now();
  const sDepo = { esitleme: { durum: 'tamam', suruyor: true, basla: simdi - 5000, sonEsitleme: simdi - 60000, acik: 2814,
    yeni: 1, degisen: 2, kapanan: 0, detayTamam: 1200, detayToplam: 2814, detayKalanDk: 150 }, hazir: true };
  const panel = { console, Date, Math, JSON, Promise, Number, String, Object, setInterval: () => 0, setTimeout,
    document: { querySelector: (s) => oge(s), activeElement: null }, navigator: {},
    chrome: { storage: { session: { get: async () => structuredClone(sDepo), set: async () => {} },
      local: { get: async () => ({ eslesme: '1234-5678', port: 8080 }), set: async () => {} }, onChanged: { addListener: () => {} } },
    runtime: { sendMessage: async () => ({}) } } };
  vm.createContext(panel);
  vm.runInContext(oku('panel.js'), panel);
  await bekle(20);
  const sa = new Date(simdi - 60000).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  assert.equal(ogeler['#durum'].textContent, `2.814 açık iş · son eşitleme ${sa}`);
  assert.equal(ogeler['#denetim'].textContent, 'denetleniyor…');
  assert.ok(ogeler['#kartlar'].innerHTML.includes('2.814'));
  assert.ok(ogeler['#detay'].textContent.startsWith('İş ayrıntıları okunuyor: 1.200 / 2.814'), ogeler['#detay'].textContent);
  assert.equal(ogeler['#simdi'].disabled, true);
  // eşitleme bitti: ikinci satır boş, sayı aynı
  sDepo.esitleme.suruyor = false;
  vm.runInContext('ciz()', panel);
  await bekle(20);
  assert.equal(ogeler['#denetim'].textContent, '');
  assert.ok(ogeler['#durum'].textContent.startsWith('2.814 açık iş'));
}

// ------------------------------------------------------------------ 5) köprü (kopru.js): yeniden yükleme
{
  const iletilen = [];
  const dinleyen = [];
  const komutlar = [];
  const arkaDinleyen = [];
  const pencere = { location: { origin: 'https://boss.turkcell.com.tr' }, document: { readyState: 'complete' }, console, Date, Math };
  pencere.postMessage = (m, origin) => {
    const k = structuredClone(m);
    if (k.kaynak === 'dehanet-komut') komutlar.push(k);
    setTimeout(() => dinleyen.forEach((f) => f({ source: pencere.window, origin, data: k })), 0);
  };
  pencere.addEventListener = (t, f) => { if (t === 'message') dinleyen.push(f); };
  pencere.chrome = {
    runtime: { sendMessage: (m) => { iletilen.push(m); return Promise.resolve(); }, onMessage: { addListener: (f) => arkaDinleyen.push(f) } },
    storage: { local: { get: async () => ({}) }, onChanged: { addListener: () => {} } },
  };
  vm.createContext(pencere);
  vm.runInContext('var window = globalThis;', pencere);
  vm.runInContext(oku('kopru.js'), pencere);
  vm.runInContext(oku('kopru.js'), pencere);         // eklenti yenilendi: köprü yeniden yüklendi
  await bekle(20);
  assert.ok(komutlar.some((k) => k.tur === 'durum'), 'yeniden yüklenen köprü kancaya durum sorar');
  assert.ok(!iletilen.some((m) => m.tur === 'sayfa-acildi'), 'yeniden yüklemede sayfa açıldı sayılmaz');
  pencere.postMessage({ kaynak: 'dehanet-kanca', tur: 'kanca-durum', liste: true }, pencere.location.origin);
  pencere.postMessage({ kaynak: 'dehanet-kanca', tur: 'yaz-sonuc', istek_id: 'y1', kayitlar: [1], durum: 'gonderildi', http: 200, return_kodu: 0, return_mesaji: 'Success' }, pencere.location.origin);
  await bekle(20);
  assert.equal(iletilen.filter((m) => m.tur === 'liste-yakalandi').length, 1, 'iki köprü aynı mesajı iki kez iletmemeli');
  const ys = iletilen.filter((m) => m.tur === 'yaz-sonuc');
  assert.equal(ys.length, 1);
  assert.deepEqual([ys[0].return_kodu, ys[0].return_mesaji], [0, 'Success']);
  komutlar.length = 0;
  arkaDinleyen.forEach((f) => f({ tur: 'yaz-baslat', istek: { istek_id: 'y1' } }));
  arkaDinleyen.forEach((f) => f({ tur: 'esitle-baslat', istek_id: 'k1' }));
  arkaDinleyen.forEach((f) => f({ tur: 'neden-oku-baslat', yol: NEDEN_YOLU }));
  arkaDinleyen.forEach((f) => f({ tur: 'detay-onden-baslat', istek_id: 'o9', isler: [{ task_no: '1', uuid: uuidOf(1) }] }));
  await bekle(10);
  assert.deepEqual(komutlar.map((k) => k.tur), ['yaz', 'esitle', 'neden-oku', 'detay-onden'], 'komut kancaya bir kez gider');
  pencere.postMessage({ kaynak: 'dehanet-kanca', tur: 'detay-onden-parca', istek_id: 'o9', sonuclar: [{ task_no: '1' }] }, pencere.location.origin);
  pencere.postMessage({ kaynak: 'dehanet-kanca', tur: 'detay-onden-bitti', istek_id: 'o9', okunan: 1 }, pencere.location.origin);
  await bekle(20);
  assert.equal(iletilen.filter((m) => m.tur === 'detay-onden-parca').length, 1);
  assert.equal(iletilen.find((m) => m.tur === 'detay-onden-bitti').okunan, 1);
  assert.equal(komutlar[2].yol, NEDEN_YOLU);
  // ekip GPS: arka → kanca komutu; kanca → arka yanıtları
  komutlar.length = 0;
  arkaDinleyen.forEach((f) => f({ tur: 'konum-oku-baslat', istek_id: 'ko1' }));
  pencere.postMessage({ kaynak: 'dehanet-kanca', tur: 'konum-bitti', istek_id: 'ko1', yol: '/x', veri: { data: [] } }, pencere.location.origin);
  pencere.postMessage({ kaynak: 'dehanet-kanca', tur: 'konum-yanit', yol: '/x', veri: [1] }, pencere.location.origin);
  await bekle(20);
  assert.deepEqual(komutlar.map((k) => [k.tur, k.istek_id]), [['konum-oku', 'ko1']]);
  assert.deepEqual(iletilen.filter((m) => /^konum-/.test(m.tur)).map((m) => m.tur), ['konum-bitti', 'konum-yanit']);
}

// ekip GPS (arka): BOSS sekmesine "konum-oku-baslat"; kancanın sonucu ham haliyle /api/boss/ekip-konum'a, eşleme koduyla
{
  const cagri = [];
  arka.fetch = async (url, ayar = {}) => { cagri.push({ url, ayar }); return { ok: true, status: 200, json: async () => ({}) }; };
  vm.runInContext('fetch = self.fetch', arka);
  sekmeMesajlari.length = 0;
  const b = await A.konumOkut();
  assert.equal(b.durum, 'basladi');
  assert.deepEqual(sekmeMesajlari.map(([id, m]) => [id, m.tur, m.istek_id]), [[7, 'konum-oku-baslat', b.istek_id]]);
  assert.equal((await A.konumOkut()).durum, 'suruyor', 'yanıt beklenirken ikinci istek gitmez');
  await A.konumBittiIsle({ istek_id: b.istek_id, yol: '/u', veri: { data: [{ teamName: 'A', lat: 40, lon: 29 }] } });
  assert.equal(cagri.length, 1);
  assert.equal(cagri[0].url, 'http://127.0.0.1:8080/api/boss/ekip-konum');
  assert.equal(cagri[0].ayar.headers['X-Eslesme-Kodu'], '1234-5678');
  const g = JSON.parse(cagri[0].ayar.body);
  assert.deepEqual([g.kaynak, g.yol, g.veri.data[0].teamName], ['komut', '/u', 'A']);
  await A.konumBittiIsle({ istek_id: 'x', hata: 'mesgul' });
  assert.equal(cagri.length, 1, 'meşgul gürültüsü sunucuya gitmez');
  await A.konumBittiIsle({ istek_id: 'x', hata: 'konum_yok' });
  assert.equal(JSON.parse(cagri[1].ayar.body).hata, 'konum_yok');
  await A.konumYanitIsle({ yol: '/u', veri: [1] });
  await A.konumYanitIsle({ yol: '/u', veri: [2] });
  assert.equal(cagri.length, 3, 'sayfanın yanıtları en çok 30 saniyede bir');
  assert.equal(JSON.parse(cagri[2].ayar.body).kaynak, 'sayfa');
}

// ------------------------------------------------------------------ 6) BOSS ile giriş: kimlik + oturum bitişi
{
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const JWT = `eyJhbGciOiJSUzI1NiJ9.${b64({ name: 'Ayşe Yılmaz', preferred_username: 'AYILMAZ', sub: 'x' })}.IMZA-GIZLI`;
  const iletilen = [];
  const dinleyen = [];
  const kSayfa = {
    location: { origin: 'https://boss.turkcell.com.tr', pathname: '/teknik-havuz', hash: '' }, console, URL, Promise, JSON,
    setTimeout, setInterval: () => 0, atob, decodeURIComponent, localStorage: { length: 0 }, sessionStorage: { length: 0 },
    fetch: async (url) => {
      const u = new URL(url);
      const json = (o, status = 200) => ({ ok: status < 300, status, json: async () => o, clone() { return this; } });
      if (u.pathname.endsWith('/users/me')) return json({ returnCode: 0, content: { firstName: 'Mehmet', lastName: 'Kaya', userCode: 'MKAYA', title: 'Operasyon Uzmanı' } });
      if (u.pathname.endsWith('/yetkisiz')) return json({}, 401);
      return json({ content: [] });
    },
    postMessage(m) { const k = structuredClone(m); if (k.kaynak === 'dehanet-kanca') iletilen.push(k); setTimeout(() => dinleyen.forEach((f) => f({ source: kSayfa, origin: kSayfa.location.origin, data: k })), 0); },
    addEventListener(t, f) { if (t === 'message') dinleyen.push(f); },
    XMLHttpRequest: class { open() {} send() {} setRequestHeader() {} addEventListener() {} },
  };
  vm.createContext(kSayfa);
  vm.runInContext('var window = globalThis;', kSayfa);
  vm.runInContext(oku('maske.js'), kSayfa);
  vm.runInContext(oku('kanca.js'), kSayfa);
  await kSayfa.fetch(`${B}/task-service/api/v1/task/statuses`, { headers: { Authorization: `Bearer ${JWT}` } });
  await bekle(20);
  const k1 = iletilen.find((m) => m.tur === 'kimlik');
  assert.deepEqual([k1.ad, k1.kod], ['Ayşe Yılmaz', 'AYILMAZ'], 'JWT ad alanlarından kimlik');
  await kSayfa.fetch(`${B}/task-service/api/v1/task/statuses`, { headers: { Authorization: `Bearer ${JWT}` } });
  await bekle(10);
  assert.equal(iletilen.filter((m) => m.tur === 'kimlik').length, 1, 'aynı kimlik bir kez');
  await kSayfa.fetch(`${B}/account-service/api/v1/users/me`, { method: 'GET' });
  await bekle(20);
  const k2 = iletilen.filter((m) => m.tur === 'kimlik')[1];
  assert.deepEqual([k2.ad, k2.kod, k2.unvan], ['Mehmet Kaya', 'MKAYA', 'Operasyon Uzmanı'], 'kimlik ucundan');
  const tanilar = iletilen.filter((m) => m.tur === 'tani' && m.adim === 'kimlik_bulundu');
  assert.ok(tanilar.length === 2 && !JSON.stringify(tanilar).includes('Kaya'), 'tanıda yalnız alan adları');
  assert.ok(!JSON.stringify(iletilen).includes('IMZA-GIZLI'), 'jeton hiçbir mesaja girmez');
  // art arda iki 401 → oturum bitti (bir kez); çıkış isteği de
  await kSayfa.fetch(`${B}/task-service/api/v1/yetkisiz`);
  assert.ok(!iletilen.some((m) => m.tur === 'oturum-bitti'), 'tek 401 yetmez');
  await kSayfa.fetch(`${B}/task-service/api/v1/yetkisiz`);
  await kSayfa.fetch(`${B}/task-service/api/v1/yetkisiz`);
  await bekle(10);
  assert.deepEqual(iletilen.filter((m) => m.tur === 'oturum-bitti').map((m) => m.neden), ['401']);

  // arka: giriş sekmesi → istek kimliği; kimlik gelince uygulamaya bir kez; bitiş bildirimi
  const d = { session: {}, local: { eslesme: '1234-5678', port: 8080 } };
  const al = (ad) => ({
    get: async (k) => Object.fromEntries((k || Object.keys(d[ad])).map((x) => [x, structuredClone(d[ad][x])])),
    set: async (o) => Object.assign(d[ad], structuredClone(o)),
  });
  const giden2 = [];
  let dinle = null;
  let guncelle = null;
  const ch = {
    sidePanel: { setPanelBehavior: () => Promise.resolve() },
    runtime: { onMessage: { addListener: (f) => (dinle = f) }, getManifest: () => ({ version: 'test' }) },
    storage: { session: al('session'), local: al('local') },
    tabs: { query: async () => [], sendMessage: async () => {}, onUpdated: { addListener: (f) => (guncelle = f) } },
    alarms: { create: () => {}, onAlarm: { addListener: () => {} } },
  };
  const a2 = { chrome: ch, console, URL, structuredClone, setTimeout, Date, Math, JSON, Promise, __dehanetTest: true,
    fetch: async (url, ayar) => { giden2.push({ url, govde: JSON.parse(ayar.body), kod: ayar.headers['X-Eslesme-Kodu'] }); return { ok: true, status: 200, json: async () => ({}) }; } };
  a2.self = a2;
  a2.importScripts = () => vm.runInContext(oku('eslem.js'), a2);
  vm.createContext(a2);
  vm.runInContext(oku('arka.js'), a2);
  const A2 = a2.__dehanetArka;
  assert.equal(await A2.girisSekmesi(9, 'https://boss.turkcell.com.tr/'), false);
  const ISTEK = 'Abc_def-0123456789xyzXYZ';
  guncelle(9, { url: `http://127.0.0.1:8080/boss-giris/${ISTEK}` }, {});
  await bekle(20);
  assert.equal(d.session.girisIstegi.id, ISTEK);
  assert.equal(giden2.length, 0, 'kimlik bilinmeden bildirilmez');
  dinle({ tur: 'kimlik', ad: 'Ayşe Yılmaz', kod: 'AYILMAZ', unvan: null }, {});
  await bekle(20);
  assert.equal(giden2.length, 1);
  assert.ok(giden2[0].url.endsWith('/api/giris/boss/kimlik') && giden2[0].kod === '1234-5678');
  assert.deepEqual(giden2[0].govde, { istek_id: ISTEK, ad: 'Ayşe Yılmaz', kod: 'AYILMAZ', unvan: null, bayi: null, kaynak: 'sayfa' });
  assert.equal(d.session.girisIstegi, null, 'istek tek kullanımlık');
  dinle({ tur: 'kimlik', ad: 'Ayşe Yılmaz', kod: 'AYILMAZ' }, {});
  await bekle(20);
  assert.equal(giden2.length, 1, 'bekleyen istek yokken kimlik gönderilmez');
  // süresi geçmiş istek: gönderilmez
  d.session.girisIstegi = { id: ISTEK, port: 8080, an: Date.now() - 121000 };
  assert.equal(await A2.kimlikGonder(), false);
  dinle({ tur: 'oturum-bitti', neden: 'cikis' }, {});
  await bekle(20);
  assert.ok(giden2[1].url.endsWith('/api/giris/boss/bitti'));
  assert.deepEqual(giden2[1].govde, { ad: 'Ayşe Yılmaz', kod: 'AYILMAZ', neden: 'cikis' });
  assert.equal(d.session.bossKimlik, null);
  // BOSS sayfa başlığı (dom) birincil: aynı ad büyük harfle gelince oturum bitmez; yedek kaynak dom'u ezmez
  dinle({ tur: 'kimlik', ad: 'Ayşe Yılmaz', kod: 'AYILMAZ' }, {});
  await bekle(20);
  const n0 = giden2.length;
  dinle({ tur: 'kimlik', ad: 'AYŞE YILMAZ', kod: null, unvan: null, bayi: 'DEHANET ECM', kaynak: 'dom' }, {});
  await bekle(20);
  assert.equal(giden2.length, n0, 'aynı kişi (büyük harf): BOSS oturumu bitmez');
  assert.deepEqual([d.session.bossKimlik.kaynak, d.session.bossKimlik.bayi, d.session.bossKimlik.kod], ['dom', 'DEHANET ECM', 'AYILMAZ']);
  dinle({ tur: 'kimlik', ad: 'Başka Biri', kod: 'XX' }, {});
  await bekle(20);
  assert.equal(d.session.bossKimlik.ad, 'AYŞE YILMAZ', 'yedek kaynak dom kimliğini ezmez');
}
// köprü: BOSS başlığındaki "AD SOYAD / BAYİ" metni okunur (yalnız ad + bayi)
{
  const iletilen = [];
  let zamanlayici = null;
  const pencere = { location: { origin: 'https://boss.turkcell.com.tr' }, console, Date, Math,
    setInterval: (f) => { zamanlayici = f; return 1; },
    document: { readyState: 'complete', evaluate: (xp) => ({ singleNodeValue: xp.includes('header/div/div[2]') ? { textContent: '  AHMET EMİRHAN KORKMAZ / DEHANET ECM ' } : null }) } };
  pencere.postMessage = () => {};
  pencere.addEventListener = () => {};
  pencere.chrome = { runtime: { sendMessage: (m) => { iletilen.push(m); return Promise.resolve(); }, onMessage: { addListener: () => {} } },
    storage: { local: { get: async () => ({}) }, onChanged: { addListener: () => {} } } };
  vm.createContext(pencere);
  vm.runInContext('var window = globalThis;', pencere);
  vm.runInContext(oku('kopru.js'), pencere);
  zamanlayici();
  zamanlayici();
  const k = iletilen.filter((m) => m.tur === 'kimlik');
  assert.equal(k.length, 1, 'değişmeyen başlık bir kez');
  assert.deepEqual({ ...k[0] }, { tur: 'kimlik', ad: 'AHMET EMİRHAN KORKMAZ', kod: null, unvan: null, bayi: 'DEHANET ECM', kaynak: 'dom' });
}

// ------------------------------------------------------------------ 9) OneMap bina eşitlemesi (BOSS'tan bağımsız)
const OM_SERVIS = 'https://arcgis.turkcell.com.tr/arcgis/rest/services/ONEMAP/BINA/MapServer/0';
const omOzellik = (i, ek = {}) => ({
  attributes: { OBJECTID: i, ID: 100000 + i + 0.0, LOCATION_ID: `BN-${String(i).padStart(8, '0')}-1`, ENTEGRASYON_ID: `O${50000000 + i}`,
    ADI: `BİNA ${i}`, SITE_ADI: ' ', BLOK_ADI: 'A', KAPI_NO: 51, TURU: 'TEK BİNA', BLOK_TIPI: 'BF', MAHALLE: 'Demirtaş Mh.',
    ILCE: 'Osmangazi', IL: 'Bursa', CADDE: null, SOKAK: 'Deneme Sk.', LAT: '40.2', LON: '29.05', KAT_ADEDI: 4.0,
    KONUT_SAYISI: '8', ISYERI_SAYISI: null, FTTX_HP: 8, PROTOKOL_FIRMA: 'DEHANET ECM', OBEK_ADI: 'BRS-X',
    UAVT_BINA_KODU: 17183339, TEKNOLOJI: null, LAST_EDITED_DATE: 1789768678000, ISDELETED: 0, ...ek },
  geometry: { rings: [[[29.0500001234, 40.2], [29.0501, 40.2], [29.0501, 40.2001], [29.0500001234, 40.2]]] },
});
{
  // 9a) sayfa betiği: jeton yalnız bellekte, yalnız izinli ArcGIS katmanına; mesaja jeton girmez
  const dinleyenler = [];
  const giden = [];
  const istekler = [];
  let arcgisYaniti = { features: [omOzellik(1)], exceededTransferLimit: false };
  const sayfaFetch = async (url, ayar) => {
    istekler.push({ url: String(url), ayar });
    return { ok: true, status: 200, json: async () => arcgisYaniti };
  };
  const omSayfa = { location: { origin: 'https://onemap.turkcell.com.tr' }, console, URLSearchParams, Date, Math, setTimeout, clearTimeout,
    fetch: sayfaFetch, AbortController, XMLHttpRequest: function () {} };
  omSayfa.XMLHttpRequest.prototype.open = function () {};
  omSayfa.XMLHttpRequest.prototype.send = function () {};
  omSayfa.addEventListener = (t, f) => dinleyenler.push(f);
  omSayfa.postMessage = (m) => giden.push(m);
  vm.createContext(omSayfa);
  vm.runInContext('var window = globalThis;', omSayfa);
  vm.runInContext(oku('onemap_sayfa.js'), omSayfa);
  assert.equal(giden[0].tur, 'hazir');
  // sayfanın kendi ArcGIS isteği (jetonlu): değiştirilmeden geçer, jeton bellekte kalır
  await vm.runInContext("fetch('https://arcgis.turkcell.com.tr/arcgis/rest/services/X/MapServer/0/query?f=json&token=GIZLI-JETON-987')", omSayfa);
  omSayfa.__dinleyenler = dinleyenler;
  vm.runInContext("window.__dagit = async (m) => { for (const f of __dinleyenler) await f({ source: window, origin: location.origin, data: m }); };", omSayfa);
  const dagit = (m) => omSayfa.__dagit(m);
  await dagit({ kaynak: 'dehanet-onemap-komut', tur: 'sorgu', istek_id: 'a1', servis: OM_SERVIS, params: { where: '1=1', f: 'json' } });
  const sorguIstegi = istekler[istekler.length - 1];
  assert.equal(sorguIstegi.url, `${OM_SERVIS}/query`);
  assert.equal(sorguIstegi.ayar.credentials, 'include');
  assert.ok(sorguIstegi.ayar.body.includes('token=GIZLI-JETON-987'), 'sayfanın jetonu yalnız ArcGIS sorgusuna eklenir');
  const sonuc = giden.find((m) => m.istek_id === 'a1');
  assert.equal(sonuc.features.length, 1);
  assert.equal(sonuc.jetonVar, true);
  assert.ok(!JSON.stringify(giden).includes('GIZLI-JETON'), 'jeton hiçbir mesaja girmez');
  // izinsiz adres reddedilir (istek atılmaz)
  const n = istekler.length;
  await dagit({ kaynak: 'dehanet-onemap-komut', tur: 'sorgu', istek_id: 'a2', servis: 'https://kotu.example.com/x', params: {} });
  assert.equal(istekler.length, n);
  assert.equal(giden.find((m) => m.istek_id === 'a2').hata, 'adres');
  // ArcGIS jeton hatası → 'yetki' (yeniden denenmez)
  arcgisYaniti = { error: { code: 498, message: 'Invalid token' } };
  await dagit({ kaynak: 'dehanet-onemap-komut', tur: 'sorgu', istek_id: 'a3', servis: OM_SERVIS, params: {} });
  assert.equal(giden.find((m) => m.istek_id === 'a3').hata, 'yetki');
  assert.equal(istekler.length, n + 1);
}
{
  // 9b) köprü: arka plan sorgusu sayfaya, sayfa sonucu aynı mesajın yanıtına
  const dinleyenler = [];
  let arkaDinle = null;
  const iletilen9 = [];
  const kp = { location: { origin: 'https://onemap.turkcell.com.tr' }, console, document: { readyState: 'complete' } };
  kp.addEventListener = (t, f) => dinleyenler.push(f);
  kp.__dinleyenler = dinleyenler;
  kp.__ozellik = omOzellik(2);
  kp.postMessage = (m) => {
    if (m.kaynak === 'dehanet-onemap-komut') kp.__yanitla(m.istek_id);
  };
  kp.chrome = { runtime: { sendMessage: (m) => { iletilen9.push(m); return Promise.resolve(); }, onMessage: { addListener: (f) => (arkaDinle = f) } } };
  vm.createContext(kp);
  vm.runInContext('var window = globalThis;', kp);
  vm.runInContext("window.__yanitla = (id) => { for (const f of __dinleyenler) f({ source: window, origin: location.origin, data: { kaynak: 'dehanet-onemap', tur: 'sonuc', istek_id: id, features: [__ozellik], asim: false } }); };", kp);
  vm.runInContext(oku('onemap_kopru.js'), kp);
  assert.deepEqual(iletilen9.map((m) => m.tur), ['onemap-sayfa']);
  let yanit = null;
  const asenkron = arkaDinle({ tur: 'onemap-sorgu', istek_id: 'k1', servis: OM_SERVIS, params: {} }, {}, (y) => (yanit = y));
  assert.equal(asenkron, true);
  assert.equal(yanit.features[0].attributes.OBJECTID, 2);
  assert.equal(arkaDinle({ tur: 'esitle-baslat' }, {}, () => {}), undefined, 'BOSS mesajlarına karışmaz');
}
{
  // 9c) arka plan: plan → arama + tam tarama (sayfalı, sunucuya her sayfa), sade satır, OneMap'siz durum
  const veri = Array.from({ length: 1200 }, (_, i) => omOzellik(i + 1));
  const sorgular = [];
  const uyg = [];
  const plan = { servis: OM_SERVIS, taban: "IL IN ('Bursa','Yalova') AND PROTOKOL_FIRMA LIKE 'DEHANET%'", sayfa: 500, bekleme_ms: 0,
    alanlar: ['OBJECTID', 'ID', 'LOCATION_ID', 'ENTEGRASYON_ID', 'LAT', 'LON'],
    arama: [{ alan: 'ENTEGRASYON_ID', degerler: ['O53762030'], where: "ENTEGRASYON_ID IN ('O53762030')" }],
    tarama: { tur: 'tam', basla: 0 } };
  let sekmeler = [{ id: 31, url: 'https://onemap.turkcell.com.tr/harita', discarded: false }];
  const depo9 = { session: {}, local: { eslesme: '1234-5678', port: 8080 } };
  const alan9 = (ad) => ({
    get: async (k) => Object.fromEntries((k || Object.keys(depo9[ad])).map((x) => [x, structuredClone(depo9[ad][x])])),
    set: async (o) => Object.assign(depo9[ad], structuredClone(o)),
  });
  let dinle9 = null;
  const ch = {
    runtime: { onMessage: { addListener: (f) => (dinle9 = f) } },
    storage: { session: alan9('session'), local: alan9('local') },
    tabs: {
      query: async (q) => { assert.deepEqual([...q.url], ['https://onemap.turkcell.com.tr/*', 'https://arcgis.turkcell.com.tr/*']); return sekmeler; },
      sendMessage: async (id, m) => {
        assert.equal(id, 31);
        assert.equal(m.tur, 'onemap-sorgu');
        assert.equal(m.servis, OM_SERVIS);
        sorgular.push(m.params);
        const w = m.params.where;
        if (w.startsWith('ENTEGRASYON_ID IN')) return { features: [omOzellik(5000, { ENTEGRASYON_ID: 'O53762030', PROTOKOL_FIRMA: 'BAŞKA' })] };
        const alt = Number((w.match(/OBJECTID > (\d+)/) || [])[1] || 0);
        const n = Number(m.params.resultRecordCount) || 1000;
        const parca = veri.filter((f) => f.attributes.OBJECTID > alt).slice(0, n);
        return { features: parca, asim: parca.length === n };
      },
    },
    alarms: { create: () => {}, onAlarm: { addListener: () => {} } },
  };
  const ark = { chrome: ch, console, URL, structuredClone, setTimeout, clearTimeout, Date, Math, JSON, Promise };
  ark.self = ark;
  ark.fetch = async (url, ayar) => {
    uyg.push({ url, ayar, govde: ayar && ayar.body ? JSON.parse(ayar.body) : null });
    assert.equal(ayar.headers['X-Eslesme-Kodu'], '1234-5678');
    if (url.endsWith('/api/onemap/gorev')) return { ok: true, status: 200, json: async () => plan };
    return { ok: true, status: 200, json: async () => ({ eklenen: 0 }) };
  };
  vm.createContext(ark);
  vm.runInContext(oku('onemap_arka.js'), ark);
  const O = ark.__dehanetOnemap;
  // sade satır: türler sunucunun beklediği gibi (metin alanlar metin, sayılar tam sayı)
  const s1 = O.sadeSatir(omOzellik(7));
  assert.equal(s1.bina_serial, 'BN-00000007-1');
  assert.equal(s1.location_id, 'O50000007');
  assert.equal(s1.om_id, '100007');
  assert.equal(s1.kapi_no, '51');
  assert.equal(s1.uavt, '17183339');
  assert.equal(s1.lat, 40.2);
  assert.equal(s1.kat, 4);
  assert.equal(s1.konut, 8);
  assert.equal(s1.site_adi, null);
  assert.equal(s1.silindi, false);
  assert.deepEqual([...s1.halka[0]], [29.05, 40.2]);
  assert.equal(O.sadeSatir(omOzellik(8, { ISDELETED: 1 })).silindi, true);

  const r = await O.onemapEsitle('test');
  assert.equal(r.durum, 'tamam');
  assert.equal(r.bulunan, 1);
  assert.equal(r.okunan, 1200);
  // arama: geometrili, sunucuya aranan listesiyle
  assert.equal(sorgular[0].where, "ENTEGRASYON_ID IN ('O53762030')");
  assert.equal(sorgular[0].returnGeometry, 'true');
  const binalarIstekleri = uyg.filter((x) => x.url.endsWith('/api/onemap/binalar'));
  assert.deepEqual(binalarIstekleri[0].govde.aranan, { alan: 'ENTEGRASYON_ID', degerler: ['O53762030'] });
  assert.equal(binalarIstekleri[0].govde.binalar[0].firma, 'BAŞKA');
  // tam tarama: OBJECTID anahtarlı, sıralı, sayfalı; geometrisiz; son sayfa "bitti"
  const tarama = sorgular.slice(1);
  assert.equal(tarama.length, 3);
  assert.deepEqual(tarama.map((p) => p.where.match(/OBJECTID > (\d+)/)[1]), ['0', '500', '1000']);
  assert.ok(tarama.every((p) => p.orderByFields === 'OBJECTID ASC' && p.returnGeometry === 'false' && p.where.includes('PROTOKOL_FIRMA')));
  const tamlar = binalarIstekleri.slice(1).map((x) => x.govde);
  assert.deepEqual(tamlar.map((b) => [b.tur, b.binalar.length, b.imlec, b.bitti]), [['tam', 500, 500, false], ['tam', 500, 1000, false], ['tam', 200, 1200, true]]);
  assert.ok(!uyg.some((x) => /token|cookie|GIZLI/i.test(JSON.stringify(x.govde || {}))), 'uygulamaya oturum bilgisi gitmez');
  assert.equal(depo9.session.onemap.durum, 'tamam');
  // OneMap sekmesi yok: sorgu yok, durum "sekme_yok"
  sekmeler = [];
  const once = sorgular.length;
  assert.equal((await O.onemapEsitle('test')).durum, 'sekme_yok');
  assert.equal(sorgular.length, once);
  assert.equal(depo9.session.onemap.durum, 'sekme_yok');
  // OneMap oturumu düştü: hata sunucuya bildirilir, durum "oturum_yok"
  sekmeler = [{ id: 31, url: 'https://onemap.turkcell.com.tr/', discarded: false }];
  ch.tabs.sendMessage = async () => ({ hata: 'yetki', http: 498 });
  uyg.length = 0;
  assert.equal((await O.onemapEsitle('test')).durum, 'oturum_yok');
  const hataBildirimi = uyg.find((x) => x.govde && x.govde.hata);
  assert.ok(hataBildirimi && hataBildirimi.govde.hata.startsWith('yetki') && hataBildirimi.govde.binalar.length === 0);
  assert.equal(dinle9({ tur: 'esitle-simdi' }), undefined, 'BOSS mesajlarını yok sayar');
}

console.log('eklenti: TAMAM · eşleme', Object.keys(E.ALANLAR).length, 'alan · kanca',
  listeIstekleri.length, 'BOSS isteği (sıralı) · arka', gonderilen.gorevler.length, 'görev → uygulama · oturum sızmadı · BOSS ile giriş · OneMap');
