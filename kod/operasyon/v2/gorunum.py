"""Role göre kırpılmış iş satırı ve ayrıntısı — müşteri bilgisinin çıktığı TEK yer (F21, spec §2.5, §5.2).

- Operasyon ve yönetici: tam müşteri adı, no, adres, BOSS ekip adı.
- Teknik: yalnız kendisine atanmış AÇIK işte kısa ad ("Ayşe K.") + no + adres. Kapanınca görmez.
- Yetkisiz yanıtta anahtar HİÇ yoktur (null değil).
Alan adları ``kod/arayuz/src/is/tipler.ts`` ile birebir aynıdır.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3

from operasyon import is_emri as ie

from . import akis, aski, kisi, kurallar, siralama, zaman
from .hatalar import IsYok

_BTK_48 = dt.timedelta(hours=48)
_ACIK_TICKET = ("AÇIK", "HATA", "TRANSFER")


def kisa_ad(ad) -> str:
    return kisi.kisa_ad(ad)


def kisa_adres(adres: str | None, bina: dict | None, mahalle: str | None = None) -> str | None:
    """"Görükle · X Sitesi": mahalle + bina/site adı (yoksa adresin mahalle işaretinden önceki kısmı)."""
    yer = None
    if bina:
        for alan in ("site_adi", "crm_site_adi", "bina_ad"):
            v = (bina.get(alan) or "").strip()
            if v and v.lower() not in ("null", "nan", "-", "none"):
                yer = v
                break
    if not yer and adres:
        on = re.split(r"\b(?:Mah(?:allesi)?|MAH(?:ALLESİ)?|Mh|MH)\.?\b", str(adres), maxsplit=1)[0]
        on = re.sub(r"\([^)]*\)", " ", on).strip(" ,.-")
        kelime = on.split()
        if kelime:
            yer = " ".join(kelime[:4])
    parca = [p for p in (mahalle, yer) if p]
    return " · ".join(dict.fromkeys(parca)) or None


def _ayar(conn, anahtar, varsayilan=None):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else varsayilan


# ----------------------------------------------------------------------------- bağlam
class Baglam:
    """Bir yanıttaki bütün satırlar için bir kez okunan tablolar (437 iş < 150 ms)."""

    def __init__(self, conn: sqlite3.Connection, k: dict | None, simdi: dt.datetime | None = None, is_nolar=None):
        self.conn = conn
        self.k = k
        self.simdi = simdi or zaman.simdi()
        self.s = zaman.metin(self.simdi)
        self.ofis = kisi.ofis_mu(conn, k) if k else True
        self.teknik = kisi.teknik_mi(conn, k) if k else False
        self.kid = (k or {}).get("id")
        self.obekler = {r[0]: {"id": r[0], "ad": r[1], "renk": r[2]} for r in
                        conn.execute("SELECT id, ad, renk FROM obek")}
        self.kisiler = kisi.kisiler(conn)
        try:
            t = conn.execute("SELECT bina_serial, COUNT(*) FROM ticket WHERE bina_serial IS NOT NULL AND durum IN "
                             "('AÇIK','HATA','TRANSFER') GROUP BY bina_serial").fetchall()
            self.bina_ticket = {r[0]: r[1] for r in t}
        except sqlite3.OperationalError:
            self.bina_ticket = {}
        self.ticketlar: dict[int, dict] = {}
        self.araliklar = aski.araliklar(conn, is_nolar)
        self.son24_durur = aski.son24_durur(conn)
        self.boss_h = kisi.boss_ekip_haritasi(conn) if self.ofis else {}
        # EK-12: öncelik, BTK şikâyet sayacı (iş günü), tatiller — yanıt boyunca bir kez
        self.oncelik_kural = kurallar.oku(conn, "oncelikli_isler")
        self.btk_kural = kurallar.oku(conn, "btk_sikayet")
        self.tatiller = kurallar.oku(conn, "resmi_tatiller")
        self.btk = akis.btk_bilgileri(conn, is_nolar)
        self._oncelik: dict[str, str | None] = {}

    def oncelik(self, task_adi: str) -> str | None:
        """Öncelik kuralı iş tipi başına bir kez eşlenir (437 işte ≈40 farklı tip; düzenli ifade her satırda değil)."""
        if task_adi not in self._oncelik:
            self._oncelik[task_adi] = kurallar.oncelik(self.oncelik_kural, task_adi)
        return self._oncelik[task_adi]

    def ticket(self, tid):
        if tid is None:
            return None
        if tid not in self.ticketlar:
            r = self.conn.execute("SELECT id, konu, durum, acilis, olusturma FROM ticket WHERE id=?", (tid,)).fetchone()
            self.ticketlar[tid] = dict(r) if r else None
        t = self.ticketlar[tid]
        return {"id": t["id"], "konu": t["konu"], "durum": t["durum"], "gun": akis.ticket_gun(t)} if t else None

    def musteri_izni(self, r) -> str | None:
        """'tam' · 'kisa' (teknikte kendi açık işi) · None."""
        if self.k is None or self.ofis:
            return "tam"
        if self.teknik and r["atanan_id"] == self.kid and r["durum"] in akis.ACIK:
            return "kisa"
        return None


_SATIR_SQL = ("SELECT e.*, b.site_adi AS b_site_adi, b.crm_site_adi AS b_crm_site_adi, b.ad AS b_ad, "
              "b.location_id AS b_location_id, b.lat AS b_lat, b.lon AS b_lon FROM is_emri e "
              "LEFT JOIN bina b ON b.bina_serial = e.bina_serial")


def _renk(r, net: dict, simdi: dt.datetime) -> tuple[str, bool]:
    if r["durum"] not in akis.ACIK:
        return "yesil", False
    acilis = zaman.oku(r["acilis"])
    if r["serit"] == "BTK" and r["btk_hedef_saat"] and net.get("btk_net_gecen_dk") is not None:
        oran = net["btk_net_gecen_dk"] / (r["btk_hedef_saat"] * 60)
    else:
        hedef = zaman.oku(net.get("son24_net") or r["son24"])
        toplam = (hedef - acilis).total_seconds() if hedef and acilis else 0
        oran = (simdi - acilis).total_seconds() / toplam if toplam > 0 else 1
    if oran >= 1:
        return "kirmizi", True
    return ("yesil" if oran < 0.5 else "amber" if oran < 0.8 else "kirmizi"), False


def _rozetler(r, b: Baglam) -> list[str]:
    z = []
    if r["serit"] == "BTK":
        z.append("btk")
    if r["ticket_id"] or b.bina_ticket.get(r["bina_serial"]):
        z.append("ticket")
    if r["tekrar7g"]:
        z.append("tekrar")
    if r["kaynak"] == "bayi" or r["kanal_grubu"] == "dehanet":
        z.append("bayi")
    if r["kanal_grubu"] == "global":
        z.append("global")
    if r["konum_yaklasik"]:
        z.append("konum")
    if r["boss_bekleyen"] and not r["boss_islendi"]:
        z.append("boss_islenecek")
    if r["boss_kapanmadi"]:
        z.append("boss_acik")
    if (r["acilma_sayisi"] or 1) > 1:
        z.append("yeniden")
    if r["obek_elle_id"]:
        z.append("elle")
    return z


def _benzer_mahalle(conn, r) -> str | None:
    from . import sozluk
    adaylar = conn.execute("SELECT ad, mahalle_k FROM mahalle WHERE il_k=? AND ilce_k=?", (r["il_k"], r["ilce_k"])).fetchall()
    for ad, mk in adaylar:
        if sozluk.benzer_mi(mk, r["mahalle_k"] or ""):
            return ad
    return None


def satir(conn: sqlite3.Connection, r, k: dict | None, b: Baglam | None = None) -> dict:
    """Arayüze giden ``IsSatir``."""
    from .aktarim import triyaj_metni
    b = b or Baglam(conn, k, is_nolar=[r["is_no"]])
    simdi = b.simdi
    net = aski.hesap(b.araliklar.get(r["is_no"]), r["acilis"], r["btk_hedef"], simdi, r["son24"], b.son24_durur)
    renk, gecikti = _renk(r, net, simdi)
    kova = akis.KOVALAR[r["durum"]]
    son24 = net.get("son24_net") or r["son24"]
    obek_id = r["obek_elle_id"] or r["obek_id"]
    o = b.obekler.get(obek_id) if obek_id else None
    randevu = None
    if r["randevu_bas"]:
        randevu = {"bas": r["randevu_bas"], "bit": r["randevu_bit"], "teyitli": bool(r["randevu_teyitli"]), "kaynak": "biz"}
    elif r["boss_randevu_bas"] and r["boss_randevu_bit"] and r["durum"] in akis.ACIK:
        randevu = {"bas": r["boss_randevu_bas"], "bit": r["boss_randevu_bit"], "teyitli": False, "kaynak": "boss"}
    oneri = None
    if r["atanan_id"] is None and r["oneri_teknik_id"] and r["durum"] in akis.ACIK:
        t = b.kisiler.get(r["oneri_teknik_id"])
        if t:
            oneri = {"teknik": kisi.ozet(t), "bas": r["oneri_bas"], "bit": r["oneri_bit"], "neden": r["oneri_neden"] or ""}
    triyaj_m = None
    if r["triyaj_nedeni"]:
        triyaj_m = triyaj_metni(r["triyaj_nedeni"], r["il"], r["ilce"], r["mahalle"],
                                _benzer_mahalle(conn, r) if r["triyaj_nedeni"] == "mahalle_benzer" else None)
    s = {
        "is_no": r["is_no"], "boss_task_no": r["boss_task_no"], "kaynak": r["kaynak"], "kanal_grubu": r["kanal_grubu"],
        "task_adi": r["task_adi"], "serit": r["serit"], "btk_hedef_saat": r["btk_hedef_saat"],
        "durum": r["durum"], "kova": kova, "durum_zamani": r["durum_zamani"],
        "il": r["il"], "ilce": r["ilce"], "mahalle": r["mahalle"],
        "obek": dict(o) if o else None, "obek_elle": bool(r["obek_elle_id"]),
        "triyaj_nedeni": r["triyaj_nedeni"], "triyaj_metni": triyaj_m,
        "konum_yaklasik": bool(r["konum_yaklasik"]), "lat": r["lat"], "lon": r["lon"],
        "acilis": r["acilis"], "son24": son24, "btk_hedef": r["btk_hedef"],
        "kalan_dk": int(round((zaman.oku(son24) - simdi).total_seconds() / 60)) if son24 else 0,
        "renk": renk, "gecikti": gecikti,
        "bekleme_dk": int(max(0, (simdi - zaman.oku(r["gorulme_zamani"])).total_seconds() // 60))
        if kova == "atanmadi" else None,
        "randevu": randevu,
        "atanan": kisi.ozet(b.kisiler.get(r["atanan_id"])) if r["atanan_id"] else None,
        "oneri": oneri,
        "ticket": b.ticket(r["ticket_id"]),
        "binada_acik_ticket": int(b.bina_ticket.get(r["bina_serial"], 0)) if r["bina_serial"] else 0,
        "rozetler": _rozetler(r, b),
        "kotu_gecmis": bool(r["kotu_gecmis"]), "sira": r["sira"], "surum": r["surum"],
        "btk_durdu": bool(net["btk_durdu"]) and r["serit"] == "BTK",
        "btk_hedef_net": net["btk_hedef_net"], "btk_kalan_dk": net["btk_kalan_dk"],
        # EK-12
        "oncelik": b.oncelik(r["task_adi"]) if r["durum"] in akis.ACIK else None,
        "btk_sikayet": kurallar.btk_sikayet_durumu(b.btk.get(r["is_no"]), (b.btk.get(r["is_no"]) or {}).get("tcs"),
                                                   simdi, b.btk_kural, b.tatiller) if r["is_no"] in b.btk else None,
        "genel_ariza": r["durum"] == "askida" and str(r["askida_neden"] or "").startswith("Genel arıza"),
    }
    izin = b.musteri_izni(r)
    if izin:
        bina = {"site_adi": r["b_site_adi"], "crm_site_adi": r["b_crm_site_adi"], "bina_ad": r["b_ad"]} \
            if "b_site_adi" in r.keys() and r["bina_serial"] else None
        s["musteri_adi"] = (r["musteri_adi"] if izin == "tam" else kisa_ad(r["musteri_adi"])) if r["musteri_adi"] else None
        s["musteri_no"] = r["musteri_no"]
        s["kisa_adres"] = kisa_adres(r["adres"], bina, r["mahalle"])
    if b.ofis:
        s["boss_ekip"] = r["boss_ekip"]
    return s


# ----------------------------------------------------------------------------- ayrıntı
_OLAY_ALAN = {"atanan_id": "teknisyen", "randevu_bas": "randevu", "durum": "durum", "obek_elle_id": "öbek",
              "ticket_id": "ticket", "mahalle": "mahalle", "adres": "adres", "musteri_adi": "müşteri adı",
              "musteri_no": "müşteri no", "task_adi": "iş tipi", "boss_durum": "BOSS durumu", "boss_ekip": "BOSS ekibi",
              "boss_randevu_bas": "BOSS randevusu", "lokasyon": "Location Id", "boss_son_aciklama": "BOSS açıklaması",
              "boss_sl": "SL", "obek_id": "öbek"}


def _dilim(bas, bit) -> str:
    b, s = zaman.oku(bas), zaman.oku(bit)
    if not b:
        return ""
    gun = "" if b.date() == zaman.simdi().date() else f"{b:%d.%m} "
    return f"{gun}{b:%H:%M}–{s:%H:%M}" if s else f"{gun}{b:%H:%M}"


def olay_ozeti(o: dict) -> str:
    """Olay → tek satır Türkçe ("Ali K.'ya atadı · 10:00–12:00")."""
    tur = o.get("tur")
    try:
        yeni = json.loads(o.get("yeni") or "{}") if isinstance(o.get("yeni"), str) else (o.get("yeni") or {})
        eski = json.loads(o.get("eski") or "{}") if isinstance(o.get("eski"), str) else (o.get("eski") or {})
    except ValueError:
        yeni, eski = {}, {}
    notu = o.get("notu")
    if tur == "olustu":
        return notu if yeni.get("kaynak") == "bayi" and notu else ("Bayi işi açıldı" if yeni.get("kaynak") == "bayi"
                                                                      else "Rapordan geldi")
    if tur == "aktarim_degisti":
        alanlar = [a for a in yeni if not a.startswith("_")]
        if "durum" in yeni:
            return f"Raporla {akis.ETIKET.get(yeni['durum'], yeni['durum'])} oldu" + (f" ({notu})" if notu else "")
        adlar = sorted({_OLAY_ALAN.get(a, a.replace("_", " ")) for a in alanlar})
        return "Raporda değişti: " + ", ".join(adlar[:4]) if adlar else (notu or "Raporda değişti")
    if tur == "yeniden_acildi":
        return "Raporda yeniden açıldı"
    if tur == "kayboldu":
        return notu or "BOSS listesinden düştü"
    if tur == "atama":
        if notu:
            return notu + (f" · {_dilim(yeni.get('randevu_bas'), yeni.get('randevu_bit'))}" if yeni.get("randevu_bas") else "")
        return "Atadı"
    if tur == "randevu":
        if yeni.get("randevu_bas"):
            return f"Randevu {_dilim(yeni['randevu_bas'], yeni.get('randevu_bit'))}" + (
                " · saat teyitli" if yeni.get("randevu_teyitli") else "")
        return notu or "Randevuyu kaldırdı"
    if tur in ("durum", "uyandi"):
        d = yeni.get("durum")
        metin = akis.ETIKET.get(d, d) if d else ""
        return f"{metin}" + (f" · {notu}" if notu and notu != metin else "") if metin else (notu or "Durum değişti")
    if tur == "not":
        return f"Not: {notu}" if notu else "Not ekledi"
    if tur == "iletisim":
        return "Müşteri telefonunu değiştirdi"
    if tur == "geri_al":
        return "Geri aldı"
    return notu or {"teknik_gordu": "Teknisyen gördü", "boss_islendi": "BOSS'a işlendi", "boss_bagla": "BOSS'a bağlandı",
                    "ticket": "Ticket değişti", "obek": "Öbek değişti", "mahalle": "Mahalle değişti",
                    "teshis": "Masa araması", "sira": "Sıra değişti"}.get(tur, "Değişti")


def soz_metni(acilis: str | None, mesai_bitis: str = "20:00") -> str:
    """Kesim kuralı (OT §3.3): 00–12 gelen → aynı gün; 12–17 → ertesi 12:00; 17–24 → ertesi 17:00."""
    a = zaman.oku(acilis)
    if a is None:
        return ""
    sa, dk = (int(x) for x in mesai_bitis.split(":")[:2])
    if a.hour < 12:
        son = a.replace(hour=sa, minute=dk, second=0)
    elif a.hour < 17:
        son = (a + dt.timedelta(days=1)).replace(hour=12, minute=0, second=0)
    else:
        son = (a + dt.timedelta(days=1)).replace(hour=17, minute=0, second=0)
    bugun = zaman.simdi().date()
    gun = "bugün" if son.date() == bugun else "yarın" if son.date() == bugun + dt.timedelta(days=1) \
        else "dün" if son.date() == bugun - dt.timedelta(days=1) else f"{son:%d.%m}"
    return f"Müşteriye söz: {gun} {son:%H:%M}'ye kadar"


def _birincil(r, b: Baglam) -> str | None:
    if not b.ofis:
        return None
    d = r["durum"]
    if d == "triyaj":
        return "obege_ata"
    if d in ("bekliyor", "randevulu"):
        if d == "bekliyor" and not r["ticket_id"] and b.bina_ticket.get(r["bina_serial"]):
            return "ticketa_bagla"
        return "ata"
    return {"ulasilamadi": "yeniden_ata", "askida": "uyandir", "altyapi": "ticketi_ac", "merkeze": "sahaya_al"}.get(d)


def _izinler(conn, r, b: Baglam) -> dict:
    ofis = b.ofis
    kendi = b.teknik and r["atanan_id"] == b.kid
    yollar = ({"operasyon"} if ofis else set()) | ({"teknik"} if kendi else set())
    durumlar = sorted({hedef for (kaynak, hedef), kural in akis.GECISLER.items()
                       if kaynak == r["durum"] and kural.roller & yollar and hedef != "kapandi"}
                      | ({"kapandi"} if ofis and r["kaynak"] == "bayi" and not r["boss_task_no"] and r["durum"] in akis.ACIK
                         else set()), key=akis.DURUMLAR.index)
    acik = r["durum"] in akis.ACIK
    return {"ata": ofis and (r["durum"], "atandi") in akis.GECISLER, "randevu": ofis and acik,
            "ticket": ofis and acik, "obek": ofis and r["durum"] != "kapandi",
            "iletisim": ofis and _ayar(conn, "musteri_tel", "kapali") == "acik",
            "durumlar": durumlar, "ofisten_kapat": ofis and acik, "yeniden_ac": ofis and r["durum"] == "cozuldu",
            "boss_bagla": ofis and r["kaynak"] == "bayi" and not r["boss_task_no"]}


def _bayi_oneri(conn, r) -> dict | None:
    if r["kaynak"] != "bayi" or r["boss_task_no"] or not r["musteri_ozet"]:
        return None
    a = zaman.oku(r["acilis"])
    adaylar = conn.execute(
        "SELECT boss_task_no FROM is_emri WHERE kaynak='boss' AND musteri_ozet=? AND task_adi=? AND acilis BETWEEN ? AND ?",
        (r["musteri_ozet"], r["task_adi"], zaman.metin(a - dt.timedelta(hours=72)),
         zaman.metin(a + dt.timedelta(hours=72)))).fetchall()
    return {"boss_task_no": adaylar[0][0]} if len(adaylar) == 1 else None


def boss_giden(conn, r, b: Baglam | None = None) -> dict | None:
    """EK-4: BOSS'a birebir yazılacak değerler (eklentiye hazır giden kutusu satırı)."""
    if not r["boss_bekleyen"] or r["boss_islendi"]:
        return None
    kisiler = b.kisiler if b else kisi.kisiler(conn, [r["atanan_id"]])
    t = kisiler.get(r["atanan_id"]) if r["atanan_id"] else None
    son = conn.execute("SELECT kayit_zamani FROM is_emri_olay WHERE is_no=? AND tur IN ('atama','randevu','durum') "
                       "ORDER BY id DESC LIMIT 1", (r["is_no"],)).fetchone()
    alanlar = {"ekip": (t.get("boss_ekip") or t["ad"]) if t else None,
               "randevu_baslangic": r["randevu_bas"], "randevu_bitis": r["randevu_bit"]}
    parca = (r["boss_bekleyen"] or "").split(",")
    if "aski" in parca:
        alanlar["aski_nedeni"] = r["askida_neden"]
        alanlar["uyanma"] = r["uyanma"]
    if "sms" in parca:                               # EK-12.4: her ulaşılamayan aramadan sonra zorunlu
        alanlar["talep_ulasamama_sms"] = True
    return {"is_no": r["is_no"], "boss_task_no": r["boss_task_no"], "alanlar": alanlar, "neden": r["boss_bekleyen"],
            "olusma": son[0] if son else r["guncelleme"]}


def ayrinti(conn: sqlite3.Connection, is_no: str, k: dict | None, *, kapsam: bool = True) -> dict:
    """``IsAyrinti``. Kapsam dışı iş (teknikte başkasının) → 404 is_yok.

    ``kapsam=False`` yalnız motorun kendi yanıtı içindir (teknik işi az önce bıraktı): müşteri alanları ve
    izinler yine role göre kırpılır, çünkü ``musteri_izni`` atanmış kişiye bakar.
    """
    r = conn.execute(_SATIR_SQL + " WHERE e.is_no = ?", (is_no,)).fetchone()
    if r is None:
        raise IsYok()
    if kapsam:
        akis.kapsam_denetle(conn, k, r)
    b = Baglam(conn, k, is_nolar=[is_no])
    s = satir(conn, r, k, b)
    izin = b.musteri_izni(r)
    if izin:
        s["adres"] = r["adres"]
        if b.ofis and _ayar(conn, "musteri_tel", "kapali") == "acik":
            s["musteri_tel"] = r["musteri_tel"]
    net = aski.hesap(b.araliklar.get(is_no), r["acilis"], r["btk_hedef"], b.simdi, r["son24"], b.son24_durur)
    olaylar = conn.execute("SELECT id, zaman, kayit_zamani, kullanici_ad, tur, eski, yeni, notu FROM is_emri_olay "
                           "WHERE is_no=? ORDER BY id DESC LIMIT 50", (is_no,)).fetchall()
    url = _ayar(conn, "boss_task_url")
    mesai = str(_ayar(conn, "mesai", "08:00-20:00")).split("-")[-1].strip() or "20:00"
    s.update({
        "lokasyon": r["lokasyon"], "mahalle_kaynak": r["mahalle_kaynak"], "konum_kaynak": r["konum_kaynak"],
        "bina": {"serial": r["bina_serial"], "ad": r["b_site_adi"] or r["b_crm_site_adi"] or r["b_ad"],
                 "location_id": r["b_location_id"], "lat": r["b_lat"], "lon": r["b_lon"]}
        if r["bina_serial"] and r["b_lat"] is not None else None,
        "boss": {"durum": r["boss_durum"], "randevu_durumu": r["boss_randevu_durumu"],
                 "randevu_bas": r["boss_randevu_bas"], "randevu_bit": r["boss_randevu_bit"],
                 "ekip": r["boss_ekip"] if b.ofis else None, "aski_nedeni": r["boss_aski_nedeni"], "sl": r["boss_sl"],
                 "sl_saat": r["boss_sl_saat"], "son_aciklama": r["boss_son_aciklama"],
                 "bekleyen": r["boss_bekleyen"], "islendi": r["boss_islendi"]},
        "uyanma": r["uyanma"], "askida_neden": r["askida_neden"], "evde_yok_sayisi": r["evde_yok_sayisi"],
        "masa_vade": r["masa_vade"], "teshis_sonucu": r["teshis_sonucu"],
        "soz": soz_metni(r["acilis"], mesai),
        "birincil": _birincil(r, b),
        "izinler": _izinler(conn, r, b),
        "boss_url": url.replace("{task_no}", r["boss_task_no"]) if url and r["boss_task_no"] and "{task_no}" in url else None,
        "bayi_oneri": _bayi_oneri(conn, r) if b.ofis else None,
        "olaylar": [{"id": o["id"], "zaman": o["zaman"], "kisi": o["kullanici_ad"], "tur": o["tur"],
                     "ozet": olay_ozeti(dict(o)), "notu": o["notu"] if o["tur"] == "not" or b.ofis else None}
                    for o in olaylar],
        "aski": [aski.gorunum(a, b.simdi) for a in b.araliklar.get(is_no, [])],
        "aski_durdu_dk": net["durdu_dk"],
        "btk_net_gecen_dk": net["btk_net_gecen_dk"] if r["serit"] == "BTK" else None,
        "boss_giden": boss_giden(conn, r, b) if b.ofis else None,
        "kapanis": r["kapanis"], "kapanis_nedeni": r["kapanis_nedeni"], "acilma_sayisi": r["acilma_sayisi"],
        "ilk_gorulme": r["ilk_gorulme"], "gorulme_zamani": r["gorulme_zamani"],
    })
    if b.ofis:
        # EK-12.4: arama merdiveni ve kayıtları (masa işi; teknikte yok)
        aramalar = aski.aramalar(conn, [is_no]).get(is_no, [])
        s["aramalar"] = [{"zaman": a["zaman"], "sonuc": a["sonuc"], "sure_sn": a["sure_sn"], "webphone": a["webphone"],
                          "sms": a["sms"], "yeni_numara": a["yeni_numara"], "kisi": a["kisi"]} for a in aramalar][-20:]
        s["merdiven"] = kurallar.merdiven_durumu(aramalar, kurallar.oku(conn, "arama_merdiveni"), b.simdi) \
            if r["durum"] in akis.ACIK else None
    s["aski_uyari"] = aski_uyarisi(conn, r, b)
    return s


def aski_uyarisi(conn, r, b: Baglam) -> str | None:
    """EK-12.3: geçersiz abone askısı (saat durmuyor) ya da abone askısının üst sınırına yaklaşılması."""
    if r["durum"] != "askida":
        return None
    acik = next((a for a in reversed(b.araliklar.get(r["is_no"], [])) if not a.get("bitis")), None)
    if acik is None or kurallar.aski_turu(acik.get("neden")) != "abone":
        return None
    if acik["kaynak"] == "elle" and not acik.get("durdurur") and aski.durdurur_mu(acik.get("neden"), aski.kural(conn)):
        _, eksik = kurallar.abone_aski_gecerli(aski.aramalar(conn, [r["is_no"]]).get(r["is_no"], []),
                                               kurallar.oku(conn, "aski_gecerlilik"))
        return f"Geçersiz askı: {eksik or 'kural tutmadı'}. Süre BTK saatine eklenmiyor."
    sinir = kurallar.oku(conn, "aski_sinirlari")
    bas = zaman.oku(acik["baslama"])
    if bas is not None:
        gecen_s = (b.simdi - bas).total_seconds() / 3600
        if gecen_s >= float(sinir.get("abone_uyari") or 72):
            return f"Abone kaynaklı askı {int(gecen_s // 24)} gündür sürüyor; en çok {int(float(sinir.get('abone') or 96) // 24)} gün."
    return None


# ----------------------------------------------------------------------------- listeler
def satirlari_oku(conn: sqlite3.Connection, k: dict | None, kova: str = "acik", gun: int = 7,
                  simdi: dt.datetime | None = None):
    """(satırlar, Baglam). Teknik: kendi açık işleri + bugün biten."""
    simdi = simdi or zaman.simdi()
    if k is not None and kisi.kapsam_teknik(conn, k):
        bugun = simdi.strftime("%Y-%m-%d")
        sql = _SATIR_SQL + (" WHERE e.atanan_id = ? AND (e.durum NOT IN ('cozuldu','kapandi') OR "
                            "substr(COALESCE(e.cozum_zamani, e.kapanis, ''), 1, 10) = ?)")
        satirlar = conn.execute(sql, (k["id"], bugun)).fetchall()
    elif kova == "biten":
        sinir = zaman.metin(simdi - dt.timedelta(days=max(1, int(gun))))
        satirlar = conn.execute(_SATIR_SQL + " WHERE e.durum IN ('cozuldu','kapandi') AND "
                                "COALESCE(e.kapanis, e.cozum_zamani, e.durum_zamani) >= ?", (sinir,)).fetchall()
    else:
        satirlar = conn.execute(_SATIR_SQL + " WHERE e.durum NOT IN ('cozuldu','kapandi')").fetchall()
    b = Baglam(conn, k, simdi, is_nolar=[r["is_no"] for r in satirlar])
    return satirlar, b


def sayac(conn: sqlite3.Connection, simdi: dt.datetime | None = None, satirlar: list[dict] | None = None) -> dict:
    simdi = simdi or zaman.simdi()
    s = zaman.metin(simdi)
    y48 = zaman.metin(simdi - _BTK_48)
    r = conn.execute(
        "SELECT COUNT(*), SUM(son24 < ?), SUM(durum IN ('triyaj','bekliyor','randevulu')), "
        "MIN(CASE WHEN durum IN ('triyaj','bekliyor','randevulu') THEN gorulme_zamani END), "
        "SUM(serit='BTK' AND acilis < ?), SUM(durum='triyaj'), SUM(boss_bekleyen IS NOT NULL AND boss_islendi IS NULL), "
        "SUM(konum_yaklasik=1), SUM(durum='askida' AND uyanma IS NULL) "
        "FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi')", (s, y48)).fetchone()
    en_eski = zaman.oku(r[3]) if r[3] else None
    boss_h = kisi.boss_ekip_haritasi(conn)
    eslesmemis = {ie.anahtar(x[0]) for x in conn.execute(
        "SELECT boss_ekip FROM is_emri WHERE boss_ekip IS NOT NULL AND atanan_id IS NULL AND durum IN "
        "('triyaj','bekliyor','randevulu')")} - set(boss_h) - {""}
    durdu = 0
    for no, liste in aski.araliklar(conn, [x[0] for x in conn.execute(
            "SELECT is_no FROM is_emri WHERE serit='BTK' AND durum NOT IN ('cozuldu','kapandi')")]).items():
        if any(a["durdurur"] and not a["bitis"] for a in liste):
            durdu += 1
    return {"acik": r[0] or 0, "asan24": r[1] or 0, "atanmamis": r[2] or 0,
            "en_eski_atanmamis_dk": int((simdi - en_eski).total_seconds() // 60) if en_eski else None,
            "btk48": r[4] or 0, "kontrol": r[5] or 0, "boss_bekleyen": r[6] or 0, "konum_yaklasik": r[7] or 0,
            "aranacak": sum(len(b["isler"]) for b in aranacak_bantlari(conn, simdi, sayim=True)),
            "eslesmemis_ekip": len(eslesmemis), "askida_btk_durdu": durdu, "askida_uyanmasiz": r[8] or 0}


def _sinin(n: int) -> str:
    """Sayının iyelik + ilgi eki: 1'inin, 2'sinin, 6'sının, 9'unun, 40'ının, 100'ünün."""
    birler = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
    onlar = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
    if n == 0:
        son = "sıfır"
    elif n % 10:
        son = birler[n % 10]
    elif n % 100:
        son = onlar[(n // 10) % 10]
    elif n % 1000:
        son = "yüz"
    else:
        son = "bin"
    unlu = [c for c in son if c in "aeıioöuü"][-1]
    uyum = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}[unlu]
    return ("s" if son[-1] in "aeıioöuü" else "") + uyum + "n" + uyum + "n"


def hikaye(sy: dict, satirlar: list[dict] | None = None) -> str:
    """EK-6: tek hikâye cümlesi — önce en önemli."""
    acik = sy.get("acik", 0)
    if not acik:
        return "Açık iş yok. Yeni rapor gelince burada olur."
    ilk = f"Bugün {acik:,} açık iş var.".replace(",", ".")
    oncelikli = sum(1 for x in satirlar or [] if x.get("oncelik"))
    if oncelikli:                                    # EK-12.5: süresi zaten kaçmış kanal şikâyeti en önce
        return f"{ilk} {oncelikli} kanal şikâyeti bekliyor; süresi zaten kaçtı — önce onlar."
    yakin = sum(1 for x in satirlar or [] if x["kova"] != "biten" and not x["gecikti"] and 0 < x["kalan_dk"] < 120)
    if yakin:
        return f"{ilk} {yakin}'{_sinin(yakin)} 24 saatine 2 saatten az kaldı — önce onlar."
    if sy.get("kontrol"):
        return f"{ilk} {sy['kontrol']} iş kontrol bekliyor; önce onları öbeğine verin."
    if sy.get("atanmamis"):
        dk = sy.get("en_eski_atanmamis_dk")
        return f"{ilk} {sy['atanmamis']} iş atanmayı bekliyor" + (f"; en eskisi {dk} dk önce geldi." if dk is not None else ".")
    if sy.get("btk48"):
        return f"{ilk} {sy['btk48']} BTK işi 48 saati aştı — sabah ilk dalgada onlar."
    return f"{ilk} Atanmamış iş kalmadı."


def son_aktarim(conn: sqlite3.Connection, simdi: dt.datetime | None = None) -> dict | None:
    simdi = simdi or zaman.simdi()
    r = conn.execute("SELECT * FROM ie_aktarim WHERE durum='uygulandi' ORDER BY id DESC LIMIT 1").fetchone()
    if r is None:
        return None
    zaman_ = r["bitis"] or r["baslama"]
    yas = int(max(0, (simdi - zaman.oku(zaman_)).total_seconds() // 60))
    try:
        esik = json.loads(_ayar(conn, "rapor_bayat_dk", "") or "{}")
    except ValueError:
        esik = {}
    mesai = str(_ayar(conn, "mesai", "08:00-20:00"))
    try:
        mb, ms = (dt.time(int(x.split(":")[0]), int(x.split(":")[1])) for x in mesai.split("-"))
        mesaide = mb <= simdi.time() <= ms
    except (ValueError, IndexError):
        mesaide = True
    renk = "yesil"
    if mesaide:
        renk = "kirmizi" if yas >= int(esik.get("kirmizi", 60)) else "amber" if yas >= int(esik.get("amber", 30)) else "yesil"
    return {"id": r["id"], "zaman": zaman_, "dosya_adi": r["dosya_adi"], "is_sayisi": r["is_sayisi"] or 0,
            "yas_dk": yas, "renk": renk, "yontem": r["yontem"],
            "fark": {"yeni": r["yeni"] or 0, "degisen": r["degisen"] or 0, "kaybolan": r["kaybolan"] or 0,
                     "yeniden_acilan": r["yeniden_acilan"] or 0, "degismeyen": r["degismeyen"] or 0}}


def imlec(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT IFNULL(MAX(id), 0) FROM is_emri_olay").fetchone()[0]


def isler_yaniti(conn: sqlite3.Connection, k: dict | None, kova: str = "acik", gun: int = 7) -> dict:
    from . import aktarim, obek
    simdi = zaman.simdi()
    im = imlec(conn)
    satirlar, b = satirlari_oku(conn, k, kova, gun, simdi)
    isler = [satir(conn, r, k, b) for r in satirlar]
    m = siralama.mod(conn, simdi)
    sira = {no: i for i, no in enumerate(siralama.sirala(
        [{**x, "son24": x["son24"], "acilis": x["acilis"]} for x in isler if x["kova"] != "biten"], m["mod"], simdi))}
    isler.sort(key=lambda x: (sira.get(x["is_no"], 10 ** 6), x.get("durum_zamani") or "", x["is_no"]))
    sy = sayac(conn, simdi)
    return {"sunucu_zamani": zaman.metin(simdi), "imlec": im, "obek_surumu": obek.surum(conn), "mod": m["mod"],
            "son_aktarim": son_aktarim(conn, simdi), "sayac": sy, "isler": isler,
            "hikaye": hikaye(sy, isler), "onay_bekleyen": aktarim.onay_bekleyenler(conn) if b.ofis else []}


def degisim(conn: sqlite3.Connection, k: dict | None, imlec_: int) -> dict:
    from . import aktarim, obek
    simdi = zaman.simdi()
    yeni_imlec = imlec(conn)
    nolar = [r[0] for r in conn.execute("SELECT DISTINCT is_no FROM is_emri_olay WHERE id > ?", (int(imlec_ or 0),))]
    isler, gorunmez = [], []
    if nolar:
        b = Baglam(conn, k, simdi, is_nolar=nolar)
        teknik_kapsam = k is not None and kisi.kapsam_teknik(conn, k)
        bugun = simdi.strftime("%Y-%m-%d")
        for parca in range(0, len(nolar), 500):
            dilim = nolar[parca:parca + 500]
            for r in conn.execute(_SATIR_SQL + f" WHERE e.is_no IN ({','.join('?' * len(dilim))})", dilim):
                if teknik_kapsam and (r["atanan_id"] != k["id"] or (
                        r["durum"] in ("cozuldu", "kapandi") and (r["cozum_zamani"] or r["kapanis"] or "")[:10] != bugun)):
                    gorunmez.append(r["is_no"])
                    continue
                isler.append(satir(conn, r, k, b))
    return {"imlec": yeni_imlec, "isler": isler, "gorunmez": gorunmez, "obek_surumu": obek.surum(conn),
            "son_aktarim": son_aktarim(conn, simdi), "sayac": sayac(conn, simdi), "sunucu_zamani": zaman.metin(simdi),
            "onay_bekleyen": aktarim.onay_bekleyenler(conn) if kisi.ofis_mu(conn, k) else []}


# ----------------------------------------------------------------------------- Aranacaklar (§6.6)
def aranacak_bantlari(conn: sqlite3.Connection, simdi: dt.datetime, k: dict | None = None,
                      sayim: bool = False) -> list[dict]:
    """1 BTK teşhis (masa vadesi) › 2 Ulaşılamadı (uyanma geldi) › 3 Uyanan askı › 4 Masa işleri."""
    s = zaman.metin(simdi)
    bir_saat_once = zaman.metin(simdi - dt.timedelta(hours=24))
    sorgular = [
        ("btk_teshis", "serit='BTK' AND masa_vade IS NOT NULL AND kotu_gecmis=0 AND teshis_sonucu IS NULL AND "
                       "durum IN ('triyaj','bekliyor','randevulu','atandi') ORDER BY masa_vade", ()),
        ("ulasilamadi", "durum='ulasilamadi' AND (uyanma IS NULL OR uyanma <= ?) ORDER BY uyanma, evde_yok_sayisi DESC",
         (s,)),
        ("uyanan", "durum IN ('bekliyor','triyaj') AND is_no IN (SELECT is_no FROM is_emri_olay WHERE tur='uyandi' "
                   "AND kayit_zamani >= ?) ORDER BY durum_zamani", (bir_saat_once,)),
        ("masa", "serit='MASA' AND durum NOT IN ('cozuldu','kapandi','askida') ORDER BY son24", ()),
    ]
    goruldu: set[str] = set()
    bantlar = []
    for bant, kosul, param in sorgular:
        if sayim:
            nolar = [r[0] for r in conn.execute(f"SELECT is_no FROM is_emri WHERE {kosul}", param)]
            nolar = [n for n in nolar if n not in goruldu]
            goruldu.update(nolar)
            bantlar.append({"bant": bant, "isler": nolar})
            continue
        # koşuldaki sütunların hepsi is_emri'ye özgüdür (bina ile çakışan ad yok)
        satirlar = [r for r in conn.execute(_SATIR_SQL + " WHERE " + kosul, param).fetchall()
                    if r["is_no"] not in goruldu]
        goruldu.update(r["is_no"] for r in satirlar)
        b = Baglam(conn, k, simdi, is_nolar=[r["is_no"] for r in satirlar])
        bantlar.append({"bant": bant, "isler": [satir(conn, r, k, b) for r in satirlar]})
    return bantlar


def islerim(conn: sqlite3.Connection, k: dict) -> dict:
    """Teknik "İşlerim": kendi açık işleri (sırayla, tam ayrıntı) + bugün bitenler."""
    simdi = zaman.simdi()
    satirlar, b = satirlari_oku(conn, k, "acik", 1, simdi)
    acik = [r for r in satirlar if r["durum"] in ("atandi", "yolda", "sahada") and r["atanan_id"] == k["id"]]
    acik = siralama.teknik_sirasi([dict(r) for r in acik])
    biten = [r for r in satirlar if r["durum"] in ("cozuldu", "kapandi")]
    return {"sunucu_zamani": zaman.metin(simdi), "imlec": imlec(conn),
            "isler": [ayrinti(conn, r["is_no"], k) for r in acik],
            "bitenler": [satir(conn, r, k, b) for r in biten]}
