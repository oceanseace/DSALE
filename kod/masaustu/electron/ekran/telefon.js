'use strict';
(function () {
  const $ = (id) => document.getElementById(id);
  let adres = '';

  async function yenile() {
    const t = await window.dehanet.telefon();
    if (!t) return;
    const bolum = !t.ag ? 'kapali' : !t.calisiyor ? 'durmus' : t.adresler.length ? 'hazir' : 'agYok';
    for (const id of ['hazir', 'kapali', 'durmus', 'agYok']) $(id).classList.toggle('gizli', id !== bolum);
    if (bolum === 'hazir') {
      adres = t.adresler[0];
      $('adres').textContent = adres;
      $('qr').innerHTML = t.qr || '';
      $('digerleri').textContent = t.adresler.length > 1
        ? `Bu bilgisayarın başka ağ adresleri de var: ${t.adresler.slice(1).join(' · ')}. Telefon hangisini açabiliyorsa o geçerlidir.`
        : '';
    }
  }

  $('kopyala').addEventListener('click', async () => {
    await window.dehanet.eylem('kopyala', adres);
    $('kopyala').textContent = 'Kopyalandı';
    setTimeout(() => ($('kopyala').textContent = 'Adresi kopyala'), 1600);
  });
  $('agiAc').addEventListener('click', () => window.dehanet.eylem('agiAc'));
  $('baslat').addEventListener('click', () => window.dehanet.eylem('baslat'));
  window.dehanet.dinle(() => yenile());
  yenile();
})();
