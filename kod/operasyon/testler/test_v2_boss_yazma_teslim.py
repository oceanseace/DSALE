"""BOSS'a yazmanın teslimi (09.10 incelemesi: 344 'hata' atamasının 306'sı "Sonuç gelmedi", ≥ 209'u BOSS'ta yazılmıştı).

- Kanca isteği kuyruğuna alınca "alindi" der; kancaya hiç ulaşmayan (sekme kapalı / köprü yok) kayıt artık 5 dk sonra
  belirsiz hata olmaz: 90 sn sonra 'bekliyor'a döner ve yeniden verilir. Eski kanca (hiç "alindi" demeyen) için eski
  davranış sürer (çift yazma olmasın).
- Sonucu gelmemiş atama/askı, BOSS'un kendi görüntüsünde yapılmış görünüyorsa (ekip + dilim / SUSPENDED) ✓ olur.
BOSS'a hiçbir istek gönderilmez.
"""
from __future__ import annotations

import datetime as dt
import json

from operasyon.testler.test_v2_boss_yazma import _ata, _gorev, _temiz, _yazilacaklar, ortam  # noqa: F401
from operasyon.v2 import boss_yazma, zaman


def _eskit(conn, kayit_id: int, sn: int = 120) -> None:
    conn.execute("UPDATE boss_yazma SET guncelleme=? WHERE id=?",
                 (zaman.metin(zaman.simdi() - dt.timedelta(seconds=sn)), kayit_id))
    conn.commit()


def _kayit(conn, kayit_id: int):
    d, s = conn.execute("SELECT durum, sonuc FROM boss_yazma WHERE id=?", (kayit_id,)).fetchone()
    return d, json.loads(s) if s else {}


def _not_istekleri(istemci, ortam):
    for no in ("400000001", "400000002"):
        r = istemci.post(f"/api/isler/{no}/not", headers=ortam["op"], json={"metin": f"not {no}"})
        assert r.status_code == 201, r.text
    ist = [i for i in _yazilacaklar(istemci, ortam["ek"])["istekler"] if i["tur"] == "not"]
    assert len(ist) == 2 and all(i["yaz"] for i in ist)
    return ist


def test_alindi_denmeyen_kayit_yeniden_verilir_alinan_bekler(istemci, conn, ortam):
    a, b = _not_istekleri(istemci, ortam)
    ia, ib = a["kayitlar"][0], b["kayitlar"][0]
    assert _kayit(conn, ia)[0] == "gonderiliyor" and _kayit(conn, ia)[1].get("verildi")
    r = istemci.post("/api/boss/yazma-sonucu", headers=ortam["ek"],
                     json={"istek_id": a["istek_id"], "kayitlar": [ia], "durum": "alindi"})
    assert r.status_code == 200 and r.json()["guncellenen"] == 1
    d, s = _kayit(conn, ia)
    assert d == "gonderiliyor" and s.get("alindi")                 # durum değişmez; yalnız onay
    _eskit(conn, ia)
    _eskit(conn, ib)
    yeni = [i for i in _yazilacaklar(istemci, ortam["ek"])["istekler"] if i["tur"] == "not"]
    assert [i["kayitlar"] for i in yeni] == [[ib]], "kancaya ulaşmayan kayıt yeniden verilir; alınan verilmez"
    assert _kayit(conn, ia)[0] == "gonderiliyor"
    assert _kayit(conn, ib)[0] == "gonderiliyor"


def test_eski_kanca_alindi_demezse_geri_donus_yok(istemci, conn, ortam):
    a, b = _not_istekleri(istemci, ortam)
    _eskit(conn, a["kayitlar"][0])
    yeni = [i for i in _yazilacaklar(istemci, ortam["ek"])["istekler"] if i["tur"] == "not"]
    assert yeni == [], "onay görülmemişse (eski kanca) kayıt yeniden verilmez — çift yazma olmasın"
    assert _kayit(conn, a["kayitlar"][0])[0] == "gonderiliyor"


def test_sekme_yokken_ertelenen_kayit_bekliyora_doner(istemci, conn, ortam):
    a, _b = _not_istekleri(istemci, ortam)
    r = istemci.post("/api/boss/yazma-sonucu", headers=ortam["ek"], json={
        "istek_id": a["istek_id"], "kayitlar": a["kayitlar"], "durum": "ertelendi", "hata": "sekme_yok"})
    assert r.json()["guncellenen"] == 1
    assert _kayit(conn, a["kayitlar"][0])[0] == "bekliyor"


def _belirsiz(conn, kayit_id: int) -> None:
    conn.execute("UPDATE boss_yazma SET durum='hata', sonuc=? WHERE id=?",
                 (json.dumps({"durum": "hata", "hata": "sonuc_gelmedi", "belirsiz": True}), kayit_id))
    conn.commit()


def test_boss_goruntusu_sonucu_gelmeyen_atamayi_dogrular(istemci, conn, ortam):
    _ata(istemci, ortam, "400000001")
    _ata(istemci, ortam, "400000002")
    ist = [i for i in _yazilacaklar(istemci, ortam["ek"])["istekler"] if i["tur"] == "atama"]
    idler = {conn.execute("SELECT is_no FROM boss_yazma WHERE id=?", (k,)).fetchone()[0]: k
             for i in ist for k in i["kayitlar"]}
    for k in idler.values():
        _belirsiz(conn, k)
    # BOSS: 1 aynı ekip + aynı dilim (yazılmış), 2 aynı ekip ama başka dilim (bilinmez → dokunulmaz)
    g1 = _gorev(1, ekip="DENEME EKIBI", randevu_bas="2026-10-01 14:00:00", randevu_bit="2026-10-01 16:00:00",
                durum="Randevu alındı")
    g2 = _gorev(2, ekip="DENEME EKIBI", randevu_bas="2026-10-02 10:00:00", randevu_bit="2026-10-02 12:00:00",
                durum="Randevu alındı")
    r = istemci.post("/api/boss/esitle", headers=ortam["ek"], json={"gorevler": [g1, g2], "tam": False})
    assert r.status_code == 200, r.text
    d1, s1 = _kayit(conn, idler["400000001"])
    assert d1 == "gonderildi" and s1["dogrulama"] == "boss_goruntusu"
    assert _kayit(conn, idler["400000002"])[0] == "hata"
    # çekmece/özet hâli: ✓
    h = boss_yazma.atama_durumlari(conn, ["400000001", "400000002"])
    assert h["400000001"]["durum"] == "tamam" and h["400000002"]["durum"] == "hata"


def test_boss_goruntusu_ekip_bossa_dogrulamaz(istemci, conn, ortam):
    _ata(istemci, ortam, "400000001")
    ist = [i for i in _yazilacaklar(istemci, ortam["ek"])["istekler"] if i["tur"] == "atama"]
    k = ist[0]["kayitlar"][0]
    _belirsiz(conn, k)
    r = istemci.post("/api/boss/esitle", headers=ortam["ek"], json={"gorevler": [_gorev(1)], "tam": False})
    assert r.status_code == 200, r.text
    assert _kayit(conn, k)[0] == "hata"
