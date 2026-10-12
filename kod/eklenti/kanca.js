// BOSS sayfasının İÇİNDE çalışır (MAIN world).
//  1) Dinleme: sayfanın kendi veri isteklerinin YANITLARINI eklentinin köprüsüne iletir.
//  2) Eşitleme: sayfanın "task/list" isteğinden YALNIZ adres yolu + başlıklar alınır (YALNIZ BU KAPANIŞIN
//     BELLEĞİNDE). Gövde KANONİK kurulur (kanonikGovde): searchTerm boş, kullanıcı süzgeçleri atılır, durum süzgeci
//     eşitlemenin kendisi (8 açık durum; kapalılar ayrı geçiş). İlk yakalamada şablon (yol, sıralama, durum değer
//     biçimi) saklanır; sonraki yakalamalar yalnız başlıkları tazeler — kullanıcının BOSS'ta yaptığı arama/süzgeç
//     ya da sayfa değiştirmesi eşitlemeye sızmaz. Başlıklar (oturum bilgisi) hiçbir mesaja, depoya, günlüğe girmez.
//  3) Kayıt modu: kullanıcı BOSS'ta elle bir işlem yapınca yalnız yöntem + yol + gövdenin YAPISI (değer yok).
//  4) Yazma yürütücüsü (yaz): sunucunun verdiği isteği (yalnız YAZILABILIR uçlar) sayfanın başlıklarıyla aynı köke
//     SINIRLI HAVUZLA (aynı anda en çok `paralel`, varsayılan 6, üst sınır 10; KANCA_SURUMU 10) POST eder; 429/502/
//     503/504'te üstel geri çekilmeyle yeniden dener, her 5xx/429 bütün havuzu bir süre yavaşlatır; yazma sürerken
//     eşitleme (task/list taraması) bekler — YALNIZ istek "yaz: true" ve ("dogrulandi: true" ya da yöneticinin tek iş
//     denemesi "deneme: true") ise. Aksi hâlde hiçbir istek göndermez, yalnız "önizleme" der. Sonuç: HTTP kodu +
//     BOSS'un returnCode/returnMessage'ı (yanıt gövdesinin geri kalanı iletilmez).
//  5) Askı nedeni kataloğu (neden-oku): sunucu işe göre (kategori + ürün kodu) ister; yalnız o kalıptaki GET.
//  6) Ayrıntı önden okuma (detay-onden): sunucunun verdiği işlerin (önce kullanıcının açacağı işler) 9 sekme ucu,
//     yalnız GET; bir işin sekmeleri aynı anda EN ÇOK 3 istekle, işler arasında kısa ara (ONDEN_ARA_MS). Eşitleme,
//     telefon okuması ya da BOSS'a yazma sürerken tek istekle sürer; kullanıcının açtığı iş (detay) araya girince
//     bekler. Her iş okununca hemen iletilir (detay-onden-parca). Oturum düşerse (401/403) durur.
//     Kullanıcının açtığı işin ayrıntısı (detay): 9 sekme aynı anda (BOSS'un kendi iş sayfası da öyle açar).
//     Başlıklar: sayfanın KENDİ yazma isteklerinin (appointment-service / task-service, GET olmayan) başlıkları
//     servis başına bellekte tutulur ve o servise yazarken onlar kullanılır (yoksa liste isteğininkiler); Content-Type
//     her zaman tek ve application/json. 2xx olmayan yanıtın metni (maskeli, kısaltılmış) "yanit_metni" ile iletilir.
//  7) BOSS ile giriş (KANCA_SURUMU 6): oturum açan BOSS kullanıcısının KİMLİĞİ (yalnız ad, kullanıcı kodu, unvan)
//     sayfanın kendi isteklerinden bulunur — oturum jetonunun (JWT) ad alanları, kimlik ucunun yanıtı (ör. /users/me)
//     ya da sayfa deposundaki kullanıcı nesnesi — ve "kimlik" mesajıyla iletilir; jetonun kendisi, şifre ya da kod
//     HİÇBİR mesaja girmez. Tanıya yalnız kaynağı ve alan ADLARI yazılır (değersiz). BOSS oturumu biterse
//     (çıkış isteği, giriş sayfasına dönüş ya da BOSS uçlarında art arda 401) "oturum-bitti" iletilir.
//  8) Ekip GPS konumu (KANCA_SURUMU 11): sayfa BOSS "GPS Takip" ucunu (GET, /user/location/TECH ya da adında gps)
//     çağırınca yol + başlıklar bellekte tutulur, sayfanın kendi yanıtı "konum-yanit" ile iletilir (en çok 20 sn'de
//     bir). "konum-oku" komutu aynı ucu sayfanın başlıklarıyla bir kez GET eder → "konum-bitti" (veri ya da hata);
//     uç hiç görülmediyse liste başlıkları biliniyorsa varsayılan yol, bilinmiyorsa hata "konum_yok". BOSS'a yazma
//     ya da geri çekilme sürerken okumaz. Yanıtın yalnız YAPISI bir kez tanıya ("konum_yapisi", değersiz).
// Yükleyen: manifest (MAIN world) ya da arka.js betikleriYukle; maske.js ondan ÖNCE yüklenir. Sayfada bir kez kurulur.
// Sürüm: eklenti yenilenince sayfada ESKİ sürüm kanca varsa yenisi kurulmaz (fetch/XHR iki kez sarılmasın); yalnız
// "durum" sorusuna `eski: true` der → kopru.js → arka.js → panel "BOSS sekmesini bir kez yenileyin" uyarısı.
(() => {
  const KANCA_SURUMU = 11;                // kanca.js davranışı değişince artırın (yeni dinleyici, yeni komut)
  if (window.__dehanetKanca === KANCA_SURUMU) return;
  if (window.__dehanetKanca) {
    window.addEventListener('message', (olay) => {
      const m = olay.data;
      if (olay.source === window && m && m.kaynak === 'dehanet-komut' && m.tur === 'durum') {
        window.postMessage({ kaynak: 'dehanet-kanca', tur: 'kanca-durum', eski: true }, location.origin);
      }
    });
    return;
  }
  window.__dehanetKanca = KANCA_SURUMU;

  const ILGILI = /\/boss-gateway-service\/(task-service|appointment-service|account-service\/api\/v1\/teams)/;
  const LISTE = /\/task-service\/api\/v\d+\/task\/list(\?|$)/;
  const SAYFA_BOYU = 200;
  const BEKLE_MS = 700;
  const EN_COK_SAYFA = 400;

  let sonDurumUcu = null;       // sayfanın kendi kullandığı durum listesi ucu (yol)
  let sonListe = null;          // { url, yontem, basliklar, govde } — yalnız bellekte; url/govde KANONİK şablondur
  let sablon = null;            // ilk yakalanan temiz şablon: { yol, yontem, sirala, durumOrnegi }
  const yazmaBasliklari = {};   // servis (appointment-service | task-service) → sayfanın son yazma isteği başlıkları
  let kayitModu = false;
  let esitleniyor = false;

  const ilet = (o) => {
    try {
      window.postMessage({ kaynak: 'dehanet-kanca', ...o }, location.origin);
    } catch (e) {
      /* aktarılamadı (çok büyük ya da kopyalanamaz) — sayfayı etkilemez */
    }
  };
  // tanı satırı (değer yok: adım, yol, kısa ileti) → arka plan → Turkcell sunucusu
  const tani = (adim, yol, ileti, ek) => ilet({ tur: 'tani', adim, yol: yol || null, ileti: ileti ? String(ileti).slice(0, 200) : null, ek: ek || null });
  const govdeCoz = (b) => {
    if (!b || typeof b !== 'string') return null;
    try { return JSON.parse(b); } catch (e) { return null; }
  };
  const yapi = (o, d = 0) => {
    if (Array.isArray(o)) return o.length ? [`dizi(${o.length})`, yapi(o[0], d + 1)] : ['dizi(0)'];
    if (o && typeof o === 'object') {
      if (d > 4) return 'nesne';
      const s = {};
      for (const k of Object.keys(o)) s[k] = o[k] && typeof o[k] === 'object' ? yapi(o[k], d + 1) : typeof o[k];
      return s;
    }
    return typeof o;
  };
  const yolSade = (url) => {
    try {
      return new URL(url, location.origin).pathname.replace(/\/\d{4,}(?=\/|$)/g, '/#');
    } catch (e) { return ''; }
  };
  const basliklariAl = (h) => {
    const o = {};
    if (!h) return o;
    if (typeof h.forEach === 'function' && !Array.isArray(h)) h.forEach((v, k) => { o[k] = v; });
    else if (Array.isArray(h)) h.forEach(([k, v]) => { o[k] = v; });
    else Object.assign(o, h);
    return o;
  };
  // Eşitleme gövdesinde kalabilecek anahtarlar (geri kalan her şey kullanıcı süzgecidir, atılır).
  const KANONIK_ANAHTAR = /^(searchTerm|taskStatus|runQuery|skipTotalCount)$/;
  const DURUM_ANAHTARI = 'taskStatus';
  const kanonikGovde = () => JSON.stringify({ searchTerm: '', [DURUM_ANAHTARI]: [], runQuery: true, skipTotalCount: false });
  const kanonikUrl = () => {
    const u = new URL(sablon.yol, location.origin);
    if (sablon.sirala) u.searchParams.set('sort', sablon.sirala);
    return u.href;
  };
  const SERVIS = /\/boss-gateway-service\/(appointment-service|task-service)\//;
  // Sayfanın kendi yazma isteğinin (GET değil, liste değil) başlıkları: aynı servise yazarken bunlar kullanılır.
  const yazmaBasligiTut = (url, yontem, basliklar) => {
    try {
      const m = SERVIS.exec(String(url || ''));
      if (!m || /^GET$/i.test(String(yontem || 'GET')) || LISTE.test(url) || /\/count(\?|$)/.test(url)) return;
      const b = basliklariAl(basliklar);
      if (!Object.keys(b).length) return;
      const ilk = !yazmaBasliklari[m[1]];
      yazmaBasliklari[m[1]] = b;
      if (ilk) tani('yazma_basliklari', yolSade(url), m[1], { adlar: Object.keys(b).map((k) => k.toLowerCase()).sort() });
    } catch (e) { /* sessiz */ }
  };
  const listeyiTut = (url, yontem, basliklar, govde) => {
    const u = new URL(String(url), location.origin);
    const g = govdeCoz(typeof govde === 'string' ? govde : null);
    const ilk = !sablon;
    if (ilk) {
      const durum = g && Array.isArray(g[DURUM_ANAHTARI]) ? g[DURUM_ANAHTARI] : [];
      sablon = { yol: u.pathname, yontem: (yontem || 'POST').toUpperCase(), sirala: u.searchParams.get('sort'),
        durumOrnegi: durum.length ? durum[0] : null };
    } else if (sablon.durumOrnegi == null && g && Array.isArray(g[DURUM_ANAHTARI]) && g[DURUM_ANAHTARI].length) {
      sablon.durumOrnegi = g[DURUM_ANAHTARI][0];          // yalnız değer BİÇİMİ öğrenilir (kod mu kimlik mi)
    }
    // yalnız başlıklar tazelenir; adres ve gövde her seferinde şablondan
    sonListe = { url: kanonikUrl(), yontem: sablon.yontem, basliklar, govde: kanonikGovde() };
    const atilan = g && typeof g === 'object' && !Array.isArray(g) ? Object.keys(g).filter((k) => !KANONIK_ANAHTAR.test(k)) : [];
    tani('liste_yakalandi', yolSade(url), sonListe.yontem, { sorgu: [...u.searchParams.keys()], govde: yapi(g), ilk, atilan });
    ilet({ tur: 'liste-yakalandi' });
  };
  // görülen her BOSS ucu bir kez tanıya yazılır (yalnız yöntem + yol); durum listesi ucu hatırlanır
  const gorulen = new Set();
  const goruldu = (url, yontem) => {
    const yol = yolSade(url);
    if (/status/i.test(yol) && !/list(\?|$)/.test(yol) && String(yontem).toUpperCase() === 'GET') sonDurumUcu = new URL(url, location.origin).pathname;
    const a = `${String(yontem).toUpperCase()} ${yol}`;
    if (!gorulen.has(a)) { gorulen.add(a); tani('uc_goruldu', yol, String(yontem).toUpperCase()); }
  };
  // Ekip GPS ucu (BOSS "GPS Takip / teknik" sayfası): yol + başlıklar YALNIZ bu kapanışın belleğinde
  const KONUM = /\/user\/location\/TECH|gps/i;
  const KONUM_VARSAYILAN = '/boss-gateway-service/account-service/api/v1/user/location/TECH';
  const KONUM_YANIT_ARA_MS = 20000;
  let konumUcu = null;          // { yol (adres yolu + sorgu), basliklar }
  let konumYapisiGitti = false;
  let konumYanitSon = 0;
  const konumMu = (url, yontem) => /boss-gateway-service/.test(String(url || '')) && KONUM.test(String(url || '')) &&
    String(yontem || 'GET').toUpperCase() === 'GET' && !GIZLI_UC.test(String(url || ''));
  const konumTut = (url, basliklar) => {
    try {
      const u = new URL(String(url), location.origin);
      if (u.origin !== location.origin) return;
      const ilk = !konumUcu;
      konumUcu = { yol: u.pathname + u.search, basliklar: basliklariAl(basliklar) };
      if (ilk) tani('konum_ucu', yolSade(url), 'GET', { sorgu: [...u.searchParams.keys()] });
    } catch (e) { /* sessiz */ }
  };
  const konumYapisi = (url, durum, veri) => {
    if (konumYapisiGitti) return;
    konumYapisiGitti = true;
    tani('konum_yapisi', yolSade(url), String(durum), { yapi: yapi(veri) });
  };
  // sayfanın kendi GPS yanıtı → arka plan (sayfa sık yokluyorsa en çok KONUM_YANIT_ARA_MS'de bir)
  const konumYaniti = (url, durum, veri) => {
    try {
      konumYapisi(url, durum, veri);
      if (Date.now() - konumYanitSon < KONUM_YANIT_ARA_MS) return;
      konumYanitSon = Date.now();
      ilet({ tur: 'konum-yanit', yol: yolHam(url), veri });
    } catch (e) { /* sessiz */ }
  };
  // Değer örneği (Kayıt modu açıkken): kişisel alanlar gizlenir (maske.js, TEK yer); maske yüklenmemişse hiç değer gitmez.
  const maskele = (window.DehanetMaske && window.DehanetMaske.maskele) || (() => null);
  // Giriş/çıkış/OTP/oturum uçları HİÇBİR koşulda kaydedilmez (şifre ve kod taşır).
  const GIZLI_UC = /authentication-service|\/login|\/logout|\/otp|token|password|sifre/i;
  const kaydet = (url, yontem, govde) => {
    if (GIZLI_UC.test(url)) return;
    if (!kayitModu || !/^(POST|PUT|PATCH|DELETE)$/i.test(yontem || '')) return;
    if (LISTE.test(url) || /\/count(\?|$)/.test(url)) return;      // okuma istekleri kayda girmez
    ilet({ tur: 'kayit', yontem: String(yontem).toUpperCase(), yol: yolSade(url), govdeYapi: govde ? yapi(govdeCoz(govde)) : null });
    tani('deger_ornegi', yolSade(url), String(yontem).toUpperCase(), { govde: maskele(govdeCoz(govde)) });
  };
  // Yazma isteğinin sonucu ve neden/sebep listeleri — ikisi de YALNIZ kayıt modunda; neden listesi işe özgü adreste
  // (UUID ya da uzun sayısal kimlik) hiç gönderilmez. Askı nedeni kataloğu (aski_nedenleri) değer süzülerek her zaman.
  const ISE_OZGU = /[0-9a-f]{8}-[0-9a-f]{4}-|\/\d{4,}(\/|\?|$)|[?&][a-z_]*id=/i;
  const yanitTani = (url, yontem, durum, veri) => {
    if (GIZLI_UC.test(url)) return;
    try {
      const y = String(yontem || 'GET').toUpperCase();
      if (kayitModu && y !== 'GET' && !LISTE.test(url)) {
        tani('yazma_sonucu', yolSade(url), `${y} ${durum}`, { yanit: maskele(veri && typeof veri === 'object' && !Array.isArray(veri) ? Object.fromEntries(Object.entries(veri).filter(([k]) => !/content|data/i.test(k))) : null) });
      }
      if (kayitModu && y === 'GET' && /reason|neden|sebep|suspend/i.test(url) && !ISE_OZGU.test(url)) {
        tani('neden_listesi', yolSade(url), String(durum), { veri: maskele(veri) });
      } else if (kayitModu && y === 'GET' && /reason/i.test(url) && !TASK_KIMLIKLI.test(url)) {
        // üst neden kimlikli neden uçları (alt nedeni yükleyen GET'i bulmak için): yol + yalnız kimlik/ad alanları
        tani('neden_listesi', yolHam(url), String(durum), { veri: nedenSade(veri) });
      }
      if (y === 'GET' && ASKI_NEDEN.test(url) && /reason|neden|sebep/i.test(url) && !ISE_OZGU.test(url)) {
        tani('aski_nedenleri', yolHam(url), String(durum), { veri: nedenSade(veri) });
      } else if (y === 'GET' && ALT_NEDEN.test(url) && !TASK_KIMLIKLI.test(url)) {
        // alt neden listesi (üst neden kimliği adreste GUID olarak geçebilir; görev kimlikli adres hiç alınmaz)
        tani('aski_alt_nedenleri', yolHam(url), String(durum), { veri: nedenSade(veri) });
      }
    } catch (e) { /* sessiz */ }
  };
  // Askı nedeni kataloğu (işe özgü değil; kişisel veri yok): yalnız kimlik/ad alanları ve alt neden dizileri kalır.
  const ASKI_NEDEN = /suspend|[/_-]aski/i;            // "taskId" içindeki "askI" eşleşmesin
  const ALT_NEDEN = /sub.?reason/i;
  const TASK_KIMLIKLI = /task-id|[?&][a-z_]*task[a-z_]*=|\/task\/[0-9a-f]{8}-/i;
  const yolHam = (url) => { try { return new URL(url, location.origin).pathname; } catch (e) { return ''; } };
  const nedenSade = (o, d = 0) => {
    if (Array.isArray(o)) return o.slice(0, 300).map((x) => nedenSade(x, d + 1));
    if (o && typeof o === 'object' && d < 6) {
      const s = {};
      for (const k of Object.keys(o)) {
        const v = o[k];
        if (v && typeof v === 'object') s[k] = nedenSade(v, d + 1);
        else if (/^(id|code|key|value|name|description|label|text|reason.?(id|name|desc)|sub.?reason.?(id|name|desc)|suspend.?(sub.?)?reason.?id)$/i.test(k)) s[k] = typeof v === 'string' ? v.slice(0, 200) : v;
      }
      return s;
    }
    return null;
  };

  // ---------------------------------------------------------------- BOSS kullanıcısı (BOSS ile giriş)
  const KIMLIK_UC = /(\/me(\?|\/|$)|current-?user|user-?info|userinfo|\/profile|whoami|\/users?\/(me|current|info|detail))/i;
  const SIFRE_UC = /\/login|\/otp|token|password|sifre|\/logout/i;
  const AD_ALANI = /^(full_?name|display_?name|name_?surname|ad_?soyad|user_?full_?name|employee_?name|name)$/i;
  const ILK_AD = /^(first_?name|given_?name|firstname|ad|isim)$/i;
  const SOYAD = /^(last_?name|sur_?name|family_?name|soyad|soyisim)$/i;
  const KOD_ALANI = /^(user_?code|user_?name|username|preferred_username|sicil(_?no)?|employee_?(code|no)|personel_?no|login_?name)$/i;
  const UNVAN_ALANI = /^(title|job_?title|unvan|position_?name|role_?name)$/i;
  const KIMLIK_ICI = /^(user|content|data|result|profile|account|kullanici|employee|payload)$/i;
  const adGecerli = (v) => typeof v === 'string' && /^[\p{L}][\p{L} .'-]{2,79}$/u.test(v.trim()) && v.trim().split(/\s+/).length >= 2;
  function kimlikCikar(o, d = 0) {
    if (!o || typeof o !== 'object' || Array.isArray(o) || d > 3) return null;
    const anahtarlar = Object.keys(o);
    const bul = (re, kosul) => anahtarlar.find((k) => re.test(k) && kosul(o[k]));
    let adA = bul(AD_ALANI, adGecerli);
    let ad = adA ? o[adA].trim() : null;
    const alanlar = [];
    if (ad) alanlar.push(adA);
    else {
      const i = bul(ILK_AD, (v) => typeof v === 'string' && v.trim());
      const s = bul(SOYAD, (v) => typeof v === 'string' && v.trim());
      if (i && s && adGecerli(`${o[i].trim()} ${o[s].trim()}`)) { ad = `${o[i].trim()} ${o[s].trim()}`; alanlar.push(i, s); }
    }
    if (!ad) {
      for (const k of anahtarlar) {
        if (KIMLIK_ICI.test(k)) { const x = kimlikCikar(o[k], d + 1); if (x) return x; }
      }
      return null;
    }
    const kodA = bul(KOD_ALANI, (v) => (typeof v === 'string' && v.trim() && v.length <= 60) || typeof v === 'number');
    const unvanA = bul(UNVAN_ALANI, (v) => typeof v === 'string' && v.trim() && v.length <= 80);
    if (kodA) alanlar.push(kodA);
    if (unvanA) alanlar.push(unvanA);
    return { ad: ad.replace(/\s+/g, ' '), kod: kodA ? String(o[kodA]).trim() : null, unvan: unvanA ? o[unvanA].trim() : null, alanlar };
  }
  // JWT yükü (yalnız sayfanın belleğinde çözülür; jetonun kendisi hiçbir yere gitmez)
  function jwtYuku(j) {
    try {
      const p = String(j || '').replace(/^Bearer\s+/i, '').split('.');
      if (p.length !== 3) return null;
      const b = p[1].replace(/-/g, '+').replace(/_/g, '/');
      const ham = atob(b + '='.repeat((4 - (b.length % 4)) % 4));
      return JSON.parse(decodeURIComponent(Array.from(ham, (c) => `%${c.charCodeAt(0).toString(16).padStart(2, '0')}`).join('')));
    } catch (e) { return null; }
  }
  let sonKimlik = null;
  let sonJetonIzi = null;
  const kimlikBildir = (k, kaynak, yol) => {
    if (!k) return;
    const anahtar = `${k.ad}|${k.kod || ''}`;
    if (anahtar === sonKimlik) return;
    sonKimlik = anahtar;
    oturumDustu = false;
    ilet({ tur: 'kimlik', ad: k.ad, kod: k.kod, unvan: k.unvan });
    tani('kimlik_bulundu', yol || null, kaynak, { alanlar: k.alanlar });
  };
  const jetonGor = (deger) => {
    try {
      if (!/^Bearer\s+[\w-]+\.[\w-]+\.[\w-]+$/i.test(String(deger || '').trim())) return;
      const iz = String(deger).slice(-24);
      if (iz === sonJetonIzi) return;
      sonJetonIzi = iz;
      kimlikBildir(kimlikCikar(jwtYuku(deger)), 'jwt');
    } catch (e) { /* sessiz */ }
  };
  const basliktaJeton = (h) => {
    const o = basliklariAl(h);
    for (const k of Object.keys(o)) if (/^authorization$/i.test(k)) jetonGor(o[k]);
  };
  const depoyuTara = () => {
    for (const ad of ['localStorage', 'sessionStorage']) {
      try {
        const d = window[ad];
        if (!d) continue;
        for (let i = 0; i < d.length; i++) {
          const a = d.key(i);
          if (!/user|kullanici|profile|account|auth|current/i.test(a || '')) continue;
          const v = d.getItem(a);
          if (!v || v.length > 20000) continue;
          let k = null;
          if (/^[\w-]+\.[\w-]+\.[\w-]+$/.test(v.trim())) k = kimlikCikar(jwtYuku(v));
          else if (/^[{[]/.test(v.trim())) { try { k = kimlikCikar(JSON.parse(v)); } catch (e) { k = null; } }
          if (k) { kimlikBildir(k, `depo:${ad}`); return; }
        }
      } catch (e) { /* depoya erişim yok */ }
    }
  };
  // BOSS oturumunun bitişi: çıkış isteği, giriş sayfası ya da BOSS uçlarında art arda 401 (2xx sayacı sıfırlar)
  let ust401 = 0;
  let oturumDustu = false;
  const oturumBitti = (neden) => {
    if (oturumDustu) return;
    oturumDustu = true;
    sonKimlik = null;
    sonJetonIzi = null;
    ilet({ tur: 'oturum-bitti', neden });
    tani('oturum_bitti', null, neden);
  };
  const durumGor = (url, durum) => {
    if (!/boss-gateway-service/.test(url || '')) return;
    if (durum === 401) { if (++ust401 >= 2) oturumBitti('401'); }
    else if (durum >= 200 && durum < 300) ust401 = 0;
  };
  const GIRIS_SAYFASI = /(^|[/#])(login|signin|sign-in|giris|auth)([/?#]|$)/i;
  let sonAdres = null;
  const adresDenetle = () => {
    try {
      const a = `${location.pathname || ''}${location.hash || ''}`;
      if (a === sonAdres) return;
      sonAdres = a;
      if (GIRIS_SAYFASI.test(a)) oturumBitti('giris_sayfasi');
    } catch (e) { /* sessiz */ }
  };
  try {
    if (typeof location.pathname === 'string') {
      adresDenetle();
      setInterval(adresDenetle, 2000);
      setTimeout(depoyuTara, 1500);
      setInterval(depoyuTara, 30000);
    }
  } catch (e) { /* sessiz */ }

  // ---------------------------------------------------------------- fetch
  const asilFetch = window.fetch;
  window.fetch = async function (girdi, ayar) {
    const url = typeof girdi === 'string' ? girdi : (girdi && girdi.url) || '';
    const yontem = (ayar && ayar.method) || (girdi && girdi.method) || 'GET';
    try {
      if (/boss-gateway-service/.test(url)) {
        goruldu(url, yontem);
        basliktaJeton((ayar && ayar.headers) || (girdi && girdi.headers));
        kaydet(url, yontem, ayar && ayar.body);
        yazmaBasligiTut(url, yontem, (ayar && ayar.headers) || (girdi && girdi.headers));
        if (LISTE.test(url)) listeyiTut(url, yontem, basliklariAl((ayar && ayar.headers) || (girdi && girdi.headers)), ayar && ayar.body);
        if (konumMu(url, yontem)) konumTut(url, (ayar && ayar.headers) || (girdi && girdi.headers));
      }
    } catch (e) { /* sessiz */ }
    const yanit = await asilFetch.apply(this, arguments);
    try {
      if (/\/logout/i.test(url)) oturumBitti('cikis');
      durumGor(url, yanit.status);
      if (String(yontem).toUpperCase() === 'GET' && yanit.ok && KIMLIK_UC.test(url) && !SIFRE_UC.test(url)) {
        yanit.clone().json().then((j) => kimlikBildir(kimlikCikar(j), 'uc', yolSade(url))).catch(() => {});
      }
      if (/boss-gateway-service/.test(url)) yanit.clone().json().then((j) => yanitTani(url, yontem, yanit.status, j)).catch(() => {});
      if (yanit.ok && konumMu(url, yontem)) yanit.clone().json().then((j) => konumYaniti(url, yanit.status, j)).catch(() => {});
      if (ILGILI.test(url)) {
        yanit.clone().json().then((j) => ilet({ tur: 'yanit', yol: url, yontem, govde: govdeCoz(ayar && ayar.body), veri: j })).catch(() => {});
      }
    } catch (e) { /* sessiz */ }
    return yanit;
  };

  // ---------------------------------------------------------------- XMLHttpRequest
  const X = XMLHttpRequest.prototype;
  const asilAc = X.open;
  const asilGonder = X.send;
  const asilBaslik = X.setRequestHeader;
  X.open = function (yontem, url) {
    this.__dhYontem = yontem;
    this.__dhUrl = String(url || '');
    this.__dhBasliklar = {};
    return asilAc.apply(this, arguments);
  };
  X.setRequestHeader = function (ad, deger) {
    try { if (this.__dhBasliklar) this.__dhBasliklar[ad] = deger; } catch (e) { /* sessiz */ }
    try { if (/^authorization$/i.test(ad) && /boss-gateway-service/.test(this.__dhUrl || '')) jetonGor(deger); } catch (e) { /* sessiz */ }
    return asilBaslik.apply(this, arguments);
  };
  X.send = function (govde) {
    const url = this.__dhUrl || '';
    try {
      if (/boss-gateway-service/.test(url)) {
        goruldu(url, this.__dhYontem);
        kaydet(url, this.__dhYontem, govde);
        yazmaBasligiTut(url, this.__dhYontem, { ...(this.__dhBasliklar || {}) });
        if (LISTE.test(url)) listeyiTut(url, this.__dhYontem, { ...(this.__dhBasliklar || {}) }, govde);
        if (konumMu(url, this.__dhYontem)) konumTut(url, { ...(this.__dhBasliklar || {}) });
      }
    } catch (e) { /* sessiz */ }
    if (/\/logout/i.test(url)) this.addEventListener('load', () => oturumBitti('cikis'));
    if (/boss-gateway-service/.test(url)) {
      const ben = this;
      this.addEventListener('load', () => {
        try {
          durumGor(url, ben.status);
          if (String(ben.__dhYontem || 'GET').toUpperCase() === 'GET' && ben.status === 200 && KIMLIK_UC.test(url) && !SIFRE_UC.test(url)) {
            kimlikBildir(kimlikCikar(JSON.parse(ben.responseText)), 'uc', yolSade(url));
          }
        } catch (e) { /* JSON değil */ }
      });
      this.addEventListener('load', () => { try { yanitTani(url, ben.__dhYontem, ben.status, JSON.parse(ben.responseText)); } catch (e) { /* JSON değil */ } });
      if (konumMu(url, this.__dhYontem)) {
        this.addEventListener('load', () => {
          try { if (ben.status >= 200 && ben.status < 300) konumYaniti(url, ben.status, JSON.parse(ben.responseText)); } catch (e) { /* JSON değil */ }
        });
      }
    }
    if (ILGILI.test(url)) {
      const self = this;
      const g = govdeCoz(govde);
      this.addEventListener('load', () => {
        try {
          if (self.status >= 200 && self.status < 300) ilet({ tur: 'yanit', yol: url, yontem: self.__dhYontem, govde: g, veri: JSON.parse(self.responseText) });
        } catch (e) { /* JSON değil */ }
      });
    }
    return asilGonder.apply(this, arguments);
  };

  // ---------------------------------------------------------------- eşitleme
  const bekle = (ms) => new Promise((r) => setTimeout(r, ms));
  const sade = (s) => String(s || '').toLocaleUpperCase('tr-TR')
    .replace(/[ÇĞİIÖŞÜÂÎÛ]/g, (c) => ({ Ç: 'C', Ğ: 'G', İ: 'I', I: 'I', Ö: 'O', Ş: 'S', Ü: 'U', Â: 'A', Î: 'I', Û: 'U' }[c]))
    .replace(/[^A-Z0-9]+/g, ' ').trim();

  function nesneDizisi(o, d = 0) {
    if (Array.isArray(o)) return o.length && typeof o[0] === 'object' ? o : (o.length === 0 ? o : null);
    if (o && typeof o === 'object' && d < 3) {
      for (const k of Object.keys(o)) {
        const x = nesneDizisi(o[k], d + 1);
        if (x && x.length) return x;
      }
      for (const k of Object.keys(o)) if (Array.isArray(o[k])) return o[k];
    }
    return null;
  }
  function toplamBul(o, d = 0) {
    if (!o || typeof o !== 'object' || Array.isArray(o) || d > 2) return null;
    for (const k of Object.keys(o)) if (/^(total.?elements|total.?count|total.?records?|total|count|toplam)$/i.test(k) && typeof o[k] === 'number') return o[k];
    for (const k of Object.keys(o)) { const t = toplamBul(o[k], d + 1); if (t != null) return t; }
    return null;
  }
  // gövdede adı kalıba uyan anahtarın (iç içe) sahibi + anahtar
  function anahtarBul(o, kalip, d = 0) {
    if (!o || typeof o !== 'object' || Array.isArray(o) || d > 3) return null;
    for (const k of Object.keys(o)) if (kalip.test(k) && (o[k] == null || typeof o[k] !== 'object' || Array.isArray(o[k]))) return { sahip: o, k };
    for (const k of Object.keys(o)) { const x = anahtarBul(o[k], kalip, d + 1); if (x) return x; }
    return null;
  }

  async function istek(url, yontem, govde) {
    const y = await asilFetch.call(window, url, {
      method: yontem, headers: sonListe.basliklar, body: yontem === 'GET' ? undefined : govde, credentials: 'include',
    });
    durumGor(url, y.status);
    if (!y.ok) throw new Error(`http_${y.status} ${new URL(url, location.origin).pathname}`);
    return y.json();
  }

  async function durumDegerleri(adlar, ornek) {
    // task/statuses → ad eşleşen kayıtların, mevcut filtre değeriyle AYNI türdeki değeri (kimlik / kod / ad)
    const kokUrl = new URL(sonListe.url, location.origin);
    // sayfanın kendi gördüğü durum listesi ucu önce; yoksa olası yollar sırayla
    const adaylar = [sonDurumUcu, '/boss-gateway-service/task-service/api/v2/task/statuses',
      '/boss-gateway-service/task-service/api/v1/task/statuses', '/boss-gateway-service/task-service/api/v1/task/status/list'].filter(Boolean);
    let liste = [];
    for (const yol of adaylar) {
      try { liste = nesneDizisi(await istek(new URL(yol, kokUrl.origin).href, 'GET')) || []; if (liste.length) break; } catch (e) { tani('durum_ucu_yok', yol, String(e.message)); }
    }
    const istenen = new Set(adlar.map(sade));
    const secilen = liste.filter((s) => s && typeof s === 'object' &&
      Object.values(s).some((v) => typeof v === 'string' && istenen.has(sade(v))));
    const ornekDeger = Array.isArray(ornek) ? ornek[0] : ornek;
    return secilen.map((s) => {
      const id = s.id ?? s.statusId ?? s.value;
      const kod = s.code ?? s.statusCode ?? s.key;
      const ad = s.name ?? s.description ?? s.label;
      if (typeof ornekDeger === 'number') return typeof id === 'number' ? id : Number(id);
      if (typeof ornekDeger === 'string') {
        if (liste.some((x) => x && x.code === ornekDeger)) return kod;
        if (liste.some((x) => x && (x.name === ornekDeger || x.description === ornekDeger))) return ad;
        return String(id ?? kod ?? ad);
      }
      return id ?? kod ?? ad;
    }).filter((v) => v != null && v !== '');
  }

  async function tara(istek_id, durumlar, enCokSayfa, etiket) {
    // gövde ya da adres üzerinden sayfa + boy + durum süzgeci kurulur
    const govde0 = govdeCoz(sonListe.govde);
    const url0 = new URL(sonListe.url, location.origin);
    let durumAyarlandi = false;
    if (durumlar && govde0) {
      const d = anahtarBul(govde0, /^(task.?)?status(es|.?ids?|.?list|.?codes?)?$/i);
      if (d) {
        const ornek = (sablon && sablon.durumOrnegi != null) ? sablon.durumOrnegi : (Array.isArray(d.sahip[d.k]) && d.sahip[d.k].length ? d.sahip[d.k] : 'OPEN');
        const deger = await durumDegerleri(durumlar, ornek);
        if (deger.length) {
          d.sahip[d.k] = Array.isArray(d.sahip[d.k]) || deger.length > 1 ? deger : deger[0];
          durumAyarlandi = true;
        }
      }
    }
    if (durumlar && !durumAyarlandi && etiket === 'kapali') return { okunan: 0, tam: false, durumAyarlandi };
    if (govde0 && 'skipTotalCount' in govde0) govde0.skipTotalCount = false;
    const sayfaG = govde0 && anahtarBul(govde0, /^(page|page.?no|page.?number|page.?index|pagenum)$/i);
    const boyG = govde0 && anahtarBul(govde0, /^(size|page.?size|limit|rows?.?per.?page)$/i);
    const sorguSayfa = ['page', 'pageNo', 'pageNumber'].find((k) => url0.searchParams.has(k)) || (sayfaG ? null : 'page');
    const sorguBoy = ['size', 'pageSize', 'limit'].find((k) => url0.searchParams.has(k)) || (boyG ? null : 'size');
    const ilkSayfa = 0;                                   // Spring biçimi: sayfa 0'dan başlar
    let okunan = 0;
    let toplam = null;
    let boy = SAYFA_BOYU;
    for (let i = 0; i < enCokSayfa; i++) {
      const url = new URL(url0.href);
      if (sorguSayfa) url.searchParams.set(sorguSayfa, String(ilkSayfa + i));
      if (sorguBoy) url.searchParams.set(sorguBoy, String(boy));
      if (sayfaG) sayfaG.sahip[sayfaG.k] = ilkSayfa + i;
      if (boyG) boyG.sahip[boyG.k] = boy;
      const yanit = await istek(url.href, sonListe.yontem, govde0 ? JSON.stringify(govde0) : sonListe.govde);
      const dizi = nesneDizisi(yanit) || [];
      if (toplam == null) toplam = toplamBul(yanit);
      tani('sayfa', url.pathname, `${etiket} s${i} n${dizi.length} toplam ${toplam}`, { sorgu: [...url.searchParams.keys()], anahtarlar: yanit && typeof yanit === 'object' && !Array.isArray(yanit) ? Object.keys(yanit) : 'dizi', ilk: dizi[0] ? String(dizi[0].taskNo || dizi[0].id || '').slice(-4) : null });
      if (i === 0 && dizi[0] && typeof dizi[0] === 'object') {
        // DEĞERSİZ alan yapısı + sayısal alanların yalnız HANE SAYISI (Task No alanını doğrulamak için)
        const haneler = {};
        const gez = (o, onek, d) => {
          if (!o || typeof o !== 'object' || d > 3) return;
          for (const k of Object.keys(o)) {
            const v = o[k]; const y = onek ? `${onek}.${k}` : k;
            if (v && typeof v === 'object' && !Array.isArray(v)) gez(v, y, d + 1);
            else if ((typeof v === 'number' && Number.isInteger(v)) || (typeof v === 'string' && /^\d{4,}$/.test(v.trim()))) haneler[y] = String(v).trim().length;
          }
        };
        gez(dizi[0], '', 0);
        tani('gorev_yapisi', url.pathname, etiket, { yapi: yapi(dizi[0]), haneler });
      }
      if (i === 0 && dizi.length && dizi.length < boy && toplam != null && toplam > dizi.length) boy = dizi.length;   // sunucu boyu kısıtladı
      okunan += dizi.length;
      ilet({ tur: 'esitle-parca', istek_id, etiket, gorevler: dizi });
      if (!dizi.length || dizi.length < boy || (toplam != null && okunan >= toplam)) {
        // son sayfa kısa geldiyse liste bitti (eşitleme sürerken toplam bir iki iş oynayabilir)
        return { okunan, toplam, tam: toplam == null || okunan >= toplam || dizi.length < boy, durumAyarlandi };
      }
      await bekle(BEKLE_MS);
    }
    return { okunan, toplam, tam: false, durumAyarlandi };
  }

  // ---------------------------------------------------------------- BOSS ekipleri (teknisyen listesi)
  const EKIP_UCU = '/boss-gateway-service/account-service/api/v1/teams/type/TECH';
  async function ekipleriOku() {
    try {
      const veri = await istek(new URL(EKIP_UCU, location.origin).href, 'GET');
      const dizi = nesneDizisi(veri) || [];
      return dizi.filter((e) => e && typeof e === 'object').map((e) => ({
        ad: e.name ?? e.teamName ?? e.description ?? null,
        id: e.id ?? e.teamId ?? e.code ?? null,
        aktif: e.active ?? e.isActive ?? e.enabled ?? (e.status ? !/pasif|inactive|passive/i.test(String(e.status.name || e.status)) : null),
      })).filter((e) => e.ad);
    } catch (e) {
      tani('ekip_hata', EKIP_UCU, String((e && e.message) || 'hata'));
      return null;
    }
  }

  // ---------------------------------------------------------------- iş ayrıntısı (isteğe bağlı, yalnız GET)
  const TASK = '/boss-gateway-service/task-service/api/v1/task';
  const DETAY_UCLARI = [
    ['aciklama', (u) => `${TASK}/${u}/descriptions`],
    ['urunler', (u) => `${TASK}/task-id/${u}/detail/product/list`],
    ['iletisim', (u) => `${TASK}/task-id/${u}/detail/customer/list`],
    ['adres_teyidi', (u) => `${TASK}/task-id/${u}/detail/customer/workflow/list`],
    ['fotograflar', (u) => `${TASK}/task-id/${u}/detail/content/list`],
    ['cihaz', (u) => `${TASK}/task-id/${u}/detail/device/list`],
    ['tarihce', (u) => `${TASK}/task-id/${u}/detail/history/list`],
    ['ariza_nedeni', (u) => `${TASK}/task-id/${u}/detail/trouble-reason`],
    ['evraklar', (u) => `${TASK}/task-id/${u}/detail/campaign/document/list`],
  ];
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  // Bir işin bütün sekmeleri, aynı anda en çok `es` istekle. Her istekten önce `once` (varsa) beklenir; oturum
  // düşerse (401/403) yeni istek başlatılmaz. Sekme sırası korunur (çekmecenin ilk sekmeleri önce).
  async function sekmeleriOku(uuid, es, once) {
    const sekmeler = {};
    let sira = 0;
    let dustu = false;
    const isci = async () => {
      while (!dustu && sira < DETAY_UCLARI.length) {
        const [ad, yol] = DETAY_UCLARI[sira++];
        if (once) await once();
        if (dustu) break;
        try {
          sekmeler[ad] = { veri: await istek(new URL(yol(uuid), location.origin).href, 'GET') };
        } catch (e) {
          sekmeler[ad] = { hata: String((e && e.message) || 'hata').split(' ')[0].slice(0, 40) };
          if (/^http_(401|403)$/.test(sekmeler[ad].hata)) dustu = true;       // oturum yok: kalan sekmeler de düşer
        }
      }
    };
    await Promise.all(Array.from({ length: Math.max(1, Math.min(es, DETAY_UCLARI.length)) }, isci));
    return sekmeler;
  }
  let detayda = 0;
  async function detay(m) {
    const bitir = (ek) => ilet({ tur: 'detay-bitti', istek_id: m.istek_id, is_no: m.is_no, uuid: m.uuid, ...ek });
    if (!sonListe) return bitir({ hata: 'istek_yok' });
    if (!UUID.test(String(m.uuid || ''))) return bitir({ hata: 'uuid_gecersiz' });
    if (detayda >= 2) return bitir({ hata: 'suruyor' });
    detayda++;
    const t0 = Date.now();
    try {
      bitir({ sekmeler: await sekmeleriOku(m.uuid, DETAY_UCLARI.length), sure_ms: Date.now() - t0 });
    } finally {
      detayda--;
    }
  }

  // ---------------------------------------------------------------- ayrıntı önden okuma (yalnız GET, nazik)
  const ONDEN_ARA_MS = 250;              // iki iş arası
  const ONDEN_ES = 3;                    // bir işin sekmeleri: aynı anda en çok 3 istek
  let ondende = false;
  let ondenAktif = 0;
  // Önden okuma isteği başlamadan: kullanıcının açtığı ayrıntı bitene dek bekler; eşitleme / telefon okuması /
  // BOSS'a yazma sürerken aynı anda yalnız 1 önden okuma isteği (toplam istek sayısı 3'ü geçmesin).
  const ondenIzin = async () => {
    for (;;) {
      const sinir = detayda ? 0 : (esitleniyor || iletisimde || yaziyor) ? 1 : ONDEN_ES;
      if (ondenAktif < sinir) { ondenAktif++; return; }
      await bekle(100);
    }
  };
  async function detayOnden(m) {
    const bitir = (ek) => ilet({ tur: 'detay-onden-bitti', istek_id: m.istek_id, ...ek });
    if (!sonListe) return bitir({ hata: 'istek_yok' });
    if (ondende) return bitir({ hata: 'suruyor' });
    ondende = true;
    let okunan = 0;
    try {
      for (const x of (Array.isArray(m.isler) ? m.isler : []).slice(0, 200)) {
        if (!x || !UUID.test(String(x.uuid || ''))) continue;
        const t0 = Date.now();
        const sekmeler = await sekmeleriOkuOnden(x.uuid);
        const hatalar = Object.values(sekmeler).map((v) => v.hata).filter(Boolean);
        if (hatalar.some((h) => /^http_(401|403)$/.test(h))) return bitir({ okunan, hata: 'oturum' });   // sonra yeniden
        ilet({ tur: 'detay-onden-parca', istek_id: m.istek_id,
          sonuclar: [{ task_no: String(x.task_no), uuid: String(x.uuid), sekmeler, sure_ms: Date.now() - t0 }] });
        okunan++;
        await bekle(ONDEN_ARA_MS);
      }
      bitir({ okunan });
    } catch (e) {
      bitir({ okunan, hata: String((e && e.message) || 'hata').slice(0, 120) });
    } finally {
      ondende = false;
    }
  }
  // önden okuma: her istek ondenIzin ile başlar, bitince sayaç düşer
  function sekmeleriOkuOnden(uuid) {
    const sekmeler = {};
    let sira = 0;
    let dustu = false;
    const isci = async () => {
      while (!dustu && sira < DETAY_UCLARI.length) {
        await ondenIzin();
        if (dustu || sira >= DETAY_UCLARI.length) { ondenAktif--; break; }
        const [ad, yol] = DETAY_UCLARI[sira++];
        try {
          sekmeler[ad] = { veri: await istek(new URL(yol(uuid), location.origin).href, 'GET') };
        } catch (e) {
          sekmeler[ad] = { hata: String((e && e.message) || 'hata').split(' ')[0].slice(0, 40) };
          if (/^http_(401|403)$/.test(sekmeler[ad].hata)) dustu = true;
        } finally {
          ondenAktif--;
        }
      }
    };
    return Promise.all(Array.from({ length: ONDEN_ES }, isci)).then(() => sekmeler);
  }

  // ---------------------------------------------------------------- müşteri telefonu önden okuma (yalnız GET, sıralı)
  const ILETISIM_ARA_MS = 300;
  const ILETISIM_PARCA = 10;
  let iletisimde = false;
  async function iletisimOku(m) {
    const bitir = (ek) => ilet({ tur: 'iletisim-bitti', istek_id: m.istek_id, ...ek });
    if (!sonListe) return bitir({ hata: 'istek_yok' });
    if (iletisimde) return bitir({ hata: 'suruyor' });
    iletisimde = true;
    let parca = [];
    let okunan = 0;
    try {
      for (const x of (Array.isArray(m.isler) ? m.isler : []).slice(0, 1000)) {
        if (!x || !UUID.test(String(x.uuid || ''))) continue;
        while (detayda || esitleniyor) await bekle(ILETISIM_ARA_MS);      // kullanıcının istediği ayrıntı önce
        const yol = `${TASK}/task-id/${x.uuid}/detail/customer/list`;
        try {
          parca.push({ task_no: String(x.task_no), veri: await istek(new URL(yol, location.origin).href, 'GET') });
        } catch (e) {
          parca.push({ task_no: String(x.task_no), hata: String((e && e.message) || 'hata').split(' ')[0].slice(0, 40) });
        }
        okunan++;
        if (parca.length >= ILETISIM_PARCA) {
          ilet({ tur: 'iletisim-parca', istek_id: m.istek_id, sonuclar: parca });
          parca = [];
        }
        await bekle(ILETISIM_ARA_MS);
      }
      if (parca.length) ilet({ tur: 'iletisim-parca', istek_id: m.istek_id, sonuclar: parca });
      bitir({ okunan });
    } catch (e) {
      bitir({ hata: String((e && e.message) || 'hata').slice(0, 120) });
    } finally {
      iletisimde = false;
    }
  }
  // Yazma patlaması sürerken (kuyrukta ya da yolda istek) eşitleme taraması başlamaz, en çok ESITLE_YAZ_BEKLE_MS
  // bekler: yüzlerce liste isteği yazmalarla aynı anda BOSS'a yüklenmesin (hız sınırı). Sonra yine de başlar.
  const ESITLE_YAZ_BEKLE_MS = 120 * 1000;
  let esitleBekliyor = false;
  async function esitle(m) {
    if (esitleniyor || esitleBekliyor) return ilet({ tur: 'esitle-bitti', istek_id: m.istek_id, hata: 'suruyor' });
    if (!sonListe) return ilet({ tur: 'esitle-bitti', istek_id: m.istek_id, hata: 'istek_yok' });
    esitleBekliyor = true;
    try {
      const t0 = Date.now();
      while (yaziyor && Date.now() - t0 < ESITLE_YAZ_BEKLE_MS) await bekle(250);
    } finally {
      esitleBekliyor = false;
    }
    esitleniyor = true;
    try {
      const a = await tara(m.istek_id, m.acik, EN_COK_SAYFA, 'acik');
      let k = { okunan: 0 };
      if (a.durumAyarlandi && m.kapali && m.kapali.length) {
        await bekle(BEKLE_MS);
        try { k = await tara(m.istek_id, m.kapali, m.kapaliSayfa || 2, 'kapali'); } catch (e) { /* kapalılar isteğe bağlı */ }
      }
      await bekle(BEKLE_MS);
      const ekipler = await ekipleriOku();
      ilet({ tur: 'esitle-bitti', istek_id: m.istek_id, tam: !!(a.tam && a.durumAyarlandi), okunan: a.okunan + k.okunan, toplam: a.toplam, ekipler });
    } catch (e) {
      tani('esitle_hata', sonListe && new URL(sonListe.url, location.origin).pathname, String((e && e.message) || 'hata'));
      ilet({ tur: 'esitle-bitti', istek_id: m.istek_id, hata: String((e && e.message) || 'hata').slice(0, 120) });
    } finally {
      esitleniyor = false;
    }
  }

  // ---------------------------------------------------------------- BOSS'a yazma yürütücüsü
  // Yalnız bu uçlara, yalnız POST, sınırlı havuzla (aynı anda en çok yazParalel; istekler geliş sırasıyla BAŞLAR).
  // Her isteğin sonucu (yaz-sonuc) ayrı ve aynı biçimde iletilir. Başlık değerleri (oturum) yalnız sayfanın belleğinde ve
  // BOSS'a giden istekte kullanılır, hiçbir mesaja/depoya girmez; BOSS'un yanıtından yalnız returnCode/returnMessage
  // (kısaltılmış, uzun sayılar maskeli) ve HTTP kodu iletilir.
  const YAZILABILIR = [
    /^\/boss-gateway-service\/appointment-service\/api\/v1\/appointment$/,
    /^\/boss-gateway-service\/task-service\/api\/v1\/task\/suspend$/,
    /^\/boss-gateway-service\/task-service\/api\/v1\/task\/note$/,
  ];
  const YAZ_ARA_MS = 400;                 // eşitleme beklerken yoklama aralığı
  const YAZ_ISCI_ARA_MS = 150;            // bir işçinin iki isteği arasındaki kısa ara (BOSS'a nazik)
  const YAZ_BEKLE_EN_COK_MS = 8000;
  const YAZ_PARALEL_VARSAYILAN = 6;
  const YAZ_PARALEL_EN_COK = 10;          // BOSS hız sınırı / hesap işaretlenmesi riski: asla 10'dan fazla
  const YAZ_YENIDEN_EN_COK = 3;           // 429/502/503/504'te en çok bu kadar yeniden deneme
  const GERI_TABAN_MS = 1000;
  const GERI_EN_COK_MS = 30000;
  // 429 ve ağ geçidi hataları (502/503/504): istek işlenmedi sayılır → aynı istek yeniden denenir. 500 ve diğer
  // 5xx: BOSS iş hatasını da 500'le dönüyor (07.10: askıdaki işe randevu) ve isteğin işlenip işlenmediği bilinmez →
  // yeniden DENENMEZ (çift yazma olmasın), yalnız bütün havuz geri çekilir (yavaşlar).
  const YENIDEN_DENENIR = new Set([429, 502, 503, 504]);
  const yazKuyrugu = [];
  let yaziyor = false;                    // kuyrukta ya da yolda yazma var (eşitleme ve önden okuma buna bakar)
  let yazAktif = 0;                       // şu an BOSS'ta yanıt bekleyen istek sayısı
  let yazIsci = 0;                        // çalışan işçi sayısı
  let yazParalel = YAZ_PARALEL_VARSAYILAN;
  let geriSeviye = 0;                     // art arda 429/5xx sayısı (başarıda sıfırlanır)
  let geriBitis = 0;                      // bu ana dek hiçbir işçi yeni istek başlatmaz
  const yazSayac = { enCok: 0, yeniden: 0, geri: 0 };   // tanı: en çok eşzamanlı istek, yeniden deneme, geri çekilme
  const paralelAyarla = (n) => {
    const v = Math.floor(Number(n));
    if (Number.isFinite(v) && v >= 1) yazParalel = Math.min(YAZ_PARALEL_EN_COK, v);
  };
  const geriCekil = (y) => {
    geriSeviye = Math.min(geriSeviye + 1, 8);
    let ms = Math.min(GERI_EN_COK_MS, GERI_TABAN_MS * 2 ** (geriSeviye - 1));
    let ra = null;
    try { ra = y && y.headers && typeof y.headers.get === 'function' ? y.headers.get('retry-after') : null; } catch (e) { ra = null; }
    if (ra && /^\d{1,4}$/.test(String(ra).trim())) ms = Math.min(GERI_EN_COK_MS * 2, Math.max(ms, Number(ra) * 1000));
    ms = Math.round(ms * (0.8 + Math.random() * 0.4));
    geriBitis = Math.max(geriBitis, Date.now() + ms);
    yazSayac.geri++;
  };
  const sonucAl = (j) => {
    if (!j || typeof j !== 'object' || Array.isArray(j)) return { kod: null, mesaj: null };
    const kod = j.returnCode ?? (j.result && j.result.returnCode);
    const mesaj = j.returnMessage ?? (j.result && j.result.returnMessage);
    return { kod: kod == null ? null : (typeof kod === 'number' ? kod : String(kod).slice(0, 40)),
      // metindeki ≥ 10 haneli sayılar (telefon, TCKN, abone no) gizlenir
      mesaj: mesaj == null ? null : String(mesaj).replace(/\+?\d[\d\s]{8,}\d/g, (x) => (x.replace(/\D/g, '').length >= 10 ? '•••' : x)).slice(0, 200) };
  };
  // Yazma isteğinin başlıkları: o servise sayfanın kendi yazma isteğindekiler (yoksa liste isteğininkiler); her
  // içerik türü başlığı atılır, tek "Content-Type: application/json" eklenir (iki başlık birleşip bozulmasın).
  const yazmaBasliklariKur = (yol) => {
    const m = SERVIS.exec(String(yol || ''));
    const kaynak = (m && yazmaBasliklari[m[1]]) || yazmaBasliklari['task-service'] || yazmaBasliklari['appointment-service'] || sonListe.basliklar || {};
    const b = {};
    for (const [k, v] of Object.entries(kaynak)) if (!/^(content-type|content-length)$/i.test(k)) b[k] = v;
    b['Content-Type'] = 'application/json';
    return b;
  };
  // 2xx olmayan yanıtın metni: JSON ise kişisel alanlar maskeli (maske.js), her durumda ≥ 10 haneli sayılar gizli
  const yanitMaskele = (metin, j) => {
    let t = '';
    try { t = j && typeof j === 'object' ? JSON.stringify(maskele(j)) : String(metin || ''); } catch (e) { t = ''; }
    return t.replace(/\+?\d[\d\s]{8,}\d/g, (x) => (x.replace(/\D/g, '').length >= 10 ? '•••' : x)).slice(0, 1500) || null;
  };
  async function yazTek(i) {
    const bitir = (ek) => ilet({ tur: 'yaz-sonuc', istek_id: i.istek_id, kayitlar: i.kayitlar || [], ...ek });
    // başlıklar henüz yakalanmadı: hiçbir şey gönderilmedi, sunucu kaydı bekletir ve sonra yeniden verir
    if (!sonListe) return bitir({ durum: 'ertelendi', hata: 'istek_yok', hazir: false });
    // Eşitleme / kullanıcının ayrıntısı sürerken kısa süre beklenir, ama EN ÇOK YAZ_BEKLE_EN_COK_MS: tam eşitleme
    // ~60 sn sürer; yazma onun bitmesini beklerse sonuç eski eklentide düşüyor, BOSS'a geç yazılıyordu (08.10).
    const t0 = Date.now();
    while ((esitleniyor || detayda) && Date.now() - t0 < YAZ_BEKLE_EN_COK_MS) await bekle(YAZ_ARA_MS);
    try {
      let y;
      let metin = '';
      for (let deneme = 0; ; deneme++) {
        while (Date.now() < geriBitis) await bekle(Math.min(500, geriBitis - Date.now()));
        yazAktif++;
        yazSayac.enCok = Math.max(yazSayac.enCok, yazAktif);
        try {
          y = await asilFetch.call(window, new URL(i.yol, location.origin).href, {
            method: 'POST', headers: yazmaBasliklariKur(i.yol), body: JSON.stringify(i.govde), credentials: 'include',
          });
          metin = '';
          try { metin = await y.text(); } catch (e) { /* gövde okunamadı */ }
        } finally {
          yazAktif--;
        }
        if (y.status === 429 || y.status >= 500) geriCekil(y);
        else if (y.ok) geriSeviye = 0;
        if (!(YENIDEN_DENENIR.has(y.status) && deneme < YAZ_YENIDEN_EN_COK)) break;
        yazSayac.yeniden++;
      }
      const j = govdeCoz(metin);
      const r = sonucAl(j);
      const tamam = y.ok && (r.kod == null || String(r.kod) === '0');
      bitir({ durum: tamam ? 'gonderildi' : 'hata', http: y.status, return_kodu: r.kod, return_mesaji: r.mesaj,
        ...(tamam ? {} : { hata: y.ok ? `boss_${r.kod}` : `http_${y.status}`, yanit_metni: yanitMaskele(metin, j) }) });
    } catch (e) {
      // ağ hatası: isteğin BOSS'a ulaşıp ulaşmadığı bilinmez → hata (sunucu kendiliğinden yeniden göndermez)
      bitir({ durum: 'hata', hata: String((e && e.message) || 'hata').slice(0, 120) });
    }
  }
  // Havuz: kuyrukta iş varken en çok yazParalel işçi; her işçi sıradaki isteği alır (başlama sırası = geliş sırası).
  async function yazIsciDongusu() {
    try {
      while (yazKuyrugu.length) {
        await yazTek(yazKuyrugu.shift());
        if (yazIsci > yazParalel) break;            // paralel ayarı düşürüldü: fazla işçi çekilir
        if (yazKuyrugu.length) await bekle(YAZ_ISCI_ARA_MS);
      }
    } finally {
      yazIsci--;
      yaziyor = yazIsci > 0 || yazKuyrugu.length > 0;
      if (yazKuyrugu.length) yazKuyruguIsle();
    }
  }
  function yazKuyruguIsle() {
    while (yazIsci < yazParalel && yazIsci < yazKuyrugu.length) {
      yazIsci++;
      yaziyor = true;
      yazIsciDongusu();
    }
  }
  function yaz(m) {
    const i = (m && m.istek) || {};
    const bitir = (ek) => ilet({ tur: 'yaz-sonuc', istek_id: i.istek_id, kayitlar: i.kayitlar || [], ...ek });
    if (String(i.yontem || '').toUpperCase() !== 'POST' || !YAZILABILIR.some((r) => r.test(String(i.yol || '')))) {
      return bitir({ durum: 'hata', hata: 'uc_izinsiz' });
    }
    if (!(i.yaz === true && (i.dogrulandi === true || i.deneme === true))) return bitir({ durum: 'onizleme', hazir: !!sonListe });
    if (yazKuyrugu.some((x) => x.istek_id === i.istek_id)) return;      // aynı istek kuyrukta zaten
    if (i.paralel != null) paralelAyarla(i.paralel);                    // sunucunun ayarı (boss_yazma_paralel, 1–10)
    yazKuyrugu.push(i);
    // teslim onayı (KANCA_SURUMU 9): sunucu kancaya hiç ulaşmayan isteği "sonuç gelmedi" yerine yeniden verir
    bitir({ durum: 'alindi' });
    yazKuyruguIsle();
  }

  // ---------------------------------------------------------------- askı nedeni kataloğu (işe göre, isteğe bağlı)
  const NEDEN_UCU = /^\/boss-gateway-service\/task-service\/api\/v1\/task\/reasons\/task-category\/[\w.-]{1,40}\/record-type\/SUSPEND_REASONS\/product-code\/[\w.-]{1,80}$/;
  // Alt neden listesi: sunucu, kayıt modunda görülen gerçek yolun kalıbından (üst neden kimliği GUID) ister.
  const ALT_UCU = /^\/boss-gateway-service\/task-service\/api\/v\d+\/task\/[\w/.-]{0,80}[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}[\w/.-]{0,120}$/;
  async function nedenOku(m) {
    const yol = String((m && m.yol) || '');
    const alt = ALT_UCU.test(yol) && ALT_NEDEN.test(yol) && !/\.\./.test(yol) && !TASK_KIMLIKLI.test(yol);
    if (!sonListe || !(NEDEN_UCU.test(yol) || alt)) return;
    try {
      tani(alt ? 'aski_alt_nedenleri' : 'aski_nedenleri', yol, '200', { veri: nedenSade(await istek(new URL(yol, location.origin).href, 'GET')) });
    } catch (e) {
      tani('aski_nedenleri_hata', yol, String((e && e.message) || 'hata').split(' ')[0].slice(0, 40));
    }
  }

  // ---------------------------------------------------------------- ekip GPS konumu (yalnız GET, tek istek)
  let konumda = false;
  async function konumOku(m) {
    const bitir = (ek) => ilet({ tur: 'konum-bitti', istek_id: m && m.istek_id, ...ek });
    const basliklar = (konumUcu && konumUcu.basliklar) || (sonListe && sonListe.basliklar) || null;
    const yol = konumUcu ? konumUcu.yol : KONUM_VARSAYILAN;
    if (!basliklar) return bitir({ hata: 'konum_yok' });            // sayfanın hiçbir başlığı bilinmiyor
    if (oturumDustu) return bitir({ hata: 'oturum', yol: yolHam(yol) });
    if (konumda) return bitir({ hata: 'suruyor' });
    if (yaziyor || Date.now() < geriBitis) return bitir({ hata: 'mesgul' });   // BOSS'a yazma / geri çekilme önce
    konumda = true;
    try {
      const url = new URL(yol, location.origin);
      if (url.origin !== location.origin || !KONUM.test(url.pathname + url.search)) return bitir({ hata: 'konum_yok' });
      const b = {};
      for (const [k, v] of Object.entries(basliklar)) if (!/^(content-type|content-length)$/i.test(k)) b[k] = v;
      const y = await asilFetch.call(window, url.href, { method: 'GET', headers: b, credentials: 'include' });
      durumGor(url.href, y.status);
      if (!y.ok) {
        if (!konumUcu && (y.status === 404 || y.status === 405)) return bitir({ hata: 'konum_yok', yol: url.pathname });
        return bitir({ hata: `http_${y.status}`, yol: url.pathname });
      }
      const veri = await y.json();
      konumYapisi(url.href, y.status, veri);
      bitir({ yol: url.pathname, veri, varsayilan: !konumUcu });
    } catch (e) {
      bitir({ hata: String((e && e.message) || 'hata').slice(0, 120) });
    } finally {
      konumda = false;
    }
  }

  window.addEventListener('message', (olay) => {
    if (olay.source !== window || olay.origin !== location.origin) return;
    const m = olay.data;
    if (!m || m.kaynak !== 'dehanet-komut') return;
    if (m.tur === 'esitle') esitle(m);
    else if (m.tur === 'detay') detay(m);
    else if (m.tur === 'iletisim') iletisimOku(m);
    else if (m.tur === 'detay-onden') detayOnden(m);
    else if (m.tur === 'kayit-modu') kayitModu = !!m.acik;
    else if (m.tur === 'yaz') yaz(m);
    else if (m.tur === 'neden-oku') nedenOku(m);
    else if (m.tur === 'konum-oku') konumOku(m);
    else if (m.tur === 'durum') {
      ilet({ tur: 'kanca-durum', liste: !!sonListe, surum: KANCA_SURUMU, konum: !!konumUcu,
        yazma: { paralel: yazParalel, aktif: yazAktif, kuyruk: yazKuyrugu.length, ...yazSayac } });
    }
  });
})();
