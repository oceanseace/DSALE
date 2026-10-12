# eklenti — BOSS Yardımcısı (Chrome/Brave)

Amaç: kullanıcının kendi BOSS oturumuyla Teknik Havuz listesini okuyup yerel uygulamaya (127.0.0.1:<port>) yollamak.
Giriş: `manifest.json` → `arka.js` (servis çalışanı). Sayfa içi: `kanca.js` (fetch/XHR dinler, sayfa sayfa okur, BOSS'a yazar);
köprü: `kopru.js` (sayfa ↔ eklenti mesajları); alan eşleme: `eslem.js` (TEK yer); kişisel veri maskesi: `maske.js` (TEK yer); yan panel: `panel.html/js/css`.
Sunucu uçları: /api/boss/esitle · izler · detay · detay-onden · istekler · iletisim · yazilacaklar · yazma-sonucu · gunluk (eşleme kodu başlığı).
Ayrıntı önden okuma: eşitleme yanıtındaki `detay_onden` (yeni/değişen açık işler) → kanca sekmeleri sırayla, ~300 ms arayla okur;
kullanıcının istediği ayrıntı, eşitleme, telefon okuması ve yazma sürerken bekler; 401/403'te durur (`kanca.js detayOnden`).
Panel: büyük sayı son başarılı eşitlemenin açık iş sayısıdır; eşitleme sürerken yalnız küçük "denetleniyor…" görünür.
Mesaj türleri ve işleyenleri: `kod/HARITA.md` §6.
Eşitleme kullanıcının BOSS'ta yaptığından bağımsızdır: yakalanan liste isteğinden yalnız başlıklar alınır, gövde kanoniktir (`kanca.js listeyiTut`).
BOSS'a yazma: not kendi anahtarıyla (`ayar.boss_yazma_not`, varsayılan açık; istekte `eylem_acik`), atama/askı genel anahtar
`ayar.boss_yazma` (varsayılan kapalı, yalnız Administrator) ya da yöneticinin tek iş denemesi
(`POST /api/boss/yazma-dene`); kanca istekleri sırayla, sayfanın bellekteki başlıklarıyla gönderir, returnCode/returnMessage bildirir.
Giriş/OTP uçları (`GIZLI_UC`) hiçbir koşulda kaydedilmez.
OneMap bina eşitlemesi (BOSS'tan bağımsız): `onemap_sayfa.js` (OneMap/ArcGIS sayfasında MAIN; sorguyu sayfanın kendi
oturumuyla atar, varsa sayfa jetonu yalnız bellekte) · `onemap_kopru.js` (köprü) · `onemap_arka.js` (arka.js yükler; 10 dk'da bir
ve OneMap sekmesi açılınca `GET /api/onemap/gorev` → ArcGIS sorguları → `POST /api/onemap/binalar`). Sorgu metnini sunucu kurar
(`kod/saha/onemap_esitle.py`); ArcGIS alanı → sade satır TEK yer: `onemap_arka.js sadeSatir`. OneMap sekmesi açık kalmalı.
Test: `node kod/eklenti/test.mjs`.
