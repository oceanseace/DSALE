"""Excel'deki TICKET sayfasını ticket defterine aktarır (bir kez; tekrar çalıştırmak güvenli).

    .venv/Scripts/python.exe -m saha.ticket_aktar                     # PS26/data.xlsx → saha/saha.db
    .venv/Scripts/python.exe -m saha.ticket_aktar --kuru              # yazmadan ne olacağını göster
    .venv/Scripts/python.exe -m saha.ticket_aktar --dosya D:/x.xlsx --db kopya.db

Her satır için bir "aktarım anahtarı" üretilir: YALNIZ satır açılırken yazılan ve sonra
değişmeyen alanlardan (başlangıç tarihi + lokasyon + konu; lokasyonsuz satırda müşteri).
Ticket numarası, durum ve detay bilerek anahtarda YOK: Excel kullanılmaya devam ederken
bir satıra sonradan OneDesk numarası yazılır, durumu "ÇÖZÜLDÜ" olur — bu yeni bir ticket
değildir. Script tekrar çalışınca:
  * yeni satır → eklenir,
  * Excel'de numarası/durumu/detayı değişmiş satır → ticket güncellenir ve geçmişe
    "Excel'den güncellendi" yazılır (ticket uygulamada henüz elle değiştirilmediyse),
  * uygulamada değiştirilmiş ticket'a DOKUNULMAZ (artık kaynak uygulamadır), raporlanır.
Kaç kez çalıştırılırsa çalıştırılsın hiçbir ticket iki kez yazılmaz.

Lokasyon → bina eşleşmesi: birebir · 8 haneye sıfırlı (00145672) · baştaki sıfırsız ·
sondaki "-1" eki atılmış. Bağlanamayan satır yine aktarılır (binasız), rapor edilir.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import sys
from collections import Counter
from pathlib import Path

import yollar

from . import ayarlar, db, ticket

VARSAYILAN_DOSYA = yollar.PS26 / "data.xlsx"
SAYFA = "TICKET"


def _metin(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "nat"):
        return ""
    return s[:-2] if s.endswith(".0") and s[:-2].isdigit() else s


def satirlari_oku(dosya: Path, sayfa: str = SAYFA) -> list[dict]:
    import pandas as pd

    d = pd.read_excel(dosya, sheet_name=sayfa, dtype=str)
    d.columns = [str(c).strip() for c in d.columns]
    ekler = [c for c in d.columns if c.lower().startswith("unnamed")]
    satirlar = []
    for i, r in enumerate(d.to_dict("records")):
        kayit = {k: _metin(r.get(k)) for k in ("Ticket", "Baslangic", "Lokasyon", "Site", "Konu", "Durum",
                                                 "Musteri", "Kanal", "Detay")}
        # Başlıksız sütunlara yazılmış notlar da kaybolmasın (ör. "13257596 PORT ÇEKİLEREK KURULDU")
        ek = " · ".join(_metin(r.get(c)) for c in ekler if _metin(r.get(c)))
        kayit["_ek"] = ek
        kayit["_satir"] = i + 2          # Excel satır numarası (başlık 1. satır)
        if not any(kayit[k] for k in ("Ticket", "Lokasyon", "Site", "Musteri", "Detay")):
            continue                     # tamamen boş satır
        satirlar.append(kayit)
    return satirlar


def _anahtar(r: dict) -> str:
    alanlar = ("Baslangic", "Lokasyon", "Konu") if r["Lokasyon"] else ("Baslangic", "Konu", "Musteri", "Site")
    ham = "|".join(r[k].strip().upper() for k in alanlar)
    return hashlib.sha1(ham.encode("utf-8")).hexdigest()[:16]


# Excel'de sonradan değişebilen ve yeniden aktarımda ticket'a işlenen alanlar
ESITLENEN = ("ticket_no", "durum", "musteri", "kanal", "detay", "site")


def _esitle(conn, anahtar: str, veri: dict, kuru: bool) -> str:
    """Var olan Excel ticket'ını Excel'deki son hâline getirir. Dönüş: sayaç adı."""
    t = conn.execute("SELECT * FROM ticket WHERE aktarim_anahtari=?", (anahtar,)).fetchone()
    farkli = {a: veri[a] for a in ESITLENEN
              if (veri.get(a) or None) != (t[a] or None) and not (a == "durum" and not veri.get(a))}
    if not farkli:
        return "zaten_var"
    elle = conn.execute("SELECT COUNT(*) FROM ticket_gecmis WHERE ticket_id=? AND kullanici_id IS NOT NULL",
                        (t["id"],)).fetchone()[0]
    if elle:
        return "uygulamada_degismis"       # uygulama artık bu ticket'ın kaynağı; Excel ezmez
    if not kuru:
        ticket.guncelle(conn, t["id"], {**farkli, "notu": "Excel'den güncellendi"}, None)
    return "guncellenen"


def aktar(conn, satirlar: list[dict], kuru: bool = False) -> dict:
    sayac = Counter()
    baglanamayan, gecersiz = [], []
    gorulen: Counter = Counter()
    for r in satirlar:
        temel = _anahtar(r)
        gorulen[temel] += 1
        anahtar = f"excel:{temel}:{gorulen[temel]}"       # aynı satır iki kez varsa ikisi de yazılır
        konu = ticket.konu_coz(r["Konu"]) or "DİĞER"
        durum = ticket.durum_coz(r["Durum"]) or "AÇIK"
        if not ticket.konu_coz(r["Konu"]) or not ticket.durum_coz(r["Durum"]):
            gecersiz.append({"satir": r["_satir"], "konu": r["Konu"], "durum": r["Durum"]})
        bina = ticket.lokasyondan_bina(conn, r["Lokasyon"]) if r["Lokasyon"] else None
        if not bina:
            baglanamayan.append({"satir": r["_satir"], "lokasyon": r["Lokasyon"], "site": r["Site"]})
        detay = " · ".join(x for x in (r["Detay"], r["_ek"]) if x)
        veri = {
            "ticket_no": r["Ticket"], "acilis": r["Baslangic"], "konu": konu, "durum": durum,
            "bina_serial": bina["bina_serial"] if bina else None,
            # Excel'deki lokasyon yazımı korunur; bina bulunduysa binanın doğru kimliği yazılır.
            "location_id": (bina or {}).get("location_id") or r["Lokasyon"],
            "site": r["Site"].strip(), "musteri": r["Musteri"], "kanal": ticket._tr_ust(r["Kanal"]),
            "detay": detay,
        }
        var = conn.execute("SELECT 1 FROM ticket WHERE aktarim_anahtari=?", (anahtar,)).fetchone()
        if var:
            sayac[_esitle(conn, anahtar, veri, kuru)] += 1
        elif kuru:
            sayac["eklenecek"] += 1
        else:
            tid, _ = ticket.olustur(conn, veri, None, kaynak="excel", aktarim_anahtari=anahtar)
            sayac["eklenen" if tid else "zaten_var"] += 1
        sayac["binaya_baglanan" if bina else "binasiz"] += 1
    if not kuru:
        conn.commit()
    return {"okunan": len(satirlar), **dict(sayac), "baglanamayan": baglanamayan,
            "bilinmeyen_konu_durum": gecersiz}


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Excel TICKET sayfasını ticket defterine aktarır.")
    ayrac.add_argument("--dosya", default=str(VARSAYILAN_DOSYA), help="data.xlsx yolu (varsayılan: ../PS26/data.xlsx)")
    ayrac.add_argument("--sayfa", default=SAYFA)
    ayrac.add_argument("--db", default=None, help="Veritabanı (varsayılan: saha/saha.db)")
    ayrac.add_argument("--kuru", action="store_true", help="Yazmadan ne olacağını göster")
    a = ayrac.parse_args(argv)
    ayarlar.konsolu_hazirla()
    dosya = Path(a.dosya)
    if not dosya.exists():
        print(f"Dosya bulunamadı: {dosya}")
        return 1
    from . import goc, yedekle

    hedef = Path(a.db) if a.db else db.db_yolu()
    conn = db.baglan(hedef)
    try:
        # Göç burada YAPILMAZ (yalnız sunucu açılışında); sürüm uymuyorsa araç durur.
        try:
            db.semayi_kur(conn)
        except goc.SurumUyumsuz as exc:
            print(exc.mesaj)
            return 3
        satirlar = satirlari_oku(dosya, a.sayfa)
        if not a.kuru:
            print(f"Yedek alındı: {yedekle.aktarim_yedegi(hedef)}")
        s = aktar(conn, satirlar, kuru=a.kuru)
        if not a.kuru:
            db.yonetim_kaydi(conn, None, "ticket_aktar", None,
                             {k: s.get(k, 0) for k in ("okunan", "eklenen", "zaten_var", "guncellenen")})
            conn.commit()
    finally:
        conn.close()
    print(f"{dosya.name} / {a.sayfa}: {s['okunan']} satır okundu.")
    if a.kuru:
        print(f"  Eklenecek     : {s.get('eklenecek', 0)}")
    else:
        print(f"  Eklenen       : {s.get('eklenen', 0)}")
    print(f"  Zaten vardı   : {s.get('zaten_var', 0)}")
    print(f"  Excel'den güncellenen : {s.get('guncellenen', 0)}   "
          f"(uygulamada değiştirildiği için dokunulmayan: {s.get('uygulamada_degismis', 0)})")
    print(f"  Binaya bağlı  : {s.get('binaya_baglanan', 0)}   (binasız: {s.get('binasiz', 0)})")
    for b in s["baglanamayan"][:15]:
        print(f"    satır {b['satir']}: lokasyon '{b['lokasyon'] or '—'}' · {b['site'] or '—'}")
    for g in s["bilinmeyen_konu_durum"][:10]:
        print(f"  ! satır {g['satir']}: konu '{g['konu']}' / durum '{g['durum']}' tanınmadı (DİĞER / AÇIK yazıldı)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
