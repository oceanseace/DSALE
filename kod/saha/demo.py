"""Gösterim (demo) verisi kurar — Hasan Bey'e boş ekran göstermemek için.

    .venv/Scripts/python.exe -m saha.demo             # kur
    .venv/Scripts/python.exe -m saha.demo --gun 7     # kaç günlük geçmiş
    .venv/Scripts/python.exe -m saha.demo_temizle     # TAMAMEN geri al

Ne yapar
    1. 8 satışçıya ad ve telefon verir (hepsi yer tutucu, gerçek kişi değil).
    2. Son N günün ziyaret geçmişini üretir: her gün her satışçı ~20-30 bina.
       Sonuç dağılımı sahadan beklenene yakındır (satış ~%14, evde yok ~%22 ...).
    3. Bugün için herkese görev listesi açar; bir kısmı yarılanmış, biri hiç
       başlamamış, birinde liste yok — yönetici ekranı gerçekçi görünsün.

Gerçek veriden ayırt etme
    Üretilen her ziyaretin ``offline_id`` değeri ``demo-`` ile başlar ve
    ``cihaz`` sütunu ``DEMO``dur. ``ayar`` tablosunda ``demo`` anahtarı durur.
    ``demo_temizle`` yalnız bu kayıtları siler; sahadan gelmiş gerçek bir
    ziyaret varsa ona dokunmaz.

Rastgelelik tohumludur (``--tohum``): aynı komut her zaman aynı tabloyu üretir,
yani ekran görüntüsü ile canlı ekran birbirini tutar.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sqlite3
import sys

from . import ayarlar, db, rota

ONEK = "demo-"                  # offline_id öneki — temizlik bunu arar
CIHAZ = "DEMO"
AYAR_ANAHTARI = "demo"

# Yer tutucu ekip. Gerçek isim ve numara yönetici ekranından girilir;
# 0555 000 00 XX numaraları kimseye ait değildir.
EKIP = [
    ("Ahmet Yıldırım", "5550000001"),
    ("Seda Arslan", "5550000002"),
    ("Burak Demir", "5550000003"),
    ("Elif Kaya", "5550000004"),
    ("Mert Şahin", "5550000005"),
    ("Zeynep Çelik", "5550000006"),
    ("Onur Aydın", "5550000007"),
    ("Derya Koç", "5550000008"),
]
YONETICI = ("Hasan Bey (yönetici)", "5550000000")

# Sahadan beklenen sonuç dağılımı. Toplam 100.
DAGILIM = [
    ("evde_yok", 24),
    ("ilgilenmedi", 23),
    ("satis", 14),
    ("randevu", 12),
    ("girilemedi", 10),
    ("altyapi_sorunu", 9),
    ("yanlis_adres", 8),
]

# Bugünün listesi: satışçı başına "kaç bina atandı / kaçı bitti".
# Biri hiç başlamamış (0), birinde liste yok (None) — yönetici uyarıyı görsün.
BUGUN_DESENI = [22, 18, 25, 11, 0, 20, None, 6]


def _sonuc_sec(rastgele: random.Random) -> str:
    n = rastgele.randint(1, 100)
    toplam = 0
    for sonuc, pay in DAGILIM:
        toplam += pay
        if n <= toplam:
            return sonuc
    return "ilgilenmedi"


def _ekibi_kur(conn: sqlite3.Connection) -> list[dict]:
    """Yer tutucu satışçı kayıtlarına ad/telefon yazar; kimseyi silmez."""
    kisiler: list[dict] = []

    yonetici = conn.execute("SELECT * FROM kullanici WHERE rol='yonetici' ORDER BY id").fetchone()
    if yonetici:
        conn.execute("UPDATE kullanici SET ad=?, telefon=? WHERE id=?",
                     (YONETICI[0], YONETICI[1], yonetici["id"]))
        kisiler.append({"id": yonetici["id"], "ad": YONETICI[0], "bolge": None})

    for bolge in range(1, ayarlar.BOLGE_SAYISI + 1):
        satir = conn.execute(
            "SELECT * FROM kullanici WHERE rol='satisci' AND bolge=? ORDER BY id", (bolge,)
        ).fetchone()
        if not satir:
            continue
        ad, telefon = EKIP[bolge - 1]
        conn.execute("UPDATE kullanici SET ad=?, telefon=? WHERE id=?", (ad, telefon, satir["id"]))
        kisiler.append({"id": satir["id"], "ad": ad, "bolge": bolge})
    return kisiler


def _gecmisi_uret(conn: sqlite3.Connection, satiscilar: list[dict], gun_sayisi: int,
                  rastgele: random.Random) -> int:
    """Son ``gun_sayisi`` günün ziyaretlerini yazar (bugün hariç)."""
    bugun = ayarlar.bugun()
    yazilan = 0

    for kisi in satiscilar:
        havuz = [
            s["bina_serial"]
            for s in conn.execute(
                "SELECT b.bina_serial FROM bina b JOIN bina_durum d USING(bina_serial) "
                "WHERE b.bolge=? AND d.son_ziyaret IS NULL ORDER BY b.firsat DESC, b.bina_serial "
                "LIMIT 400",
                (kisi["bolge"],),
            ).fetchall()
        ]
        rastgele.shuffle(havuz)
        sira = 0

        for geri in range(gun_sayisi, 0, -1):
            gun = bugun - dt.timedelta(days=geri)
            if gun.weekday() == 6:              # pazar sahaya çıkılmaz
                continue
            adet = rastgele.randint(18, 30)
            for _ in range(adet):
                if sira >= len(havuz):
                    break
                serial = havuz[sira]
                sira += 1
                sonuc = _sonuc_sec(rastgele)
                an = dt.datetime.combine(gun, dt.time(9, 0)) + dt.timedelta(
                    minutes=rastgele.randint(0, 8 * 60)
                )
                _ziyaret_yaz(conn, kisi["id"], serial, sonuc, an, rastgele)
                yazilan += 1
    return yazilan


def _ziyaret_yaz(conn: sqlite3.Connection, kullanici_id: int, serial: str, sonuc: str,
                 an: dt.datetime, rastgele: random.Random) -> None:
    satis_adedi = rastgele.randint(1, 3) if sonuc == "satis" else 0
    offline_id = f"{ONEK}{kullanici_id}-{serial}-{an:%Y%m%d%H%M%S}"
    conn.execute(
        "INSERT OR IGNORE INTO ziyaret "
        "(offline_id, bina_serial, kullanici_id, zaman, sonuc, satis_adedi, konusulan_daire, "
        " notu, lat, lon, cihaz, kayit_zamani) "
        "VALUES (?,?,?,?,?,?,?,NULL,NULL,NULL,?,?)",
        (offline_id, serial, kullanici_id, ayarlar.zaman_metni(an), sonuc, satis_adedi,
         rastgele.randint(0, 6), CIHAZ, ayarlar.zaman_metni(an)),
    )
    durum = ayarlar.SONUC_DURUM.get(sonuc, "ziyaret_edildi")
    tekrar = None
    if sonuc == "randevu":
        tekrar = (an.date() + dt.timedelta(days=ayarlar.RANDEVU_GUN)).isoformat()
    elif sonuc == "evde_yok":
        tekrar = (an.date() + dt.timedelta(days=ayarlar.EVDE_YOK_GUN)).isoformat()
    conn.execute(
        "UPDATE bina_durum SET durum=?, son_ziyaret=?, son_kullanici_id=?, son_sonuc=?, "
        "tekrar_tarih=?, toplam_satis=toplam_satis+?, ziyaret_sayisi=ziyaret_sayisi+1 "
        "WHERE bina_serial=?",
        (durum, ayarlar.zaman_metni(an), kullanici_id, sonuc, tekrar, satis_adedi, serial),
    )


def _bugunu_kur(conn: sqlite3.Connection, satiscilar: list[dict], rastgele: random.Random) -> int:
    """Bugün için görev listeleri açar ve bir kısmını yarılar."""
    bugun = ayarlar.bugun()
    simdi = ayarlar.zaman_metni()
    acilan = 0

    for kisi in satiscilar:
        desen = BUGUN_DESENI[(kisi["bolge"] or 1) - 1]
        if desen is None:
            continue                                   # bu satışçının bugün listesi yok
        adaylar = rota.gunluk_rota(
            conn, kisi["bolge"],
            baslangic=(ayarlar.OFIS["lat"], ayarlar.OFIS["lon"]), adet=25, bugun=bugun,
        )
        if not adaylar:
            continue
        imlec = conn.execute(
            "INSERT INTO gorev (kullanici_id, tarih, durum, olusturan_id, kaynak, notu, olusturma) "
            "VALUES (?,?,'acik',?, 'algoritma', ?, ?)",
            (kisi["id"], bugun.isoformat(), kisi["id"], "Gösterim verisi", simdi),
        )
        gorev_id = int(imlec.lastrowid)
        acilan += 1
        for sira, bina in enumerate(adaylar, start=1):
            conn.execute(
                "INSERT OR IGNORE INTO gorev_bina (gorev_id, bina_serial, sira, durum, mesafe_m) "
                "VALUES (?,?,?,'bekliyor',?)",
                (gorev_id, bina["bina_serial"], sira, int(bina.get("mesafe_m") or 0)),
            )
            conn.execute(
                "UPDATE bina_durum SET durum='planli' WHERE bina_serial=? AND durum='bekliyor'",
                (bina["bina_serial"],),
            )

        # Listenin bir kısmını bugün gezilmiş say.
        bitmis = min(desen, len(adaylar))
        for bina in adaylar[:bitmis]:
            sonuc = _sonuc_sec(rastgele)
            an = dt.datetime.combine(bugun, dt.time(9, 0)) + dt.timedelta(
                minutes=rastgele.randint(0, 7 * 60)
            )
            _ziyaret_yaz(conn, kisi["id"], bina["bina_serial"], sonuc, an, rastgele)
            conn.execute(
                "UPDATE gorev_bina SET durum='tamam' WHERE gorev_id=? AND bina_serial=?",
                (gorev_id, bina["bina_serial"]),
            )
    return acilan


def kur(gun_sayisi: int = 7, tohum: int = 20260921, sessiz: bool = False) -> dict:
    ayarlar.konsolu_hazirla()
    rastgele = random.Random(tohum)
    from . import goc

    conn = db.baglan()
    try:
        try:
            db.semayi_kur(conn)      # göç burada yapılmaz; sürüm uymuyorsa durur
        except goc.SurumUyumsuz as exc:
            raise SystemExit(exc.mesaj) from exc
        if conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0] == 0:
            raise SystemExit("Önce veritabanını kurun:  python -m saha.kur")
        if db.ayar_oku(conn, AYAR_ANAHTARI):
            raise SystemExit(
                "Gösterim verisi zaten kurulu. Önce temizleyin:  python -m saha.demo_temizle"
            )

        kisiler = _ekibi_kur(conn)
        satiscilar = [k for k in kisiler if k["bolge"]]
        ziyaret = _gecmisi_uret(conn, satiscilar, gun_sayisi, rastgele)
        gorev = _bugunu_kur(conn, satiscilar, rastgele)

        db.ayar_yaz(conn, AYAR_ANAHTARI, json.dumps({
            "kurulum": ayarlar.zaman_metni(),
            "gun": gun_sayisi,
            "tohum": tohum,
            "onek": ONEK,
            "aciklama": "Gösterim verisi — gerçek saha kaydı değildir.",
        }, ensure_ascii=False))
        conn.commit()

        ozet = {
            "satisci": len(satiscilar),
            "ziyaret": conn.execute(
                "SELECT COUNT(*) FROM ziyaret WHERE offline_id LIKE ?", (ONEK + "%",)
            ).fetchone()[0],
            "bugun_gorev": gorev,
            "dokunulan": conn.execute(
                "SELECT COUNT(*) FROM bina_durum WHERE son_ziyaret IS NOT NULL"
            ).fetchone()[0],
            "toplam_bina": conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0],
            "uretilen_ziyaret": ziyaret,
        }
    finally:
        conn.close()

    if not sessiz:
        _ozet_yaz(ozet)
    return ozet


def _ozet_yaz(o: dict) -> None:
    def s(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    print("\n  GÖSTERİM VERİSİ KURULDU")
    print("  " + "-" * 56)
    print(f"  Satışçı                 : {o['satisci']} kişi (yer tutucu ad/telefon)")
    print(f"  Üretilen ziyaret        : {s(o['ziyaret'])}")
    print(f"  Bugün açılan liste      : {o['bugun_gorev']}")
    print(f"  Dokunulan bina          : {s(o['dokunulan'])} / {s(o['toplam_bina'])}")
    print("  " + "-" * 56)
    print("  Bu veri GERÇEK DEĞİLDİR. Geri almak için:")
    print("      .venv\\Scripts\\python.exe -m saha.demo_temizle\n")


def demo_bilgisi(conn: sqlite3.Connection) -> dict | None:
    """Kurulu gösterim verisinin künyesi; yoksa None."""
    ham = db.ayar_oku(conn, AYAR_ANAHTARI)
    if not ham:
        return None
    try:
        return json.loads(ham)
    except (TypeError, ValueError):
        return {"aciklama": "Gösterim verisi kurulu."}


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Saha Sistemi gösterim verisi")
    ayrac.add_argument("--gun", type=int, default=7, help="Kaç günlük geçmiş üretilsin (varsayılan 7)")
    ayrac.add_argument("--tohum", type=int, default=20260921, help="Rastgelelik tohumu")
    a = ayrac.parse_args(argv)
    kur(gun_sayisi=max(1, a.gun), tohum=a.tohum)
    return 0


if __name__ == "__main__":
    sys.exit(main())
