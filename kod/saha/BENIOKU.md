# saha — FastAPI sunucusu

Amaç: tek süreçte API + PWA sunumu; giriş/PIN, yetki, satış, ekip, ticket, bölgeleme, göç ve yedek.
Giriş: `api.py` (`uygulama`; uç modüllerini ve `_v2_bagla` ile operasyon/v2'yi bağlar). Başlatma: `sunucu.py` (geliştirme 8090) ya da Turkcell.exe.
Uçlar birim dosyalarında: `giris_uclari` · `satis_uclari` · `ekip_uclari` · `yonetim_uclari` · `admin_uclari` · `tablolar_uclari` · `arama_uclari` · `ek_dosya` · `onemap_esitle` (OneMap canlı bina eşitlemesi: /api/onemap/gorev · binalar · durum).
Yetki: `yetki.py` (IZINLER, ROTA_IZNI, `izin()`); şema: `db.py` + `sema_v2.py`; göç: `goc.py` (ADIMLAR, yedekli).
Kim çağırır: `kod/masaustu/turkcell.py`, `sunucu.py`, testler (`saha/testler`).
Bağımlı: `yollar`, `operasyon` (v2 iş motoru), `dsale` (bölgeleme, kalite).
