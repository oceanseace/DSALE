"""Paketler arası sözleşme kilitleri (entegrasyon, 30.09): WP-A sunucusu ↔ WP-B motoru ↔ WP-E arayüzü.

* /api/ben ortak alanı ``kutlamalar`` (EK-6; arayüz ``ozet.kutlamalar`` okur, ayar kapatılabilir).
* Geçiş dönemi: eski "İş emirleri" ekranı dosyası yerindeyken eski /api/is-emri uçları çalışır ve yalnız
  iş yükleyebilen görevlere açıktır (WP-C yeni ekranı getirip dosyayı kaldırınca 410 ``yenilendi``).
"""
from __future__ import annotations

import pytest

import yollar

ESKI_EKRAN = yollar.ARAYUZ / "src" / "yonetici" / "ekran" / "IsEmirleri.tsx"
YONETIM_GIRIS = yollar.ARAYUZ / "src" / "yonetici" / "index.tsx"


def test_ben_kutlamalar_ayardan(istemci, kisi, conn):
    _kid, h = kisi("operasyon")
    assert istemci.get("/api/ben", headers=h).json()["kutlamalar"] is True
    conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('kutlamalar','kapali') "
                 "ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger")
    conn.commit()
    assert istemci.get("/api/ben", headers=h).json()["kutlamalar"] is False


@pytest.mark.skipif(not ESKI_EKRAN.exists(), reason="eski ekran kaldırıldı (WP-C): uçlar 410")
def test_eski_is_emri_ekrani_gecis_doneminde_calisir(istemci, kisi):
    """Eski ekran dururken uçları açık ve arayüz onu İşler yerinde gösteriyor (ikisi birlikte kalkar)."""
    assert "./ekran/IsEmirleri.tsx" in YONETIM_GIRIS.read_text(encoding="utf-8")
    for gorev, beklenen in (("operasyon", 200), ("yonetici", 200), ("teknik", 403), ("satisci", 403)):
        _kid, h = kisi(gorev, bolge=1 if gorev == "satisci" else None)
        y = istemci.get("/api/is-emri", headers=h)
        assert y.status_code == beklenen, (gorev, y.status_code)
    assert istemci.get("/api/is-emri").status_code == 401
