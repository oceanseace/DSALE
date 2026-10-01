"""Saha Sistemi API — FastAPI.

Tek süreç hem API'yi hem PWA'yı sunar:
    /api/...        JSON uçları (Bearer jeton)
    /               kod/arayuz/dist (derlenmiş PWA)

Hata biçimi her yerde ``{"hata": "...", "kod": "..."}``; HTTP 401 alan uygulama
giriş ekranına döner. Bütün metinler Türkçedir.

Yetki (spec §2 + Ek-1): her uç ``Depends(izin("eylem"))`` ile kendi eylemini ister
(``saha/yetki.py``; varsayılan YASAK, izinler görev kümesinin birleşimi). Göç bu dosyada
YAPILMAZ: ``saha/sunucu.py`` port denetiminden sonra ``goc.hazirla`` çağırır; burada yalnız
sürüm denetlenir (uyumsuzsa v2 uçları 503 ``guncelleme_bekliyor``, eski uçlar çalışır).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hmac
import importlib
import importlib.util
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import time

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import SURUM, altlik, ayarlar, db, goc, guvenlik, rapor, rota, sema_v2, veri_kalitesi, yetki
from .yetki import (Bagimliliklar, _jeton_al, baglanti, bina_gorebilir, bolge_kapsami, hata, izin,  # noqa: F401
                    izinli, mevcut_kullanici, ziyaret_yazabilir)

_gunluk = logging.getLogger("saha.api")

# Sürüm uyumsuzsa (uvicorn doğrudan eski bir veritabanıyla açıldı) v2 uçları 503 döner.
GUNCELLEME_BEKLIYOR = False
# v2 yönlendiricileri yüklenemediyse nedeni (sağlık ucunda uyarı olarak görünür).
V2_YUKLEME_HATASI: str | None = None


@contextlib.asynccontextmanager
async def _yasam_dongusu(_uygulama: FastAPI):
    """Açılış: sürüm denetimi (göç YOK), veri kalitesi, ağır modüller, harita önbelleği."""
    _veritabanini_hazirla()
    # Ağır modüller (pandas, scipy, shapely ~3 sn) yield'den ÖNCE, eşzamanlı yüklenir: arka
    # plandaki ısınma iş parçacığı ilk istekle yarışıyordu (spec §1.2 "ağır modüller").
    _agir_modulleri_yukle()
    _haritayi_isit()
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
    title="Saha Sistemi",
    version=SURUM,
    description="Dehanet EÇM saha ekibi için görev, ziyaret ve kapsama takibi.",
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


# ============================================================================= kimlik
# baglanti, mevcut_kullanici, hata, izin, bolge_kapsami ... saha/yetki.py'dadır (yukarıda içe aktarıldı).

# Eski ad: yalnız "veri yönetimi" anlamında kalır (spec §2.2); yeni uçlar kendi eylemini ister.
yonetici = izin("veri.yonet")

# Eski ad; yeni kod yetki.bolge_kapsami kullanır.
_bolge_kontrol = bolge_kapsami


def _listesinde_mi(conn: sqlite3.Connection, kullanici_id: int, bina_serial: str) -> bool:
    return yetki.listesinde_mi(conn, kullanici_id, bina_serial)


def _etiket_listesi(metin: str | None) -> list[str]:
    try:
        deger = json.loads(metin) if metin else []
    except (TypeError, ValueError):
        return []
    return [str(x) for x in deger] if isinstance(deger, list) else []


def _kullanici_kart(k: dict | sqlite3.Row, gorevler: list[str] | None = None, maskeli: bool = False) -> dict:
    """Kişi kartı. ``maskeli``: listelerde telefon "0532 ••• •• 06" (tam hâli yalnız tek kişi yanıtında)."""
    k = dict(k)
    kume = gorevler if gorevler is not None else (k.get("gorevler") or [k["rol"]])
    kisi = {**k, "gorevler": kume}
    kart = {
        "id": k["id"],
        "ad": k["ad"],
        "telefon_goster": guvenlik.telefon_maskeli(k["telefon"]) if maskeli else guvenlik.telefon_goster(k["telefon"]),
        "rol": k["rol"],
        "gorevler": [r for r in yetki.ROLLER if r in set(kume) | {k["rol"]}],
        "gorev_etiketi": yetki.gorev_etiketi(kisi),
        "bolge": k["bolge"],
        "aktif": bool(k["aktif"]),
        "pin_var": bool(k.get("pin_hash")),
        # Ek-2: telefonu olmayan kişi giriş yapamaz (BOSS Mobil'le çalışır); atama yine yapılabilir.
        "giris_var": bool(k["telefon"]),
        "unvan": k.get("unvan"),
        "kaynak": k.get("kaynak") or "elle",
        "etiket": _etiket_listesi(k.get("etiket")),
        "boss_ekip": k.get("boss_ekip"),
        "kapasite": k.get("kapasite"),
    }
    if not maskeli:
        kart["telefon"] = k["telefon"]
    return kart


# ============================================================================= bina kartı
_BOS_AD = {"", "null", "none", "nan", "-"}


def _baslik(b: dict) -> str:
    # Kaynakta ad yerine 'Null' yazan binalar var; kartta "Null" başlığı çıkmasın.
    for alan in ("ad", "site_adi"):
        deger = (b.get(alan) or "").strip()
        if deger.lower() not in _BOS_AD:
            return deger
    sokak = (b.get("sokak") or "").strip()
    kapi = (b.get("kapi_no") or "").strip()
    if sokak:
        return f"{sokak} No:{kapi}" if kapi else sokak
    return b.get("bina_serial", "")


def _adres(b: dict) -> str:
    sokak = (b.get("sokak") or b.get("cadde") or "").strip()
    kapi = (b.get("kapi_no") or "").strip()
    satir = f"{sokak} No:{kapi}" if (sokak and kapi) else sokak
    kuyruk = " / ".join(x for x in [(b.get("mahalle") or "").strip(), (b.get("ilce") or "").strip()] if x)
    return " · ".join(x for x in [satir, kuyruk] if x)


def _penetrasyon(b: dict) -> float | None:
    """Doluluk oranı. Ölçülemiyorsa None — kartta "%0" değil "veri yok" yazar.

    ``res_hp=0`` olan 165 binada daire sayısı dolu ve 122'sinde kayıtlı abone
    var; eski hesap bunlara "%0 doluluk, 0 boş kapı" diyerek kendi içinde
    çelişen bir kart gösteriyordu. 303 binada da aktif_res > res_hp olduğu için
    oran %100'ü aşıyordu.
    """
    taban = max(int(b.get("res_hp") or 0), int(b.get("daire") or 0))
    if taban <= 0:
        return None
    return round(min(int(b.get("aktif_res") or 0) / taban, 1.0), 4)


def _bina_kart(b: dict | sqlite3.Row, bugun: dt.date | None = None) -> dict:
    b = dict(b)
    gun = bugun or ayarlar.bugun()
    durum = b.get("durum") or "bekliyor"
    baslik = _baslik(b)
    kart = {
        "bina_serial": b["bina_serial"],
        "baslik": baslik,
        # Uygulama bazı yerlerde ham `ad` alanını okuyor (sözleşmedeki `bina.ad`).
        # İkisi de aynı metni verir; site adı yoksa sokak/kapı numarasına düşer.
        "ad": baslik,
        "adres": _adres(b),
        "site_adi": b.get("site_adi") or "",
        "site_grup": b.get("site_grup") or "",
        "mahalle": b.get("mahalle") or "",
        "ilce": b.get("ilce") or "",
        "sokak": b.get("sokak") or "",
        "kapi_no": b.get("kapi_no") or "",
        "lat": b.get("lat"),
        "lon": b.get("lon"),
        "kat": b.get("kat") or 0,
        "daire": b.get("daire") or 0,
        "res_hp": b.get("res_hp") or 0,
        "aktif_res": b.get("aktif_res") or 0,
        "firsat": b.get("firsat") or 0,
        "penetrasyon": _penetrasyon(b),
        "sales_ready": b.get("sales_ready"),
        "yeni_site": rota.yeni_site_carpani(b.get("sales_ready"), gun) > 1.0,
        "bolge": b.get("bolge"),
        "durum": durum,
        "durum_etiket": ayarlar.DURUM_ETIKET.get(durum, durum),
        "son_ziyaret": b.get("son_ziyaret"),
        "son_sonuc": b.get("son_sonuc"),
        "tekrar_tarih": b.get("tekrar_tarih"),
        "toplam_satis": b.get("toplam_satis") or 0,
        "ziyaret_sayisi": b.get("ziyaret_sayisi") or 0,
        # Yönetici "Ayrıntılar" penceresi ve BOSS/Fox iş emri eşleştirmesi için
        "kimlik": {
            "bina_serial": b["bina_serial"],
            "location_id": b.get("location_id") or "",
            "tellcordia_id": b.get("tellcordia_id") or "",
            "uavt_bina_kodu": b.get("uavt_bina_kodu") or "",
        },
        "blok_adi": b.get("blok_adi") or "",
        "bina_turu": b.get("bina_turu") or "",
        "toplam_hp": b.get("toplam_hp") or 0,
        "altyapi": b.get("altyapi") or "",
        "teknoloji": b.get("teknoloji") or "",
        "obek": b.get("obek") or "",
        "crm_site_adi": b.get("crm_site_adi") or "",
        # Veri kalitesi bulguları (dsale/kalite.py): [{kural, mesaj, seviye, duzeltme?}]
        "kalite": veri_kalitesi.bayraklar(b.get("kalite")),
        # Son tur raporunda yok: listeye girmez, geçmişi durur.
        "pasif": bool(b.get("pasif")),
    }
    for ek in ("sira", "mesafe_m", "oncelik", "gorev_durum"):
        if ek in b and b[ek] is not None:
            kart[ek] = b[ek]
    return kart


# ============================================================================= görev yardımcıları
def _tarih_coz(metin: str | None, varsayilan: dt.date | None = None) -> dt.date:
    if not metin:
        return varsayilan or ayarlar.bugun()
    try:
        return dt.date.fromisoformat(metin[:10])
    except ValueError:
        raise hata(400, "Tarih biçimi geçersiz (YYYY-AA-GG bekleniyor).", "tarih_gecersiz")


def _acik_planli(conn: sqlite3.Connection, tarih: dt.date) -> set[str]:
    """O gün açık görevlerde bekleyen binalar — başka listeye girmemeli."""
    satirlar = conn.execute(
        "SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
        "WHERE g.tarih=? AND g.durum='acik' AND gb.durum='bekliyor'",
        (tarih.isoformat(),),
    ).fetchall()
    return {s["bina_serial"] for s in satirlar}


def _planli_temizle(conn: sqlite3.Connection, tarih: dt.date) -> None:
    """Dünden kalan 'planli' işaretlerini kaldırır (durum yalnız 'bekliyor'dan alındığı için kayıpsız)."""
    conn.execute(
        "UPDATE bina_durum SET durum='bekliyor' WHERE durum='planli' AND bina_serial NOT IN ("
        "  SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id"
        "  WHERE g.tarih=? AND g.durum='acik' AND gb.durum='bekliyor')",
        (tarih.isoformat(),),
    )


def _acik_gorev(conn: sqlite3.Connection, kullanici_id: int, tarih: dt.date) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM gorev WHERE kullanici_id=? AND tarih=? AND durum='acik' ORDER BY id DESC LIMIT 1",
        (kullanici_id, tarih.isoformat()),
    ).fetchone()


def _gorev_bul(
    conn: sqlite3.Connection, kullanici_id: int, tarih: dt.date, sadece_acik: bool = True
) -> sqlite3.Row | None:
    """Bir günün görevi. Geçmiş günlere bakarken kapanmış görev de görünmeli."""
    if sadece_acik:
        return _acik_gorev(conn, kullanici_id, tarih)
    return conn.execute(
        "SELECT * FROM gorev WHERE kullanici_id=? AND tarih=? ORDER BY id DESC LIMIT 1",
        (kullanici_id, tarih.isoformat()),
    ).fetchone()


def _gecmis_gorevleri_kapat(conn: sqlite3.Connection) -> None:
    """Dünden kalan açık görevleri kapatır.

    Kapanmadıkları sürece bir kullanıcının aynı anda birden çok açık görevi
    oluyor, aynı bina iki günün listesinde birden bekliyor ve dün indirilen
    raporla bugün indirilen aynı-tarihli rapor farklı çıkıyordu.
    """
    conn.execute(
        "UPDATE gorev SET durum='tamam' WHERE durum='acik' AND tarih < ?",
        (ayarlar.bugun().isoformat(),),
    )


def _gorev_binalari(conn: sqlite3.Connection, gorev_id: int) -> list[dict]:
    satirlar = conn.execute(
        f"SELECT {rota.BINA_ALANLARI}, gb.sira, gb.mesafe_m, gb.durum AS gorev_durum "
        "FROM gorev_bina gb "
        "JOIN bina b ON b.bina_serial=gb.bina_serial "
        "JOIN bina_durum d ON d.bina_serial=gb.bina_serial "
        "WHERE gb.gorev_id=? ORDER BY gb.sira",
        (gorev_id,),
    ).fetchall()
    return [_bina_kart(s) for s in satirlar]


def _gunun_onceki_binalari(
    conn: sqlite3.Connection, kullanici_id: int, tarih: dt.date, acik_gorev_id: int | None
) -> list[dict]:
    """Aynı GÜN içinde kapanmış görevlerin binaları.

    Satışçı 25 binayı bitirip "yeni liste al" derse sunucu sabahki görevi
    kapatıp yenisini açar. `/api/gorev/bugun` yalnız açık görevi döndürdüğü
    için sabah gezilen 25 bina ekrandan siliniyordu: adam öğleden sonra
    telefonuna bakıp bütün emeğini kaybolmuş görüyordu. Bunlar "Bitenler"in
    altında durmalı — bugünün işi bir görev değil, BİR GÜN.
    """
    satirlar = conn.execute(
        f"SELECT {rota.BINA_ALANLARI}, gb.sira, gb.mesafe_m, gb.durum AS gorev_durum "
        "FROM gorev_bina gb "
        "JOIN gorev g ON g.id=gb.gorev_id "
        "JOIN bina b ON b.bina_serial=gb.bina_serial "
        "JOIN bina_durum d ON d.bina_serial=gb.bina_serial "
        "WHERE g.kullanici_id=? AND g.tarih=? AND g.id<>COALESCE(?, -1) "
        "  AND gb.durum='tamam' "
        "ORDER BY g.id, gb.sira",
        (kullanici_id, tarih.isoformat(), acik_gorev_id),
    ).fetchall()
    return [_bina_kart(s) for s in satirlar]


def _gorev_ozet(conn: sqlite3.Connection, gorev_id: int | None) -> dict:
    if not gorev_id:
        return {"gorev_id": None, "toplam": 0, "tamam": 0, "kalan": 0, "satis": 0,
                "satis_bina": 0, "ziyaret": 0, "donusum": 0.0}
    s = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "SUM(CASE WHEN durum='tamam' THEN 1 ELSE 0 END) AS tamam, "
        "SUM(CASE WHEN durum='bekliyor' THEN 1 ELSE 0 END) AS kalan "
        "FROM gorev_bina WHERE gorev_id=?",
        (gorev_id,),
    ).fetchone()
    g = conn.execute("SELECT kullanici_id, tarih FROM gorev WHERE id=?", (gorev_id,)).fetchone()
    z = conn.execute(
        "SELECT COALESCE(SUM(satis_adedi),0) AS adet, "
        "       COALESCE(SUM(CASE WHEN sonuc='satis' THEN 1 ELSE 0 END),0) AS bina, "
        "       COUNT(*) AS ziyaret "
        "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10)=?",
        (g["kullanici_id"], g["tarih"]),
    ).fetchone()
    ziyaret = int(z["ziyaret"] or 0)
    return {
        "gorev_id": gorev_id,
        "toplam": s["toplam"] or 0,
        "tamam": s["tamam"] or 0,
        "kalan": s["kalan"] or 0,
        # "satis" = satılan abonelik adedi (satışçının primi buna bağlı),
        # "satis_bina" = satışla biten bina. Dönüşüm İKİNCİSİNDEN hesaplanır ki
        # yönetici ekranıyla aynı şeyi söylesin.
        "satis": int(z["adet"] or 0),
        "satis_bina": int(z["bina"] or 0),
        "ziyaret": ziyaret,
        "donusum": round(int(z["bina"] or 0) / ziyaret, 4) if ziyaret else 0.0,
    }


def _gorev_yaz(
    conn: sqlite3.Connection,
    kullanici_id: int,
    tarih: dt.date,
    binalar: list[dict],
    kaynak: str,
    olusturan_id: int,
    notu: str | None = None,
    mevcut: sqlite3.Row | None = None,
) -> int:
    """Görevi oluşturur (ya da açık göreve ekler) ve binaları 'planli' işaretler."""
    if mevcut is not None:
        gorev_id = mevcut["id"]
        baslangic = conn.execute(
            "SELECT COALESCE(MAX(sira),0) FROM gorev_bina WHERE gorev_id=?", (gorev_id,)
        ).fetchone()[0]
    else:
        imlec = conn.execute(
            "INSERT INTO gorev (kullanici_id, tarih, durum, olusturan_id, kaynak, notu, olusturma) "
            "VALUES (?,?,'acik',?,?,?,?)",
            (kullanici_id, tarih.isoformat(), olusturan_id, kaynak, notu, ayarlar.zaman_metni()),
        )
        gorev_id = int(imlec.lastrowid)
        baslangic = 0

    for b in binalar:
        conn.execute(
            "INSERT INTO gorev_bina (gorev_id, bina_serial, sira, durum, mesafe_m) "
            "VALUES (?,?,?,'bekliyor',?) ON CONFLICT(gorev_id, bina_serial) DO NOTHING",
            (gorev_id, b["bina_serial"], baslangic + b.get("sira", 0), int(b.get("mesafe_m", 0))),
        )
        conn.execute(
            "UPDATE bina_durum SET durum='planli' WHERE bina_serial=? AND durum='bekliyor'",
            (b["bina_serial"],),
        )
    db.surumu_arttir(conn)
    return gorev_id


def _demo_kurulu(conn: sqlite3.Connection) -> bool:
    """Gösterim verisi kurulu mu? Ekranlarda uyarı şeridi bunun için çıkar."""
    try:
        return db.ayar_oku(conn, "demo") is not None
    except sqlite3.Error:
        return False


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


# ============================================================================= giriş
class GirisGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    telefon: str
    pin: str = ""


class PinGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    telefon: str
    pin: str
    davet_kodu: str = Field(default="", validation_alias=AliasChoices("davet_kodu", "davet"))


def _telefon_veya_hata(ham: str) -> str:
    telefon = guvenlik.telefon_duzelt(ham)
    if not telefon:
        raise hata(400, "Telefon numarası geçersiz. Örnek: 0532 111 22 33", "telefon_gecersiz")
    return telefon


def _ip(istek: Request) -> str | None:
    return istek.client.host if istek.client else None


def _ip_kontrol(conn: sqlite3.Connection, ip: str | None, tur: str = "giris") -> None:
    """IP başına sınır. Telefon başına SERT KİLİT YOK (bkz. guvenlik.py)."""
    kalan = guvenlik.ip_asildi_mi(conn, ip, tur)
    if kalan:
        dakika = max(1, round(kalan / 60))
        raise hata(429, f"Bu cihazdan çok fazla deneme yapıldı. {dakika} dakika sonra "
                        "tekrar deneyin.", "kilitli")


def _yanlis_pin(conn: sqlite3.Connection, telefon: str, ip: str | None, mesaj: str) -> None:
    """Hatalı denemeyi yazar, cezalı bekleme uygular ve hatayı fırlatır.

    Doğru PIN hiçbir zaman reddedilmez: meşru satışçı sahadayken kilitli kalmaz.
    Kaba kuvveti durduran şey artan gecikme ve IP sınırıdır.
    """
    guvenlik.deneme_yaz(conn, telefon, False, ip)
    conn.commit()
    bekle = guvenlik.gecikme_saniye(guvenlik.hatali_sayisi(conn, telefon))
    if bekle:
        time.sleep(bekle)
    raise hata(401, mesaj, "kimlik_hatali")


@uygulama.post("/api/giris")
def giris(girdi: GirisGirdi, istek: Request, conn: sqlite3.Connection = Depends(baglanti)):
    """Giriş — ve PIN girilmeden yapılan "ilk kez mi?" yoklaması.

    Uygulama önce boş PIN ile sorar. Yanıt ``pin_belirle`` ise ekran doğrudan
    davet kodu adımına geçer; yoksa PIN sorar. Böylece hesabı yeni açılan
    satışçı, PIN'i olmadığı halde "Şifren" ekranına düşüp rastgele denemez.

    Yoklama hesabın ADINI DÖNDÜRMEZ ve hatalı deneme sayılmaz; kimliksiz birinin
    05xx aralığını tarayıp "hangi numara Turkcell saha ekibinde, kim" listesi
    çıkarmasını engellemek için. IP başına sınır yine de işler.
    """
    telefon = _telefon_veya_hata(girdi.telefon)
    ip = _ip(istek)
    k = conn.execute("SELECT * FROM kullanici WHERE telefon=?", (telefon,)).fetchone()

    if not (girdi.pin or "").strip():
        _ip_kontrol(conn, ip, "yoklama")
        pin_belirle_gerek = bool(k and k["aktif"] and not k["pin_hash"])
        guvenlik.deneme_yaz(conn, telefon, False, ip, tur="yoklama")
        conn.commit()
        return {
            "pin_belirle": pin_belirle_gerek,
            "telefon": telefon,
            "mesaj": ("İlk giriş. Yöneticinizden aldığınız 6 haneli davet koduyla "
                      "kendi PIN'inizi belirleyeceksiniz.") if pin_belirle_gerek else None,
        }

    _ip_kontrol(conn, ip)
    if not k:
        _yanlis_pin(conn, telefon, ip, "Telefon veya PIN hatalı.")
    if not k["aktif"]:
        raise hata(403, "Hesabınız kapalı. Yöneticinize başvurun.", "hesap_kapali")
    if not k["pin_hash"]:
        return {"pin_belirle": True, "telefon": telefon,
                "mesaj": "İlk giriş. Yöneticinizden aldığınız davet koduyla PIN belirleyin."}
    if not guvenlik.pin_dogrula(girdi.pin, k["pin_hash"]):
        _yanlis_pin(conn, telefon, ip, "PIN hatalı. Tekrar deneyin.")

    guvenlik.deneme_yaz(conn, telefon, True, ip)
    conn.commit()
    return _oturum_yaniti(conn, k)


def _oturum_yaniti(conn: sqlite3.Connection, k) -> dict:
    """Giriş / PIN yanıtı: jeton + kişi kartı + girişte açılacak ekran (spec §2.1)."""
    k = dict(k)
    k["gorevler"] = yetki.gorev_kumesi_oku(conn, k)
    return {"token": guvenlik.jeton_uret(k), "kullanici": _kullanici_kart(k),
            "ana_ekran": yetki.ana_ekran(k["rol"])}


def _davet_suresi_doldu(k) -> bool:
    """Yeni davet kodları (``davet_zamani`` dolu) 48 saat geçerlidir; eski kodlar süresizdir."""
    zaman = (dict(k).get("davet_zamani") or "").strip()
    if not zaman:
        return False
    try:
        uretim = dt.datetime.fromisoformat(zaman)
    except ValueError:
        return False
    return ayarlar.simdi() - uretim > dt.timedelta(hours=ayarlar.DAVET_GECERLILIK_SAAT)


@uygulama.post("/api/pin")
def pin_belirle(girdi: PinGirdi, istek: Request, conn: sqlite3.Connection = Depends(baglanti)):
    telefon = _telefon_veya_hata(girdi.telefon)
    ip = _ip(istek)
    _ip_kontrol(conn, ip)
    k = conn.execute("SELECT * FROM kullanici WHERE telefon=?", (telefon,)).fetchone()
    if not k or not k["aktif"]:
        _yanlis_pin(conn, telefon, ip, "Telefon veya davet kodu hatalı.")
    # Davet kodu DOĞRULANMADAN "bu hesabın PIN'i var" bilgisi verilmez; yoksa
    # kimliksiz biri hangi hesapların açık olduğunu öğrenebiliyordu.
    kayitli_kod = (k["davet_kodu"] or "").strip()
    if not kayitli_kod or not hmac.compare_digest(girdi.davet_kodu.strip(), kayitli_kod):
        _yanlis_pin(conn, telefon, ip, "Telefon veya davet kodu hatalı.")
    if k["pin_hash"]:
        raise hata(409, "PIN zaten belirlenmiş. Unuttuysanız yöneticiden sıfırlatın.", "pin_var")
    if _davet_suresi_doldu(k):
        raise hata(410, "Kodun süresi doldu. Yöneticinizden yeni kod isteyin.", "davet_suresi_doldu")
    if not guvenlik.pin_gecerli_mi(girdi.pin):
        raise hata(400, "PIN 4 rakamdan oluşmalı.", "pin_gecersiz")
    if guvenlik.pin_zayif_mi(girdi.pin):
        raise hata(400, "Bu PIN çok kolay tahmin ediliyor (1111, 1234 gibi). "
                        "Başka bir 4 hane seçin.", "pin_zayif")

    conn.execute(
        "UPDATE kullanici SET pin_hash=?, davet_kodu=NULL WHERE id=?",
        (guvenlik.pin_hashle(girdi.pin), k["id"]),
    )
    guvenlik.deneme_yaz(conn, telefon, True, ip)
    conn.commit()
    k = conn.execute("SELECT * FROM kullanici WHERE id=?", (k["id"],)).fetchone()
    return _oturum_yaniti(conn, k)


def _gorev_gozden_gecir(conn: sqlite3.Connection) -> dict:
    """Göçten sonra yöneticiye sakin şerit: "8 kişi 'Yönetici' görünüyor" (spec §1.11-2)."""
    try:
        bitti = db.ayar_oku(conn, "gorev_gozden_gecirildi", "0") == "1"
    except sqlite3.Error:
        bitti = True
    yalniz_yonetici = conn.execute(
        "SELECT COUNT(*) FROM kullanici k WHERE k.rol='yonetici' AND k.aktif=1"
    ).fetchone()[0]
    return {"gorev_gozden_gecir": (not bitti) and yalniz_yonetici > 1, "yonetici_sayisi": int(yalniz_yonetici)}


def _teknik_bugun(conn: sqlite3.Connection, k: dict) -> dict:
    """Teknik ana ekranının üst satırı: bugün açık iş, BTK, biten (is_emri yoksa sıfır)."""
    try:
        s = conn.execute(
            "SELECT SUM(CASE WHEN durum NOT IN ('cozuldu','kapandi') THEN 1 ELSE 0 END), "
            "       SUM(CASE WHEN durum NOT IN ('cozuldu','kapandi') AND serit='BTK' THEN 1 ELSE 0 END), "
            "       SUM(CASE WHEN durum IN ('cozuldu','kapandi') AND substr(COALESCE(cozum_zamani, kapanis, ''),1,10)=? "
            "                THEN 1 ELSE 0 END) "
            "FROM is_emri WHERE atanan_id=?", (ayarlar.bugun().isoformat(), k["id"])).fetchone()
    except sqlite3.OperationalError:
        return {"is": 0, "btk": 0, "biten": 0}
    return {"is": int(s[0] or 0), "btk": int(s[1] or 0), "biten": int(s[2] or 0)}


@uygulama.get("/api/ben")
def ben(k: dict = Depends(izin("oturum")), conn: sqlite3.Connection = Depends(baglanti)):
    """Her görev kendi dalını alır (spec §5.3.1); dal ANA göreve göredir, izinler kümenin birleşimi."""
    ortak = {"kullanici": _kullanici_kart(k), "ana_ekran": yetki.ana_ekran(k["rol"]),
             "izinler": yetki.izin_listesi(k), "gorev_etiketi": yetki.gorev_etiketi(k),
             "demo": _demo_kurulu(conn), "tarih": ayarlar.bugun().isoformat(),
             "guncelleme_bekliyor": GUNCELLEME_BEKLIYOR,
             # EK-6: küçük sevinçler sunucudan kapatılabilir (ayar 'acik' | 'kapali'); arayüz buradan okur.
             "kutlamalar": (db.ayar_oku(conn, "kutlamalar", "acik") or "acik") != "kapali"}
    kume = yetki.gorevler(k)
    if "yonetici" in kume:
        ortak.update(_gorev_gozden_gecir(conn))
    if "operasyon" in kume or "teknik" in kume:
        ortak["yardim"] = {"telefon": db.ayar_oku(conn, "yardim_telefon"), "ad": db.ayar_oku(conn, "yardim_ad")}
    if k["rol"] == "satisci":
        return {**ortak, **_ben_satis(conn, k)}
    if k["rol"] == "teknik":
        return {**ortak, "bugun": _teknik_bugun(conn, k)}
    if k["rol"] == "operasyon":
        return {**ortak, "bugun": _teknik_bugun_ekip(conn)}
    return {**ortak, "bugun": _ben_yonetici_ozeti(conn)}


def _teknik_bugun_ekip(conn: sqlite3.Connection) -> dict:
    """Operasyon ana ekranının üst satırı için kaba sayılar (ayrıntı İşler panosunda)."""
    try:
        s = conn.execute(
            "SELECT SUM(CASE WHEN durum NOT IN ('cozuldu','kapandi') THEN 1 ELSE 0 END), "
            "       SUM(CASE WHEN durum IN ('triyaj','bekliyor','randevulu') THEN 1 ELSE 0 END) "
            "FROM is_emri").fetchone()
    except sqlite3.OperationalError:
        return {"acik": 0, "atanmamis": 0}
    return {"acik": int(s[0] or 0), "atanmamis": int(s[1] or 0)}


def _ben_satis(conn: sqlite3.Connection, k: dict) -> dict:
    """Satış dalı: bugünkü alanlar değişmez (+ ``bolge_yok``)."""
    gun = ayarlar.bugun()
    gorev = _acik_gorev(conn, k["id"], gun)
    ozet = _gorev_ozet(conn, gorev["id"] if gorev else None)
    b = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "       SUM(CASE WHEN d.son_ziyaret IS NULL THEN 0 ELSE 1 END) AS dokunulan, "
        # "Kalan boş kapı" = HENÜZ SATILMAMIŞ kapı. Eski hesap binaya bir kez
        # dokunulduğu anda o binanın BÜTÜN boş kapılarını "halledilmiş"
        # sayıyor, 753 satışla ~38.000 kapıyı bitmiş gösteriyordu.
        "       SUM(MAX(b.firsat - d.toplam_satis, 0)) AS kalan_firsat "
        "FROM bina b JOIN bina_durum d USING(bina_serial) WHERE b.bolge=? AND b.pasif=0",
        (k["bolge"],),
    ).fetchone()
    toplam, dokunulan = int(b["toplam"] or 0), int(b["dokunulan"] or 0)
    ozet["bolge_bina"] = toplam
    ozet["bolge_dokunulmayan"] = toplam - dokunulan
    # "Ben" ekranındaki hafta ve bölge kartları (sözleşme §4.5).
    hafta_basi = (gun - dt.timedelta(days=gun.weekday())).isoformat()
    # "Satış" hem bugün hem bu hafta AYNI şeyi saymalı: satılan abonelik adedi.
    # (Bugünkü kart `_gorev_ozet` üzerinden satis_adedi topluyor.) Aynı ekranda
    # iki farklı tanım olursa satışçı ilk gün "sayılar tutmuyor" der.
    h = conn.execute(
        "SELECT COUNT(*) AS ziyaret, "
        "       COALESCE(SUM(satis_adedi),0) AS satis, "
        "       SUM(CASE WHEN sonuc='satis' THEN 1 ELSE 0 END) AS satis_bina, "
        "       SUM(CASE WHEN sonuc='randevu' THEN 1 ELSE 0 END) AS randevu "
        "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10)>=?",
        (k["id"], hafta_basi),
    ).fetchone()
    ziyaret_h = int(h["ziyaret"] or 0)
    return {
        # Etiketler TEK KAYNAKTAN gelir (ayarlar.py). Aksi halde aynı sonuç
        # telefonda başka, raporda başka yazıyor.
        "etiketler": {"sonuc": ayarlar.SONUC_ETIKET_SAHA, "durum": ayarlar.DURUM_ETIKET},
        "bugun": ozet,
        # DÖNÜŞÜM TEK TANIM: satışla biten bina / gezilen bina. Yüzde 100'ü
        # aşamaz. Abonelik adedi ayrı bir sayıdır ("satis_adedi"), ikisi
        # karıştırılmasın diye ikisi de burada.
        "hafta": {"ziyaret": ziyaret_h, "satis": int(h["satis_bina"] or 0),
                  "satis_adedi": int(h["satis"] or 0), "randevu": int(h["randevu"] or 0),
                  "donusum": round(int(h["satis_bina"] or 0) / ziyaret_h, 4) if ziyaret_h else 0.0},
        "bolge": {"toplam": toplam, "dokunulan": dokunulan, "kalan": toplam - dokunulan,
                  "kalan_firsat": int(b["kalan_firsat"] or 0)},
        # Bölgesi NULL/0 satışçı: listeler boş döner, ekranda "Size henüz bölge atanmadı" (spec §2.4-1).
        "bolge_yok": not int(k.get("bolge") or 0),
    }


def _ben_yonetici_ozeti(conn: sqlite3.Connection) -> dict:
    """Yönetici dalının bugünkü satış özeti (değişmez)."""
    gun = ayarlar.bugun()
    # Yönetici özeti de BİNA sayar, ziyaret değil: aynı binaya iki kez
    # gidilince ya da listede olmayan binaya ziyaret yazılınca ilerleme
    # çubuğu şişip "28 / 28 bina" gibi imkânsız sayılar çıkıyordu.
    g = conn.execute(
        "SELECT COUNT(*) AS toplam, "
        "SUM(CASE WHEN gb.durum='tamam' THEN 1 ELSE 0 END) AS tamam, "
        "SUM(CASE WHEN gb.durum='bekliyor' THEN 1 ELSE 0 END) AS kalan "
        "FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id WHERE g.tarih=?",
        (gun.isoformat(),),
    ).fetchone()
    z = conn.execute(
        "SELECT COALESCE(SUM(satis_adedi),0) AS satis "
        "FROM ziyaret WHERE iptal=0 AND substr(zaman,1,10)=?",
        (gun.isoformat(),),
    ).fetchone()
    return {"gorev_id": None, "toplam": int(g["toplam"] or 0), "tamam": int(g["tamam"] or 0),
            "kalan": int(g["kalan"] or 0), "satis": int(z["satis"])}


# ============================================================================= görev
class RotaGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    adet: int = Field(default=ayarlar.VARSAYILAN_ADET, ge=1, le=ayarlar.EN_FAZLA_ADET)
    baslangic: list[float] | None = None


@uygulama.get("/api/gorev/bugun")
def gorev_bugun(
    kullanici_id: int | None = None,
    tarih: str | None = None,
    k: dict = Depends(izin("satis.kendi", "satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    hedef_id = k["id"]
    if kullanici_id is not None and int(kullanici_id) != k["id"]:
        if not izinli(k, "satis.izle"):
            raise hata(403, "Yalnızca kendi listenizi görebilirsiniz.", "yasak")
        hedef_id = int(kullanici_id)
    gun = _tarih_coz(tarih)
    gorev = _gorev_bul(conn, hedef_id, gun, sadece_acik=gun >= ayarlar.bugun())
    if not gorev:
        return {"gorev_id": None, "tarih": gun.isoformat(), "kaynak": None, "notu": None,
                "binalar": [], "onceki_binalar": _gunun_onceki_binalari(conn, hedef_id, gun, None),
                "toplam_mesafe_m": 0, "ozet": _gorev_ozet(conn, None),
                "uyari": None, "mesaj": "Bugün için liste yok."}
    binalar = _gorev_binalari(conn, gorev["id"])
    return {
        "gorev_id": gorev["id"],
        "tarih": gorev["tarih"],
        "kaynak": gorev["kaynak"],
        "notu": gorev["notu"],
        "binalar": binalar,
        # Aynı gün daha önce bitirilen listelerin binaları: ekranda "Bitenler"
        # bölümünün altına eklenir, sayaçlara KARIŞMAZ.
        "onceki_binalar": _gunun_onceki_binalari(conn, hedef_id, gun, gorev["id"]),
        "toplam_mesafe_m": sum(b.get("mesafe_m", 0) for b in binalar),
        "uyari": rota.tur_uyarisi(binalar),
        "ozet": _gorev_ozet(conn, gorev["id"]),
    }


@uygulama.post("/api/gorev/olustur")
def gorev_olustur(
    girdi: RotaGirdi | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    girdi = girdi or RotaGirdi()
    if "satisci" not in yetki.gorevler(k) or not k["bolge"]:
        raise hata(400, "Rota yalnızca satışçı hesapları için kurulur.", "bolge_yok")

    gun = ayarlar.bugun()
    _gecmis_gorevleri_kapat(conn)
    _planli_temizle(conn, gun)
    mevcut = _acik_gorev(conn, k["id"], gun)
    if mevcut:
        ozet = _gorev_ozet(conn, mevcut["id"])
        if ozet["kalan"] > 0:
            conn.commit()
            binalar = _gorev_binalari(conn, mevcut["id"])
            return {"gorev_id": mevcut["id"], "tarih": mevcut["tarih"], "zaten_var": True,
                    "kaynak": mevcut["kaynak"], "notu": mevcut["notu"], "binalar": binalar,
                    "toplam_mesafe_m": sum(b.get("mesafe_m", 0) for b in binalar),
                    "uyari": rota.tur_uyarisi(binalar),
                    "ozet": ozet, "mesaj": "Bugünkü listeniz zaten hazır."}
        conn.execute("UPDATE gorev SET durum='tamam' WHERE id=?", (mevcut["id"],))
        mevcut = None

    baslangic = None
    if girdi.baslangic and len(girdi.baslangic) == 2:
        baslangic = (float(girdi.baslangic[0]), float(girdi.baslangic[1]))
    haric = _acik_planli(conn, gun)
    binalar = rota.gunluk_rota(conn, int(k["bolge"]), baslangic, girdi.adet, gun, haric=haric)
    if not binalar:
        conn.commit()
        return {"gorev_id": None, "tarih": gun.isoformat(), "kaynak": "algoritma", "notu": None,
                "binalar": [], "toplam_mesafe_m": 0, "ozet": _gorev_ozet(conn, None),
                "uyari": None,
                "mesaj": "Bölgenizde şu an ziyaret edilecek bina kalmadı."}

    gorev_id = _gorev_yaz(conn, k["id"], gun, binalar, "algoritma", k["id"])
    conn.commit()
    return {
        "gorev_id": gorev_id,
        "tarih": gun.isoformat(),
        "kaynak": "algoritma",
        "notu": None,
        "binalar": _gorev_binalari(conn, gorev_id),
        "toplam_mesafe_m": rota.toplam_mesafe_m(binalar),
        # Tur bir günde gezilemeyecek kadar uzunsa satışçı bunu SABAH görmeli.
        "uyari": rota.tur_uyarisi(binalar),
        "ozet": _gorev_ozet(conn, gorev_id),
    }


class AtamaGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kullanici_id: int
    tarih: str | None = None
    bina_serial: list[str] | None = None
    mahalle: str | None = None
    ilce: str | None = None
    bbox: list[float] | None = None          # [lat1, lon1, lat2, lon2]
    adet: int = Field(default=ayarlar.VARSAYILAN_ADET, ge=1, le=ayarlar.EN_FAZLA_ADET)
    notu: str | None = Field(default=None, validation_alias=AliasChoices("notu", "not"))


@uygulama.post("/api/gorev/ata")
def gorev_ata(
    girdi: AtamaGirdi,
    k: dict = Depends(izin("satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    hedef = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.kullanici_id,)).fetchone()
    if not hedef or not hedef["aktif"]:
        raise hata(404, "Satışçı bulunamadı.", "kullanici_yok")
    if "satisci" not in yetki.gorev_kumesi_oku(conn, dict(hedef)) or not hedef["bolge"]:
        raise hata(400, "Görev yalnızca satışçıya atanır.", "rol_hatali")

    gun = _tarih_coz(girdi.tarih)
    _gecmis_gorevleri_kapat(conn)
    _planli_temizle(conn, gun)
    bolge = int(hedef["bolge"])

    if girdi.bina_serial:
        isaretler = ",".join("?" * len(girdi.bina_serial))
        satirlar = conn.execute(
            f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
            f"WHERE b.bina_serial IN ({isaretler})",
            tuple(girdi.bina_serial),
        ).fetchall()
        bulunan = {s["bina_serial"] for s in satirlar}
        eksik = [s for s in girdi.bina_serial if s not in bulunan]
        if eksik:
            raise hata(404, f"{len(eksik)} bina bulunamadı: {', '.join(eksik[:3])}", "bina_yok")
        pasifler = [s["bina_serial"] for s in satirlar if s["pasif"]]
        if pasifler:
            raise hata(400, f"{len(pasifler)} bina son tur raporunda yok (pasif): "
                            f"{', '.join(pasifler[:3])}", "bina_pasif")
        yabanci = [s["bina_serial"] for s in satirlar if s["bolge"] != bolge]
        if yabanci:
            raise hata(400, f"{len(yabanci)} bina {hedef['ad']} kişisinin bölgesinde değil.", "baska_bolge")
        adaylar = [dict(s) for s in satirlar]
    elif girdi.mahalle:
        # İlçe verilirse süzgeç daraltılır: aynı adlı mahalleler farklı
        # ilçelerde olabiliyor ("Kurtuluş" Gürsu'da da var Yenişehir'de de,
        # aralarında 41 km).
        kosullar = ["b.bolge=?", "b.mahalle=?"]
        degerler = [bolge, girdi.mahalle]
        if girdi.ilce:
            kosullar.append("b.ilce=?")
            degerler.append(girdi.ilce)
        satirlar = conn.execute(
            f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
            "WHERE " + " AND ".join(kosullar),
            tuple(degerler),
        ).fetchall()
        adaylar = [dict(s) for s in satirlar if rota.uygun_mu(dict(s), gun)]
    elif girdi.bbox and len(girdi.bbox) == 4:
        lat1, lon1, lat2, lon2 = girdi.bbox
        satirlar = conn.execute(
            f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
            "WHERE b.bolge=? AND b.lat BETWEEN ? AND ? AND b.lon BETWEEN ? AND ?",
            (bolge, min(lat1, lat2), max(lat1, lat2), min(lon1, lon2), max(lon1, lon2)),
        ).fetchall()
        adaylar = [dict(s) for s in satirlar if rota.uygun_mu(dict(s), gun)]
    else:
        raise hata(400, "Bina listesi, mahalle veya harita alanı seçin.", "secim_yok")

    if not adaylar:
        raise hata(400, "Seçimde atanacak uygun bina yok.", "bina_yok")

    # Başka bir açık listede bekleyen bina İKİNCİ KEZ ATANAMAZ. Eskiden filtre
    # her şeyi elerse "or adaylar" ile tamamen iptal ediliyordu; sonuç: aynı
    # bina aynı gün iki satışçının listesine düşüyor, iki kişi aynı kapıyı
    # çalıyordu. Artık filtre atlanamaz, boş kalırsa açıkça söylenir.
    haric = _acik_planli(conn, gun)
    adaylar = [a for a in adaylar if a["bina_serial"] not in haric]
    if not adaylar:
        raise hata(400, "Seçtiğiniz binaların hepsi bugün başka bir listede. "
                        "Başka bina seçin ya da o listeyi boşaltın.", "bina_yok")
    for a in adaylar:
        a["oncelik"] = round(rota.oncelik_puani(a, gun), 3)
        a["sinif"] = rota.oncelik_sinifi(a)
    adaylar.sort(key=rota.sirala_anahtari)
    binalar = rota.tur_kur(adaylar, None, min(girdi.adet, len(adaylar)))

    mevcut = _acik_gorev(conn, hedef["id"], gun)
    gorev_id = _gorev_yaz(conn, hedef["id"], gun, binalar, "yonetici", k["id"], girdi.notu, mevcut)
    conn.commit()
    return {
        "gorev_id": gorev_id,
        "tarih": gun.isoformat(),
        "kullanici": _kullanici_kart(hedef),
        "eklenen": len(binalar),
        "binalar": _gorev_binalari(conn, gorev_id),
        "toplam_mesafe_m": rota.toplam_mesafe_m(binalar),
        "uyari": rota.tur_uyarisi(binalar),
        "ozet": _gorev_ozet(conn, gorev_id),
    }


# ============================================================================= ziyaret
class ZiyaretGirdi(BaseModel):
    """Sahadan gelen tek bir ziyaret.

    Bir ziyaretin ÖZÜ ``bina_serial`` + ``sonuc``tur; yalnız bu ikisi yanlışsa
    kayıt reddedilir. Yanındaki alanlar (cihaz künyesi, not, daire) teşhis ve
    ayrıntı içindir: uzunsa kırpılır, anlamsızsa yok sayılır. Sebep basit —
    satışçının kaydı, tarayıcı künyesi iki karakter uzun diye kaybolamaz.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    offline_id: str = Field(min_length=4, max_length=80)
    bina_serial: str
    sonuc: str
    satis_adedi: int = Field(default=0, ge=0, le=500)
    konusulan_daire: int = 0
    notu: str | None = Field(default=None, validation_alias=AliasChoices("notu", "not"))
    lat: float | None = None
    lon: float | None = None
    zaman: str | None = None
    cihaz: str | None = None
    tekrar_tarih: str | None = None
    # Yanlış işlenen bir kaydı düzeltmek için: bu offline_id'li ziyaret iptal
    # edilir, sayaçlardan düşer, yerine bu kayıt geçer.
    duzeltilen_offline_id: str | None = None

    @field_validator("cihaz")
    @classmethod
    def _cihazi_kirp(cls, deger):
        return (deger or "").strip()[:80] or None

    @field_validator("notu")
    @classmethod
    def _notu_kirp(cls, deger):
        return (deger or "").strip()[:1000] or None

    @field_validator("konusulan_daire", mode="before")
    @classmethod
    def _daireyi_coz(cls, deger):
        """Uygulama buraya serbest metin de yazabiliyor ("3", "3. kat", "")."""
        if deger is None or deger == "":
            return 0
        if isinstance(deger, bool):
            return 0
        if isinstance(deger, (int, float)):
            return max(0, min(2000, int(deger)))
        rakamlar = "".join(k for k in str(deger) if k.isdigit())[:4]
        return max(0, min(2000, int(rakamlar))) if rakamlar else 0


def _zamani_coz(ham, an):
    """Sahadan gelen zaman damgasını Türkiye saatine çevirir ve pencereye sıkıştırır.

    İki gerçek hatayı birden kapatır:
      1. Uygulama ``new Date().toISOString()`` ile UTC gonderiyordu; sunucu "Z"yi
         kırpıp Türkiye saati sanıyordu. Her kayıt 3 saat geriye yazılıyor, daha
         SONRA yapılan ziyaret "daha eski" görünüp binanın durumunu
         güncellemiyordu. Gece 00:00-03:00 arası her ziyaret DÜNE düşüyordu.
      2. İleri tarihli tek bir kayıt (bozuk saatli telefon) binayı kalıcı olarak
         iş havuzundan düşürüyordu: 2031 damgalı "girilemedi" 30 günlük soğumayı
         sonsuza uzatıyordu.
    """
    metin = (ham or "").strip()
    if not metin:
        return ayarlar.zaman_metni(an)
    try:
        cozulen = dt.datetime.fromisoformat(metin.replace("Z", "+00:00").replace(" ", "T"))
    except ValueError:
        return ayarlar.zaman_metni(an)
    if cozulen.tzinfo is not None:
        cozulen = cozulen.astimezone(ayarlar.TR).replace(tzinfo=None)
    # Saat dilimi yoksa yerel saat kabul edilir (eski istemciler).
    cozulen = cozulen.replace(microsecond=0)
    if cozulen > an + dt.timedelta(minutes=ayarlar.ZAMAN_ILERI_DK):
        return ayarlar.zaman_metni(an)
    if cozulen < an - dt.timedelta(days=ayarlar.ZAMAN_GERI_GUN):
        return ayarlar.zaman_metni(an)
    return ayarlar.zaman_metni(cozulen)


def _bina_durumunu_kur(conn, bina_serial):
    """``bina_durum`` satırını GEÇERLİ (iptal edilmemiş) ziyaretlerden yeniden kurar.

    İptal sonrası sayaçların ve "son durum"un elle düzeltilmesi hataya açık;
    tek doğru kaynak ziyaret tablosudur. Çevrimdışı kuyruk sırasız gelse de
    sonuç aynı çıkar.
    """
    satirlar = conn.execute(
        "SELECT zaman, sonuc, satis_adedi, kullanici_id FROM ziyaret "
        "WHERE bina_serial=? AND iptal=0 ORDER BY zaman, id",
        (bina_serial,),
    ).fetchall()
    if not satirlar:
        conn.execute(
            "UPDATE bina_durum SET durum='bekliyor', son_ziyaret=NULL, son_kullanici_id=NULL, "
            "son_sonuc=NULL, tekrar_tarih=NULL, toplam_satis=0, ziyaret_sayisi=0 "
            "WHERE bina_serial=?",
            (bina_serial,),
        )
        return
    son = satirlar[-1]
    toplam_satis = sum(int(z["satis_adedi"] or 0) for z in satirlar if z["sonuc"] == "satis")
    durum = ayarlar.SONUC_DURUM[son["sonuc"]]
    tekrar = None
    gun = dt.date.fromisoformat(son["zaman"][:10])
    if son["sonuc"] == "randevu":
        tekrar = (gun + dt.timedelta(days=ayarlar.RANDEVU_GUN)).isoformat()
    elif son["sonuc"] == "evde_yok":
        tekrar = (gun + dt.timedelta(days=ayarlar.EVDE_YOK_GUN)).isoformat()
    conn.execute(
        "UPDATE bina_durum SET durum=?, son_ziyaret=?, son_kullanici_id=?, son_sonuc=?, "
        "tekrar_tarih=?, toplam_satis=?, ziyaret_sayisi=? WHERE bina_serial=?",
        (durum, son["zaman"], son["kullanici_id"], son["sonuc"], tekrar,
         toplam_satis, len(satirlar), bina_serial),
    )


def _ziyaret_isle(conn, k, g):
    if g.sonuc not in ayarlar.ZIYARET_SONUCLARI:
        raise hata(400, "Geçersiz sonuç: " + str(g.sonuc), "sonuc_gecersiz")
    bina = conn.execute(
        "SELECT b.bina_serial, b.bolge, b.daire, b.res_hp FROM bina b "
        "JOIN bina_durum d USING(bina_serial) WHERE b.bina_serial=?",
        (g.bina_serial,),
    ).fetchone()
    if not bina:
        raise hata(404, "Bina bulunamadı.", "bina_yok")
    # Ziyaret yalnız satış (kendi bölgesi ya da listesi) ve yönetici yazar (spec §2.4-2).
    if not ziyaret_yazabilir(conn, k, g.bina_serial):
        raise hata(403, "Bu bina sizin bölgenizde değil.", "baska_bolge")

    an = ayarlar.simdi()
    zaman = _zamani_coz(g.zaman, an)

    # DÜZELTME: satışçı yanlış düğmeye bastıysa eski kaydı iptal edip yenisini yazar.
    # Böylece "Satış" yerine "Evde yok" işlenen bina iki kez sayılmaz.
    duzeltilen = None
    if g.duzeltilen_offline_id:
        duzeltilen = conn.execute(
            "SELECT * FROM ziyaret WHERE kullanici_id=? AND offline_id=? AND iptal=0",
            (k["id"], g.duzeltilen_offline_id),
        ).fetchone()
        if duzeltilen and duzeltilen["bina_serial"] != g.bina_serial:
            duzeltilen = None          # başka binanın kaydı düzeltilemez

    # Satış adedi binanın daire sayısını aşamaz: kayan bir parmak 500 satış yazıp
    # bütün kapsama sayılarını bozmasın.
    satis = g.satis_adedi if g.sonuc == "satis" else 0
    tavan = max(int(bina["daire"] or 0), int(bina["res_hp"] or 0), 1)
    if satis > tavan:
        raise hata(400, "Bu binada en çok " + str(tavan) + " abonelik olabilir (" +
                   str(satis) + " girildi).", "satis_adedi_yuksek")

    imlec = conn.execute(
        "INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, sonuc, satis_adedi, "
        "konusulan_daire, notu, lat, lon, cihaz, kayit_zamani) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(kullanici_id, offline_id) DO NOTHING",
        (g.offline_id, g.bina_serial, k["id"], zaman, g.sonuc, satis, g.konusulan_daire,
         (g.notu or "").strip() or None, g.lat, g.lon, g.cihaz, ayarlar.zaman_metni(an)),
    )
    if imlec.rowcount == 0:  # aynı kayıt ikinci kez geldi — hiçbir şey iki kez sayılmaz
        eski = conn.execute(
            "SELECT z.id, z.bina_serial, d.durum FROM ziyaret z "
            "JOIN bina_durum d USING(bina_serial) WHERE z.kullanici_id=? AND z.offline_id=?",
            (k["id"], g.offline_id),
        ).fetchone()
        durum = (eski["durum"] if eski else None) or "bekliyor"
        return {"ziyaret_id": eski["id"] if eski else None, "yinelenen": True,
                "bina_serial": eski["bina_serial"] if eski else g.bina_serial,
                "durum": durum, "durum_etiket": ayarlar.DURUM_ETIKET.get(durum, durum),
                "duzeltildi": False, "mesaj": "Bu kayıt zaten alınmıştı."}

    ziyaret_id = int(imlec.lastrowid)
    if duzeltilen is not None:
        conn.execute(
            "UPDATE ziyaret SET iptal=1, iptal_eden_id=?, iptal_zamani=? WHERE id=?",
            (k["id"], ayarlar.zaman_metni(an), duzeltilen["id"]),
        )

    if g.sonuc == "randevu" and (g.tekrar_tarih or "").strip():
        istenen = (g.tekrar_tarih or "").strip()[:10]
    else:
        istenen = None
    _bina_durumunu_kur(conn, g.bina_serial)
    if istenen:
        try:
            dt.date.fromisoformat(istenen)
            conn.execute("UPDATE bina_durum SET tekrar_tarih=? WHERE bina_serial=?",
                         (istenen, g.bina_serial))
        except ValueError:
            pass
    durum = conn.execute(
        "SELECT durum FROM bina_durum WHERE bina_serial=?", (g.bina_serial,)
    ).fetchone()["durum"]

    # Görev binası YALNIZ O GÜNÜN açık görevinde kapatılır. Tarih süzgeci olmadan
    # dünden kalan açık görevdeki aynı bina da kapanıyor ve dünün raporu bugün
    # geriye dönük değişiyordu.
    conn.execute(
        "UPDATE gorev_bina SET durum='tamam' WHERE bina_serial=? AND durum='bekliyor' AND gorev_id IN ("
        "  SELECT id FROM gorev WHERE kullanici_id=? AND durum='acik' AND tarih=?)",
        (g.bina_serial, k["id"], zaman[:10]),
    )
    db.surumu_arttir(conn)
    return {"ziyaret_id": ziyaret_id, "yinelenen": False, "bina_serial": g.bina_serial,
            "durum": durum, "durum_etiket": ayarlar.DURUM_ETIKET.get(durum, durum),
            "duzeltildi": duzeltilen is not None,
            "mesaj": "Düzeltildi." if duzeltilen is not None else "Kaydedildi."}


@uygulama.post("/api/ziyaret")
def ziyaret_ekle(
    girdi: ZiyaretGirdi,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    sonuc = _ziyaret_isle(conn, k, girdi)
    conn.commit()
    gorev = _acik_gorev(conn, k["id"], ayarlar.bugun())
    sonuc["ozet"] = _gorev_ozet(conn, gorev["id"] if gorev else None)
    return sonuc


@uygulama.post("/api/ziyaret/toplu")
def ziyaret_toplu(
    girdiler: list[ZiyaretGirdi],
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Çevrimdışı kuyruğun senkronu. Tek bir kayıt hatalıysa kuyruğun tamamı düşmez.

    HER KAYIT İÇİN TEKİL SONUÇ döner. Uygulama kuyruktan YALNIZCA ``kabul``
    listesindeki ``offline_id``leri siler; ``hatali`` listesindekiler telefonda
    kalır ve satışçıya "N kayıt gönderilemedi" diye gösterilir.

    Eskiden yanıt sadece sayı döndürüyordu, uygulama da kuyruğun TAMAMINI
    siliyordu: sunucunun reddettiği kayıt (ör. yönetici gün içinde bölgeyi
    değiştirdiyse ``baska_bolge``) sessizce ve kalıcı olarak kayboluyordu.
    Sessiz silme hiçbir koşulda olmamalı — bu uygulamanın tek sözü, kaydın
    kaybolmayacağı.
    """
    if len(girdiler) > 500:
        raise hata(400, "Tek seferde en çok 500 kayıt gönderilebilir.", "cok_kayit")
    kaydedilen, yinelenen, kabul, hatali = 0, 0, [], []
    for g in girdiler:
        try:
            sonuc = _ziyaret_isle(conn, k, g)
            yinelenen += 1 if sonuc["yinelenen"] else 0
            kaydedilen += 0 if sonuc["yinelenen"] else 1
            kabul.append(g.offline_id)          # kesin yazıldı ya da zaten vardı
        except HTTPException as exc:
            ayrinti = exc.detail if isinstance(exc.detail, dict) else {"hata": str(exc.detail), "kod": "hata"}
            hatali.append({"offline_id": g.offline_id, **ayrinti})
    conn.commit()
    gorev = _acik_gorev(conn, k["id"], ayarlar.bugun())
    return {"kaydedilen": kaydedilen, "yinelenen": yinelenen,
            "kabul": kabul, "hatali": hatali,
            "ozet": _gorev_ozet(conn, gorev["id"] if gorev else None)}


class IptalGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    neden: str | None = None


@uygulama.post("/api/ziyaret/{ziyaret_id}/iptal")
def ziyaret_iptal(
    ziyaret_id: int,
    girdi: IptalGirdi | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Yanlış işlenen bir ziyareti geri alır.

    Yanlış düğmeye basmak sahada en sık yapılan hatadır ve bugüne kadar geri
    dönüşü yoktu: sayaçlar, kapsama ve Excel raporu kalıcı olarak bozuluyordu.
    Kayıt SİLİNMEZ, iptal edilir; sahada ne olduğunun izi kalır ama bütün
    toplamlardan düşer ve bina durumu kalan GEÇERLİ ziyaretlerden yeniden kurulur.

    Kaydı giren satışçı AYNI GÜN içinde iptal edebilir; yönetici her zaman.
    """
    z = conn.execute("SELECT * FROM ziyaret WHERE id=?", (ziyaret_id,)).fetchone()
    if not z:
        raise hata(404, "Ziyaret kaydı bulunamadı.", "ziyaret_yok")
    if z["iptal"]:
        return {"ziyaret_id": ziyaret_id, "iptal": True, "mesaj": "Bu kayıt zaten iptal edilmişti.",
                "bina_serial": z["bina_serial"]}
    if "yonetici" not in yetki.gorevler(k):
        if z["kullanici_id"] != k["id"]:
            raise hata(403, "Yalnızca kendi kaydınızı geri alabilirsiniz.", "yasak")
        if z["zaman"][:10] != ayarlar.bugun().isoformat():
            raise hata(403, "Geçmiş günün kaydını yalnızca yönetici geri alabilir.", "gec_kaldi")

    conn.execute(
        "UPDATE ziyaret SET iptal=1, iptal_eden_id=?, iptal_zamani=?, "
        "notu=COALESCE(notu,'') || ? WHERE id=?",
        (k["id"], ayarlar.zaman_metni(),
         (" [iptal: " + girdi.neden.strip()[:120] + "]") if (girdi and girdi.neden) else "",
         ziyaret_id),
    )
    _bina_durumunu_kur(conn, z["bina_serial"])

    # O GÜNÜN LİSTESİ DE AÇILIR. Yoksa bina_durum "bekliyor" derken günün
    # listesinde yeşil tikli kalıyordu: satışçı yanlış kaydı geri alıyor ama
    # binayı bugün yeniden gezemiyor, yöneticinin "kalan"ı da bir eksik
    # görünüyordu. Kendi içinde çelişen bir ekran, güveni en hızlı bitiren şey.
    gun = z["zaman"][:10]
    kalan_gecerli = conn.execute(
        "SELECT COUNT(*) FROM ziyaret WHERE bina_serial=? AND kullanici_id=? "
        "AND iptal=0 AND substr(zaman,1,10)=?",
        (z["bina_serial"], z["kullanici_id"], gun),
    ).fetchone()[0]
    if not kalan_gecerli:
        conn.execute(
            "UPDATE gorev_bina SET durum='bekliyor' WHERE bina_serial=? AND durum='tamam' "
            "AND gorev_id IN (SELECT id FROM gorev WHERE kullanici_id=? AND durum='acik' AND tarih=?)",
            (z["bina_serial"], z["kullanici_id"], gun),
        )

    db.surumu_arttir(conn)
    conn.commit()
    gorev = _acik_gorev(conn, k["id"], ayarlar.bugun())
    return {"ziyaret_id": ziyaret_id, "iptal": True, "bina_serial": z["bina_serial"],
            "mesaj": "Kayıt geri alındı.", "ozet": _gorev_ozet(conn, gorev["id"] if gorev else None)}

# ============================================================================= bina
@uygulama.get("/api/bina")
def bina_listesi(
    bolge: int | None = None,
    durum: str | None = None,
    mahalle: str | None = None,
    ilce: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    bolge = bolge_kapsami(k, bolge)
    kosul, deger = [], []
    if bolge is not None:
        kosul.append("b.bolge=?")
        deger.append(int(bolge))
    if durum:
        if durum not in ayarlar.BINA_DURUMLARI:
            raise hata(400, f"Geçersiz durum: {durum}", "durum_gecersiz")
        kosul.append("d.durum=?")
        deger.append(durum)
    if mahalle:
        kosul.append("b.mahalle=?")
        deger.append(mahalle)
    if ilce:
        kosul.append("b.ilce=?")
        deger.append(ilce)
    if q:
        kosul.append("(b.ad LIKE ? OR b.site_adi LIKE ? OR b.sokak LIKE ? OR b.bina_serial LIKE ?)")
        deger.extend([f"%{q}%"] * 4)
    nerede = (" WHERE " + " AND ".join(kosul)) if kosul else ""

    toplam = conn.execute(
        f"SELECT COUNT(*) FROM bina b JOIN bina_durum d USING(bina_serial){nerede}", tuple(deger)
    ).fetchone()[0]
    satirlar = conn.execute(
        f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial){nerede} "
        "ORDER BY b.firsat DESC, b.bina_serial LIMIT ? OFFSET ?",
        tuple(deger) + (limit, offset),
    ).fetchall()
    return {"toplam": toplam, "limit": limit, "offset": offset,
            "binalar": [_bina_kart(s) for s in satirlar]}


@uygulama.get("/api/bina/{bina_serial}")
def bina_detay(
    bina_serial: str,
    k: dict = Depends(izin("bina.oku")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    satir = conn.execute(
        f"SELECT {rota.BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
        "WHERE b.bina_serial=?",
        (bina_serial,),
    ).fetchone()
    if not satir:
        raise hata(404, "Bina bulunamadı.", "bina_yok")
    if not bina_gorebilir(conn, k, bina_serial):
        raise hata(403, "Bu bina sizin bölgenizde değil.", "baska_bolge")

    ziyaretler = conn.execute(
        "SELECT z.id, z.offline_id, z.zaman, z.sonuc, z.satis_adedi, z.konusulan_daire, z.notu, "
        "       z.kullanici_id, k.ad AS kullanici "
        "FROM ziyaret z LEFT JOIN kullanici k ON k.id=z.kullanici_id "
        "WHERE z.bina_serial=? AND z.iptal=0 ORDER BY z.zaman DESC LIMIT 50",
        (bina_serial,),
    ).fetchall()
    from . import ticket as ticket_defteri

    return {
        "bina": _bina_kart(satir),
        "ziyaretler": [
            {**dict(z), "sonuc_etiket": ayarlar.SONUC_ETIKET.get(z["sonuc"], z["sonuc"])}
            for z in ziyaretler
        ],
        # Bu binaya açılmış OneDesk ticket'ları (en yenisi önce). Kart "açık ticket
        # var" rozetini buradan gösterir; aynı sorun için ikinci ticket açılmasın.
        "ticketlar": ticket_defteri.binanin_ticketlari(conn, bina_serial),
    }


# Harita yanıtının DEĞİŞMEYEN yarısı: {bölge: ((bina sayısı, künye sürümü), seri sırası, JSON parçası)}.
# Bina adı, konumu ve fırsatı asla değişmez; yalnız `durum` değişir. Böylece bir
# ziyaret kaydedildiğinde 1,4 MB'ı baştan kurmak yerine sadece durum dizisini
# yeniden yazıyoruz.
_harita_sabit: dict[str, tuple[tuple[int, int], list[str], bytes]] = {}
# Tam yanıt: {bölge: ((veri_surumu, bina_surumu), hazır baytlar)}
_harita_onbellek: dict[str, tuple[tuple[int, int], bytes]] = {}


def _harita_sabiti(conn: sqlite3.Connection, bolge: int | None, anahtar: str):
    # Bina sayısı ya da künye sürümü değiştiyse (bölge planı uygulandı, tur raporu
    # işlendi, "python -m saha.kur" yeniden çalıştı) sunucuyu yeniden başlatmadan tazelenir.
    if bolge is None:
        adet = conn.execute("SELECT COUNT(*) FROM bina WHERE pasif=0").fetchone()[0]
    else:
        adet = conn.execute("SELECT COUNT(*) FROM bina WHERE bolge=? AND pasif=0",
                            (int(bolge),)).fetchone()[0]
    imza = (adet, db.bina_surum_oku(conn))
    saklanan = _harita_sabit.get(anahtar)
    if saklanan and saklanan[0] == imza:
        return saklanan[1], saklanan[2]
    alanlar = ("SELECT b.bina_serial, b.lat, b.lon, b.firsat, b.bolge, "
               "b.ad, b.site_adi, b.sokak, b.kapi_no, b.location_id "
               "FROM bina b ")
    if bolge is None:
        satirlar = conn.execute(alanlar + "WHERE b.pasif=0 ORDER BY b.bina_serial").fetchall()
    else:
        satirlar = conn.execute(alanlar + "WHERE b.bolge=? AND b.pasif=0 ORDER BY b.bina_serial",
                                (int(bolge),)).fetchall()
    seriler = [s["bina_serial"] for s in satirlar]
    parca = json.dumps({
        "adet": len(satirlar),
        "serial": seriler,
        # Haritada bir noktaya dokununca kartta seri numarası değil bina adı çıksın.
        "ad": [_baslik(dict(s)) for s in satirlar],
        # Kartta adın yanında Location Id (BOSS/OneMap'te aranan kimlik)
        "loc": [s["location_id"] or "" for s in satirlar],
        # 5 basamak ~1 m hassasiyet; yanıtı belirgin ölçüde küçültür.
        "lat": [round(s["lat"], 5) for s in satirlar],
        "lon": [round(s["lon"], 5) for s in satirlar],
        "firsat": [s["firsat"] for s in satirlar],
        "bolge": [s["bolge"] for s in satirlar],
        "ofis": ayarlar.OFIS,
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    _harita_sabit[anahtar] = (imza, seriler, parca[1:-1])   # dış süslü parantezler atılır
    return seriler, parca[1:-1]


@uygulama.get("/api/harita")
def harita(
    bolge: int | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Harita için sıkı diziler — 19.706 nokta tek istekte, alan adı tekrarı olmadan."""
    bolge = bolge_kapsami(k, bolge)
    surum = (db.surum_oku(conn), db.bina_surum_oku(conn))
    anahtar = "hepsi" if bolge is None else str(int(bolge))

    saklanan = _harita_onbellek.get(anahtar)
    if saklanan and saklanan[0] == surum:
        return Response(content=saklanan[1], media_type="application/json")

    seriler, sabit = _harita_sabiti(conn, bolge, anahtar)
    durumlar = dict(conn.execute("SELECT bina_serial, durum FROM bina_durum").fetchall())
    durum_parcasi = json.dumps(
        [durumlar.get(x, "bekliyor") for x in seriler], separators=(",", ":"),
    ).encode("utf-8")
    govde = b"{" + sabit + b',"durum":' + durum_parcasi + b"}"
    _harita_onbellek[anahtar] = (surum, govde)
    return Response(content=govde, media_type="application/json")


# Yol ağı büyük ve hiç değişmez: süreç başına bir kez okunur, bellekte tutulur.
_yol_onbellek: dict[str, bytes] = {}


@uygulama.get("/api/yollar")
def yollar(
    bolge: int | None = None,
    k: dict = Depends(izin("satis.kendi")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Haritanın arka planındaki yol çizgileri (``veri/ref/osm_yollar.geojson``).

    Sözleşmede yok; harita bu olmadan da çizilir. Bölge verilirse o bölgenin
    binalarını çevreleyen kutuya kırpılır — telefona gereksiz veri gitmesin.
    """
    bolge = bolge_kapsami(k, bolge)
    # Bölge kutusu bölge planıyla değişir: anahtara künye sürümü girer.
    anahtar = ("hepsi" if bolge is None else str(int(bolge))) + f"@{db.bina_surum_oku(conn)}"
    saklanan = _yol_onbellek.get(anahtar)
    if saklanan is None:
        yol = ayarlar.VERI_YOLLAR
        if not yol.exists():
            raise hata(404, "Yol ağı dosyası bulunamadı.", "yol_yok")
        veri = json.loads(yol.read_text(encoding="utf-8"))
        ozellikler = veri.get("features", [])
        if bolge is not None:
            kutu = conn.execute(
                "SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM bina WHERE bolge=?",
                (int(bolge),),
            ).fetchone()
            if kutu and kutu[0] is not None:
                ozellikler = _yollari_kirp(ozellikler, *kutu)
        saklanan = json.dumps(
            {"type": "FeatureCollection", "features": ozellikler}, ensure_ascii=False,
        ).encode("utf-8")
        _yol_onbellek[anahtar] = saklanan
    return Response(content=saklanan, media_type="application/json",
                    headers={"Cache-Control": "public, max-age=86400"})


def _yollari_kirp(ozellikler: list, lat_min, lat_max, lon_min, lon_max, pay: float = 0.01) -> list:
    """Kutuya değmeyen yolları atar (kaba ama hızlı: her çizginin kendi kutusuna bakar)."""
    lat1, lat2 = lat_min - pay, lat_max + pay
    lon1, lon2 = lon_min - pay, lon_max + pay

    def deger(koordinatlar) -> bool:
        ax = [c[0] for c in koordinatlar]
        ay = [c[1] for c in koordinatlar]
        return not (max(ax) < lon1 or min(ax) > lon2 or max(ay) < lat1 or min(ay) > lat2)

    kalan = []
    for o in ozellikler:
        g = o.get("geometry") or {}
        tur, koor = g.get("type"), g.get("coordinates") or []
        if tur == "LineString" and koor and deger(koor):
            kalan.append(o)
        elif tur == "MultiLineString":
            parcalar = [c for c in koor if c and deger(c)]
            if parcalar:
                kalan.append({**o, "geometry": {"type": "MultiLineString", "coordinates": parcalar}})
    return kalan


# ============================================================================= özet
@uygulama.get("/api/ozet/gun")
def ozet_gun(
    tarih: str | None = None,
    k: dict = Depends(izin("satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    gun = _tarih_coz(tarih).isoformat()
    satiscilar = conn.execute(
        "SELECT * FROM kullanici WHERE rol='satisci' ORDER BY bolge, id"
    ).fetchall()
    satirlar, toplam = [], {"ziyaret": 0, "satis": 0, "ret": 0, "randevu": 0, "kalan": 0,
                            "satis_adedi": 0, "gorev_toplam": 0, "gorev_tamam": 0}
    for s in satiscilar:
        z = conn.execute(
            "SELECT COUNT(*) AS ziyaret, "
            "COALESCE(SUM(CASE WHEN sonuc='satis' THEN 1 ELSE 0 END),0) AS satis, "
            "COALESCE(SUM(satis_adedi),0) AS satis_adedi, "
            "COALESCE(SUM(CASE WHEN sonuc='ilgilenmedi' THEN 1 ELSE 0 END),0) AS ret, "
            "COALESCE(SUM(CASE WHEN sonuc='randevu' THEN 1 ELSE 0 END),0) AS randevu, "
            "COALESCE(SUM(CASE WHEN sonuc='evde_yok' THEN 1 ELSE 0 END),0) AS evde_yok, "
            "COALESCE(SUM(CASE WHEN sonuc='girilemedi' THEN 1 ELSE 0 END),0) AS girilemedi, "
            "COALESCE(SUM(CASE WHEN sonuc='altyapi_sorunu' THEN 1 ELSE 0 END),0) AS altyapi_sorunu "
            "FROM ziyaret WHERE kullanici_id=? AND iptal=0 AND substr(zaman,1,10)=?",
            (s["id"], gun),
        ).fetchone()
        gorev = conn.execute(
            "SELECT id FROM gorev WHERE kullanici_id=? AND tarih=? ORDER BY id DESC LIMIT 1",
            (s["id"], gun),
        ).fetchone()
        # İlerleme çubuğunun paydası GÖREV LİSTESİNDEN gelir, ziyaret
        # sayısından değil. Aksi halde aynı binaya ikinci kez gidilince payda da
        # şişiyor ve 25 binalık listede "28 / 28 bina · Listeyi bitirdi" yazıyor,
        # eksik hiç görünmüyordu.
        gb = conn.execute(
            "SELECT COUNT(*) AS toplam, "
            "SUM(CASE WHEN gb.durum='tamam' THEN 1 ELSE 0 END) AS tamam, "
            "SUM(CASE WHEN gb.durum='bekliyor' THEN 1 ELSE 0 END) AS kalan "
            "FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
            "WHERE g.kullanici_id=? AND g.tarih=?",
            (s["id"], gun),
        ).fetchone()
        kalan = int(gb["kalan"] or 0)
        satir = {
            "kullanici_id": s["id"], "ad": s["ad"], "bolge": s["bolge"],
            "gorev_id": gorev["id"] if gorev else None,
            "ziyaret": z["ziyaret"], "satis": z["satis"], "satis_adedi": int(z["satis_adedi"]),
            "ret": z["ret"], "randevu": z["randevu"], "evde_yok": z["evde_yok"],
            "girilemedi": z["girilemedi"], "altyapi_sorunu": z["altyapi_sorunu"], "kalan": kalan,
            "gorev_toplam": int(gb["toplam"] or 0), "gorev_tamam": int(gb["tamam"] or 0),
            # "satis" = satışla biten BİNA, "satis_adedi" = satılan ABONELİK.
            # Dönüşüm binadan hesaplanır; satışçı ekranıyla aynı tanım.
            "donusum": round(z["satis"] / z["ziyaret"], 4) if z["ziyaret"] else 0.0,
        }
        for alan in toplam:
            toplam[alan] += satir[alan]
        satirlar.append(satir)
    toplam["donusum"] = round(toplam["satis"] / toplam["ziyaret"], 4) if toplam["ziyaret"] else 0.0
    return {"tarih": gun, "satiscilar": satirlar, "toplam": toplam}


@uygulama.get("/api/ozet/kapsama")
def ozet_kapsama(
    kirilim: str = Query(default="bolge", pattern="^(bolge|mahalle|ilce)$"),
    bolge: int | None = None,
    k: dict = Depends(izin("satis.kendi", "satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Sudokunun doldurulan kareleri: neye dokunuldu, ne kaldı.

    ÜÇ AYRI SAYI, üçü de farklı soruya cevap verir:
      dokunulan  — binaya gidildi (sonuç ne olursa olsun)
      temas      — kapı açıldı, biriyle konuşuldu (girilemedi/altyapı hariç)
      kalan_firsat — HENÜZ SATILMAMIŞ boş kapı
    Eski tek sayı ("kalan fırsat = dokunulmamış binaların bütün kapıları")
    ilerlemeyi ciddi şekilde abartıyordu: 753 satışla ~38.000 kapı bitmiş
    görünüyordu. Manşet cümlenin doğru olması, sistemin ikna gücünün tamamı.
    """
    bolge = bolge_kapsami(k, bolge)
    # Mahalle kırılımında İLÇE de gruba girer: Bursa'da "Yeni" mahallesi dört
    # ayrı ilçede var ve tek satırda toplanınca yönetici 41 km aralıktaki iki
    # yerleşimi tek liste sanıyordu.
    sutun = {"bolge": "b.bolge", "mahalle": "b.mahalle", "ilce": "b.ilce"}[kirilim]
    gruplar = "b.ilce, b.mahalle" if kirilim == "mahalle" else sutun
    # Son tur raporunda olmayan (pasif) bina kapsamaya girmez: artık satılacak kapı değil.
    kosul, deger = ["b.pasif=0"], []
    if bolge is not None:
        kosul.append("b.bolge=?")
        deger.append(int(bolge))
    nerede = (" WHERE " + " AND ".join(kosul)) if kosul else ""

    temas_sql = ",".join("'%s'" % x for x in ayarlar.TEMAS_SONUCLARI)
    olculer = (
        "COUNT(*) AS toplam, "
        "SUM(CASE WHEN d.son_ziyaret IS NOT NULL THEN 1 ELSE 0 END) AS dokunulan, "
        f"SUM(CASE WHEN d.son_sonuc IN ({temas_sql}) THEN 1 ELSE 0 END) AS temas, "
        "COALESCE(SUM(b.firsat),0) AS firsat, "
        "COALESCE(SUM(MAX(b.firsat - d.toplam_satis, 0)),0) AS kalan_firsat, "
        "COALESCE(SUM(CASE WHEN d.son_ziyaret IS NULL THEN b.firsat ELSE 0 END),0) "
        "    AS dokunulmayan_firsat, "
        "COALESCE(SUM(d.toplam_satis),0) AS satis, "
        "COALESCE(SUM(CASE WHEN d.toplam_satis>0 THEN 1 ELSE 0 END),0) AS satis_bina"
    )

    sorgu = (
        f"SELECT {sutun} AS ad, b.ilce AS ilce, {olculer} "
        f"FROM bina b JOIN bina_durum d USING(bina_serial){nerede} "
        f"GROUP BY {gruplar} ORDER BY toplam DESC"
    )
    satirlar = []
    for r in conn.execute(sorgu, tuple(deger)).fetchall():
        toplam = r["toplam"] or 0
        ad = r["ad"] if r["ad"] is not None else "Atanmamış"
        satirlar.append({
            "ad": f"{ad} / {r['ilce']}" if (kirilim == "mahalle" and r["ilce"]) else ad,
            "mahalle": ad if kirilim == "mahalle" else None,
            "ilce": r["ilce"] if kirilim == "mahalle" else None,
            "toplam": toplam,
            "dokunulan": r["dokunulan"] or 0,
            "temas": r["temas"] or 0,
            "kalan": toplam - (r["dokunulan"] or 0),
            "oran": round((r["dokunulan"] or 0) / toplam, 4) if toplam else 0.0,
            "firsat": int(r["firsat"]),
            "kalan_firsat": int(r["kalan_firsat"]),
            "dokunulmayan_firsat": int(r["dokunulmayan_firsat"]),
            "satis": int(r["satis"]),
            "satis_bina": int(r["satis_bina"]),
        })
    genel = conn.execute(
        f"SELECT {olculer} FROM bina b JOIN bina_durum d USING(bina_serial){nerede}",
        tuple(deger),
    ).fetchone()
    toplam = genel["toplam"] or 0
    return {
        "kirilim": kirilim,
        "toplam": toplam,
        "dokunulan": genel["dokunulan"] or 0,
        "temas": genel["temas"] or 0,
        "kalan": toplam - (genel["dokunulan"] or 0),
        "oran": round((genel["dokunulan"] or 0) / toplam, 4) if toplam else 0.0,
        "firsat": int(genel["firsat"]),
        "kalan_firsat": int(genel["kalan_firsat"]),
        "dokunulmayan_firsat": int(genel["dokunulmayan_firsat"]),
        "satis": int(genel["satis"]),
        "satis_bina": int(genel["satis_bina"]),
        "satirlar": satirlar,
    }


# ============================================================================= kullanıcı yönetimi (Ekip)
# Spec §5.3.7 + Ek-1 (görev kümesi) + Ek-2 (girişsiz kişiler, personel rehberi). Hepsi ``ekip.yonet``.
# Korumalar (409): kendi görevini değiştiremez (kendi_rolu), kendini pasife alamaz/silemez
# (kendini_silemez), son aktif yönetici düşürülemez/pasife alınamaz/silinemez (son_yonetici).
# Her değişiklik yonetim_kaydi'na yazılır; kişisel veri DEĞERİ (telefon, PIN, kod) yazılmaz.

class KullaniciGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int | None = None
    ad: str = Field(min_length=2, max_length=80)
    telefon: str | None = None          # Ek-2: boş = girişsiz kişi (BOSS Mobil'le çalışır)
    rol: str = "satisci"                # ANA görev: girişte açılan ekran
    gorevler: list[str] | None = None   # Ek-1: görev kümesi; verilmezse yalnız ana görev
    bolge: int | None = None
    etiket: list[str] | None = None     # ["lider"] / ["btk","arama"] — yetki VERMEZ
    boss_ekip: str | None = Field(default=None, max_length=80)
    kapasite: int | None = Field(default=None, ge=1, le=60)
    unvan: str | None = Field(default=None, max_length=120)
    aktif: bool = True


_GOREV_METNI = "Görev Satış, Operasyon, Teknik ya da Yönetici olmalı."


def _kume_coz(rol: str, gorevler: list[str] | None) -> list[str]:
    """Ana görev + küme → sabit sıralı küme. Tanınmayan görev 400."""
    if rol not in yetki.ROLLER:
        raise hata(400, _GOREV_METNI, "rol_hatali")
    kume = set(gorevler or []) | {rol}
    if not kume <= set(yetki.ROLLER):
        raise hata(400, _GOREV_METNI, "rol_hatali")
    return [r for r in yetki.ROLLER if r in kume]


def _bolge_coz(conn: sqlite3.Connection, kume: list[str], bolge: int | None, ad: str | None = None) -> int | None:
    """Bölge yalnız satışta tutulur ve orada zorunludur (spec §5.3.7, Ek-1)."""
    if "satisci" not in kume:
        return None
    ust = db.bolge_sayisi(conn)       # 8 ekipten 14 ekibe çıkınca 14
    if not bolge or not (1 <= int(bolge) <= ust):
        kimin = f"{ad} için " if ad else "Satışçı için "
        raise hata(400, f"{kimin}1-{ust} arası bölge seçin.", "bolge_gecersiz")
    return int(bolge)


def _kume_yaz(conn: sqlite3.Connection, kid: int, kume: list[str]) -> None:
    conn.execute(f"DELETE FROM kullanici_gorev WHERE kullanici_id=? AND rol NOT IN ({','.join('?' * len(kume))})",
                 (kid, *kume))
    conn.executemany("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) VALUES (?,?)",
                     [(kid, r) for r in kume])


def _aktif_yoneticiler(conn: sqlite3.Connection, haric: int | None = None) -> int:
    """Aktif ve kümesinde 'yonetici' olan kişi sayısı (``haric`` dışında)."""
    return int(conn.execute(
        "SELECT COUNT(*) FROM kullanici k WHERE k.aktif=1 AND k.id IS NOT ? AND (k.rol='yonetici' OR EXISTS "
        "(SELECT 1 FROM kullanici_gorev g WHERE g.kullanici_id=k.id AND g.rol='yonetici'))",
        (haric,)).fetchone()[0])


def _son_yonetici_mi(conn: sqlite3.Connection, satir: dict, kume_once: list[str]) -> bool:
    return bool(satir["aktif"]) and "yonetici" in kume_once and _aktif_yoneticiler(conn, satir["id"]) == 0


_SON_YONETICI = "Son aktif yönetici düşürülemez, pasife alınamaz, silinemez."


def _davet_durumu(satir: dict) -> dict:
    bekliyor = bool(satir["telefon"]) and not satir.get("pin_hash") and bool(satir.get("davet_kodu"))
    doldu = bekliyor and _davet_suresi_doldu(satir)
    return {"davet_bekliyor": bekliyor and not doldu, "davet_suresi_doldu": doldu}


def _obek_sahiplikleri(conn: sqlite3.Connection) -> dict[int, list[dict]]:
    """Kişi → ev teknisyeni olduğu öbekler (Ekip listesinde "Teknik · Görükle, Özlüce")."""
    try:
        satirlar = conn.execute("SELECT id, ad, sahip_id FROM obek WHERE aktif=1 AND sahip_id IS NOT NULL "
                                "ORDER BY ad").fetchall()
    except sqlite3.OperationalError:
        return {}
    sonuc: dict[int, list[dict]] = {}
    for r in satirlar:
        sonuc.setdefault(r["sahip_id"], []).append({"id": r["id"], "ad": r["ad"]})
    return sonuc


def _son_etkinlikler(conn: sqlite3.Connection) -> dict[int, str]:
    """Kişi başına son etkinlik: son başarılı giriş ya da son ziyaret kaydı (hangisi yeniyse)."""
    sonuc: dict[int, str] = {}
    for kid, zaman in conn.execute(
            "SELECT k.id, MAX(g.zaman) FROM kullanici k JOIN giris_denemesi g ON g.telefon=k.telefon "
            "WHERE g.basarili=1 GROUP BY k.id").fetchall():
        sonuc[kid] = zaman
    for kid, zaman in conn.execute("SELECT kullanici_id, MAX(kayit_zamani) FROM ziyaret GROUP BY kullanici_id"):
        if zaman and (kid not in sonuc or zaman > sonuc[kid]):
            sonuc[kid] = zaman
    return sonuc


def _kume_haritasi(conn: sqlite3.Connection) -> dict[int, list[str]]:
    harita: dict[int, set[str]] = {}
    for kid, rol in conn.execute("SELECT kullanici_id, rol FROM kullanici_gorev").fetchall():
        harita.setdefault(kid, set()).add(rol)
    return {kid: [r for r in yetki.ROLLER if r in kume] for kid, kume in harita.items()}


def _ekip_karti(satir: dict, kume: list[str], obekler: list[dict], son: str | None, maskeli: bool) -> dict:
    return {**_kullanici_kart(satir, kume, maskeli=maskeli), **_davet_durumu(satir),
            "obekler": obekler, "son_etkinlik": son}


@uygulama.get("/api/kullanici")
def kullanici_listesi(k: dict = Depends(izin("ekip.yonet")), conn: sqlite3.Connection = Depends(baglanti)):
    """Ekip listesi. ``davet_kodu`` artık DÖNMEZ; telefon maskeli (tam hâli tek kişi yanıtında)."""
    satirlar = conn.execute("SELECT * FROM kullanici ORDER BY rol DESC, bolge, id").fetchall()
    kumeler, obekler, son = _kume_haritasi(conn), _obek_sahiplikleri(conn), _son_etkinlikler(conn)
    kisiler = []
    for s in satirlar:
        s = dict(s)
        kisiler.append(_ekip_karti(s, kumeler.get(s["id"], [s["rol"]]), obekler.get(s["id"], []),
                                   son.get(s["id"]), maskeli=True))
    return {"kullanicilar": kisiler, "gorevler": [{"rol": r, "etiket": yetki.ETIKET[r],
                                                   "aciklama": yetki.ACIKLAMA[r]} for r in yetki.ROLLER]}


@uygulama.get("/api/kullanici/{kullanici_id}")
def kullanici_getir(kullanici_id: int, k: dict = Depends(izin("ekip.yonet")),
                    conn: sqlite3.Connection = Depends(baglanti)):
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    s = dict(satir)
    return {"kullanici": _ekip_karti(s, yetki.gorev_kumesi_oku(conn, s),
                                     _obek_sahiplikleri(conn).get(s["id"], []),
                                     _son_etkinlikler(conn).get(s["id"]), maskeli=False)}


def _yeni_davet(conn: sqlite3.Connection, kid: int) -> str:
    kod = guvenlik.davet_kodu_uret()
    conn.execute("UPDATE kullanici SET davet_kodu=?, davet_zamani=? WHERE id=?",
                 (kod, ayarlar.zaman_metni(), kid))
    return kod


@uygulama.post("/api/kullanici")
def kullanici_kaydet(
    girdi: KullaniciGirdi,
    k: dict = Depends(izin("ekip.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    ham_tel = (girdi.telefon or "").strip()
    telefon = _telefon_veya_hata(ham_tel) if ham_tel else None
    kume = _kume_coz(girdi.rol, girdi.gorevler)
    bolge = _bolge_coz(conn, kume, girdi.bolge)
    verilen = girdi.model_fields_set

    if telefon:
        cakisma = conn.execute(
            "SELECT id FROM kullanici WHERE telefon=? AND id IS NOT ?", (telefon, girdi.id)
        ).fetchone()
        if cakisma:
            raise hata(409, "Bu telefon numarası başka bir kullanıcıda kayıtlı.", "telefon_var")

    davet = None
    oturum_dustu = False
    if girdi.id:
        varsa = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.id,)).fetchone()
        if not varsa:
            raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
        varsa = dict(varsa)
        kume_once = yetki.gorev_kumesi_oku(conn, varsa)
        gorev_degisti = girdi.rol != varsa["rol"] or kume != kume_once
        if varsa["id"] == k["id"]:
            if gorev_degisti:
                raise hata(409, "Kendi görevinizi değiştiremezsiniz.", "kendi_rolu")
            if not girdi.aktif:
                raise hata(409, "Kendinizi silemez ya da pasife alamazsınız.", "kendini_silemez")
        if (not girdi.aktif or "yonetici" not in kume) and _son_yonetici_mi(conn, varsa, kume_once):
            raise hata(409, _SON_YONETICI, "son_yonetici")
        # Hesap kapatılınca / görev ya da bölge değişince O KİŞİNİN BÜTÜN CİHAZLARI DÜŞER.
        # Eskiden "pasife al, sonra tekrar aktif et" eski jetonu yeniden geçerli kılıyordu.
        # Tekrar aktif etmek de oturumu düşürür: kapatılmadan önceki jeton yine GEÇERSİZ kalmalı.
        neden = None
        if gorev_degisti:
            neden = "gorev"
        elif (bolge or 0) != (varsa["bolge"] or 0):
            neden = "bolge"
        elif bool(girdi.aktif) != bool(varsa["aktif"]):
            neden = "pasif"
        elif varsa["telefon"] and not telefon:
            # Ek-2: telefonu silinen kişi girişsiz olur; elindeki açık oturum da kapanmalı.
            neden = "cihaz"
        oturum_dustu = neden is not None
        alanlar = {
            "ad": girdi.ad.strip(), "telefon": telefon, "rol": girdi.rol, "bolge": bolge,
            "aktif": 1 if girdi.aktif else 0,
            "etiket": json.dumps(girdi.etiket, ensure_ascii=False) if "etiket" in verilen and girdi.etiket is not None
            else (None if "etiket" in verilen else varsa.get("etiket")),
            "boss_ekip": ((girdi.boss_ekip or "").strip() or None) if "boss_ekip" in verilen else varsa.get("boss_ekip"),
            "kapasite": girdi.kapasite if "kapasite" in verilen else varsa.get("kapasite"),
            "unvan": ((girdi.unvan or "").strip() or None) if "unvan" in verilen else varsa.get("unvan"),
        }
        degisen = sorted(a for a, v in alanlar.items() if v != varsa.get(a))
        conn.execute(
            "UPDATE kullanici SET ad=?, telefon=?, rol=?, bolge=?, aktif=?, etiket=?, boss_ekip=?, kapasite=?, "
            "unvan=?, oturum_no=oturum_no+?, oturum_neden=COALESCE(?, oturum_neden) WHERE id=?",
            (alanlar["ad"], alanlar["telefon"], alanlar["rol"], alanlar["bolge"], alanlar["aktif"],
             alanlar["etiket"], alanlar["boss_ekip"], alanlar["kapasite"], alanlar["unvan"],
             1 if oturum_dustu else 0, neden, girdi.id),
        )
        _kume_yaz(conn, girdi.id, kume)
        # Girişsiz kişiye telefon eklendi: bugünkü davet akışı çalışır (kod yalnız bu yanıtta).
        if telefon and not varsa["telefon"] and not varsa.get("pin_hash"):
            davet = _yeni_davet(conn, girdi.id)
        # Yalnız DEĞİŞEN ALANIN ADI yazılır; telefonun kendisi yazılmaz.
        ozet = {"alanlar": degisen, "oturum_dustu": oturum_dustu}
        if gorev_degisti:
            ozet["gorev"] = {"once": kume_once, "sonra": kume, "ana_once": varsa["rol"], "ana_sonra": girdi.rol}
        eylem = "gorev" if gorev_degisti else ("pasif" if (varsa["aktif"] and not girdi.aktif) else "kisi_duzenle")
        db.yonetim_kaydi(conn, k, eylem, f"kullanici:{girdi.id}", ozet)
        yeni_id = girdi.id
    else:
        davet = guvenlik.davet_kodu_uret() if telefon else None
        imlec = conn.execute(
            "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, davet_zamani, rol, bolge, aktif, olusturma, "
            "etiket, boss_ekip, kapasite, unvan, kaynak) VALUES (?,?,NULL,?,?,?,?,?,?,?,?,?,?,'elle')",
            (girdi.ad.strip(), telefon, davet, ayarlar.zaman_metni() if davet else None, girdi.rol, bolge,
             1 if girdi.aktif else 0, ayarlar.zaman_metni(),
             json.dumps(girdi.etiket, ensure_ascii=False) if girdi.etiket else None,
             (girdi.boss_ekip or "").strip() or None, girdi.kapasite, (girdi.unvan or "").strip() or None),
        )
        yeni_id = int(imlec.lastrowid)
        _kume_yaz(conn, yeni_id, kume)
        db.yonetim_kaydi(conn, k, "kisi_ekle", f"kullanici:{yeni_id}",
                         {"gorevler": kume, "giris_var": bool(telefon)})
    conn.commit()
    satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (yeni_id,)).fetchone())
    yanit = {"kullanici": _kullanici_kart(satir, yetki.gorev_kumesi_oku(conn, satir)),
             "davet_kodu": davet, "oturum_dustu": oturum_dustu}
    if davet:
        yanit["davet_gecerlilik_saat"] = ayarlar.DAVET_GECERLILIK_SAAT
    return yanit


class GorevDegisikligi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    rol: str
    gorevler: list[str] | None = None
    bolge: int | None = None


class GorevlerGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    degisiklikler: list[GorevDegisikligi] = Field(default_factory=list, max_length=500)
    tamam: bool = False


@uygulama.post("/api/kullanici/gorevler")
def kullanici_gorevler(girdi: GorevlerGirdi, k: dict = Depends(izin("ekip.yonet")),
                       conn: sqlite3.Connection = Depends(baglanti)):
    """"Görevleri gözden geçirin" kartı: tek işlemde toplu görev değişikliği (spec §1.11-2)."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        degisen = 0
        for d in girdi.degisiklikler:
            satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (d.id,)).fetchone()
            if not satir:
                raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
            satir = dict(satir)
            kume = _kume_coz(d.rol, d.gorevler if d.gorevler is not None else None)
            bolge = _bolge_coz(conn, kume, d.bolge if d.bolge is not None else satir["bolge"], satir["ad"])
            kume_once = yetki.gorev_kumesi_oku(conn, satir)
            if d.rol == satir["rol"] and kume == kume_once and (bolge or 0) == (satir["bolge"] or 0):
                continue
            if satir["id"] == k["id"] and (d.rol != satir["rol"] or kume != kume_once):
                raise hata(409, "Kendi görevinizi değiştiremezsiniz.", "kendi_rolu")
            neden = "gorev" if (d.rol != satir["rol"] or kume != kume_once) else "bolge"
            conn.execute("UPDATE kullanici SET rol=?, bolge=?, oturum_no=oturum_no+1, oturum_neden=? WHERE id=?",
                         (d.rol, bolge, neden, d.id))
            _kume_yaz(conn, d.id, kume)
            db.yonetim_kaydi(conn, k, "gorev", f"kullanici:{d.id}",
                             {"once": kume_once, "sonra": kume, "ana_once": satir["rol"], "ana_sonra": d.rol})
            degisen += 1
        if _aktif_yoneticiler(conn) == 0:
            raise hata(409, _SON_YONETICI, "son_yonetici")
        if girdi.tamam:
            db.ayar_yaz(conn, "gorev_gozden_gecirildi", "1")
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return {"degisen": degisen}


@uygulama.post("/api/kullanici/{kullanici_id}/davet")
def kullanici_davet(kullanici_id: int, k: dict = Depends(izin("ekip.yonet")),
                    conn: sqlite3.Connection = Depends(baglanti)):
    """Yeni 6 haneli davet kodu: 48 saat geçerli, YALNIZ bu yanıtta gösterilir."""
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    if not satir["telefon"]:
        raise hata(409, "Bu kişinin telefonu yok (girişsiz). Önce telefon ekleyin.", "telefon_yok")
    if satir["pin_hash"]:
        raise hata(409, "Bu kişinin PIN'i var. Unuttuysa 'PIN'i sıfırla'yı kullanın.", "pin_var")
    kod = _yeni_davet(conn, kullanici_id)
    db.yonetim_kaydi(conn, k, "davet", f"kullanici:{kullanici_id}")
    conn.commit()
    bitis = ayarlar.simdi() + dt.timedelta(hours=ayarlar.DAVET_GECERLILIK_SAAT)
    return {"davet_kodu": kod, "gecerlilik": f"{ayarlar.DAVET_GECERLILIK_SAAT} saat",
            "gecerlilik_bitis": ayarlar.zaman_metni(bitis)}


# Silme ilişki sayımında insanın okuyacağı karşılık (tablo.sütun → "312 ziyaret").
_ILISKI_ETIKETI = {
    "ziyaret.kullanici_id": "ziyaret",
    "ziyaret.iptal_eden_id": "iptal ettiği ziyaret",
    "bina_durum.son_kullanici_id": "binada son ziyaret kaydı",
    "gorev.kullanici_id": "görev listesi",
    "gorev.olusturan_id": "oluşturduğu görev listesi",
    "bolge_plani.olusturan_id": "bölge planı",
    "tur_raporu.yukleyen_id": "tur raporu yüklemesi",
    "tur_raporu.uygulayan_id": "tur raporu uygulaması",
    "ticket.olusturan_id": "ticket kaydı",
    "ticket_gecmis.kullanici_id": "ticket geçmişi kaydı",
    "is_emri.atanan_id": "iş emri",
    "obek.sahip_id": "öbeğin ev teknisyenliği",
    "obek.yedek_id": "öbeğin yedek teknisyenliği",
}
_OBEK_BAGLARI = ("obek.sahip_id", "obek.yedek_id")


def _kullanici_fklari(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """kullanici'ye giden BÜTÜN yabancı anahtarlar, dinamik (yeni tablolar kendiliğinden girer).

    ``kullanici_gorev`` engel sayılmaz: kişiyle birlikte silinir (ON DELETE CASCADE, Ek-1).
    """
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT m.name, p.\"from\" FROM sqlite_master m, pragma_foreign_key_list(m.name) p "
        "WHERE m.type='table' AND p.\"table\"='kullanici' AND m.name NOT IN ('kullanici','kullanici_gorev') "
        "ORDER BY m.name, p.\"from\"").fetchall()]


def _iliskiler(conn: sqlite3.Connection, satir: dict, k: dict) -> dict:
    kid = satir["id"]
    sayilar: dict[str, int] = {}
    for tablo, sutun in _kullanici_fklari(conn):
        n = conn.execute(f'SELECT COUNT(*) FROM "{tablo}" WHERE "{sutun}"=?', (kid,)).fetchone()[0]
        if n:
            sayilar[f"{tablo}.{sutun}"] = int(n)
    acik_is = 0
    try:
        acik_is = int(conn.execute(
            "SELECT COUNT(*) FROM is_emri WHERE atanan_id=? AND durum NOT IN ('cozuldu','kapandi')",
            (kid,)).fetchone()[0])
    except sqlite3.OperationalError:
        pass
    obek = sum(n for a, n in sayilar.items() if a in _OBEK_BAGLARI)
    diger = {a: n for a, n in sayilar.items() if a not in _OBEK_BAGLARI}
    # Gösterim verisi: demo ziyaretleri ve "Gösterim verisi" görev listeleri (spec §6.10).
    demo_ziyaret = int(conn.execute(
        "SELECT COUNT(*) FROM ziyaret WHERE kullanici_id=? AND offline_id LIKE 'demo-%'", (kid,)).fetchone()[0])
    demo_gorev = int(conn.execute(
        "SELECT COUNT(*) FROM gorev WHERE kullanici_id=? AND notu='Gösterim verisi'", (kid,)).fetchone()[0])
    # Gösterim listelerini kişi "kendisi oluşturmuş" sayılır (olusturan_id = kişi): o bağ da gösterim verisidir.
    demo_olusturdugu = int(conn.execute(
        "SELECT COUNT(*) FROM gorev WHERE olusturan_id=? AND notu='Gösterim verisi'", (kid,)).fetchone()[0])
    demo_sayilari = {"ziyaret.kullanici_id": demo_ziyaret, "gorev.kullanici_id": demo_gorev,
                     "gorev.olusturan_id": demo_olusturdugu}
    # bina_durum.son_kullanici_id ziyaretlerden türer: ziyaretlerin hepsi gösterimse o da gösterimdir.
    hepsi_demo = bool(diger) and all(
        a == "bina_durum.son_kullanici_id" or (a in demo_sayilari and n == demo_sayilari[a])
        for a, n in diger.items())
    engeller = []
    if kid == k["id"]:
        engeller.append("kendini_silemez")
    if _son_yonetici_mi(conn, satir, yetki.gorev_kumesi_oku(conn, satir)):
        engeller.append("son_yonetici")
    if diger:
        engeller.append("iliskili_kayit")
    return {
        "silinebilir": not engeller,
        "engeller": engeller,
        "sayilar": sayilar,
        "acik_is": acik_is,
        "obek_sahipligi": obek,
        "obekleri_birak_gerekli": obek > 0,
        "demo": demo_ziyaret + demo_gorev,
        "hepsi_demo": hepsi_demo,
        "etiketler": [{"metin": _ILISKI_ETIKETI.get(a, a.split(".")[0] + " kaydı"), "sayi": n}
                      for a, n in sayilar.items()],
    }


@uygulama.get("/api/kullanici/{kullanici_id}/iliskiler")
def kullanici_iliskileri(kullanici_id: int, k: dict = Depends(izin("ekip.yonet")),
                         conn: sqlite3.Connection = Depends(baglanti)):
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    return _iliskiler(conn, dict(satir), k)


def _iliski_cumlesi(il: dict) -> str:
    parca = [f"{n} {e['metin']}" for e in il["etiketler"] for n in [e["sayi"]]
             if not e["metin"].startswith("öbeğin")]
    return ", ".join(parca) if parca else "ilişkili kayıtları"


@uygulama.delete("/api/kullanici/{kullanici_id}", status_code=204)
def kullanici_sil(kullanici_id: int, obekleri_birak: int = Query(default=0, ge=0, le=1),
                  k: dict = Depends(izin("ekip.yonet")), conn: sqlite3.Connection = Depends(baglanti)):
    """Yalnız kaydı olmayan kişi silinir; kaydı olan pasife alınır (F13). Kontrol + silme TEK işlem."""
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
        if not satir:
            raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
        satir = dict(satir)
        il = _iliskiler(conn, satir, k)
        if "kendini_silemez" in il["engeller"]:
            raise hata(409, "Kendinizi silemez ya da pasife alamazsınız.", "kendini_silemez")
        if "son_yonetici" in il["engeller"]:
            raise hata(409, _SON_YONETICI, "son_yonetici")
        if "iliskili_kayit" in il["engeller"] or (il["obek_sahipligi"] and not obekleri_birak):
            detay = {"hata": f"Bu kişi silinemez: {_iliski_cumlesi(il)} var. Pasife alabilirsiniz."
                     if "iliskili_kayit" in il["engeller"]
                     else "Bu kişi öbeklerin teknisyeni. Öbekleri teknisyensiz bırakarak silmek için onaylayın.",
                     "kod": "iliskili_kayit", **{a: il[a] for a in ("sayilar", "etiketler", "acik_is",
                                                                    "obek_sahipligi", "hepsi_demo")}}
            raise HTTPException(status_code=409, detail=detay)
        birakilan = 0
        if il["obek_sahipligi"]:
            birakilan += conn.execute("UPDATE obek SET sahip_id=NULL WHERE sahip_id=?", (kullanici_id,)).rowcount
            birakilan += conn.execute("UPDATE obek SET yedek_id=NULL WHERE yedek_id=?", (kullanici_id,)).rowcount
        conn.execute("DELETE FROM kullanici_gorev WHERE kullanici_id=?", (kullanici_id,))
        if satir["telefon"]:
            conn.execute("DELETE FROM giris_denemesi WHERE telefon=?", (satir["telefon"],))
        conn.execute("DELETE FROM kullanici WHERE id=?", (kullanici_id,))
        db.yonetim_kaydi(conn, k, "kisi_sil", f"kullanici:{kullanici_id}",
                         {"gorevler": yetki.gorev_kumesi_oku(conn, satir) or [satir["rol"]],
                          "obek_birakildi": birakilan})
        conn.execute("COMMIT")
    except sqlite3.IntegrityError:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise hata(409, "Bu kişi silinemez: başka kayıtlarla bağlantılı. Pasife alabilirsiniz.", "iliskili_kayit")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    return Response(status_code=204)


class IsAktarGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    hedef_id: int


@uygulama.post("/api/kullanici/{kullanici_id}/is-aktar")
def kullanici_is_aktar(kullanici_id: int, girdi: IsAktarGirdi, k: dict = Depends(izin("ekip.yonet")),
                       conn: sqlite3.Connection = Depends(baglanti)):
    """Açık işleri başka bir teknik kişiye aktarır; her iş kendi olayıyla (``operasyon.v2.akis.ata``)."""
    hedef = conn.execute("SELECT * FROM kullanici WHERE id=?", (girdi.hedef_id,)).fetchone()
    if (not hedef or not hedef["aktif"] or girdi.hedef_id == kullanici_id
            or "teknik" not in yetki.gorev_kumesi_oku(conn, dict(hedef))):
        raise hata(422, "Seçilen kişi aktif bir teknik görevli değil.", "teknik_gecersiz")
    try:
        from operasyon.v2 import akis
    except ImportError:
        raise hata(503, "İş emri modülü hazır değil.", "hazir_degil")
    import uuid

    toplu_id = uuid.uuid4().hex[:12]
    isler = conn.execute("SELECT is_no, surum FROM is_emri WHERE atanan_id=? "
                         "AND durum NOT IN ('cozuldu','kapandi') ORDER BY is_no", (kullanici_id,)).fetchall()
    aktarilan, atlanan = [], []
    if conn.in_transaction:
        conn.commit()
    for is_no, surum in isler:
        try:
            akis.ata(conn, is_no, girdi.hedef_id, k, surum=surum, yine_de=True, toplu_id=toplu_id, kaynak="elle")
            conn.commit()
            aktarilan.append(is_no)
        except Exception as exc:  # her iş kendi başına; biri takılırsa diğerleri sürer
            if conn.in_transaction:
                conn.rollback()
            atlanan.append({"is_no": is_no, "kod": getattr(exc, "kod", type(exc).__name__)})
    db.yonetim_kaydi(conn, k, "is_aktar", f"kullanici:{kullanici_id}",
                     {"hedef": f"kullanici:{girdi.hedef_id}", "aktarilan": len(aktarilan), "atlanan": len(atlanan),
                      "toplu_id": toplu_id})
    conn.commit()
    return {"toplu_id": toplu_id, "aktarilan": len(aktarilan), "atlanan": atlanan}


class AyarGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    yardim_telefon: str | None = None
    yardim_ad: str | None = None


@uygulama.post("/api/ayar")
def ayar_kaydet(
    girdi: AyarGirdi,
    k: dict = Depends(izin("veri.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Giriş ekranında görünecek yardım numarası.

    Sözleşmede yok; "giriş yapamıyorum" diye takılan satışçının tek çaresi
    WhatsApp'a dönmek olmasın diye eklendi.
    """
    if girdi.yardim_telefon is not None:
        ham = girdi.yardim_telefon.strip()
        db.ayar_yaz(conn, "yardim_telefon", _telefon_veya_hata(ham) if ham else "")
    if girdi.yardim_ad is not None:
        db.ayar_yaz(conn, "yardim_ad", girdi.yardim_ad.strip()[:60])
    db.yonetim_kaydi(conn, k, "ayar", "ayar:yardim")
    conn.commit()
    return {"yardim_telefon": db.ayar_oku(conn, "yardim_telefon"),
            "yardim_ad": db.ayar_oku(conn, "yardim_ad"),
            "mesaj": "Yardım bilgisi kaydedildi."}


@uygulama.get("/api/ayar")
def ayar_oku_ucu(k: dict = Depends(izin("oturum")), conn: sqlite3.Connection = Depends(baglanti)):
    return {"yardim_telefon": db.ayar_oku(conn, "yardim_telefon"),
            "yardim_ad": db.ayar_oku(conn, "yardim_ad")}


@uygulama.post("/api/kullanici/{kullanici_id}/pin-sifirla")
def pin_sifirla(
    kullanici_id: int,
    k: dict = Depends(izin("ekip.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    if not satir["telefon"]:
        raise hata(409, "Bu kişinin telefonu yok (girişsiz). Önce telefon ekleyin.", "telefon_yok")
    kod = guvenlik.davet_kodu_uret()
    conn.execute(
        "UPDATE kullanici SET pin_hash=NULL, davet_kodu=?, davet_zamani=?, oturum_no=oturum_no+1, "
        "oturum_neden='pin' WHERE id=?",
        (kod, ayarlar.zaman_metni(), kullanici_id),
    )
    conn.execute("DELETE FROM giris_denemesi WHERE telefon=?", (satir["telefon"],))
    db.yonetim_kaydi(conn, k, "pin_sifirla", f"kullanici:{kullanici_id}")
    conn.commit()
    return {"kullanici_id": kullanici_id, "davet_kodu": kod,
            "gecerlilik": f"{ayarlar.DAVET_GECERLILIK_SAAT} saat",
            "mesaj": f"{satir['ad']} bu kodla yeni PIN belirleyecek."}


@uygulama.post("/api/kullanici/{kullanici_id}/cihaz-cikis")
def cihaz_cikis(
    kullanici_id: int,
    k: dict = Depends(izin("ekip.yonet")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    """Bu kişinin BÜTÜN cihazlarını çıkış yaptırır — PIN'i değiştirmeden.

    Telefon kaybolduğunda/çalındığında yapılacak ilk hareket budur: kişi kendi
    PIN'iyle yeni telefonundan hemen girebilir, kayıp cihazdaki 30 günlük jeton
    ise anında ölür. PIN sıfırlamak gereksiz yere satışçıyı sahada kilitliyordu
    (yeni PIN belirlemek için yöneticiden davet kodu beklemesi gerekiyordu).
    """
    satir = conn.execute("SELECT * FROM kullanici WHERE id=?", (kullanici_id,)).fetchone()
    if not satir:
        raise hata(404, "Kullanıcı bulunamadı.", "kullanici_yok")
    conn.execute("UPDATE kullanici SET oturum_no=oturum_no+1, oturum_neden='cihaz' WHERE id=?", (kullanici_id,))
    db.yonetim_kaydi(conn, k, "cihaz_cikis", f"kullanici:{kullanici_id}")
    conn.commit()
    return {
        "kullanici_id": kullanici_id,
        "pin_degismedi": True,
        "mesaj": f"{satir['ad']} adlı kişinin tüm cihazları çıkış yaptı. "
                 "Kendi PIN'iyle yeniden girebilir.",
    }


# ----------------------------------------------------------------------------- personel rehberi (Ek-2)
class RehberGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    metin: str = Field(max_length=400_000)
    uygula: bool = False


class EslemeKurali(BaseModel):
    model_config = ConfigDict(extra="ignore")
    desen: str = Field(min_length=2, max_length=80)
    gorevler: list[str] = Field(min_length=1, max_length=4)


class EslemeGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    esleme: list[EslemeKurali] = Field(max_length=100)


def _ad_anahtari(metin: str) -> str:
    """Türkçe harf duyarsız karşılaştırma anahtarı (BOSS ekip eşleşmesiyle aynı işlev)."""
    try:
        from operasyon.is_emri import anahtar
    except ImportError:  # iş emri modülü yoksa aynı kuralın yalın hâli
        tablo = str.maketrans("ÇĞİIÖŞÜçğıiöşü", "CGIIOSUCGIIOSU")
        return "".join(ch for ch in str(metin).translate(tablo).upper() if ch.isalnum())
    return anahtar(metin)


def _esleme_oku(conn: sqlite3.Connection) -> list[dict]:
    try:
        esleme = json.loads(db.ayar_oku(conn, "unvan_gorev_esleme") or "null")
    except (TypeError, ValueError):
        esleme = None
    if not isinstance(esleme, list):
        esleme = sema_v2.UNVAN_GOREV_ESLEME
    return [e for e in esleme if isinstance(e, dict) and e.get("desen") and e.get("gorevler")]


def _unvan_gorevleri(esleme: list[dict], unvan: str) -> list[str] | None:
    """İlk eşleşen kural kazanır; kümenin ilk görevi ANA görevdir."""
    anahtar = _ad_anahtari(unvan)
    for kural in esleme:
        if _ad_anahtari(kural["desen"]) and _ad_anahtari(kural["desen"]) in anahtar:
            return [r for r in kural["gorevler"] if r in yetki.ROLLER] or None
    return None


# Atmosfer/Pusula "Çalışanlar" listesinden kopyalanan metindeki gürültü satırları.
_REHBER_GURULTU = {"CALISANLAR", "CALISAN", "ARA", "TUMU", "PROFILIGOR", "PROFILIGORUNTULE", "DAHAFAZLA",
                   "MESAJGONDER", "EPOSTA", "TELEFON", "UNVAN", "ADSOYAD", "BIRIM", "DEPARTMAN"}
_UNVAN_SOZCUKLERI = ("MUDUR", "SORUMLU", "UZMAN", "LIDER", "KOORDINATOR", "DANISMAN", "TEMSILCI", "ASISTAN",
                     "SEF", "TEKNISYEN", "OPERATOR", "DIREKTOR", "SEKRETER", "STAJYER", "STOK", "IDARI",
                     "FINANS", "MUHASEBE", "INSANKAYNAKLARI", "YAYILIM", "DESTEK", "YONETICI", "SORUMLUSU",
                     "ELEMANI", "PERSONEL", "MUHENDIS")


def _unvan_satiri_mi(satir: str, esleme: list[dict]) -> bool:
    anahtar = _ad_anahtari(satir)
    if any(_ad_anahtari(k["desen"]) in anahtar for k in esleme):
        return True
    return " - " in satir or "-" in satir.replace(" ", "")[1:-1] or any(s in anahtar for s in _UNVAN_SOZCUKLERI)


def _ad_satiri_mi(satir: str) -> bool:
    kelimeler = satir.split()
    if not 2 <= len(kelimeler) <= 5:
        return False
    return all(any(ch.isalpha() for ch in w) and (w[0].isupper() or not w[0].isalpha())
               and sum(ch.isdigit() for ch in w) == 0 for w in kelimeler)


def rehber_coz(metin: str, esleme: list[dict]) -> tuple[list[dict], int]:
    """Yapıştırılan metin → [{ad, unvan}] (ad satırı + unvan satırı çiftleri) ve okunamayan satır sayısı."""
    satirlar = [" ".join(s.split()) for s in (metin or "").splitlines()]
    satirlar = [s for s in satirlar if s]
    kisiler: list[dict] = []
    okunamayan = 0
    i = 0
    while i < len(satirlar):
        s = satirlar[i]
        a = _ad_anahtari(s)
        if (a in _REHBER_GURULTU or "@" in s or not any(ch.isalpha() for ch in s)
                or (len(s) <= 3 and s.isupper())):
            i += 1
            continue
        if _ad_satiri_mi(s) and not _unvan_satiri_mi(s, esleme):
            sonraki = satirlar[i + 1] if i + 1 < len(satirlar) else ""
            if sonraki and _unvan_satiri_mi(sonraki, esleme):
                kisiler.append({"ad": s, "unvan": sonraki})
                i += 2
                continue
            kisiler.append({"ad": s, "unvan": None})
            i += 1
            continue
        okunamayan += 1
        i += 1
    return kisiler, okunamayan


@uygulama.post("/api/kullanici/rehber")
def kullanici_rehber(girdi: RehberGirdi, k: dict = Depends(izin("ekip.yonet")),
                     conn: sqlite3.Connection = Depends(baglanti)):
    """Personel rehberi (Atmosfer/Pusula "Çalışanlar" listesi) içe aktarımı: önce önizleme, sonra uygula.

    * Ad mevcut bir kişiyle eşleşirse yalnız ``unvan`` yazılır (görevine dokunulmaz).
    * Eşleşmez ve unvan bir göreve eşlenirse GİRİŞSİZ kişi açılır (telefon yok, ``kaynak='rehber'``).
    * Göreve eşlenmeyen unvanlar alınmaz, sayısı raporlanır. İki kez uygulamak çift kayıt üretmez.
    """
    esleme = _esleme_oku(conn)
    kisiler, okunamayan = rehber_coz(girdi.metin, esleme)
    mevcut: dict[str, dict] = {}
    for r in conn.execute("SELECT id, ad, unvan FROM kullanici").fetchall():
        mevcut.setdefault(_ad_anahtari(r["ad"]), dict(r))
    eklenecek, guncellenecek, atlanacak, ayni = [], [], [], 0
    gorulen: set[str] = set()
    for kisi in kisiler:
        anahtar = _ad_anahtari(kisi["ad"])
        if not anahtar or anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        var = mevcut.get(anahtar)
        if var:
            if kisi["unvan"] and kisi["unvan"] != (var["unvan"] or None):
                guncellenecek.append({"id": var["id"], "ad": var["ad"], "unvan_eski": var["unvan"],
                                      "unvan": kisi["unvan"]})
            else:
                ayni += 1
            continue
        gorevler = _unvan_gorevleri(esleme, kisi["unvan"]) if kisi["unvan"] else None
        if not gorevler:
            atlanacak.append({"ad": kisi["ad"], "unvan": kisi["unvan"],
                              "neden": "gorev_yok" if kisi["unvan"] else "unvan_yok"})
            continue
        eklenecek.append({"ad": kisi["ad"], "unvan": kisi["unvan"], "gorevler": gorevler, "rol": gorevler[0]})

    sonuc = {"okunan": len(kisiler), "okunamayan_satir": okunamayan, "ayni": ayni,
             "eklenecek": eklenecek, "guncellenecek": guncellenecek, "atlanacak": atlanacak,
             "sayilar": {"eklenecek": len(eklenecek), "guncellenecek": len(guncellenecek),
                         "atlanacak": len(atlanacak), "ayni": ayni},
             "uygulandi": False}
    if not girdi.uygula:
        return sonuc

    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        simdi = ayarlar.zaman_metni()
        for g in guncellenecek:
            conn.execute("UPDATE kullanici SET unvan=? WHERE id=?", (g["unvan"], g["id"]))
        for e in eklenecek:
            kid = conn.execute(
                "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, olusturma, unvan, kaynak) "
                "VALUES (?,NULL,NULL,NULL,?,NULL,1,?,?,'rehber')",
                (e["ad"], e["rol"], simdi, e["unvan"])).lastrowid
            _kume_yaz(conn, int(kid), [r for r in yetki.ROLLER if r in e["gorevler"]])
        db.yonetim_kaydi(conn, k, "rehber_aktar", "kullanici:*", sonuc["sayilar"])
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    sonuc["uygulandi"] = True
    return sonuc


@uygulama.get("/api/kullanici/rehber/esleme")
def rehber_esleme_oku(k: dict = Depends(izin("ekip.yonet")), conn: sqlite3.Connection = Depends(baglanti)):
    return {"esleme": _esleme_oku(conn),
            "gorevler": [{"rol": r, "etiket": yetki.ETIKET[r]} for r in yetki.ROLLER]}


@uygulama.put("/api/kullanici/rehber/esleme")
def rehber_esleme_yaz(girdi: EslemeGirdi, k: dict = Depends(izin("ekip.yonet")),
                      conn: sqlite3.Connection = Depends(baglanti)):
    kurallar = []
    for kural in girdi.esleme:
        gorevler = [r for r in yetki.ROLLER if r in set(kural.gorevler)]
        if not gorevler or len(gorevler) != len(set(kural.gorevler)):
            raise hata(400, _GOREV_METNI, "rol_hatali")
        # Kullanıcının yazdığı sıra korunur: ilk görev ana görevdir.
        kurallar.append({"desen": kural.desen.strip(), "gorevler": list(dict.fromkeys(kural.gorevler))})
    db.ayar_yaz(conn, "unvan_gorev_esleme", json.dumps(kurallar, ensure_ascii=False))
    db.yonetim_kaydi(conn, k, "ayar", "ayar:unvan_gorev_esleme", {"kural": len(kurallar)})
    conn.commit()
    return {"esleme": kurallar}


# ============================================================================= rapor
@uygulama.get("/api/dosya/rapor.xlsx")
def gunluk_rapor(
    tarih: str | None = None,
    k: dict = Depends(izin("satis.izle")),
    conn: sqlite3.Connection = Depends(baglanti),
):
    gun = _tarih_coz(tarih)
    yol = rapor.gunluk_rapor_yaz(conn, gun)
    return FileResponse(
        yol,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"Saha_Gun_Raporu_{gun.isoformat()}.xlsx",
    )


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
                "hata": "Saha uygulaması henüz derlenmemiş.",
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
               "/api/ilceler", "/api/takip", "/api/aranacaklar", "/api/boss", "/api/kullanici",
               "/api/ticket", "/api/tablolar", "/api/ps26", "/api/ek")


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


def _haritayi_isit() -> None:
    """Harita yanıtının değişmeyen yarısını açılışta hazırlar.

    Böylece yöneticinin ilk harita isteği de, satışçının ilk isteği de hazır
    veriyle karşılanır; kimse "ilk açılış yavaş" demez. Maliyeti açılışta ~1 sn.
    """
    gunluk = logging.getLogger("saha.harita")
    try:
        conn = db.baglan()
    except Exception:
        return
    try:
        if conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == 0:
            return
        _harita_sabiti(conn, None, "hepsi")
        n = db.bolge_sayisi(conn)
        for b in range(1, n + 1):
            _harita_sabiti(conn, b, str(b))
        gunluk.info("Harita önbelleği hazır (%d bölge + şehir geneli).", n)
    except sqlite3.Error as exc:
        gunluk.warning("Harita önbelleği hazırlanamadı: %s", exc)
    finally:
        conn.close()


# ============================================================================= yönlendiriciler
# PWA bağlamasından ÖNCE eklenmeli: "/" bağlaması sonradan eklenen her yolu yutar.

# Faz 2 uçları (veri kalitesi, bölge planlayıcı, tur raporu, ticket, 3B geometri, altlık).
from . import yonetim_uclari  # noqa: E402  (döngüsel içe aktarma: yardımcılar yukarıda tanımlı)

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
    for ad in ("operasyon.v2.api", "saha.tablolar_uclari", "saha.ek_dosya"):
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
