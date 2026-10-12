"""BOSS ile giriş: Turkcell.exe giriş ekranı kullanıcıyı GERÇEK BOSS giriş sayfasına (Brave) gönderir; şifre ve tek
kullanımlık kod yalnız BOSS'a yazılır — uygulama ne görür ne saklar. BOSS sayfasındaki eklenti (BOSS Yardımcısı)
oturum açan BOSS kullanıcısının KİMLİĞİNİ (ad, varsa kullanıcı kodu/unvan) eşleme koduyla bildirir; sunucu onu bir
uygulama hesabına eşler ve oturumu YALNIZ isteği başlatan pencereye verir.

Akış:
  1) Pencere ``POST /api/giris/boss/baslat`` → {istek_id, gizli, ac_yolu}. ``gizli`` yalnız o pencerenin belleğinde
     durur (yoklama onunla yapılır); bekleyen istek 2 dk yaşar, TEK kullanımlıktır. Yalnız bu bilgisayardan
     (127.0.0.1): eklenti de yalnız bu bilgisayardaki sunucuya bildirir.
  2) Kabuk ``ac_yolu``nu (``/boss-giris/<istek_id>``) Brave'de açar; sayfa BOSS'a yönlendirir. Eklenti sekmenin bu
     adresini görür ve ``istek_id``yi hatırlar (chrome.storage.session).
  3) Kullanıcı BOSS'ta oturum açar (ya da zaten açıktır); kanca kimliği sayfanın kendi isteklerinden bulur
     (oturum jetonunun ad alanları, kimlik ucu yanıtı ya da sayfa deposu — değerler yalnız ad/kod/unvan) →
     ``POST /api/giris/boss/kimlik`` {istek_id, ad, kod?, unvan?} (X-Eslesme-Kodu).
  4) Sunucu kimliği hesaba eşler (``kullanici_bul``: Administrator ``turkcell.json`` adıyla; diğerleri ad, eşit adlı
     birden çok kişide unvanla). Pencere ``POST /api/giris/boss/durum`` {istek_id, gizli} ile yoklar; eşleşince bir kez
     oturum jetonu alır (jetonda ``bg`` = BOSS oturum kimliği).
  5) BOSS oturumu bitince (çıkış, giriş sayfası ya da BOSS uçlarında 401) eklenti ``POST /api/giris/boss/bitti``
     der; o BOSS kullanıcısından açılmış uygulama oturumları biter (``yetki.mevcut_kullanici`` ``bg``yi
     ``oturum_acik`` ile denetler → 401 ``boss_oturumu_bitti``; arayüz giriş ekranına döner). Telefon + PIN oturumları
     etkilenmez (yedek giriş yolu).
Bekleyen istekler bellekte (2 dk); açık BOSS oturumları ``ayar.boss_oturumlari`` (JSON) — sunucu yeniden başlasa da
sürer.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import re
import secrets
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from . import ayarlar, db, guvenlik, yetki
from .yetki import baglanti, hata, izin

yonlendirici = APIRouter()

SURE_SN = 120                      # bekleyen giriş isteği bu kadar yaşar
EN_COK_BEKLEYEN = 20
BOSS_ADRESI = "https://boss.turkcell.com.tr/"
AYAR_OTURUM = "boss_oturumlari"
_YEREL = {"127.0.0.1", "::1", "localhost", "testclient"}   # testclient: FastAPI TestClient

_KILIT = threading.Lock()
_BEKLEYEN: dict[str, dict] = {}    # istek_id → {gizli_iz, an, durum, tarayicida, kid, bg, mesaj, kimlik}


def sifirla() -> None:
    with _KILIT:
        _BEKLEYEN.clear()


def _iz(gizli: str) -> str:
    return hashlib.sha256(gizli.encode("utf-8")).hexdigest()


def _temizle(simdi: float) -> None:
    for i in [i for i, b in _BEKLEYEN.items() if simdi - b["an"] > SURE_SN]:
        del _BEKLEYEN[i]


def _yerel_mi(istek: Request) -> bool:
    return bool(istek.client and istek.client.host in _YEREL)


def _yerel_sart(istek: Request) -> None:
    if not _yerel_mi(istek):
        raise hata(403, "BOSS ile giriş yalnız Turkcell uygulamasının açık olduğu bilgisayarda yapılır. "
                        "Telefonda numara ve PIN ile girin.", "yalniz_yerel")


# ----------------------------------------------------------------------------- kimlik → hesap
_TR = str.maketrans({"Ç": "C", "Ğ": "G", "İ": "I", "I": "I", "Ö": "O", "Ş": "S", "Ü": "U", "Â": "A", "Î": "I",
                     "Û": "U"})


def ad_sade(s) -> str:
    """'Ahmet Emirhan  Korkmaz' → 'AHMET EMIRHAN KORKMAZ' (büyük harf, Türkçe harfler sade, noktalama boşluk)."""
    t = str(s or "").replace("i", "İ").replace("ı", "I").upper().translate(_TR)
    return re.sub(r"[^A-Z0-9]+", " ", t).strip()


def _ayni_ad(a: str, b: str) -> bool:
    a, b = ad_sade(a), ad_sade(b)
    return bool(a) and (a == b or sorted(a.split()) == sorted(b.split()))


def _unvan_adi(conn: sqlite3.Connection, satir) -> str:
    k = dict(satir)
    if k.get("unvan_id"):
        try:
            r = conn.execute("SELECT ad FROM unvan WHERE id=?", (k["unvan_id"],)).fetchone()
            if r and r[0]:
                return r[0]
        except sqlite3.OperationalError:
            pass
    return k.get("unvan") or ""


def kullanici_bul(conn: sqlite3.Connection, ad: str | None, unvan: str | None = None) -> tuple[dict | None, str | None]:
    """BOSS kimliği → (aktif uygulama hesabı, hata metni). Administrator: ``turkcell.json``daki ad. Diğerleri: ad
    (büyük/küçük harf, Türkçe harf ve sözcük sırası farkı yok sayılır); aynı adda birden çok kişi varsa unvan."""
    if not ad_sade(ad) or len(ad_sade(ad)) < 3:
        return None, "BOSS kullanıcısının adı okunamadı."
    adm = yetki.administrator_ayari()
    if adm.get("telefon") and adm.get("ad") and _ayni_ad(adm["ad"], ad):
        try:
            yetki.administrator_hesabi_hazirla(conn)
            conn.commit()
        except sqlite3.Error:
            if conn.in_transaction:
                conn.rollback()
        r = conn.execute("SELECT * FROM kullanici WHERE telefon=? AND aktif=1", (adm["telefon"],)).fetchone()
        if r:
            return dict(r), None
    adaylar = [r for r in conn.execute("SELECT * FROM kullanici WHERE aktif=1").fetchall() if _ayni_ad(r["ad"], ad)]
    if len(adaylar) > 1 and ad_sade(unvan):
        adaylar = [r for r in adaylar if ad_sade(_unvan_adi(conn, r)) == ad_sade(unvan)] or adaylar
    if len(adaylar) == 1:
        return dict(adaylar[0]), None
    if len(adaylar) > 1:
        return None, (f"Uygulamada “{ad}” adıyla birden çok hesap var. Yöneticiniz Kişiler'de adları ayırsın ya da "
                      "numara ve PIN ile girin.")
    return None, (f"BOSS kullanıcısı “{ad}” uygulamada bir hesapla eşleşmedi. Yöneticiniz Kişiler'de adınızı BOSS'taki "
                  "gibi yazsın ya da numara ve PIN ile girin.")


# ----------------------------------------------------------------------------- açık BOSS oturumları (kalıcı)
def _oturumlar(conn: sqlite3.Connection) -> dict:
    try:
        v = json.loads(db.ayar_oku(conn, AYAR_OTURUM) or "{}")
    except (ValueError, sqlite3.Error):
        return {}
    return v if isinstance(v, dict) else {}


def _oturum_yaz(conn: sqlite3.Connection, v: dict) -> None:
    db.ayar_yaz(conn, AYAR_OTURUM, json.dumps(v, ensure_ascii=False))
    conn.commit()


def oturum_acik(conn: sqlite3.Connection, bg: str, kid: int) -> bool:
    """Jetondaki BOSS oturumu hâlâ açık mı (BOSS'tan çıkılmadı) ve bu kişinin mi."""
    o = _oturumlar(conn).get(str(bg))
    return bool(o) and int(o.get("kid") or 0) == int(kid)


def _oturum_ac(conn: sqlite3.Connection, kid: int, kimlik: dict) -> str:
    v = _oturumlar(conn)
    sinir = time.time() - ayarlar.TOKEN_GUN * 86400
    v = {b: o for b, o in v.items() if float(o.get("an") or 0) > sinir}
    bg = secrets.token_urlsafe(12)
    v[bg] = {"kid": int(kid), "ad": ad_sade(kimlik.get("ad")), "kod": kimlik.get("kod"), "an": time.time()}
    _oturum_yaz(conn, v)
    return bg


def oturumlari_bitir(conn: sqlite3.Connection, ad: str | None = None, kod: str | None = None,
                     haric: bool = False) -> int:
    """BOSS kimliğine (ad/kod) bağlı uygulama oturumlarını bitirir; kimlik yoksa hepsini. ``haric``: bu kimliğin
    DIŞINDAKİLERİ bitirir (BOSS'ta başka kullanıcı oturum açtı). Bitirilen sayısı döner."""
    v = _oturumlar(conn)
    if not v:
        return 0
    s, kod = ad_sade(ad), (str(kod).strip() if kod else None)

    def bu_mu(o: dict) -> bool:
        if not s and not kod:
            return True
        return bool((s and o.get("ad") and _ayni_ad(o["ad"], s)) or (kod and o.get("kod") == kod))

    kalan = {b: o for b, o in v.items() if (bu_mu(o) if haric else not bu_mu(o))}
    n = len(v) - len(kalan)
    if n:
        _oturum_yaz(conn, kalan)
    return n


# ----------------------------------------------------------------------------- uçlar
class BaslatYanit(BaseModel):
    istek_id: str
    gizli: str
    ac_yolu: str
    sure_sn: int


class DurumGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    istek_id: str = Field(max_length=80)
    gizli: str = Field(max_length=120)


class KimlikGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    istek_id: str = Field(max_length=80)
    ad: str = Field(default="", max_length=120)
    kod: str | None = Field(default=None, max_length=80)
    unvan: str | None = Field(default=None, max_length=120)
    # BOSS başlığındaki bayi metni (ör. "DEHANET ECM"); kaynak: dom (sayfa başlığı) · jwt · uc · depo
    bayi: str | None = Field(default=None, max_length=120)
    kaynak: str | None = Field(default=None, max_length=20)


class BittiGirdi(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ad: str | None = Field(default=None, max_length=120)
    kod: str | None = Field(default=None, max_length=80)
    neden: str | None = Field(default=None, max_length=40)


def _eklenti(x_eslesme_kodu: str | None = Header(default=None)) -> bool:
    """Eklentinin eşleme kodu (BOSS bağlantısı ekranındaki). Kod yoksa/yanlışsa 401."""
    try:
        from operasyon.v2 import boss
    except Exception:  # noqa: BLE001 — iş motoru yoksa BOSS ile giriş de yok
        raise hata(503, "BOSS bağlantısı bu kurulumda yok.", "boss_yok")
    if not x_eslesme_kodu or not boss.kod_dogru(x_eslesme_kodu):
        raise hata(401, "Eşleme kodu yanlış. Uygulamadaki BOSS bağlantısı ekranındaki kodu girin.", "eslesme_yanlis")
    return True


@yonlendirici.post("/api/giris/boss/baslat")
def baslat(istek: Request) -> BaslatYanit:
    _yerel_sart(istek)
    simdi = time.time()
    with _KILIT:
        _temizle(simdi)
        if len(_BEKLEYEN) >= EN_COK_BEKLEYEN:
            raise hata(429, "Çok fazla bekleyen BOSS girişi var. Biraz sonra yeniden deneyin.", "kilitli")
        istek_id, gizli = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
        _BEKLEYEN[istek_id] = {"gizli_iz": _iz(gizli), "an": simdi, "durum": "bekliyor", "tarayicida": False}
    return BaslatYanit(istek_id=istek_id, gizli=gizli, ac_yolu=f"/boss-giris/{istek_id}", sure_sn=SURE_SN)


_SAYFA = """<!doctype html><html lang="tr"><head><meta charset="utf-8">{yonlendir}
<meta name="viewport" content="width=device-width,initial-scale=1"><title>BOSS ile giriş</title>
<style>body{{font:16px system-ui,sans-serif;background:#f5f5f5;color:#1f1f1f;display:grid;place-items:center;
min-height:100vh;margin:0}}main{{max-width:420px;padding:24px;text-align:center}}a{{color:#0050b4}}</style></head>
<body><main><h1>BOSS ile giriş</h1><p>{metin}</p></main></body></html>"""


@yonlendirici.get("/boss-giris/{istek_id}", response_class=HTMLResponse)
def tarayici_sayfasi(istek_id: str, istek: Request):
    """Brave'de açılan ara sayfa: eklenti bu adresten isteği tanır, sayfa 1 sn sonra BOSS'a geçer."""
    _yerel_sart(istek)
    with _KILIT:
        _temizle(time.time())
        b = _BEKLEYEN.get(istek_id)
        if b is not None:
            b["tarayicida"] = True
    if b is None:
        return HTMLResponse(_SAYFA.format(yonlendir="", metin="Bu giriş isteğinin süresi doldu. Turkcell "
                                          "uygulamasında “BOSS ile giriş yap”a yeniden basın."), status_code=410)
    adres = html.escape(BOSS_ADRESI, quote=True)
    return HTMLResponse(_SAYFA.format(
        yonlendir=f'<meta http-equiv="refresh" content="1;url={adres}">',
        metin=f'BOSS açılıyor… Şifrenizi yalnız BOSS sayfasına yazın. Açılmazsa <a href="{adres}">buraya basın</a>.'))


@yonlendirici.post("/api/giris/boss/kimlik")
def kimlik(girdi: KimlikGirdi, conn: sqlite3.Connection = Depends(baglanti), _e: bool = Depends(_eklenti)):
    """Eklenti: BOSS'ta oturum açan kullanıcının kimliği (yalnız ad/kod/unvan) + bekleyen giriş isteği."""
    simdi = time.time()
    with _KILIT:
        _temizle(simdi)
        b = _BEKLEYEN.get(girdi.istek_id)
        if b is None or b["durum"] != "bekliyor":
            return {"ok": False, "durum": "yok"}
    k, mesaj = kullanici_bul(conn, girdi.ad, girdi.unvan)
    kim = {"ad": girdi.ad, "kod": (girdi.kod or "").strip() or None, "bayi": (girdi.bayi or "").strip() or None}
    # BOSS'ta artık bu kullanıcı var: başka BOSS kullanıcısından kalan uygulama oturumları biter
    oturumlari_bitir(conn, kim["ad"], kim["kod"], haric=True)
    with _KILIT:
        b = _BEKLEYEN.get(girdi.istek_id)
        if b is None or b["durum"] != "bekliyor":
            return {"ok": False, "durum": "yok"}
        if k is None:
            b.update(durum="reddedildi", mesaj=mesaj)
            return {"ok": False, "durum": "eslesmedi"}
        b.update(durum="onaylandi", kid=int(k["id"]), kimlik=kim)
    return {"ok": True, "durum": "onaylandi"}


@yonlendirici.post("/api/giris/boss/durum")
def durum(girdi: DurumGirdi, istek: Request, conn: sqlite3.Connection = Depends(baglanti)):
    """Pencerenin yoklaması: bekliyor · reddedildi (nedeniyle) · tamam (jeton; TEK kullanımlık)."""
    _yerel_sart(istek)
    with _KILIT:
        _temizle(time.time())
        b = _BEKLEYEN.get(girdi.istek_id)
        if b is None or not hmac.compare_digest(b["gizli_iz"], _iz(girdi.gizli)):
            raise hata(410, "BOSS girişinin süresi doldu. Yeniden deneyin.", "suresi_doldu")
        if b["durum"] == "bekliyor":
            return {"durum": "bekliyor", "tarayicida": b["tarayicida"], "kalan_sn": max(0, int(SURE_SN - (time.time() - b["an"])))}
        if b["durum"] == "reddedildi":
            del _BEKLEYEN[girdi.istek_id]
            raise hata(403, b.get("mesaj") or "BOSS kullanıcısı uygulamada bulunamadı.", "boss_eslesmedi")
        del _BEKLEYEN[girdi.istek_id]                     # tek kullanımlık: jeton bir kez verilir
        kid, kim = b["kid"], b.get("kimlik") or {}
    k = conn.execute("SELECT * FROM kullanici WHERE id=? AND aktif=1", (kid,)).fetchone()
    if k is None:
        raise hata(403, "Hesabınız kapalı. Yöneticinize başvurun.", "hesap_kapali")
    bg = _oturum_ac(conn, kid, kim)
    k = dict(k)
    yetki.kisi_erisimini_yukle(conn, k)
    from .api_ortak import _kullanici_kart
    return {"durum": "tamam", "token": guvenlik.jeton_uret(k, bg=bg), "kullanici": _kullanici_kart(k),
            "ana_ekran": yetki.ana_ekran_kisi(k)}


@yonlendirici.post("/api/giris/boss/bitti")
def bitti(girdi: BittiGirdi, conn: sqlite3.Connection = Depends(baglanti), _e: bool = Depends(_eklenti)):
    """Eklenti: BOSS oturumu bitti (çıkış / giriş sayfası / BOSS uçlarında 401) → o kullanıcının BOSS'la açılmış
    uygulama oturumları biter (kimlik yoksa bütün BOSS oturumları)."""
    return {"ok": True, "biten": oturumlari_bitir(conn, girdi.ad, girdi.kod)}


@yonlendirici.get("/api/oturum/boss")
def oturum_yokla(k: dict = Depends(izin("oturum"))):
    """BOSS'la açılmış oturumun hafif yoklaması (arayüz 15 sn'de bir): BOSS'tan çıkılınca 401 döner."""
    return {"ok": True}
