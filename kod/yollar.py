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
      veri/cikti/                   CIKTI           bölgeleme planları, Excel raporları, sunum dosyaları
      belgeler/                     BELGELER        kılavuzlar ve tasarım belgeleri
      canli/                        CANLI           ESKİ çalışan sistem (git dışı; Turkcell.exe ilk açılışta devralır, dokunmaz)
      veri/canli/                   MASAUSTU_VERI   Turkcell.exe'nin canlı çalışma klasörü (git dışı)
      Turkcell.exe  .turkcell/      masaüstü uygulaması (kod/masaustu/derle.py üretir; git dışı)
      gelistirme/veri/              CALISMA         geliştirme verisi (git dışı; varsayılan çalışma klasörü)
      gelistirme/test/              TEST_VERISI     gerçek veriden sabit test girdileri (git dışı): BOSS_RAPOR ve
                                                    analiz betiklerinin ham dökümleri (ANALIZ_GIRDI)

ÇALIŞMA KLASÖRÜ (``CALISMA``): sunucunun yazdığı her şey. ``SAHA_VERI_DIZINI`` ortam değişkeni verilirse
orası (göreli yol depo köküne göredir), verilmezse ``gelistirme/veri``. Varsayılan ASLA ``canli/`` değildir:
canlı veriye yalnız yayın aracı ``SAHA_VERI_DIZINI=<DSALE>\\canli\\veri`` (MUTLAK yol) vererek bağlanır.
Depo İÇİNDE yalnız git dışı iki yer çalışma klasörü olabilir: ``gelistirme/`` ve ``canli/``. Başka bir depo yolu
(ör. ``SAHA_VERI_DIZINI=veri`` → ham veri klasörü) reddedilir: saha.db/gizli.key git'in izlediği bir yere yazılmaz.
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

TEK SEFERLİK ANALİZ BETİKLERİ (``kod/operasyon/analiz``): ham girdileri (BOSS/Fox dökümleri, TAMAMLANDI.xlsx …)
``ANALIZ_GIRDI``'den (varsayılan ``gelistirme/test``; başka yer: ``SAHA_ANALIZ_GIRDI``), BOSS raporunu
``BOSS_RAPOR``'dan okur; çıktıları git dışı ``ANALIZ_CIKTI``'ya (alt çalışmalar ``ANALIZ/hakemN/cikti``) yazar.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

DONMUS = bool(getattr(sys, "frozen", False))
if DONMUS:
    # Turkcell.exe (PyInstaller, kod/masaustu/derle.py): salt okunur kaynaklar exe'nin yanındaki gizli
    # ``.turkcell/`` klasöründe depo düzeniyle durur (veri/ref, kod/arayuz/dist ...). KOK orasıdır; exe'nin
    # durduğu klasör (depo kökü) DEPO'dur ve yazılan her şey DEPO altında kalır.
    KOK = Path(getattr(sys, "_MEIPASS"))
else:
    KOK = Path(__file__).resolve().parent.parent

KOD = KOK / "kod"
VERI = KOK / "veri"
CIKTI = VERI / "cikti"
BELGELER = KOK / "belgeler"
ARAYUZ = KOD / "arayuz"
ARAYUZ_DIST = Path(os.environ["SAHA_ARAYUZ_DIST"]) if os.environ.get("SAHA_ARAYUZ_DIST") else ARAYUZ / "dist"
SUNUM = KOD / "sunum"
SUNUM_URETILEN = SUNUM / "src" / "data" / "generated"
ARACLAR = KOD / "araclar"
CANLI = (Path(sys.executable).resolve().parent if DONMUS else KOK) / "canli"   # eski düzen: canli/surum, canli/veri
GELISTIRME = KOK / "gelistirme"
# Gerçek veriden alınmış SABİT test girdileri (ör. BOSS raporu kopyası; kişisel veri → git dışı).
TEST_VERISI = GELISTIRME / "test"
# BOSS 'TeknikTaskDetayRaporu.xlsx' sabit kopyası: gerçek-rapor testleri ve analiz betikleri okur (yalnız okunur).
BOSS_RAPOR = Path(os.environ["BOSS_RAPOR"]) if os.environ.get("BOSS_RAPOR") else TEST_VERISI / "TeknikTaskDetayRaporu.xlsx"
# Tek seferlik operasyon analizleri: ham dökümler (kişisel veri) ve üretilen JSON'lar depoda izlenmez.
ANALIZ = KOD / "operasyon" / "analiz"
ANALIZ_CIKTI = ANALIZ / "cikti"
ANALIZ_GIRDI = Path(os.environ["SAHA_ANALIZ_GIRDI"]) if os.environ.get("SAHA_ANALIZ_GIRDI") else TEST_VERISI

# Bu kod yayınlanmış bir kopyadan mı çalışıyor (…/DSALE/canli/surum/kod/yollar.py)? O zaman KOK kopyanın
# köküdür; depo kökü 'canli' klasörünün üstüdür.
CANLI_KOPYA = not DONMUS and any(p.name.lower() == "canli" for p in (KOK, *KOK.parents))
DEPO = (Path(sys.executable).resolve().parent if DONMUS
        else next((p.parent for p in (KOK, *KOK.parents) if p.name.lower() == "canli"), KOK))
# Turkcell.exe'nin canlı çalışma klasörü (git dışı). Eski düzenden (canli/surum) ilk açılışta bir kez devralınır:
# kod/masaustu/devir.py.
MASAUSTU_VERI = DEPO / "veri" / "canli"

# Depo DIŞINDAKİ tek girdi: kardeş klasördeki PS26 dökümü (ticket/altyapı aktarımı; yalnız okunur).
# Canlı kopyada da depo kökünün yanıdır (canli/PS26 DEĞİL); başka yer: SAHA_PS26.
PS26 = Path(os.environ["SAHA_PS26"]) if os.environ.get("SAHA_PS26") else DEPO.parent / "PS26"


def _icinde(yol: Path, kok: Path) -> bool:
    """``yol`` ``kok``'ün kendisi ya da altında mı (Windows'ta büyük/küçük harf duyarsız, ``..`` çözülmüş)."""
    a = os.path.normcase(os.path.abspath(yol))
    b = os.path.normcase(os.path.abspath(kok))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:                       # farklı sürücüler
        return False


def _calisma() -> Path:
    ortam = os.environ.get("SAHA_VERI_DIZINI")
    if CANLI_KOPYA and not (ortam and Path(ortam).is_absolute()):
        # Yayınlanmış kopya varsayılana (kopya/gelistirme/veri → boş, taze veritabanı) ya da kopyaya göre
        # çözülen göreli bir yola (canli/surum/canli/veri) düşerse canlı veri "kaybolmuş" görünür. Durdur.
        raise RuntimeError(
            f"Canlı kopya ({KOK}) çalışma klasörü olmadan başlatılamaz: SAHA_VERI_DIZINI MUTLAK yol olmalı "
            f"(ör. {DEPO / 'canli' / 'veri'}). Şu an: {ortam or 'verilmedi'}.")
    if not ortam:
        return MASAUSTU_VERI if DONMUS else GELISTIRME / "veri"
    yol = Path(ortam)
    yol = yol if yol.is_absolute() else (DEPO if DONMUS else KOK) / yol
    # Depo içinde yalnız git dışı gelistirme/ ve canli/ çalışma klasörü olabilir: saha.db, gizli.key, yedek/, kayit/
    # kişisel veridir; git'in izlediği bir klasöre düşerse bir sonraki commit'le GitHub'a gider.
    if _icinde(yol, DEPO) and not (_icinde(yol, DEPO / "gelistirme") or _icinde(yol, DEPO / "canli")
                                   or _icinde(yol, MASAUSTU_VERI)):
        raise RuntimeError(
            f"SAHA_VERI_DIZINI depoda git'in izlediği bir yeri gösteriyor: {yol}. Depo içinde çalışma klasörü yalnız "
            f"{DEPO / 'gelistirme'} ya da {DEPO / 'canli'} altında olabilir (ya da depo dışında bir klasör).")
    return yol


CALISMA = _calisma()
CALISMA_SAHA = CALISMA / "saha"             # saha.db, gizli.key, yedek/, kayit/, ek/, raporlar/
CALISMA_OPERASYON = CALISMA / "operasyon"   # obekler.json, veri/
# Masaüstü kabuğunun (Turkcell.exe) gizli klasörü: WebView2 profili, geçici dosyalar, kabuk günlüğü.
# Bilgisayarda başka bir yere (%LOCALAPPDATA%, %TEMP%) yazılmasın diye her şey çalışma klasörünün içinde.
KABUK = CALISMA / ".turkcell"


def canli_veri_mi() -> bool:
    """Çalışma klasörü canlı veri mi: kod ``canli/`` altından çalışıyor ya da ``SAHA_VERI_DIZINI`` ``canli/``'yi
    gösteriyor. Sunucunun varsayılan adresi, rapor klasörü izleme ve göç/geri yükleme bekçileri buna bakar."""
    if CANLI_KOPYA:
        return True
    try:                                     # bağlantı/junction üzerinden verilmiş yollar da yakalansın
        c = CALISMA.resolve()
        return _icinde(c, (DEPO / "canli").resolve()) or _icinde(c, MASAUSTU_VERI.resolve())
    except OSError:
        return _icinde(CALISMA, DEPO / "canli") or _icinde(CALISMA, MASAUSTU_VERI)
