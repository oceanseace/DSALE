// Kişisel veri maskesi (TEK yer): tanı/kayıt örneklerinde kişisel alanın değeri "•••(uzunluk)" olur; yapı görünür kalır.
// Kullananlar: kanca.js (BOSS sayfasında, MAIN world'de kanca.js'ten ÖNCE yüklenir: manifest + arka.js betikleriYukle)
// ve test.mjs. Sunucudaki karşılığı operasyon/v2/boss_ham.py KISISEL; ikisi aynı örnek adlarla sınanır
// (test.mjs "maske" bölümü ve operasyon/testler/test_v2_tasks_tablosu.py KISISEL_ORNEKLER).
(function (kok) {
  // Anahtar adı bunlardan birini içeriyorsa değer (dizi ya da nesne olsa da) tamamen gizlenir.
  const KISISEL = /password|passwd|sifre|otp|token|secret|user.?code|name|ad.?soyad|surname|phone|tel|gsm|msisdn|mobile|address|adres|customer|subscriber|contact|musteri|abone|tckn|identity|kimlik|birth|dogum|description|aciklama|note|mail/i;
  // Anahtarı ne olursa olsun ≥ 10 haneli sayı (telefon, TCKN, abone no) gizlenir; 9 haneli Task No görünür kalır.
  const UZUN_SAYI = /^\+?\d{10,}$/;                     // boşluklar atılarak bakılır (tarih "2026-10-01" değildir)
  const EN_DERIN = 5;
  const EN_COK_OGE = 5;

  const gizle = (v) => {
    if (v == null) return v;
    if (Array.isArray(v)) return `•••(${v.length} öğe)`;
    if (typeof v === 'object') return '•••(nesne)';
    return `•••(${String(v).length})`;
  };
  const sade = (v) => ((typeof v === 'string' || typeof v === 'number') && UZUN_SAYI.test(String(v).replace(/\s/g, '')) ? gizle(v) : v);

  function maskele(o, d = 0) {
    if (o == null) return o;
    if (typeof o !== 'object') return sade(o);
    if (d >= EN_DERIN) return Array.isArray(o) ? 'dizi' : 'nesne';     // derinlik sınırında değer hiç dönmez
    if (Array.isArray(o)) return o.slice(0, EN_COK_OGE).map((x) => maskele(x, d + 1));
    const s = {};
    for (const k of Object.keys(o)) s[k] = KISISEL.test(k) ? gizle(o[k]) : maskele(o[k], d + 1);
    return s;
  }

  kok.DehanetMaske = Object.freeze({ KISISEL, maskele });
})(typeof self !== 'undefined' ? self : globalThis);
