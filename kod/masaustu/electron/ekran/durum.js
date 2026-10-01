'use strict';
/* Kabuğun durum ekranı: açılıyor · ilk kurulum · yedek var · tamam · durdu · başka sunucu · hata */
(function () {
  const $ = (id) => document.getElementById(id);
  const BOLUMLER = { bekleme: ['hazirlaniyor', 'kuruluyor'], ilk: ['ilk'], yedekVar: ['yedek-var'], tamam: ['kurulum-tamam'], durdu: ['durdu'], harici: ['harici'], calisiyor: ['calisiyor'], hata: ['hata'] };
  let beklemeBasi = 0;
  let sabirZamanlayici = null;
  let sonCikti = '';

  function ciz(d) {
    if (!d) return;
    for (const [id, ekranlar] of Object.entries(BOLUMLER)) $(id).classList.toggle('gizli', !ekranlar.includes(d.ekran));
    $('baslik').textContent = d.baslik || '';
    const bekliyor = d.ekran === 'hazirlaniyor' || d.ekran === 'kuruluyor';
    $('ayrinti').textContent = bekliyor ? '' : d.ayrinti || '';
    $('canli').textContent = bekliyor ? d.ayrinti || '' : '';

    const rozet = { hata: ['hata', 'Dikkat'], harici: ['uyari', 'Bilgi'], durdu: ['uyari', 'Durduruldu'], 'kurulum-tamam': ['tamam', 'Tamam'], calisiyor: ['tamam', 'Çalışıyor'] }[d.ekran];
    $('rozet').innerHTML = '';
    if (rozet) {
      const r = document.createElement('span');
      r.className = `rozet ${rozet[0]}`;
      r.textContent = rozet[1];
      r.style.marginTop = '18px';
      $('rozet').appendChild(r);
    }

    $('veriYolu').classList.toggle('gizli', d.ekran !== 'ilk');
    if (d.ekran === 'ilk') {
      $('ayrinti').textContent = 'Dehanet Saha bu bilgisayarda ilk kez açılıyor. Verileriniz bu klasörde tutulur; güncellemeler ona dokunmaz:';
      $('veriYolu').textContent = d.veri;
    }
    if (d.ekran === 'yedek-var') {
      const n = (d.ekstra && d.ekstra.yedekSayisi) || 0;
      $('ayrinti').textContent = `Bu veri klasöründe veritabanı yok ama ${n} yedek var. Yeni ve boş bir veritabanı kurulmadı; önce yedeği geri yükleyin.`;
    }
    if (d.ekran === 'kurulum-tamam') {
      sonCikti = (d.ekstra && d.ekstra.cikti) || '';
      $('cikti').textContent = sonCikti;
    }
    if (d.ekran === 'hata') {
      const satirlar = (d.satirlar || []).join('\n');
      $('satirlar').textContent = satirlar;
      $('ayrintiKutusu').classList.toggle('gizli', !satirlar);
      $('ayrintiKutusu').open = !!satirlar && /GÜNCELLEME|Traceback|Error/i.test(satirlar);
    }

    if (bekliyor) {
      if (!beklemeBasi) {
        beklemeBasi = Date.now();
        clearTimeout(sabirZamanlayici);
        sabirZamanlayici = setTimeout(() => $('sabir').classList.remove('gizli'), 12000);
      }
    } else {
      beklemeBasi = 0;
      clearTimeout(sabirZamanlayici);
      $('sabir').classList.add('gizli');
    }

    const parcalar = [`Sürüm ${d.surum}`, `Port ${d.port}`, d.ag ? 'ofis ağı' : 'yalnız bu bilgisayar'];
    if (d.adresler && d.adresler[0] && d.ekran === 'calisiyor') parcalar.push(`Telefon: ${d.adresler[0]}`);
    $('altNot').textContent = parcalar.join('  ·  ');
    $('altYol').textContent = d.ekran === 'ilk' ? '' : `Veri klasörü: ${d.veri}`;
    document.title = d.ekran === 'calisiyor' ? 'Dehanet Saha' : `Dehanet Saha — ${d.baslik || ''}`;
  }

  document.addEventListener('click', async (e) => {
    const hedef = e.target.closest('[data-eylem]');
    if (hedef) {
      hedef.disabled = true;
      try {
        await window.dehanet.eylem(hedef.dataset.eylem);
      } finally {
        hedef.disabled = false;
      }
    }
  });
  $('kopyala').addEventListener('click', () => window.dehanet.eylem('kopyala', sonCikti));
  $('bosKurulum').addEventListener('click', () => {
    if (window.confirm('Yedekler yerinde kalır ama yeni ve BOŞ bir veritabanı kurulur. Emin misiniz?')) window.dehanet.eylem('bosKurulum');
  });

  window.dehanet.dinle(ciz);
  window.dehanet.durum().then(ciz);
})();
