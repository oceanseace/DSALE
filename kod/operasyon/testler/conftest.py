"""v2 iş motoru testleri: canlı yedeğin KARALAMA kopyası + göç + sentetik test kişileri.

- Kaynak, çalışma klasöründeki (``gelistirme/veri``) göç öncesi yedek
  (``saha/yedek/goc/saha-oncesi-v0-v8-20260930-145414.db``; yoksa ``saha/yedek/saha-2026-09-30.db``) salt okunur (``mode=ro&immutable=1``) açılır, SQLite backup API ile
  geçici klasöre kopyalanır; göç (``saha.goc.hazirla``) yalnız kopyada koşar. Canlı ``saha.db``'ye ve
  ``operasyon/obekler.json``'a DOKUNULMAZ (öbek aktarımı JSON'un geçici kopyasından okur).
- Yedek yoksa taze kurulum (``saha.kur``) kullanılır; o zaman öbekler sentetik örnek dosyadandır.
- Test kişileri 555… numaralı, uydurma adlıdır. Testler kişisel veri yazdırmaz (yalnız sayı).
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

import yollar  # kod/ içe aktarma yolunda: kökteki pytest.ini (pythonpath = kod)

os.environ.setdefault("SAHA_GIZLI", "test-icin-sabit-gizli-anahtar-0123456789")

# Canlının göç öncesi hâli (30.09 14:54, v0; doğrulanmış yedek) — yoksa 12:05 günlük yedeği. İkisi de yalnız OKUNUR.
_YEDEK = yollar.CALISMA_SAHA / "yedek"
CANLI_YEDEK = next((p for p in (_YEDEK / "goc" / "saha-oncesi-v0-v8-20260930-145414.db",
                                _YEDEK / "saha-2026-09-30.db") if p.exists()),
                   _YEDEK / "saha-2026-09-30.db")
# Gerçek BOSS raporunun SABİT kopyası (müşteri bilgisi içerir → depoya girmez; gelistirme/ git dışıdır).
# Masaüstündeki dosya her gün değiştiği için testler oradan okumaz. Başka bir dosya: BOSS_RAPOR=<yol>.
# Kopya yoksa gerçek-rapor testleri atlanır.
GERCEK_RAPOR = Path(os.environ.get("BOSS_RAPOR") or yollar.TEST_VERISI / "TeknikTaskDetayRaporu.xlsx")
GERCEK_OBEK = yollar.CALISMA_OPERASYON / "obekler.json"

# Testlerin "şimdi"si: v2 testleri sabit tarihlerle (randevu 2026-10-01 10:00, askı sınırı 2026-10-05 …)
# yazıldı; gerçek saat ilerledikçe kırılmasınlar diye ``saha.ayarlar.simdi`` buna sabitlenir. Saati
# kendisi yöneten testler ``saat`` fikstürünü kullanır; gerçek saat isteyen test ``@pytest.mark.gercek_saat``.
SABIT_AN = dt.datetime(2026, 10, 1, 10, 30, 0)     # arama penceresi (10:00–18:00) içinde

# Başarım bütçesi payı (spec §5.6 bütçeleri ofis sunucusu içindir). Geliştirme makinesi yükteyken
# bütçeler bu katsayıyla gevşer; kesin ölçüm için SAHA_BUTCE_PAYI=1.
BUTCE_PAYI = float(os.environ.get("SAHA_BUTCE_PAYI") or 2.0)


@pytest.fixture(autouse=True)
def sabit_saat(request, monkeypatch):
    if request.node.get_closest_marker("gercek_saat"):
        return
    from saha import ayarlar
    monkeypatch.setattr(ayarlar, "simdi", lambda: SABIT_AN)


# Sentetik test kişileri (uydurma ad, gerçek olmayan numara)
KISILER = {
    "yonetici": ("Deneme Yönetici", "5009990001", "yonetici", None, None),
    "operasyon": ("Deneme Operasyon", "5009990002", "operasyon", None, None),
    "teknik1": ("Ali Deneme", "5009990003", "teknik", None, "ALI DENEME EKIBI"),
    "teknik2": ("Veli Deneme", "5009990004", "teknik", None, None),
    "satis": ("Deneme Satış", "5009990005", "satisci", 1, None),
    "girissiz": ("Can Girişsiz", None, "teknik", None, None),
}


def _kopya_al(kaynak: Path, hedef: Path) -> None:
    src = sqlite3.connect(f"file:{kaynak.as_posix()}?mode=ro&immutable=1", uri=True)
    dst = sqlite3.connect(hedef)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def _kisileri_ekle(yol: Path) -> dict[str, int]:
    conn = sqlite3.connect(yol)
    ids = {}
    simdi = "2026-09-30 08:00:00"
    sut = {r[1] for r in conn.execute("PRAGMA table_info(kullanici)")}
    for anahtar, (ad, tel, rol, bolge, boss_ekip) in KISILER.items():
        while tel and conn.execute("SELECT 1 FROM kullanici WHERE telefon=?", (tel,)).fetchone():
            tel = str(int(tel) + 100)                  # kopyadaki bir numarayla çakışmasın (gerçek olmayan aralık)
        alan = ["ad", "telefon", "rol", "bolge", "aktif", "oturum_no", "olusturma"]
        deger = [ad, tel, rol, bolge, 1, 1, simdi]
        if "boss_ekip" in sut:
            alan.append("boss_ekip")
            deger.append(boss_ekip)
        cur = conn.execute(f"INSERT INTO kullanici ({','.join(alan)}) VALUES ({','.join('?' * len(alan))})", deger)
        ids[anahtar] = cur.lastrowid
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='kullanici_gorev'").fetchone():
            conn.execute("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) VALUES (?,?)", (cur.lastrowid, rol))
    conn.commit()
    conn.close()
    return ids


@pytest.fixture(scope="session")
def v2_ortam(tmp_path_factory) -> dict:
    """Göç edilmiş şablon veritabanı + gerçek öbek JSON'unun kopyası (session boyunca bir kez)."""
    kok = tmp_path_factory.mktemp("v2-sablon")
    obek_kopya = kok / "obekler.json"
    veri = kok / "veri"
    eski_env = {k: os.environ.get(k) for k in ("OPERASYON_OBEK", "OPERASYON_VERI", "SAHA_DB")}
    if GERCEK_OBEK.exists() and CANLI_YEDEK.exists():
        shutil.copyfile(GERCEK_OBEK, obek_kopya)
    else:
        shutil.copyfile(yollar.KOD / "operasyon" / "obekler.ornek.json", obek_kopya)
    sablon = kok / "sablon.db"
    os.environ["OPERASYON_OBEK"] = str(obek_kopya)
    os.environ["OPERASYON_VERI"] = str(veri)
    os.environ["SAHA_DB"] = str(sablon)
    try:
        if CANLI_YEDEK.exists():
            _kopya_al(CANLI_YEDEK, sablon)
            from saha import goc
            goc.hazirla(sablon, yedek=False)
            kaynak = "canli_kopya"
        else:
            from saha import kur
            kur.kur(sifirla=True, yol=sablon, sessiz=True)
            kaynak = "taze"
        ids = _kisileri_ekle(sablon)
        conn = sqlite3.connect(sablon)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    finally:
        for k, v in eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return {"sablon": sablon, "obek_json": obek_kopya, "kisi": ids, "kaynak": kaynak}


@pytest.fixture
def v2db(v2_ortam, tmp_path, monkeypatch) -> Path:
    """Her test kendi kopyasında; ortam değişkenleri geçici klasörleri gösterir."""
    hedef = tmp_path / "saha.db"
    shutil.copy2(v2_ortam["sablon"], hedef)
    obek_json = tmp_path / "obekler.json"
    shutil.copyfile(v2_ortam["obek_json"], obek_json)
    monkeypatch.setenv("SAHA_DB", str(hedef))
    monkeypatch.setenv("OPERASYON_VERI", str(tmp_path / "veri"))
    monkeypatch.setenv("OPERASYON_OBEK", str(obek_json))
    monkeypatch.setenv("SAHA_IZLEME", "0")
    from operasyon.v2 import sozluk
    sozluk.onbellegi_bosalt(bina=True)
    return hedef


@pytest.fixture
def kisi(v2_ortam) -> dict[str, int]:
    return dict(v2_ortam["kisi"])


@pytest.fixture
def conn(v2db):
    from saha import db
    c = db.baglan(v2db)
    yield c
    c.close()


def k_of(conn, kid: int) -> dict:
    """mevcut_kullanici'nin döndürdüğü biçimde kişi (görev kümesiyle)."""
    k = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
    try:
        k["gorevler"] = sorted({k["rol"]} | {r[0] for r in conn.execute(
            "SELECT rol FROM kullanici_gorev WHERE kullanici_id=?", (kid,))})
    except sqlite3.OperationalError:
        k["gorevler"] = [k["rol"]]
    return k


@pytest.fixture
def kim(conn, kisi):
    """kim('operasyon') → kişi sözlüğü."""
    return lambda ad: k_of(conn, kisi[ad])


@pytest.fixture
def saat(monkeypatch):
    """Dondurulmuş saat: saat.ayarla('2026-09-30 10:00:00'); saat.ilerlet(dakika=9)."""
    from operasyon.v2 import zaman

    class _Saat:
        an = dt.datetime(2026, 9, 30, 10, 0, 0)

        def ayarla(self, metin):
            self.an = dt.datetime.fromisoformat(metin)

        def ilerlet(self, **kw):
            self.an = self.an + dt.timedelta(**kw)

    s = _Saat()
    monkeypatch.setattr(zaman, "simdi", lambda: s.an)
    return s


def uygulama():
    """Yalnız v2 yönlendiricileri + gerçek yetki (saha.yetki) ile küçük uygulama."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from starlette.exceptions import HTTPException as SHE

    from operasyon.v2 import api as v2api
    from saha import yetki

    app = FastAPI()

    @app.exception_handler(SHE)
    async def _h(_istek, exc):
        d = exc.detail if isinstance(exc.detail, dict) else {"hata": str(exc.detail), "kod": "hata"}
        return JSONResponse(d, status_code=exc.status_code)

    for r in v2api.yonlendiriciler(yetki.Bagimliliklar()):
        app.include_router(r)
    return app


@pytest.fixture
def istemci(v2db):
    from fastapi.testclient import TestClient
    with TestClient(uygulama()) as c:
        yield c


@pytest.fixture
def jeton(conn):
    from saha import guvenlik

    def _j(kid: int) -> dict:
        r = conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone()
        return {"Authorization": f"Bearer {guvenlik.jeton_uret(r)}"}
    return _j
