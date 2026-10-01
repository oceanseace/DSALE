"""Bugünün işi bir GÖREV değil, bir GÜN.

Satışçı 25 binayı bitirip "yeni liste al" derse sunucu sabahki görevi kapatıp
yenisini açar. `/api/gorev/bugun` yalnız açık görevi döndürdüğü için sabah
gezilen binalar ekrandan siliniyor, satışçı öğleden sonra telefonuna bakıp
bütün emeğini kaybolmuş görüyordu. Bu testler günün tamamının erişilebilir
kaldığını ve sayaçların YİNE DE açık listeyi saydığını garanti eder.
"""
from __future__ import annotations

from .conftest import SATISCI_TEL


def _liste_al(istemci, bas, adet=3):
    yanit = istemci.post("/api/gorev/olustur", json={"adet": adet}, headers=bas)
    assert yanit.status_code == 200, yanit.text
    return yanit.json()


def _hepsini_bitir(istemci, bas, gorev, onek):
    for i, b in enumerate(gorev["binalar"]):
        yanit = istemci.post(
            "/api/ziyaret",
            json={
                "offline_id": f"{onek}-{i}",
                "bina_serial": b["bina_serial"],
                "sonuc": "evde_yok",
            },
            headers=bas,
        )
        assert yanit.status_code == 200, yanit.text


def test_ikinci_liste_sabahki_binalari_gizlemiyor(istemci, satisci1):
    ilk = _liste_al(istemci, satisci1, adet=3)
    sabah = [b["bina_serial"] for b in ilk["binalar"]]
    _hepsini_bitir(istemci, satisci1, ilk, "sabah")

    ikinci = _liste_al(istemci, satisci1, adet=3)
    assert ikinci["gorev_id"] != ilk["gorev_id"], "yeni liste açılmalıydı"

    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    onceki = {b["bina_serial"] for b in bugun["onceki_binalar"]}
    assert set(sabah) <= onceki, "sabah gezilen binalar günün geçmişinde durmalı"
    assert all(b["gorev_durum"] == "tamam" for b in bugun["onceki_binalar"])

    # ...ama ilerleme sayacı AÇIK listeyi saymalı: "3 / 6" gibi bir sayı çıkmamalı.
    assert bugun["ozet"]["toplam"] == len(ikinci["binalar"])
    assert bugun["ozet"]["tamam"] == 0
    assert len(bugun["binalar"]) == len(ikinci["binalar"])
    # Aynı bina iki listede birden görünmemeli.
    acik = {b["bina_serial"] for b in bugun["binalar"]}
    assert not (acik & onceki)


def test_tek_liste_varken_gun_gecmisi_bos(istemci, satisci1):
    _liste_al(istemci, satisci1, adet=3)
    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    assert bugun["onceki_binalar"] == []


def test_liste_bitip_yenisi_alinmadan_gecmis_dolmaz(istemci, satisci1):
    """Görev kapanmadan önce binalar HÂLÂ açık listede; iki kez sayılmamalı."""
    ilk = _liste_al(istemci, satisci1, adet=3)
    _hepsini_bitir(istemci, satisci1, ilk, "bitir")
    bugun = istemci.get("/api/gorev/bugun", headers=satisci1).json()
    assert bugun["onceki_binalar"] == []
    assert bugun["ozet"]["tamam"] == len(ilk["binalar"])


def test_liste_yokken_de_gun_gecmisi_geliyor(istemci, basliklar):
    """Görev kapandıysa ama yenisi alınmadıysa gün yine de görünür."""
    bas = basliklar(SATISCI_TEL[3], "6482")
    ilk = _liste_al(istemci, bas, adet=2)
    _hepsini_bitir(istemci, bas, ilk, "kapat")
    # Görevi elle kapat: satışçı listeyi bitirdi, yenisini HENÜZ almadı.
    istemci.post("/api/gorev/olustur", json={"adet": 2}, headers=bas)
    bugun = istemci.get("/api/gorev/bugun", headers=bas).json()
    assert len(bugun["onceki_binalar"]) == len(ilk["binalar"])
