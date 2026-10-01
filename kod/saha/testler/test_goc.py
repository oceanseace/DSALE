"""Göç çerçevesi (spec §1.2–§1.14, F20): yedek önce, çökme güvenli, ikinci koşu etkisiz, CLI göç etmez.

Bütün veritabanları sentetik ya da test kopyasıdır; canlı saha.db ve operasyon/obekler.json'a dokunulmaz.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

import yollar
from saha import db, goc, kur, sema_v2, yedekle

from .goc_yardim import anlik_goruntu, eski_db_kur, eski_sema, fk_hedefleri, surum, sutun_haritasi



@pytest.fixture
def eski_db(tmp_path) -> Path:
    return eski_db_kur(tmp_path / "eski.db")


def _tablolar(yol: Path) -> set[str]:
    c = sqlite3.connect(yol)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


# ============================================================ taze kurulum
def test_bos_db_hedef_surumde_kurulur(tmp_path):
    yol = tmp_path / "bos.db"
    conn = db.baglan(yol)
    try:
        db.semayi_kur(conn)
        assert goc.user_version(conn) == goc.HEDEF
        assert goc.bekleyen(conn) in ([], ["tohum"])
        tablolar = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"kullanici", "kullanici_gorev", "is_emri", "is_emri_olay", "obek", "obek_mahalle", "mahalle",
                "ilce", "ie_aktarim", "erisim_kaydi", "yonetim_kaydi", "is_aski", "altyapi_bekleyen",
                "ticket_ek", "sema_goc"} <= tablolar
        assert conn.execute("SELECT ad FROM sema_goc").fetchone()[0] == "taze_kurulum"
        assert db.ayar_oku(conn, "musteri_tel") == "kapali"
        assert db.ayar_oku(conn, "ticket_varsayilan_ekip") == "TEAM-TAS1BRS"
        # Taze tanım: dört görev kabul, 'hacker' ret; telefon boş olabilir (Ek-2 girişsiz kişi).
        conn.execute("INSERT INTO kullanici (ad, telefon, rol, olusturma) VALUES ('A', NULL, 'teknik', 'z')")
        conn.execute("INSERT INTO kullanici (ad, telefon, rol, olusturma) VALUES ('B', NULL, 'operasyon', 'z')")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO kullanici (ad, telefon, rol, olusturma) VALUES ('C', NULL, 'hacker', 'z')")
    finally:
        conn.close()


# ============================================================ eski şemadan
def test_checksiz_eski_sema_hedefe_cikar(tmp_path):
    """test_kalite'nin faz 1 şeması (rol CHECK'i yok, faz 2 tabloları yok) hedef sürüme çıkar."""
    from .test_kalite import ESKI_SEMA

    yol = tmp_path / "faz1.db"
    c = sqlite3.connect(yol)
    c.executescript(ESKI_SEMA)
    c.execute("INSERT INTO kullanici (ad, telefon, rol, bolge, olusturma) VALUES ('A','5550000001','satisci',1,'x')")
    c.execute("INSERT INTO bina (bina_serial, lat, lon) VALUES ('BN1', 40.2, 29.0)")
    c.execute("INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, sonuc, kayit_zamani) "
              "VALUES ('z1','BN1',1,'2026-09-20 10:00:00','satis','2026-09-20 10:00:00')")
    c.commit()
    c.close()

    rapor = goc.hazirla(yol, yedek=False)
    assert not rapor.bos and rapor.eski_surum == 0 and rapor.yeni_surum == goc.HEDEF
    conn = sqlite3.connect(yol)
    try:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='kullanici'").fetchone()[0]
        assert "'operasyon'" in sql and "'teknik'" in sql
        assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == 1
        assert conn.execute("SELECT rol FROM kullanici_gorev").fetchall() == [("satisci",)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_bilinmeyen_rol_rollback_turkce(tmp_path):
    """CHECK'siz tabloda tanınmayan görev: göç durur, Türkçe neden, veritabanı birebir aynı."""
    kullanici = sema_v2_eski_checksiz()
    yol = eski_db_kur(tmp_path / "x.db", kullanici=kullanici, roller=("yonetici", "x"))
    once = anlik_goruntu(yol)
    with pytest.raises(goc.GocHatasi) as hata:
        goc.hazirla(yol, yedek=False)
    assert "tanınmayan görev 'x'" in hata.value.mesaj and "kişi" in hata.value.mesaj
    assert hata.value.degismedi
    assert anlik_goruntu(yol) == once
    assert "DEĞİŞMEDİ" in goc.hata_metni(hata.value)


def sema_v2_eski_checksiz() -> str:
    from .goc_yardim import ESKI_KULLANICI

    return ESKI_KULLANICI.replace("CHECK (rol IN ('satisci','yonetici'))", "")


# ============================================================ çökme
@pytest.mark.parametrize("nokta", ["v1:insert", "v1:drop", "v1:rename"])
def test_cokme_enjeksiyonu(eski_db, monkeypatch, nokta):
    once = anlik_goruntu(eski_db)

    def kanca(ad):
        if ad == nokta:
            raise RuntimeError("enjekte edilen çökme")

    monkeypatch.setattr(goc, "_kanca", kanca)
    with pytest.raises(goc.GocHatasi) as hata:
        goc.hazirla(eski_db, yedek=False)
    assert hata.value.degismedi
    assert anlik_goruntu(eski_db) == once           # şema metni + sayılar + özetler + user_version
    assert not goc._kilit_yolu(eski_db).exists()     # kilit bırakıldı


def test_os_exit_alt_surec(eski_db):
    """Süreç RENAME'den sonra öldürülür: işlem yarım kalır, veritabanı göç öncesiyle birebir aynı."""
    once = anlik_goruntu(eski_db)
    betik = (
        "import os, sys\n"
        f"sys.path.insert(0, {str(yollar.KOD)!r})\n"
        "from saha import goc\n"
        "goc._kanca = lambda ad: os._exit(7) if ad == 'v1:rename' else None\n"
        f"goc.hazirla(__import__('pathlib').Path({str(eski_db)!r}), yedek=False)\n"
    )
    sonuc = subprocess.run([sys.executable, "-c", betik], capture_output=True, timeout=120,
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert sonuc.returncode == 7, sonuc.stderr.decode("utf-8", "replace")[-500:]
    # Bir sonraki açılış yarım işlemi geri alır (sıcak günlük / WAL'daki commit'siz sayfalar).
    sqlite3.connect(eski_db).execute("SELECT COUNT(*) FROM kullanici").fetchone()
    assert anlik_goruntu(eski_db) == once
    # Ölen sürecin kilidi bayattır: bir sonraki açılış bekletilmeden güncellenir.
    assert goc._kilit_yolu(eski_db).exists()
    rapor = goc.hazirla(eski_db, yedek=False)
    assert rapor.yeni_surum == goc.HEDEF


# ============================================================ ikinci koşu, yedek
def test_ikinci_kosu_bos_yedek_yok(eski_db):
    ilk = goc.hazirla(eski_db)
    assert not ilk.bos and ilk.yedek_yolu
    ikinci = goc.hazirla(eski_db)
    assert ikinci.bos and ikinci.yedek_yolu is None
    assert len(list((eski_db.parent / "yedek" / "goc").glob("*.db"))) == 1
    conn = sqlite3.connect(eski_db)
    try:
        assert goc.bekleyen(conn) == []
        assert db.ayar_oku(db_satir(conn), "son_goc")
    finally:
        conn.close()


def db_satir(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    return conn


def test_goc_yedegi_dogrulanir_salt_okunur_delete_journal(eski_db):
    once = anlik_goruntu(eski_db)
    rapor = goc.hazirla(eski_db)
    yedek = Path(rapor.yedek_yolu)
    assert yedek.parent == eski_db.parent / "yedek" / "goc"
    assert yedek.name.startswith(f"saha-oncesi-v0-v{goc.HEDEF}-")
    assert not os.access(yedek, os.W_OK)                       # salt okunur
    assert not Path(str(yedek) + "-wal").exists()
    c = sqlite3.connect(yedek.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        c.close()
    # Yedek göç öncesinin birebir kopyası
    assert anlik_goruntu(yedek) == once


def test_yedek_alinamazsa_goc_yok(eski_db, monkeypatch):
    once = anlik_goruntu(eski_db)

    def bozuk(*_a, **_k):
        raise yedekle.YedekHatasi("Diskte yer yok (deneme).")

    monkeypatch.setattr(yedekle, "goc_yedegi", bozuk)
    with pytest.raises(goc.GocHatasi) as hata:
        goc.hazirla(eski_db)
    assert "yedeği alınamadı" in hata.value.mesaj and hata.value.degismedi
    assert anlik_goruntu(eski_db) == once


def test_yedek_gocler_oncesi(tmp_path):
    """Yedek db.gocler'den ÖNCE alınır: faz 1 yedeğinde faz 2 sütunları henüz yoktur."""
    from .test_kalite import ESKI_SEMA

    yol = tmp_path / "faz1.db"
    c = sqlite3.connect(yol)
    c.executescript(ESKI_SEMA)
    c.execute("INSERT INTO kullanici (ad, telefon, rol, bolge, olusturma) VALUES ('A','5550000001','satisci',1,'x')")
    c.commit()
    c.close()
    rapor = goc.hazirla(yol)
    yedek_sutun = sutun_haritasi(Path(rapor.yedek_yolu))
    assert "kalite" not in yedek_sutun["bina"] and "ticket" not in yedek_sutun
    assert "kalite" in sutun_haritasi(yol)["bina"]


def test_disk_yetersizse_dokunulmaz(eski_db, monkeypatch):
    once = anlik_goruntu(eski_db)

    class Kullanim:
        free = 10

    monkeypatch.setattr(goc.shutil, "disk_usage", lambda _yol: Kullanim())
    with pytest.raises(goc.GocHatasi) as hata:
        goc.hazirla(eski_db)
    assert "Diskte yer yok" in hata.value.mesaj
    assert anlik_goruntu(eski_db) == once


# ============================================================ yasak desen
def test_yasak_desen_7_tablo(eski_db):
    """ÖNCE eskiyi RENAME etmek (bugünkü ziyaret kalıbı) kullanici'ye bakan 7 tablonun
    REFERENCES metnini kullanici_eski'ye yeniden yazar — v1 bu yüzden bu deseni KULLANMAZ."""
    c = sqlite3.connect(eski_db, isolation_level=None)
    try:
        c.execute("PRAGMA foreign_keys=OFF")
        c.execute("ALTER TABLE kullanici RENAME TO kullanici_eski")
        bozulan = [r[0] for r in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name<>'kullanici_eski' "
            "AND sql LIKE '%kullanici_eski%'")]
    finally:
        c.close()
    assert sorted(bozulan) == ["bina_durum", "bolge_plani", "gorev", "ticket", "ticket_gecmis",
                               "tur_raporu", "ziyaret"]


def test_v1_fk_hedefleri_ve_sayac_korunur(eski_db):
    once_fk = [f for f in fk_hedefleri(eski_db)]
    once_seq = anlik_goruntu(eski_db)["seq"]["kullanici"]
    goc.hazirla(eski_db, yedek=False)
    sonra = fk_hedefleri(eski_db)
    assert set(once_fk) <= set(sonra)                       # eski FK'lar aynen
    kullaniciya = [f for f in sonra if f[2] == "kullanici"]
    # 10 eski + obek.sahip_id + obek.yedek_id + is_emri.atanan_id + kullanici_gorev
    assert len(kullaniciya) == 14
    c = sqlite3.connect(eski_db)
    try:
        assert c.execute("SELECT seq FROM sqlite_sequence WHERE name='kullanici'").fetchone()[0] >= once_seq
        assert len(c.execute("PRAGMA table_info(kullanici)").fetchall()) == 17
        assert c.execute("SELECT COUNT(*) FROM sema_goc").fetchone()[0] == goc.HEDEF
    finally:
        c.close()


# ============================================================ sunucu ve CLI
def test_port_doluyken_goc_yok(eski_db, monkeypatch):
    from saha import sunucu

    dinleyen = socket.socket()
    dinleyen.bind(("127.0.0.1", 0))
    dinleyen.listen(1)
    port = dinleyen.getsockname()[1]
    monkeypatch.setenv("SAHA_DB", str(eski_db))
    once = anlik_goruntu(eski_db)
    try:
        assert sunucu.main(["--host", "127.0.0.1", "--port", str(port)]) == 2
    finally:
        dinleyen.close()
    assert anlik_goruntu(eski_db) == once
    assert not (eski_db.parent / "yedek").exists()


def test_cli_surum_eskiyse_durur(eski_db, monkeypatch, capsys):
    from saha import demo, demo_temizle, ticket_aktar, veri_araci

    monkeypatch.setenv("SAHA_DB", str(eski_db))
    once = anlik_goruntu(eski_db)
    assert ticket_aktar.main(["--db", str(eski_db), "--dosya", str(eski_db)]) == 3
    assert "eski sürümde" in capsys.readouterr().out
    assert veri_araci.main(["--db", str(eski_db), "kalite"]) == 3
    with pytest.raises(SystemExit):
        demo_temizle.temizle(sor=False)
    with pytest.raises(SystemExit):
        demo.kur(gun_sayisi=1, sessiz=True)
    assert kur.kur(yol=eski_db, sessiz=True)["zaten_kurulu"] is True
    with pytest.raises(kur.KurulumReddi):
        kur.kur(yol=eski_db, sessiz=True, bina_tazele=True)
    assert anlik_goruntu(eski_db) == once

    # Veritabanı araçtan YENİyse de durur.
    c = sqlite3.connect(eski_db)
    c.execute(f"PRAGMA user_version = {goc.HEDEF + 1}")
    c.close()
    assert veri_araci.main(["--db", str(eski_db), "kalite"]) == 3
    assert "Bu araç veritabanından eski" in capsys.readouterr().out


def test_goc_komut_satiri_kuru_ve_uygula(eski_db, capsys):
    assert goc.main(["--db", str(eski_db), "--kuru"]) == 0
    assert "v1:kullanici_rol_dort" in capsys.readouterr().out
    assert surum(eski_db) == 0
    assert goc.main(["--db", str(eski_db), "--yedeksiz"]) == 0
    assert "GÜNCELLEME TAMAM (v0 → v" in capsys.readouterr().out
    assert surum(eski_db) == goc.HEDEF


def test_kilit_bayat_10dk(eski_db):
    kilit = goc._kilit_yolu(eski_db)
    kilit.write_text('{"pid": %d}' % os.getpid(), encoding="utf-8")
    with pytest.raises(goc.GocHatasi) as hata:          # taze kilit, sahibi yaşıyor
        goc.hazirla(eski_db, yedek=False)
    assert "Başka bir güncelleme" in hata.value.mesaj and surum(eski_db) == 0
    eski = time.time() - 11 * 60                        # 11 dakikalık kilit bayattır
    os.utime(kilit, (eski, eski))
    assert goc.hazirla(eski_db, yedek=False).yeni_surum == goc.HEDEF
    assert not kilit.exists()


def test_kilit_sahibi_olmus_surec(eski_db):
    olu = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                         capture_output=True, text=True).stdout.strip()
    goc._kilit_yolu(eski_db).write_text('{"pid": %s}' % olu, encoding="utf-8")
    assert goc.hazirla(eski_db, yedek=False).yeni_surum == goc.HEDEF


# ============================================================ şema eşitliği
def test_sutun_kumesi_taze_ile_ayni(eski_db, tmp_path):
    goc.hazirla(eski_db, yedek=False)
    taze = tmp_path / "taze.db"
    conn = db.baglan(taze)
    try:
        db.semayi_kur(conn)
    finally:
        conn.close()
    g, t = sutun_haritasi(eski_db), sutun_haritasi(taze)
    assert set(g) == set(t)
    for tablo in t:
        assert set(g[tablo]) == set(t[tablo]), tablo

    def nesneler(yol):
        c = sqlite3.connect(yol)
        try:
            return {(r[0], r[1]) for r in c.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('index','trigger')")}
        finally:
            c.close()

    assert nesneler(eski_db) == nesneler(taze)


def test_ziyaret_yeniden_kurma_guvenli_desen(tmp_path):
    """Çok eski ziyaret tablosu (offline_id tek başına UNIQUE, indeksler kayıp) güvenle yeniden kurulur."""
    yol = eski_db_kur(tmp_path / "z.db")
    c = sqlite3.connect(yol, isolation_level=None)
    c.execute("PRAGMA foreign_keys=OFF")
    c.execute("BEGIN")
    c.execute("CREATE TABLE ziyaret_x (id INTEGER PRIMARY KEY AUTOINCREMENT, offline_id TEXT NOT NULL UNIQUE, "
              "bina_serial TEXT NOT NULL REFERENCES bina(bina_serial), kullanici_id INTEGER NOT NULL "
              "REFERENCES kullanici(id), zaman TEXT NOT NULL, sonuc TEXT NOT NULL, satis_adedi INTEGER NOT NULL "
              "DEFAULT 0, konusulan_daire INTEGER NOT NULL DEFAULT 0, notu TEXT, lat REAL, lon REAL, cihaz TEXT, "
              "kayit_zamani TEXT NOT NULL)")
    c.execute("INSERT INTO ziyaret_x SELECT id, offline_id, bina_serial, kullanici_id, zaman, sonuc, satis_adedi, "
              "konusulan_daire, notu, lat, lon, cihaz, kayit_zamani FROM ziyaret")
    c.execute("DROP TABLE ziyaret")
    c.execute("ALTER TABLE ziyaret_x RENAME TO ziyaret")
    c.execute("COMMIT")
    n = c.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0]
    once_diger = [r for r in c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name<>'ziyaret'")]
    c.close()

    conn = db.baglan(yol)
    try:
        assert "ziyaret.UNIQUE(kullanici_id, offline_id)" in db.bekleyen_gocler(conn)
        yapilan = db.gocler(conn)
        assert "ziyaret.UNIQUE(kullanici_id, offline_id)" in yapilan and "ziyaret.iptal" in yapilan
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name='ziyaret'").fetchone()[0]
        assert "UNIQUE (kullanici_id, offline_id)" in sql
        assert conn.execute("SELECT COUNT(*) FROM ziyaret").fetchone()[0] == n
        indeksler = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' "
                                                "AND tbl_name='ziyaret'")}
        assert {"ix_ziyaret_bina", "ix_ziyaret_kullanici", "ix_ziyaret_gun"} <= indeksler
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE sql LIKE '%ziyaret_yeni%' "
                            "OR sql LIKE '%ziyaret_eski%'").fetchone()[0] == 0
        # Başka tabloların tanımı değişmedi
        assert [tuple(r) for r in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name<>'ziyaret' "
            "AND name IN (%s)" % ",".join("?" * len(once_diger)), [r[0] for r in once_diger])] == \
            [tuple(r) for r in once_diger]
        assert db.gocler(conn) == []
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_kur_sifirla_gercek_kisi_reddi(db_yolu):
    """Gerçek kişi olan veritabanında --sifirla reddedilir; onayla da önce yedek alınır."""
    conn = db.baglan(db_yolu)
    conn.execute("INSERT INTO kullanici (ad, telefon, rol, olusturma) VALUES ('Gerçek Kişi', '5321230000', "
                 "'yonetici', 'z')")
    conn.commit()
    conn.close()
    once = anlik_goruntu(db_yolu)
    with pytest.raises(kur.KurulumReddi) as hata:
        kur.kur(sifirla=True, yol=db_yolu, sessiz=True)
    assert "gerçek kişiler var" in str(hata.value)
    assert anlik_goruntu(db_yolu) == once
    # Kurulu veritabanında --sifirla'sız kur binaları ezmez.
    assert kur.kur(yol=db_yolu, sessiz=True)["zaten_kurulu"] is True
    assert anlik_goruntu(db_yolu) == once

    kur.kur(sifirla=True, yol=db_yolu, sessiz=True, evet_gercek=True)
    yedekler = list((db_yolu.parent / "yedek" / "goc").glob("saha-sifirla-*.db"))
    assert len(yedekler) == 1
    c = sqlite3.connect(yedekler[0])
    try:
        assert c.execute("SELECT COUNT(*) FROM kullanici WHERE telefon='5321230000'").fetchone()[0] == 1
    finally:
        c.close()
    assert kur.gercek_kisi_sayisi(db_yolu) == 0


# ============================================================ tohum ve WP-B uyumu
def test_tohum_modul_yoksa_ertelenir_sonra_tamamlanir(eski_db, monkeypatch):
    gercek = goc._tohum_fonksiyonlari()
    monkeypatch.setattr(goc, "_tohum_fonksiyonlari", lambda: None)
    rapor = goc.hazirla(eski_db, yedek=False)
    assert rapor.yeni_surum == goc.HEDEF and rapor.tohum.get("durum") == "bekliyor"
    conn = db.baglan(eski_db)
    try:
        assert db.ayar_oku(conn, "tohum_bekliyor") == "1"
    finally:
        conn.close()
    if gercek is None:
        pytest.skip("operasyon.v2 tohum işlevleri henüz yok")
    monkeypatch.setattr(goc, "_tohum_fonksiyonlari", lambda: gercek)
    ikinci = goc.hazirla(eski_db, yedek=False)
    assert "tohum" in ikinci.adimlar
    conn = db.baglan(eski_db)
    try:
        assert db.ayar_oku(conn, "tohum_bekliyor") is None
        assert conn.execute("SELECT COUNT(*) FROM ilce").fetchone()[0] == 23
    finally:
        conn.close()


def test_is_durumlari_akis_ile_ayni():
    akis = pytest.importorskip("operasyon.v2.akis")
    assert tuple(akis.DURUMLAR) == sema_v2.IS_DURUMLARI
    assert tuple(getattr(akis, "KAYNAKLAR", sema_v2.IS_KAYNAKLARI)) == sema_v2.IS_KAYNAKLARI


def test_ayar_varsayilanlari_operasyon_ile_celismez():
    try:
        from operasyon.v2 import sema as op_sema
    except ImportError:
        pytest.skip("operasyon.v2.sema yok")
    bizim = {**sema_v2.AYAR_V4, **sema_v2.AYAR_EK}
    for anahtar, deger in getattr(op_sema, "AYAR_VARSAYILAN", {}).items():
        if anahtar in bizim:
            assert bizim[anahtar] == deger, anahtar


def test_eski_sema_yardimcisi_canli_tanimla_uyumlu():
    """Test yardımcısının v0 şeması gerçekten iki rollü CHECK ve v8 sütunsuz ticket üretir."""
    metin = eski_sema()
    assert "CHECK (rol IN ('satisci','yonetici'))" in metin and "onedesk_ekip" not in metin
    assert stat is not None
