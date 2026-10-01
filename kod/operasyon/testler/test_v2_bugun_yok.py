"""Spec §6.10 "Bugün çalışmıyor": yazma ucu + GET /api/isler/teknikler.bugun_yok (entegrasyon; WP-E isteği)."""
from __future__ import annotations

import json


def test_bugun_yok_yazilir_okunur_geri_alinir(istemci, jeton, conn, kisi):
    h = jeton(kisi["operasyon"])
    tid = kisi["teknik1"]
    y = istemci.put(f"/api/isler/teknikler/{tid}/bugun-yok", headers=h, json={"tarih": "2026-10-01", "yok": True})
    assert y.status_code == 200, y.text
    assert y.json() == {"teknik_id": tid, "tarih": "2026-10-01", "bugun_yok": True}
    liste = istemci.get("/api/isler/teknikler?tarih=2026-10-01", headers=h).json()
    assert next(t for t in liste if t["id"] == tid)["bugun_yok"] is True
    assert not next(t for t in liste if t["id"] == kisi["teknik2"])["bugun_yok"]
    # Yalnız o gün: ertesi gün anahtar boştur
    ertesi = istemci.get("/api/isler/teknikler?tarih=2026-10-02", headers=h).json()
    assert not next(t for t in ertesi if t["id"] == tid)["bugun_yok"]
    # İki kez işaretlemek çift kayıt üretmez; kaldırınca listeden çıkar
    istemci.put(f"/api/isler/teknikler/{tid}/bugun-yok", headers=h, json={"tarih": "2026-10-01", "yok": True})
    deger = conn.execute("SELECT deger FROM ayar WHERE anahtar='bugun_yok_2026-10-01'").fetchone()[0]
    assert json.loads(deger) == [tid]
    y = istemci.put(f"/api/isler/teknikler/{tid}/bugun-yok", headers=h, json={"tarih": "2026-10-01", "yok": False})
    assert y.json()["bugun_yok"] is False
    liste = istemci.get("/api/isler/teknikler?tarih=2026-10-01", headers=h).json()
    assert not next(t for t in liste if t["id"] == tid)["bugun_yok"]
    # Yönetim kaydına düşer (kişisel veri yok: yalnız id + tarih)
    assert conn.execute("SELECT COUNT(*) FROM yonetim_kaydi WHERE eylem='teknik_bugun_yok'").fetchone()[0] == 3


def test_bugun_yok_dogrulama_ve_yetki(istemci, jeton, kisi):
    h = jeton(kisi["operasyon"])
    y = istemci.put(f"/api/isler/teknikler/{kisi['operasyon']}/bugun-yok", headers=h, json={"yok": True})
    assert y.status_code == 422 and y.json()["kod"] == "teknik_gecersiz"
    y = istemci.put(f"/api/isler/teknikler/{kisi['teknik1']}/bugun-yok", headers=h, json={"tarih": "01.10.2026", "yok": True})
    assert y.status_code == 422 and y.json()["kod"] == "alan_eksik"
    for ad in ("teknik1", "satis"):
        y = istemci.put(f"/api/isler/teknikler/{kisi['teknik1']}/bugun-yok", headers=jeton(kisi[ad]), json={"yok": True})
        assert y.status_code == 403 and y.json()["kod"] == "yasak"
