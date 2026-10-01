"""Öbekler ve mahalle sözlüğü (F1, F2, F5; spec §1.6, §5.3.5). Kullanıcının öbek JSON'unun yalnız KOPYASI okunur."""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from operasyon.testler import yardim as y
from operasyon.testler.conftest import GERCEK_OBEK
from operasyon.v2 import obek, sozluk
from operasyon.v2.hatalar import V2Hata


def _obeksiz(conn, n=1, ilce="Nilüfer"):
    """Öbeği olmayan, tek sözcüklü (adresten sorunsuz ayrışan) sözlük mahalleleri."""
    ms = [m for m in sozluk.ara(conn, None, "Bursa", ilce, 500)["mahalleler"]
          if m["obek"] is None and m["kaynak"] in ("liste", "resmi", "bina") and re.fullmatch(r"[^\W\d_]{4,}", m["ad"])]
    assert len(ms) >= n
    return ms[:n]


def _durum(conn, no):
    return conn.execute("SELECT durum, obek_id, triyaj_nedeni FROM is_emri WHERE is_no=?", (no,)).fetchone()


def _yeni_obek(conn, op, ad="Deneme Öbeği"):
    s = obek.olustur(conn, ad, op, obek.surum(conn))
    return s["obek"]["id"], s["surum"]


def test_mahalle_ekle_cikar_is_sayisi(v2db, conn, kim):
    """F1: öbeğe mahalle eklenince o mahallenin işleri öbeğe geçer; çıkarılınca Kontrol'e döner. Sayılar anında."""
    op = kim("operasyon")
    m1, m2 = _obeksiz(conn, 2)
    y.aktar(v2db, [y.satir(1, mahalle=m1["ad"]), y.satir(2, mahalle=m1["ad"]), y.satir(3, mahalle=m2["ad"])])
    nolar = sorted(r[0] for r in conn.execute("SELECT is_no FROM is_emri"))
    assert [(_durum(conn, n)["durum"], _durum(conn, n)["triyaj_nedeni"]) for n in nolar] == [("triyaj", "obeksiz")] * 3
    oid, surum = _yeni_obek(conn, op)
    s = obek.mahalle_ekle(conn, oid, op, surum, mahalle_idler=[m1["id"], m2["id"]])
    assert s["etkilenen_is"] == 3
    o = next(x for x in s["obekler"] if x["id"] == oid)
    assert o["acik"] == 3 and {m["mahalle"]: m["acik"] for m in o["mahalleler"]} == {m1["ad"]: 2, m2["ad"]: 1}
    assert {_durum(conn, n)["durum"] for n in nolar} == {"bekliyor"} and {_durum(conn, n)["obek_id"] for n in nolar} == {oid}
    s = obek.mahalle_cikar(conn, oid, [m2["ref"]], op, s["surum"])
    assert s["etkilenen_is"] == 1
    o = next(x for x in s["obekler"] if x["id"] == oid)
    assert o["acik"] == 2 and [m["mahalle"] for m in o["mahalleler"]] == [m1["ad"]]
    assert tuple(_durum(conn, nolar[2])) == ("triyaj", None, "obeksiz")
    olay = conn.execute("SELECT notu FROM is_emri_olay WHERE is_no=? ORDER BY id DESC LIMIT 1", (nolar[2],)).fetchone()[0]
    assert "Kontrol" in olay


def test_son_mahalle_obegi_silmez(v2db, conn, kim):
    op = kim("operasyon")
    (m,) = _obeksiz(conn, 1)
    oid, surum = _yeni_obek(conn, op)
    s = obek.mahalle_ekle(conn, oid, op, surum, mahalle_idler=[m["id"]])
    s = obek.mahalle_cikar(conn, oid, [m["ref"]], op, s["surum"])
    o = next(x for x in obek.liste(conn)["obekler"] if x["id"] == oid)          # boş kalsa da listede
    assert o["mahalleler"] == [] and o["acik"] == 0
    assert conn.execute("SELECT aktif FROM obek WHERE id=?", (oid,)).fetchone()[0] == 1


def test_baska_obekte_409_ve_tasi(v2db, conn, kim):
    op = kim("operasyon")
    (m,) = _obeksiz(conn, 1)
    y.aktar(v2db, [y.satir(1, mahalle=m["ad"])])
    a, surum = _yeni_obek(conn, op, "Deneme A")
    s = obek.mahalle_ekle(conn, a, op, surum, mahalle_idler=[m["id"]])
    b = obek.olustur(conn, "Deneme B", op, s["surum"])
    with pytest.raises(V2Hata) as e:
        obek.mahalle_ekle(conn, b["obek"]["id"], op, b["surum"], mahalle_idler=[m["id"]])
    assert e.value.kod == "baska_obekte" and e.value.durum == 409
    assert e.value.ek["catisma"] == [{"ref": m["ref"], "obek": {"id": a, "ad": "Deneme A"}}]
    assert "Buraya taşınsın mı?" in e.value.mesaj
    s = obek.mahalle_ekle(conn, b["obek"]["id"], op, obek.surum(conn), mahalle_idler=[m["id"]], tasi=True)
    assert s["etkilenen_is"] == 1
    assert conn.execute("SELECT obek_id FROM is_emri").fetchone()[0] == b["obek"]["id"]
    assert conn.execute("SELECT tur FROM obek_olay ORDER BY id DESC LIMIT 1").fetchone()[0] == "tasi"


def test_rapordisi_mahalle_ve_ilce_tamami(v2db, conn, kim):
    """F2: rapora hiç düşmemiş mahalle ve 'ilçenin tamamı' öbeğe eklenebilir; işi 0 olan öbek de listede görünür."""
    op = kim("operasyon")
    yeni = sozluk.ekle(conn, "Bursa", "Kestel", "Yenigöçmen Deneme", op, benzerine_ragmen=True)
    conn.commit()
    assert yeni["kaynak"] == "elle" and yeni["acik"] == 0
    bul = sozluk.ara(conn, "yenigocmen", None, None)["mahalleler"]         # Türkçe harf duyarsız
    assert [m["ad"] for m in bul] == ["Yenigöçmen Deneme"]
    gursu = sozluk.ara(conn, "gursu", None, None)
    assert any(i["ilce"] == "Gürsu" for i in gursu["ilceler"])
    oid, surum = _yeni_obek(conn, op, "Deneme Doğu")
    s = obek.mahalle_ekle(conn, oid, op, surum, mahalle_idler=[yeni["id"]], tum_ilce=[{"il": "Bursa", "ilce": "Gürsu"}],
                          tasi=True)
    o = next(x for x in obek.liste(conn)["obekler"] if x["id"] == oid)
    assert o["acik"] == 0                                                   # işi 0 öbek listede
    assert {m["ref"] for m in o["mahalleler"]} == {"Bursa/Kestel/Yenigöçmen Deneme", "Bursa/Gürsu/*"}
    assert any(m["tum_ilce"] and m["mahalle"] == "İlçenin tamamı" for m in o["mahalleler"])
    # Gürsu'nun tek tek başka öbeğe verilmemiş her mahallesi bu öbeğe düşer
    gm = next(m for m in sozluk.ara(conn, None, "Bursa", "Gürsu", 500)["mahalleler"]
              if re.fullmatch(r"[^\W\d_]{4,}", m["ad"]) and (m["obek"] or {}).get("id") == oid)
    y.aktar(v2db, [y.satir(1, ilce="Gürsu", mahalle=gm["ad"])])
    assert conn.execute("SELECT obek_id FROM is_emri").fetchone()[0] == oid
    assert s["surum"] == obek.surum(conn)


def test_23_ilce(v2db, conn):
    ilceler = sozluk.ilceler(conn)
    assert len(ilceler) == 23
    assert sum(1 for i in ilceler if i["il"] == "Bursa") == 17 and sum(1 for i in ilceler if i["il"] == "Yalova") == 6
    assert conn.execute("SELECT COUNT(*) FROM mahalle WHERE kaynak IN ('liste','resmi')").fetchone()[0] >= 600
    # 621'lik liste 10 Bursa ilçesini kapsar; diğer 13 ilçe bina/öbek/rapor/elle ya da resmî liste yüklemesiyle dolar
    # (POST /api/mahalleler/yukle) — o zamana kadar "İlçenin tamamı" ile öbeğe verilebilir.
    listeli = {"Gemlik", "Gürsu", "Kestel", "Mudanya", "Nilüfer", "Orhangazi", "Osmangazi", "Yenişehir", "Yıldırım", "İnegöl"}
    sayi = {i["ilce"]: i["mahalle_sayisi"] for i in ilceler}
    assert all(sayi[a] >= 15 for a in listeli)
    # ilçe eşadları: 'M.Kemalpaşa' ve 'Yalova Merkez' asıl ilçeye iner
    h = sozluk.ilce_haritasi(conn)
    assert sozluk.ilce_coz(h, "Bursa", "M.Kemalpaşa")[3] == "Mustafakemalpaşa"
    assert sozluk.ilce_coz(h, "Yalova", "Yalova Merkez")[3] == "Merkez"


def test_sonraki_rapordaki_is_obege_duser(v2db, conn, kim):
    """F2: bugün işi olmayan mahalle öbeğe eklenir; sonraki rapordaki işi o öbeğe düşer."""
    op = kim("operasyon")
    (m,) = _obeksiz(conn, 1, ilce="Osmangazi")
    oid, surum = _yeni_obek(conn, op)
    obek.mahalle_ekle(conn, oid, op, surum, mahalle_idler=[m["id"]])
    y.aktar(v2db, [y.satir(1, ilce="Osmangazi", mahalle=m["ad"])])
    r = conn.execute("SELECT durum, obek_id, obek_elle_id FROM is_emri").fetchone()
    assert tuple(r) == ("bekliyor", oid, None)


def test_ad_var_409(v2db, conn, kim):
    op = kim("operasyon")
    oid, surum = _yeni_obek(conn, op, "Deneme Görükle Batı")
    for ad in ("DENEME GÖRÜKLE BATI", "deneme gorukle bati"):              # Türkçe harf / büyük-küçük duyarsız
        with pytest.raises(V2Hata) as e:
            obek.olustur(conn, ad, op, obek.surum(conn))
        assert e.value.kod == "ad_var" and e.value.durum == 409
    b = obek.olustur(conn, "Deneme İkinci", op, obek.surum(conn))
    with pytest.raises(V2Hata) as e:
        obek.guncelle(conn, b["obek"]["id"], op, b["surum"], ad="Deneme Görükle Batı")       # sessiz birleştirme yok
    assert e.value.kod == "ad_var"


def test_sil_geri_al(v2db, conn, kim, saat):
    op = kim("operasyon")
    (m,) = _obeksiz(conn, 1)
    y.aktar(v2db, [y.satir(1, mahalle=m["ad"])])
    oid, surum = _yeni_obek(conn, op, "Deneme Silinecek")
    s = obek.mahalle_ekle(conn, oid, op, surum, mahalle_idler=[m["id"]])
    assert conn.execute("SELECT durum FROM is_emri").fetchone()[0] == "bekliyor"
    s = obek.sil(conn, oid, op, s["surum"])
    assert s["obeksiz_kalan_is"] >= 1 and oid not in [x["id"] for x in s["obekler"]]
    assert tuple(conn.execute("SELECT durum, triyaj_nedeni FROM is_emri").fetchone()) == ("triyaj", "obeksiz")
    with pytest.raises(V2Hata) as e:
        obek.geri_al(conn, s["geri_al_olay_id"], kim("yonetici"), s["surum"])      # başkası geri alamaz
    assert e.value.kod == "geri_alinamaz"
    g = obek.geri_al(conn, s["geri_al_olay_id"], op, s["surum"])
    assert oid in [x["id"] for x in g["obekler"]]
    assert tuple(conn.execute("SELECT durum, obek_id FROM is_emri").fetchone()) == ("bekliyor", oid)
    # 10 dk sonra geri alınamaz
    s = obek.sil(conn, oid, op, g["surum"])
    saat.ilerlet(minutes=11)
    with pytest.raises(V2Hata) as e:
        obek.geri_al(conn, s["geri_al_olay_id"], op, s["surum"])
    assert e.value.kod == "sure_doldu"
    # silinen öbeğin adı serbest kalır
    assert obek.olustur(conn, "Deneme Silinecek", op, obek.surum(conn))["obek"]["ad"] == "Deneme Silinecek"


def test_json_aktarim_14_120_bul_ayni(v2_ortam, v2db, conn):
    """Göç v3: öbekler.json (kopyası) BİREBİR aktarıldı; her ref için DB'nin öbeği = bugünkü JSON motorunun öbeği.

    Sayılar dosyadan okunur (30.09'da 14 öbek, 120 ref); kullanıcı öbek eklerse test yine geçerlidir."""
    from operasyon import is_emri as ie
    veri = json.loads(v2_ortam["obek_json"].read_text(encoding="utf-8"))
    tanimlar = veri["obekler"]
    assert conn.execute("SELECT COUNT(*) FROM obek").fetchone()[0] == len(tanimlar)
    olay = conn.execute("SELECT veri FROM obek_olay WHERE tur='json_aktarim'").fetchone()
    catisma = json.loads(olay[0])["sonra"]["catisma"] if olay else []
    ref_sayisi = sum(len(t["mahalleler"]) for t in tanimlar)
    assert conn.execute("SELECT COUNT(*) FROM obek_mahalle").fetchone()[0] + len(catisma) == ref_sayisi
    motor = ie.Obekler(tanimlar=tanimlar)
    motor._derle()
    adlar = {r[0]: r[1] for r in conn.execute("SELECT id, ad FROM obek")}
    h = obek.harita(conn)
    ilce_h = sozluk.ilce_haritasi(conn)
    fark = 0
    for t in tanimlar:
        for ref in t["mahalleler"]:
            p = [x.strip() for x in ref.split("/")]
            p = ["", *p] if len(p) == 2 else p
            c = sozluk.ilce_coz(ilce_h, p[0], p[1])
            mk = None if p[2] == "*" else ie.anahtar(p[2])
            fark += motor.bul(p[0] or c[2], p[1], None if p[2] == "*" else p[2]) != adlar.get(
                obek.haritadan(h, c[0], c[1], mk))
    assert fark == 0 and obek.surum(conn) >= 1


def test_obekler_json_yazilmaz(v2_ortam, v2db, conn, kim):
    """Öbek düzenlemek JSON'a hiç yazmaz (kaynak DB); okunabilir ayna OPERASYON_VERI altına yazılır."""
    def ozet(yol):
        return hashlib.sha256(yol.read_bytes()).hexdigest() if yol.exists() else None
    import os
    from pathlib import Path
    kopya = Path(os.environ["OPERASYON_OBEK"])
    once = (ozet(GERCEK_OBEK), ozet(kopya))
    op = kim("operasyon")
    oid, surum = _yeni_obek(conn, op)
    (m,) = _obeksiz(conn, 1)
    s = obek.mahalle_ekle(conn, oid, op, surum, mahalle_idler=[m["id"]])
    obek.guncelle(conn, oid, op, s["surum"], ad="Deneme Yeni Ad")
    assert (ozet(GERCEK_OBEK), ozet(kopya)) == once
    aynalar = sorted((Path(os.environ["OPERASYON_VERI"]) / "obek_yedek").glob("obekler-2*.json"))
    assert aynalar and "Deneme Yeni Ad" in aynalar[-1].read_text(encoding="utf-8")


def test_benzer_ad_ve_esad(v2db, conn, kim):
    op = kim("operasyon")
    gor = next(m for m in sozluk.ara(conn, "gorukle", "Bursa", "Nilüfer")["mahalleler"] if m["ad"] == "Görükle")
    with pytest.raises(V2Hata) as e:
        sozluk.ekle(conn, "Bursa", "Nilüfer", "Görüklee", op)
    assert e.value.kod == "benzer_var" and e.value.ek["oneriler"][0]["ad"] == "Görükle"
    with pytest.raises(V2Hata) as e:
        sozluk.ekle(conn, "Bursa", "Nilüfer", "GÖRÜKLE", op)
    assert e.value.kod == "var"
    with pytest.raises(V2Hata) as e:
        sozluk.ekle(conn, "İzmir", "Karşıyaka", "Bostanlı", op)
    assert e.value.kod == "ilce_yok"
    # eşad: "Görüklee" yazımı sonraki raporlarda Görükle'ye düşer
    sozluk.esad_ekle(conn, "Bursa", "Nilüfer", "Görüklee", gor["id"], op)
    conn.commit()
    y.aktar(v2db, [y.satir(1, adres="DENEME APT. Görüklee Mh. Test Sk. No:1 Nilüfer")])
    r = conn.execute("SELECT mahalle, obek_id, triyaj_nedeni FROM is_emri").fetchone()
    assert r["mahalle"] == "Görükle" and r["obek_id"] == gor["obek"]["id"] and r["triyaj_nedeni"] is None


def test_obek_surum_409(v2db, conn, kim):
    op, yon = kim("operasyon"), kim("yonetici")
    eski = obek.surum(conn)
    obek.olustur(conn, "Deneme Eşzamanlı 1", op, eski)
    with pytest.raises(V2Hata) as e:
        obek.olustur(conn, "Deneme Eşzamanlı 2", yon, eski)                # aynı eski sürümle ikinci yazar
    assert e.value.kod == "guncel_degil" and e.value.durum == 409
    assert e.value.ek["surum"] == eski + 1 and e.value.ek["obekler"]
