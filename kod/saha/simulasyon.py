"""60 iş günlük kapsama simülasyonu — algoritma tıkanıyor mu?

    .venv/Scripts/python.exe -m saha.simulasyon [--gun 60] [--adet 25] [--tohum 7]

Gerçek 19.706 binayı gerçek `rota.py` ile 60 iş günü boyunca gezer: her gün
8 satışçı × 25 bina. Sonuçlar gerçekçi bir dağılımla rastgele üretilir
(satış · ilgilenmedi · evde yok · randevu · altyapı · girilemedi), randevular
`tekrar_gel` yazar, böylece "sözü olan bina" sınıfı da devreye girer.

Sistemin vaadi "sudoku gibi boşlukları doldurmak". Bu betik o vaadi ÖLÇER:

  1. Kapsama her gün artar mı, yoksa bir yerde takılıp aynı binaları mı döner?
  2. 30 günlük soğuma delindi mi — bir binaya 30 gün dolmadan ikinci kez
     gidildi mi? (randevusu olan bina muaf)
  3. Fırsatı sıfır olan 666 bina sıraya girdi mi, yoksa sonsuza kadar
     görünmez mi kaldı?
  4. Günlük turlar bir günde gezilebilecek uzunlukta mı?
  5. Sonunda her bölgenin her binası en az bir kez listeye düştü mü?

Veritabanına DOKUNMAZ: şablonun geçici bir kopyasında çalışır.
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

from . import ayarlar, db, goc, rota

# Sahadan gözlenen kaba dağılım. Toplamı 1 olmak zorunda değil; ağırlık olarak
# kullanılır. "girilemedi" ve "altyapi_sorunu" binayı bir süreliğine kapatır.
SONUC_AGIRLIK = {
    "satis": 8,
    "ilgilenmedi": 34,
    "evde_yok": 30,
    "randevu": 12,
    "girilemedi": 9,
    "altyapi_sorunu": 5,
    "yanlis_adres": 2,
}

DURUM_ESLEME = {
    "satis": "ziyaret_edildi",
    "ilgilenmedi": "ziyaret_edildi",
    "evde_yok": "ziyaret_edildi",
    "randevu": "tekrar_gel",
    "girilemedi": "girilemedi",
    "altyapi_sorunu": "altyapi_sorunu",
    "yanlis_adres": "ziyaret_edildi",
}


def _is_gunu_ekle(gun: dt.date, adet: int = 1) -> dt.date:
    """Hafta sonlarını atlayarak `adet` iş günü ilerler."""
    for _ in range(adet):
        gun += dt.timedelta(days=1)
        while gun.weekday() >= 5:
            gun += dt.timedelta(days=1)
    return gun


def _ziyaret_yaz(conn, bina_serial: str, kullanici_id: int, zaman: dt.datetime, sonuc: str, rast) -> None:
    """Gerçek uçların yaptığı yazmanın simülasyon karşılığı."""
    satis_adedi = rast.randint(1, 3) if sonuc == "satis" else 0
    tekrar = None
    if sonuc == "randevu":
        # Randevu 2-10 iş günü sonrasına; soğumadan muaf olan tek yol bu.
        tekrar = _is_gunu_ekle(zaman.date(), rast.randint(2, 10)).isoformat()
    conn.execute(
        "INSERT INTO ziyaret (offline_id, bina_serial, kullanici_id, zaman, kayit_zamani, "
        "sonuc, satis_adedi, konusulan_daire, notu, cihaz) "
        "VALUES (?,?,?,?,?,?,?,0,NULL,'simulasyon')",
        (f"sim-{bina_serial}-{zaman.isoformat()}", bina_serial, kullanici_id,
         zaman.strftime("%Y-%m-%d %H:%M:%S"), zaman.strftime("%Y-%m-%d %H:%M:%S"),
         sonuc, satis_adedi),
    )
    conn.execute(
        "UPDATE bina_durum SET durum=?, son_ziyaret=?, son_kullanici_id=?, son_sonuc=?, "
        "tekrar_tarih=?, toplam_satis=toplam_satis+?, ziyaret_sayisi=ziyaret_sayisi+1 "
        "WHERE bina_serial=?",
        (DURUM_ESLEME[sonuc], zaman.strftime("%Y-%m-%d %H:%M:%S"), kullanici_id, sonuc,
         tekrar, satis_adedi, bina_serial),
    )


def calistir(gun_sayisi: int = 60, adet: int = 25, tohum: int = 7, kaynak: Path | None = None) -> dict:
    rast = random.Random(tohum)
    kaynak = Path(kaynak or ayarlar.DB_YOLU)
    if not kaynak.exists():
        raise SystemExit(f"Veritabanı yok: {kaynak}. Önce `python -m saha.kur` çalıştırın.")

    gecici = Path(tempfile.mkdtemp(prefix="saha-sim-")) / "sim.db"
    shutil.copy2(kaynak, gecici)
    # Kaynak eski şemadaysa GEÇİCİ kopya yeni sürüme taşınır (yedeksiz; canlı dosyaya dokunulmaz).
    goc.hazirla(gecici, yedek=False)
    conn = db.baglan(gecici)

    # Simülasyon TEMİZ bir sahadan başlar: gösterim verisi sonuçları kirletmesin.
    conn.execute("DELETE FROM ziyaret")
    conn.execute("DELETE FROM gorev_bina")
    conn.execute("DELETE FROM gorev")
    conn.execute(
        "UPDATE bina_durum SET durum='bekliyor', son_ziyaret=NULL, son_kullanici_id=NULL, "
        "son_sonuc=NULL, tekrar_tarih=NULL, toplam_satis=0, ziyaret_sayisi=0"
    )
    conn.commit()

    bolgeler = [r[0] for r in conn.execute(
        "SELECT DISTINCT bolge FROM bina WHERE bolge IS NOT NULL ORDER BY bolge")]
    bolge_bina = {b: conn.execute(
        "SELECT COUNT(*) FROM bina WHERE bolge=?", (b,)).fetchone()[0] for b in bolgeler}
    sifir_firsat = {r[0] for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE COALESCE(firsat,0) <= 0")}
    ofis = (ayarlar.OFIS["lat"], ayarlar.OFIS["lon"])

    listeye_giren: dict[str, int] = {}     # bina → kaç kez listeye düştü
    son_ziyaret_gunu: dict[str, dt.date] = {}
    ihlaller: list[str] = []
    gunluk: list[dict] = []
    tur_km: list[float] = []
    sonuc_sayaci: Counter = Counter()

    gun = ayarlar.bugun()
    while gun.weekday() >= 5:
        gun = _is_gunu_ekle(gun)

    for gun_no in range(1, gun_sayisi + 1):
        gunun_toplami = 0
        bos_bolge = []
        for i, bolge in enumerate(bolgeler):
            kullanici_id = i + 2  # 1 numara yönetici
            liste = rota.gunluk_rota(conn, bolge, ofis, adet, gun)
            if not liste:
                bos_bolge.append(bolge)
                continue
            tur_km.append(rota.toplam_mesafe_m(liste) / 1000.0)
            for sira, b in enumerate(liste):
                serial = b["bina_serial"]
                listeye_giren[serial] = listeye_giren.get(serial, 0) + 1

                # --- KURAL 1: 30 gün dolmadan tekrar gelinmesin ---
                onceki = son_ziyaret_gunu.get(serial)
                if onceki is not None:
                    fark = (gun - onceki).days
                    randevulu = (b.get("durum") or "") == "tekrar_gel"
                    if fark < ayarlar.SOGUMA_GUN and not randevulu:
                        ihlaller.append(
                            f"{gun} · {serial} · son ziyaretten {fark} gün sonra "
                            f"(durum={b.get('durum')})"
                        )

                sonuc = rast.choices(
                    list(SONUC_AGIRLIK), weights=list(SONUC_AGIRLIK.values()), k=1)[0]
                sonuc_sayaci[sonuc] += 1
                zaman = dt.datetime.combine(gun, dt.time(9, 0)) + dt.timedelta(minutes=18 * sira)
                _ziyaret_yaz(conn, serial, kullanici_id, zaman, sonuc, rast)
                son_ziyaret_gunu[serial] = gun
                gunun_toplami += 1
        conn.commit()

        dokunulan = conn.execute(
            "SELECT COUNT(*) FROM bina_durum WHERE durum<>'bekliyor'").fetchone()[0]
        gunluk.append({
            "gun": gun_no,
            "tarih": gun.isoformat(),
            "ziyaret": gunun_toplami,
            "dokunulan": dokunulan,
            "bos_bolge": bos_bolge,
        })
        gun = _is_gunu_ekle(gun)

    # ---------------------------------------------------------------- ölçüler
    dokunulanlar = [g["dokunulan"] for g in gunluk]
    monoton = all(b >= a for a, b in zip(dokunulanlar, dokunulanlar[1:]))
    duraganlik = [g["gun"] for g, o in zip(gunluk[1:], dokunulanlar) if g["dokunulan"] == o]

    bolge_kapsama = {}
    for b in bolgeler:
        toplam = bolge_bina[b]
        deger = conn.execute(
            "SELECT COUNT(*) FROM bina b JOIN bina_durum d USING (bina_serial) "
            "WHERE b.bolge=? AND d.durum<>'bekliyor'", (b,)).fetchone()[0]
        bolge_kapsama[b] = (deger, toplam, 100.0 * deger / toplam if toplam else 0.0)

    sifir_giren = len(sifir_firsat & set(listeye_giren))
    conn.close()
    shutil.rmtree(gecici.parent, ignore_errors=True)

    return {
        "gun_sayisi": gun_sayisi,
        "adet": adet,
        "gunluk": gunluk,
        "monoton": monoton,
        "duraganlik": duraganlik,
        "toplam_ziyaret": sum(g["ziyaret"] for g in gunluk),
        "benzersiz_bina": len(listeye_giren),
        "tekrar_gelinen": sum(1 for v in listeye_giren.values() if v > 1),
        "en_cok_tekrar": max(listeye_giren.values()) if listeye_giren else 0,
        "soguma_ihlali": ihlaller,
        "sifir_firsat_toplam": len(sifir_firsat),
        "sifir_firsat_giren": sifir_giren,
        "bolge_kapsama": bolge_kapsama,
        "tur_km_ortalama": sum(tur_km) / len(tur_km) if tur_km else 0.0,
        "tur_km_en_uzun": max(tur_km) if tur_km else 0.0,
        "tur_km_uzun_sayisi": sum(1 for k in tur_km if k > ayarlar.UZUN_TUR_KM),
        "tur_sayisi": len(tur_km),
        "sonuclar": dict(sonuc_sayaci),
        "son_dokunulan": dokunulanlar[-1] if dokunulanlar else 0,
        "toplam_bina": sum(bolge_bina.values()),
    }


def bolgeyi_bitir(bolge: int, adet: int = 25, tohum: int = 7, en_fazla_gun: int = 500,
                  kaynak: Path | None = None) -> dict:
    """Tek bir bölgeyi, HER BİNASI en az bir kez listeye düşene kadar gezer.

    60 iş günü bir bölgeyi bitirmeye yetmez (en büyüğü 3.052 bina, günde 25).
    "Sonunda her binaya uğranıyor mu" sorusunun cevabı ancak bölge bitene kadar
    koşarak verilebilir. Fırsatı sıfır olan binalar taban öncelikle en sonda
    beklediği için asıl sınav da budur: sıra onlara geliyor mu, yoksa algoritma
    son %3'te sonsuza kadar mı dönüyor?
    """
    rast = random.Random(tohum)
    kaynak = Path(kaynak or ayarlar.DB_YOLU)
    gecici = Path(tempfile.mkdtemp(prefix="saha-sim-bolge-")) / "sim.db"
    shutil.copy2(kaynak, gecici)
    # Kaynak eski şemadaysa GEÇİCİ kopya yeni sürüme taşınır (yedeksiz; canlı dosyaya dokunulmaz).
    goc.hazirla(gecici, yedek=False)
    conn = db.baglan(gecici)
    conn.execute("DELETE FROM ziyaret")
    conn.execute("DELETE FROM gorev_bina")
    conn.execute("DELETE FROM gorev")
    conn.execute(
        "UPDATE bina_durum SET durum='bekliyor', son_ziyaret=NULL, son_kullanici_id=NULL, "
        "son_sonuc=NULL, tekrar_tarih=NULL, toplam_satis=0, ziyaret_sayisi=0"
    )
    conn.commit()

    hepsi = {r[0] for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=?", (bolge,))}
    sifir = {r[0] for r in conn.execute(
        "SELECT bina_serial FROM bina WHERE bolge=? AND COALESCE(firsat,0) <= 0", (bolge,))}
    ofis = (ayarlar.OFIS["lat"], ayarlar.OFIS["lon"])

    gorulen: set[str] = set()
    son_gun: dict[str, dt.date] = {}
    ihlaller: list[str] = []
    sifir_gun: int | None = None
    tamam_gun: int | None = None

    gun = ayarlar.bugun()
    while gun.weekday() >= 5:
        gun = _is_gunu_ekle(gun)

    for gun_no in range(1, en_fazla_gun + 1):
        liste = rota.gunluk_rota(conn, bolge, ofis, adet, gun)
        if not liste:
            break
        for sira, b in enumerate(liste):
            serial = b["bina_serial"]
            onceki = son_gun.get(serial)
            if onceki is not None:
                fark = (gun - onceki).days
                if fark < ayarlar.SOGUMA_GUN and (b.get("durum") or "") != "tekrar_gel":
                    ihlaller.append(f"{gun} · {serial} · {fark} gün")
            gorulen.add(serial)
            sonuc = rast.choices(list(SONUC_AGIRLIK), weights=list(SONUC_AGIRLIK.values()), k=1)[0]
            zaman = dt.datetime.combine(gun, dt.time(9, 0)) + dt.timedelta(minutes=18 * sira)
            _ziyaret_yaz(conn, serial, kullanici_id=bolge + 1, zaman=zaman, sonuc=sonuc, rast=rast)
            son_gun[serial] = gun
        conn.commit()
        if sifir_gun is None and sifir <= gorulen:
            sifir_gun = gun_no
        if tamam_gun is None and hepsi <= gorulen:
            tamam_gun = gun_no
            break
        gun = _is_gunu_ekle(gun)

    conn.close()
    shutil.rmtree(gecici.parent, ignore_errors=True)
    return {
        "bolge": bolge,
        "bina": len(hepsi),
        "gorulen": len(gorulen),
        "tamam_gun": tamam_gun,
        "sifir_firsat": len(sifir),
        "sifir_gun": sifir_gun,
        "soguma_ihlali": ihlaller,
        "adet": adet,
    }


def yazdir(s: dict) -> int:
    """Sonucu Türkçe özetler; bir kural düştüyse çıkış kodu 1."""
    ayarlar.konsolu_hazirla()
    dusen = []
    bicim = lambda n: f"{n:,}".replace(",", ".")

    print(f"\n{s['gun_sayisi']} İŞ GÜNÜ · her gün 8 satışçı × {s['adet']} bina\n")
    print(f"  toplam ziyaret        {bicim(s['toplam_ziyaret'])}")
    print(f"  listeye düşen bina    {bicim(s['benzersiz_bina'])} / {bicim(s['toplam_bina'])}")
    print(f"  gün sonu kapsama      {bicim(s['son_dokunulan'])} bina")
    print(f"  tekrar gidilen bina   {bicim(s['tekrar_gelinen'])} (en çok {s['en_cok_tekrar']} kez)")
    print(f"  tur uzunluğu          ort. {s['tur_km_ortalama']:.1f} km · en uzun {s['tur_km_en_uzun']:.1f} km")

    print("\n1) Kapsama her gün arttı mı?")
    if s["monoton"] and not s["duraganlik"]:
        print(f"   ✓ evet — 1. gün {bicim(s['gunluk'][0]['dokunulan'])} → "
              f"{s['gun_sayisi']}. gün {bicim(s['son_dokunulan'])}, hiç duraklamadan")
    else:
        dusen.append("kapsama duraklıyor")
        print(f"   ✗ HAYIR — duraklayan günler: {s['duraganlik'][:10]}")

    print("\n2) 30 günlük soğuma delindi mi?")
    if not s["soguma_ihlali"]:
        print("   ✓ hayır — randevusu olmayan hiçbir binaya 30 gün dolmadan gidilmedi")
    else:
        dusen.append("soğuma ihlali")
        print(f"   ✗ {len(s['soguma_ihlali'])} ihlal:")
        for i in s["soguma_ihlali"][:5]:
            print(f"      {i}")

    print("\n3) Fırsatı sıfır olan binalar sıraya girdi mi?")
    if s["sifir_firsat_giren"] == s["sifir_firsat_toplam"]:
        print(f"   ✓ evet — {bicim(s['sifir_firsat_toplam'])} binanın hepsi listeye düştü")
    else:
        eksik = s["sifir_firsat_toplam"] - s["sifir_firsat_giren"]
        print(f"   · {bicim(s['sifir_firsat_giren'])} / {bicim(s['sifir_firsat_toplam'])} girdi — "
              f"{bicim(eksik)} bina HENÜZ sıraya gelmedi.")
        print("     Beklenen: boş kapısı olmayan bina taban öncelikle en sonda bekler,")
        print("     sırası bölgenin sonunda gelir. Kanıtı için bölgeyi bitirene kadar koşun:")
        print("       python -m saha.simulasyon --bitir 8")

    print("\n4) Turlar bir günde gezilebilir mi?")
    if s["tur_km_uzun_sayisi"] == 0:
        print(f"   ✓ evet — {bicim(s['tur_sayisi'])} turun hiçbiri "
              f"{ayarlar.UZUN_TUR_KM} km eşiğini aşmadı")
    else:
        oran = 100.0 * s["tur_km_uzun_sayisi"] / s["tur_sayisi"]
        print(f"   · {s['tur_km_uzun_sayisi']} tur ({oran:.1f}%) {ayarlar.UZUN_TUR_KM} km üstünde "
              "— satışçı listeyi alırken uyarı görüyor")

    print("\n5) Bölge bölge kapsama (gezilen / toplam):")
    for b, (deger, toplam, yuzde) in sorted(s["bolge_kapsama"].items()):
        print(f"   {b}. bölge  {bicim(deger):>6} / {bicim(toplam):<6} %{yuzde:4.1f}")

    print("\n   sonuç dağılımı: " + " · ".join(
        f"{k} {bicim(v)}" for k, v in sorted(s["sonuclar"].items(), key=lambda x: -x[1])))

    print(f"\n{'✅ ALGORİTMA TIKANMIYOR' if not dusen else '❌ ' + ', '.join(dusen)}\n")
    return 1 if dusen else 0


def main(argv: list[str] | None = None) -> int:
    ayarlar.konsolu_hazirla()
    ayristirici = argparse.ArgumentParser(description="Kapsama simülasyonu")
    ayristirici.add_argument("--gun", type=int, default=60, help="kaç iş günü (varsayılan 60)")
    ayristirici.add_argument("--adet", type=int, default=25, help="satışçı başına günlük bina")
    ayristirici.add_argument("--tohum", type=int, default=7, help="rastgelelik tohumu")
    ayristirici.add_argument("--db", type=Path, default=None, help="kaynak veritabanı")
    ayristirici.add_argument(
        "--bitir", type=int, default=None, metavar="BOLGE",
        help="tek bölgeyi her binası listeye düşene kadar gez (1..8)",
    )
    a = ayristirici.parse_args(argv)
    if a.bitir:
        s = bolgeyi_bitir(a.bitir, a.adet, a.tohum, kaynak=a.db)
        bicim = lambda n: f"{n:,}".replace(",", ".")
        print(f"\n{s['bolge']}. BÖLGE — bitene kadar (günde {s['adet']} bina)\n")
        print(f"  bölgedeki bina        {bicim(s['bina'])}")
        print(f"  listeye düşen         {bicim(s['gorulen'])}")
        if s["tamam_gun"]:
            print(f"\n   ✓ {s['tamam_gun']} iş gününde bölgedeki HER binaya en az bir kez uğranıldı")
        else:
            print(f"\n   ✗ bölge bitmedi — {bicim(s['bina'] - s['gorulen'])} bina hiç listeye düşmedi")
        if s["sifir_firsat"]:
            if s["sifir_gun"]:
                print(f"   ✓ fırsatı sıfır {bicim(s['sifir_firsat'])} binanın hepsi "
                      f"{s['sifir_gun']}. günde sıraya girdi")
            else:
                print(f"   ✗ fırsatı sıfır {bicim(s['sifir_firsat'])} bina hiç sıraya girmedi")
        print(f"   {'✓' if not s['soguma_ihlali'] else '✗'} soğuma ihlali: "
              f"{len(s['soguma_ihlali'])}\n")
        return 0 if (s["tamam_gun"] and not s["soguma_ihlali"]) else 1
    return yazdir(calistir(a.gun, a.adet, a.tohum, a.db))


if __name__ == "__main__":
    sys.exit(main())
