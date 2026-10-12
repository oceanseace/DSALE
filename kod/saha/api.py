"""Turkcell API — FastAPI.

Tek süreç hem API'yi hem PWA'yı sunar:
    /api/...        JSON uçları (Bearer jeton)
    /               kod/arayuz/dist (derlenmiş PWA)

Hata biçimi her yerde ``{"hata": "...", "kod": "..."}``; HTTP 401 alan uygulama
giriş ekranına döner. Bütün metinler Türkçedir.

Yetki (spec §2 + Ek-1): her uç ``Depends(izin("eylem"))`` ile kendi eylemini ister
(``saha/yetki.py``; varsayılan YASAK, izinler görev kümesinin birleşimi). Göç bu dosyada
YAPILMAZ: ``saha/sunucu.py`` port denetiminden sonra ``goc.hazirla`` çağırır; burada yalnız
sürüm denetlenir (uyumsuzsa v2 uçları 503 ``guncelleme_bekliyor``, eski uçlar çalışır).

Uçlar birimlere bölünmüştür (bir değişiklik tek dosyaya dokunsun): ``giris_uclari`` (giriş, PIN, ben),
``satis_uclari`` (Saha), ``ekip_uclari`` (Yönetim: Ekip), ``yonetim_uclari`` (Faz 2); ortak yardımcılar
``api_ortak``'tadır. Bu dosyada uygulama, hata biçimi, ara katman, sağlık, PWA ve bağlama kalır.
"""
from __future__ import annotations

import contextlib
import importlib
import importlib.util
import logging
import os
import shutil
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import (SURUM, altlik, ayarlar, boss_giris, db, ekip_uclari, giris_uclari, goc, satis_uclari, veri_kalitesi,
               yetki, yonetim_uclari)
from .api_ortak import _demo_kurulu
from .yetki import Bagimliliklar, baglanti, hata

_gunluk = logging.getLogger("saha.api")

# Sürüm uyumsuzsa (uvicorn doğrudan eski bir veritabanıyla açıldı) v2 uçları 503 döner.
GUNCELLEME_BEKLIYOR = False
# v2 yönlendiricileri yüklenemediyse nedeni (sağlık ucunda uyarı olarak görünür).
V2_YUKLEME_HATASI: str | None = None


@contextlib.asynccontextmanager
async def _yasam_dongusu(_uygulama: FastAPI):
    """Açılış: sürüm denetimi (göç YOK), veri kalitesi, ağır modüller, harita önbelleği."""
    _veritabanini_hazirla()
    # Ağır modüller (shapely, dsale) ve harita önbelleği arka planda ısınır: /api/saglik bunları
    # beklemez (masaüstü açılış süresi). İlgili uç erken gelirse modülü kendisi yükler/hesaplar.
    threading.Thread(target=_arka_plan_isit, name="saha-isit", daemon=True).start()
    capa = _capa_ac()
    try:
        yield
    finally:
        if capa is not None:
            capa.close()


def _capa_ac() -> sqlite3.Connection | None:
    """Sunucu açık kaldıkça tutulan, işlemsiz, boşta duran tek bağlantı.

    Her istek kendi bağlantısını açıp kapatır; açık başka bağlantı yoksa SQLite her kapanışta WAL'ı
    diske işleyip -wal dosyasını siler (fsync, Windows'ta istek başına ≈30 ms). Bu çapa o işi sunucu
    kapanışına bırakır; WAL yine 1000 sayfada kendiliğinden işlenir. Hiçbir kilit tutmaz.
    """
    yol = db.db_yolu()
    if not yol.exists():
        return None
    try:
        capa = sqlite3.connect(yol, check_same_thread=False)
        capa.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        return capa
    except sqlite3.Error as exc:
        _gunluk.warning("Çapa bağlantısı açılamadı (istekler biraz yavaş olur): %s", exc)
        return None


uygulama = FastAPI(
    lifespan=_yasam_dongusu,
    title="Turkcell",
    version=SURUM,
    description="Turkcell bayi iş akışı: görev, ziyaret, iş emri ve kapsama takibi.",
    # Swagger arayüzü ve şema ÜRETİMDE KAPALI: ağdaki herkese iç API yüzeyini
    # göstermemeli ve Swagger'ın JS/CSS'ini cdn.jsdelivr.net'ten çekmemeli
    # (çalışma anında harici kaynak yok kuralı). Açmak için: SAHA_GELISTIRME=1
    docs_url="/api/belge" if ayarlar.GELISTIRME else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if ayarlar.GELISTIRME else None,
)
app = uygulama  # uvicorn saha.api:app

# Ofis wifi'si üzerinden telefona giden her şey sıkıştırılır. En çok işe yarayan
# yerler: uygulama paketi (JS/CSS) ve 19.706 noktalık /api/harita yanıtı.
# Seviye 3 bilinçli: 1,4 MB harita yanıtında 6. seviyeye göre 12 KB daha büyük
# ama 22 ms daha hızlı — ofis ağında kazanan taraf hız.
uygulama.add_middleware(GZipMiddleware, minimum_size=900, compresslevel=3)


# ============================================================================= hatalar
@uygulama.exception_handler(StarletteHTTPException)
async def _http_hata(_istek: Request, exc: StarletteHTTPException):
    icerik = exc.detail
    if not isinstance(icerik, dict) or "hata" not in icerik:
        varsayilan = {
            400: ("İstek okunamadı (bozuk veri ya da karakter kodlaması). Tekrar deneyin.", "istek_bozuk"),
            401: ("Oturum gerekli.", "yetkisiz"),
            403: ("Bu işlem için yetkiniz yok.", "yasak"),
            404: ("Kayıt bulunamadı.", "bulunamadi"),
            405: ("Bu istek desteklenmiyor.", "yontem_yok"),
        }.get(exc.status_code, ("Beklenmeyen bir hata oluştu.", "hata"))
        icerik = {"hata": varsayilan[0], "kod": varsayilan[1]}
    return JSONResponse(icerik, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@uygulama.exception_handler(sqlite3.IntegrityError)
async def _butunluk_hatasi(_istek: Request, exc: sqlite3.IntegrityError):
    """Yabancı anahtar / tekillik ihlali bir KULLANICI durumudur, sunucu arızası değil (spec §2.4-4).

    Ör. üstünde iş olan kişiyi silmek: 503 "sunucu yazamıyor" yerine 409 ve anlaşılır cümle.
    """
    _gunluk.warning("Bütünlük hatası: %s", exc)
    return JSONResponse(
        {"hata": "Bu kayıt başka kayıtlarla bağlantılı olduğu için değiştirilemedi.", "kod": "butunluk"},
        status_code=409,
    )


@uygulama.exception_handler(sqlite3.Error)
async def _veritabani_hatasi(_istek: Request, exc: sqlite3.Error):
    """Disk dolduğunda / veritabanı kilitli kaldığında Türkçe konuş.

    Eskiden bu durumda uvicorn düz İngilizce "Internal Server Error" döndürüyor,
    satışçı "Bir şeyler ters gitti" görüyor, yönetici hiçbir şey görmüyordu.
    """
    logging.getLogger("saha.api").error("Veritabanı hatası: %s", exc)
    return JSONResponse(
        {"hata": "Sunucu şu an kayıt yazamıyor. Kaydınız telefonunuzda duruyor, "
                 "lütfen BT'ye haber verin.", "kod": "yazilamiyor"},
        status_code=503,
    )


@uygulama.exception_handler(Exception)
async def _beklenmeyen_hata(_istek: Request, exc: Exception):
    logging.getLogger("saha.api").exception("Beklenmeyen hata: %s", exc)
    return JSONResponse(
        {"hata": "Sunucuda beklenmeyen bir hata oluştu. Kaydınız telefonunuzda "
                 "duruyor; tekrar denenecek.", "kod": "sunucu_hatasi"},
        status_code=500,
    )


@uygulama.exception_handler(RequestValidationError)
async def _dogrulama_hatasi(_istek: Request, exc: RequestValidationError):
    ilk = (exc.errors() or [{}])[0]
    alan = ".".join(str(p) for p in ilk.get("loc", ()) if p not in ("body", "query", "path"))
    mesaj = "Gönderilen bilgiler eksik veya geçersiz."
    if alan:
        mesaj = f"{mesaj} Kontrol edin: {alan}"
    return JSONResponse({"hata": mesaj, "kod": "gecersiz_veri"}, 422)


# ============================================================================= sağlık
# Yazma denemesi başarılıysa 30 sn yeniden yapılmaz ve yazma kilidinde BEKLEMEZ: rapor aktarımı kilidi
# tutarken sağlık ucu sıraya girmemeli (spec §5.6: aktarım sırasında /api/saglik < 300 ms). Kilit başkasında
# demek dosya yazılabilir demektir. Başarısız deneme saklanmaz: düzelince hemen görünür.
_YAZMA_ARALIGI_SN = 30.0
_son_yazma: dict = {"yol": None, "zaman": 0.0}


def _yazma_denemesi(conn: sqlite3.Connection) -> tuple[bool, str | None]:
    yol, simdi = str(db.db_yolu()), time.monotonic()
    if _son_yazma["yol"] == yol and simdi - _son_yazma["zaman"] < _YAZMA_ARALIGI_SN:
        return True, None
    conn.execute("PRAGMA busy_timeout=100")
    try:
        db.ayar_yaz(conn, "saglik_kontrol", ayarlar.zaman_metni())
        conn.commit()
    except sqlite3.OperationalError as exc:
        if conn.in_transaction:
            conn.rollback()
        if "locked" in str(exc) or "busy" in str(exc):
            return True, None                     # başka biri yazıyor: dosya yazılabilir
        return False, f"Veritabanına yazılamıyor ({exc}). Disk dolu olabilir; BT'ye haber verin."
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.rollback()
        return False, f"Veritabanına yazılamıyor ({exc}). Disk dolu olabilir; BT'ye haber verin."
    finally:
        conn.execute("PRAGMA busy_timeout=15000")
    _son_yazma.update(yol=yol, zaman=simdi)
    return True, None


@uygulama.get("/api/saglik")
def saglik(conn: sqlite3.Connection = Depends(baglanti)):
    try:
        bina = conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
        kullanici = conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0]
    except sqlite3.Error:
        raise hata(503, "Veritabanı hazır değil. Önce 'python -m saha.kur' çalıştırın.", "veritabani_yok")

    # OKUMAK YETMEZ: disk dolduğunda ya da dosya salt-okunur olduğunda okumalar
    # çalışmaya devam eder ve sağlık ucu "her şey yolunda" der. Küçük bir yazma
    # denemesi gerçeği söyler; yönetici konsolu bunu kırmızı şerit olarak gösterir.
    yazilabilir, uyari = _yazma_denemesi(conn)

    bos_mb = None
    try:
        bos_mb = int(shutil.disk_usage(db.db_yolu().parent).free / (1024 * 1024))
        if yazilabilir and bos_mb < 200:
            uyari = f"Diskte yalnız {bos_mb} MB yer kaldı. Yer açılmazsa kayıtlar durur."
    except OSError:
        pass

    if not uyari and V2_YUKLEME_HATASI:
        uyari = "İş emri modülü yüklenemedi; satış uygulaması çalışıyor. Günlüğü BT'ye iletin."
    return {"ok": yazilabilir, "surum": SURUM, "zaman": ayarlar.zaman_metni(), "bina": bina,
            "sema_surumu": goc.user_version(conn), "guncelleme_bekliyor": GUNCELLEME_BEKLIYOR,
            "kullanici": kullanici, "demo": _demo_kurulu(conn),
            # Giriş ekranındaki "Yöneticini ara" satırı buradan beslenir.
            # Takılan satışçının tek çaresi WhatsApp'a dönmek olmamalı.
            "yardim_telefon": db.ayar_oku(conn, "yardim_telefon"),
            "yardim_ad": db.ayar_oku(conn, "yardim_ad"),
            "yazilabilir": yazilabilir, "bos_disk_mb": bos_mb, "uyari": uyari,
            # Etkin bölge planının N'i (8 → 14 ekip). Arayüz sabit 8 varsaymamalı.
            "bolge_sayisi": db.bolge_sayisi(conn),
            "etiketler": {"sonuc": ayarlar.SONUC_ETIKET, "sonuc_saha": ayarlar.SONUC_ETIKET_SAHA,
                          "durum": ayarlar.DURUM_ETIKET}}


# ============================================================================= PWA
class TekSayfa(StaticFiles):
    """PWA yönlendirmeleri (``/bugun``, ``/harita`` ...) index.html'e düşer.

    Dizin süreç açılırken yoksa da bağlanır: ``check_dir=False`` sayesinde
    ``kod/arayuz`` ilk kez derlendiğinde sunucuyu yeniden başlatmak gerekmez.
    """

    def __init__(self, *a, **kw):
        kw.setdefault("check_dir", False)
        super().__init__(*a, **kw)

    async def get_response(self, path: str, scope):
        if path.startswith("api"):                       # /api altı buraya düşmemeli
            return JSONResponse({"hata": "Kayıt bulunamadı.", "kod": "bulunamadi"}, status_code=404)
        if not (ayarlar.PWA_DIZINI / "index.html").exists():
            return JSONResponse({
                "hata": "Uygulama henüz derlenmemiş.",
                "kod": "pwa_yok",
                "cozum": "kod/arayuz klasöründe 'npm run build' çalıştırın; dist/ otomatik sunulur.",
                "api": "/api/saglik",
            }, status_code=503)
        # Starlette eksik dosyada 404 DÖNDÜRMEZ, HTTPException FIRLATIR —
        # ikisini de yakalayıp uygulamanın kabuğuna düşürüyoruz. Böylece
        # telefona "http://<ip>:8080/bugun" yazan biri de uygulamayı açar.
        try:
            yanit = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)
        if yanit.status_code == 404:
            return await super().get_response("index.html", scope)
        return yanit


# Her yanıta eklenen güvenlik başlıkları. CSP harici kaynağı kapatır; TEK istisna
# harita altlığının karo sunucularıdır (img-src/connect-src), o da yönetici ayarından
# gelir (``altlik.py``): uygulama hiçbir CDN'den font/JS çekmiyor.
# Referrer-Policy: karo sağlayıcıları (OSM) Referer ister; yalnız KÖKEN gider
# (http://<ofis-ip>:8080), yol/sorgu/ekran adı asla gitmez.
GUVENLIK_BASLIKLARI = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# Sürüm uyumsuzken (GUNCELLEME_BEKLIYOR) 503 dönen uçlar: yeni şemaya dayanan her şey. Satışın
# eski uçları (bugün, bina, harita, ziyaret, özet) çalışmaya devam eder.
V2_ONEKLERI = ("/api/isler", "/api/islerim", "/api/aktarim", "/api/obekler", "/api/mahalleler",
               "/api/ilceler", "/api/takip", "/api/boss", "/api/kullanici",
               "/api/ticket", "/api/tablolar", "/api/ek")


def _v2_ucu_mu(yol: str) -> bool:
    return any(yol == o or yol.startswith(o + "/") for o in V2_ONEKLERI)


@uygulama.middleware("http")
async def _onbellek_basliklari(istek: Request, sonraki):
    """index.html ve sw.js hiç önbelleğe alınmaz (telefon eski sürümde kalmasın);
    parmak izli varlıklar sonsuza dek önbellekte kalır (açılış hızı)."""
    yol = istek.url.path
    if GUNCELLEME_BEKLIYOR and _v2_ucu_mu(yol):
        yanit = JSONResponse({"hata": "Sunucu güncellenmeyi bekliyor. BASLAT.bat ile yeniden açın.",
                              "kod": "guncelleme_bekliyor"}, status_code=503)
    else:
        yanit = await sonraki(istek)
    if yol.startswith("/varlik/") or yol.startswith("/ikon/"):
        yanit.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif yol in ("/", "/index.html", "/sw.js", "/manifest.webmanifest"):
        yanit.headers["Cache-Control"] = "no-cache"
    yanit.headers.setdefault("Content-Security-Policy", altlik.csp())
    for ad, deger in GUVENLIK_BASLIKLARI.items():
        yanit.headers.setdefault(ad, deger)
    # Kişiye özel API yanıtları tarayıcı/ara önbelleklerde paylaşılmamalı.
    if yol.startswith("/api/"):
        yanit.headers.setdefault("Cache-Control", "no-store, private")
    return yanit


def _arka_plan_isit() -> None:
    _agir_modulleri_yukle()
    try:
        satis_uclari._haritayi_isit()
    except Exception as exc:  # ısınma hiçbir koşulda sunucuyu düşürmemeli
        _gunluk.warning("Harita ısınması tamamlanamadı: %s", exc)


def _agir_modulleri_yukle() -> None:
    """Bölge planlayıcının ağır kütüphaneleri: yield'den ÖNCE, eşzamanlı (≈3 sn).

    Başarısızsa günlüğe yazılır, sunucu yine açılır; ilgili uç kendi hatasını Türkçe verir.
    """
    try:
        import dsale.metrics  # noqa: F401
        import dsale.partition  # noqa: F401
        import shapely  # noqa: F401
    except Exception as exc:
        _gunluk.warning("Ağır modüller yüklenemedi (bölge planlayıcı etkilenir): %s", exc)


def _is_saklamasi(conn: sqlite3.Connection) -> None:
    """Kapanmış işlerin müşteri alanları (spec §1.12); açılışta bir kez. Modül yoksa atlanır."""
    try:
        from operasyon.v2 import saklama
    except ImportError:
        return
    try:
        sonuc = saklama.uygula(conn, ayarlar.simdi())
        conn.commit()
        if sonuc:
            _gunluk.info("Saklama kuralı uygulandı: %s", sonuc)
    except Exception as exc:  # açılış bu yüzden durmamalı
        _gunluk.warning("Saklama kuralı uygulanamadı: %s", exc)


def _veritabanini_hazirla() -> None:
    """Açılışta: sürümü denetler (göç YAPMAZ), veri kalitesi hiç hesaplanmamışsa bir kez hesaplar
    ve altlık ayarından CSP'yi kurar.

    Göç yalnız ``saha.sunucu`` açılışında (port denetiminden ve doğrulanmış yedekten sonra) koşar.
    ``SAHA_GOC_LIFESPAN=1`` (yalnız testler ve ``uvicorn saha.api:app`` ile geliştirme) burada yedeksiz
    göç yaptırır. Sürüm uyumsuzsa GUNCELLEME_BEKLIYOR: v2 uçları 503, eski uçlar çalışır.
    """
    global GUNCELLEME_BEKLIYOR
    GUNCELLEME_BEKLIYOR = False
    yol = db.db_yolu()
    if not yol.exists():
        return
    try:
        conn = db.baglan()
    except Exception:
        return
    try:
        if not db.tablo_var(conn, "bina"):
            return
        if os.environ.get("SAHA_GOC_LIFESPAN") == "1":
            try:
                rapor = goc.hazirla(yol, yedek=False)
                for satir in rapor.satirlar:
                    _gunluk.info(satir)
            except goc.GocHatasi as exc:
                _gunluk.error("Veritabanı güncellenemedi: %s", exc.mesaj)
        try:
            goc.surum_dogrula(conn)
        except goc.SurumUyumsuz as exc:
            GUNCELLEME_BEKLIYOR = True
            _gunluk.error("Veritabanı sürümü uyumsuz — iş emri uçları kapalı: %s", exc.mesaj)
        if not GUNCELLEME_BEKLIYOR:
            try:
                yetki.administrator_hesabi_hazirla(conn)
                conn.commit()
            except Exception as exc:
                _gunluk.warning("Administrator hesabı hazırlanamadı: %s", exc)
        sonuc = veri_kalitesi.hazirla(conn)
        if sonuc:
            _gunluk.info("Veri kalitesi hesaplandı: %d binada bulgu, %d binada güvenli düzeltme.",
                         sonuc["bayrakli"], sonuc["duzeltilen"])
        altlik.csp_tazele(conn=conn)
        if not GUNCELLEME_BEKLIYOR:
            _is_saklamasi(conn)
    except Exception as exc:  # açılış hiçbir koşulda bu yüzden durmamalı
        _gunluk.warning("Açılış hazırlığı tamamlanamadı: %s", exc)
    finally:
        conn.close()


# ============================================================================= yönlendiriciler
# PWA bağlamasından ÖNCE eklenmeli: "/" bağlaması sonradan eklenen her yolu yutar.

# Birim uçları: giriş (çekirdek), satış (Saha), Ekip (Yönetim). Sıra eski tek dosyadaki sırayı korur.
uygulama.include_router(giris_uclari.yonlendirici)
uygulama.include_router(boss_giris.yonlendirici)
uygulama.include_router(satis_uclari.yonlendirici)
uygulama.include_router(ekip_uclari.yonlendirici)

# Faz 2 uçları (veri kalitesi, bölge planlayıcı, tur raporu, ticket, 3B geometri, altlık).
uygulama.include_router(yonetim_uclari.yonlendirici)

# v2 yönlendiricilerine verilen bağımlılıklar (spec §5.1): döngüsel içe aktarma yok.
BAGIMLILIKLAR = Bagimliliklar()

# Eski iş emri uçları (pickle'lı tek yükleme) kalktı: 410 ``yenilendi`` (spec §5.3.9). v2 modülü
# kendi ``eski_yonlendirici``'sini verirse o kullanılır; yoksa bu yedek.
_ESKI_YONTEMLER = ["GET", "POST", "PUT", "PATCH", "DELETE"]
_eski_is_emri = APIRouter()


@_eski_is_emri.api_route("/api/is-emri", methods=_ESKI_YONTEMLER)
@_eski_is_emri.api_route("/api/is-emri/{yol:path}", methods=_ESKI_YONTEMLER)
def _is_emri_yenilendi():
    raise hata(410, "İş emirleri ekranı yenilendi; sayfayı yenileyin.", "yenilendi")


def _yonlendirici_listesi(nesne) -> list:
    """Modülün verdiği şey: APIRouter, APIRouter listesi ya da ``f(Bagimliliklar)``."""
    from fastapi import APIRouter

    if nesne is None:
        return []
    if isinstance(nesne, APIRouter):
        return [nesne]
    if isinstance(nesne, (list, tuple)):
        return [r for r in nesne if isinstance(r, APIRouter)]
    if callable(nesne):
        try:
            return _yonlendirici_listesi(nesne(BAGIMLILIKLAR))
        except TypeError:
            return _yonlendirici_listesi(nesne())
    return []


def rota_izni_ekle(modul_adi: str, tablo: dict) -> int:
    """Bağlanan modülün kendi uçları için bildirdiği izinleri ``yetki.ROTA_IZNI``'na ekler.

    Böylece WP-G gibi paketler ``saha/yetki.py``'ye dokunmadan yeni uç açabilir; kural aynı kalır:
    her uç tabloda olmalı ve ucun istediği eylem tablodakiyle aynı olmalı (``test_yetki_matrisi``).
    * Eylemler ``yetki.IZINLER``'de TANIMLI olmalı (yeni eylem yalnız yetki.py'ye eklenir).
    * Modül "herkese açık" (None) uç bildiremez; açık uçlar yalnız sözleşme tablosundadır.
    * Sözleşme tablosundaki bir satır EZİLMEZ (çelişki matris testinde görünür).
    Hata → ``ValueError``: o modül bağlanmaz, neden /api/saglik uyarısına düşer.
    """
    temiz: dict[tuple[str, str], str | tuple[str, ...]] = {}
    for anahtar, deger in (tablo or {}).items():
        yontem, yol = anahtar
        eylemler = (deger,) if isinstance(deger, str) else tuple(deger or ())
        if not eylemler:
            raise ValueError(f"{modul_adi}: {yontem} {yol} için eylem yok (herkese açık uç modülden bildirilemez)")
        bilinmeyen = [e for e in eylemler if e not in yetki.IZINLER]
        if bilinmeyen:
            raise ValueError(f"{modul_adi}: {yontem} {yol} bilinmeyen eylem: {', '.join(bilinmeyen)}")
        temiz[(str(yontem).upper(), str(yol))] = deger
    eklenen = 0
    for anahtar, deger in temiz.items():
        if anahtar not in yetki.ROTA_IZNI:
            yetki.ROTA_IZNI[anahtar] = deger
            eklenen += 1
    return eklenen


def _v2_bagla() -> None:
    """operasyon.v2.api (WP-B), saha.tablolar_uclari ve saha.ek_dosya (WP-G) — varsa bağlanır.

    Modül yoksa sessizce geçilir; VARSA ama yüklenemiyorsa satış uygulaması yine açılır, neden
    günlüğe ve /api/saglik uyarısına yazılır (tek bir modül hatası bütün sunucuyu düşürmesin).
    Modül ``ROTA_IZNI`` sözlüğü verirse kendi uçlarının izinleri tabloya eklenir (``rota_izni_ekle``).
    """
    global V2_YUKLEME_HATASI
    hatalar = []
    eski_baglandi = False
    for ad in ("operasyon.v2.api", "saha.tablolar_uclari", "saha.ek_dosya", "saha.arama_uclari", "saha.admin_uclari",
               "operasyon.v2.rut_api", "saha.onemap_esitle"):
        try:
            if importlib.util.find_spec(ad) is None:
                continue
            modul = importlib.import_module(ad)
            ek_izin = getattr(modul, "ROTA_IZNI", None)
            if isinstance(ek_izin, dict):
                rota_izni_ekle(ad, ek_izin)          # önce doğrula: hatalıysa uçlar hiç bağlanmaz
            yonlendiriciler = (_yonlendirici_listesi(getattr(modul, "yonlendiriciler", None))
                               or _yonlendirici_listesi(getattr(modul, "yonlendirici", None)))
            for r in yonlendiriciler:
                uygulama.include_router(r)
            eski = _yonlendirici_listesi(getattr(modul, "eski_yonlendirici", None))
            for r in eski:
                uygulama.include_router(r)
                eski_baglandi = True
        except Exception as exc:  # noqa: BLE001 — bilinçli: bir modül bütün sunucuyu düşürmesin
            _gunluk.exception("%s bağlanamadı: %s", ad, exc)
            hatalar.append(f"{ad}: {type(exc).__name__}: {exc}")
    if not eski_baglandi:
        uygulama.include_router(_eski_is_emri)
    V2_YUKLEME_HATASI = "; ".join(hatalar) or None


_v2_bagla()

uygulama.mount("/", TekSayfa(directory=str(ayarlar.PWA_DIZINI), html=True), name="pwa")
