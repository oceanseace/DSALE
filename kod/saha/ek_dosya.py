"""Ticket fotoğrafları (Ek-8): PS26'nın ``imgs/<no>.zip`` arşivlerinin ve telefondan çekilenlerin yeri.

Dosyalar veritabanının yanındaki ``ek/ticket/<ticket_id>/`` klasöründe durur (git dışı; ``saha/.gitignore``
ve ``KORUNAN.txt``). Test ve prova sunucuları ``SAHA_DB`` karalama kopyasını gösterdiği için fotoğrafları da
kendiliğinden o kopyanın yanına yazar; ``SAHA_EK`` ile ayrıca yönlendirilebilir.

Kurallar:
  * Yalnız JPEG ve PNG (içeriğin ilk baytlarına bakılır, dosya adına değil). iPhone HEIC gönderirse
    ``pillow_heif`` kuruluysa JPEG'e çevrilir; değilse Türkçe bir cümleyle reddedilir.
  * Dosya başına 10 MB. Boş dosya, bozuk resim ve arşivdeki "Thumbs.db" gibi resim olmayanlar alınmaz.
  * Aynı ticket'a aynı fotoğraf iki kez eklenmez (``UNIQUE(ticket_id, sha256)``): içe aktarım etkisizdir.
  * Diskteki ad içerikten türetilir (``<sha256>.jpg``); kullanıcının verdiği ad yalnız ekranda görünür.
    Arşivdeki yol ("klasor/../x.jpg") hiçbir zaman diske yol olarak kullanılmaz.
  * Yetki: ticket'ı GÖREBİLEN fotoğrafını görür (spec Ek-8). Ticket defteri (operasyon, yönetici) hepsini;
    satış ve teknik yalnız görebildiği binanın ticket'larını (``bina_gorebilir``). Göremediği ticket 404'tür,
    varlığı sızdırılmaz. Yükleme: ticket defteri + teknik (kendisine atanmış açık işin binası; sahadan kamera).
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from . import ayarlar, db
from .yetki import T, baglanti, bina_gorebilir, gorevler, hata, izin, izinli, teknik_acik_isi_var

EN_BUYUK = 10 * 1024 * 1024          # dosya başına (Ek-8)
KUCUK_PX = 360                       # küçük resmin uzun kenarı
TURLER = {"jpg": "image/jpeg", "png": "image/png"}

# Bu modülün uçlarının izinleri: ``saha/api.py`` bağlarken ``yetki.ROTA_IZNI``'na ekler (``rota_izni_ekle``).
# Kapsam (hangi ticket) uçların içinde ayrıca denetlenir.
GORME = ("ticket.defter", "bina.oku")
YUKLEME = ("ticket.defter", "is.saha")
ROTA_IZNI: dict[tuple[str, str], tuple[str, ...]] = {
    ("GET", "/api/ticket/{ticket_id}/ek"): GORME,
    ("GET", "/api/ticket/{ticket_id}/ek/{ek_id}"): GORME,
    ("GET", "/api/ticket/{ticket_id}/ek/{ek_id}/kucuk"): GORME,
    ("POST", "/api/ticket/{ticket_id}/ek"): YUKLEME,
}


class EkHatasi(Exception):
    """Fotoğraf alınamadı. ``mesaj`` Türkçe; ``kod`` API hata kodu; ``durum`` HTTP durumu."""

    def __init__(self, mesaj: str, kod: str, durum: int = 422):
        super().__init__(mesaj)
        self.mesaj, self.kod, self.durum = mesaj, kod, durum


# ============================================================================= disk
def ek_kok() -> Path:
    """Eklerin kök klasörü: ``SAHA_EK`` ya da veritabanının yanındaki ``ek/``."""
    ozel = os.environ.get("SAHA_EK")
    return Path(ozel) if ozel else db.db_yolu().parent / "ek"


def ticket_dizini(ticket_id: int) -> Path:
    return ek_kok() / "ticket" / str(int(ticket_id))


def _tur(dosya_adi: str) -> str:
    return "png" if dosya_adi.lower().endswith(".png") else "jpg"


def dosya_yolu(ticket_id: int, sha256: str, dosya_adi: str) -> Path:
    return ticket_dizini(ticket_id) / f"{sha256}.{_tur(dosya_adi)}"


def kucuk_yolu(ticket_id: int, sha256: str) -> Path:
    return ticket_dizini(ticket_id) / "kucuk" / f"{sha256}.jpg"


def _atomik_yaz(hedef: Path, icerik: bytes) -> None:
    """Önce geçici dosya, sonra ``os.replace``: yarım yazılmış fotoğraf kalmaz."""
    hedef.parent.mkdir(parents=True, exist_ok=True)
    fd, gecici = tempfile.mkstemp(prefix=".yaziliyor-", dir=hedef.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(icerik)
        os.replace(gecici, hedef)
    except BaseException:
        try:
            os.unlink(gecici)
        except OSError:
            pass
        raise


# ============================================================================= içerik denetimi
_HEIC = {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1", b"heim", b"heis"}


def icerik_turu(icerik: bytes) -> str | None:
    """İlk baytlardan: 'jpg' | 'png' | 'heic' | None (dosya adına güvenilmez)."""
    if icerik[:3] == b"\xff\xd8\xff":
        return "jpg"
    if icerik[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if icerik[4:8] == b"ftyp" and icerik[8:12] in _HEIC:
        return "heic"
    return None


def _pil():
    try:
        from PIL import Image  # noqa: WPS433 — isteğe bağlı: yoksa doğrulama ve küçük resim atlanır
    except ImportError:
        return None
    return Image


def _heic_jpeg(icerik: bytes) -> bytes:
    Image = _pil()
    try:
        import pillow_heif  # noqa: WPS433 — isteğe bağlı
    except ImportError:
        pillow_heif = None
    if Image is None or pillow_heif is None:
        raise EkHatasi("iPhone fotoğrafı (HEIC) bu sunucuda açılamıyor. Telefonun Ayarlar › Kamera › Biçimler "
                       "bölümünden \"En Uyumlu\"yu seçin ya da fotoğrafı JPEG olarak gönderin.", "dosya_turu", 415)
    pillow_heif.register_heif_opener()
    try:
        with Image.open(io.BytesIO(icerik)) as resim:
            cikti = io.BytesIO()
            resim.convert("RGB").save(cikti, "JPEG", quality=88)
    except Exception as exc:  # noqa: BLE001 — bozuk HEIC
        raise EkHatasi("Fotoğraf açılamadı; dosya bozuk olabilir.", "dosya_bozuk") from exc
    return cikti.getvalue()


def _dogrula(icerik: bytes) -> None:
    """Pillow varsa resmi gerçekten açar (bozuk ya da resim kılığında dosya reddedilir)."""
    Image = _pil()
    if Image is None:
        return
    try:
        with Image.open(io.BytesIO(icerik)) as resim:
            resim.verify()
    except Exception as exc:  # noqa: BLE001 — Pillow'un bütün hataları (DecompressionBomb dahil)
        raise EkHatasi("Fotoğraf açılamadı; dosya bozuk olabilir.", "dosya_bozuk") from exc


def hazirla(icerik: bytes, ad: str | None) -> tuple[bytes, str]:
    """Yüklenecek içeriği denetler; (içerik, ekranda görünecek ad) döndürür. Hata → ``EkHatasi``."""
    if not icerik:
        raise EkHatasi("Dosya boş.", "dosya_yok", 400)
    if len(icerik) > EN_BUYUK:
        raise EkHatasi("Fotoğraf çok büyük (en çok 10 MB).", "dosya_buyuk", 413)
    tur = icerik_turu(icerik)
    if tur == "heic":
        icerik, tur = _heic_jpeg(icerik), "jpg"
        if len(icerik) > EN_BUYUK:
            raise EkHatasi("Fotoğraf çok büyük (en çok 10 MB).", "dosya_buyuk", 413)
    if tur not in TURLER:
        raise EkHatasi("Yalnız fotoğraf eklenebilir (JPEG ya da PNG).", "dosya_turu", 415)
    _dogrula(icerik)
    return icerik, gorunen_ad(ad, tur)


def gorunen_ad(ad: str | None, tur: str) -> str:
    """Kullanıcının verdiği ad → ekranda görünen güvenli ad; uzantı içeriğin gerçek türüdür."""
    kok = Path((ad or "").replace("\\", "/")).name
    kok = re.sub(r"\.(jpe?g|png|heic|heif)$", "", kok, flags=re.IGNORECASE)
    kok = re.sub(r"[^\w .()-]+", "_", kok, flags=re.UNICODE).strip(" ._") or "foto"
    return f"{kok[:80]}.{tur}"


# ============================================================================= kayıt
def _satir(r: sqlite3.Row | dict) -> dict:
    r = dict(r)
    tid, eid = int(r["ticket_id"]), int(r["id"])
    return {"id": eid, "ticket_id": tid, "dosya_adi": r["dosya_adi"], "boyut": r["boyut"],
            "olusturma": r["olusturma"], "tur": _tur(r["dosya_adi"]),
            "kucuk": f"/api/ticket/{tid}/ek/{eid}/kucuk", "tam": f"/api/ticket/{tid}/ek/{eid}"}


def liste(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    try:
        satirlar = conn.execute("SELECT * FROM ticket_ek WHERE ticket_id=? ORDER BY olusturma, id",
                                (int(ticket_id),)).fetchall()
    except sqlite3.OperationalError:          # göç öncesi veritabanı: tablo yok
        return []
    return [_satir(r) for r in satirlar]


def sayilar(conn: sqlite3.Connection) -> dict[int, int]:
    """{ticket_id: fotoğraf sayısı} — tablolar ve defter için tek sorgu."""
    try:
        return {int(r[0]): int(r[1]) for r in conn.execute(
            "SELECT ticket_id, COUNT(*) FROM ticket_ek GROUP BY ticket_id")}
    except sqlite3.OperationalError:
        return {}


def var_mi(conn: sqlite3.Connection, ticket_id: int, sha256: str) -> bool:
    return conn.execute("SELECT 1 FROM ticket_ek WHERE ticket_id=? AND sha256=?",
                        (int(ticket_id), sha256)).fetchone() is not None


def ekle(conn: sqlite3.Connection, ticket_id: int, icerik: bytes, ad: str | None,
         olusturma: str | None = None) -> tuple[dict, bool]:
    """Fotoğrafı diske ve ``ticket_ek``'e yazar. Dönüş: (kayıt, yeni_mi). Commit çağıranın işidir.

    Önce dosya (atomik), sonra satır: satır yazılamazsa diskte sahipsiz ama zararsız bir dosya kalır;
    aynı içerik yeniden gelince aynı ada yazılır. Aynı ticket'ta aynı içerik varsa hiçbir şey yazılmaz.
    """
    icerik, gorunen = hazirla(icerik, ad)
    sha = hashlib.sha256(icerik).hexdigest()
    eski = conn.execute("SELECT * FROM ticket_ek WHERE ticket_id=? AND sha256=?", (int(ticket_id), sha)).fetchone()
    if eski:
        yol = dosya_yolu(ticket_id, sha, eski["dosya_adi"])
        if not yol.exists():                   # disk elle temizlenmişse geri yazılır
            _atomik_yaz(yol, icerik)
        return _satir(eski), False
    _atomik_yaz(dosya_yolu(ticket_id, sha, gorunen), icerik)
    imlec = conn.execute(
        "INSERT INTO ticket_ek (ticket_id, dosya_adi, boyut, sha256, olusturma) VALUES (?,?,?,?,?) "
        "ON CONFLICT(ticket_id, sha256) DO NOTHING",
        (int(ticket_id), gorunen, len(icerik), sha, olusturma or ayarlar.zaman_metni()))
    if imlec.rowcount == 0:                    # aynı anda iki yükleme: ikincisi yeni değildir
        satir = conn.execute("SELECT * FROM ticket_ek WHERE ticket_id=? AND sha256=?", (int(ticket_id), sha)).fetchone()
        return _satir(satir), False
    satir = conn.execute("SELECT * FROM ticket_ek WHERE id=?", (imlec.lastrowid,)).fetchone()
    return _satir(satir), True


# ============================================================================= arşiv (PS26 imgs/<no>.zip)
def arsiv_dosyalari(zip_yolu: Path) -> tuple[list[tuple[str, bytes]], int]:
    """Arşivdeki resimler: ([(ad, içerik)], alınmayan sayısı). Resim olmayan (Thumbs.db), 10 MB'ı aşan ya da
    okunamayan girdi alınmaz. Arşivin iç yolları diske hiç yazılmaz (yalnız ad olarak okunur)."""
    alinan: list[tuple[str, bytes]] = []
    alinmayan = 0
    with zipfile.ZipFile(zip_yolu) as zf:
        for bilgi in zf.infolist():
            if bilgi.is_dir():
                continue
            if bilgi.file_size > EN_BUYUK:
                alinmayan += 1
                continue
            try:
                with zf.open(bilgi) as f:
                    icerik = f.read(EN_BUYUK + 1)       # başlık yalan söylese de 10 MB'tan fazla okunmaz
            except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError):
                alinmayan += 1
                continue
            if len(icerik) > EN_BUYUK or icerik_turu(icerik) not in ("jpg", "png", "heic"):
                alinmayan += 1
                continue
            alinan.append((bilgi.filename, icerik))
    return alinan, alinmayan


# ============================================================================= küçük resim
def kucuk_resim(ticket_id: int, sha256: str, dosya_adi: str) -> tuple[Path, str]:
    """Küçük resmin yolu ve türü. İlk istekte üretilip diske yazılır; Pillow yoksa asıl dosya döner."""
    asil = dosya_yolu(ticket_id, sha256, dosya_adi)
    kucuk = kucuk_yolu(ticket_id, sha256)
    if kucuk.exists():
        return kucuk, TURLER["jpg"]
    Image = _pil()
    if Image is None or not asil.exists():
        return asil, TURLER[_tur(dosya_adi)]
    try:
        from PIL import ImageOps

        with Image.open(asil) as resim:
            resim.draft("RGB", (KUCUK_PX * 2, KUCUK_PX * 2))          # JPEG'i küçük çözer: hızlı
            resim = ImageOps.exif_transpose(resim)                     # telefonun döndürme bilgisi
            resim.thumbnail((KUCUK_PX, KUCUK_PX))
            cikti = io.BytesIO()
            resim.convert("RGB").save(cikti, "JPEG", quality=80, optimize=True)
        _atomik_yaz(kucuk, cikti.getvalue())
        return kucuk, TURLER["jpg"]
    except Exception:  # noqa: BLE001 — küçük resim üretilemezse asıl resim gösterilir
        return asil, TURLER[_tur(dosya_adi)]


# ============================================================================= yetki
def ticket_getir_gorunur(conn: sqlite3.Connection, k: dict, ticket_id: int) -> dict:
    """Kişinin GÖREBİLDİĞİ ticket; göremediği ya da olmayan → 404 (varlık sızdırılmaz)."""
    t = conn.execute("SELECT id, bina_serial FROM ticket WHERE id=?", (int(ticket_id),)).fetchone()
    if t and (izinli(k, "ticket.defter") or (t["bina_serial"] and bina_gorebilir(conn, k, t["bina_serial"]))):
        return dict(t)
    raise hata(404, "Ticket bulunamadı.", "ticket_yok")


def yukleyebilir(conn: sqlite3.Connection, k: dict, t: dict) -> bool:
    """Ticket defteri her ticket'a; teknik yalnız kendisine atanmış açık işin binasındaki ticket'a."""
    if izinli(k, "ticket.defter"):
        return True
    return T in gorevler(k) and bool(t.get("bina_serial")) and teknik_acik_isi_var(conn, k, t["bina_serial"])


def _ek_satiri(conn: sqlite3.Connection, ticket_id: int, ek_id: int) -> sqlite3.Row:
    try:
        r = conn.execute("SELECT * FROM ticket_ek WHERE id=? AND ticket_id=?", (int(ek_id), int(ticket_id))).fetchone()
    except sqlite3.OperationalError:
        r = None
    if not r:
        raise hata(404, "Fotoğraf bulunamadı.", "ek_yok")
    return r


# ============================================================================= uçlar
yonlendirici = APIRouter()


@yonlendirici.get("/api/ticket/{ticket_id}/ek")
def ek_listesi(ticket_id: int, k: dict = Depends(izin(*GORME)), conn: sqlite3.Connection = Depends(baglanti)):
    t = ticket_getir_gorunur(conn, k, ticket_id)
    ekler = liste(conn, ticket_id)
    return {"ticket_id": int(ticket_id), "ekler": ekler, "toplam": len(ekler),
            "yukleyebilir": yukleyebilir(conn, k, t), "en_buyuk_bayt": EN_BUYUK,
            "turler": ["image/jpeg", "image/png"]}


def _dosya_yaniti(yol: Path, tur: str, ad: str) -> Response:
    if not yol.exists():
        raise hata(404, "Fotoğraf dosyası diskte bulunamadı.", "ek_yok")
    # Ad ASCII'ye indirgenir (başlıkta Türkçe harf sorun çıkarmasın); asıl ad listede görünür.
    guvenli = re.sub(r"[^A-Za-z0-9._-]+", "_", ad)[:80] or "foto"
    return FileResponse(yol, media_type=tur, headers={"Content-Disposition": f'inline; filename="{guvenli}"'})


@yonlendirici.get("/api/ticket/{ticket_id}/ek/{ek_id}")
def ek_tam(ticket_id: int, ek_id: int, k: dict = Depends(izin(*GORME)),
           conn: sqlite3.Connection = Depends(baglanti)):
    ticket_getir_gorunur(conn, k, ticket_id)
    r = _ek_satiri(conn, ticket_id, ek_id)
    return _dosya_yaniti(dosya_yolu(ticket_id, r["sha256"], r["dosya_adi"]), TURLER[_tur(r["dosya_adi"])],
                         f"ticket-{int(ticket_id)}-{r['dosya_adi']}")


@yonlendirici.get("/api/ticket/{ticket_id}/ek/{ek_id}/kucuk")
async def ek_kucuk(ticket_id: int, ek_id: int, k: dict = Depends(izin(*GORME)),
                   conn: sqlite3.Connection = Depends(baglanti)):
    ticket_getir_gorunur(conn, k, ticket_id)
    r = _ek_satiri(conn, ticket_id, ek_id)
    # İlk istekte resim küçültülür (≈50 ms): olay döngüsünü tutmasın.
    yol, tur = await run_in_threadpool(kucuk_resim, ticket_id, r["sha256"], r["dosya_adi"])
    return _dosya_yaniti(yol, tur, f"kucuk-{r['dosya_adi']}")


async def _govde_oku(istek: Request) -> tuple[bytes, str]:
    """Ham gövde (``X-Dosya-Adi``) ya da multipart (``dosya`` alanı). 10 MB'ı aşan hiç okunmaz."""
    uzunluk = int(istek.headers.get("content-length") or 0)
    if uzunluk > EN_BUYUK + 64 * 1024:
        raise hata(413, "Fotoğraf çok büyük (en çok 10 MB).", "dosya_buyuk")
    tur = (istek.headers.get("content-type") or "").lower()
    if tur.startswith("multipart/form-data"):
        form = await istek.form()
        f = form.get("dosya") or next((v for v in form.values() if hasattr(v, "read")), None)
        if f is None or not hasattr(f, "read"):
            raise hata(400, "Formda 'dosya' alanı yok.", "dosya_yok")
        icerik = await f.read(EN_BUYUK + 1)
        return icerik, getattr(f, "filename", "") or ""
    govde = bytearray()
    async for parca in istek.stream():
        govde.extend(parca)
        if len(govde) > EN_BUYUK:
            raise hata(413, "Fotoğraf çok büyük (en çok 10 MB).", "dosya_buyuk")
    from urllib.parse import unquote

    return bytes(govde), unquote(istek.headers.get("x-dosya-adi", ""))


@yonlendirici.post("/api/ticket/{ticket_id}/ek")
async def ek_yukle(ticket_id: int, istek: Request, k: dict = Depends(izin(*YUKLEME)),
                   conn: sqlite3.Connection = Depends(baglanti)):
    t = ticket_getir_gorunur(conn, k, ticket_id)
    if not yukleyebilir(conn, k, t):
        raise hata(403, "Bu ticket'a fotoğraf ekleyemezsiniz.", "yasak")
    icerik, ad = await _govde_oku(istek)

    def _yaz() -> tuple[dict, bool]:
        try:
            kayit, yeni = ekle(conn, ticket_id, icerik, ad)
        except EkHatasi as exc:
            raise hata(exc.durum, exc.mesaj, exc.kod) from exc
        if yeni:
            db.yonetim_kaydi(conn, k, "ticket_ek", str(int(ticket_id)), {"boyut": kayit["boyut"]})
        conn.commit()
        return kayit, yeni

    kayit, yeni = await run_in_threadpool(_yaz)
    return JSONResponse({"ek": kayit, "zaten_vardi": not yeni,
                         "mesaj": "Fotoğraf eklendi." if yeni else "Bu fotoğraf zaten ekliydi."},
                        status_code=201 if yeni else 200)
