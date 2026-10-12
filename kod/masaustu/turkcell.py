"""Turkcell — masaüstü uygulaması (Turkcell.exe). Tek tık: pencere açılır, sunucu ve API'ler aynı süreçte başlar.

    .venv\\Scripts\\python.exe kod\\masaustu\\turkcell.py        # geliştirme (derlemeden)
    Turkcell.exe                                                # depo kökünde (kod/masaustu/derle.py üretir)
    Turkcell.exe --kapat                                        # açık olanı düzgün kapatır (kurulum sihirbazı için)

Ne yapar:
  * Tek örnek (adlı mutex). İkinci açılış açık pencereyi öne getirir ve çıkar.
  * Pencere HEMEN görünür ve ilk karede YERLİ açılış perdesi (WinForms paneli: Turkcell işareti + ad, uygulamanın
    zemin rengi; ``yerli_perde``) WebView2'nin üstünü örter — WebView2 kurulurken (soğuk açılışta saniyelerce) kara
    yüzey hiç görünmez. Gömülü HTML açılış ekranı (aynı görünüm + aşama yazısı) yüklenip boyanınca perde kalkar;
    sunucu ``/api/saglik`` 200 dönünce uygulamaya geçilir; uygulamanın aynı görünümlü perdesi (index.html #acilis)
    ilk veri gelene dek kalır, kalkınca arayüz ``KabukApi.acilis_bitti`` der.
    Zaman çizelgesi günlüğe: ``Açılış zaman çizelgesi`` satırı (.turkcell/kayit/turkcell.log).
  * Sunucu bu süreçte, arka iş parçacığında (uvicorn, ``saha.api:uygulama``). Varsayılan ``0.0.0.0:8080`` (telefonlar
    ofis ağından buraya bağlanır); ``TURKCELL_HOST`` / ``TURKCELL_PORT`` ile değişir.
  * Açılış sırası: port denetimi → eski düzenden canlı veri devri (bir kez; ``devir.py``) → ilk kurulum (veritabanı
    hiç yoksa) → şema göçü (``saha.goc``, doğrulanmış yedekle) → uvicorn.
  * Pencereyi kapatmak sunucuyu DURDURMAZ: pencere gizlenir, bildirim alanındaki simgeden geri açılır. "Çıkış"
    sunucuyu düzgün kapatır. Günde bir yedek (``saha.yedekle``), saatlik denetimle.
  * Projenin dışına yazılmaz: WebView2 profili, geçici dosyalar ve kabuk günlüğü çalışma klasörünün gizli
    ``.turkcell/`` alt klasöründe (``yollar.KABUK``).
  * "Excel'de aç" köprüsü (``KabukApi.excel_ac``): TASKS ekranı ``window.pywebview.api.excel_ac`` ile ürettiği .xlsx'i
    gizli ``tmp/``'ye yazdırır ve gerçek Excel'de açtırır (arayüz: kod/arayuz/.../isler/excelAc.ts).
"""
from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import urllib.request
from ctypes import wintypes
from pathlib import Path

DONMUS = bool(getattr(sys, "frozen", False))
if not DONMUS:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))       # kod/

import yollar  # noqa: E402

AD = "Turkcell"
UYGULAMA_KIMLIGI = "Turkcell.Bayi.Masaustu"                    # görev çubuğu gruplaması (AppUserModelID)
MUTEX_ADI = "Local\\Turkcell.Masaustu.TekOrnek"
OLAY_AC = "Local\\Turkcell.Masaustu.Ac"
OLAY_KAPAT = "Local\\Turkcell.Masaustu.Kapat"
# Exe (ve canlı veri) 0.0.0.0:8080'de açılır: telefonlar ofis ağından buraya bağlanır. Derlemeden, geliştirme
# verisiyle çalışınca saha.sunucu'nun kuralı geçerli: yalnız bu bilgisayar, 8090.
_CANLI = DONMUS or yollar.canli_veri_mi()
HOST = os.environ.get("TURKCELL_HOST") or ("0.0.0.0" if _CANLI else "127.0.0.1")
PORT = int(os.environ.get("TURKCELL_PORT") or (8080 if _CANLI else 8090))
KAYNAK = Path(getattr(sys, "_MEIPASS", "")) / "masaustu" if DONMUS else Path(__file__).resolve().parent / "kaynak"
IKON = KAYNAK / "turkcell.ico"
LOGO = KAYNAK / "logo.png"
ZEMIN_ACIK, ZEMIN_KOYU = "#F5F5F5", "#1F1F1F"                    # arayüzün --zemin'i (stil/tokenlar.css)

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateEventW.restype = wintypes.HANDLE
_k32.OpenEventW.restype = wintypes.HANDLE
_k32.WaitForMultipleObjects.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE), wintypes.BOOL,
                                        wintypes.DWORD]
_u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_u32.SetForegroundWindow.argtypes = [wintypes.HWND]
_u32.IsWindowVisible.argtypes = [wintypes.HWND]
_gunluk = logging.getLogger("turkcell")


# ============================================================================ tek örnek
def _olay_tetikle(ad: str) -> bool:
    h = _k32.OpenEventW(0x0002, False, ad)                      # EVENT_MODIFY_STATE
    if not h:
        return False
    try:
        return bool(_k32.SetEvent(h))
    finally:
        _k32.CloseHandle(h)


def tek_ornek() -> object | None:
    """İlk örnekse mutex tutamacını döner (süreç boyunca tutulur); değilse açık olanı uyarıp ``None``."""
    h = _k32.CreateMutexW(None, False, MUTEX_ADI)
    if ctypes.get_last_error() == 183:                          # ERROR_ALREADY_EXISTS
        _u32.AllowSetForegroundWindow(-1)                       # ASFW_ANY: açık örnek öne gelebilsin
        _olay_tetikle(OLAY_KAPAT if "--kapat" in sys.argv else OLAY_AC)
        return None
    return h


# ============================================================================ proje içinde kal
def gizli_klasor_hazirla() -> Path:
    """WebView2 profili, geçici dosyalar ve günlük çalışma klasörünün gizli ``.turkcell/`` alt klasörüne."""
    kok = yollar.KABUK
    for alt in ("webview", "tmp", "kayit"):
        (kok / alt).mkdir(parents=True, exist_ok=True)
    # Her açılışta güncel arayüz: önbellekteki eski sayfa ve servis çalışanı silinir (oturum çerezleri kalır)
    import shutil
    for eski in ("Cache", "Code Cache", "Service Worker"):
        shutil.rmtree(kok / "webview" / "EBWebView" / "Default" / eski, ignore_errors=True)
    _k32.SetFileAttributesW(str(kok), 0x2)                      # FILE_ATTRIBUTE_HIDDEN
    gecici = str(kok / "tmp")
    os.environ["TEMP"] = os.environ["TMP"] = gecici            # WebView2 alt süreçleri de devralır
    os.environ["WEBVIEW2_USER_DATA_FOLDER"] = str(kok / "webview")
    import tempfile
    tempfile.tempdir = gecici
    return kok


_KABUK_ISLEYICI: list[logging.Handler] = []


def _kabuk_isleyici() -> logging.Handler:
    return _KABUK_ISLEYICI[0] if _KABUK_ISLEYICI else logging.NullHandler()


def gunlugu_kur(kok: Path) -> None:
    """Pencereli exe'de stdout/stderr yoktur: ikisi de gizli klasördeki kabuk günlüğüne (2 MB'da döner)."""
    yol = kok / "kayit" / "turkcell.log"
    try:
        if yol.exists() and yol.stat().st_size > 2 * 1024 * 1024:
            os.replace(yol, yol.with_suffix(".log.1"))
    except OSError:
        pass
    if DONMUS or sys.stdout is None:
        akis = open(yol, "a", encoding="utf-8", errors="replace", buffering=1)  # noqa: SIM115 (süreç boyunca)
        sys.stdout = sys.stderr = akis
    kabuk = logging.StreamHandler(sys.stderr)
    _KABUK_ISLEYICI.append(kabuk)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(name)-14s %(message)s",
                        handlers=[kabuk])


# ============================================================================ Windows
def uygulama_kimligi() -> None:
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(UYGULAMA_KIMLIGI)
    except (OSError, AttributeError):
        pass


def koyu_tema() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as a:
            return winreg.QueryValueEx(a, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def pencereyi_susle(hwnd: int, koyu: bool) -> None:
    """Başlık çubuğu temaya uysun (DWMWA_USE_IMMERSIVE_DARK_MODE=20); Windows 11'de Mica (DWMWA_SYSTEMBACKDROP_TYPE=38).
    Desteklenmeyen sürümde DWM hata döner: sessizce geçilir."""
    try:
        dwm = ctypes.windll.dwmapi
        deger = ctypes.c_int(1 if koyu else 0)
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 20, ctypes.byref(deger), 4)
        mica = ctypes.c_int(2)                                  # DWMSBT_MAINWINDOW
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), 38, ctypes.byref(mica), 4)
    except (OSError, AttributeError):
        pass


def panoya_kopyala(metin: str) -> bool:
    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    _k32.GlobalAlloc.restype = wintypes.HGLOBAL
    _k32.GlobalLock.restype = ctypes.c_void_p
    _k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    veri = metin.encode("utf-16-le") + b"\0\0"
    for _ in range(10):                                         # pano başka süreçte açıksa kısa bekle
        if _u32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        _u32.EmptyClipboard()
        h = _k32.GlobalAlloc(GMEM_MOVEABLE, len(veri))
        p = _k32.GlobalLock(h)
        ctypes.memmove(p, veri, len(veri))
        _k32.GlobalUnlock(h)
        return bool(_u32.SetClipboardData(CF_UNICODETEXT, h))
    finally:
        _u32.CloseClipboard()


# ============================================================================ "Excel'de aç" köprüsü
EXCEL_EN_BUYUK = 64 * 1024 * 1024
EXCEL_SAKLAMA_SN = 24 * 3600
ZIP_IMZASI = bytes((0x50, 0x4B, 0x03, 0x04))                    # .xlsx bir zip dosyasıdır ("PK")


def excel_dosyasi_yaz(klasor: Path, dosya_adi: str, icerik_b64: str) -> Path:
    """Arayüzün ürettiği .xlsx'i ``klasor``e yazar, yolunu döner. Ad süzülür (yalnız ad, .xlsx); içerik zip (PK)
    olmalı. Aynı ad Excel'de açık durabilir: üstüne yazılmaz, "(2)" eklenir. Bir günden eski .xlsx'ler silinir."""
    ad = re.sub(r"[^\w .()-]+", "_", Path(str(dosya_adi)).name).strip(" .") or "TASKS"
    if not ad.lower().endswith(".xlsx"):
        ad += ".xlsx"
    veri = base64.b64decode(icerik_b64, validate=True)
    if len(veri) > EXCEL_EN_BUYUK or not veri.startswith(ZIP_IMZASI):
        raise ValueError("Geçersiz Excel dosyası")
    klasor.mkdir(parents=True, exist_ok=True)
    simdi = time.time()
    for eski in klasor.glob("*.xlsx"):
        try:
            if simdi - eski.stat().st_mtime > EXCEL_SAKLAMA_SN:
                eski.unlink()
        except OSError:                                         # Excel'de açıksa kalır
            pass
    yol, n = klasor / ad, 2
    while yol.exists():
        yol = klasor / f"{ad[:-5]} ({n}).xlsx"
        n += 1
    yol.write_bytes(veri)
    return yol


def boss_giris_adresi_mi(adres: str) -> bool:
    """Yalnız yerel sunucunun BOSS giriş ara sayfası (http://127.0.0.1|localhost:<port>/boss-giris/<istek>)."""
    return bool(re.fullmatch(r"http://(127\.0\.0\.1|localhost):\d{2,5}/boss-giris/[A-Za-z0-9_-]{16,80}", adres or ""))


def brave_yolu() -> Path | None:
    """Brave'in kurulu olduğu yer (eklenti orada); yoksa None."""
    for ortam in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        kok = os.environ.get(ortam)
        if kok:
            yol = Path(kok) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe"
            if yol.exists():
                return yol
    return None


class KabukApi:
    """Arayüzün ``window.pywebview.api`` ile çağırdığı kabuk işleri (yalnız bunlar; public öznitelik yok)."""

    def __init__(self, klasor: Path | None = None, ac=None) -> None:
        self._klasor = klasor
        self._ac = ac

    def acilis_bitti(self) -> dict:
        """Arayüzün açılış perdesi kalktı (ilk veri geldi): zaman çizelgesinin son adımı."""
        D.an("ilk_veri")
        D.cizelge_yaz()
        return {"ok": True}

    def tarayicida_ac(self, adres: str) -> dict:
        """"BOSS ile giriş": yalnız bu sunucunun ``/boss-giris/<istek>`` ara sayfası Brave'de (yoksa varsayılan
        tarayıcıda) açılır; başka adres açılmaz. Sayfa BOSS'a yönlendirir, şifre yalnız BOSS'a yazılır."""
        if not boss_giris_adresi_mi(adres):
            return {"ok": False, "hata": "Bu adres açılamaz."}
        try:
            brave = brave_yolu()
            if brave:
                import subprocess
                subprocess.Popen([str(brave), adres], close_fds=True)
            else:
                (self._ac or os.startfile)(adres)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001 — arayüz tarayıcı penceresine düşer
            _gunluk.warning("Tarayıcı açılamadı: %s", exc)
            return {"ok": False, "hata": "Tarayıcı açılamadı."}

    def excel_ac(self, dosya_adi: str, icerik_b64: str) -> dict:
        try:
            yol = excel_dosyasi_yaz(self._klasor or yollar.KABUK / "tmp", dosya_adi, icerik_b64)
            (self._ac or os.startfile)(str(yol))                # Windows: .xlsx → Excel
            _gunluk.info("Excel'de açıldı: %s", yol.name)
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001 — arayüz indirmeye düşer
            _gunluk.warning("Excel açılamadı: %s", exc)
            return {"ok": False, "hata": "Excel açılamadı; dosya indirilecek."}


# ============================================================================ durum
class Durum:
    def __init__(self) -> None:
        self.asama = "Açılıyor…"
        self.ayrinti = ""
        self.hata: str | None = None
        self.hazir = threading.Event()
        self.cikiliyor = threading.Event()
        self.sunucu = None                                      # uvicorn.Server
        self.sunucu_isi: threading.Thread | None = None
        self.t0 = time.perf_counter()
        self.pencere = None
        self.hwnd = 0
        self.dinleyiciler: list = []
        self.tepsi = None                                       # pystray.Icon
        self.cizelge: dict[str, float] = {}                     # açılış adımı → saniye (D.t0'dan)
        self.gosterildi = threading.Event()

    def an(self, ad: str) -> None:
        """Açılış zaman çizelgesine adım (ilk kez olanı)."""
        if ad not in self.cizelge:
            self.cizelge[ad] = round(time.perf_counter() - self.t0, 2)
            _gunluk.info("Açılış · %s (%.2f sn)", ad, self.cizelge[ad])

    def cizelge_yaz(self) -> None:
        _gunluk.info("Açılış zaman çizelgesi: %s", " → ".join(f"{a} {t:.2f}" for a, t in self.cizelge.items()))

    def degisti(self, asama: str | None = None, ayrinti: str = "", hata: str | None = None) -> None:
        if asama:
            self.asama = asama
        self.ayrinti = ayrinti
        if hata:
            self.hata = hata
            _gunluk.error("%s", hata)
        else:
            _gunluk.info("%s %s", self.asama, ayrinti)
        for f in list(self.dinleyiciler):
            try:
                f()
            except Exception:  # noqa: BLE001 — pencere kapanmış olabilir
                pass


D = Durum()


def surum() -> str:
    try:
        from saha import SURUM
        return str(SURUM)
    except Exception:  # noqa: BLE001
        return ""


def lan_adresi() -> str:
    try:
        from saha.sunucu import yerel_ipler
        ip = yerel_ipler()[0]
    except Exception:  # noqa: BLE001
        ip = "127.0.0.1"
    if HOST not in ("0.0.0.0", "::"):
        ip = HOST
    return f"http://{ip}:{PORT}"


# ============================================================================ sunucu
def _veritabani_hazirla(sunucu_mod) -> bool:
    """Devir (bir kez) → ilk kurulum (hiç veri yoksa). False: pencerede açıklanan bir engel var."""
    from masaustu import devir

    # Yalnız exe'nin kendi canlı klasörüne (veri/canli) devralınır: deneme/geliştirme klasörüne gerçek veri gelmez.
    if yollar.CALISMA == yollar.MASAUSTU_VERI and devir.gerekli_mi(yollar.CANLI / "surum", yollar.CALISMA):
        D.degisti("Eski sürümün verisi taşınıyor…", "Doğrulanmış kopya alınıyor; eski klasöre dokunulmaz.")
        try:
            sonuc = devir.devral(yollar.CANLI / "surum", yollar.CALISMA, sunucu_mod.port_dolu_mu)
        except Exception as exc:  # noqa: BLE001
            _gunluk.exception("Devir")
            D.degisti(hata=f"Eski sürümün verisi taşınamadı; hiçbir şey değişmedi. ({exc})")
            return False
        if sonuc.durum == "eski_surum_acik":
            D.degisti(hata="Eski sürüm açık; kapatıp Turkcell'i yeniden açın.")
            return False
        D.degisti(ayrinti=sonuc.mesaj)

    from saha import ayarlar

    if not Path(ayarlar.DB_YOLU).exists():
        yedekler = list((Path(ayarlar.DB_YOLU).parent / "yedek").glob("saha-*.db"))
        if yedekler:
            D.degisti(hata=f"Veritabanı bulunamadı ama {len(yedekler)} yedek var: yeni ve boş bir veritabanı "
                           f"KURULMADI. Yedek klasörü: {Path(ayarlar.DB_YOLU).parent / 'yedek'}")
            return False
        D.degisti("İlk kurulum…", "Binalar yükleniyor; bir dakikadan kısa sürer.")
        from saha import kur
        if int(kur.main([]) or 0) != 0:
            D.degisti(hata="İlk kurulum tamamlanamadı. Ayrıntı: .turkcell\\kayit\\turkcell.log")
            return False
    return True


def sunucuyu_calistir() -> None:
    try:
        D.degisti("Hazırlanıyor…")
        from saha import sunucu as s

        if s.port_dolu_mu(PORT):
            D.degisti(hata=f"{PORT} numaralı port kullanımda. Eski sürüm (ya da başka bir sunucu) açık olabilir: "
                           f"onu kapatıp Turkcell'i yeniden açın.")
            return
        if not _veritabani_hazirla(s):
            return
        s.kaydi_kur("info")                                     # saha/kayit/saha.log (dönüşümlü)
        kok = logging.getLogger()
        for h in list(kok.handlers):                            # konsol yok: saha'nın konsol kopyası kabuk
            if type(h) is logging.StreamHandler:                # günlüğüne ikinci kez yazmasın; yalnız kabuk
                kok.removeHandler(h)                            # kayıtları (turkcell.*) orada kalsın
        _gunluk.addHandler(_kabuk_isleyici())                   # kaydi_kur kök işleyicileri sildi
        D.degisti("Veritabanı denetleniyor…")
        if not s._veritabani_kontrol():
            D.degisti(hata="Veritabanı okunamadı. Ayrıntı: saha\\kayit\\saha.log")
            return
        if not s._guncelle():
            D.degisti(hata="Veritabanı güncellemesi durdu — veriniz korundu. Ayrıntı: saha\\kayit\\saha.log")
            return
        D.degisti("Sunucu açılıyor…")
        import uvicorn
        from saha.api import uygulama

        D.sunucu = uvicorn.Server(uvicorn.Config(uygulama, host=HOST, port=PORT, log_level="info",
                                                 access_log=True, log_config=None, timeout_graceful_shutdown=3))
        D.sunucu.run()
        if not D.cikiliyor.is_set():
            D.degisti(hata="Sunucu beklenmedik şekilde kapandı. Ayrıntı: saha\\kayit\\saha.log")
    except BaseException as exc:  # noqa: BLE001 — uvicorn bağlanamazsa SystemExit atar
        _gunluk.error("Sunucu: %s\n%s", exc, traceback.format_exc())
        if not D.cikiliyor.is_set():
            D.degisti(hata=f"Sunucu açılamadı: {exc}" if str(exc) not in ("", "1") else
                      f"Sunucu açılamadı ({PORT} kullanımda olabilir). Ayrıntı: saha\\kayit\\saha.log")


def isit() -> None:
    """Sunucunun ağır kütüphanelerini (pandas, openpyxl, bölge planlayıcı) pencere kurulurken ayrı iş parçacığında
    yükler: sunucu iş parçacığı devir/göç denetimindeyken (çoğu disk beklemesi) içe aktarma ilerler."""
    t = time.perf_counter()
    for ad in ("pandas", "openpyxl", "fastapi", "dsale.metrics", "dsale.partition", "shapely"):
        try:
            __import__(ad)
        except Exception:  # noqa: BLE001 — sunucu kendi hatasını verir
            pass
    _gunluk.info("Isınma bitti (%.2f sn)", time.perf_counter() - t)


def saglik_bekle() -> None:
    adres = f"http://127.0.0.1:{PORT}/api/saglik"
    while not D.cikiliyor.is_set() and not D.hata:
        # Uvicorn dinlemeye başlamadan bağlanmayı denemek boşa: Windows'ta kapalı porta bağlanma ~0,5 sn sürer.
        if D.sunucu is None or not getattr(D.sunucu, "started", False):
            time.sleep(0.05)
            continue
        try:
            with urllib.request.urlopen(adres, timeout=2) as y:
                if y.status == 200:
                    sure = time.perf_counter() - D.t0
                    _gunluk.info("Hazır: /api/saglik 200 (%.2f sn)", sure)
                    D.an("sunucu_hazir")
                    # açılış ekranı görünmeden uygulamaya geçilmez (gizli pencerede yüklenen sayfa ilk boyamayı
                    # pencere görünür olunca yapar; açılış ekranı hep ilk görünen şeydir)
                    D.gosterildi.wait(35)
                    D.hazir.set()
                    if D.pencere is not None:
                        D.an("uygulamaya_gecis")
                        D.pencere.load_url(f"http://127.0.0.1:{PORT}/")
                    return
        except Exception:  # noqa: BLE001 — henüz açılmadı
            pass
        time.sleep(0.1)


def gunluk_yedek() -> None:
    """Günde bir doğrulanmış yedek (``saha/yedek/saha-AAAA-AA-GG.db``); ilk denetim 60 sn sonra, sonra saatte bir."""
    if D.cikiliyor.wait(60):
        return
    while True:
        try:
            from saha import ayarlar, yedekle
            if D.hazir.is_set() and not (yedekle.YEDEK_DIZINI / f"saha-{ayarlar.bugun():%Y-%m-%d}.db").exists():
                _gunluk.info("Günlük yedek: kod %s", yedekle.main([]))
        except BaseException as exc:  # noqa: BLE001
            _gunluk.warning("Günlük yedek alınamadı: %s", exc)
        if D.cikiliyor.wait(3600):
            return


# ============================================================================ açılış ekranı
def acilis_html(koyu: bool) -> str:
    try:
        logo = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    except OSError:
        logo = ""
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>{AD}</title>
<style>
:root{{--zemin:#f5f5f5;--yazi:#242424;--soluk:#616161;--iz:rgba(0,0,0,.08);--sari:#FEC600;--hata:#b10e1c}}
@media (prefers-color-scheme:dark){{:root{{--zemin:#1f1f1f;--yazi:#ffffff;--soluk:#adadad;--iz:rgba(255,255,255,.12);--hata:#dc626d}}}}
html,body{{margin:0;height:100%;background:var(--zemin);color:var(--yazi);
 font-family:"Segoe UI Variable Text","Segoe UI",system-ui,sans-serif;-webkit-user-select:none;user-select:none;cursor:default}}
main{{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px}}
img{{width:64px;height:64px;object-fit:contain;animation:gir .5s cubic-bezier(0,0,0,1) both}}
h1{{margin:0;font-size:20px;font-weight:600;letter-spacing:-.01em;animation:gir .5s .05s cubic-bezier(0,0,0,1) both}}
.cubuk{{width:160px;height:2px;border-radius:2px;background:var(--iz);overflow:hidden}}
.cubuk i{{display:block;width:40%;height:100%;border-radius:2px;background:var(--sari);animation:kay 1.2s cubic-bezier(.4,0,.2,1) infinite}}
p{{margin:0;min-height:1.3em;font-size:12px;color:var(--soluk);text-align:center;max-width:560px;line-height:1.45}}
.hata .cubuk{{display:none}} .hata p#asama{{color:var(--hata);font-size:14px;font-weight:600}}
@keyframes gir{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
@keyframes kay{{from{{transform:translateX(-110%)}}to{{transform:translateX(260%)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style></head><body><main id="kok">
<img src="{logo}" alt=""><h1>{AD}</h1><div class="cubuk"><i></i></div>
<p id="asama">Açılıyor…</p><p id="ayrinti"></p></main>
<script>
function durum(d){{document.getElementById('asama').textContent=d.hata||d.asama;
 document.getElementById('ayrinti').textContent=d.hata?'':(d.ayrinti||'');
 document.getElementById('kok').classList.toggle('hata',!!d.hata);}}
</script></body></html>"""


# ============================================================================ pencere + bildirim alanı
def pencereyi_one_getir() -> None:
    w = D.pencere
    if w is None:
        return
    try:
        w.show()
        w.restore()
    except Exception:  # noqa: BLE001
        pass
    if D.hwnd:
        _u32.ShowWindow(D.hwnd, 9)                              # SW_RESTORE
        _u32.SetForegroundWindow(D.hwnd)


def olaylari_dinle() -> None:
    ac = _k32.CreateEventW(None, False, False, OLAY_AC)
    kapat = _k32.CreateEventW(None, False, False, OLAY_KAPAT)
    dizi = (wintypes.HANDLE * 2)(ac, kapat)
    while not D.cikiliyor.is_set():
        r = _k32.WaitForMultipleObjects(2, dizi, False, 500)
        if r == 0:
            pencereyi_one_getir()
        elif r == 1:
            cikis()
            return


def cikis(*_a) -> None:
    if D.cikiliyor.is_set():
        return
    D.cikiliyor.set()
    _gunluk.info("Çıkış: sunucu düzgün kapatılıyor")
    if D.tepsi is not None:                                     # önce görünenler gitsin
        try:
            D.tepsi.stop()
        except Exception:  # noqa: BLE001
            pass
    if D.pencere is not None:
        try:
            D.pencere.hide()
        except Exception:  # noqa: BLE001
            pass
    if D.sunucu is not None:
        D.sunucu.should_exit = True                             # açık istekler biter (en çok 3 sn), SQLite kapanır
    if D.sunucu_isi is not None:
        D.sunucu_isi.join(timeout=15)
    if D.pencere is not None:
        try:
            D.pencere.destroy()
        except Exception:  # noqa: BLE001
            pass
    else:
        os._exit(0)



def tepsi_kur() -> None:
    try:
        import pystray
        from PIL import Image
    except ImportError as exc:
        _gunluk.warning("Bildirim alanı simgesi yok: %s", exc)
        return

    def adres_metni(_m=None) -> str:
        return f"Telefonlar için adres: {lan_adresi()}"

    def kopyala(_i=None, _m=None) -> None:
        panoya_kopyala(lan_adresi())

    menu = pystray.Menu(
        pystray.MenuItem("Aç", lambda *_: pencereyi_one_getir(), default=True),
        pystray.MenuItem(adres_metni, kopyala),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Çıkış", cikis),
    )
    ipucu = f"{AD} {surum()}".strip()
    D.tepsi = pystray.Icon("Turkcell", Image.open(IKON), ipucu, menu)
    threading.Thread(target=D.tepsi.run, name="tepsi", daemon=True).start()


def vekil_ulasilamaz(sure: float = 1.0) -> bool:
    """Windows'ta otomatik vekil betiği (AutoConfigURL) tanımlı ama sunucusuna ulaşılamıyorsa True. Ulaşılamayan
    betikte Chromium zaten doğrudan bağlanır; yalnız önce saniyelerce bekler. Ulaşılabiliyorsa vekil ayarına dokunulmaz."""
    try:
        import socket
        import winreg
        from urllib.parse import urlparse
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as a:
            adres = winreg.QueryValueEx(a, "AutoConfigURL")[0]
    except OSError:
        return False
    u = urlparse(str(adres or ""))
    if not u.hostname:
        return False
    sonuc = {"ulasti": False}

    def dene() -> None:
        try:
            with socket.create_connection((u.hostname, u.port or 80), timeout=sure):
                sonuc["ulasti"] = True
        except OSError:
            pass

    t = threading.Thread(target=dene, daemon=True)
    t.start()
    t.join(sure + 0.2)                                  # DNS takılırsa da en çok ~1 sn beklenir
    if not sonuc["ulasti"]:
        _gunluk.info("Vekil betiği sunucusuna ulaşılamadı (%s): WebView2 doğrudan bağlanacak", u.hostname)
    return not sonuc["ulasti"]


def yerli_perde(form, koyu: bool):
    """WinForms paneli: pencerenin ilk karesinden itibaren açılış görünümü (WebView2'nin kara yüzeyini örter).
    UI iş parçacığında çağrılır (before_show). Dönüş: paneli kaldıran işlev (UI iş parçacığına kendisi geçer)."""
    import clr  # noqa: F401 — pythonnet (pywebview yükledi)
    from System import Action
    from System.Drawing import Color, ColorTranslator, Font, FontStyle, Image, Point, Size
    from System.Windows.Forms import DockStyle, Label, Panel, PictureBox, PictureBoxSizeMode

    zemin = ColorTranslator.FromHtml(ZEMIN_KOYU if koyu else ZEMIN_ACIK)
    yazi = Color.White if koyu else ColorTranslator.FromHtml("#242424")
    panel = Panel()
    panel.Dock = DockStyle.Fill
    panel.BackColor = zemin
    resim = PictureBox()
    resim.Size = Size(64, 64)
    resim.SizeMode = PictureBoxSizeMode.Zoom
    resim.BackColor = zemin
    try:
        resim.Image = Image.FromFile(str(LOGO))
    except Exception:  # noqa: BLE001
        pass
    ad = Label()
    ad.Text = AD
    ad.AutoSize = True
    ad.ForeColor = yazi
    ad.BackColor = zemin
    ad.Font = Font("Segoe UI Semibold", 15.0, FontStyle.Regular)
    panel.Controls.Add(resim)
    panel.Controls.Add(ad)

    def ortala(*_):
        w, h = panel.ClientSize.Width, panel.ClientSize.Height
        ust = int(h / 2) - 52
        resim.Location = Point(int((w - 64) / 2), ust)
        ad.Location = Point(int((w - ad.PreferredWidth) / 2), ust + 64 + 14)

    panel.Resize += ortala
    form.Controls.Add(panel)
    panel.BringToFront()
    ortala()

    def kaldir() -> None:
        def yap():
            try:
                form.Controls.Remove(panel)
                panel.Dispose()
            except Exception:  # noqa: BLE001
                pass
        try:
            if form.InvokeRequired:
                form.Invoke(Action(yap))
            else:
                yap()
        except Exception as exc:  # noqa: BLE001
            _gunluk.warning("Yerli açılış perdesi kaldırılamadı: %s", exc)

    return kaldir


def _webview_ayarla(webview) -> None:
    """Tarayıcı kısayolları (Ctrl+F bul, Ctrl+P yazdır, yakınlaştırma) ve sağ tık menüsü açık;
    geliştirici araçları kapalı. İndirmeler kaydetme penceresiyle."""
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        from webview.platforms import edgechromium

        eski = edgechromium.EdgeChrome.on_webview_ready

        def hazir(self, sender, args):
            D.an("webview_hazir")
            eski(self, sender, args)
            try:
                a = sender.CoreWebView2.Settings
                a.AreBrowserAcceleratorKeysEnabled = True
                a.AreDefaultContextMenusEnabled = True
            except Exception:  # noqa: BLE001
                pass
            try:                                       # yerel sunucuya geçişte SmartScreen denetimi beklenmesin
                sender.CoreWebView2.Settings.IsReputationCheckingRequired = False
            except Exception:  # noqa: BLE001 — eski WebView2 SDK'sında yok
                pass

        eski_bas = edgechromium.EdgeChrome.on_navigation_start
        eski_bit = edgechromium.EdgeChrome.on_navigation_completed

        def gezinme_bas(self, sender, args):
            if D.hazir.is_set():
                D.an("uygulama_istendi")
            return eski_bas(self, sender, args)

        def gezinme_bit(self, sender, args):
            if D.hazir.is_set():
                D.an("uygulama_gezinme_bitti")
            return eski_bit(self, sender, args)

        edgechromium.EdgeChrome.on_webview_ready = hazir
        edgechromium.EdgeChrome.on_navigation_start = gezinme_bas
        edgechromium.EdgeChrome.on_navigation_completed = gezinme_bit
    except Exception as exc:  # noqa: BLE001
        _gunluk.warning("WebView2 ayarları uygulanamadı: %s", exc)


def main() -> int:
    if "--kapat" in sys.argv:
        tek_ornek()                                             # açık örnek varsa ona "kapat" der
        return 0
    kilit = tek_ornek()
    if kilit is None:
        return 0
    uygulama_kimligi()
    kok = gizli_klasor_hazirla()
    gunlugu_kur(kok)
    _gunluk.info("--- %s %s · veri %s · %s:%s", AD, surum(), yollar.CALISMA, HOST, PORT)

    vekil: dict = {}                                    # vekil betiği denetimi pencereyle paralel (DNS bekletmesin)
    vekil_isi = threading.Thread(target=lambda: vekil.update(yok=vekil_ulasilamaz()), name="vekil", daemon=True)
    vekil_isi.start()
    D.sunucu_isi = threading.Thread(target=sunucuyu_calistir, name="sunucu", daemon=True)
    D.sunucu_isi.start()                                        # pencereyle aynı anda ısınsın
    threading.Thread(target=saglik_bekle, name="saglik", daemon=True).start()
    threading.Thread(target=olaylari_dinle, name="olaylar", daemon=True).start()
    threading.Thread(target=gunluk_yedek, name="yedek", daemon=True).start()

    # Kara ekran olmasın: WebView2 tarayıcı süreci açılırken (soğuk açılışta birkaç saniye) ve sayfa geçişlerinde
    # kendi varsayılan zeminini boyar. Zemin rengi uygulamanın --zemin'i (stil/tokenlar.css) ile aynı; ortam
    # değişkeni denetim oluşturulmadan ÖNCE verilmeli (DefaultBackgroundColor özelliği ancak çekirdek kurulunca işler).
    koyu = koyu_tema()
    zemin = ZEMIN_KOYU if koyu else ZEMIN_ACIK
    os.environ["WEBVIEW2_DEFAULT_BACKGROUND_COLOR"] = "FF" + zemin.lstrip("#").upper()

    import webview

    _gunluk.info("WebView2 zemin rengi: %s (WEBVIEW2_DEFAULT_BACKGROUND_COLOR=%s)", zemin,
                 os.environ.get("WEBVIEW2_DEFAULT_BACKGROUND_COLOR"))
    _webview_ayarla(webview)
    # Pencere hemen görünür; ilk karesinden itibaren YERLİ açılış perdesi (before_show, UI iş parçacığı) WebView2'nin
    # üstünü örter. Gömülü HTML açılış ekranı yüklenip boyanınca perde kalkar (yuklendi → goster).
    pencere = webview.create_window(
        AD, html=acilis_html(koyu), width=1360, height=900, min_size=(980, 640),
        background_color=zemin, text_select=True, js_api=KabukApi())
    perde = {"kaldir": None}

    def gosterilecek(window) -> None:                    # before_show: senkron, UI iş parçacığında
        try:
            perde["kaldir"] = yerli_perde(window.native, koyu)
            D.an("yerli_perde")
        except Exception as exc:  # noqa: BLE001 — perde yoksa HTML açılış ekranı yine gelir
            _gunluk.warning("Yerli açılış perdesi kurulamadı: %s", exc)

    def ilk_gorunus() -> None:                           # shown: pencere ekranda (yerli perdeyle)
        try:
            D.hwnd = int(pencere.native.Handle.ToInt64())
            pencereyi_susle(D.hwnd, koyu)
        except Exception as exc:  # noqa: BLE001
            _gunluk.warning("Pencere süslenemedi: %s", exc)
        if D.hwnd and not _u32.IsWindowVisible(D.hwnd) and not D.cikiliyor.is_set():
            # Gizli bir süreçten (görev zamanlayıcı, kurulum sihirbazı) başlatılınca Windows İLK ShowWindow'u
            # STARTUPINFO'daki SW_HIDE ile ezer; ikinci çağrı pencereyi gerçekten gösterir.
            _u32.ShowWindow(D.hwnd, 5)                          # SW_SHOW
        D.an("pencere_gorundu")
        # Ağır kütüphaneler pencere göründükten SONRA ısınır: GIL'i pencere/WebView2 kurulumuyla paylaşmasın.
        if not any(t.name == "isit" for t in threading.enumerate()) and not D.hazir.is_set():
            threading.Thread(target=isit, name="isit", daemon=True).start()
    D.pencere = pencere

    def durum_yay() -> None:
        if not D.hazir.is_set():
            pencere.evaluate_js(f"durum({json.dumps({'asama': D.asama, 'ayrinti': D.ayrinti, 'hata': D.hata})})")

    def goster() -> None:
        """HTML açılış ekranı boyandı: yerli perde kalkar (bir kez); uygulamaya geçiş bundan sonra."""
        if D.gosterildi.is_set() or D.cikiliyor.is_set():
            return
        if perde["kaldir"]:
            perde["kaldir"]()
        D.an("html_acilis_gorundu")
        D.gosterildi.set()

    def yuklendi() -> None:
        if not D.gosterildi.is_set():                      # 1) gömülü açılış ekranı yüklendi
            D.an("acilis_ekrani_yuklendi")
            D.dinleyiciler.append(durum_yay)
            durum_yay()
            try:                                           # iki kare bekle: sayfa gerçekten boyansın
                pencere.evaluate_js("new Promise(function(r){requestAnimationFrame(function(){"
                                    "requestAnimationFrame(function(){r(1)})})})")
            except Exception:  # noqa: BLE001
                time.sleep(0.05)
            D.an("acilis_ekrani_boyandi")
            goster()
            return
        if D.hazir.is_set():                               # 2) uygulama sayfası yüklendi (perdesi ilk veriye dek)
            D.an("uygulama_yuklendi")
            if D.dinleyiciler:
                D.dinleyiciler.clear()

    def guvence() -> None:
        """HTML açılış ekranı yüklenmezse de (WebView2 sorunu) en geç 30 sn sonra perde kalkar, uygulamaya geçilir."""
        if not D.gosterildi.wait(30):
            _gunluk.warning("Açılış ekranı 30 sn'de yüklenmedi; yerli perde kaldırılıyor")
            goster()

    def kapaniyor():
        if D.cikiliyor.is_set():
            return True
        _gunluk.info("Pencere gizlendi; sunucu çalışmaya devam ediyor")
        threading.Thread(target=pencere.hide, daemon=True).start()   # sunucu çalışmaya devam eder
        return False

    pencere.events.before_show += gosterilecek
    pencere.events.shown += ilk_gorunus
    pencere.events.loaded += yuklendi
    threading.Thread(target=guvence, name="guvence", daemon=True).start()
    pencere.events.closing += kapaniyor
    # Uygulama yerel sunucudan açılır: SmartScreen (ağ denetimi) ve ulaşılamayan vekil betiği (WPAD/PAC) ilk
    # gezinmeyi bekletmesin (ofis dışında wpad.dat'a ulaşılamayınca WebView2 ilk isteği ~11 sn bekletiyordu).
    argumanlar = ["--disable-features=msSmartScreenProtection"]
    vekil_isi.join(1.5)
    if vekil.get("yok"):
        argumanlar.append("--no-proxy-server")
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", " ".join(argumanlar))
    _gunluk.info("WebView2 argümanları: %s", os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"))
    tepsi_kur()
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(kok / "webview"), debug=False,
                  icon=str(IKON), localization={"windows.fileFilter.allFiles": "Tüm dosyalar",
                                                "global.saveFile": "Kaydet"})
    cikis()
    _gunluk.info("Kapandı")
    # Sunucu durdu, veritabanı kapandı. .NET/WebView2/pystray'in yorumlayıcı kapanışı ~8 sn sürüyor; beklemeden çık.
    logging.shutdown()
    for akis in (sys.stdout, sys.stderr):
        try:
            akis.flush()
        except (AttributeError, OSError, ValueError):
            pass
    os._exit(0)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    sys.exit(main())
