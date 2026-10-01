"""Sentetik BOSS "Teknik Task Detay Raporu" üretici (adlar/numaralar uydurma; mahalle adları gerçek coğrafya)."""
from __future__ import annotations

import io

import pandas as pd

SUTUNLAR = ["Bayi", "Müşteri No", "Müşteri Adı", "Task No", "Task Adı", "Ekip", "Adres", "Satış Kanalı", "İl", "İlçe",
            "Task Başlangıç Tarihi", "Task Durumu", "Randevu Durumu", "Randevu Başlangıç Tarihi",
            "Randevu Bitiş Tarihi", "Askıya Alınma Nedeni", "SL", "SL Süresi(Sa)", "Son Açıklama", "Lokasyon",
            "Teknik Ekip Konum Paylaşma Tarihi", "Teknik Ekip İşe Başlama Tarihi", "Merkeze Gönder Statüsü"]


def satir(no: int | str, *, task="Bağlantı Problemi", mahalle="Görükle", ilce="Nilüfer", il="Bursa",
          adres: str | None = None, baslangic="2026-09-30 09:00:00", durum="Açık", ekip=None, lokasyon=None,
          musteri_no=None, kanal="GLOBAL CC", aski=None, randevu=None, **ek) -> dict:
    no = str(no) if isinstance(no, str) else f"{400000000 + int(no)}"
    s = {
        "Bayi": "DENEME BAYI", "Müşteri No": musteri_no or f"9{no[-8:]}", "Müşteri Adı": "Deneme Müşteri",
        "Task No": no, "Task Adı": task, "Ekip": ekip, "Adres": adres or f"DENEME APT. {mahalle} Mh. Test Sk. No:{no[-3:]} {ilce}",
        "Satış Kanalı": kanal, "İl": il, "İlçe": ilce, "Task Başlangıç Tarihi": baslangic, "Task Durumu": durum,
        "Randevu Durumu": "Randevulu" if randevu else "Randevusuz",
        "Randevu Başlangıç Tarihi": randevu[0] if randevu else None,
        "Randevu Bitiş Tarihi": randevu[1] if randevu else None,
        "Askıya Alınma Nedeni": aski, "SL": None, "SL Süresi(Sa)": None, "Son Açıklama": None, "Lokasyon": lokasyon,
        "Teknik Ekip Konum Paylaşma Tarihi": None, "Teknik Ekip İşe Başlama Tarihi": None, "Merkeze Gönder Statüsü": None,
    }
    s.update(ek)
    return s


def xlsx(satirlar: list[dict], sayfa: str = "Task Detail Report") -> bytes:
    df = pd.DataFrame(satirlar, columns=SUTUNLAR)
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        pd.DataFrame({"Özet": ["pivot"]}).to_excel(w, index=False, sheet_name="Sayfa1")
        df.to_excel(w, index=False, sheet_name=sayfa)
    return b.getvalue()


def standart(n: int = 12, baslangic="2026-09-30 09:00:00") -> list[dict]:
    """Görükle/Dumlupınar/Özlüce mahallelerinde n iş. Görükle ve Dumlupınar kullanıcının öbeklerindedir;
    Özlüce hiçbir öbekte değildir → o işler Kontrol'e (triyaj, 'obeksiz') düşer."""
    mh = ["Görükle", "Dumlupınar", "Özlüce"]
    return [satir(i, mahalle=mh[i % 3], task=["Bağlantı Problemi", "Modem Değişikliği", "TV+ Arıza"][i % 3],
                  baslangic=baslangic) for i in range(1, n + 1)]


def fabrika(yol):
    from saha import db
    return lambda: db.baglan(yol)


def aktar(yol, satirlar, *, dosya_zamani=None, k=None, ad="rapor.xlsx", veri: bytes | None = None):
    from operasyon.v2 import aktarim
    return aktarim.aktar(fabrika(yol), veri if veri is not None else xlsx(satirlar), ad, dosya_zamani, k)


def db_ozeti(conn) -> tuple:
    """İş tablolarının içerik özeti (etkisizlik testleri için)."""
    import hashlib
    h = hashlib.sha256()
    for tablo in ("is_emri", "is_emri_olay", "is_aski", "obek", "obek_mahalle", "mahalle"):
        for r in conn.execute(f"SELECT * FROM {tablo} ORDER BY rowid"):
            h.update(repr(tuple(r)).encode())
    n = conn.execute("SELECT COUNT(*) FROM ie_aktarim").fetchone()[0]
    return h.hexdigest(), n


def lokasyon_kacan(conn) -> int:
    """Raporda Location Id'si olup binası AYNI ilçede bulunduğu hâlde bina konumu almamış iş sayısı (0 olmalı).

    Gerçek raporda Location Id'nin binası başka ilçedeyse eşleşme bilerek kullanılmaz (is_emri.hazirla:
    "Lokasyon/site başka ilçede — konumu kullanılmadı"); sözlükte hiç olmayan yeni bina da eşleşmez.
    Bunlar veri farkıdır, hata değildir; yalnız aynı ilçedeki kaçan eşleşme hatadır.
    """
    from operasyon import is_emri as ie
    kacan = 0
    for lok, il_k, ilce_k in conn.execute("SELECT lokasyon, il_k, ilce_k FROM is_emri "
                                          "WHERE lokasyon IS NOT NULL AND lokasyon <> '' AND konum_kaynak IS NOT 'bina'"):
        adaylar = ie.lokasyon_adaylari(lok)
        if not adaylar:
            continue
        for il, ilce in conn.execute(f"SELECT il, ilce FROM bina WHERE location_id IN ({','.join('?' * len(adaylar))})",
                                     adaylar):
            if ie.ilce_anahtari(il or "", ilce or "") == (il_k, ilce_k):
                kacan += 1
                break
    return kacan
