"""Ticket defteri — OneDesk ticket'larının takibi (Excel'deki TICKET sayfasının yerine).

Operasyonun bugünkü akışı: sahadan (WhatsApp) "sinyal yok / ek kapasite" gelir →
ticket metni yazılır (BN, Tellcordia, Location Id, öbek, site, ekip telefonu) →
OneDesk'te ticket açılır → numarası Excel'e işlenir → çözülünce ya da transfer
olunca mail gelir, Excel elle güncellenir.

Burada aynı şey tek yerde: ticket binaya bağlıdır (bina kartında görünür), metni
bina kimliklerinden otomatik üretilir (``kod/arayuz/src/cekirdek/ortak/kimlik.ts`` ile BİREBİR
aynı şablon), her durum değişikliği notuyla birlikte ``ticket_gecmis`` tablosunda
iz bırakır; iptal de bir durumdur (silme ayrıdır, aşağıda).

Yeni ticket Excel satırı gibi girilir: Müşteri No yazılınca ``musteri_bilgisi`` müşterinin açık işinden Loc ID,
bina/site adı ve Task adını verir (birden çok müşteri no virgülle). Loc ID doğrudan da yazılabilir: bina, site, ilçe/mahalle ve binadaki açık işlerin
müşteri numaraları ``lokasyon_bilgisi`` ile doldurulur (``olustur`` da aynı yardımcıyla doldurur).
Açık ticket'ların TEK kaynağı ``acik_ticketlar``: TASKS uyarısı (``operasyon/v2/uyari.py``), ``acik_lokasyonlar``
ve kurulum engeli bağı (``operasyon/v2/akis.py`` → ``_engel_bagla``) aynı listeyi okur. Listede her ticket'ın
``bekleyen_is`` sayısı (bağlı, kapanmamış, Bizim durumu "İptal" olmayan işler) vardır: "Açık engeller" görünümü.

Ticket'ın İŞLERİ (``kart["isler"]``): yeni satırda seçilen işler (``ticket_is``: Task No, Task adı, satış kanalı;
seçici ``is_secenekleri``) + kurulum engeliyle bağlanan işler (``is_emri.ticket_id``). Tablodaki Task No · Task adı ·
Satış kanalı bunlardan; ⚠ kanal şikâyeti uyarısı TASKS'la aynı yerden (``operasyon/v2/uyari.py`` → ``Uyarilar``).
Silme KALICIDIR, iz bırakmaz (``sil`` · ``toplu_sil``, tek işlem): bağlı AÇIK işler ayrılır (``akis.ticket_ayir``;
iş geçmişinde yalnız nötr "Ticket'tan ayrıldı"), kapanmış işlerin bağı boşalır; ``ticket_is`` · ``ticket_gecmis`` ·
``ticket_ek`` (+ diskteki fotoğraflar) · ``ticket_boss_not`` satırları ve ticket'ın kendisi silinir; yonetim_kaydi
yazılmaz. BOSS'a gitmiş notlar BOSS'ta kalır. ``ticket_is`` yan tablodur, ``sema`` gerektiğinde kurar.
Aynı lokasyonda yakın tarihli ticket uyarısı: ``benzer_ticketlar``.
Ticket numarası girilince işlere kendiliğinden BOSS notu: ``saha/ticket_boss_not.py`` (``getir`` → ``boss_notlari``).
Uçlar: ``saha/yonetim_uclari.py``.
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import ayarlar

KONULAR = ("SİNYAL", "EK SP", "GÜZERGAH", "ALTYAPI", "DİĞER")
DURUMLAR = ("AÇIK", "ÇÖZÜLDÜ", "HATA", "KAPATILDI", "İPTAL", "TRANSFER", "BÖLGE")
# Takip gerektiren durumlar: AÇIK (bekliyor), HATA (OneDesk reddetti / yanlış açıldı —
# düzeltilip yeniden açılmalı), TRANSFER (başka ekibe geçti, sonucu beklenir), BÖLGE (ticket bölgeye iletildi;
# sonucu bölgeden beklenir). Hepsi "çözülmedi" sayılır: bağlı işler askıda kalır, otomatik askı yenilenir (HATA gibi).
# Ticketlar ekranının "Açık engeller" görünümü ise YALNIZ AÇIK'ı izler (HATA/BÖLGE ayrı çiplerde).
ACIK_DURUMLAR = ("AÇIK", "HATA", "TRANSFER", "BÖLGE")
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


# ----------------------------------------------------------------------------- yan tablolar
_YAN_SEMA = (
    "CREATE TABLE IF NOT EXISTS ticket_is (ticket_id INTEGER NOT NULL, task_no TEXT NOT NULL, is_no TEXT, "
    "task_adi TEXT, satis_kanali TEXT, musteri_no TEXT, lokasyon TEXT, ekleme TEXT NOT NULL, "
    "PRIMARY KEY (ticket_id, task_no))",
)


def sema(conn: sqlite3.Connection) -> None:
    """``ticket_is`` yoksa kurar (etkisiz; var olana dokunmaz). Eski yumuşak silme tablosu ``ticket_silme``
    ``ticket_temizlik.silinenler_calistir`` ile (yedekli) kalıcı silinip kaldırılır."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticket_is'").fetchone():
        for ifade in _YAN_SEMA:
            conn.execute(ifade)


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
    "BOLGEYE": "BÖLGE", "BOLGEYEILETILDI": "BÖLGE", "BOLGEYEGITTI": "BÖLGE",
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
        # Ek-5: OneDesk ekibi ve başlığı · tur: eski (2026-10'da silinen) PS26 GÜZERGAH satırlarındandı
        "onedesk_ekip": r.get("onedesk_ekip") or "", "kategori": r.get("kategori") or "",
        "tur": r.get("tur"),
        # İşler (``_task_bilgileri`` doldurur; binanın ticket'ları gibi kısa listelerde boş kalır)
        "isler": [], "musteriler": musteri_nolari(r.get("musteri")), "satis_kanali": r.get("kanal") or "",
        "uyari": "", "silindi": False, "isi_kapandi": False,
        "bina": ({"bina_serial": r.get("bina_serial"),
                  "ad": _baslik({"ad": r.get("bina_ad"), "site_adi": r.get("bina_site_adi")}),
                  "bolge": r.get("bolge"), "ilce": r.get("ilce"), "mahalle": r.get("mahalle"),
                  "lat": r.get("lat"), "lon": r.get("lon")} if r.get("bina_serial") else None),
    }


def getir(conn: sqlite3.Connection, ticket_id: int) -> dict | None:
    sema(conn)
    r = conn.execute(f"SELECT {_SUTUNLAR} {_KATILIM} WHERE t.id=?", (ticket_id,)).fetchone()
    if not r:
        return None
    k = kart(r)
    _task_bilgileri(conn, [k])
    _bekleyenler(conn, [k])
    from . import ticket_boss_not             # iş başına "BOSS notu: gidiyor / ✓ / hata" (çekmece)
    k["boss_notlari"] = ticket_boss_not.durumlar(conn, ticket_id)
    from . import ticket_boss_aski            # iş başına otomatik askı / çözümde geri atama hâli (çekmece)
    k["boss_askilar"] = ticket_boss_aski.durumlar(conn, ticket_id)
    return k


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
        sema(conn)
        satirlar = conn.execute(
            f"SELECT {_SUTUNLAR} {_KATILIM} WHERE t.bina_serial=? "
            "ORDER BY CASE WHEN t.durum IN ('AÇIK','HATA','TRANSFER','BÖLGE') THEN 0 ELSE 1 END, "
            "COALESCE(t.acilis, t.olusturma) DESC, t.id DESC LIMIT 50", (bina_serial,)).fetchall()
    except sqlite3.Error:
        return []                    # tablo henüz yoksa (göç çalışmamış) kart yine açılır
    return [kart(r) for r in satirlar]


def liste(conn: sqlite3.Connection, durum: str | None = None, konu: str | None = None,
          kanal: str | None = None, q: str | None = None, bina_serial: str | None = None,
          acik: bool | None = None, bolge: int | None = None, limit: int = 100, offset: int = 0) -> dict:
    sema(conn)
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
        kosul.append("t.durum IN ('AÇIK','HATA','TRANSFER','BÖLGE')")
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
        "ORDER BY CASE WHEN t.durum IN ('AÇIK','HATA','TRANSFER','BÖLGE') THEN 0 ELSE 1 END, "
        "COALESCE(t.acilis, substr(t.olusturma,1,10)) DESC, t.id DESC LIMIT ? OFFSET ?",
        tuple(deger) + (limit, offset)).fetchall()
    sayilar = {d: 0 for d in DURUMLAR}
    for r in conn.execute("SELECT durum, COUNT(*) c FROM ticket t GROUP BY durum"):
        sayilar[r["durum"]] = int(r["c"])
    konu_sayilari = {k: 0 for k in KONULAR}
    for r in conn.execute("SELECT konu, COUNT(*) c FROM ticket t WHERE durum IN ('AÇIK','HATA','TRANSFER','BÖLGE') "
                          "GROUP BY konu"):
        konu_sayilari[r["konu"]] = int(r["c"])
    kartlar = [kart(r) for r in satirlar]
    _task_bilgileri(conn, kartlar)
    _bekleyenler(conn, kartlar)
    return {"toplam": int(toplam), "limit": limit, "offset": offset,
            "sayilar": sayilar, "acik_toplam": sum(sayilar[d] for d in ACIK_DURUMLAR),
            "acik_konu": konu_sayilari,
            "ticketlar": kartlar}


def harita_sayilari(conn: sqlite3.Connection) -> dict:
    """3B ikiz / harita boyaması için: açık ticket'ı olan binalar."""
    sema(conn)
    satirlar = conn.execute(
        "SELECT bina_serial, COUNT(*) c FROM ticket t WHERE bina_serial IS NOT NULL "
        "AND durum IN ('AÇIK','HATA','TRANSFER','BÖLGE') GROUP BY bina_serial ORDER BY bina_serial"
    ).fetchall()
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


def _lokasyon_adaylari(lokasyon: str | None) -> list[str]:
    """Bir Loc ID'nin veritabanındaki olası yazımları: birebir · 8 haneye sıfırlı · baştaki sıfırsız ·
    sondaki "-1" eki atılmış (TICKET sayfasında 'O27592861-1' gibi yazımlar var; aynı site 'O27592861')."""
    lok = (lokasyon or "").strip().upper()
    if not lok:
        return []
    adaylar = [lok]
    if lok.isdigit():
        adaylar += [lok.zfill(8), lok.lstrip("0")]
    ekisiz = re.sub(r"-\d{1,2}$", "", lok)
    if ekisiz != lok:
        adaylar.append(ekisiz)
    return [a for a in dict.fromkeys(adaylar) if a]


def lokasyon_anahtari(lokasyon: str | None) -> str:
    """Karşılaştırma anahtarı: büyük harf, boşluksuz, "-1" eksiz, rakamsa baştaki sıfırsız.

    İş (``is_emri.lokasyon``) ile ticket'ı eşlemek için: ``lokasyon_anahtari(is.lokasyon) in acik_lokasyonlar(conn)``.
    """
    lok = re.sub(r"\s+", "", (lokasyon or "")).upper()
    lok = re.sub(r"-\d{1,2}$", "", lok)
    return lok.lstrip("0") if lok.isdigit() else lok


def lokasyondan_bina(conn: sqlite3.Connection, lokasyon: str) -> dict | None:
    """BOSS/Excel "Lokasyon" → bina (adaylar sırayla denenir; pasif bina en sona)."""
    alanlar = ("bina_serial, ad, site_adi, crm_site_adi, location_id, tellcordia_id, obek, bolge, lat, lon")
    for a in _lokasyon_adaylari(lokasyon):
        r = conn.execute(f"SELECT {alanlar} FROM bina WHERE location_id=? ORDER BY pasif, bina_serial LIMIT 1",
                         (a,)).fetchone()
        if r:
            return dict(r)
    return None


def acik_ticketlar(conn: sqlite3.Connection) -> list[dict]:
    """Açık (AÇIK · HATA · TRANSFER) ticket'lar — TEK kaynak: {id, konu, durum, bina_serial, location_id,
    bina_location_id}, id sırasıyla. TASKS uyarısı, ``acik_lokasyonlar``, iş görünümündeki binada açık ticket sayısı
    ve kurulum engeli bağı bunu okur. Tablo yoksa (göç çalışmamış) boş liste."""
    try:
        satirlar = conn.execute(
            "SELECT t.id, t.konu, t.durum, t.bina_serial, t.location_id, b.location_id AS bina_location_id "
            "FROM ticket t LEFT JOIN bina b ON b.bina_serial=t.bina_serial "
            f"WHERE t.durum IN ({','.join('?' * len(ACIK_DURUMLAR))}) ORDER BY t.id", ACIK_DURUMLAR).fetchall()
    except sqlite3.Error:
        return []
    return [dict(r) for r in satirlar]


def acik_lokasyonlar(conn: sqlite3.Connection, ticketlar: list[dict] | None = None) -> set[str]:
    """Açık ticket'ı olan Loc ID'ler, ``lokasyon_anahtari`` biçiminde (``acik_ticketlar``'dan).

    Ticket'ın kendi Loc ID'si ve bağlı olduğu binanınki birlikte sayılır.
    """
    liste = acik_ticketlar(conn) if ticketlar is None else ticketlar
    return {lokasyon_anahtari(t[a]) for t in liste for a in ("location_id", "bina_location_id")
            if t.get(a) and lokasyon_anahtari(t[a])}


def bekleyen_isler(conn: sqlite3.Connection, ticket_idler) -> dict[int, int]:
    """{ticket_id: bekleyen iş}: ticket'a bağlı, kapanmamış, Bizim durumu "İptal" olmayan işler (kurulum engeli
    takibi; ``operasyon/v2/akis.py`` → ``BIZIM_IPTAL``). İş emri tablosu yoksa boş."""
    idler = sorted({int(t) for t in ticket_idler})
    sonuc: dict[int, int] = {}
    try:
        for i in range(0, len(idler), 500):
            parca = idler[i:i + 500]
            for r in conn.execute(
                    "SELECT ticket_id, COUNT(*) FROM is_emri WHERE ticket_id IN "
                    f"({','.join('?' * len(parca))}) AND durum NOT IN ('cozuldu','kapandi') "
                    "AND COALESCE(bizim_durum,'') <> 'İptal' GROUP BY ticket_id", parca):
                sonuc[int(r[0])] = int(r[1])
    except sqlite3.Error:
        return {}
    return sonuc


def _bekleyenler(conn: sqlite3.Connection, kartlar: list[dict]) -> None:
    sayi = bekleyen_isler(conn, [k["id"] for k in kartlar])
    for k in kartlar:
        k["bekleyen_is"] = sayi.get(k["id"], 0)


def acik_is_musterileri(conn: sqlite3.Connection, bina_serial: str | None, lokasyon: str | None) -> list[str]:
    """Binadaki (ya da o Loc ID'deki) AÇIK işlerin müşteri numaraları, tekrarsız, açılış sırasıyla."""
    from .yetki import KAPALI_IS_DURUMLARI

    kosul, deger = [], []
    if bina_serial:
        kosul.append("bina_serial=?")
        deger.append(bina_serial)
    adaylar = _lokasyon_adaylari(lokasyon)
    if adaylar:
        kosul.append(f"UPPER(TRIM(lokasyon)) IN ({','.join('?' * len(adaylar))})")
        deger += adaylar
    if not kosul:
        return []
    kapali = ",".join("?" * len(KAPALI_IS_DURUMLARI))
    try:
        satirlar = conn.execute(
            f"SELECT musteri_no FROM is_emri WHERE ({' OR '.join(kosul)}) AND durum NOT IN ({kapali}) "
            "AND COALESCE(TRIM(musteri_no),'') <> '' ORDER BY acilis, is_no",
            (*deger, *KAPALI_IS_DURUMLARI)).fetchall()
    except sqlite3.Error:
        return []                    # iş emri tablosu yoksa (yalnız satış kurulumu)
    return list(dict.fromkeys(str(r[0]).strip() for r in satirlar))


def lokasyon_bilgisi(conn: sqlite3.Connection, lokasyon: str | None = None,
                     bina_serial: str | None = None) -> dict:
    """Yeni ticket penceresi: Loc ID (ya da binadan açılınca Bina Serial) → doldurulacak her şey.

    ``bulundu``: bina ya da açık iş bulundu mu. Bulunmasa da ticket o Loc ID ile kaydedilebilir.
    """
    b = _bina(conn, (bina_serial or "").strip() or None, None) if bina_serial else lokasyondan_bina(conn, lokasyon or "")
    ek = None
    if b:
        ek = conn.execute("SELECT ilce, mahalle FROM bina WHERE bina_serial=?", (b["bina_serial"],)).fetchone()
    loc = (b or {}).get("location_id") or (lokasyon or "").strip().upper()
    musteriler = acik_is_musterileri(conn, (b or {}).get("bina_serial"), loc)
    return {
        "location_id": loc, "bulundu": bool(b or musteriler),
        "bina_serial": (b or {}).get("bina_serial"), "site": site_adi(b) if b else "",
        "ilce": (ek["ilce"] if ek else None) or "", "mahalle": (ek["mahalle"] if ek else None) or "",
        "bolge": (b or {}).get("bolge"), "musteriler": musteriler,
        "acik_ticketlar": [t for t in binanin_ticketlari(conn, b["bina_serial"]) if t["acik"]] if b else [],
    }


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
    secilen = [str(x).strip() for x in (veri.get("isler") or []) if str(x or "").strip()]
    if secilen and not (veri.get("location_id") or "").strip() and not (veri.get("bina_serial") or "").strip():
        ilk = _is_bul(conn, secilen[:1])               # Loc ID yazılmadıysa seçilen ilk işinki
        if ilk:
            veri = {**veri, "location_id": (ilk[0]["lokasyon"] or "").strip().upper() or None,
                    "bina_serial": None if ilk[0]["lokasyon"] else ilk[0]["bina_serial"]}
    b = _bina(conn, (veri.get("bina_serial") or "").strip() or None,
              (veri.get("location_id") or "").strip() or None)
    if veri.get("bina_serial") and not b:
        raise LookupError("Bina bulunamadı.")
    simdi = olusturma or ayarlar.zaman_metni()
    location_id = (veri.get("location_id") or "").strip() or (b or {}).get("location_id") or ""
    site = (veri.get("site") or "").strip() or (site_adi(b) if b else "")
    musteri = (veri.get("musteri") or "").strip()
    if not musteri and kaynak == "uygulama" and not secilen:   # Excel'deki gibi: binadaki açık işlerin müşteri no'ları
        musteri = ", ".join(acik_is_musterileri(conn, (b or {}).get("bina_serial"), location_id))
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
         location_id or None, site or None, musteri or None,
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
    bilgi = {"bina": b, "sablon_taslak": konu not in ONAYLI_SABLONLAR}
    if secilen:                                   # seçicide işaretlenen işler (Task No · Task adı · satış kanalı)
        bilgi["isler"] = isleri_ekle(conn, tid, secilen, yapan_id, not_yaz=False)
    return tid, bilgi


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


# ----------------------------------------------------------------------------- müşteri no → iş (Excel satırı gibi giriş)
_MUSTERI_AYIR = re.compile(r"[\s,;/|]+")


def musteri_nolari(metin: str | None) -> list[str]:
    """"123, 456 ; 789" → ["123", "456", "789"] (tekrarsız, sırası korunur). Ticket'ta birden çok müşteri olur."""
    return list(dict.fromkeys(p for p in _MUSTERI_AYIR.split((metin or "").strip()) if p))


def _musteri_isi(conn: sqlite3.Connection, musteri_no: str) -> dict | None:
    """Müşterinin işi: önce AÇIK olanların en yenisi, açık yoksa en yeni iş."""
    from .yetki import KAPALI_IS_DURUMLARI

    kapali = ",".join("?" * len(KAPALI_IS_DURUMLARI))
    try:
        r = conn.execute(
            "SELECT is_no, boss_task_no, task_adi, lokasyon, bina_serial, durum FROM is_emri "
            f"WHERE TRIM(musteri_no)=? ORDER BY CASE WHEN durum IN ({kapali}) THEN 1 ELSE 0 END, acilis DESC, "
            "is_no DESC LIMIT 1", (musteri_no.strip(), *KAPALI_IS_DURUMLARI)).fetchone()
    except sqlite3.Error:
        return None                  # iş emri tablosu yoksa (yalnız satış kurulumu)
    return dict(r) if r else None


def musteri_bilgisi(conn: sqlite3.Connection, musteri_no: str) -> dict:
    """Yeni ticket satırı: Müşteri No → Loc ID, bina/site adı, Task adı, Task No (müşterinin açık işinden).

    ``bulundu`` False ise hücreler boş kalır; Loc ID elle yazılır. ``acik`` False: iş bulundu ama kapanmış.
    """
    from .yetki import KAPALI_IS_DURUMLARI

    no = (musteri_no or "").strip()
    bos = {"musteri_no": no, "bulundu": False, "acik": False, "lokasyon": "", "bina_serial": None,
           "bina_adi": "", "task_adi": "", "task_no": ""}
    is_ = _musteri_isi(conn, no) if no else None
    if not is_:
        return bos
    b = _bina(conn, is_.get("bina_serial")) if is_.get("bina_serial") else None
    if b is None and is_.get("lokasyon"):
        b = lokasyondan_bina(conn, is_["lokasyon"])
    return {
        "musteri_no": no, "bulundu": True, "acik": is_["durum"] not in KAPALI_IS_DURUMLARI,
        "lokasyon": (is_.get("lokasyon") or "").strip().upper() or (b or {}).get("location_id") or "",
        "bina_serial": (b or {}).get("bina_serial"), "bina_adi": site_adi(b) if b else "",
        "task_adi": is_.get("task_adi") or "", "task_no": is_.get("boss_task_no") or is_.get("is_no") or "",
    }


def _ilk_musteri_isi(conn: sqlite3.Connection, kartlar: list[dict]) -> None:
    """Yedek (işi seçilmemiş/bağlanmamış ticket): İLK müşteri no'sunun işi → ``task_adi``, ``task_no``,
    ``satis_kanali`` (tek sorguda, yerinde)."""
    from .yetki import KAPALI_IS_DURUMLARI

    ilkler = {k["id"]: (musteri_nolari(k.get("musteri")) or [None])[0] for k in kartlar}
    nolar = sorted({n for n in ilkler.values() if n})
    bulunan: dict[str, tuple] = {}
    if nolar:
        kapali = ",".join("?" * len(KAPALI_IS_DURUMLARI))
        try:
            for i in range(0, len(nolar), 500):
                parca = nolar[i:i + 500]
                for r in conn.execute(
                        "SELECT TRIM(musteri_no) m, task_adi, COALESCE(boss_task_no, is_no) t, satis_kanali, "
                        f"CASE WHEN durum IN ({kapali}) THEN 1 ELSE 0 END kapali, acilis FROM is_emri "
                        f"WHERE TRIM(musteri_no) IN ({','.join('?' * len(parca))})",
                        (*KAPALI_IS_DURUMLARI, *parca)).fetchall():
                    sira = (-int(r["kapali"]), r["acilis"] or "")     # açık önce, sonra en yeni
                    if r["m"] not in bulunan or sira > bulunan[r["m"]][0]:
                        bulunan[r["m"]] = (sira, r["task_adi"] or "", r["t"] or "", r["satis_kanali"] or "")
        except sqlite3.Error:
            bulunan = {}
    for k in kartlar:
        b = bulunan.get(ilkler[k["id"]] or "")
        k["task_adi"], k["task_no"] = (b[1], b[2]) if b else ("", "")
        k["satis_kanali"] = (b[3] if b else "") or k.get("kanal") or ""


# ----------------------------------------------------------------------------- ticket'ın işleri (Task No · satış kanalı)
EN_COK_SECENEK = 500
BENZER_GUN = 180


def _kurulum_mu(task_adi) -> bool:
    return "KURULUM" in _sade(task_adi or "")


def _kanal_sikayeti_mi(task_adi) -> bool:
    try:
        from operasyon.v2.uyari import kanal_sikayeti_mi
    except ImportError:                                  # yalnız satış kurulumu: iş modülü yok
        return "KANALSIKAYET" in _sade(task_adi or "")
    return kanal_sikayeti_mi(task_adi)


def _uyarici(conn: sqlite3.Connection):
    """TASKS'taki ⚠ kanal şikâyeti uyarısının AYNISI (``operasyon/v2/uyari.py`` → ``Uyarilar``); yoksa None."""
    try:
        from operasyon.v2.uyari import Uyarilar
        return Uyarilar(conn)
    except (ImportError, sqlite3.Error):
        return None


def _kanal_uyarisi(u, is_: dict) -> str:
    if u is None or not is_.get("is_no"):
        return ""
    try:
        sonuc = u._kanal({"task_adi": is_.get("task_adi"), "musteri_no": is_.get("musteri_no"),
                          "is_no": is_["is_no"]})
    except (KeyError, TypeError):
        return ""
    return (sonuc or {}).get("metin") or ""


def _ham_kanallar(conn: sqlite3.Connection, task_nolar) -> dict[str, str]:
    """``is_emri.satis_kanali`` boşsa BOSS ham alanı ``saleChannel`` (``boss_ham``)."""
    nolar = sorted({str(t) for t in task_nolar if t})
    out: dict[str, str] = {}
    try:
        for i in range(0, len(nolar), 500):
            parca = nolar[i:i + 500]
            for r in conn.execute("SELECT task_no, json_extract(veri, '$.saleChannel') FROM boss_ham "
                                  f"WHERE task_no IN ({','.join('?' * len(parca))})", parca):
                if r[1]:
                    out[str(r[0])] = str(r[1]).strip()
    except sqlite3.Error:
        return {}
    return out


_IS_ALANLARI = ("is_no, COALESCE(boss_task_no, is_no) AS task_no, task_adi, satis_kanali, boss_durum, adres, "
                "TRIM(musteri_no) AS musteri_no, lokasyon, bina_serial, durum, acilis, bizim_durum, ticket_id")


_KAPANIS_BOSS = ("TAMAMLAND", "IPTAL")          # BOSS durumu: Tamamlandı · İptal · FOX iptal (…) — sade biçimde


def is_kapandi_mi(d: dict) -> bool:
    """İş kapandı mı: bizim durum kapalı (``cozuldu``/``kapandi``) ya da BOSS durumu Tamamlandı / İptal / FOX iptal."""
    if d.get("durum") in ("cozuldu", "kapandi"):
        return True
    b = _sade(d.get("boss_durum") or "")
    return bool(b) and any(x in b for x in _KAPANIS_BOSS)


def _is_satiri(r, ham: dict[str, str], kisisel: bool) -> dict:
    d = dict(r)
    kapali = d.get("durum") in ("cozuldu", "kapandi")
    return {
        "is_no": d["is_no"], "task_no": d["task_no"] or "", "task_adi": d.get("task_adi") or "",
        "satis_kanali": (d.get("satis_kanali") or "").strip() or ham.get(str(d["task_no"]), ""),
        "boss_durum": d.get("boss_durum") or "", "adres": (d.get("adres") or "") if kisisel else "",
        "musteri_no": (d.get("musteri_no") or "") if kisisel else "", "lokasyon": (d.get("lokasyon") or "").strip(),
        "bina_serial": d.get("bina_serial"), "acik": not kapali, "acilis": d.get("acilis"),
        "kurulum": _kurulum_mu(d.get("task_adi")), "kanal_sikayeti": _kanal_sikayeti_mi(d.get("task_adi")),
    }


def is_secenekleri(conn: sqlite3.Connection, musteri: str | None = None, lokasyon: str | None = None,
                   kisisel: bool = True) -> dict:
    """Yeni ticket / "+ abone ekle" seçicisi: müşteri no'ların (virgülle çok) ve/veya Loc ID'nin AÇIK işleri.

    Her iş: Task No, Task adı, satış kanalı, BOSS durumu, adres ve müşteri no (yalnız ``kisisel``), ⚠ kanal
    şikâyeti uyarısı (TASKS'la aynı). Sıra: kurulum işleri önce, sonra en yeni. ``varsayilan``: kurulum işi (kanal
    şikâyeti asla); kurulum yoksa ve tek iş varsa o. ``benzer``: aynı lokasyon/binada son 180 günün ticket'ları.
    """
    from .yetki import KAPALI_IS_DURUMLARI

    nolar = musteri_nolari(musteri)[:50]
    kosul, deger = [], []
    if nolar:
        kosul.append(f"TRIM(musteri_no) IN ({','.join('?' * len(nolar))})")
        deger += nolar
    b = None
    adaylar = _lokasyon_adaylari(lokasyon)
    if adaylar:
        b = lokasyondan_bina(conn, lokasyon or "")
        kosul.append(f"UPPER(TRIM(lokasyon)) IN ({','.join('?' * len(adaylar))})")
        deger += adaylar
        if b:
            kosul.append("bina_serial=?")
            deger.append(b["bina_serial"])
    satirlar = []
    if kosul:
        kapali = ",".join("?" * len(KAPALI_IS_DURUMLARI))
        try:
            satirlar = conn.execute(
                f"SELECT {_IS_ALANLARI} FROM is_emri WHERE ({' OR '.join(kosul)}) AND durum NOT IN ({kapali}) "
                "ORDER BY acilis DESC, is_no DESC LIMIT ?", (*deger, *KAPALI_IS_DURUMLARI, EN_COK_SECENEK + 1)
            ).fetchall()
        except sqlite3.Error:
            satirlar = []
    fazla = len(satirlar) > EN_COK_SECENEK
    satirlar = satirlar[:EN_COK_SECENEK]
    ham = _ham_kanallar(conn, [r["task_no"] for r in satirlar if not (r["satis_kanali"] or "").strip()])
    u = _uyarici(conn) if satirlar else None
    isler = []
    for r in satirlar:
        x = _is_satiri(r, ham, kisisel)
        x["uyari"] = _kanal_uyarisi(u, dict(r))
        isler.append(x)
    isler.sort(key=lambda x: (not x["kurulum"] or x["kanal_sikayeti"]))     # kararlı: kurulum önce, en yeni
    kurulum = [x["task_no"] for x in isler if x["kurulum"] and not x["kanal_sikayeti"]]
    varsayilan = kurulum[:1] or ([isler[0]["task_no"]] if len(isler) == 1 and not isler[0]["kanal_sikayeti"] else [])
    # Toptan müşteri (tek müşteri no yüzlerce abone; ör. 23722338): müşteri no ile aranınca hiçbir iş kendiliğinden
    # seçilmez — abone Loc ID ile ya da elle seçilir (ilişki abone düzeyinde: operasyon/v2/iliskili.py Iliski).
    toptan = False
    if nolar and isler:
        try:
            from . import ticket_boss_not as tbn
            toptan = tbn.toptan_mi(isler, tbn._ham(conn, [x["task_no"] for x in isler[:tbn.TOPTAN_ACIK_IS + 1]]))
        except ImportError:
            toptan = False
        if toptan and not adaylar:
            varsayilan = []
    loklar = {x["lokasyon"] for x in isler if x["lokasyon"]} | ({(lokasyon or "").strip()} - {""})
    binalar = {x["bina_serial"] for x in isler if x["bina_serial"]} | ({b["bina_serial"]} if b else set())
    return {"isler": isler, "fazla": fazla, "varsayilan": varsayilan, "toptan": toptan,
            "lokasyon": (b or {}).get("location_id") or next(iter(sorted(loklar)), ""),
            "bina_serial": (b or {}).get("bina_serial"), "site": site_adi(b) if b else "",
            "benzer": benzer_ticketlar(conn, loklar, binalar)}


def benzer_ticketlar(conn: sqlite3.Connection, lokasyonlar, bina_serialler=(), gun: int = BENZER_GUN,
                     haric: int | None = None) -> list[dict]:
    """Aynı lokasyonda (Loc ID anahtarı ya da bina) açık ya da son ``gun`` günde kapanmış ticket'lar —
    yeni ticket'ta engellemeyen uyarı ("Bu lokasyonda 12.09'da açılmış (Çözüldü) ticket var")."""
    import datetime as dt

    anahtarlar = {lokasyon_anahtari(x) for x in lokasyonlar or () if x} - {""}
    binalar = {x for x in bina_serialler or () if x}
    if not anahtarlar and not binalar:
        return []
    sema(conn)
    sinir = (ayarlar.bugun() - dt.timedelta(days=gun)).isoformat()
    out = []
    for r in conn.execute(
            "SELECT t.id, t.ticket_no, t.acilis, t.olusturma, t.durum, t.konu, t.location_id, t.bina_serial, "
            "t.kapanis, b.location_id AS bina_loc FROM ticket t LEFT JOIN bina b ON b.bina_serial=t.bina_serial "
            "WHERE (t.durum IN ('AÇIK','HATA','TRANSFER','BÖLGE') "
            "OR COALESCE(t.kapanis, t.guncelleme, t.olusturma) >= ?) ORDER BY t.id DESC", (sinir,)):
        if haric is not None and r["id"] == haric:
            continue
        if (r["bina_serial"] and r["bina_serial"] in binalar) or anahtarlar & {
                lokasyon_anahtari(r["location_id"]), lokasyon_anahtari(r["bina_loc"])}:
            out.append({"id": r["id"], "ticket_no": r["ticket_no"] or "", "durum": r["durum"], "konu": r["konu"],
                        "acilis": r["acilis"] or (r["olusturma"] or "")[:10], "acik": r["durum"] in ACIK_DURUMLAR})
    return out[:20]


def _is_bul(conn: sqlite3.Connection, task_nolar) -> list[sqlite3.Row]:
    nolar = list(dict.fromkeys(str(t).strip() for t in task_nolar or () if str(t or "").strip()))[:EN_COK_SECENEK]
    if not nolar:
        return []
    soru = ",".join("?" * len(nolar))
    try:
        satirlar = conn.execute(f"SELECT {_IS_ALANLARI} FROM is_emri WHERE boss_task_no IN ({soru}) "
                                f"OR is_no IN ({soru})", (*nolar, *nolar)).fetchall()
    except sqlite3.Error:
        return []
    sira = {n: i for i, n in enumerate(nolar)}
    return sorted(satirlar, key=lambda r: sira.get(str(r["task_no"]), sira.get(str(r["is_no"]), 10 ** 6)))


def _gecmis_notu(conn: sqlite3.Connection, ticket_id: int, yapan_id: int | None, notu: str) -> None:
    durum = conn.execute("SELECT durum FROM ticket WHERE id=?", (ticket_id,)).fetchone()[0]
    conn.execute("INSERT INTO ticket_gecmis (ticket_id, zaman, kullanici_id, eski_durum, yeni_durum, notu) "
                 "VALUES (?,?,?,?,?,?)", (ticket_id, ayarlar.zaman_metni(), yapan_id, durum, durum, notu))


def isleri_ekle(conn: sqlite3.Connection, ticket_id: int, task_nolar, yapan_id: int | None = None,
                not_yaz: bool = True) -> dict:
    """Ticket'a iş(ler) ekler (``ticket_is``; tekrar eklemek etkisiz). İşin kendisine DOKUNMAZ.

    Ticket'ın Müşteri No hücresine yeni müşteri no'lar eklenir; Loc ID boşsa ilk işinkinden dolar.
    Dönüş: {eklenen: [task no], bulunmayan: [istenip bulunamayan]}.
    """
    sema(conn)
    t = conn.execute("SELECT id, musteri, location_id FROM ticket WHERE id=?", (ticket_id,)).fetchone()
    if not t:
        raise LookupError("Ticket bulunamadı.")
    istenen = list(dict.fromkeys(str(x).strip() for x in task_nolar or () if str(x or "").strip()))
    satirlar = _is_bul(conn, istenen)
    bulunan = {str(r["task_no"]) for r in satirlar} | {str(r["is_no"]) for r in satirlar}
    ham = _ham_kanallar(conn, [r["task_no"] for r in satirlar if not (r["satis_kanali"] or "").strip()])
    simdi = ayarlar.zaman_metni()
    eklenen = []
    for r in satirlar:
        x = _is_satiri(r, ham, True)
        n = conn.execute(
            "INSERT OR IGNORE INTO ticket_is (ticket_id, task_no, is_no, task_adi, satis_kanali, musteri_no, "
            "lokasyon, ekleme) VALUES (?,?,?,?,?,?,?,?)",
            (ticket_id, x["task_no"], x["is_no"], x["task_adi"] or None, x["satis_kanali"] or None,
             x["musteri_no"] or None, x["lokasyon"] or None, simdi)).rowcount
        if n:
            eklenen.append(x)
    if eklenen:
        nolar = musteri_nolari(t["musteri"])
        yeni_m = [x["musteri_no"] for x in eklenen if x["musteri_no"] and x["musteri_no"] not in nolar]
        alan: dict = {}
        if yeni_m:
            alan["musteri"] = ", ".join(dict.fromkeys([*nolar, *yeni_m]))
        if not (t["location_id"] or "").strip() and eklenen[0]["lokasyon"]:
            alan["location_id"] = eklenen[0]["lokasyon"].upper()
        if alan:
            conn.execute(f"UPDATE ticket SET {', '.join(f'{a}=?' for a in alan)}, guncelleme=? WHERE id=?",
                         (*alan.values(), simdi, ticket_id))
        if not_yaz:
            ozet = ", ".join(x["task_no"] for x in eklenen[:10]) + (f" (+{len(eklenen) - 10})" if len(eklenen) > 10 else "")
            _gecmis_notu(conn, ticket_id, yapan_id, f"İş eklendi: Task {ozet}")
    return {"eklenen": [x["task_no"] for x in eklenen], "bulunmayan": [n for n in istenen if n not in bulunan]}


def is_cikar(conn: sqlite3.Connection, ticket_id: int, task_no: str, yapan_id: int | None = None) -> bool:
    """Seçilen işi ticket'tan çıkarır (yalnız ``ticket_is``; kurulum engeli bağı İş çekmecesinden ayrılır)."""
    sema(conn)
    n = conn.execute("DELETE FROM ticket_is WHERE ticket_id=? AND task_no=?", (ticket_id, str(task_no))).rowcount
    if n:
        _gecmis_notu(conn, ticket_id, yapan_id, f"İş çıkarıldı: Task {task_no}")
    return bool(n)


def _task_bilgileri(conn: sqlite3.Connection, kartlar: list[dict]) -> None:
    """Liste/kart için (yerinde): ``isler`` = seçilen işler (``ticket_is``) + kurulum engeliyle bağlı işler
    (``is_emri.ticket_id``), tekrarsız; ``task_no`` (virgüllü), ``task_adi`` (ilk işin; çoksa "+N"),
    ``satis_kanali`` (işlerin; yoksa ticket'ın eski Kanal alanı), ``musteriler`` (ticket + işler, tekrarsız),
    ``uyari`` (⚠ kanal şikâyeti, TASKS'la aynı). İşi olmayan ticket'ta ilk müşteri no'sunun işi (eski davranış)."""
    if not kartlar:
        return
    sema(conn)
    idler = [k["id"] for k in kartlar]
    secilen: dict[int, list[str]] = {}
    bagli: dict[int, list[str]] = {}
    for i in range(0, len(idler), 500):
        parca = idler[i:i + 500]
        soru = ",".join("?" * len(parca))
        for r in conn.execute(f"SELECT ticket_id, task_no FROM ticket_is WHERE ticket_id IN ({soru}) "
                              "ORDER BY ekleme, rowid", parca):
            secilen.setdefault(int(r[0]), []).append(str(r[1]))
        try:
            for r in conn.execute(f"SELECT ticket_id, COALESCE(boss_task_no, is_no) FROM is_emri "
                                  f"WHERE ticket_id IN ({soru}) ORDER BY acilis, is_no", parca):
                bagli.setdefault(int(r[0]), []).append(str(r[1]))
        except sqlite3.Error:
            pass
    saklanan: dict[tuple, sqlite3.Row] = {}
    if secilen:
        for r in conn.execute(f"SELECT * FROM ticket_is WHERE ticket_id IN ({','.join('?' * len(secilen))})",
                              list(secilen)):
            saklanan[(int(r["ticket_id"]), str(r["task_no"]))] = r
    hepsi = {n for v in (*secilen.values(), *bagli.values()) for n in v}
    canli = {str(r["task_no"]): r for r in _is_bul(conn, hepsi)} if hepsi else {}
    ham = _ham_kanallar(conn, [n for n in hepsi if n not in canli or not (canli[n]["satis_kanali"] or "").strip()])
    u = _uyarici(conn) if hepsi else None
    yedek = []
    for k in kartlar:
        sira = list(dict.fromkeys([*secilen.get(k["id"], []), *bagli.get(k["id"], [])]))
        isler = []
        for n in sira:
            r = canli.get(n)
            if r is not None:
                x = _is_satiri(r, ham, True)
            else:                                        # iş artık yok: seçilirken saklanan bilgi
                s = saklanan.get((k["id"], n))
                x = {"is_no": (s["is_no"] if s else None) or n, "task_no": n,
                     "task_adi": (s["task_adi"] if s else "") or "",
                     "satis_kanali": (s["satis_kanali"] if s else "") or "", "boss_durum": "", "adres": "",
                     "musteri_no": (s["musteri_no"] if s else "") or "", "lokasyon": (s["lokasyon"] if s else "") or "",
                     "bina_serial": None, "acik": False, "acilis": None, "kurulum": False, "kanal_sikayeti": False}
            x["secildi"] = n in secilen.get(k["id"], [])
            x["bagli"] = n in bagli.get(k["id"], [])
            x["kapandi"] = r is not None and is_kapandi_mi(dict(r))
            x["uyari"] = _kanal_uyarisi(u, dict(r)) if r is not None and x["acik"] else ""
            isler.append(x)
        k["isler"] = isler
        if isler:
            ilk = next((x for x in isler if x["secildi"]), isler[0])
            k["task_no"] = ", ".join(x["task_no"] for x in isler)
            k["task_adi"] = ilk["task_adi"] + (f" +{len(isler) - 1}" if len(isler) > 1 else "")
            k["satis_kanali"] = ", ".join(dict.fromkeys(x["satis_kanali"] for x in isler if x["satis_kanali"])) \
                or k.get("kanal") or ""
            k["uyari"] = next((x["uyari"] for x in isler if x["uyari"]), "")
        else:
            yedek.append(k)
            k["uyari"] = ""
        # Bağlı işlerin HEPSİ BOSS'ta kapandı (Tamamlandı / İptal / FOX iptal): ticket'ı takip etmeye gerek yok.
        k["isi_kapandi"] = bool(isler) and k.get("acik", False) and all(x["kapandi"] for x in isler)
        k["musteriler"] = list(dict.fromkeys([*musteri_nolari(k.get("musteri")),
                                              *(x["musteri_no"] for x in isler if x["musteri_no"])]))
    _ilk_musteri_isi(conn, yedek)


# ----------------------------------------------------------------------------- kalıcı silme (iz bırakmaz)
TEMIZLIK_GUN = 90
# Ticket'a ait bütün satırlar (sıra: önce çocuklar, sonra ``ticket``; FK açık). ``ticket_silme`` eski yumuşak silmeden
# kalmış olabilir (``ticket_temizlik.silinenler_calistir`` kaldırır).
_TICKET_TABLOLARI = ("ticket_is", "ticket_gecmis", "ticket_ek", "ticket_boss_not", "ticket_boss_aski", "ticket_silme")


def _ayir(conn: sqlite3.Connection, ticket_id: int, k: dict | None) -> list[str]:
    """Bağlı AÇIK işleri ticket'tan ayırır (``akis.ticket_ayir``: yalnız bağ; 'altyapi' bekleyen iş bekliyor'a);
    kapanmış işlerin bağı olaysız boşalır. Dönüş: ayrılan AÇIK işler."""
    try:
        nolar = [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE ticket_id=? AND durum NOT IN "
                                            "('cozuldu','kapandi') ORDER BY is_no", (ticket_id,))]
    except sqlite3.Error:
        return []                                     # iş emri tablosu yok
    try:
        from operasyon.v2 import akis
    except ImportError:
        akis = None
    for no in nolar:
        if akis is not None:
            akis.ticket_ayir(conn, no, k)
    conn.execute("UPDATE is_emri SET ticket_id=NULL WHERE ticket_id=?", (ticket_id,))
    return nolar


def _satirlari_sil(conn: sqlite3.Connection, ticket_id: int) -> None:
    var = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for tablo in _TICKET_TABLOLARI:
        if tablo in var:
            conn.execute(f"DELETE FROM {tablo} WHERE ticket_id=?", (ticket_id,))
    conn.execute("DELETE FROM ticket WHERE id=?", (ticket_id,))


def fotolari_sil(idler, ek_kok=None) -> int:
    """Silinen ticket'ların fotoğraf klasörleri (``ek/ticket/<id>``, küçük resimler dahil) diskten silinir.
    Veritabanı işlemi BAŞARIYLA bittikten sonra çağrılır. Dönüş: silinen klasör sayısı."""
    import shutil
    from pathlib import Path

    if ek_kok is None:
        from . import ek_dosya
        ek_kok = ek_dosya.ek_kok()
    n = 0
    for tid in idler:
        d = Path(ek_kok) / "ticket" / str(int(tid))
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    return n


def toplu_sil(conn: sqlite3.Connection, idler, k: dict | None) -> dict:
    """KALICI silme, tek işlemde (hata → hiçbir şey silinmez): bağlı işler ayrılır (``_ayir``), ticket'ın bütün
    satırları silinir (``_TICKET_TABLOLARI`` + ``ticket``), sonra fotoğraf klasörleri. yonetim_kaydi yazılmaz.
    Olmayan kimlik atlanır. Dönüş: ``{"silinen": n, "silinen_idler": [...], "ayrilan_is": [...]}``."""
    sema(conn)
    if conn.in_transaction:
        conn.commit()
    sonuc: dict = {"silinen": 0, "silinen_idler": [], "ayrilan_is": []}
    conn.execute("BEGIN IMMEDIATE")
    try:
        for tid in dict.fromkeys(int(x) for x in idler):
            if not conn.execute("SELECT 1 FROM ticket WHERE id=?", (tid,)).fetchone():
                continue
            sonuc["ayrilan_is"] += _ayir(conn, tid, k)
            _satirlari_sil(conn, tid)
            sonuc["silinen_idler"].append(tid)
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    sonuc["silinen"] = len(sonuc["silinen_idler"])
    fotolari_sil(sonuc["silinen_idler"])
    return sonuc


def sil(conn: sqlite3.Connection, ticket_id: int, k: dict | None) -> dict:
    """Tek ticket'ı KALICI siler (``toplu_sil``). Yoksa ``LookupError``."""
    if not conn.execute("SELECT 1 FROM ticket WHERE id=?", (ticket_id,)).fetchone():
        raise LookupError("Ticket bulunamadı.")
    s = toplu_sil(conn, [ticket_id], k)
    return {"silindi": bool(s["silinen"]), "ayrilan_is": s["ayrilan_is"]}


def eski_cozulenler(conn: sqlite3.Connection, gun: int = TEMIZLIK_GUN) -> list[int]:
    """Toplu temizlik adayları: ÇÖZÜLDÜ, kapanışı (yoksa son güncellemesi) ``gun`` günden eski."""
    import datetime as dt

    sinir = (ayarlar.bugun() - dt.timedelta(days=gun)).isoformat()
    return [int(r[0]) for r in conn.execute(
        "SELECT t.id FROM ticket t WHERE t.durum='ÇÖZÜLDÜ' "
        "AND COALESCE(t.kapanis, t.guncelleme) < ? ORDER BY t.id", (sinir,))]


# ----------------------------------------------------------------------------- çözülünce: seçilen işler de aranır
def secilen_isler_aranacak(conn: sqlite3.Connection, ticket_id: int, k: dict | None) -> list[str]:
    """Ticket ÇÖZÜLDÜ/KAPATILDI olunca seçilen (``ticket_is``) AÇIK işlerin Bizim durumu "Aranacak" olur — kurulum
    engeliyle bağlı işlerdeki kuralın aynısı (``akis.ticket_degisti``): Bizim durumu boş ya da engel etiketi olan iş;
    "İptal" (ya da başka bir etiket) olana dokunulmaz. Bu ticket'a bağlı işleri ``ticket_degisti`` işler (atlanır).
    Dönüş: değişen iş no'lar."""
    try:
        from operasyon.v2 import akis
        from operasyon.v2.islem import islem
    except ImportError:
        return []
    t = conn.execute("SELECT durum FROM ticket WHERE id=?", (ticket_id,)).fetchone()
    if t is None or t["durum"] not in ("ÇÖZÜLDÜ", "KAPATILDI"):
        return []
    sema(conn)
    nolar = [r[0] for r in conn.execute("SELECT task_no FROM ticket_is WHERE ticket_id=?", (ticket_id,))]
    donen = []
    with islem(conn):
        for r in _is_bul(conn, nolar):
            if r["durum"] in ("cozuldu", "kapandi") or r["ticket_id"] == ticket_id:
                continue
            b = r["bizim_durum"]
            if b and b not in akis.ENGEL_KONU:
                continue
            akis.yaz(conn, akis.is_getir(conn, r["is_no"]), {"bizim_durum": akis.BIZIM_ARANACAK}, k, "bizim_durum",
                     notu=akis.ENGEL_COZULDU_NOTU)
            donen.append(r["is_no"])
    return donen


def task_nolari(conn: sqlite3.Connection, is_nolar) -> list[str]:
    """İş no → BOSS task no (bildirimde gösterilir)."""
    nolar = list(dict.fromkeys(is_nolar or ()))
    if not nolar:
        return []
    try:
        es = {r[0]: r[1] for r in conn.execute(
            f"SELECT is_no, COALESCE(boss_task_no, is_no) FROM is_emri WHERE is_no IN ({','.join('?' * len(nolar))})",
            nolar)}
    except sqlite3.Error:
        es = {}
    return [str(es.get(n, n)) for n in nolar]
