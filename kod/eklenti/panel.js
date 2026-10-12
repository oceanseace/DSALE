// Yan panel: bağlantı durumu, son eşitleme, açık iş sayısı, son eşitlemenin farkı ("+3 yeni · 2 değişti · 1 kapandı"),
// ayrıntı önden okuma ilerlemesi, eşleme kodu, şimdi eşitle, kayıt modu, alan haritası. İş listesi gösterilmez
// (eklentide müşteri verisi tutulmaz). Büyük sayı SON BAŞARILI eşitlemenindir ("2.814 açık iş · son eşitleme 13:02");
// eşitleme sürerken yalnız küçük "denetleniyor…" görünür, sayı hiç 0/— olmaz.

const $ = (s) => document.querySelector(s);
const sayi = (n) => Number(n || 0).toLocaleString('tr-TR');
const saat = (ms) => new Date(ms).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
const ESITLEME_ASIMI_MS = 4 * 60 * 1000;
// eşitleme sürüyor mu (eski sürümün 'okunuyor' durumu da sayılır; asılı kalmış işaret 4 dk sonra düşer)
const suruyor = (e) => (e.suruyor || e.durum === 'okunuyor') && Date.now() - (e.basla || 0) < ESITLEME_ASIMI_MS;
const kac = (ms) => {
  const sn = Math.max(0, Math.round((Date.now() - ms) / 1000));
  return sn < 60 ? 'az önce' : sn < 3600 ? `${Math.round(sn / 60)} dk önce` : `${Math.round(sn / 3600)} sa önce`;
};

// Durum → panelin tek cümlesi ve (gerekirse) yapılacak adım
function ozet(e, ayar, hazir) {
  if (!ayar.eslesme) return { sinif: 'uyari', metin: 'Kurulum bitmedi', adim: 'Eşleme kodunu yazın', ayrinti: 'Kodu Turkcell uygulamasında Operasyon ▸ BOSS bağlantısı ekranında görürsünüz.' };
  switch (e.durum) {
    case 'boss_kapali': return { sinif: 'uyari', metin: 'BOSS açık değil', adim: 'BOSS\'u açın', ayrinti: 'Bu tarayıcıda BOSS\'a girin ve Teknik Havuz ekranını açık bırakın.' };
    case 'istek_yok': return { sinif: 'uyari', metin: 'Teknik Havuz bekleniyor', adim: 'BOSS\'ta Teknik Havuz\'u bir kez açın', ayrinti: 'Liste ekrana gelince eklenti gerisini kendisi yapar.' };
    case 'sayfa_yenile': return { sinif: 'uyari', metin: 'BOSS sekmesine yeniden bağlanılıyor…', ayrinti: 'Eklenti kendisi yeniden dener; bir şey yapmanız gerekmez.' };
    case 'kod_yanlis': return { sinif: 'hata', metin: 'Eşleme kodu yanlış', adim: 'Kodu yeniden yazın', ayrinti: 'Uygulamadaki BOSS bağlantısı ekranında görünen kodu yazın.' };
    case 'sunucu_yok': return { sinif: 'hata', metin: 'Turkcell uygulaması kapalı', adim: 'Turkcell uygulamasını açın', ayrinti: `Bu bilgisayarda uygulama çalışmıyor ya da port farklı (şu an ${ayar.port}).` };
    case 'sunucu_mesgul': return { sinif: 'uyari', metin: 'Uygulama meşgul; birazdan yeniden denenecek' };
    case 'sunucu_hata': return { sinif: 'hata', metin: `Uygulama kabul etmedi: ${e.mesaj || ''}` };
    case 'okuma_hata': return { sinif: 'hata', metin: `BOSS listesi okunamadı (${e.hata || '?'})`, adim: 'BOSS\'ta oturumunuz açık mı?', ayrinti: 'Gerekirse BOSS\'a yeniden girip Teknik Havuz\'u açın.' };
    case 'kod_yok': return { sinif: 'uyari', metin: 'Eşleme kodu yok' };
    default: break;
  }
  if (e.sonEsitleme) {
    const eski = Date.now() - e.sonEsitleme > 10 * 60 * 1000;
    return { sinif: eski ? 'uyari' : 'canli', metin: `${sayi(e.acik)} açık iş · son eşitleme ${saat(e.sonEsitleme)}` };
  }
  if (suruyor(e)) return { sinif: 'canli', metin: 'BOSS ilk kez okunuyor…' };
  if (!hazir) return { sinif: 'uyari', metin: 'Teknik Havuz bekleniyor', adim: 'BOSS\'ta Teknik Havuz\'u bir kez açın', ayrinti: 'Liste ekrana gelince eklenti gerisini kendisi yapar.' };
  return { sinif: '', metin: 'Bekleniyor…' };
}

function kart(deger, etiket) {
  return `<div class="kart"><div class="deger">${deger}</div><div class="etiket">${etiket}</div></div>`;
}
// son eşitlemenin farkı: "+3 yeni · 2 değişti · 1 kapandı" (bilinmiyorsa boş)
function farkMetni(e) {
  if (!e.sonEsitleme || (e.yeni == null && e.degisen == null && e.kapanan == null)) return '';
  const p = [`+${sayi(e.yeni)} yeni`, `${sayi(e.degisen)} değişti`, `${sayi(e.kapanan)} kapandı`];
  return `Son eşitleme: ${p.join(' · ')}`;
}

// ayrıntı önden okuma: "İş ayrıntıları: 1.234 / 2.814 hazır · ~2 sa kaldı" (bittiyse kısa)
function detayMetni(e) {
  if (e.detayToplam == null || !e.detayToplam) return '';
  const t = Number(e.detayTamam || 0);
  if (t >= e.detayToplam) return `İş ayrıntıları hazır (${sayi(e.detayToplam)})`;
  const dk = Number(e.detayKalanDk || 0);
  const kalan = dk >= 90 ? `~${Math.round(dk / 60)} sa kaldı` : dk > 0 ? `~${dk} dk kaldı` : '';
  return `İş ayrıntıları okunuyor: ${sayi(t)} / ${sayi(e.detayToplam)}${kalan ? ` · ${kalan}` : ''}`;
}

async function ciz() {
  const s = await chrome.storage.session.get(['esitleme', 'uclar', 'hazir', 'kancaEski']);
  const l = await chrome.storage.local.get(['eslesme', 'port', 'kayitModu', 'kayitlar', 'alanHaritasi']);
  const ayar = { eslesme: l.eslesme || '', port: Number(l.port) || 8080 };
  const e = s.esitleme || {};
  const o = ozet(e, ayar, s.hazir);
  // Eklenti güncellendi ama BOSS sekmesinde eski parça çalışıyor (okuma sürer; yeni özellikler F5'ten sonra).
  if (!o.adim && Object.keys(s.kancaEski || {}).length) {
    o.adim = 'BOSS sekmesini bir kez yenileyin (F5)';
    o.ayrinti = 'Eklenti güncellendi. Okuma sürüyor; yeni özellikler sayfa yenilenince çalışır.';
  }
  $('#durum').textContent = o.metin;
  $('#durum').className = `durum ${o.sinif}`;
  // eşitleme sürerken küçük ikinci satır; büyük sayı son başarılı eşitlemede kalır
  $('#denetim').textContent = suruyor(e) && e.sonEsitleme ? 'denetleniyor…' : '';
  $('#adim').hidden = !o.adim;
  if (o.adim) {
    $('#adimMetin').textContent = o.adim;
    $('#adimAyrinti').textContent = o.ayrinti || '';
  }
  $('#kodBolum').hidden = !!ayar.eslesme && e.durum !== 'kod_yanlis';
  if (document.activeElement !== $('#kod') && !$('#kod').value) $('#kod').value = ayar.eslesme;
  if (document.activeElement !== $('#port')) $('#port').value = ayar.port;
  $('#simdi').disabled = suruyor(e);

  $('#kartlar').innerHTML = [
    kart(e.sonEsitleme ? sayi(e.acik) : '—', 'BOSS\'ta açık iş'),
    kart(e.sonEsitleme ? saat(e.sonEsitleme) : '—', `son eşitleme${e.sonEsitleme ? ` · ${kac(e.sonEsitleme)}` : ''}`),
  ].join('');

  $('#fark').textContent = farkMetni(e);
  $('#detay').textContent = detayMetni(e);

  $('#kayitModu').checked = !!l.kayitModu;
  $('#kayitlar').textContent = (l.kayitlar || []).length ? JSON.stringify(l.kayitlar, null, 1) : 'Kayıt yok.';
  const uclar = Object.values(s.uclar || {}).map((u) => ({ uc: u.ad, yontem: u.yontem, istek: u.govdeYapi, yanit: u.yapi }));
  $('#harita').textContent = JSON.stringify({ alanlar: l.alanHaritasi || {}, uclar }, null, 1);
}

const kodSade = (v) => {
  const r = String(v || '').replace(/\D/g, '').slice(0, 8);
  return r.length > 4 ? `${r.slice(0, 4)}-${r.slice(4)}` : r;
};
$('#kod').addEventListener('input', (e) => { e.target.value = kodSade(e.target.value); });
$('#kodKaydet').addEventListener('click', async () => {
  const kod = kodSade($('#kod').value);
  if (kod.length !== 9) {
    $('#kod').focus();
    return;
  }
  await chrome.storage.local.set({ eslesme: kod });
  await chrome.storage.session.set({ esitleme: {} });
  chrome.runtime.sendMessage({ tur: 'esitle-simdi' }).catch(() => {});
  ciz();
});
$('#portKaydet').addEventListener('click', async () => {
  const p = Number($('#port').value);
  if (p > 0 && p < 65536) await chrome.storage.local.set({ port: p });
  ciz();
});
$('#simdi').addEventListener('click', async () => {
  $('#simdi').disabled = true;
  await chrome.runtime.sendMessage({ tur: 'esitle-simdi' }).catch(() => {});
  ciz();
});
$('#kayitModu').addEventListener('change', (e) => chrome.storage.local.set({ kayitModu: e.target.checked }));
const kopyala = (dugme, kaynak) => async () => {
  await navigator.clipboard.writeText($(kaynak).textContent);
  const eski = $(dugme).textContent;
  $(dugme).textContent = 'Kopyalandı ✓';
  setTimeout(() => ($(dugme).textContent = eski), 1800);
};
$('#kopyala').addEventListener('click', kopyala('#kopyala', '#harita'));
$('#kayitKopyala').addEventListener('click', kopyala('#kayitKopyala', '#kayitlar'));

chrome.storage.onChanged.addListener(() => ciz());
setInterval(ciz, 15000);
ciz();
