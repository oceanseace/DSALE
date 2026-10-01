/*
 * OneMap bina çekme aracı — Saha Sistemi (Dehanet EÇM)
 * ======================================================
 *
 * NE YAPAR: Tur raporuyla gelen YENİ binaların konumunu (bina poligonu, LAT/LON,
 * mahalle, kat, daire) Turkcell OneMap'ten çeker ve bilgisayarınıza
 * "onemap_yeni.json" olarak indirir. Bu dosyayı Saha Sistemi'nde
 * Yönetim → Veri → "OneMap dosyasını yükle" ile yüklersiniz.
 *
 * NASIL KULLANILIR (docs/SAHA_KULLANIM.md §12):
 *   1. Saha Sistemi'nden "bekleyen_idler.txt" dosyasını indirin
 *      (Yönetim → Veri → "Konum bekleyen binalar" → "Kimlik listesini indir").
 *   2. OneMap'in açık olduğu tarayıcıda (Brave, OneMap oturumunuz açık) şu adresi açın:
 *        https://arcgis.turkcell.com.tr/arcgis/rest/services/ONEMAP/BINA/MapServer/0
 *   3. F12 → "Console" (Konsol) sekmesi. Bu dosyanın TAMAMINI kopyalayıp yapıştırın, Enter.
 *      (Tarayıcı "yapıştırmaya izin ver" isterse "allow pasting" yazıp Enter'a basın.)
 *   4. Sağ üstte açılan kutudan "bekleyen_idler.txt" dosyasını seçin.
 *   5. İş bitince "onemap_yeni.json" kendiliğinden iner. Kutuda kaç binanın
 *      bulunduğu, kaçının bulunamadığı yazar.
 *
 * GÜVENLİK: Araç YALNIZ OneMap sunucusuna sorgu atar ve sonucu SİZİN
 * bilgisayarınıza indirir. Başka hiçbir yere veri göndermez, şifre sormaz,
 * oturum bilgisine dokunmaz.
 *
 * Kimlik eşlemesi: satış raporundaki "Tellcordia ID" = OneMap "ID";
 * "Bina Serial Number" = OneMap "LOCATION_ID". Dosyada rakamdan oluşan satırlar
 * ID ile, "BN..." ile başlayanlar LOCATION_ID ile aranır.
 */
(function () {
  'use strict';

  var SERVIS = 'https://arcgis.turkcell.com.tr/arcgis/rest/services/ONEMAP/BINA/MapServer/0';
  var PARTI = 100;          // tek sorguda en çok kaç kimlik
  var DENEME = 3;           // hata olursa her parti kaç kez denenir

  var eski = document.getElementById('saha-onemap-araci');
  if (eski) eski.remove();

  var kutu = document.createElement('div');
  kutu.id = 'saha-onemap-araci';
  kutu.style.cssText = 'position:fixed;top:16px;right:16px;z-index:2147483647;width:360px;' +
    'background:#fff;color:#111;border:2px solid #1f6feb;border-radius:12px;padding:16px;' +
    'font:14px/1.45 system-ui,Segoe UI,Arial,sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.25)';
  kutu.innerHTML =
    '<div style="font-weight:700;font-size:16px;margin-bottom:6px">OneMap bina çekme aracı</div>' +
    '<div style="margin-bottom:10px;color:#444">Saha Sistemi\'nden indirdiğiniz <b>bekleyen_idler.txt</b> ' +
    'dosyasını seçin.</div>' +
    '<input type="file" accept=".txt,.csv" style="width:100%;margin-bottom:10px">' +
    '<div data-durum style="min-height:42px;color:#0b4"></div>' +
    '<div style="height:8px;background:#eee;border-radius:4px;overflow:hidden;margin:8px 0">' +
    '<div data-cubuk style="height:100%;width:0;background:#1f6feb"></div></div>' +
    '<button data-kapat style="margin-top:6px;padding:6px 12px;border-radius:8px;border:1px solid #bbb;' +
    'background:#f6f6f6;cursor:pointer">Kapat</button>';
  document.body.appendChild(kutu);

  var durumAlani = kutu.querySelector('[data-durum]');
  var cubuk = kutu.querySelector('[data-cubuk]');
  kutu.querySelector('[data-kapat]').onclick = function () { kutu.remove(); };

  function durum(metin, renk) {
    durumAlani.textContent = metin;
    durumAlani.style.color = renk || '#0b4';
    console.log('[OneMap aracı] ' + metin);
  }

  function bekle(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function sorguMetni(kimlikler, sayisal) {
    if (sayisal) return 'ID IN (' + kimlikler.join(',') + ')';
    return "LOCATION_ID IN ('" + kimlikler.map(function (k) { return k.replace(/'/g, "''"); })
      .join("','") + "')";
  }

  async function sorgula(where) {
    var govde = new URLSearchParams({
      where: where, outFields: '*', returnGeometry: 'true', outSR: '4326', f: 'json'
    });
    var sonHata = null;
    for (var i = 0; i < DENEME; i++) {
      try {
        var yanit = await fetch(SERVIS + '/query', {
          method: 'POST', body: govde, credentials: 'include',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        if (!yanit.ok) throw new Error('HTTP ' + yanit.status);
        var veri = await yanit.json();
        if (veri.error) throw new Error((veri.error.message || 'OneMap hatası') + ' (' + (veri.error.code || '') + ')');
        return veri.features || [];
      } catch (e) {
        sonHata = e;
        await bekle(1500 * (i + 1));
      }
    }
    throw sonHata;
  }

  function indir(nesne, ad) {
    var blob = new Blob([JSON.stringify(nesne)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = ad;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }

  kutu.querySelector('input[type=file]').onchange = async function (olay) {
    var dosya = olay.target.files && olay.target.files[0];
    if (!dosya) return;
    var metin = await dosya.text();
    var hepsi = Array.from(new Set(metin.split(/[\s,;]+/).map(function (s) { return s.trim(); })
      .filter(Boolean)));
    var sayisal = hepsi.filter(function (k) { return /^\d+$/.test(k); });
    var serial = hepsi.filter(function (k) { return !/^\d+$/.test(k); });
    if (!hepsi.length) { durum('Dosyada kimlik bulunamadı.', '#c00'); return; }

    var partiler = [];
    for (var i = 0; i < sayisal.length; i += PARTI) partiler.push([sayisal.slice(i, i + PARTI), true]);
    for (var j = 0; j < serial.length; j += PARTI) partiler.push([serial.slice(j, j + PARTI), false]);

    var ozellikler = [];
    var hatalar = [];
    for (var p = 0; p < partiler.length; p++) {
      durum((p + 1) + ' / ' + partiler.length + ' sorgu · ' + ozellikler.length + ' bina bulundu');
      cubuk.style.width = Math.round(100 * p / partiler.length) + '%';
      try {
        var sonuc = await sorgula(sorguMetni(partiler[p][0], partiler[p][1]));
        sonuc.forEach(function (f) {
          ozellikler.push({ a: f.attributes || {}, g: (f.geometry && f.geometry.rings) || [] });
        });
      } catch (e) {
        hatalar.push(String(e && e.message || e));
      }
    }
    cubuk.style.width = '100%';

    var bulunan = new Set();
    ozellikler.forEach(function (f) {
      if (f.a.ID != null) bulunan.add(String(f.a.ID));
      if (f.a.LOCATION_ID) bulunan.add(String(f.a.LOCATION_ID));
    });
    var bulunamayan = hepsi.filter(function (k) { return !bulunan.has(k); });

    indir({
      source: SERVIS,
      outSR: 4326,
      extracted_at: new Date().toISOString(),
      n: ozellikler.length,
      istenen: hepsi.length,
      bulunamayan: bulunamayan,
      hatalar: hatalar,
      features: ozellikler
    }, 'onemap_yeni.json');

    var mesaj = hepsi.length + ' kimlikten ' + (hepsi.length - bulunamayan.length) +
      ' bina bulundu. onemap_yeni.json indirildi.';
    if (bulunamayan.length) mesaj += ' Bulunamayan: ' + bulunamayan.length + ' (OneMap\'e henüz girilmemiş olabilir).';
    if (hatalar.length) mesaj += ' ' + hatalar.length + ' sorgu hata verdi: ' + hatalar[0];
    durum(mesaj, hatalar.length ? '#c60' : '#0b4');
  };

  durum('Hazır. Dosyayı seçin.', '#1f6feb');
})();
