"""Canlı veritabanının KOPYASINDA yükseltme (spec §10 adım 1–6 ve 8, F20). ``SAHA_CANLI_YEDEK`` yoksa atlanır.

    SAHA_CANLI_YEDEK=gelistirme/veri/saha/yedek/goc/saha-oncesi-v0-v8-20260930-145414.db \\
        .venv/Scripts/python.exe -m pytest kod/saha/testler/test_guncelleme_canli_kopya.py -q

* Kaynak YALNIZ okunur: ``file:…?mode=ro&immutable=1`` + SQLite backup API; kaynağın sha256'sı değişmez,
  yanında -wal/-shm oluşmaz. Her test ``tmp_path``'teki kendi kopyasında çalışır.
* Öbek dosyası ``SAHA_CANLI_OBEK`` (yoksa çalışma klasöründeki ``operasyon/obekler.json``, o da yoksa sentetik örnek) → tmp'ye
  KOPYALANIR; asıl dosyanın sha256'sı değişmez.
* Kişisel veri çıktıya düşmez: iddialar yalnız sayı ve özet (sha256) karşılaştırır; hata iletilerinde
  ad/telefon yoktur.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import yollar
from saha import db, goc, guvenlik, sema_v2, yedekle

from .conftest import PIN
from .goc_yardim import anlik_goruntu, fk_hedefleri, sutun_haritasi

KAYNAK = os.environ.get("SAHA_CANLI_YEDEK")

pytestmark = pytest.mark.skipif(not KAYNAK, reason="SAHA_CANLI_YEDEK verilmedi (canlı kopya provası)")


def _sha(yol: Path) -> str:
    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()


def _kaynak() -> Path:
    yol = Path(KAYNAK)
    return yol if yol.is_absolute() else (yollar.KOK / yol)      # göreli yol: depo köküne göre


def _obek_kaynagi() -> Path:
    ortam = os.environ.get("SAHA_CANLI_OBEK")
    if ortam:
        return Path(ortam)
    gercek = yollar.CALISMA_OPERASYON / "obekler.json"
    return gercek if gercek.exists() else yollar.KOD / "operasyon" / "obekler.ornek.json"


def yedekten_kopya(kaynak: Path, hedef: Path) -> Path:
    """Spec §0.3-2: kaynak salt okunur (yedek dosyası: ``immutable=1``) açılır, backup API ile kopyalanır."""
    uri = kaynak.resolve().as_uri() + "?mode=ro&immutable=1"
    k = sqlite3.connect(uri, uri=True)
    try:
        h = sqlite3.connect(hedef)
        try:
            k.backup(h)
        finally:
            h.close()
    finally:
        k.close()
    return hedef


@pytest.fixture(scope="module")
def sablon(tmp_path_factory) -> dict:
    """Modülde BİR KEZ: kaynaktan kopya + iki kişiye test PIN'i (anlık görüntüden ÖNCE, spec §10-2)."""
    kaynak = _kaynak()
    yan = [Path(str(kaynak) + e) for e in ("-wal", "-shm")]
    yan_once = {p: p.exists() for p in yan}
    sha_once = _sha(kaynak)
    dizin = tmp_path_factory.mktemp("canli")
    yol = yedekten_kopya(kaynak, dizin / "a.db")
    assert _sha(kaynak) == sha_once, "kaynak dosya değişti"
    assert {p: p.exists() for p in yan} == yan_once, "kaynağın yanında -wal/-shm oluştu"

    c = sqlite3.connect(yol)
    try:
        assert int(c.execute("PRAGMA user_version").fetchone()[0]) < goc.HEDEF, "kaynak zaten güncel"
        kisiler = {}
        for rol in ("yonetici", "satisci"):
            satir = c.execute("SELECT id FROM kullanici WHERE rol=? AND aktif=1 AND telefon IS NOT NULL "
                              "ORDER BY id LIMIT 1", (rol,)).fetchone()
            assert satir, f"kopyada aktif {rol} yok"
            kisiler[rol] = int(satir[0])
            c.execute("UPDATE kullanici SET pin_hash=? WHERE id=?", (guvenlik.pin_hashle(PIN), satir[0]))
        c.commit()
    finally:
        c.close()
    return {"yol": yol, "kisiler": kisiler}


@pytest.fixture
def kopya(sablon, tmp_path, monkeypatch) -> Path:
    """Testin kendi kopyası + öbek dosyasının kopyası (asıl dosya yalnız okunur)."""
    hedef = tmp_path / "a.db"
    shutil.copy2(sablon["yol"], hedef)
    obek = tmp_path / "obekler.json"
    shutil.copyfile(_obek_kaynagi(), obek)
    monkeypatch.setenv("OPERASYON_OBEK", str(obek))
    monkeypatch.setenv("OPERASYON_VERI", str(tmp_path / "opveri"))
    return hedef


def _ozet(satirlar) -> str:
    """Değer yerine özet: iddia tutmazsa pytest kişisel veriyi/PIN özetini ekrana basmasın."""
    return hashlib.sha256(json.dumps([list(r) for r in satirlar], ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def _ro(yol: Path) -> sqlite3.Connection:
    c = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ============================================================ §10-5 göç
def test_goc_canli_kopya_satir_satir_ayni(kopya, tmp_path):
    obek_dosyasi = Path(os.environ["OPERASYON_OBEK"])
    obek_sha = _sha(obek_dosyasi)
    obek_json = json.loads(obek_dosyasi.read_text(encoding="utf-8")).get("obekler", [])
    eski_sutunlar = sutun_haritasi(kopya)
    once = anlik_goruntu(kopya)
    once_fk = fk_hedefleri(kopya)
    c = _ro(kopya)
    try:
        once_ayar = dict(c.execute("SELECT anahtar, deger FROM ayar").fetchall())
        once_pin = _ozet(c.execute("SELECT id, pin_hash FROM kullanici ORDER BY id").fetchall())
    finally:
        c.close()

    rapor = goc.hazirla(kopya)

    # Rapor yalnız sayı taşır; sürüm ve yedek.
    assert not rapor.bos and rapor.eski_surum == once["user_version"] and rapor.yeni_surum == goc.HEDEF
    assert rapor.sayilar["kullanici"] == once["tablolar"]["kullanici"][0]
    assert rapor.sayilar["bina"] == once["tablolar"]["bina"][0]
    assert rapor.sayilar["ziyaret"] == once["tablolar"]["ziyaret"][0]

    # Göç yedeği: yerinde, salt okunur, DELETE günlüğü, bütün, sayılar ve satırlar kaynakla aynı.
    yedek = Path(rapor.yedek_yolu)
    assert yedek.parent == kopya.parent / "yedek" / "goc"
    assert yedek.name.startswith(f"saha-oncesi-v{once['user_version']}-v{goc.HEDEF}-")
    assert not os.stat(yedek).st_mode & stat.S_IWRITE
    assert not Path(str(yedek) + "-wal").exists() and not Path(str(yedek) + "-shm").exists()
    y = _ro(yedek)
    try:
        assert y.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert y.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        y.close()
    assert anlik_goruntu(yedek) == once

    c = _ro(kopya)
    try:
        assert c.execute("PRAGMA user_version").fetchone()[0] == goc.HEDEF
        assert [r[0] for r in c.execute("SELECT surum FROM sema_goc ORDER BY surum")] == list(range(1, goc.HEDEF + 1))
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        # kullanici: 10 sütun birebir, 17 sütun, sıra sayacı gerilemedi, PIN özetleri aynı
        assert len(c.execute("PRAGMA table_info(kullanici)").fetchall()) == 17
        seq = c.execute("SELECT seq FROM sqlite_sequence WHERE name='kullanici'").fetchone()[0]
        assert seq >= once["seq"]["kullanici"]
        assert _ozet(c.execute("SELECT id, pin_hash FROM kullanici ORDER BY id").fetchall()) == once_pin
        # Ek-1: herkes bugünkü göreviyle kümede
        assert c.execute("SELECT COUNT(*) FROM kullanici_gorev").fetchone()[0] == once["tablolar"]["kullanici"][0]
        assert c.execute("SELECT COUNT(*) FROM kullanici k JOIN kullanici_gorev g "
                         "ON g.kullanici_id=k.id AND g.rol=k.rol").fetchone()[0] == once["tablolar"]["kullanici"][0]
        # Eski ayarlar aynen (yalnız yeni anahtarlar eklendi)
        sonra_ayar = dict(c.execute("SELECT anahtar, deger FROM ayar").fetchall())
        # (yardım telefonu gibi değerler ayarda durur: karşılaştırma özetle, hata iletisine değer düşmez)
        assert _ozet(sorted((a, sonra_ayar.get(a)) for a in once_ayar)) == _ozet(sorted(once_ayar.items()))
        assert set(sema_v2.AYAR_V4) | set(sema_v2.AYAR_EK) <= set(sonra_ayar)
        # Tohum: 23 ilçe; öbekler JSON'la aynı (her ref DB'de JSON motoruyla aynı öbeğe çözülür —
        # json_aktar bunu aynı işlemde doğrular, tutmasaydı göç ROLLBACK olurdu).
        assert c.execute("SELECT COUNT(*) FROM ilce").fetchone()[0] == 23
        assert c.execute("SELECT COUNT(*) FROM mahalle").fetchone()[0] > 0
        assert c.execute("SELECT COUNT(*) FROM obek WHERE aktif=1").fetchone()[0] == len(obek_json)
        catisma = c.execute("SELECT veri FROM obek_olay WHERE tur='json_aktarim'").fetchone()
        n_catisma = len(json.loads(catisma[0])["sonra"]["catisma"]) if catisma else 0
        n_ref = sum(len(t.get("mahalleler", [])) for t in obek_json)
        assert c.execute("SELECT COUNT(*) FROM obek_mahalle").fetchone()[0] + n_catisma == n_ref
        # CHECK: yeni görevler kabul, bilinmeyen ret (salt okunur bağlantıda değil; aşağıda)
    finally:
        c.close()
    assert _sha(obek_dosyasi) == obek_sha                              # öbek dosyası yalnız okundu

    # Eski tabloların hepsi SATIR SATIR aynı (yalnız eski sütunlar üzerinden; ayar yukarıda).
    sonra = anlik_goruntu(kopya, sutunlar=eski_sutunlar)
    for tablo, (sayi, ozet) in once["tablolar"].items():
        if tablo == "ayar":
            continue
        assert sonra["tablolar"][tablo] == (sayi, ozet), f"{tablo} tablosu değişti"
    assert sonra["kullanici10"] == once["kullanici10"]

    # FK: eski bağlar aynen; kullanici'ye bakanların HEPSİNİN hedefi kullanici.
    sonra_fk = fk_hedefleri(kopya)
    assert set(once_fk) <= set(sonra_fk)
    once_kullaniciya = [f for f in once_fk if f[2] == "kullanici"]
    kullaniciya = [f for f in sonra_fk if f[2] == "kullanici"]
    # eski + obek.sahip_id + obek.yedek_id + is_emri.atanan_id + kullanici_gorev
    assert len(kullaniciya) == len(once_kullaniciya) + 4
    c = sqlite3.connect(kopya)
    try:
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%kullanici_eski%' "
                         "OR sql LIKE '%kullanici_yeni%'").fetchone()[0] == 0
        c.execute("SAVEPOINT dene")
        for rol in ("teknik", "operasyon"):
            c.execute("INSERT INTO kullanici (ad, telefon, rol, olusturma) VALUES ('Deneme', NULL, ?, 'x')", (rol,))
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO kullanici (ad, telefon, rol, olusturma) VALUES ('Deneme', NULL, 'hacker', 'x')")
        c.execute("ROLLBACK TO dene")
        c.execute("RELEASE dene")
        assert db.bekleyen_gocler(c) == [] and goc.bekleyen(c) == []
    finally:
        c.close()

    # İkinci açılış: iş yok, yeni yedek yok.
    ikinci = goc.hazirla(kopya)
    assert ikinci.bos and ikinci.yedek_yolu is None
    assert len(list((kopya.parent / "yedek" / "goc").glob("*.db"))) == 1


def test_goc_komut_satiri_canli_kopya(kopya, capsys):
    """§10-5 tek komut: ``python -m saha.goc --db <kopya>`` — çıktıda yalnız sayılar."""
    assert goc.main(["--db", str(kopya)]) == 0
    cikti = capsys.readouterr().out
    assert cikti.startswith(f"GÜNCELLEME TAMAM (v0 → v{goc.HEDEF})")
    assert "yedek:" in cikti
    assert goc.main(["--db", str(kopya)]) == 0
    assert "yapılacak iş yok" in capsys.readouterr().out


# ============================================================ §10-6 yeni kodla oturum
def test_yeni_kodla_oturum_surer_gorev_degisince_401(sablon, kopya, monkeypatch):
    from fastapi.testclient import TestClient

    from saha import api

    # Jetonlar göçten ÖNCE üretilir (açık telefonların elindeki jetonlar).
    c = sqlite3.connect(kopya)
    c.row_factory = sqlite3.Row
    try:
        satirlar = {rol: dict(c.execute("SELECT * FROM kullanici WHERE id=?", (kid,)).fetchone())
                    for rol, kid in sablon["kisiler"].items()}
    finally:
        c.close()
    jeton = {rol: {"Authorization": f"Bearer {guvenlik.jeton_uret(s)}"} for rol, s in satirlar.items()}

    goc.hazirla(kopya)
    monkeypatch.setenv("SAHA_DB", str(kopya))
    # Yanıt gövdeleri kişi kartı (ad, telefon) taşır: iddialardan önce yalnız gereken tek değer alınır,
    # tutmazsa pytest gövdeyi ekrana basmasın.
    with TestClient(api.uygulama) as ist:
        kod, ekran = _kod_alan(ist.get("/api/ben", headers=jeton["yonetici"]), "ana_ekran")
        assert (kod, ekran) == (200, "isler")
        assert ist.get("/api/ben", headers=jeton["satisci"]).status_code == 200
        assert _kod_alan(ist.get("/api/saglik"), "guncelleme_bekliyor") == (200, False)

        s = satirlar["satisci"]
        yanit = ist.post("/api/kullanici", headers=jeton["yonetici"],
                         json={"id": s["id"], "ad": s["ad"], "telefon": s["telefon"], "rol": "teknik", "aktif": True})
        assert _kod_alan(yanit, "oturum_dustu") == (200, True)
        assert _kod_alan(ist.get("/api/ben", headers=jeton["satisci"]), "kod") == (401, "gorev_degisti")
        giris = ist.post("/api/giris", json={"telefon": s["telefon"], "pin": PIN})
        assert _kod_alan(giris, "ana_ekran") == (200, "islerim")
        yeni = {"Authorization": f"Bearer {giris.json()['token']}"}
        assert _kod_alan(ist.get("/api/ben", headers=yeni), "ana_ekran") == (200, "islerim")
        # Teknik artık satış uçlarına kapalı (bölgesiz şehir geneli açığı yok).
        assert ist.get("/api/bina", headers=yeni).status_code == 403
    c = sqlite3.connect(kopya)
    try:
        ayni_pin = c.execute("SELECT pin_hash FROM kullanici WHERE id=?", (s["id"],)).fetchone()[0] == s["pin_hash"]
    finally:
        c.close()
    assert ayni_pin


def _kod_alan(yanit, alan: str) -> tuple:
    try:
        deger = yanit.json().get(alan)
    except ValueError:
        deger = None
    return yanit.status_code, deger


# ============================================================ §10-8 çökme enjeksiyonu
@pytest.mark.parametrize("nokta", ["v1:insert", "v1:drop", "v1:rename", "adim:4:commit"])
def test_cokme_canli_kopya(kopya, monkeypatch, nokta):
    eski_sutunlar = sutun_haritasi(kopya)
    once = anlik_goruntu(kopya)

    def kanca(ad):
        if ad == nokta:
            raise RuntimeError("enjekte edilen çökme")

    monkeypatch.setattr(goc, "_kanca", kanca)
    with pytest.raises(goc.GocHatasi) as hata:
        goc.hazirla(kopya, yedek=False)
    if nokta.startswith("v1:"):
        assert hata.value.degismedi
        assert anlik_goruntu(kopya) == once
    else:
        # v4 işleminin içinde çöktü: v1–v3 kalıcı, v4 hiç olmamış gibi; sonraki açılış kaldığı yerden sürer.
        assert hata.value.durdugu_surum == 3
        monkeypatch.setattr(goc, "_kanca", lambda ad: None)
        assert goc.hazirla(kopya, yedek=False).yeni_surum == goc.HEDEF
        sonra = anlik_goruntu(kopya, sutunlar=eski_sutunlar)
        assert sonra["kullanici10"] == once["kullanici10"]
        for tablo in ("bina", "ziyaret", "gorev", "bina_durum"):
            assert sonra["tablolar"][tablo] == once["tablolar"][tablo], f"{tablo} tablosu değişti"


def test_os_exit_canli_kopya(kopya):
    once = anlik_goruntu(kopya)
    betik = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(yollar.KOD)!r})\n"
        "from saha import goc\n"
        "goc._kanca = lambda ad: os._exit(7) if ad == 'v1:rename' else None\n"
        f"goc.hazirla(__import__('pathlib').Path({str(kopya)!r}), yedek=False)\n"
    )
    sonuc = subprocess.run([sys.executable, "-c", betik], capture_output=True, timeout=300,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert sonuc.returncode == 7
    sqlite3.connect(kopya).execute("SELECT COUNT(*) FROM kullanici").fetchone()
    assert anlik_goruntu(kopya) == once


def test_yasak_desen_canli_kopya(kopya):
    """Önce eskiyi RENAME etmek kullanici'ye bakan HER tablonun REFERENCES metnini bozar (spec §1.4)."""
    bakanlar = sorted({m for m, _, hedef in fk_hedefleri(kopya) if hedef == "kullanici"})
    c = sqlite3.connect(kopya, isolation_level=None)
    try:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("BEGIN")
        c.execute("ALTER TABLE kullanici RENAME TO kullanici_eski")
        bozulan = sorted(r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name<>'kullanici_eski' "
            "AND sql LIKE '%kullanici_eski%'"))
        c.execute("ROLLBACK")
    finally:
        c.close()
    assert bozulan == bakanlar and len(bozulan) >= 7


def test_kaynak_yalniz_okundu():
    kaynak = _kaynak()
    uri = kaynak.resolve().as_uri() + "?mode=ro&immutable=1"
    c = sqlite3.connect(uri, uri=True)
    try:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert yedekle.kullanici_ozeti(c)
    finally:
        c.close()
