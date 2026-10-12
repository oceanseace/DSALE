# operasyon/v2 — iş motoru (sunucu)

Amaç: BOSS işlerinin veritabanındaki hayatı: eşitleme, durum makinesi, atama/randevu, görünüm, dağıtım, BOSS'a yazma kuyruğu.
Giriş: `api.py` → `yonlendiriciler(b)` (bütün uçlar) + modül düzeyi `ROTA_IZNI` (uç → izin).
Ana dosyalar: `boss.py` eşitleme · `aktarim.py` iş emrine yazma · `akis.py` durum geçişleri · `gorunum.py` liste/ayrıntı yanıtı
(müşteri verisinin çıktığı TEK yer) · `dagitim.py` görünümler/kural dağıtımı · `boss_yazma.py` BOSS'a yazma (anahtar varsayılan kapalı; tek iş denemesi) · `boss_ham.py` ham alanlar.
Kim çağırır: `kod/saha/api.py` `_v2_bagla` (içe aktarıp yönlendiricileri bağlar).
Bağımlı: `saha.yetki` (izin, baglanti), `saha.sema_v2`/`saha.goc` (şema), `operasyon.is_emri`, `operasyon.tembel`.
Testler: `kod/operasyon/testler/test_v2_*.py`. Harita: `kod/HARITA.md`.
