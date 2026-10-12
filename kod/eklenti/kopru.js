// Sayfadaki kanca (kanca.js, MAIN) ↔ eklentinin arka planı (arka.js) arasında köprü; yalnız aynı kökenden mesaj.
// Oturum bilgisi bu köprüden hiç geçmez: kanca başlıkları kendi belleğinde tutar.
// Yükleyen: manifest (sayfa açılırken) ya da arka.js betikleriYukle (eklenti yenilenince, F5'siz). İkinci kez
// yüklenince yeni köprü "devir" der; eski köprü (eklenti yenilenmişse ölü) susar — mesajlar iki kez gitmez.
(() => {
  const KOMUT = 'dehanet-komut';
  const BASLA = Date.now();
  const BEN = Math.random().toString(36).slice(2, 10);
  let etkin = true;
  // daha SONRA yüklenmiş köprü kazanır (aynı anda yüklenenlerde kimlik sırası)
  const dahaYeni = (d) => d.zaman > BASLA || (d.zaman === BASLA && String(d.ben) > BEN);

  const gonder = (m) => {
    try {
      const p = chrome.runtime.sendMessage(m);
      if (p && typeof p.catch === 'function') p.catch(() => {});
    } catch (e) {
      etkin = false;                     // eklenti yeniden yüklendi: bu köprü ölü; yenisi yüklenecek
    }
  };

  window.addEventListener('message', (olay) => {
    if (olay.source !== window || olay.origin !== location.origin) return;
    const d = olay.data;
    if (!d) return;
    if (d.kaynak === 'dehanet-kopru' && d.tur === 'devir') {
      if (d.ben !== BEN && dahaYeni(d)) etkin = false;
      return;
    }
    if (!etkin || d.kaynak !== 'dehanet-kanca') return;
    if (d.tur === 'yanit') {
      gonder({ tur: 'boss-yanit', yol: d.yol, yontem: d.yontem, govde: d.govde, veri: d.veri, zaman: Date.now() });
    } else if (d.tur === 'liste-yakalandi') {
      gonder({ tur: 'liste-yakalandi' });
    } else if (d.tur === 'kanca-durum') {
      if (d.eski) gonder({ tur: 'kanca-eski' });             // sayfada eski sürüm kanca: panel "F5" der
      else if (d.liste) gonder({ tur: 'liste-yakalandi' });  // yeniden yüklenen köprü: kanca listeyi zaten tutuyor
    } else if (d.tur === 'esitle-parca') {
      gonder({ tur: 'esitle-parca', istek_id: d.istek_id, etiket: d.etiket, gorevler: d.gorevler });
    } else if (d.tur === 'esitle-bitti') {
      gonder({ tur: 'esitle-bitti', istek_id: d.istek_id, tam: d.tam, okunan: d.okunan, toplam: d.toplam, hata: d.hata, ekipler: d.ekipler });
    } else if (d.tur === 'detay-bitti') {
      gonder({ tur: 'detay-bitti', istek_id: d.istek_id, is_no: d.is_no, uuid: d.uuid, sekmeler: d.sekmeler, hata: d.hata });
    } else if (d.tur === 'iletisim-parca') {
      gonder({ tur: 'iletisim-parca', istek_id: d.istek_id, sonuclar: d.sonuclar });
    } else if (d.tur === 'iletisim-bitti') {
      gonder({ tur: 'iletisim-bitti', istek_id: d.istek_id, okunan: d.okunan, hata: d.hata });
    } else if (d.tur === 'detay-onden-parca') {
      gonder({ tur: 'detay-onden-parca', istek_id: d.istek_id, sonuclar: d.sonuclar });
    } else if (d.tur === 'detay-onden-bitti') {
      gonder({ tur: 'detay-onden-bitti', istek_id: d.istek_id, okunan: d.okunan, hata: d.hata });
    } else if (d.tur === 'yaz-sonuc') {
      gonder({ tur: 'yaz-sonuc', istek_id: d.istek_id, kayitlar: d.kayitlar, durum: d.durum, http: d.http, hata: d.hata, hazir: d.hazir,
        return_kodu: d.return_kodu, return_mesaji: d.return_mesaji, yanit_metni: d.yanit_metni });
    } else if (d.tur === 'tani') {
      gonder({ tur: 'tani', adim: d.adim, yol: d.yol, ileti: d.ileti, ek: d.ek });
    } else if (d.tur === 'kimlik') {
      gonder({ tur: 'kimlik', ad: d.ad, kod: d.kod, unvan: d.unvan });
    } else if (d.tur === 'oturum-bitti') {
      gonder({ tur: 'oturum-bitti', neden: d.neden });
    } else if (d.tur === 'kayit') {
      gonder({ tur: 'kayit', yontem: d.yontem, yol: d.yol, govdeYapi: d.govdeYapi });
    } else if (d.tur === 'konum-yanit') {
      gonder({ tur: 'konum-yanit', yol: d.yol, veri: d.veri });
    } else if (d.tur === 'konum-bitti') {
      gonder({ tur: 'konum-bitti', istek_id: d.istek_id, yol: d.yol, veri: d.veri, hata: d.hata, varsayilan: d.varsayilan });
    }
  });

  // arka plan → kanca
  const komut = (o) => window.postMessage({ kaynak: KOMUT, ...o }, location.origin);
  chrome.runtime.onMessage.addListener((m) => {
    if (!m || !etkin) return;
    if (m.tur === 'esitle-baslat') {
      komut({ tur: 'esitle', istek_id: m.istek_id, acik: m.acik, kapali: m.kapali, kapaliSayfa: m.kapaliSayfa });
    } else if (m.tur === 'detay-baslat') {
      komut({ tur: 'detay', istek_id: m.istek_id, is_no: m.is_no, uuid: m.uuid });
    } else if (m.tur === 'iletisim-baslat') {
      komut({ tur: 'iletisim', istek_id: m.istek_id, isler: m.isler });
    } else if (m.tur === 'detay-onden-baslat') {
      komut({ tur: 'detay-onden', istek_id: m.istek_id, isler: m.isler });
    } else if (m.tur === 'yaz-baslat') {
      komut({ tur: 'yaz', istek: m.istek });
    } else if (m.tur === 'neden-oku-baslat') {
      komut({ tur: 'neden-oku', yol: m.yol });
    } else if (m.tur === 'konum-oku-baslat') {
      komut({ tur: 'konum-oku', istek_id: m.istek_id });
    }
  });

  // BOSS ile giriş — kimliğin BİRİNCİL kaynağı: BOSS sayfa başlığındaki kullanıcı metni
  // (//*[@id="root"]/div[1]/div[2]/header/div/div[2], ör. "AD SOYAD / DEHANET ECM"). Yalnız ad + bayi metni okunur
  // (bu yalıtılmış dünyada DOM okuma); değişince ya da dakikada bir arka plana "kimlik" (kaynak: dom) gider.
  const BASLIK_XPATH = '//*[@id="root"]/div[1]/div[2]/header/div/div[2]';
  const adGecerli = (v) => /^[\p{L}][\p{L} .'-]{2,79}$/u.test(v) && v.split(/\s+/).length >= 2;
  const baslikKimligi = () => {
    try {
      if (typeof document.evaluate !== 'function') return null;
      let el = document.evaluate(BASLIK_XPATH, document, null, 9, null).singleNodeValue;   // FIRST_ORDERED_NODE_TYPE
      if (!el && document.querySelectorAll) {
        el = [...document.querySelectorAll('#root header div')].find((x) => / \/ /.test(x.textContent || '') && x.children.length <= 3) || null;
      }
      const metin = String((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
      if (!metin || metin.length > 200) return null;
      const i = metin.indexOf('/');
      const ad = (i >= 0 ? metin.slice(0, i) : metin).trim();
      const bayi = i >= 0 ? metin.slice(i + 1).trim().slice(0, 120) : null;
      return adGecerli(ad) ? { ad: ad.slice(0, 120), bayi: bayi || null } : null;
    } catch (e) { return null; }
  };
  let sonBaslik = '';
  let sonBaslikAn = 0;
  const baslikDenetle = () => {
    if (!etkin) return;
    const k = baslikKimligi();
    if (!k) return;
    const a = `${k.ad}|${k.bayi || ''}`;
    if (a === sonBaslik && Date.now() - sonBaslikAn < 60000) return;
    sonBaslik = a;
    sonBaslikAn = Date.now();
    gonder({ tur: 'kimlik', ad: k.ad, kod: null, unvan: null, bayi: k.bayi, kaynak: 'dom' });
  };
  try { if (typeof setInterval === 'function') setInterval(baslikDenetle, 3000); } catch (e) { /* sessiz */ }

  // Kayıt modu (panelden açılır; yalnız yapı kaydedilir)
  const kayitModuGonder = (acik) => komut({ tur: 'kayit-modu', acik: !!acik });
  try {
    window.postMessage({ kaynak: 'dehanet-kopru', tur: 'devir', ben: BEN, zaman: BASLA }, location.origin);
    chrome.storage.local.get(['kayitModu']).then((d) => kayitModuGonder(d.kayitModu));
    chrome.storage.onChanged.addListener((d, alan) => {
      if (etkin && alan === 'local' && d.kayitModu) kayitModuGonder(d.kayitModu.newValue);
    });
    if (document.readyState === 'loading') gonder({ tur: 'sayfa-acildi' });   // yeni sayfa (yeniden yükleme değil)
    else komut({ tur: 'durum' });                                             // kanca listeyi tutuyor mu?
  } catch (e) { /* sessiz */ }
})();
