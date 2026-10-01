"""Test altyapısı: gerçek veriyle tohumlanmış geçici veritabanı + TestClient.

Ağ yok, dış servis yok. Veritabanı oturum başına bir kez tohumlanır (19.706 bina),
her test kendi kopyası üzerinde çalışır; testler birbirini kirletmez.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

import yollar  # kod/ içe aktarma yolunda: kökteki pytest.ini (pythonpath = kod)

# Testler repodaki gizli anahtarı ne okur ne yazar.
os.environ["SAHA_GIZLI"] = "test-icin-sabit-gizli-anahtar-0123456789"

# Öbek JSON'u ve operasyon veri klasörü: testler ASLA çalışma klasöründeki operasyon/obekler.json'a ya da
# operasyon/veri/'ye dokunmaz. Taze kurulum (kur → goc.taze_kur) sentetik örnek dosyayı okur.
_OP_GECICI = Path(tempfile.mkdtemp(prefix="saha-test-op-"))
if not os.environ.get("OPERASYON_VERI"):
    os.environ["OPERASYON_VERI"] = str(_OP_GECICI / "veri")
if not os.environ.get("OPERASYON_OBEK"):
    _ornek = yollar.KOD / "operasyon" / "obekler.ornek.json"
    _hedef = _OP_GECICI / "obekler.json"
    if _ornek.exists():
        shutil.copyfile(_ornek, _hedef)
    os.environ["OPERASYON_OBEK"] = str(_hedef)      # dosya yoksa öbek aktarımı boş geçer

YONETICI_TEL = "5000000000"
SATISCI_TEL = {b: f"500000000{b}" for b in range(1, 9)}
PIN = "7391"          # zayıf değil: ardışık değil, tek rakam değil
PIN2 = "8264"


@pytest.fixture(scope="session")
def temel_db(tmp_path_factory) -> Path:
    """Gerçek CSV'lerden bir kez tohumlanan şablon veritabanı."""
    from saha import db, kur

    yol = tmp_path_factory.mktemp("saha-temel") / "temel.db"
    kur.kur(sifirla=True, yol=yol, sessiz=True)
    conn = db.baglan(yol)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return yol


@pytest.fixture
def db_yolu(temel_db: Path, tmp_path: Path, monkeypatch) -> Path:
    hedef = tmp_path / "saha.db"
    shutil.copy2(temel_db, hedef)
    monkeypatch.setenv("SAHA_DB", str(hedef))
    return hedef


@pytest.fixture
def conn(db_yolu: Path):
    from saha import db

    baglanti = db.baglan(db_yolu)
    yield baglanti
    baglanti.close()


@pytest.fixture
def istemci(db_yolu: Path):
    from fastapi.testclient import TestClient

    from saha import api

    with TestClient(api.uygulama) as c:
        yield c


def davet_kodu(db_yolu: Path, telefon: str) -> str:
    from saha import db

    baglanti = db.baglan(db_yolu)
    try:
        satir = baglanti.execute("SELECT davet_kodu FROM kullanici WHERE telefon=?", (telefon,)).fetchone()
    finally:
        baglanti.close()
    assert satir and satir["davet_kodu"], f"{telefon} için davet kodu yok"
    return satir["davet_kodu"]


@pytest.fixture
def giris(istemci, db_yolu: Path):
    """Telefon için PIN belirleyip (ya da giriş yapıp) jeton döndürür."""

    def _giris(telefon: str, pin: str = PIN) -> str:
        yanit = istemci.post("/api/giris", json={"telefon": telefon, "pin": pin})
        if yanit.status_code == 200 and yanit.json().get("token"):
            return yanit.json()["token"]
        kod = davet_kodu(db_yolu, telefon)
        yanit = istemci.post("/api/pin", json={"telefon": telefon, "pin": pin, "davet_kodu": kod})
        assert yanit.status_code == 200, yanit.text
        return yanit.json()["token"]

    return _giris


@pytest.fixture
def basliklar(giris):
    def _basliklar(telefon: str, pin: str = PIN) -> dict:
        return {"Authorization": f"Bearer {giris(telefon, pin)}"}

    return _basliklar


@pytest.fixture
def satisci1(basliklar):
    return basliklar(SATISCI_TEL[1])


@pytest.fixture
def satisci2(basliklar):
    return basliklar(SATISCI_TEL[2], PIN2)


@pytest.fixture
def yonetici(basliklar):
    return basliklar(YONETICI_TEL)


@pytest.fixture
def kisi(conn):
    """v2 görevli kişi ekler ve jeton başlığı döndürür: ``kisi('teknik', gorevler=[...], bolge=None)``.

    PIN'li (``PIN``); jeton test anahtarıyla doğrudan üretilir (davet akışı gerekmez). Numaralar
    uydurmadır (555000xxxx).
    """
    from saha import ayarlar, guvenlik

    sayac = iter(range(1, 10_000))

    def _kisi(rol: str, gorevler: list[str] | None = None, bolge: int | None = None, ad: str | None = None,
              telefon: str | None = "", pin: str | None = PIN, aktif: int = 1) -> tuple[int, dict]:
        n = next(sayac)
        tel = f"555{n:07d}" if telefon == "" else telefon
        kid = conn.execute(
            "INSERT INTO kullanici (ad, telefon, pin_hash, rol, bolge, aktif, olusturma) VALUES (?,?,?,?,?,?,?)",
            (ad or f"Deneme {rol} {n}", tel, guvenlik.pin_hashle(pin) if pin else None, rol, bolge, aktif,
             ayarlar.zaman_metni())).lastrowid
        for r in set(gorevler or []) | {rol}:
            conn.execute("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) VALUES (?,?)", (kid, r))
        conn.commit()
        satir = dict(conn.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
        return int(kid), {"Authorization": f"Bearer {guvenlik.jeton_uret(satir)}"}

    return _kisi


@pytest.fixture(autouse=True)
def _gecici_ciktilar(tmp_path: Path, monkeypatch):
    """Faz 2: yüklenen dosyalar ve üretilen planlar/Excel'ler repoya değil geçici klasöre yazılır.

    Bellekteki harita/geometri önbellekleri de her testte boşaltılır: her test kendi
    veritabanı kopyasında çalışır ve sürüm numaraları kopyalar arasında çakışabilir.
    """
    monkeypatch.setenv("SAHA_GELEN", str(tmp_path / "gelen"))
    monkeypatch.setenv("SAHA_CIKTI", str(tmp_path / "cikti"))
    from saha import altlik, api, geometri

    altlik._csp_onbellek.clear()
    api._harita_sabit.clear()
    api._harita_onbellek.clear()
    api._yol_onbellek.clear()
    geometri._onbellek.clear()
    yield
