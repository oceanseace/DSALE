'use strict';
(function () {
  const $ = (id) => document.getElementById(id);
  let ilk = null;
  let veri = '';

  async function yukle() {
    ilk = await window.dehanet.ayarlar();
    if (!ilk) return;
    veri = ilk.veriKlasoru;
    $(ilk.ag ? 'agAcik' : 'agKapali').checked = true;
    $('port').value = ilk.port;
    $('veri').textContent = veri;
    $('otomatik').checked = !!ilk.otomatikBaslat;
    $('gecici').classList.toggle('gizli', !ilk.gecici);
  }

  $('degistir').addEventListener('click', async () => {
    const secilen = await window.dehanet.eylem('veriKlasoruSec');
    if (secilen) {
      veri = secilen;
      $('veri').textContent = veri;
    }
  });
  $('varsayilan').addEventListener('click', () => {
    veri = ilk.varsayilanVeri;
    $('veri').textContent = veri;
  });
  $('ac').addEventListener('click', () => window.dehanet.eylem('veriKlasorunuAc'));
  $('vazgec').addEventListener('click', () => window.dehanet.eylem('pencereyiKapat'));
  $('kaydet').addEventListener('click', async () => {
    const yeni = { ag: $('agAcik').checked, port: Number($('port').value), veriKlasoru: veri, otomatikBaslat: $('otomatik').checked };
    const onemli = yeni.ag !== ilk.ag || yeni.port !== ilk.port || veri !== ilk.veriKlasoru;
    if (onemli && !window.confirm('Sunucu yeni ayarla yeniden başlatılacak. Açık telefonlar birkaç saniye bağlantı kaybeder. Devam edilsin mi?')) return;
    $('kaydet').disabled = true;
    $('mesaj').className = 'mesaj';
    $('mesaj').textContent = onemli ? 'Kaydediliyor, sunucu yeniden başlatılıyor…' : 'Kaydediliyor…';
    const r = await window.dehanet.eylem('ayarKaydet', yeni);
    $('kaydet').disabled = false;
    if (!r || !r.ok) {
      $('mesaj').className = 'mesaj hata';
      $('mesaj').textContent = (r && r.hata) || 'Kaydedilemedi.';
      return;
    }
    window.dehanet.eylem('pencereyiKapat');
  });
  yukle();
})();
