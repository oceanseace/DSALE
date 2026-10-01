"""Saha Sistemi — 8 satışçının sahadaki işini yöneten sunucu.

Algoritma "bugün şuraya git" listesini üretir (``rota.py``), satışçı sonucu işler
(``api.py`` → ``/api/ziyaret``), yönetici boşlukların dolduğunu görür (``/api/ozet/*``).

Modüller
    ayarlar   dosya yolları, sabitler, ofis konumu
    db        SQLite bağlantısı ve şema
    kur       veritabanını oluştur + 19.706 binayı tohumla
    guvenlik  PIN özeti, oturum jetonu, hatalı giriş kilidi
    rota      öncelik puanı ve günlük tur kurucu
    rapor     günlük Excel raporu
    api       FastAPI uygulaması
"""

SURUM = "1.0.0"
