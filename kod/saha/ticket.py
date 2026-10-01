"""Ticket defteri — OneDesk ticket'larının takibi (Excel'deki TICKET sayfasının yerine).

Operasyonun bugünkü akışı: sahadan (WhatsApp) "sinyal yok / ek kapasite" gelir →
ticket metni yazılır (BN, Tellcordia, Location Id, öbek, site, ekip telefonu) →
OneDesk'te ticket açılır → numarası Excel'e işlenir → çözülünce ya da transfer
olunca mail gelir, Excel elle güncellenir.

Burada aynı şey tek yerde: ticket binaya bağlıdır (bina kartında görünür), metni
bina kimliklerinden otomatik üretilir (``kod/arayuz/src/ortak/kimlik.ts`` ile BİREBİR
aynı şablon), her durum değişikliği notuyla birlikte ``ticket_gecmis`` tablosunda
iz bırakır. Hiçbir kayıt silinmez; iptal de bir durumdur.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import ayarlar

KONULAR = ("SİNYAL", "EK SP", "GÜZERGAH", "ALTYAPI", "DİĞER")
DURUMLAR = ("AÇIK", "ÇÖZÜLDÜ", "HATA", "KAPATILDI", "İPTAL", "TRANSFER")
# Takip gerektiren durumlar: AÇIK (bekliyor), HATA (OneDesk reddetti / yanlış açıldı —
# düzeltilip yeniden açılmalı), TRANSFER (başka ekibe geçti, sonucu beklenir).
ACIK_DURUMLAR = ("AÇIK", "HATA", "TRANSFER")
KAPALI_DURUMLAR = ("ÇÖZÜLDÜ", "KAPATILDI", "İPTAL")

KONU_ETIKET = {
    "SİNYAL": "Sinyal zayıf (BTK)",
    "EK SP": "Ek kapasite (EK SP)",
    "GÜZERGAH": "Güzergah",
    "ALTYAPI": "Altyapı",
    "DİĞER": "Diğer",
}

# Ticket metninin giriş cümlesi. SİNYAL, kullanıcının gerçek ticket'ından birebir;
# diğerleri örnek metin gelene kadar TASLAK (yanıtta ``sablon_taslak: true``).
# kod/arayuz/src/ortak/kimlik.ts → TICKET_GIRIS ile aynı tutulmalı.
TICKET_GIRIS = {
    "SİNYAL": "*BTK ÇAĞRISI ACİL MÜDAHALE* Merhaba, bilgisi olan lokasyonda boş kılda/kıllarda sinyal "
              "zayıftır, düzeltilmesi konusunda desteğinizi rica ederim.",
    "EK SP": "Merhaba, bilgisi olan lokasyonda boş port kalmamıştır, ek kapasite (EK SP) açılması "
             "konusunda desteğinizi rica ederim.",
    "GÜZERGAH": "Merhaba, bilgisi olan lokasyonda güzergah (hat) sorunu vardır, giderilmesi konusunda "
                "desteğinizi rica ederim.",
    "ALTYAPI": "Merhaba, bilgisi olan lokasyonda altyapı sorunu vardır, giderilmesi konusunda desteğinizi "
               "rica ederim.",
    "DİĞER": "Merhaba, bilgisi olan lokasyonla ilgili desteğinizi rica ederim.",
}
ONAYLI_SABLONLAR = {"SİNYAL"}


# ----------------------------------------------------------------------------- sözlük
def _tr_ust(metin: str) -> str:
    return (metin or "").replace("i", "İ").replace("ı", "I").upper()


def _sade(metin: str) -> str:
    """Karşılaştırma anahtarı: Türkçe büyük harf, noktalama/boşluk yok, şapkasız."""
    s = _tr_ust(metin).translate(str.maketrans("İIŞĞÜÖÇÂÎÛ", "IISGUOCAIU"))
    return re.sub(r"[^A-Z0-9]", "", s)


_KONU_ES = {_sade(k): k for k in KONULAR} | {
    "SINYALZAYIF": "SİNYAL", "SINYALYOK": "SİNYAL", "BTK": "SİNYAL",
    "EKSP": "EK SP", "EKKAPASITE": "EK SP", "EKAPASITE": "EK SP", "KAPASITE": "EK SP",
    "HAT": "GÜZERGAH", "DIGER": "DİĞER",
}
_DURUM_ES = {_sade(d): d for d in DURUMLAR} | {
    "COZULMUS": "ÇÖZÜLDÜ", "COZUM": "ÇÖZÜLDÜ", "KAPALI": "KAPATILDI", "ACIL": "AÇIK", "IPTALEDILDI": "İPTAL",
    "REDDEDILDI": "HATA", "TRANSFEREDILDI": "TRANSFER",
}


def konu_coz(ham: str | None) -> str | None:
    return _KONU_ES.get(_sade(ham or "")) if ham else None


def durum_coz(ham: str | None) -> str | None:
    return _DURUM_ES.get(_sade(ham or "")) if ham else None


# ----------------------------------------------------------------------------- metin
_BOS = {"", "null", "none", "nan", "-"}


def _baslik(b: dict) -> str:
    for alan in ("ad", "site_adi"):
        deger = (b.get(alan) or "").strip()
        if deger.lower() not in _BOS:
            return deger
    return ""


def site_adi(b: dict) -> str:
    """Ticket'taki "Site Adı": CRM'deki site adı (data.xlsx 'Site Adı'), yoksa bina adı."""
    return ((b.get("crm_site_adi") or "").strip() or _baslik(b) or (b.get("site_adi") or "")).strip()


def ticket_metni(b: dict, konu: str, ekip: str = "") -> str:
    """OneDesk'e yapıştırılan sekme ayrımlı metin (kimlik.ts → ticketMetni ile birebir).

    Sütun düzeni Excel'deki LOCS sayfasıyla aynı: yapıştırınca her değer kendi hücresine düşer.
    """
    alanlar = [
        TICKET_GIRIS.get(konu, TICKET_GIRIS["DİĞER"]),
        "Bina Serial Number", b.get("bina_serial") or "",
        "Tellcordia ID", b.get("tellcordia_id") or "",
        "",
        "Location Id", b.get("location_id") or "",
        "", "",
        "Obek Adı", b.get("obek") or "",
        "Site Adı", site_adi(b),
        f"Ekip: {(ekip or '').strip()}".strip(),
    ]
    return "\t".join(alanlar)


# ----------------------------------------------------------------------------- okuma
# ``t.*``: v8 sütunları (onedesk_ekip, kategori, tur) göç öncesi bir veritabanında da okunabilsin
# diye tek tek sayılmaz; kart yeni alanları ``.get`` ile okur.
_SUTUNLAR = ("t.*, "
             "k.ad AS olusturan, b.ad AS bina_ad, b.site_adi AS bina_site_adi, b.bolge AS bolge, "
             "b.ilce AS ilce, b.mahalle AS mahalle, b.lat AS lat, b.lon AS lon")
_KATILIM = ("FROM ticket t LEFT JOIN kullanici k ON k.id=t.olusturan_id "
            "LEFT JOIN bina b ON b.bina_serial=t.bina_serial")


def kart(r: sqlite3.Row | dict) -> dict:
    r = dict(r)
    acilis = r.get("acilis")
    gun = None
    if acilis and r.get("durum") in ACIK_DURUMLAR:
        try:
            import datetime as dt

            gun = (ayarlar.bugun() - dt.date.fromisoformat(acilis[:10])).days
        except ValueError:
            gun = None
    return {
        "id": r["id"], "ticket_no": r.get("ticket_no") or "", "acilis": acilis, "konu": r["konu"],
        "konu_etiket": KONU_ETIKET.get(r["konu"], r["konu"]), "durum": r["durum"],
        "acik": r["durum"] in ACIK_DURUMLAR, "acik_gun": gun,
        "bina_serial": r.get("bina_serial"), "location_id": r.get("location_id") or "",
        "site": r.get("site") or "", "musteri": r.get("musteri") or "", "kanal": r.get("kanal") or "",
        "detay": r.get("detay") or "", "metin": r.get("metin") or "",
        "olusturan": r.get("olusturan"), "olusturma": r.get("olusturma"), "guncelleme": r.get("guncelleme"),
        "kapanis": r.get("kapanis"), "kaynak": r.get("kaynak"),
        # Ek-5: OneDesk ekibi ve başlığı · Ek-8: 'guzergah' = PS26 GÜZERGAH sayfasından
        "onedesk_ekip": r.get("onedesk_ekip") or "", "kategori": r.get("kategori") or "",
        "tur": r.get("tur"),
        "bina": ({"bina_serial": r.get("bina_serial"),
                  "ad": _baslik({"ad": r.get("bina_ad"), "site_adi": r.get("bina_site_adi")}),
                  "bolge": r.get("bolge"), "ilce": r.get("ilce"), "mahalle": r.get("mahalle"),
                  "lat": r.get("lat"), "lon": r.get("lon")} if r.get("bina_serial") else None),
    }


def getir(conn: sqlite3.Connection, ticket_id: int) -> dict | None:
    r = conn.execute(f"SELECT {_SUTUNLAR} {_KATILIM} WHERE t.id=?", (ticket_id,)).fetchone()
    return kart(r) if r else None


def gecmis(conn: sqlite3.Connection, ticket_id: int) -> list[dict]:
    return [
        {**dict(r), "alanlar": json.loads(r["alanlar"]) if r["alanlar"] else None}
        for r in conn.execute(
            "SELECT g.id, g.zaman, g.eski_durum, g.yeni_durum, g.notu, g.alanlar, k.ad AS kullanici "
            "FROM ticket_gecmis g LEFT JOIN kullanici k ON k.id=g.kullanici_id "
            "WHERE g.ticket_id=? ORDER BY g.id", (ticket_id,)).fetchall()
    ]


def binanin_ticketlari(conn: sqlite3.Connection, bina_serial: str) -> list[dict]:
    try:
        satirlar = conn.execute(
            f"SELECT {_SUTUNLAR} {_KATILIM} WHERE t.bina_serial=? "
            "ORDER BY CASE WHEN t.durum IN ('AÇIK','HATA','TRANSFER') THEN 0 ELSE 1 END, "
            "COALESCE(t.acilis, t.olusturma) DESC, t.id DESC LIMIT 50", (bina_serial,)).fetchall()
    except sqlite3.Error:
        return []                    # tablo henüz yoksa (göç çalışmamış) kart yine açılır
    return [kart(r) for r in satirlar]


def liste(conn: sqlite3.Connection, durum: str | None = None, konu: str | None = None,
          kanal: str | None = None, q: str | None = None, bina_serial: str | None = None,
          acik: bool | None = None, bolge: int | None = None, limit: int = 100, offset: int = 0) -> dict:
    kosul, deger = [], []
    if durum:
        d = durum_coz(durum)
        if not d:
            raise ValueError(f"Geçersiz durum: {durum}")
        kosul.append("t.durum=?")
        deger.append(d)
    if konu:
        k = konu_coz(konu)
        if not k:
            raise ValueError(f"Geçersiz konu: {konu}")
        kosul.append("t.konu=?")
        deger.append(k)
    if kanal:
        kosul.append("UPPER(t.kanal)=?")
        deger.append(_tr_ust(kanal.strip()))
    if bina_serial:
        kosul.append("t.bina_serial=?")
        deger.append(bina_serial)
    if acik is True:
        kosul.append("t.durum IN ('AÇIK','HATA','TRANSFER')")
    elif acik is False:
        kosul.append("t.durum IN ('ÇÖZÜLDÜ','KAPATILDI','İPTAL')")
    if bolge is not None:
        kosul.append("b.bolge=?")
        deger.append(int(bolge))
    if q and q.strip():
        aranan = f"%{q.strip()}%"
        kosul.append("(t.ticket_no LIKE ? OR t.location_id LIKE ? OR t.site LIKE ? OR t.musteri LIKE ? "
                     "OR t.detay LIKE ? OR t.bina_serial LIKE ? OR b.ad LIKE ?)")
        deger.extend([aranan] * 7)
    nerede = (" WHERE " + " AND ".join(kosul)) if kosul else ""
    toplam = conn.execute(f"SELECT COUNT(*) {_KATILIM}{nerede}", tuple(deger)).fetchone()[0]
    satirlar = conn.execute(
        f"SELECT {_SUTUNLAR} {_KATILIM}{nerede} "
        "ORDER BY CASE WHEN t.durum IN ('AÇIK','HATA','TRANSFER') THEN 0 ELSE 1 END, "
        "COALESCE(t.acilis, substr(t.olusturma,1,10)) DESC, t.id DESC LIMIT ? OFFSET ?",
        tuple(deger) + (limit, offset)).fetchall()
    sayilar = {d: 0 for d in DURUMLAR}
    for r in conn.execute("SELECT durum, COUNT(*) c FROM ticket GROUP BY durum"):
        sayilar[r["durum"]] = int(r["c"])
    konu_sayilari = {k: 0 for k in KONULAR}
    for r in conn.execute("SELECT konu, COUNT(*) c FROM ticket WHERE durum IN ('AÇIK','HATA','TRANSFER') "
                          "GROUP BY konu"):
        konu_sayilari[r["konu"]] = int(r["c"])
    return {"toplam": int(toplam), "limit": limit, "offset": offset,
            "sayilar": sayilar, "acik_toplam": sum(sayilar[d] for d in ACIK_DURUMLAR),
            "acik_konu": konu_sayilari,
            "ticketlar": [kart(r) for r in satirlar]}


def harita_sayilari(conn: sqlite3.Connection) -> dict:
    """3B ikiz / harita boyaması için: açık ticket'ı olan binalar."""
    satirlar = conn.execute(
        "SELECT bina_serial, COUNT(*) c FROM ticket WHERE bina_serial IS NOT NULL "
        "AND durum IN ('AÇIK','HATA','TRANSFER') GROUP BY bina_serial ORDER BY bina_serial").fetchall()
    return {"serial": [r[0] for r in satirlar], "acik": [int(r[1]) for r in satirlar]}


# ----------------------------------------------------------------------------- yazma
def _bina(conn: sqlite3.Connection, bina_serial: str | None = None, location_id: str | None = None) -> dict | None:
    alanlar = ("bina_serial, ad, site_adi, crm_site_adi, location_id, tellcordia_id, obek, bolge, lat, lon")
    if bina_serial:
        r = conn.execute(f"SELECT {alanlar} FROM bina WHERE bina_serial=?", (bina_serial,)).fetchone()
        return dict(r) if r else None
    if location_id:
        return lokasyondan_bina(conn, location_id)
    return None


def lokasyondan_bina(conn: sqlite3.Connection, lokasyon: str) -> dict | None:
    """BOSS/Excel "Lokasyon" → bina.

    Sırayla: birebir · 8 haneye sıfırlı · baştaki sıfırsız · sondaki "-1" eki atılmış
    (TICKET sayfasında 'O27592861-1' gibi yazımlar var; aynı site adıyla 'O27592861').
    """
    lok = (lokasyon or "").strip()
    if not lok:
        return None
    alanlar = ("bina_serial, ad, site_adi, crm_site_adi, location_id, tellcordia_id, obek, bolge, lat, lon")
    adaylar = [lok]
    if lok.isdigit():
        adaylar += [lok.zfill(8), lok.lstrip("0")]
    ekisiz = re.sub(r"-\d{1,2}$", "", lok)
    if ekisiz != lok:
        adaylar.append(ekisiz)
    for a in dict.fromkeys(adaylar):
        r = conn.execute(f"SELECT {alanlar} FROM bina WHERE location_id=? ORDER BY pasif, bina_serial LIMIT 1",
                         (a,)).fetchone()
        if r:
            return dict(r)
    return None


def _tarih(metin: str | None) -> str | None:
    if not metin:
        return None
    s = str(metin).strip()[:10]
    try:
        import datetime as dt

        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$", s)
        if m:
            import datetime as dt

            try:
                return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            except ValueError:
                return None
    return None


def olustur(conn: sqlite3.Connection, veri: dict, yapan_id: int | None, kaynak: str = "uygulama",
            aktarim_anahtari: str | None = None, olusturma: str | None = None) -> tuple[int | None, dict]:
    """Yeni ticket. Binadan açılırsa kimlik ve site alanları binadan dolar.

    Dönüş: (id, bilgi). ``aktarim_anahtari`` zaten varsa id=None (Excel aktarımı tekrar yazmaz).
    """
    konu = konu_coz(veri.get("konu"))
    if not konu:
        raise ValueError(f"Konu şunlardan biri olmalı: {', '.join(KONULAR)}")
    durum = durum_coz(veri.get("durum")) if veri.get("durum") else "AÇIK"
    if not durum:
        raise ValueError(f"Durum şunlardan biri olmalı: {', '.join(DURUMLAR)}")
    b = _bina(conn, (veri.get("bina_serial") or "").strip() or None,
              (veri.get("location_id") or "").strip() or None)
    if veri.get("bina_serial") and not b:
        raise LookupError("Bina bulunamadı.")
    simdi = olusturma or ayarlar.zaman_metni()
    location_id = (veri.get("location_id") or "").strip() or (b or {}).get("location_id") or ""
    site = (veri.get("site") or "").strip() or (site_adi(b) if b else "")
    metin = (veri.get("metin") or "").strip()
    if not metin and b is not None:
        metin = ticket_metni(b, konu, veri.get("ekip") or "")
    acilis = _tarih(veri.get("acilis")) or (simdi[:10] if kaynak == "uygulama" else None)
    kapanis = simdi if durum in KAPALI_DURUMLAR and kaynak == "uygulama" else None
    ek_alanlar = {a: (str(veri.get(a) or "").strip() or None) for a in ("onedesk_ekip", "kategori", "tur")
                  if veri.get(a)}
    ek_sutun = "".join(f", {a}" for a in ek_alanlar)
    imlec = conn.execute(
        "INSERT INTO ticket (ticket_no, acilis, konu, durum, bina_serial, location_id, site, musteri, kanal, "
        f"  detay, metin, olusturan_id, olusturma, guncelleme, kapanis, kaynak, aktarim_anahtari{ek_sutun}) "
        f"VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?{',?' * len(ek_alanlar)}) "
        "ON CONFLICT(aktarim_anahtari) DO NOTHING",
        ((veri.get("ticket_no") or "").strip() or None, acilis, konu, durum, (b or {}).get("bina_serial"),
         location_id or None, site or None, (veri.get("musteri") or "").strip() or None,
         _tr_ust((veri.get("kanal") or "").strip()) or None, (veri.get("detay") or "").strip() or None,
         metin or None, yapan_id, simdi, simdi, kapanis, kaynak, aktarim_anahtari, *ek_alanlar.values()))
    if imlec.rowcount == 0:
        return None, {"bina": b}
    tid = int(imlec.lastrowid)
    conn.execute(
        "INSERT INTO ticket_gecmis (ticket_id, zaman, kullanici_id, eski_durum, yeni_durum, notu) "
        "VALUES (?,?,?,?,?,?)",
        (tid, simdi, yapan_id, None, durum,
         "Excel'den aktarıldı" if kaynak == "excel" else ((veri.get("notu") or "").strip() or "Oluşturuldu")))
    return tid, {"bina": b, "sablon_taslak": konu not in ONAYLI_SABLONLAR}


GUNCELLENEBILIR = ("ticket_no", "acilis", "konu", "durum", "musteri", "kanal", "detay", "site", "location_id",
                   "onedesk_ekip", "kategori")


def guncelle(conn: sqlite3.Connection, ticket_id: int, veri: dict, yapan_id: int) -> dict:
    eski = conn.execute("SELECT * FROM ticket WHERE id=?", (ticket_id,)).fetchone()
    if not eski:
        raise LookupError("Ticket bulunamadı.")
    yeni: dict = {}
    for alan in GUNCELLENEBILIR:
        if alan not in veri or veri[alan] is None:
            continue
        deger = veri[alan]
        if alan == "durum":
            deger = durum_coz(deger)
            if not deger:
                raise ValueError(f"Durum şunlardan biri olmalı: {', '.join(DURUMLAR)}")
        elif alan == "konu":
            deger = konu_coz(deger)
            if not deger:
                raise ValueError(f"Konu şunlardan biri olmalı: {', '.join(KONULAR)}")
        elif alan == "acilis":
            deger = _tarih(deger)
            if not deger:
                raise ValueError("Açılış tarihi YYYY-AA-GG olmalı.")
        elif alan == "kanal":
            deger = _tr_ust(str(deger).strip()) or None
        else:
            deger = str(deger).strip() or None
        if deger != (eski[alan] if alan in eski.keys() else None):
            yeni[alan] = deger
    notu = (veri.get("notu") or "").strip()[:2000] or None
    if not yeni and not notu:
        return {"degisti": False}
    simdi = ayarlar.zaman_metni()
    if "durum" in yeni:
        if yeni["durum"] in KAPALI_DURUMLAR and not eski["kapanis"]:
            yeni["kapanis"] = simdi
        elif yeni["durum"] in ACIK_DURUMLAR and eski["kapanis"]:
            yeni["kapanis"] = None                  # yeniden açıldı
    if yeni:
        atama = ", ".join(f"{a}=?" for a in yeni) + ", guncelleme=?"
        conn.execute(f"UPDATE ticket SET {atama} WHERE id=?", (*yeni.values(), simdi, ticket_id))
    else:
        conn.execute("UPDATE ticket SET guncelleme=? WHERE id=?", (simdi, ticket_id))
    alanlar = {a: [eski[a], v] for a, v in yeni.items() if a not in ("durum", "kapanis")}
    conn.execute(
        "INSERT INTO ticket_gecmis (ticket_id, zaman, kullanici_id, eski_durum, yeni_durum, notu, alanlar) "
        "VALUES (?,?,?,?,?,?,?)",
        (ticket_id, simdi, yapan_id, eski["durum"], yeni.get("durum", eski["durum"]), notu,
         json.dumps(alanlar, ensure_ascii=False) if alanlar else None))
    return {"degisti": True, "alanlar": list(yeni)}
