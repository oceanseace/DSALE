"""Depo yolları — TEK KAYNAK.

Bütün kod (Python paketleri, araçlar, betikler) depo içindeki yolları buradan alır; hiçbir modül
``Path(__file__)``'dan yukarı çıkarak yol hesaplamaz. Klasör adı değişirse yalnız bu dosya değişir.

    DSALE/                          KOK
      kod/                          KOD             bütün kaynak kod (bu dosya burada)
        saha/ operasyon/ dsale/ lisans/            Python paketleri
        arayuz/                     ARAYUZ          telefon + yönetici uygulaması (PWA)
          dist/                     ARAYUZ_DIST     derlenmiş hâli; sunucu bunu sunar
        sunum/                      SUNUM           3B sunum uygulaması (Electron)
          src/data/generated/       SUNUM_URETILEN  bölgeleme veri paketi (bolge.py üretir)
        araclar/  eklenti/  masaustu/
      veri/                         VERI            raw/ (ham) · ref/ (referans) · master/ (işlenmiş bina tablosu)
      cikti/                        CIKTI           bölgeleme planları, Excel raporları, sunum dosyaları
      belgeler/                     BELGELER        kılavuzlar ve tasarım belgeleri
      canli/                        CANLI           çalışan sistem (git dışı; yalnız YAYINLA değiştirir)
      gelistirme/veri/              CALISMA         geliştirme verisi (git dışı; varsayılan çalışma klasörü)
      gelistirme/test/              TEST_VERISI     gerçek veriden sabit test girdileri (git dışı)

ÇALIŞMA KLASÖRÜ (``CALISMA``): sunucunun yazdığı her şey. ``SAHA_VERI_DIZINI`` ortam değişkeni verilirse
orası (göreli yol depo köküne göredir), verilmezse ``gelistirme/veri``. Varsayılan ASLA ``canli/`` değildir:
canlı veriye yalnız yayın aracı ``SAHA_VERI_DIZINI=<DSALE>\\canli\\veri`` (MUTLAK yol) vererek bağlanır.
Kod ``canli/`` altındaki yayınlanmış bir kopyadan çalışıyorsa (``CANLI_KOPYA``), ``SAHA_VERI_DIZINI`` mutlak
yol olarak verilmeden içe aktarılamaz: yayınlanmış kopya boş geliştirme varsayılanına hiçbir zaman düşmez.

    CALISMA/
      saha/         saha.db (+ -wal/-shm) · gizli.key · yedek/ · kayit/ · ek/ · raporlar/
      operasyon/    obekler.json · veri/
      gelen/        yüklenen tur raporları ve OneMap dökümleri
      cikti/        sunucunun hesapladığı planlar ve bölgeleme Excel'leri

Tek tek yönlendirmeler her zaman önce gelir (testler, provalar ve masaüstü sürümü bunları kullanır):
``SAHA_DB`` · ``SAHA_GELEN`` · ``SAHA_CIKTI`` · ``SAHA_EK`` · ``OPERASYON_VERI`` · ``OPERASYON_OBEK``.
Depo dışındaki PS26 dökümü: ``SAHA_PS26`` (verilmezse depo kökünün yanındaki ``PS26/``).

Doğrudan çalıştırılan betikler (``python kod/araclar/bolge.py``) ``kod/``'u içe aktarma yoluna kendileri
koyar; ``.bat`` dosyaları ve kökteki ``pytest.ini`` ``PYTHONPATH=kod`` verir.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Dondurulmuş masaüstü sunucusu (PyInstaller): salt okunur kaynaklar _internal altında bu düzende
    # durur (kod/masaustu/araclar/kaynak_topla.py kopyalar).
    KOK = Path(getattr(sys, "_MEIPASS"))
else:
    KOK = Path(__file__).resolve().parent.parent

KOD = KOK / "kod"
VERI = KOK / "veri"
CIKTI = KOK / "cikti"
BELGELER = KOK / "belgeler"
ARAYUZ = KOD / "arayuz"
ARAYUZ_DIST = ARAYUZ / "dist"
SUNUM = KOD / "sunum"
SUNUM_URETILEN = SUNUM / "src" / "data" / "generated"
ARACLAR = KOD / "araclar"
CANLI = KOK / "canli"
GELISTIRME = KOK / "gelistirme"
# Gerçek veriden alınmış SABİT test girdileri (ör. BOSS raporu kopyası; kişisel veri → git dışı).
TEST_VERISI = GELISTIRME / "test"

# Bu kod yayınlanmış bir kopyadan mı çalışıyor (…/DSALE/canli/surum/kod/yollar.py)? O zaman KOK kopyanın
# köküdür; depo kökü 'canli' klasörünün üstüdür.
CANLI_KOPYA = not getattr(sys, "frozen", False) and any(p.name.lower() == "canli" for p in (KOK, *KOK.parents))
DEPO = next((p.parent for p in (KOK, *KOK.parents) if p.name.lower() == "canli"), KOK)

# Depo DIŞINDAKİ tek girdi: kardeş klasördeki PS26 dökümü (ticket/altyapı aktarımı; yalnız okunur).
# Canlı kopyada da depo kökünün yanıdır (canli/PS26 DEĞİL); başka yer: SAHA_PS26.
PS26 = Path(os.environ["SAHA_PS26"]) if os.environ.get("SAHA_PS26") else DEPO.parent / "PS26"


def _calisma() -> Path:
    ortam = os.environ.get("SAHA_VERI_DIZINI")
    if CANLI_KOPYA and not (ortam and Path(ortam).is_absolute()):
        # Yayınlanmış kopya varsayılana (kopya/gelistirme/veri → boş, taze veritabanı) ya da kopyaya göre
        # çözülen göreli bir yola (canli/surum/canli/veri) düşerse canlı veri "kaybolmuş" görünür. Durdur.
        raise RuntimeError(
            f"Canlı kopya ({KOK}) çalışma klasörü olmadan başlatılamaz: SAHA_VERI_DIZINI MUTLAK yol olmalı "
            f"(ör. {DEPO / 'canli' / 'veri'}). Şu an: {ortam or 'verilmedi'}.")
    if not ortam:
        return GELISTIRME / "veri"
    yol = Path(ortam)
    return yol if yol.is_absolute() else KOK / yol


CALISMA = _calisma()
CALISMA_SAHA = CALISMA / "saha"             # saha.db, gizli.key, yedek/, kayit/, ek/, raporlar/
CALISMA_OPERASYON = CALISMA / "operasyon"   # obekler.json, veri/
