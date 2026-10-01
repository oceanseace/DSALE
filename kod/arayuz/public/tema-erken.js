/* Görünüm (Sistem · Açık · Koyu) İLK BOYAMADAN önce uygulanır: koyu seçen kişi
   açılışta beyaz bir parlama görmez. Ayrı dosya, çünkü sunucunun güvenlik
   politikası satır içi betiğe izin vermez (script-src 'self'). Anahtar
   src/ortak/tema.ts ile aynıdır. */
(function () {
  try {
    var g = localStorage.getItem('saha.gorunum');
    if (g === 'koyu' || g === 'acik') {
      document.documentElement.setAttribute('data-theme', g === 'koyu' ? 'dark' : 'light');
      var renk = g === 'koyu' ? '#0F1319' : '#EFF1F5';
      var metalar = document.querySelectorAll('meta[name="theme-color"]');
      for (var i = 0; i < metalar.length; i++) metalar[i].setAttribute('content', renk);
    }
  } catch (e) {
    /* depolama kapalı: sistem tercihi geçerli */
  }
})();
