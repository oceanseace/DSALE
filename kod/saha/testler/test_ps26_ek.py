"""Ticket fotoğrafları (Ek-8): ticket'ı GÖREBİLEN görür, yükleme sınırları (10 MB, yalnız JPEG/PNG), etkisizlik,
küçük resim, disk yolu. Fotoğraflar test veritabanı kopyasının yanındaki ``ek/`` klasörüne yazılır.
"""
from __future__ import annotations

import hashlib

import pytest

from saha import ayarlar, ek_dosya, ticket

from .test_ps26_yardim import binalar, resim

JPEG = "image/jpeg"


@pytest.fixture
def t_bina(conn):
    """Bölge 1'deki bir binada ticket + binasız bir ticket."""
    b = binalar(conn, 1, bolge=1)[0]
    tid, _ = ticket.olustur(conn, {"konu": "SİNYAL", "bina_serial": b["bina_serial"]}, None)
    binasiz, _ = ticket.olustur(conn, {"konu": "EK SP", "site": "Binasız site"}, None)
    conn.commit()
    return {"id": tid, "binasiz": binasiz, "bina": b["bina_serial"]}


def _yukle(istemci, baslik, tid, icerik: bytes, ad: str = "foto.jpg"):
    """Arayüz gibi: ham gövde, ad ``encodeURIComponent`` ile (başlıkta Türkçe harf taşınamaz)."""
    from urllib.parse import quote

    return istemci.post(f"/api/ticket/{tid}/ek", headers={**baslik, "Content-Type": "application/octet-stream",
                                                         "X-Dosya-Adi": quote(ad)}, content=icerik)


def _teknik_is(conn, kid: int, bina: str, durum: str = "atandi") -> None:
    z = ayarlar.zaman_metni()
    conn.execute(
        "INSERT INTO is_emri (is_no, kaynak, task_adi, serit, durum, durum_zamani, atanan_id, bina_serial, "
        "acilis, son24, ilk_gorulme, gorulme_zamani, guncelleme) VALUES ('412300001','boss','Bağlantı Problemi',"
        "'SAHA',?,?,?,?,?,?,?,?,?)", (durum, z, kid, bina, z, z, z, z, z))
    conn.commit()


# ============================================================ yükleme, liste, gösterme
def test_yukle_listele_tam_ve_kucuk_resim(istemci, kisi, t_bina):
    _, op = kisi("operasyon")
    foto = resim("JPEG", boyut=(1600, 1200))
    y = _yukle(istemci, op, t_bina["id"], foto, "IMG 2031.jpeg")
    assert y.status_code == 201, y.text
    ek = y.json()["ek"]
    assert ek["dosya_adi"] == "IMG 2031.jpg" and ek["boyut"] == len(foto) and ek["tur"] == "jpg"
    # Aynı fotoğraf ikinci kez: yeni kayıt yok.
    y = _yukle(istemci, op, t_bina["id"], foto)
    assert y.status_code == 200 and y.json()["zaten_vardi"] is True
    liste = istemci.get(f"/api/ticket/{t_bina['id']}/ek", headers=op).json()
    assert liste["toplam"] == 1 and liste["yukleyebilir"] is True and liste["en_buyuk_bayt"] == 10 * 1024 * 1024
    tam = istemci.get(ek["tam"], headers=op)
    assert tam.status_code == 200 and tam.headers["content-type"] == JPEG and tam.content == foto
    kucuk = istemci.get(ek["kucuk"], headers=op)
    assert kucuk.status_code == 200 and kucuk.headers["content-type"] == JPEG
    assert len(kucuk.content) < len(foto)
    from PIL import Image
    import io

    assert max(Image.open(io.BytesIO(kucuk.content)).size) <= ek_dosya.KUCUK_PX
    # Küçük resim diske bir kez yazılır, ikinci istekte oradan gelir.
    assert ek_dosya.kucuk_yolu(t_bina["id"], hashlib.sha256(foto).hexdigest()).exists()


def test_png_ve_multipart(istemci, kisi, t_bina):
    _, op = kisi("operasyon")
    y = istemci.post(f"/api/ticket/{t_bina['id']}/ek", headers=op,
                     files={"dosya": ("ekran.png", resim("PNG"), "image/png")})
    assert y.status_code == 201 and y.json()["ek"]["tur"] == "png"
    tam = istemci.get(y.json()["ek"]["tam"], headers=op)
    assert tam.headers["content-type"] == "image/png"


# ============================================================ sınırlar
def test_on_mb_siniri(istemci, kisi, t_bina, conn):
    _, op = kisi("operasyon")
    buyuk = b"\xff\xd8\xff\xe0" + b"0" * (ek_dosya.EN_BUYUK - 3)          # 10 MB + 1 bayt
    y = _yukle(istemci, op, t_bina["id"], buyuk)
    assert y.status_code == 413 and y.json()["kod"] == "dosya_buyuk"
    y = istemci.post(f"/api/ticket/{t_bina['id']}/ek", headers=op, files={"dosya": ("b.jpg", buyuk, JPEG)})
    assert y.status_code == 413
    assert conn.execute("SELECT COUNT(*) FROM ticket_ek").fetchone()[0] == 0


@pytest.mark.parametrize("icerik,kod", [
    (b"GIF89a" + b"\x00" * 64, "dosya_turu"),
    (b"%PDF-1.7\n" + b"\x00" * 64, "dosya_turu"),
    (b"<html><script>alert(1)</script></html>", "dosya_turu"),
    (b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64, "dosya_turu"),           # HEIC: pillow_heif yoksa açıklamalı red
    (b"\xff\xd8\xff\xe0" + b"bozuk" * 20, "dosya_bozuk"),                 # JPEG gibi başlıyor ama resim değil
    (b"", "dosya_yok"),
])
def test_yalniz_jpeg_png(istemci, kisi, t_bina, conn, icerik, kod):
    _, op = kisi("operasyon")
    y = _yukle(istemci, op, t_bina["id"], icerik, "x.jpg")
    assert y.status_code in (400, 415, 422), y.text
    assert y.json()["kod"] == kod
    assert conn.execute("SELECT COUNT(*) FROM ticket_ek").fetchone()[0] == 0
    assert not ek_dosya.ticket_dizini(t_bina["id"]).exists() or not any(
        p for p in ek_dosya.ticket_dizini(t_bina["id"]).rglob("*") if p.is_file())


def test_heic_uyarisi_turkce():
    heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64
    try:
        import pillow_heif  # noqa: F401
    except ImportError:
        with pytest.raises(ek_dosya.EkHatasi) as h:
            ek_dosya.hazirla(heic, "IMG.HEIC")
        assert "HEIC" in h.value.mesaj and h.value.durum == 415


def test_disk_adi_icerikten_kullanici_adi_yalniz_gorunur(conn, t_bina):
    foto = resim()
    kayit, yeni = ek_dosya.ekle(conn, t_bina["id"], foto, "../../../gizli/..\\x<>.jpeg")
    conn.commit()
    assert yeni and kayit["dosya_adi"] == "x.jpg"
    yol = ek_dosya.dosya_yolu(t_bina["id"], hashlib.sha256(foto).hexdigest(), kayit["dosya_adi"])
    assert yol.exists() and yol.parent == ek_dosya.ticket_dizini(t_bina["id"])
    assert yol.name == hashlib.sha256(foto).hexdigest() + ".jpg"
    # Kök: SAHA_DB kopyasının yanı (repodaki saha/ek'e değil).
    from saha import db

    assert ek_dosya.ek_kok() == db.db_yolu().parent / "ek"


# ============================================================ yetki: ticket'ı görebilen görür
def test_ticketi_gorebilen_gorur(istemci, kisi, t_bina, conn):
    _, yon = kisi("yonetici")
    y = _yukle(istemci, yon, t_bina["id"], resim())
    ek = y.json()["ek"]
    liste = f"/api/ticket/{t_bina['id']}/ek"

    # Satış: binası kendi bölgesindeyse görür (bina kartındaki ticket'ı gibi), yükleyemez.
    _, satis1 = kisi("satisci", bolge=1)
    _, satis2 = kisi("satisci", bolge=2)
    assert istemci.get(liste, headers=satis1).status_code == 200
    assert istemci.get(liste, headers=satis1).json()["yukleyebilir"] is False
    assert istemci.get(ek["kucuk"], headers=satis1).status_code == 200
    assert _yukle(istemci, satis1, t_bina["id"], resim(renk=(1, 2, 3))).status_code == 403
    for yol in (liste, ek["tam"], ek["kucuk"]):
        y = istemci.get(yol, headers=satis2)
        assert y.status_code == 404 and y.json()["kod"] == "ticket_yok"      # başka bölge: varlığı sızmaz

    # Teknik: yalnız kendisine atanmış AÇIK işin binasındaki ticket; orada sahadan yükleyebilir.
    kid, tek = kisi("teknik")
    assert istemci.get(liste, headers=tek).status_code == 404
    assert _yukle(istemci, tek, t_bina["id"], resim(renk=(9, 9, 9))).status_code == 404
    _teknik_is(conn, kid, t_bina["bina"])
    assert istemci.get(liste, headers=tek).json()["yukleyebilir"] is True
    assert _yukle(istemci, tek, t_bina["id"], resim(renk=(9, 9, 9))).status_code == 201
    conn.execute("UPDATE is_emri SET durum='cozuldu' WHERE is_no='412300001'")
    conn.commit()
    assert istemci.get(ek["tam"], headers=tek).status_code == 404

    # Binasız ticket: yalnız ticket defteri görür.
    _, op = kisi("operasyon")
    assert istemci.get(f"/api/ticket/{t_bina['binasiz']}/ek", headers=op).status_code == 200
    assert istemci.get(f"/api/ticket/{t_bina['binasiz']}/ek", headers=satis1).status_code == 404
    # Jetonsuz 401; olmayan ticket 404.
    assert istemci.get(liste).status_code == 401
    assert istemci.get("/api/ticket/999999/ek", headers=op).status_code == 404


def test_ek_baska_ticketin_adresinden_alinamaz(istemci, kisi, t_bina):
    _, op = kisi("operasyon")
    ek = _yukle(istemci, op, t_bina["id"], resim()).json()["ek"]
    y = istemci.get(f"/api/ticket/{t_bina['binasiz']}/ek/{ek['id']}", headers=op)
    assert y.status_code == 404 and y.json()["kod"] == "ek_yok"
    assert istemci.get(f"/api/ticket/{t_bina['binasiz']}/ek/{ek['id']}/kucuk", headers=op).status_code == 404


def test_yukleme_yonetim_kaydina_yazilir_kisisel_veri_yok(istemci, kisi, t_bina, conn):
    _, op = kisi("operasyon")
    _yukle(istemci, op, t_bina["id"], resim(), "Ayşe Hanım evi.jpg")
    r = conn.execute("SELECT eylem, hedef, ozet FROM yonetim_kaydi WHERE eylem='ticket_ek'").fetchone()
    assert r["hedef"] == str(t_bina["id"]) and "Ayşe" not in (r["ozet"] or "")
