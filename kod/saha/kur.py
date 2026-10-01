"""Veritabanını kurar ve 19.706 binayı tohumlar.

    .venv/Scripts/python.exe -m saha.kur              # kur / tazele
    .venv/Scripts/python.exe -m saha.kur --sifirla    # sıfırdan kur (tüm saha kaydı silinir)

Kaynaklar
    veri/master/bina_master.csv        bina künyesi (adres, konum, kat, daire, HP, fırsat)
    cikti/N08_res_hp/atama.csv       8 satışçıya bölgeleme (bina_serial → bolge)

Tazeleme binanın künyesini günceller; ``bina_durum`` ve ``ziyaret`` kayıtlarına dokunmaz.
Bölge planlayıcı kullanılmışsa bölgelere, tur raporuyla güncellenmiş binaların
HP/abone sayılarına da dokunmaz (ikisi de artık veritabanında yönetilir).
Sonunda veri kalitesi kuralları (``dsale/kalite.py``) bütün binalara uygulanır.

v2 korumaları (spec §1.13):
    * Dolu veritabanında ``kur`` bina alanlarını CSV'den EZMEZ ("zaten kurulu"); bilerek
      tazelemek için ``--bina-tazele`` (önce doğrulanmış yedek alınır).
    * ``--sifirla``: veritabanında tohum numaraları (500000xxxx) dışında kişi varsa REDDEDİLİR;
      ``--evet-gercek-kisileri-sil`` ile de önce ``goc_yedegi(etiket='sifirla')`` alınır.
    * Şema sürümü eski/yeniyse durur (göç yalnız sunucu açılışında yapılır).
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

from . import ayarlar, db, guvenlik, veri_kalitesi


# ----------------------------------------------------------------------------- yardımcılar
def _sayi(deger, varsayilan=0) -> int:
    try:
        metin = str(deger).strip()
        return int(float(metin)) if metin else varsayilan
    except (TypeError, ValueError):
        return varsayilan


def _ondalik(deger):
    try:
        metin = str(deger).strip()
        return float(metin) if metin else None
    except (TypeError, ValueError):
        return None


def _metin(deger) -> str:
    return (str(deger).strip() if deger is not None else "") or ""


def _kod(deger) -> str:
    """Kimlik alanları: CSV'de sayıya dönmüş olanların sondaki '.0'ını atar (19981529.0 → 19981529)."""
    metin = _metin(deger)
    if metin.lower() in ("nan", "none", "null"):
        return ""
    return metin[:-2] if metin.endswith(".0") and metin[:-2].isdigit() else metin


def _csv_oku(yol: Path) -> list[dict]:
    if not yol.exists():
        raise SystemExit(f"Kaynak dosya bulunamadı: {yol}")
    with open(yol, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ----------------------------------------------------------------------------- bina
def binalari_tohumla(conn: sqlite3.Connection) -> tuple[int, dict[int, str]]:
    master = _csv_oku(ayarlar.VERI_BINA)
    atama = _csv_oku(ayarlar.VERI_ATAMA)

    bolge_of = {}
    bolge_adlari: dict[int, str] = {}
    for a in atama:
        serial = _metin(a.get("bina_serial"))
        bolge = _sayi(a.get("bolge"), 0)
        if serial and bolge:
            bolge_of[serial] = bolge
            ad = _metin(a.get("bolge_adi"))
            if ad:
                bolge_adlari.setdefault(bolge, ad)

    satirlar = []
    for m in master:
        serial = _metin(m.get("bina_serial"))
        lat, lon = _ondalik(m.get("lat")), _ondalik(m.get("lon"))
        if not serial or lat is None or lon is None:
            continue
        res_hp = _sayi(m.get("res_hp"))
        satirlar.append((
            serial,
            _metin(m.get("ad")),
            _metin(m.get("site_adi")),
            _metin(m.get("mahalle")),
            _metin(m.get("ilce")),
            _metin(m.get("il")) or "Bursa",
            _metin(m.get("cadde")),
            _metin(m.get("sokak")),
            _metin(m.get("kapi_no")),
            lat, lon,
            _sayi(m.get("kat")),
            _sayi(m.get("konut_sayisi")) or res_hp,
            res_hp,
            _sayi(m.get("aktif_res")),
            _sayi(m.get("firsat")),
            _metin(m.get("sales_ready"))[:10] or None,
            bolge_of.get(serial),
            _metin(m.get("obek")),
            _metin(m.get("site_grup")),
            _kod(m.get("location_id")),
            _kod(m.get("tellcordia_id")),
            _kod(m.get("uavt_bina_kodu")),
            _metin(m.get("blok_adi")),
            _metin(m.get("bina_turu")),
            _sayi(m.get("toplam_hp")),
            _sayi(m.get("soho_hp")),
            _metin(m.get("altyapi")),
            _metin(m.get("teknoloji")),
            _metin(m.get("protokol_segment")),
            _metin(m.get("site_adi_crm")),
        ))

    conn.executemany(
        """INSERT INTO bina (bina_serial, ad, site_adi, mahalle, ilce, il, cadde, sokak, kapi_no,
                             lat, lon, kat, daire, res_hp, aktif_res, firsat, sales_ready,
                             bolge, obek, site_grup,
                             location_id, tellcordia_id, uavt_bina_kodu, blok_adi, bina_turu,
                             toplam_hp, soho_hp, altyapi, teknoloji, protokol_segment, crm_site_adi)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(bina_serial) DO UPDATE SET
             ad=excluded.ad, site_adi=excluded.site_adi, mahalle=excluded.mahalle,
             ilce=excluded.ilce, il=excluded.il, cadde=excluded.cadde, sokak=excluded.sokak,
             kapi_no=excluded.kapi_no, lat=excluded.lat, lon=excluded.lon, kat=excluded.kat,
             daire=excluded.daire,
             -- Tur raporuyla güncellenmiş bina master'daki ESKİ sayılara dönmez.
             res_hp=CASE WHEN bina.tur_tarihi IS NULL THEN excluded.res_hp ELSE bina.res_hp END,
             aktif_res=CASE WHEN bina.tur_tarihi IS NULL THEN excluded.aktif_res ELSE bina.aktif_res END,
             firsat=CASE WHEN bina.tur_tarihi IS NULL THEN excluded.firsat ELSE bina.firsat END,
             sales_ready=excluded.sales_ready,
             -- Bölge planlayıcı bir kez kullanıldıysa bölgeler yalnız oradan değişir;
             -- kurulumu yeniden çalıştırmak 14 bölgelik planı 8'e geri çevirmemeli.
             bolge=CASE WHEN EXISTS (SELECT 1 FROM bolge_plani WHERE aktif=1)
                        THEN bina.bolge ELSE excluded.bolge END,
             obek=excluded.obek, site_grup=excluded.site_grup,
             location_id=excluded.location_id, tellcordia_id=excluded.tellcordia_id,
             uavt_bina_kodu=excluded.uavt_bina_kodu, blok_adi=excluded.blok_adi,
             bina_turu=excluded.bina_turu,
             toplam_hp=CASE WHEN bina.tur_tarihi IS NULL THEN excluded.toplam_hp ELSE bina.toplam_hp END,
             soho_hp=CASE WHEN bina.tur_tarihi IS NULL THEN excluded.soho_hp ELSE bina.soho_hp END,
             altyapi=excluded.altyapi, teknoloji=excluded.teknoloji,
             protokol_segment=excluded.protokol_segment, crm_site_adi=excluded.crm_site_adi""",
        satirlar,
    )
    # Her bina için bir durum satırı; var olanlara dokunulmaz.
    conn.execute(
        "INSERT INTO bina_durum (bina_serial, durum) "
        "SELECT bina_serial, 'bekliyor' FROM bina "
        "WHERE bina_serial NOT IN (SELECT bina_serial FROM bina_durum)"
    )
    return len(satirlar), bolge_adlari


# ----------------------------------------------------------------------------- kullanıcı
def kullanicilari_tohumla(conn: sqlite3.Connection, bolge_adlari: dict[int, str]) -> list[dict]:
    """1 yönetici + 8 satışçı yeri. Ad ve telefon yönetici ekranından düzenlenir,
    PIN ilk girişte davet koduyla belirlenir."""
    # Yalnız boş bir veritabanında: yönetici numaraları değiştirdikten sonra
    # kurulum yeniden çalışırsa (ör. yeni tur raporu) yinelenen yer tutucu hesap açılmasın.
    if conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0] > 0:
        return []
    simdi = ayarlar.zaman_metni()
    istenen = [("Yönetici", "5000000000", "yonetici", None)]
    for bolge in range(1, ayarlar.BOLGE_SAYISI + 1):
        ad = bolge_adlari.get(bolge, f"Bölge {bolge}")
        istenen.append((f"{bolge}. Satışçı — {ad}", f"500000000{bolge}", "satisci", bolge))

    yeni: list[dict] = []
    for ad, telefon, rol, bolge in istenen:
        varsa = conn.execute("SELECT id FROM kullanici WHERE telefon=?", (telefon,)).fetchone()
        if varsa:
            continue
        kod = guvenlik.davet_kodu_uret()
        conn.execute(
            "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, olusturma) "
            "VALUES (?,?,NULL,?,?,?,1,?)",
            (ad, telefon, kod, rol, bolge, simdi),
        )
        yeni.append({"ad": ad, "telefon": telefon, "rol": rol, "bolge": bolge, "davet_kodu": kod})
    # Görev kümesi (Ek-1): herkes ana göreviyle kümede.
    conn.execute("INSERT OR IGNORE INTO kullanici_gorev (kullanici_id, rol) SELECT id, rol FROM kullanici")
    return yeni


# ----------------------------------------------------------------------------- akış
class KurulumReddi(SystemExit):
    """Kurulum güvenlik nedeniyle yapılmadı; mesaj Türkçe, veritabanına dokunulmadı."""


def gercek_kisi_sayisi(yol: Path) -> int:
    """Tohum numaraları (500000xxxx: kurulumun ve bölge planlayıcının yer tutucuları) dışındaki kişiler.

    Telefonu olmayan (girişsiz, rehberden gelen) kişi de gerçek kişidir.
    """
    if not Path(yol).exists():
        return 0
    conn = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kullanici'").fetchone():
            return 0
        return int(conn.execute(
            "SELECT COUNT(*) FROM kullanici WHERE telefon IS NULL OR substr(telefon,1,6) <> '500000'"
        ).fetchone()[0])
    finally:
        conn.close()


def _surum(yol: Path) -> int:
    conn = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def kur(sifirla: bool = False, yol: Path | None = None, sessiz: bool = False,
        evet_gercek: bool = False, bina_tazele: bool = False) -> dict:
    from . import goc, yedekle

    hedef = Path(yol) if yol else db.db_yolu()
    if sifirla:
        gercek = gercek_kisi_sayisi(hedef)
        if gercek and not evet_gercek:
            raise KurulumReddi(
                f"Bu veritabanında gerçek kişiler var ({gercek}). Sıfırlamak için önce yedek alın ve "
                "--evet-gercek-kisileri-sil ekleyin.")
        if hedef.exists() and hedef.stat().st_size > 0:
            v = _surum(hedef)
            yedek = yedekle.goc_yedegi(hedef, eski=v, yeni=v, etiket="sifirla")
            if not sessiz:
                print(f"Sıfırlamadan önce yedek alındı: {yedek}")
        for ek in ("", "-wal", "-shm"):
            p = Path(str(hedef) + ek)
            if p.exists():
                p.unlink()
    elif hedef.exists() and not bina_tazele and _kullanici_sayisi(hedef) > 0:
        mesaj = ("Veritabanı zaten kurulu; bina güncellemesi için Tur raporu ekranını kullanın. "
                 "(Binaları CSV'den bilerek tazelemek için: --bina-tazele)")
        if not sessiz:
            print(mesaj)
        return {"veritabani": str(hedef), "zaten_kurulu": True, "mesaj": mesaj}

    conn = db.baglan(hedef)
    try:
        try:
            db.semayi_kur(conn)
        except goc.SurumUyumsuz as exc:
            raise KurulumReddi(exc.mesaj) from exc
        taze = db.ayar_oku(conn, "kurulum") is None
        if bina_tazele and not taze:
            yedek = yedekle.goc_yedegi(hedef, eski=goc.HEDEF, yeni=goc.HEDEF, etiket="bina-tazele")
            if not sessiz:
                print(f"Tazelemeden önce yedek alındı: {yedek}")
        bina_sayisi, bolge_adlari = binalari_tohumla(conn)
        yeni_kullanicilar = kullanicilari_tohumla(conn, bolge_adlari)
        conn.commit()
        # Sözlük binalardan da beslenir (taze kurulumda binalar tohumdan SONRA gelir).
        goc.tohum_tazele(conn)
        # Veri kalitesi: kanıtlar kaynaktan tazelenir, bayraklar yeniden hesaplanır
        # (tohumlama kimlikleri ham hâline döndürdü; güvenli düzeltmeler tekrar uygulanır).
        conn.commit()
        kalite = veri_kalitesi.hazirla(conn, zorla=True) or {}
        db.bina_surumu_arttir(conn)
        db.ayar_yaz(conn, "kurulum", ayarlar.zaman_metni())
        db.ayar_yaz(conn, "bina_sayisi", str(bina_sayisi))
        db.ayar_yaz(conn, "bolge_adlari", json.dumps(bolge_adlari, ensure_ascii=False))
        db.ayar_yaz(conn, "ofis", json.dumps(ayarlar.OFIS, ensure_ascii=False))
        conn.commit()

        ozet = {
            "veritabani": str(hedef),
            "bina": bina_sayisi,
            "res_hp": conn.execute("SELECT COALESCE(SUM(res_hp),0) FROM bina").fetchone()[0],
            "firsat": conn.execute("SELECT COALESCE(SUM(firsat),0) FROM bina").fetchone()[0],
            "bolgesiz": conn.execute("SELECT COUNT(*) FROM bina WHERE bolge IS NULL").fetchone()[0],
            "kullanici": conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0],
            "yeni_kullanicilar": yeni_kullanicilar,
            "kalite": kalite,
        }
    finally:
        conn.close()

    if not sessiz:
        _ozet_yaz(ozet)
    return ozet


def _ozet_yaz(ozet: dict) -> None:
    b = lambda n: f"{n:,}".replace(",", ".")  # noqa: E731  → 19.706
    print("Saha Sistemi veritabanı hazır.")
    print(f"  Dosya        : {ozet['veritabani']}")
    print(f"  Bina         : {b(ozet['bina'])}")
    print(f"  RES HP       : {b(ozet['res_hp'])}")
    print(f"  Boş kapı     : {b(ozet['firsat'])}")
    print(f"  Kullanıcı    : {ozet['kullanici']}")
    if ozet.get("kalite"):
        k = ozet["kalite"]
        print(f"  Veri kalitesi: {b(k.get('bayrakli', 0))} binada bulgu, "
              f"{b(k.get('duzeltilen', 0))} binada güvenli düzeltme")
    if ozet["bolgesiz"]:
        print(f"  UYARI        : {ozet['bolgesiz']} binanın bölgesi yok")
    if ozet["yeni_kullanicilar"]:
        print("\n  İlk giriş davet kodları (yöneticiye teslim edilir, PIN ilk girişte belirlenir):")
        for k in ozet["yeni_kullanicilar"]:
            tel = guvenlik.telefon_goster(k["telefon"])
            print(f"    {tel}  {k['davet_kodu']}  {k['ad']}")


def kodlari_yaz(yol: Path | None = None) -> None:
    """Henüz PIN belirlememiş kullanıcıların davet kodlarını tekrar basar."""
    conn = db.baglan(Path(yol) if yol else None)
    try:
        satirlar = conn.execute(
            "SELECT ad, telefon, davet_kodu, rol FROM kullanici "
            "WHERE pin_hash IS NULL AND davet_kodu IS NOT NULL AND aktif=1 ORDER BY rol DESC, bolge"
        ).fetchall()
    finally:
        conn.close()
    if not satirlar:
        print("Bekleyen davet kodu yok — herkes PIN'ini belirlemiş.")
        return
    print("İlk giriş davet kodları (yalnız PIN belirlememiş kullanıcılar):")
    for s in satirlar:
        print(f"  {guvenlik.telefon_goster(s['telefon'])}  {s['davet_kodu']}  {s['ad']}")


def _kullanici_sayisi(yol: Path) -> int:
    if not Path(yol).exists() or Path(yol).stat().st_size == 0:
        return 0
    conn = sqlite3.connect(Path(yol).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kullanici'").fetchone():
            return 0
        return int(conn.execute("SELECT COUNT(*) FROM kullanici").fetchone()[0])
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Saha Sistemi veritabanını kurar ve tohumlar.")
    ayrac.add_argument("--sifirla", action="store_true", help="Var olan veritabanını silip sıfırdan kurar.")
    ayrac.add_argument("--evet-gercek-kisileri-sil", action="store_true", dest="evet_gercek",
                       help="Gerçek kişileri olan veritabanını sıfırlamayı onaylar (önce yedek alınır).")
    ayrac.add_argument("--bina-tazele", action="store_true",
                       help="Kurulu veritabanında binaları CSV'den tazeler (önce yedek alınır).")
    ayrac.add_argument("--kodlar", action="store_true", help="Bekleyen davet kodlarını yazar, kurulum yapmaz.")
    ayrac.add_argument("--db", default=None, help="Veritabanı dosya yolu (varsayılan: saha/saha.db)")
    a = ayrac.parse_args(argv)
    ayarlar.konsolu_hazirla()
    yol = Path(a.db) if a.db else None
    if a.kodlar:
        kodlari_yaz(yol)
        return 0
    try:
        kur(sifirla=a.sifirla, yol=yol, evet_gercek=a.evet_gercek, bina_tazele=a.bina_tazele)
    except KurulumReddi as exc:
        print(str(exc))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
