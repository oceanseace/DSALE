"""Bölgenin SONU: son gri noktalar gerçekten listeye giriyor mu?

Ürünün vaadi "sudoku gibi boşlukları doldurmak". İlk %90 kolay; asıl sınav
kalan birkaç bina. Dokunulmamış bina sayısı bir günlük işin altına düşünce
havuz tekrar ziyaretlerle dolar ve son binalar puan yarışını KALICI olarak
kaybedebilir: fırsatı sıfır ya da öbeğin dışında kalan bir bina, yanındaki
"30 günü dolmuş, 40 boş kapılı" binaya karşı hiçbir gün kazanamaz.

Ölçüldü: düzeltmeden önce 1. bölge 88 günde 1.972/1.973'e geliyor, kalan TEK
bina 350 iş günü daha seçilmiyordu. Bu testler o deliği kapalı tutar.
"""
from __future__ import annotations

import datetime as dt

from saha import ayarlar, rota

BUGUN = dt.date(2026, 9, 21)


def _bolgeyi_gez(conn, bolge: int, gun: dt.date, sonuc: str = "ilgilenmedi",
                 birak: int = 0) -> list[str]:
    """Bölgedeki binaları `birak` tanesi hariç ziyaret edilmiş yapar.

    Zaman damgası 40 gün öncesine yazılır: soğuma dolmuş olur, yani bu binalar
    tekrar ziyarete UYGUNDUR ve son kalanlarla yarışırlar.
    """
    eski = (gun - dt.timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
    seriler = [
        r[0] for r in conn.execute(
            "SELECT bina_serial FROM bina WHERE bolge=? ORDER BY bina_serial", (bolge,)
        )
    ]
    dokunulacak = seriler[birak:]
    conn.executemany(
        "UPDATE bina_durum SET durum='ziyaret_edildi', son_ziyaret=?, son_sonuc=?, "
        "ziyaret_sayisi=1 WHERE bina_serial=?",
        [(eski, sonuc, s) for s in dokunulacak],
    )
    conn.commit()
    return seriler[:birak]


def test_son_kalan_tek_bina_listeye_giriyor(conn):
    """Bölgede tek bir dokunulmamış bina kaldıysa o bina BUGÜN listeye girer."""
    kalanlar = _bolgeyi_gez(conn, 1, BUGUN, birak=1)
    liste = rota.gunluk_rota(conn, 1, None, 25, BUGUN)
    seriler = [b["bina_serial"] for b in liste]
    assert kalanlar[0] in seriler, "son dokunulmamış bina listeye girmeliydi"
    # Gün yine dolu olmalı: satışçı tek binayla eve gönderilmez.
    assert len(liste) >= 20, f"gün tekrar ziyaretlerle dolmalıydı ({len(liste)})"


def test_son_kalanlar_hepsi_birden_giriyor(conn):
    """Bir günlük işin altındaki kalanların TAMAMI aynı gün alınır."""
    kalanlar = _bolgeyi_gez(conn, 2, BUGUN, birak=6)
    liste = rota.gunluk_rota(conn, 2, None, 25, BUGUN)
    seriler = {b["bina_serial"] for b in liste}
    eksik = [s for s in kalanlar if s not in seriler]
    assert not eksik, f"dokunulmamış bina listede yok: {eksik}"


def test_firsati_sifir_olan_son_bina_da_giriyor(conn):
    """Fırsatı sıfır olan bina taban öncelikle en sonda bekler ama unutulmaz."""
    kalanlar = _bolgeyi_gez(conn, 3, BUGUN, birak=1)
    conn.execute("UPDATE bina SET firsat=0 WHERE bina_serial=?", (kalanlar[0],))
    conn.commit()
    liste = rota.gunluk_rota(conn, 3, None, 25, BUGUN)
    assert kalanlar[0] in [b["bina_serial"] for b in liste]


def test_bol_dokunulmamis_varken_tekrar_ziyaret_karismaz(conn):
    """Normal günde kural değişmez: bölge bitmeden aynı kapıya ikinci kez gidilmez."""
    _bolgeyi_gez(conn, 4, BUGUN, birak=400)
    liste = rota.gunluk_rota(conn, 4, None, 25, BUGUN)
    tekrar = [b["bina_serial"] for b in liste if b.get("son_ziyaret")]
    assert not tekrar, f"dokunulmamış bina varken tekrar ziyaret listeye girmemeli: {tekrar}"


def test_sira_numaralari_bozulmuyor(conn):
    """İki parçadan kurulan listede sıra 1..n olarak kesintisiz akar."""
    _bolgeyi_gez(conn, 5, BUGUN, birak=3)
    liste = rota.gunluk_rota(conn, 5, None, 25, BUGUN)
    assert [b["sira"] for b in liste] == list(range(1, len(liste) + 1))
    assert all(b.get("mesafe_m") is not None for b in liste)


def test_bolge_bitince_bos_donmuyor(conn):
    """Hiç dokunulmamış bina kalmadıysa gün yine de tekrar ziyaretlerle dolar."""
    _bolgeyi_gez(conn, 6, BUGUN, birak=0)
    liste = rota.gunluk_rota(conn, 6, None, 25, BUGUN)
    assert len(liste) >= 20
    assert all(b.get("son_ziyaret") for b in liste)


def test_soguma_dolmadiysa_tekrar_gelinmez(conn):
    """Kalanları tamamlarken bile 30 günlük soğuma delinmez."""
    taze = BUGUN.strftime("%Y-%m-%d %H:%M:%S")
    kalanlar = _bolgeyi_gez(conn, 7, BUGUN, birak=2)
    # Bölgedeki bütün tekrar adaylarını BUGÜN ziyaret edilmiş yap.
    conn.execute(
        "UPDATE bina_durum SET son_ziyaret=? WHERE bina_serial IN "
        "(SELECT bina_serial FROM bina WHERE bolge=7) AND durum='ziyaret_edildi'",
        (taze,),
    )
    conn.commit()
    liste = rota.gunluk_rota(conn, 7, None, 25, BUGUN)
    seriler = [b["bina_serial"] for b in liste]
    assert set(seriler) == set(kalanlar), (
        "soğuması dolmamış bina listeye girmemeliydi; yalnız son iki bina beklenir"
    )
    assert ayarlar.SOGUMA_GUN == 30
