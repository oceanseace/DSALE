"""İş emrinin hayatı: 12 durum, dört kova, geçiş tablosu ve geçişi yapan tek fonksiyon (spec §3).

Her geçiş tek işlemde yapılır: ``is_emri`` güncellenir (operasyon alanıysa ``surum+1``), ``is_emri_olay``
satırı yazılır, ilgili zaman damgası dolar. Tablo dışı her geçiş 409 ``gecersiz_gecis``.
Kural kodları KARMA-2'dir (belgeler/OPERASYON_TASARIM.md §3).
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import uuid
from dataclasses import dataclass

from operasyon import is_emri as ie

from . import aski as aski_mod
from . import kurallar, zaman
from .islem import islem

# ----------------------------------------------------------------------------- sözlük
DURUMLAR: tuple[str, ...] = ("triyaj", "bekliyor", "randevulu", "atandi", "yolda", "sahada",
                             "ulasilamadi", "askida", "altyapi", "merkeze", "cozuldu", "kapandi")
KAYNAKLAR: tuple[str, ...] = ("boss", "bayi")
KOVALAR: dict[str, str] = {
    "triyaj": "atanmadi", "bekliyor": "atanmadi", "randevulu": "atanmadi",
    "atandi": "teknikte", "yolda": "teknikte", "sahada": "teknikte",
    "ulasilamadi": "beklemede", "askida": "beklemede", "altyapi": "beklemede", "merkeze": "beklemede",
    "cozuldu": "biten", "kapandi": "biten",
}
ETIKET: dict[str, str] = {
    "triyaj": "Kontrol gerekli", "bekliyor": "Atanmadı", "randevulu": "Randevu verildi", "atandi": "Atandı",
    "yolda": "Yolda", "sahada": "Sahada", "ulasilamadi": "Ulaşılamadı", "askida": "Askıda",
    "altyapi": "Altyapı bekliyor", "merkeze": "Merkeze gönderildi", "cozuldu": "Çözüldü", "kapandi": "Kapandı",
}
ACIK: frozenset[str] = frozenset(DURUMLAR) - {"cozuldu", "kapandi"}
ATANMADI: frozenset[str] = frozenset({"triyaj", "bekliyor", "randevulu"})
TEKNIKTE: frozenset[str] = frozenset({"atandi", "yolda", "sahada"})
# İleri kuralı (§3.4-1): BOSS yalnız bu sırada ileri götürebilir, geri asla.
ILERI_SIRA: dict[str, int] = {"triyaj": 0, "bekliyor": 0, "randevulu": 0, "atandi": 1, "yolda": 2, "sahada": 3}

# Şerit ve BTK hedefi: Task Adı'nın sade() hâlinde geçen parça → (şerit, BTK hedef saati). Kaynak artık
# ``ayar.serit_kurallari``dır (EK-12); bu sözlük yalnız varsayılanın okunur görüntüsüdür. İlk eşleşen kazanır;
# listede olmayan iş SAHA'dır (OT §3.1).
SERITLER: dict[str, tuple[str, int | None]] = {
    k["desen"]: (k["serit"], k.get("btk_saat")) for k in kurallar.VARSAYILAN["serit_kurallari"]}
VARSAYILAN_SERIT = ("SAHA", None)

# F16: BOSS "Satış Kanalı" (sade) → kanal grubu. İlk eşleşen kazanır; boş → 'bos'; hiçbiri → 'diger_bayi'.
KANAL_KURALLARI: list[tuple[str, str]] = [
    ("GLOBAL", "global"),
    ("DEHANET", "dehanet"),
    ("DEHA", "dehanet"),
    ("TURKCELL", "kurumsal"),
]

# Kapanış nedenleri (ofisten kapat) — ekranda görünen metinleriyle.
KAPANIS_NEDENLERI: dict[str, str] = {
    "telefonda_cozuldu": "Telefonda çözüldü (canlı test yapıldı)",
    "iptal": "İptal",
    "mukerrer": "Mükerrer kayıt",
    "musteri_vazgecti": "Müşteri vazgeçti",
    # EK-12.4: yalnız arama merdiveni tamamsa (kapanışın kimde olduğu kullanıcıya soruldu; varsayılan: açık)
    "musteriye_ulasilamadi": "Müşteriye ulaşılamadı (arama merdiveni tamam)",
}
ARAMA_METNI: dict[str, str] = {
    "ulasildi": "Müşteriye ulaşıldı", "ulasilamadi": "Ulaşılamadı (çaldı, açmadı)",
    "mesgul_kapali": "Meşgul / kapalı", "dit": "Numara engelli (dıt sesi)", "yanlis_no": "İrtibat hatalı",
}
TESHIS_SONUCLARI = ("duzeldi", "simdi_evde", "baska_gun", "cevapsiz", "kapali", "yanlis_no")


def serit_bul(task_adi: str, kural: list[dict] | None = None) -> tuple[str, int | None]:
    """(şerit, BTK hedef saati). ``kural`` = ``kurallar.oku(conn, 'serit_kurallari')``; yoksa varsayılan."""
    return kurallar.serit(kural if kural is not None else kurallar.VARSAYILAN["serit_kurallari"], task_adi)


def kanal_grubu(satis_kanali) -> str:
    s = ie.sade(satis_kanali) if satis_kanali is not None and str(satis_kanali).strip().lower() not in ("", "nan") else ""
    if not s:
        return "bos"
    for bas, grup in KANAL_KURALLARI:
        if s.startswith(bas):
            return grup
    return "diger_bayi"


# ----------------------------------------------------------------------------- geçiş tablosu
@dataclass(frozen=True)
class GecisKurali:
    roller: frozenset[str]                       # 'operasyon' (yönetici dahil) · 'teknik' · 'sistem'
    zorunlu_alanlar: tuple[str, ...] = ()
    teknik_kendi_isi: bool = False               # teknik yalnız kendisine atanmış işte
    notu: str = ""


def _kural(roller: str, zorunlu: tuple[str, ...] = (), kendi: bool = False, notu: str = "") -> GecisKurali:
    return GecisKurali(frozenset(roller.split()), zorunlu, kendi, notu)


def _tablo() -> dict[tuple[str, str], GecisKurali]:
    t: dict[tuple[str, str], GecisKurali] = {}

    def ekle(nereden, nereye, kural):
        # Aynı çift birden çok satırda geçebilir (ör. atandi→cozuldu: teknik "Bitti" ve operasyonun
        # "Ofisten kapat"ı); roller birleşir, zorunlu alanlar yola göre kodda denetlenir.
        for a in nereden.split():
            for b in nereye.split():
                eski = t.get((a, b))
                if eski is None:
                    t[(a, b)] = kural
                else:
                    t[(a, b)] = GecisKurali(eski.roller | kural.roller, eski.zorunlu_alanlar or kural.zorunlu_alanlar,
                                            eski.teknik_kendi_isi or kural.teknik_kendi_isi,
                                            "; ".join(x for x in (eski.notu, kural.notu) if x))

    acik = " ".join(d for d in DURUMLAR if d in ACIK)
    ekle("triyaj", "bekliyor", _kural("operasyon sistem", notu="3: öbek/mahalle belli oldu"))
    ekle("bekliyor triyaj", "randevulu", _kural("operasyon", ("randevu",), notu="4: teknisyensiz randevu"))
    ekle("randevulu", "bekliyor", _kural("operasyon", notu="randevu kaldırıldı"))
    ekle("bekliyor randevulu triyaj askida merkeze", "atandi", _kural("operasyon sistem", ("teknik_id",), notu="5: ata"))
    ekle("ulasilamadi", "atandi", _kural("operasyon", ("teknik_id", "randevu_teyitli"), notu="6: yeniden ata"))
    ekle("atandi", "atandi", _kural("operasyon teknik", kendi=True, notu="7: başka tekniğe / başka gün"))
    # 7 (genişletme): yoldaki/sahadaki işi operasyon BAŞKA bir tekniğe verebilir (araç arızası, hastalık).
    # Aynı tekniğe "yeniden ata" geri gitmek olurdu: ``ata`` bunu 409 ile reddeder. Ekip "iş aktar" da bu yolu kullanır.
    ekle("yolda sahada", "atandi", _kural("operasyon", ("teknik_id",), notu="7: başka tekniğe ver (yolda/sahada)"))
    ekle("atandi", "yolda", _kural("operasyon teknik sistem", kendi=True, notu="8: yola çıktım"))
    ekle("atandi yolda", "sahada", _kural("operasyon teknik sistem", kendi=True, notu="9: işe başladım"))
    ekle("atandi yolda sahada", "cozuldu", _kural("operasyon teknik", kendi=True, notu="10/11: bitti · ofisten kapat"))
    ekle("atandi yolda sahada", "askida", _kural("operasyon teknik sistem", kendi=True, notu="10a/14: malzeme · askıya al"))
    ekle("atandi yolda sahada", "triyaj", _kural("teknik", ("evde_miydi",), kendi=True, notu="10b: altyapı sorunu"))
    ekle("atandi yolda sahada", "ulasilamadi", _kural("operasyon teknik", kendi=True, notu="12: evde yok"))
    ekle("ulasilamadi", "randevulu", _kural("operasyon", ("randevu",), notu="13: başka gün (teşhis)"))
    ekle(acik, "cozuldu", _kural("operasyon", ("neden",), notu="11: ofisten kapat"))
    ekle(acik, "askida", _kural("operasyon sistem", ("neden",), notu="14: askıya al"))
    ekle("askida", "bekliyor", _kural("operasyon sistem", notu="15: uyandır"))
    ekle(acik, "altyapi", _kural("operasyon sistem", ("ticket_id",), notu="16: ticket'a bağla"))
    ekle("altyapi", "bekliyor", _kural("operasyon sistem", notu="17: ticket çözüldü / ayır"))
    ekle(acik, "merkeze", _kural("operasyon sistem", ("neden",), notu="18: merkeze gönderildi"))
    ekle("merkeze", "bekliyor", _kural("operasyon", notu="19: sahaya al"))
    ekle("cozuldu", "atandi", _kural("operasyon", ("teknik_id", "neden"), notu="20: yeniden aç"))
    ekle(" ".join(DURUMLAR), "kapandi", _kural("sistem", notu="21: listeden düştü"))
    # Bağlanmamış bayi işi raporda hiç görünmez: ofisten kapatılınca doğrudan kapanır (11).
    ekle(acik, "kapandi", _kural("operasyon", ("neden",), notu="11: bayi işi ofisten kapandı"))
    return t


GECISLER: dict[tuple[str, str], GecisKurali] = _tablo()


def trigger_sql() -> list[str]:
    """is_emri değer tetikleyicileri (spec §1.7). Liste DURUMLAR/KAYNAKLAR'dan üretilir.

    Göçün metniyle birebir aynı olsun diye ``saha.sema_v2.is_emri_tetikleyicileri`` (WP-A) varsa o kullanılır.
    """
    try:
        from saha import sema_v2
        return list(sema_v2.is_emri_tetikleyicileri(DURUMLAR, KAYNAKLAR))
    except (ImportError, AttributeError):
        pass
    durumlar = ",".join(f"'{d}'" for d in DURUMLAR)
    kaynaklar = ",".join(f"'{k}'" for k in KAYNAKLAR)
    kosul = f"NEW.durum NOT IN ({durumlar})\n  OR NEW.kaynak NOT IN ({kaynaklar})"
    return [
        "CREATE TRIGGER IF NOT EXISTS trg_is_deger_ekle BEFORE INSERT ON is_emri\n"
        f"WHEN {kosul}\nBEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END",
        "CREATE TRIGGER IF NOT EXISTS trg_is_deger_guncelle BEFORE UPDATE OF durum, kaynak ON is_emri\n"
        f"WHEN {kosul}\nBEGIN SELECT RAISE(ABORT, 'is_emri: gecersiz durum/kaynak'); END",
    ]


# ============================================================================= yardımcılar
GERI_AL_DK = 10
_ALTYAPI_KONU = ("SİNYAL", "EK SP", "GÜZERGAH", "ALTYAPI")
_TICKET_ACIK = ("AÇIK", "HATA", "TRANSFER")
_TICKET_KAPALI = ("ÇÖZÜLDÜ", "KAPATILDI", "İPTAL")
# Geri al ile geri yazılabilen alanlar (kişisel veri alanı yok)
_GERI_ALINABILIR = {"durum", "atanan_id", "atama_kaynagi", "randevu_bas", "randevu_bit", "randevu_teyitli",
                    "obek_elle_id", "ticket_id", "uyanma", "askida_neden", "sira", "boss_islendi", "triyaj_nedeni",
                    "il", "ilce", "mahalle", "il_k", "ilce_k", "mahalle_k", "mahalle_elle", "mahalle_kaynak",
                    "obek_id", "lat", "lon", "konum_kaynak", "konum_yaklasik", "boss_bekleyen", "kapanis_nedeni",
                    "teshis_sonucu", "oneri_teknik_id", "cozum_zamani", "atama_zamani", "teknik_gordu"}


def _H():
    from . import hatalar
    return hatalar


def is_getir(conn: sqlite3.Connection, is_no: str) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM is_emri WHERE is_no = ?", (is_no,)).fetchone()
    if r is None:
        raise _H().IsYok()
    return r


def kapsam_denetle(conn, k: dict | None, r: sqlite3.Row) -> None:
    """Teknik (ofis görevi olmayan) yalnız kendisine atanmış işi görür; başkasınınki 404 (varlığı sızmaz)."""
    from . import kisi
    if k is not None and kisi.kapsam_teknik(conn, k) and r["atanan_id"] != k.get("id"):
        raise _H().IsYok()


def olay_yaz(conn, is_no, tur, k, *, eski=None, yeni=None, notu=None, aktarim_id=None, toplu_id=None,
             istemci_id=None, an=None) -> int:
    simdi = zaman.metin()
    return conn.execute(
        "INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, kullanici_id, kullanici_ad, tur, eski, yeni, notu, "
        "aktarim_id, toplu_id, istemci_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (is_no, an or simdi, simdi, (k or {}).get("id"), (k or {}).get("ad"), tur,
         json.dumps(eski, ensure_ascii=False, default=str) if eski is not None else None,
         json.dumps(yeni, ensure_ascii=False, default=str) if yeni is not None else None,
         (str(notu)[:1000] if notu else None), aktarim_id, toplu_id, istemci_id)).lastrowid


def _guncel_degil(conn, k, is_no):
    from . import gorunum
    son = conn.execute("SELECT * FROM is_emri_olay WHERE is_no=? ORDER BY id DESC LIMIT 1", (is_no,)).fetchone()
    kim = (son["kullanici_ad"] or "Sistem") if son else "Sistem"
    ne = gorunum.olay_ozeti(dict(son)) if son else "değiştirdi"
    saat = zaman.saat_dk(son["kayit_zamani"]) if son else ""
    return _H().GuncelDegil(f"Bu iş siz bakarken değişti: {saat}'te {kim} · {ne}.",
                            guncel=gorunum.ayrinti(conn, is_no, k),
                            degistiren=son["kullanici_ad"] if son else None,
                            zaman=son["kayit_zamani"] if son else None)


def yaz(conn, r: sqlite3.Row, alanlar: dict, k, tur: str, *, surum: int | None = None, notu=None, toplu_id=None,
        istemci_id=None, an=None, surum_arttir: bool = True) -> int:
    """İyimser kilitli yazma: ``UPDATE … WHERE is_no=? AND surum=?``; 0 satır → 409 guncel_degil.

    Olay defterine değişen alanların ESKİ değerleri (geri al için) ve yeni değerleri yazılır; kişisel alanlarda
    yalnız alan adı. Dönüş: olay id.
    """
    if surum is not None and int(surum) != r["surum"]:
        raise _guncel_degil(conn, k, r["is_no"])
    simdi = zaman.metin()
    degisen = {a: v for a, v in alanlar.items() if r[a] != v}
    set_ = "".join(f"{a}=?, " for a in alanlar)
    n = conn.execute(f"UPDATE is_emri SET {set_}surum=surum+?, guncelleme=? WHERE is_no=? AND surum=?",
                     (*alanlar.values(), 1 if surum_arttir else 0, simdi, r["is_no"], r["surum"])).rowcount
    if n == 0:
        raise _guncel_degil(conn, k, r["is_no"])
    kisisel = {"musteri_tel", "musteri_adi", "musteri_no", "adres"}
    eski = {a: ("değişti" if a in kisisel else r[a]) for a in degisen}
    yeni = {a: ("değişti" if a in kisisel else v) for a, v in degisen.items()}
    yeni["_surum"] = r["surum"] + (1 if surum_arttir else 0)
    return olay_yaz(conn, r["is_no"], tur, k, eski=eski, yeni=yeni, notu=notu, toplu_id=toplu_id,
                    istemci_id=istemci_id, an=an)


def _istemci_tekrar(conn, k, istemci_id) -> bool:
    if not istemci_id or not k:
        return False
    return conn.execute("SELECT 1 FROM is_emri_olay WHERE kullanici_id=? AND istemci_id=?",
                        (k.get("id"), istemci_id)).fetchone() is not None


def _cihaz_ani(an) -> str | None:
    """Çevrimdışı basış anı: gelecekte 5 dk'dan, geçmişte 14 günden uzaksa sunucu saati."""
    t = zaman.oku(an) if an else None
    if t is None:
        return None
    simdi = zaman.simdi()
    if t > simdi + dt.timedelta(minutes=5) or t < simdi - dt.timedelta(days=14):
        return None
    return zaman.metin(t)


def randevu_dogrula(bas, bit) -> tuple[str, str]:
    G = _H().Gecersiz
    b, s = zaman.oku(bas), zaman.oku(bit)
    if b is None or s is None:
        raise G("Randevunun başlangıç ve bitişini seçin.", kod="randevu_gecersiz")
    if s <= b:
        raise G("Bitiş başlangıçtan sonra olmalı.", kod="randevu_gecersiz")
    if (s - b) > dt.timedelta(hours=4):
        raise G("En çok 4 saatlik aralık.", kod="randevu_gecersiz")
    simdi = zaman.simdi()
    if b < simdi - dt.timedelta(hours=1):
        raise G("Randevu geçmişte olamaz.", kod="randevu_gecersiz")
    if b > simdi + dt.timedelta(days=7):
        raise G("En çok 7 gün ileri.", kod="randevu_gecersiz")
    return zaman.metin(b), zaman.metin(s)


def altyapi_ticketi(conn, bina_serial) -> dict | None:
    """Binadaki açık ticket (altyapı konuları önce)."""
    if not bina_serial:
        return None
    try:
        r = conn.execute(f"SELECT id, konu, durum, acilis, olusturma FROM ticket WHERE bina_serial=? AND durum IN "
                         f"({','.join('?' * len(_TICKET_ACIK))}) ORDER BY (konu IN ({','.join('?' * len(_ALTYAPI_KONU))})) "
                         f"DESC, id LIMIT 1", (bina_serial, *_TICKET_ACIK, *_ALTYAPI_KONU)).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(r) if r else None


def ticket_gun(t: dict) -> int:
    bas = zaman.oku(t.get("acilis") or t.get("olusturma"))
    return max(0, (zaman.simdi().date() - bas.date()).days) if bas else 0


def _boss_bekleyen_hesapla(conn, r, atanan_id, randevu_bas, randevu_bit, aski_ek=False, sms_ek=False) -> str | None:
    """Giden kutusu (§3.4-4 + EK-4): ekip · randevu · aski · sms ("Talep Ulaşamama SMS", EK-12.4).

    'aski' ve 'sms' raporla doğrulanamaz: işlendi denene kadar kalır (işlendi işareti bütün kutuyu kapatır).
    """
    from . import kisi
    parca = []
    if atanan_id is not None:
        esl = kisi.boss_ekip_haritasi(conn).get(ie.anahtar(r["boss_ekip"] or "")) if r["boss_ekip"] else None
        if esl != atanan_id:
            parca.append("ekip")
    if randevu_bas and (randevu_bas, randevu_bit) != (r["boss_randevu_bas"], r["boss_randevu_bit"]):
        parca.append("randevu")
    bekleyen = (r["boss_bekleyen"] or "").split(",") if not r["boss_islendi"] else []
    if aski_ek or "aski" in bekleyen:
        parca.append("aski")
    if sms_ek or "sms" in bekleyen:
        parca.append("sms")
    return ",".join(dict.fromkeys(parca)) or None


def _uyanma_siniri(conn, r, neden_metni: str | None) -> dt.timedelta:
    """Askı üst sınırı (spec §3.1 + EK-12.3; ``ayar.aski_sinirlari``): abone kaynaklı 4 g · malzeme 8 s (BTK 2 s) ·
    genel arıza 7 g · Bilgi & Belge 10 g · diğer 3 g (BTK 1 g)."""
    return kurallar.aski_siniri(conn, neden_metni, r["serit"])


def _gorev_yolu(conn, k, r, istemci_id) -> str:
    """'sistem' · 'teknik' (kendi işinde, telefondan) · 'operasyon' (ofis görevi)."""
    from . import kisi
    if k is None:
        return "sistem"
    ofis = kisi.ofis_mu(conn, k)
    kendi = kisi.teknik_mi(conn, k) and r["atanan_id"] == k.get("id")
    if kendi and (istemci_id or not ofis):
        return "teknik"
    if ofis:
        return "operasyon"
    if kisi.teknik_mi(conn, k):
        raise _H().IsYok()
    raise _H().Yasak()


def _gecersiz(eski: str, yeni: str):
    return _H().GecersizGecis(f"Bu iş '{ETIKET.get(eski, eski)}' durumunda; '{ETIKET.get(yeni, yeni)}' yapılamaz.")


def _bayi_bagsiz(r) -> bool:
    return r["kaynak"] == "bayi" and not r["boss_task_no"]


def _kapanis_kurali(conn, r, neden: str) -> None:
    """EK-12: BTK'ya bildirilmiş şikâyet işi elle iptal edilmez; "Müşteriye ulaşılamadı" yalnız merdiven tamamsa."""
    H = _H()
    if neden == "iptal" and btk_bilgileri(conn, [r["is_no"]]).get(r["is_no"], {}).get("tarih"):
        raise H.Catisma("BTK'ya bildirilmiş şikâyet işi iptal edilemez. Başlık yanlışsa yeni task açılır; eskisi "
                        "birleştirme nedeniyle kapanır.", kod="btk_iptal_yasak")
    if neden == "musteriye_ulasilamadi":
        m = kurallar.merdiven_durumu(aski_mod.aramalar(conn, [r["is_no"]]).get(r["is_no"], []),
                                     kurallar.oku(conn, "arama_merdiveni"), zaman.simdi())
        if not m["tamam"]:
            raise H.Catisma(f"Arama merdiveni tamamlanmadı: {m['eksik'] or 'müşteriye ulaşıldı'}. "
                            "Ulaşılamadı kapanışı merdiven bitince açılır.", kod="merdiven_eksik", merdiven=m)


def _aski_gecerli_mi(conn, is_no: str, neden: str) -> bool:
    """Elle açılan askının saati durdurabilmesi için (EK-12.3): abone kaynaklıysa arama kayıtları geçerli olmalı."""
    if kurallar.aski_turu(neden) != "abone":
        return True
    return kurallar.abone_aski_gecerli(aski_mod.aramalar(conn, [is_no]).get(is_no, []),
                                       kurallar.oku(conn, "aski_gecerlilik"))[0]


def btk_bilgileri(conn, is_nolar=None) -> dict[str, dict]:
    """BTK şikâyet kaydı ve TÇS (olay 'btk_sikayet' / 'tcs'; son kayıt geçerli): {is_no: {tarih, reopen, tcs}}."""
    sql = "SELECT is_no, tur, yeni FROM is_emri_olay WHERE tur IN ('btk_sikayet','tcs')"
    param: list = []
    if is_nolar is not None:
        is_nolar = list(is_nolar)
        if not is_nolar:
            return {}
        if len(is_nolar) <= 500:
            sql += f" AND is_no IN ({','.join('?' * len(is_nolar))})"
            param = is_nolar
    out: dict[str, dict] = {}
    for r in conn.execute(sql + " ORDER BY id", param):
        try:
            y = json.loads(r["yeni"] or "{}")
        except ValueError:
            continue
        d = out.setdefault(r["is_no"], {"tarih": None, "reopen": False, "tcs": None})
        if r["tur"] == "tcs":
            d["tcs"] = y.get("tcs")
        elif y.get("kaldir"):
            d.update(tarih=None, reopen=False, tcs=None)
        else:
            d.update(tarih=y.get("tarih"), reopen=bool(y.get("reopen")))
    return out


def _surum_denetle(conn, k, r, surum):
    if surum is not None and int(surum) != r["surum"]:
        raise _guncel_degil(conn, k, r["is_no"])


# ============================================================================= geçiş
def gecis(conn: sqlite3.Connection, is_no: str, yeni: str, k: dict | None, *, surum: int | None = None,
          istemci_id: str | None = None, zaman_: str | None = None, **alanlar) -> dict:
    """Tek geçiş (spec §3.3). Dönüş: güncel ``IsAyrinti``. Hatalar: GecersizGecis, GuncelDegil, AlanEksik …"""
    from . import gorunum
    H = _H()
    if yeni not in DURUMLAR:
        raise H.Gecersiz("Tanınmayan durum.", kod="alan_eksik")
    r = is_getir(conn, is_no)
    kapsam_denetle(conn, k, r)
    if _istemci_tekrar(conn, k, istemci_id):
        return gorunum.ayrinti(conn, is_no, k)
    yol = _gorev_yolu(conn, k, r, istemci_id)
    # başka fonksiyona devredilen geçişler (kendi işlemlerini açarlar)
    if yol == "operasyon" and yeni == "atandi":
        if (r["durum"], yeni) not in GECISLER:
            raise _gecersiz(r["durum"], yeni)
        return ata(conn, is_no, alanlar.get("teknik_id"), k, randevu=alanlar.get("randevu"), surum=surum,
                   yine_de=bool(alanlar.get("yine_de")), notu=alanlar.get("notu"),
                   yeniden_ac_nedeni=alanlar.get("neden") if r["durum"] == "cozuldu" else None)
    if yol == "operasyon" and yeni == "randevulu":
        if (r["durum"], yeni) not in GECISLER:
            raise _gecersiz(r["durum"], yeni)
        rv = alanlar.get("randevu") or {}
        return randevu(conn, is_no, k, rv.get("bas"), rv.get("bit"), bool(rv.get("teyitli", True)), surum=surum,
                       notu=alanlar.get("notu"))
    if yol == "operasyon" and yeni == "altyapi" and r["durum"] != "altyapi":
        if (r["durum"], yeni) not in GECISLER:
            raise _gecersiz(r["durum"], yeni)
        return ticket_bagla(conn, is_no, k, ticket_id=alanlar.get("ticket_id"), yeni=alanlar.get("ticket"),
                            teknisyen_gonderme=True, surum=surum)
    with islem(conn):
        r = is_getir(conn, is_no)
        an = _cihaz_ani(zaman_) if yol == "teknik" else None
        simdi = zaman.metin()
        ani = an or simdi
        kural = GECISLER.get((r["durum"], yeni))
        if kural is None or yol not in kural.roller:
            # Çevrimdışı geç gelen "Yola çıktım": iş zaten ilerdeyse yalnız olay yazılır, durum geri gitmez (§5.5)
            if yol == "teknik" and yeni in ("yolda", "sahada") and r["durum"] in ILERI_SIRA \
                    and ILERI_SIRA[r["durum"]] >= ILERI_SIRA[yeni]:
                olay_yaz(conn, is_no, "durum", k, yeni={"durum": yeni, "gec": True},
                         notu="Geç ulaştı; durum değişmedi", istemci_id=istemci_id, an=ani)
                return gorunum.ayrinti(conn, is_no, k)
            raise _gecersiz(r["durum"], yeni)
        if yol == "operasyon":
            _surum_denetle(conn, k, r, surum)
        a: dict = {"durum": yeni, "durum_zamani": ani}
        notu = alanlar.get("notu")
        tur = "durum"
        aski_ac: tuple | None = None
        onceki_askida = r["durum"] == "askida"

        if yeni == "cozuldu":
            if yol == "teknik":
                if not isinstance(alanlar.get("evde_miydi"), bool):
                    raise H.AlanEksik("Müşteri evde miydi?")
                a.update(evde_miydi=1 if alanlar["evde_miydi"] else 0,
                         sonuc_kodu=alanlar.get("sonuc_kodu") or "cozuldu", cozum_zamani=ani)
            else:
                neden = alanlar.get("neden")
                if neden not in KAPANIS_NEDENLERI:
                    raise H.AlanEksik("Neden kapatıyorsunuz?", secenekler=list(KAPANIS_NEDENLERI))
                if neden == "telefonda_cozuldu":
                    if r["tekrar7g"]:
                        raise H.Catisma("Bu arıza 7 gün içinde tekrar geldi; telefonda kapatılamaz. Kıdemli "
                                        "teknisyene atayın.", kod="tekrar_ariza")
                    if not alanlar.get("canli_test"):
                        raise H.AlanEksik("Canlı test yapıldı mı? (hız testi, kanal açılıyor)")
                _kapanis_kurali(conn, r, neden)
                a.update(kapanis_nedeni=neden, cozum_zamani=simdi, ilk_atama_zamani=r["ilk_atama_zamani"] or simdi)
                notu = notu or KAPANIS_NEDENLERI[neden]
            if _bayi_bagsiz(r):                      # raporda hiç görünmez: doğrulayan biziz
                a.update(durum="kapandi", kapanis=ani, kapanis_kesin=1,
                         kapanis_nedeni=a.get("kapanis_nedeni") or "cozuldu_dogrulandi")
        elif yeni == "kapandi":                      # yalnız bağlanmamış bayi işi, ofisten
            if not _bayi_bagsiz(r):
                raise _gecersiz(r["durum"], yeni)
            neden = alanlar.get("neden")
            if neden not in KAPANIS_NEDENLERI:
                raise H.AlanEksik("Neden kapatıyorsunuz?", secenekler=list(KAPANIS_NEDENLERI))
            _kapanis_kurali(conn, r, neden)
            a.update(kapanis=simdi, kapanis_kesin=1, kapanis_nedeni=neden, cozum_zamani=r["cozum_zamani"] or simdi)
            notu = notu or KAPANIS_NEDENLERI[neden]
        elif yeni == "askida":
            if yol == "teknik":                      # 10a: malzeme gerekiyor
                if not isinstance(alanlar.get("evde_miydi"), bool):
                    raise H.AlanEksik("Müşteri evde miydi?")
                neden_m = "Malzeme bekleniyor"
                uyanma = zaman.oku(ani) + _uyanma_siniri(conn, r, neden_m)
                a.update(evde_miydi=1 if alanlar["evde_miydi"] else 0, sonuc_kodu="malzeme")
            else:
                neden_m = aski_mod.neden_metni(conn, alanlar.get("neden"))
                if not neden_m:
                    raise H.AlanEksik("Neden askıya alıyorsunuz?")
                if "IRTIBAT HATALI" in ie.sade(neden_m) and not notu:
                    raise H.AlanEksik("Hatalı iletişim bilgisini açıklamaya yazın (ATA havuzu).")
                uyanma = zaman.oku(alanlar.get("uyanma")) if alanlar.get("uyanma") else None
                if uyanma is None:
                    raise H.AlanEksik("Uyanma zamanı gerekli: ne zaman tekrar bakılsın?")
                sinir = _uyanma_siniri(conn, r, neden_m)
                if uyanma > zaman.simdi() + sinir + dt.timedelta(minutes=1):
                    gun = sinir.total_seconds() / 86400
                    metin = f"{int(gun)} gün" if gun >= 1 else f"{int(sinir.total_seconds() // 3600)} saat"
                    raise H.Gecersiz(f"Bu nedenle uyanma en çok {metin} sonrası olabilir.", kod="uyanma_gecersiz")
                if uyanma <= zaman.simdi():
                    raise H.Gecersiz("Uyanma zamanı ileride olmalı.", kod="uyanma_gecersiz")
            a.update(askida_neden=neden_m, uyanma=zaman.metin(uyanma))
            if not onceki_askida:
                aski_ac = (ani, neden_m, _aski_gecerli_mi(conn, is_no, neden_m))
                a["boss_bekleyen"] = _boss_bekleyen_hesapla(conn, r, r["atanan_id"], r["randevu_bas"],
                                                            r["randevu_bit"], aski_ek=True)
                a["boss_islendi"] = None
            notu = notu or neden_m
        elif yeni == "triyaj":                       # 10b: altyapı sorunu (teknik)
            if not isinstance(alanlar.get("evde_miydi"), bool):
                raise H.AlanEksik("Müşteri evde miydi?")
            a.update(triyaj_nedeni="altyapi_supheli", evde_miydi=1 if alanlar["evde_miydi"] else 0,
                     sonuc_kodu="altyapi_sorunu", oneri_teknik_id=r["atanan_id"], atanan_id=None, sira=None)
            notu = notu or "Teknisyen altyapı sorunu bildirdi"
        elif yeni == "ulasilamadi":                  # 12: evde yok
            a.update(evde_yok_sayisi=r["evde_yok_sayisi"] + 1, uyanma=ani, sira=None, sonuc_kodu="evde_yok")
            if yol == "teknik":
                a["evde_miydi"] = 0
            notu = notu or "Evde yok: 10 dk beklendi, BOSS'tan 2 kez arandı, not bırakıldı"
        elif yeni == "atandi":                       # 7 (teknik): başka gün, kendi işinde teyitli yeni dilim
            rv = alanlar.get("randevu") or {}
            bas, bit = randevu_dogrula(rv.get("bas"), rv.get("bit"))
            a.update(randevu_bas=bas, randevu_bit=bit, randevu_teyitli=1, sira=None,
                     boss_bekleyen=_boss_bekleyen_hesapla(conn, r, r["atanan_id"], bas, bit), boss_islendi=None)
            a.pop("durum_zamani")
            tur = "randevu"
            notu = notu or "Müşteriyle başka güne anlaşıldı"
        elif yeni == "yolda":
            a["yolda_zamani"] = r["yolda_zamani"] or ani
        elif yeni == "sahada":
            a["sahada_zamani"] = r["sahada_zamani"] or ani
        elif yeni == "merkeze":
            neden = alanlar.get("neden")
            if not neden:
                raise H.AlanEksik("Neden merkeze gönderildi?")
            a["askida_neden"] = str(neden)[:200]
            notu = notu or str(neden)
        elif yeni == "altyapi":                      # sistem kolu (ticket zaten bağlı)
            if not r["ticket_id"]:
                raise H.AlanEksik("Hangi ticket'a bağlansın?")
        elif yeni == "bekliyor":
            if r["durum"] == "triyaj":
                if not (r["obek_elle_id"] or r["obek_id"]) and r["triyaj_nedeni"] != "altyapi_supheli":
                    raise H.Gecersiz("Önce işin öbeğini seçin.", kod="alan_eksik")
                a["triyaj_nedeni"] = None
            elif r["durum"] == "altyapi":
                a["ticket_id"] = None
                notu = notu or "Ticket'tan ayrıldı"
            elif r["durum"] == "askida":
                a.update(uyanma=None, askida_neden=None)
                tur = "uyandi"
                notu = notu or "Uyandırıldı"
            elif r["durum"] == "merkeze":
                a["askida_neden"] = None
                notu = notu or "Sahaya alındı"
            elif r["durum"] == "randevulu":
                a.update(randevu_bas=None, randevu_bit=None, randevu_teyitli=0)
        # askıdan çıkış: operatörün açtığı aralık kapanır
        if onceki_askida and a.get("durum") != "askida":
            aski_mod.kapat(conn, is_no, ani, kaynak="elle")
        yaz(conn, r, a, k, tur, notu=notu, istemci_id=istemci_id, an=ani)
        if aski_ac:
            aski_mod.ac(conn, is_no, aski_ac[0], aski_ac[1], "elle", durdurur=aski_ac[2])
        birakti = yol == "teknik" and a.get("atanan_id", r["atanan_id"]) != r["atanan_id"]
    _sonra_oneri(conn, [is_no])
    # Teknik "Altyapı sorunu" deyince iş ondan çıkar: yanıt kapsam denetimsiz ama müşteri alanları ve
    # izinler kırpılmış hâlde döner (telefon işi listesinden düşürür; sonraki okumalar 404).
    return gorunum.ayrinti(conn, is_no, k, kapsam=not birakti)


def _sonra_oneri(conn, is_nolar) -> None:
    from . import siralama
    try:
        siralama.oneri_hesapla(conn, is_nolar)
    except Exception:          # noqa: BLE001 — öneri kolaylıktır, geçişi bozmaz
        import logging
        logging.getLogger("operasyon.akis").exception("Öneri hesaplanamadı")


# ============================================================================= atama
def teknik_denetle(conn, teknik_id) -> dict:
    from . import kisi
    H = _H()
    if teknik_id is None:
        raise H.AlanEksik("Teknisyeni seçin.")
    try:
        tid = int(teknik_id)
    except (TypeError, ValueError):
        raise H.Gecersiz("Seçilen kişi aktif bir teknik görevli değil.", kod="teknik_gecersiz")
    t = kisi.kisiler(conn, [tid]).get(tid)
    if not t or not t["aktif"] or "teknik" not in t["gorevler"]:
        raise H.Gecersiz("Seçilen kişi aktif bir teknik görevli değil.", kod="teknik_gecersiz")
    return t


def ata(conn: sqlite3.Connection, is_no: str, teknik_id, k: dict | None, *, randevu: dict | None = None,
        surum: int | None = None, yine_de: bool = False, toplu_id: str | None = None, kaynak: str = "elle",
        notu: str | None = None, yeniden_ac_nedeni: str | None = None) -> dict:
    """Ata / başka tekniğe ver / yeniden ata / yeniden aç (geçiş 5, 6, 7, 20). Dönüş: IsAyrinti."""
    from . import gorunum, kisi, siralama
    H = _H()
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        _surum_denetle(conn, k, r, surum)
        if (r["durum"], "atandi") not in GECISLER:
            raise _gecersiz(r["durum"], "atandi")
        t = teknik_denetle(conn, teknik_id)
        if r["durum"] in ("yolda", "sahada") and t["id"] == r["atanan_id"]:
            raise _gecersiz(r["durum"], "atandi")        # aynı teknikte geri gitmek yok; yalnız başkasına verilir
        if r["durum"] == "cozuldu" and not yeniden_ac_nedeni:
            raise H.AlanEksik("Neden yeniden açıyorsunuz?")
        rv = dict(randevu or {})
        if r["durum"] == "ulasilamadi" and not rv.get("teyitli"):
            raise H.Gecersiz("Müşteriye ulaşılmadan aynı işe ikinci kez teknisyen gönderilmez. \"Saat teyitli\" "
                             "işaretleyin.", kod="teyit_gerekli")
        if not yine_de and not r["ticket_id"]:
            tk = altyapi_ticketi(conn, r["bina_serial"])
            if tk is not None:
                raise H.Catisma(f"Bu binada açık {tk['konu']} ticket'ı var (#{tk['id']}, {ticket_gun(tk)} gündür). "
                                "Teknisyen gönderilmez.", kod="altyapi_engeli",
                                ticket={"id": tk["id"], "konu": tk["konu"]})
        simdi = zaman.metin()
        if rv.get("bas"):
            bas, bit = randevu_dogrula(rv.get("bas"), rv.get("bit"))
            teyit = 1 if rv.get("teyitli") else 0
        elif r["randevu_bas"] and r["durum"] in ("randevulu", "atandi", "ulasilamadi") \
                and r["atanan_id"] in (None, t["id"]) and r["randevu_bas"] >= zaman.metin(zaman.simdi() - dt.timedelta(hours=1)):
            bas, bit, teyit = r["randevu_bas"], r["randevu_bit"], r["randevu_teyitli"]
        else:
            bas, bit = siralama.dilim_oner(conn, t["id"], zaman.simdi(), haric=is_no)
            teyit = 0
        a = {"durum": "atandi", "durum_zamani": simdi, "atanan_id": t["id"], "atama_kaynagi": kaynak,
             "atama_zamani": simdi, "ilk_atama_zamani": r["ilk_atama_zamani"] or simdi,
             "randevu_bas": bas, "randevu_bit": bit, "randevu_teyitli": teyit,
             "oneri_teknik_id": None, "oneri_bas": None, "oneri_bit": None, "oneri_neden": None,
             "boss_bekleyen": None if kaynak == "boss" else _boss_bekleyen_hesapla(conn, r, t["id"], bas, bit),
             "boss_islendi": None}
        if r["atanan_id"] != t["id"]:
            a.update(teknik_gordu=None, sira=None)
        if r["durum"] in ("yolda", "sahada"):            # yeni teknisyenin yolu kendi basışıyla ölçülür
            a.update(yolda_zamani=None, sahada_zamani=None)
        if r["durum"] == "triyaj" and r["triyaj_nedeni"] == "altyapi_supheli":
            a["triyaj_nedeni"] = None
        if r["durum"] == "askida":
            a.update(uyanma=None, askida_neden=None)
            aski_mod.kapat(conn, is_no, simdi, kaynak="elle")
        if r["durum"] == "merkeze":
            a["askida_neden"] = None
        if r["durum"] == "cozuldu":
            a.update(cozum_zamani=None, kapanis_nedeni=None, boss_kapanmadi=0, evde_miydi=None, sonuc_kodu=None)
            notu = notu or f"Yeniden açıldı: {yeniden_ac_nedeni}"
        ad = kisi.kisa_ad(t["ad"])
        yaz(conn, r, a, k, "atama", toplu_id=toplu_id,
            notu=notu or (f"{ad}'ya atandı" + (" (BOSS'taki ekip)" if kaynak == "boss" else "")))
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


def randevu(conn: sqlite3.Connection, is_no: str, k: dict | None, bas, bit, teyitli: bool, *,
            surum: int | None = None, notu: str | None = None) -> dict:
    """Randevu ver / değiştir / kaldır (geçiş 4, 7, 13). Teknisyensiz randevu: bekliyor → randevulu."""
    from . import gorunum
    H = _H()
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        _surum_denetle(conn, k, r, surum)
        if r["durum"] in ("cozuldu", "kapandi"):
            raise _gecersiz(r["durum"], "randevulu")
        a: dict = {}
        if not bas:                                  # kaldır
            a.update(randevu_bas=None, randevu_bit=None, randevu_teyitli=0)
            if r["durum"] == "randevulu":
                a.update(durum="triyaj" if r["triyaj_nedeni"] else "bekliyor", durum_zamani=zaman.metin())
            yaz(conn, r, a, k, "randevu", notu=notu or "Randevu kaldırıldı")
        else:
            b, s = randevu_dogrula(bas, bit)
            if r["durum"] == "ulasilamadi" and not teyitli:
                raise H.Gecersiz("Müşteriye ulaşılmadan randevu verilmez. \"Saat teyitli\" işaretleyin.",
                                 kod="teyit_gerekli")
            a.update(randevu_bas=b, randevu_bit=s, randevu_teyitli=1 if teyitli else 0)
            if r["durum"] in ("bekliyor", "triyaj", "ulasilamadi"):
                a.update(durum="randevulu", durum_zamani=zaman.metin())
            if r["atanan_id"] is not None:
                a["boss_bekleyen"] = _boss_bekleyen_hesapla(conn, r, r["atanan_id"], b, s)
                a["boss_islendi"] = None
            yaz(conn, r, a, k, "randevu", notu=notu)
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


# ============================================================================= arama merdiveni (EK-12.4)
_ATA_NEDENI = "İrtibat hatalı (ATA havuzu)"


def arama_kaydet(conn: sqlite3.Connection, is_no: str, k: dict | None, sonuc: str, *, sure_sn: int | None = None,
                 webphone: bool = True, sms: bool = False, yeni_numara: bool = False, notu: str | None = None,
                 istemci_id: str | None = None, teshis_sonucu: str | None = None) -> dict:
    """Masadan yapılan müşteri araması (EÇM Müşteri Arama Kuralları; ``ayar.arama_merdiveni``).

    - 22:00'den sonra / pencere başından önce arama kaydı alınmaz (422 ``arama_saati``).
    - Ulaşılamayan her aramadan sonra BOSS "Talep Ulaşamama SMS" zorunludur: ``sms`` işaretli değilse giden kutusuna
      'sms' düşer (operatör BOSS'ta gönderip "işlendi" der).
    - Ulaşılamadı durumundaki işte uyanma = merdivendeki sonraki arama zamanı (≥3 s; 1. gün dolunca ertesi gün).
    - İrtibat hatalı → iş "İrtibat hatalı (ATA havuzu)" askısına alınır (saati durdurmaz, açıklama zorunlu);
      ``yeni_numara`` ile gelen aramada merdiven sıfırlanır.
    - Açık elle abone askısının geçerliliği (Webphone + SMS + 2 gün) her aramadan sonra yeniden değerlendirilir.
    Arama ``surum`` artırmaz (not gibi eklenen bir olgudur); iş durumunu değiştirirse (ATA) artırır.
    """
    from . import gorunum
    H = _H()
    if sonuc not in kurallar.ARAMA_SONUCLARI:
        raise H.Gecersiz("Tanınmayan arama sonucu.", kod="alan_eksik", secenekler=list(kurallar.ARAMA_SONUCLARI))
    kural = kurallar.oku(conn, "arama_merdiveni")
    an = zaman.simdi()
    uygun, neden = kurallar.aranabilir_mi(an, kural)
    if not uygun:
        raise H.Gecersiz(neden, kod="arama_saati")
    en_az = int(kural.get("min_sure_sn") or 0)
    if sonuc == "ulasilamadi" and sure_sn is not None and int(sure_sn) < en_az:
        raise H.Gecersiz(f"Ulaşılamadı sayılması için en az {en_az} sn çaldırın.", kod="arama_kisa")
    if sonuc == "yanlis_no" and not (notu or "").strip():
        raise H.AlanEksik("Hatalı iletişim bilgisini yazın (ATA havuzu açıklaması).")
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        if _istemci_tekrar(conn, k, istemci_id):
            return gorunum.ayrinti(conn, is_no, k)
        if r["durum"] in ("cozuldu", "kapandi"):
            raise H.Catisma(f"Bu iş '{ETIKET[r['durum']]}' durumunda; arama kaydedilmez.", kod="gecersiz_gecis")
        ulasilamadi = sonuc in kurallar.ULASILAMADI_SONUCLARI
        olay_yaz(conn, is_no, "arama", k, notu=(notu or ARAMA_METNI[sonuc])[:1000], istemci_id=istemci_id,
                 yeni={"sonuc": sonuc, "sure_sn": int(sure_sn) if sure_sn is not None else None,
                       "webphone": bool(webphone), "sms": bool(sms), "yeni_numara": bool(yeni_numara)})
        aramalar = aski_mod.aramalar(conn, [is_no]).get(is_no, [])
        m = kurallar.merdiven_durumu(aramalar, kural, zaman.simdi())
        # türetilen alanlar (surum artmaz): uyanma, masa vadesi, giden kutusu, teşhis sonucu
        a: dict = {}
        if r["masa_vade"]:
            a["masa_vade"] = None
        if teshis_sonucu:
            a["teshis_sonucu"] = teshis_sonucu
        if r["durum"] == "ulasilamadi" and m["sonraki"]:
            a["uyanma"] = m["sonraki"]
        if ulasilamadi and not sms and kural.get("sms_zorunlu", True):
            a["boss_bekleyen"] = _boss_bekleyen_hesapla(conn, r, r["atanan_id"], r["randevu_bas"], r["randevu_bit"],
                                                        sms_ek=True)
            a["boss_islendi"] = None
        if a:
            conn.execute(f"UPDATE is_emri SET {', '.join(f'{x}=?' for x in a)}, guncelleme=? WHERE is_no=?",
                         (*a.values(), zaman.metin(), is_no))
        aski_mod.gecerlilik_yenile(conn, is_no, kurallar.abone_aski_gecerli(
            aramalar, kurallar.oku(conn, "aski_gecerlilik"))[0])
    if sonuc == "yanlis_no" and r["durum"] != "askida" and (r["durum"], "askida") in GECISLER:
        # ATA havuzu: yeni numara gelene kadar askı (saati durdurmaz); üst sınır 'diğer' askı sınırı
        uyanma = zaman.simdi() + _uyanma_siniri(conn, r, _ATA_NEDENI)
        return gecis(conn, is_no, "askida", k, neden=_ATA_NEDENI, uyanma=zaman.metin(uyanma),
                     notu=f"ATA havuzu: {notu.strip()[:900]}")
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


# ============================================================================= BTK şikâyet sayacı ve TÇS (EK-12.2)
def btk_sikayet_kaydet(conn: sqlite3.Connection, is_no: str, k: dict | None, *, tarih: str | None = None,
                       reopen: bool = False, kaldir: bool = False, surum: int | None = None) -> dict:
    """İşte BTK şikâyeti bildirilmiş (FOX'ta şikâyet akışı var): 10 iş günü (reopen 5) sayacı başlar.

    BOSS raporu bunu söylemez; operatör işaretler. ``kaldir`` yanlış işareti geri alır.
    """
    from . import gorunum
    H = _H()
    t = zaman.oku(tarih) if tarih else zaman.simdi()
    if t is None:
        raise H.Gecersiz("Şikâyet tarihi okunamadı.", kod="alan_eksik")
    if t > zaman.simdi() + dt.timedelta(minutes=5):
        raise H.Gecersiz("Şikâyet tarihi ileride olamaz.", kod="alan_eksik")
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        _surum_denetle(conn, k, r, surum)
        yeni = {"kaldir": True} if kaldir else {"tarih": zaman.metin(t), "reopen": bool(reopen)}
        _olayli_surum(conn, r, k, "btk_sikayet", yeni,
                      "BTK şikâyet işareti kaldırıldı" if kaldir else
                      ("BTK şikâyeti (reopen) işaretlendi" if reopen else "BTK şikâyeti işaretlendi"))
    return gorunum.ayrinti(conn, is_no, k)


def tcs_gir(conn: sqlite3.Connection, is_no: str, k: dict | None, tarih: str, teyitli: bool, *,
            surum: int | None = None) -> dict:
    """TÇS (tahmini çözüm tarihi): bir kez girilir, değişmez; süre içindeki bir tarih seçilemez. Girilince iş BTK'da
    "Kapalı" görünür, FOX'ta sürer (rozet). Gerçekçi ve ekipten teyitli olmalı (``teyitli``)."""
    from . import gorunum
    H = _H()
    if not teyitli:
        raise H.AlanEksik("TÇS bir kez girilir ve değişmez: çözüm beklenen ekipten teyitli, gerçekçi tarih mi?")
    t = zaman.oku(tarih)
    if t is None:
        raise H.Gecersiz("TÇS tarihi okunamadı.", kod="alan_eksik")
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        _surum_denetle(conn, k, r, surum)
        b = btk_bilgileri(conn, [is_no]).get(is_no) or {}
        if not b.get("tarih"):
            raise H.Catisma("TÇS yalnız BTK şikâyeti işaretli işte girilir.", kod="btk_sikayet_yok")
        if b.get("tcs"):
            raise H.Catisma(f"TÇS zaten girilmiş ({zaman.oku(b['tcs']):%d.%m.%Y}); değiştirilemez.", kod="tcs_var")
        d = kurallar.btk_sikayet_durumu(b, None, zaman.simdi(), kurallar.oku(conn, "btk_sikayet"),
                                        kurallar.oku(conn, "resmi_tatiller"))
        if d and t <= zaman.oku(d["son_gun"]):
            raise H.Gecersiz(f"TÇS süre içindeki bir tarih olamaz (süre {zaman.oku(d['son_gun']):%d.%m.%Y} biter).",
                             kod="tcs_gecersiz")
        _olayli_surum(conn, r, k, "tcs", {"tcs": zaman.metin(t)}, f"TÇS girildi: {t:%d.%m.%Y}")
    return gorunum.ayrinti(conn, is_no, k)


def hedefleri_yeniden_hesapla(conn: sqlite3.Connection) -> int:
    """Şerit/hedef kuralı değişince açık işlerin şeridi, BTK hedefi ve hedef saati (``son24``) yeniden hesaplanır.

    Bunlar rapordan türeyen alanlardır: ``surum`` artmaz, olay yazılmaz (pano bir sonraki okumada görür).
    Çağıranın işlemi içinde koşar. Dönüş: değişen iş sayısı.
    """
    kr = kurallar.yukle(conn)
    n = 0
    for r in conn.execute("SELECT is_no, task_adi, acilis, serit, btk_hedef_saat, btk_hedef, son24 FROM is_emri "
                          "WHERE durum NOT IN ('cozuldu','kapandi')").fetchall():
        a = zaman.oku(r["acilis"])
        if a is None:
            continue
        serit, btk = serit_bul(r["task_adi"], kr["serit"])
        son24 = zaman.metin(a + dt.timedelta(hours=kurallar.hedef_saat(kr["hedef"], r["task_adi"])))
        btk_hedef = zaman.metin(a + dt.timedelta(hours=btk)) if btk else None
        if (serit, btk, btk_hedef, son24) != (r["serit"], r["btk_hedef_saat"], r["btk_hedef"], r["son24"]):
            n += conn.execute("UPDATE is_emri SET serit=?, btk_hedef_saat=?, btk_hedef=?, son24=? WHERE is_no=?",
                              (serit, btk, btk_hedef, son24, r["is_no"])).rowcount
    return n


def _olayli_surum(conn, r, k, tur: str, yeni: dict, notu: str) -> int:
    """İş satırında alan değiştirmeyen ama operasyonun kararı olan kayıt: surum +1 ve olay (veri ``yeni``de)."""
    conn.execute("UPDATE is_emri SET surum=surum+1, guncelleme=? WHERE is_no=? AND surum=?",
                 (zaman.metin(), r["is_no"], r["surum"]))
    return olay_yaz(conn, r["is_no"], tur, k, yeni={**yeni, "_surum": r["surum"] + 1}, notu=notu)


def teshis(conn: sqlite3.Connection, is_no: str, k: dict | None, sonuc: str, *, canli_test: bool = False,
           randevu_: dict | None = None, surum: int | None = None) -> dict:
    """Aranacaklar sonucu (spec §5.3.2): düzeldi · şimdi evde · başka gün · cevapsız · kapalı · yanlış no.

    Cevapsız / kapalı / yanlış no birer aramadır: EK-12.4 merdivenine yazılır (``arama_kaydet``).
    """
    from . import gorunum
    H = _H()
    if sonuc not in TESHIS_SONUCLARI:
        raise H.Gecersiz("Tanınmayan sonuç.", kod="alan_eksik")
    if sonuc == "duzeldi":
        return gecis(conn, is_no, "cozuldu", k, surum=surum, neden="telefonda_cozuldu", canli_test=canli_test)
    if sonuc in ("cevapsiz", "kapali", "yanlis_no"):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        _surum_denetle(conn, k, r, surum)
        if r["durum"] in ("cozuldu", "kapandi"):
            raise _gecersiz(r["durum"], "randevulu")
        return arama_kaydet(conn, is_no, k, {"cevapsiz": "ulasilamadi", "kapali": "mesgul_kapali",
                                             "yanlis_no": "yanlis_no"}[sonuc],
                            notu={"cevapsiz": "Cevap vermedi", "kapali": "Telefon kapalı",
                                  "yanlis_no": "Yanlış numara"}[sonuc], teshis_sonucu=sonuc)
    simdi_t = zaman.simdi()
    with islem(conn):
        r = is_getir(conn, is_no)
        _surum_denetle(conn, k, r, surum)
        if r["durum"] in ("cozuldu", "kapandi"):
            raise _gecersiz(r["durum"], "randevulu")
        if sonuc == "simdi_evde":
            bas, bit = zaman.metin(simdi_t), zaman.metin(simdi_t + dt.timedelta(hours=3))
        else:
            rv = randevu_ or {}
            bas, bit = randevu_dogrula(rv.get("bas"), rv.get("bit"))
        a = {"randevu_bas": bas, "randevu_bit": bit, "randevu_teyitli": 1, "teshis_sonucu": sonuc, "masa_vade": None}
        if r["durum"] in ("bekliyor", "triyaj", "ulasilamadi"):
            a.update(durum="randevulu", durum_zamani=zaman.metin(simdi_t))
        if sonuc == "simdi_evde" and r["atanan_id"] is not None:
            a["sira"] = 0                        # teknisyenin sırasında öne
        if r["atanan_id"] is not None:
            a["boss_bekleyen"] = _boss_bekleyen_hesapla(conn, r, r["atanan_id"], bas, bit)
        yaz(conn, r, a, k, "teshis", notu="Şimdi evde" if sonuc == "simdi_evde" else "Başka güne randevu")
        # müşteriyle konuşuldu: merdivene "ulaşıldı" yazılır (Webphone varsayılır)
        olay_yaz(conn, is_no, "arama", k, notu=ARAMA_METNI["ulasildi"],
                 yeni={"sonuc": "ulasildi", "sure_sn": None, "webphone": True, "sms": False, "yeni_numara": False})
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


# ============================================================================= toplu
def _toplu(conn, liste, fn, toplu_id: str | None = None) -> dict:
    """Her iş kendi işleminde: kısmi başarı normaldir (spec §5.5)."""
    H = _H()
    toplu_id = toplu_id or uuid.uuid4().hex[:12]
    atanan, atlanan = [], []
    for oge in liste:
        is_no = oge[0]
        try:
            fn(oge, toplu_id)
            atanan.append(is_no)
        except H.V2Hata as e:
            atlanan.append({"is_no": is_no, "kod": e.kod, "hata": e.mesaj})
    return {"toplu_id": toplu_id, "atanan": atanan, "atlanan": atlanan}


def oneri_onayla(conn: sqlite3.Connection, isler: dict[str, int], k: dict | None) -> dict:
    """O / Shift+O / toplu kart: önerisi olan işler önerilen teknisyen + dilimle atanır."""
    H = _H()

    def tek(oge, toplu_id):
        is_no, surum = oge
        r = is_getir(conn, is_no)
        if not r["oneri_teknik_id"] or r["durum"] in ("ulasilamadi", "triyaj"):
            raise H.Catisma("Bu işin önerisi yok.", kod="oneri_yok")
        rv = {"bas": r["oneri_bas"], "bit": r["oneri_bit"], "teyitli": False} if r["oneri_bas"] else None
        ata(conn, is_no, r["oneri_teknik_id"], k, randevu=rv, surum=surum, toplu_id=toplu_id, kaynak="oneri")

    return _toplu(conn, list((isler or {}).items()), tek)


def toplu_ata(conn: sqlite3.Connection, atamalar: list[dict], k: dict | None, parca: str | None = None) -> dict:
    def tek(oge, toplu_id):
        is_no, x = oge
        ata(conn, is_no, x.get("teknik_id"), k, randevu=x.get("randevu"), surum=x.get("surum"), toplu_id=toplu_id,
            kaynak="toplu")
        if parca:
            with islem(conn):
                conn.execute("UPDATE is_emri SET parca=?, parca_tarih=? WHERE is_no=?", (parca, zaman.metin()[:10], is_no))

    return _toplu(conn, [(x.get("is_no"), x) for x in atamalar or []], tek)


def geri_al(conn: sqlite3.Connection, is_no: str, olay_id: int, k: dict | None) -> dict:
    """Bildirimdeki "Geri al": 10 dk içinde, aynı kişi, iş o olaydan beri değişmemişse (spec §3.3 son satır)."""
    from . import gorunum
    with islem(conn):
        _geri_al_tek(conn, is_no, olay_id, k, toplu_id=None)
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


def _geri_al_tek(conn, is_no, olay_id, k, toplu_id):
    H = _H()
    o = conn.execute("SELECT * FROM is_emri_olay WHERE id=? AND is_no=?", (olay_id, is_no)).fetchone()
    if o is None or o["tur"] in ("olustu", "aktarim_degisti", "kayboldu", "yeniden_acildi", "geri_al", "not",
                                 "iletisim", "teknik_gordu") or not o["eski"]:
        raise H.Catisma("Bu değişiklik geri alınamaz.", kod="geri_alinamaz")
    if o["kullanici_id"] is None or o["kullanici_id"] != (k or {}).get("id"):
        raise H.Catisma("Yalnız değişikliği yapan kişi geri alabilir.", kod="geri_alinamaz")
    if (zaman.simdi() - zaman.oku(o["kayit_zamani"])).total_seconds() > GERI_AL_DK * 60:
        raise H.Catisma("Bu değişiklik artık geri alınamaz.", kod="sure_doldu")
    r = is_getir(conn, is_no)
    yeni = json.loads(o["yeni"] or "{}")
    if yeni.get("_surum") != r["surum"]:
        raise H.Catisma("Bu değişiklik artık geri alınamaz; iş sonra değişti.", kod="geri_alinamaz")
    eski = {a: v for a, v in json.loads(o["eski"]).items() if a in _GERI_ALINABILIR}
    if not eski:
        raise H.Catisma("Bu değişiklik geri alınamaz.", kod="geri_alinamaz")
    if r["durum"] == "askida" and eski.get("durum") not in (None, "askida"):
        aski_mod.kapat(conn, is_no, zaman.metin(), kaynak="elle")
    if "durum" in eski:
        eski["durum_zamani"] = zaman.metin()
    yaz(conn, r, eski, k, "geri_al", notu="Geri alındı", toplu_id=toplu_id)


def toplu_geri_al(conn: sqlite3.Connection, toplu_id: str, k: dict | None) -> dict:
    H = _H()
    olaylar = conn.execute("SELECT id, is_no, kullanici_id, kayit_zamani FROM is_emri_olay WHERE toplu_id=? AND "
                           "tur<>'geri_al' ORDER BY id DESC", (toplu_id,)).fetchall()
    if not olaylar:
        raise H.Catisma("Bu toplu işlem bulunamadı.", kod="geri_alinamaz")
    # Toplu geri al bütünüyle aynı kişinin ve 10 dakikanın içindedir (spec §5.3.2); iş iş değil, baştan denetlenir.
    if any(o["kullanici_id"] is None or o["kullanici_id"] != (k or {}).get("id") for o in olaylar):
        raise H.Catisma("Yalnız toplu işlemi yapan kişi geri alabilir.", kod="geri_alinamaz")
    ilk = min(zaman.oku(o["kayit_zamani"]) for o in olaylar)
    if (zaman.simdi() - ilk).total_seconds() > GERI_AL_DK * 60:
        raise H.Catisma("Bu değişiklik artık geri alınamaz.", kod="sure_doldu")
    geri, atlanan = [], []
    for o in olaylar:
        try:
            with islem(conn):
                _geri_al_tek(conn, o["is_no"], o["id"], k, toplu_id=f"geri-{toplu_id}")
            geri.append(o["is_no"])
        except H.V2Hata as e:
            atlanan.append({"is_no": o["is_no"], "kod": "guncel_degil" if e.kod == "geri_alinamaz" else e.kod})
    _sonra_oneri(conn, geri)
    return {"geri_alinan": geri, "atlanan": atlanan}


# ============================================================================= ticket bağı (F9)
def ticket_bagla(conn: sqlite3.Connection, is_no: str, k: dict | None, *, ticket_id: int | None = None,
                 yeni: dict | None = None, teknisyen_gonderme: bool = True, surum: int | None = None) -> dict:
    from saha import ticket as ticket_mod
    from . import gorunum
    H = _H()
    with islem(conn):
        r = is_getir(conn, is_no)
        _surum_denetle(conn, k, r, surum)
        if r["durum"] in ("cozuldu", "kapandi"):
            raise _gecersiz(r["durum"], "altyapi")
        if ticket_id is None and yeni:
            veri = {"konu": yeni.get("konu"), "ticket_no": yeni.get("ticket_no"), "detay": yeni.get("detay"),
                    "bina_serial": r["bina_serial"], "location_id": r["lokasyon"]}
            try:
                ticket_id, _ = ticket_mod.olustur(conn, veri, (k or {}).get("id"))
            except (ValueError, LookupError) as e:
                raise H.Gecersiz(str(e), kod="alan_eksik")
        if ticket_id is None:
            raise H.AlanEksik("Hangi ticket'a bağlansın?")
        t = conn.execute("SELECT id, konu, durum FROM ticket WHERE id=?", (int(ticket_id),)).fetchone()
        if t is None:
            raise H.Gecersiz("Ticket bulunamadı.", kod="alan_eksik")
        a: dict = {"ticket_id": int(ticket_id)}
        if teknisyen_gonderme and r["durum"] != "altyapi":
            a.update(durum="altyapi", durum_zamani=zaman.metin(), ilk_atama_zamani=r["ilk_atama_zamani"] or zaman.metin())
            if r["durum"] == "askida":
                aski_mod.kapat(conn, is_no, zaman.metin(), kaynak="elle")
        yaz(conn, r, a, k, "ticket", notu=f"Ticket #{t['id']} ({t['konu']}) bağlandı"
            + ("; teknisyen gönderilmez" if teknisyen_gonderme else ""))
    return gorunum.ayrinti(conn, is_no, k)


def ticket_ayir(conn: sqlite3.Connection, is_no: str, k: dict | None, surum: int | None = None) -> dict:
    from . import gorunum
    with islem(conn):
        r = is_getir(conn, is_no)
        _surum_denetle(conn, k, r, surum)
        a: dict = {"ticket_id": None}
        if r["durum"] == "altyapi":
            a.update(durum="triyaj" if r["triyaj_nedeni"] else "bekliyor", durum_zamani=zaman.metin())
        yaz(conn, r, a, k, "ticket", notu="Ticket'tan ayrıldı")
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


def ticket_degisti(conn: sqlite3.Connection, ticket_id: int, k: dict | None) -> list[str]:
    """Ticket ÇÖZÜLDÜ/KAPATILDI/İPTAL olunca bağlı 'altyapi' işler 'bekliyor'a döner (geçiş 17).

    ``PATCH /api/ticket/{id}`` ve Excel'den ticket aktarımı sonrası (WP-A) çağrılır; her rapor aktarımında da.
    Çağıranın işlemi açıksa onun içinde (SAVEPOINT) koşar.
    """
    t = conn.execute("SELECT id, durum FROM ticket WHERE id=?", (ticket_id,)).fetchone()
    if t is None or t["durum"] not in _TICKET_KAPALI:
        return []
    donen = []
    with islem(conn):
        for r in conn.execute("SELECT * FROM is_emri WHERE ticket_id=? AND durum='altyapi'", (ticket_id,)).fetchall():
            yaz(conn, r, {"durum": "triyaj" if r["triyaj_nedeni"] else "bekliyor", "durum_zamani": zaman.metin()},
                k, "durum", notu="Ticket çözüldü; teyitli ziyarete döndü")
            donen.append(r["is_no"])
    if not conn.in_transaction:
        _sonra_oneri(conn, donen)
    return donen


def ticket_denetimi(conn: sqlite3.Connection) -> list[str]:
    """Kaçan olmasın: bağlı ticket'ı kapanmış bütün 'altyapi' işler."""
    try:
        idler = [r[0] for r in conn.execute(
            f"SELECT DISTINCT e.ticket_id FROM is_emri e JOIN ticket t ON t.id = e.ticket_id WHERE e.durum='altyapi' "
            f"AND t.durum IN ({','.join('?' * len(_TICKET_KAPALI))})", _TICKET_KAPALI)]
    except sqlite3.OperationalError:
        return []
    out: list[str] = []
    for tid in idler:
        out += ticket_degisti(conn, tid, None)
    return out


def uyananlari_isle(conn: sqlite3.Connection, simdi: dt.datetime) -> list[str]:
    """Uyanma zamanı gelen askıdaki işler 'bekliyor'a döner (geçiş 15; olay 'uyandi', Aranacaklar bant 3)."""
    s = zaman.metin(simdi)
    satirlar = conn.execute("SELECT is_no FROM is_emri WHERE durum='askida' AND uyanma IS NOT NULL AND uyanma <= ?",
                            (s,)).fetchall()
    out = []
    for (is_no,) in satirlar:
        try:
            with islem(conn):
                r = is_getir(conn, is_no)
                if r["durum"] != "askida":
                    continue
                aski_mod.kapat(conn, is_no, r["uyanma"], kaynak="elle")
                yaz(conn, r, {"durum": "triyaj" if r["triyaj_nedeni"] else "bekliyor", "durum_zamani": s,
                              "uyanma": None}, None, "uyandi",
                    notu=f"Uyanma zamanı geldi ({zaman.saat_dk(r['uyanma'])})")
            out.append(is_no)
        except Exception:      # noqa: BLE001 — bir iş diğerlerini bekletmesin
            continue
    return out


# ============================================================================= öbek / mahalle / iletişim
def obek_ata(conn: sqlite3.Connection, is_no: str, obek_id: int | None, k: dict | None, surum: int | None) -> dict:
    """Elle öbek (F5): raporla ezilmez; ``None`` elle öbeği kaldırır (mahallesine göre)."""
    from . import aktarim, gorunum, obek
    H = _H()
    with islem(conn):
        r = is_getir(conn, is_no)
        _surum_denetle(conn, k, r, surum)
        if obek_id is not None and not conn.execute("SELECT 1 FROM obek WHERE id=? AND aktif=1", (obek_id,)).fetchone():
            raise H.Gecersiz("Bu öbek bulunamadı.", kod="alan_eksik")
        yeni_obek = obek.bul(conn, r["il_k"], r["ilce_k"], r["mahalle_k"])
        triyaj = aktarim.triyaj_hesapla(conn, il=r["il"], il_k=r["il_k"], ilce_k=r["ilce_k"], mahalle_k=r["mahalle_k"],
                                        mahalle_kaynak=r["mahalle_kaynak"], obek_id=yeni_obek, obek_elle_id=obek_id,
                                        eski_neden=r["triyaj_nedeni"])
        a = {"obek_elle_id": obek_id, "obek_id": yeni_obek, "triyaj_nedeni": triyaj}
        if r["durum"] == "triyaj" and not triyaj:
            a.update(durum="bekliyor", durum_zamani=zaman.metin())
        elif r["durum"] == "bekliyor" and triyaj:
            a.update(durum="triyaj", durum_zamani=zaman.metin())
        ad = conn.execute("SELECT ad FROM obek WHERE id=?", (obek_id,)).fetchone() if obek_id else None
        yaz(conn, r, a, k, "obek", notu=f"Öbeğe elle atandı: {ad[0]}" if ad else "Elle öbek kaldırıldı (mahallesine göre)")
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


def mahalle_sec(conn: sqlite3.Connection, is_no: str, mahalle_id: int, k: dict | None, surum: int | None) -> dict:
    """"Mahalleyi seç": mahalle_elle=1 (raporla ezilmez), öbek yeniden çözülür, konum mahalle merkezi."""
    from . import aktarim, gorunum, obek, sozluk
    H = _H()
    with islem(conn):
        r = is_getir(conn, is_no)
        _surum_denetle(conn, k, r, surum)
        m = sozluk.getir(conn, int(mahalle_id))
        if m is None:
            raise H.Gecersiz("Mahalle bulunamadı.", kod="alan_eksik")
        yeni_obek = obek.bul(conn, m["il_k"], m["ilce_k"], m["mahalle_k"])
        triyaj = aktarim.triyaj_hesapla(conn, il=m["il"], il_k=m["il_k"], ilce_k=m["ilce_k"], mahalle_k=m["mahalle_k"],
                                        mahalle_kaynak="elle", obek_id=yeni_obek, obek_elle_id=r["obek_elle_id"])
        a = {"il": m["il"], "ilce": m["ilce"], "mahalle": m["ad"], "il_k": m["il_k"], "ilce_k": m["ilce_k"],
             "mahalle_k": m["mahalle_k"], "mahalle_kaynak": "elle", "mahalle_elle": 1, "obek_id": yeni_obek,
             "triyaj_nedeni": triyaj}
        if r["konum_kaynak"] not in ("bina", "site") and m["lat"] is not None:
            a.update(lat=m["lat"], lon=m["lon"], konum_kaynak="mahalle_merkezi", konum_yaklasik=1)
        if r["durum"] == "triyaj" and not triyaj:
            a.update(durum="bekliyor", durum_zamani=zaman.metin())
        elif r["durum"] == "bekliyor" and triyaj:
            a.update(durum="triyaj", durum_zamani=zaman.metin())
        yaz(conn, r, a, k, "mahalle", notu=f"Mahalle elle seçildi: {m['ad']} · {m['ilce']}")
    _sonra_oneri(conn, [is_no])
    return gorunum.ayrinti(conn, is_no, k)


def not_ekle(conn: sqlite3.Connection, is_no: str, metin: str, k: dict | None, istemci_id: str | None = None) -> int:
    H = _H()
    metin = str(metin or "").strip()
    if not 1 <= len(metin) <= 1000:
        raise H.Gecersiz("Not 1–1000 karakter olmalı.", kod="alan_eksik")
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        if istemci_id and _istemci_tekrar(conn, k, istemci_id):
            return conn.execute("SELECT id FROM is_emri_olay WHERE kullanici_id=? AND istemci_id=?",
                                ((k or {}).get("id"), istemci_id)).fetchone()[0]
        return olay_yaz(conn, is_no, "not", k, notu=metin, istemci_id=istemci_id)


def iletisim(conn: sqlite3.Connection, is_no: str, musteri_tel: str | None, k: dict | None, surum: int | None) -> dict:
    """Müşteri telefonu yalnız ``ayar.musteri_tel='acik'`` iken tutulur (F21 · varsayılan kapalı)."""
    from saha import guvenlik
    from . import gorunum
    H = _H()
    ayar = conn.execute("SELECT deger FROM ayar WHERE anahtar='musteri_tel'").fetchone()
    if not ayar or ayar[0] != "acik":
        raise H.V2Hata("Müşteri telefonu tutulmuyor (ayar kapalı).", kod="tel_kapali", durum=403)
    tel = None
    if musteri_tel:
        tel = guvenlik.telefon_duzelt(musteri_tel)
        if tel is None:
            raise H.Gecersiz("Telefon numarası geçersiz.", kod="telefon_gecersiz")
    with islem(conn):
        r = is_getir(conn, is_no)
        yaz(conn, r, {"musteri_tel": tel}, k, "iletisim", surum=surum, notu="Müşteri telefonu değişti")
    return gorunum.ayrinti(conn, is_no, k)


def boss_islendi(conn: sqlite3.Connection, is_no: str, islendi: bool, k: dict | None, surum: int | None = None) -> dict:
    """"BOSS'a işlendi" (giden kutusu). Sonraki raporda BOSS eşleşirse bayrak kalkar ("BOSS'ta doğrulandı")."""
    from . import gorunum
    with islem(conn):
        r = is_getir(conn, is_no)
        kapsam_denetle(conn, k, r)
        yaz(conn, r, {"boss_islendi": zaman.metin() if islendi else None}, k, "boss_islendi", surum=surum,
            notu="BOSS'a işlendi" if islendi else "BOSS işareti kaldırıldı")
        if islendi and "sms" in (r["boss_bekleyen"] or "").split(",") and not r["boss_islendi"]:
            # "Talep Ulaşamama SMS" BOSS'tan gönderildi: merdivendeki SMS'siz aramaya işlenir (askı geçerliliği)
            olay_yaz(conn, is_no, "arama_sms", k, yeni={"sms": True}, notu="Talep Ulaşamama SMS gönderildi (BOSS)")
            aski_mod.gecerlilik_yenile(conn, is_no, kurallar.abone_aski_gecerli(
                aski_mod.aramalar(conn, [is_no]).get(is_no, []), kurallar.oku(conn, "aski_gecerlilik"))[0])
    return gorunum.ayrinti(conn, is_no, k)


def boss_bagla(conn: sqlite3.Connection, is_no: str, boss_task_no: str, k: dict | None, surum: int | None) -> dict:
    """Bayi işi BOSS'ta açılınca: sonraki rapor AYNI satırı günceller (toplam artmaz). Otomatik birleşme yok."""
    import re as _re
    from . import gorunum
    H = _H()
    no = str(boss_task_no or "").strip()
    if not _re.fullmatch(r"\d{9}", no):
        raise H.Gecersiz("BOSS Task No 9 haneli olmalı.", kod="task_no_gecersiz")
    with islem(conn):
        r = is_getir(conn, is_no)
        if r["kaynak"] != "bayi" or r["boss_task_no"]:
            raise H.Catisma("Bu iş zaten BOSS'a bağlı.", kod="boss_no_kullanilmis")
        if conn.execute("SELECT 1 FROM is_emri WHERE boss_task_no=? OR is_no=?", (no, no)).fetchone():
            raise H.Catisma("Bu Task No başka bir işte.", kod="boss_no_kullanilmis")
        yaz(conn, r, {"boss_task_no": no}, k, "boss_bagla", surum=surum, notu=f"BOSS Task No bağlandı: {no}")
    return gorunum.ayrinti(conn, is_no, k)


# ============================================================================= bayi işi (F16)
def bayi_olustur(conn: sqlite3.Connection, veri: dict, k: dict | None) -> dict:
    """"+ Yeni iş": numara B-AAGGAA-NNN (günlük sayaç, BEGIN IMMEDIATE içinde MAX+1)."""
    from . import aktarim, gorunum, obek, sozluk
    H = _H()
    task = str(veri.get("task_adi") or "").strip()
    if not task:
        raise H.AlanEksik("İş tipini seçin.")
    istemci_id = veri.get("istemci_id")
    if istemci_id and _istemci_tekrar(conn, k, istemci_id):
        no = conn.execute("SELECT is_no FROM is_emri_olay WHERE kullanici_id=? AND istemci_id=?",
                          ((k or {}).get("id"), istemci_id)).fetchone()[0]
        return {"is_no": no, "is": gorunum.ayrinti(conn, no, k)}
    simdi_t = zaman.simdi()
    simdi = zaman.metin(simdi_t)
    bina = None
    if veri.get("bina_serial"):
        bina = conn.execute("SELECT * FROM bina WHERE bina_serial=?", (veri["bina_serial"],)).fetchone()
        if bina is None:
            raise H.Gecersiz("Bina bulunamadı.", kod="alan_eksik")
    mh = sozluk.getir(conn, int(veri["mahalle_id"])) if veri.get("mahalle_id") else None
    adres = str(veri.get("adres") or "").strip() or None
    if bina is None and (mh is None or not adres):
        raise H.AlanEksik("Bina ya da adres + mahalle gerekli.")
    kr = kurallar.yukle(conn)
    serit, btk = serit_bul(task, kr["serit"])
    hedef_saat = kurallar.hedef_saat(kr["hedef"], task)
    if bina is not None:
        c = sozluk.ilce_coz(sozluk.ilce_haritasi(conn), bina["il"], bina["ilce"])
        il, ilce = (c[2], c[3]) if c else (bina["il"], bina["ilce"])
        il_k, ilce_k = (c[0], c[1]) if c else ie.ilce_anahtari(bina["il"] or "", bina["ilce"] or "")
        mahalle = ie.mahalle_eki_sil(bina["mahalle"] or "") or None
        if mahalle == "Bilinmiyor":
            mahalle = None
        yer = {"il": il, "ilce": ilce, "mahalle": mahalle, "il_k": il_k, "ilce_k": ilce_k,
               "mahalle_k": ie.anahtar(mahalle) if mahalle else None, "mahalle_kaynak": "lokasyon",
               "bina_serial": bina["bina_serial"], "lokasyon": bina["location_id"], "lat": bina["lat"],
               "lon": bina["lon"], "konum_kaynak": "bina", "konum_yaklasik": 0}
        adres = adres or " ".join(str(x) for x in (bina["site_adi"] or bina["ad"], bina["sokak"], bina["kapi_no"],
                                                   mahalle, ilce) if x)
    else:
        yer = {"il": mh["il"], "ilce": mh["ilce"], "mahalle": mh["ad"], "il_k": mh["il_k"], "ilce_k": mh["ilce_k"],
               "mahalle_k": mh["mahalle_k"], "mahalle_kaynak": "elle", "bina_serial": None, "lokasyon": None,
               "lat": mh["lat"], "lon": mh["lon"], "konum_kaynak": "mahalle_merkezi", "konum_yaklasik": 1}
    musteri_no = str(veri.get("musteri_no") or "").strip() or None
    ozet = aktarim.musteri_ozeti(musteri_no)
    with islem(conn):
        on = f"B-{simdi_t:%y%m%d}-"
        son = conn.execute("SELECT MAX(CAST(SUBSTR(is_no, 10) AS INTEGER)) FROM is_emri WHERE is_no LIKE ?",
                           (on + "%",)).fetchone()[0]
        is_no = f"{on}{(son or 0) + 1:03d}"
        obek_id = obek.bul(conn, yer["il_k"], yer["ilce_k"], yer["mahalle_k"])
        triyaj = aktarim.triyaj_hesapla(conn, il=yer["il"], il_k=yer["il_k"], ilce_k=yer["ilce_k"],
                                        mahalle_k=yer["mahalle_k"], mahalle_kaynak=yer["mahalle_kaynak"],
                                        obek_id=obek_id, obek_elle_id=None)
        tk = altyapi_ticketi(conn, yer["bina_serial"])
        durum = "altyapi" if tk else ("triyaj" if triyaj else "bekliyor")
        tekrar = 1 if ozet and conn.execute(
            "SELECT 1 FROM is_emri WHERE musteri_ozet=? AND task_adi=? AND durum IN ('cozuldu','kapandi') AND "
            "COALESCE(cozum_zamani, kapanis) >= ?", (ozet, task, zaman.metin(simdi_t - dt.timedelta(days=7)))
        ).fetchone() else 0
        acik = {**yer, "is_no": is_no, "boss_task_no": None, "kaynak": "bayi", "satis_kanali": None,
                "kanal_grubu": "dehanet", "task_adi": task, "serit": serit, "btk_hedef_saat": btk,
                "musteri_no": musteri_no, "musteri_ozet": ozet,
                "musteri_adi": str(veri.get("musteri_adi") or "").strip() or None, "adres": adres,
                "obek_id": obek_id, "triyaj_nedeni": triyaj, "durum": durum, "durum_zamani": simdi,
                "ticket_id": tk["id"] if tk else None, "ilk_atama_zamani": simdi if tk else None,
                "acilis": simdi, "son24": zaman.metin(simdi_t + dt.timedelta(hours=hedef_saat)),
                "btk_hedef": zaman.metin(simdi_t + dt.timedelta(hours=btk)) if btk else None,
                "ilk_gorulme": simdi, "gorulme_zamani": simdi, "son_gorulme": simdi,
                "masa_vade": zaman.metin(simdi_t + dt.timedelta(minutes=45)) if serit == "BTK" else None,
                "olusturan_id": (k or {}).get("id"), "olusturan_ad": (k or {}).get("ad"), "guncelleme": simdi,
                "tekrar7g": tekrar}
        kol = list(acik)
        conn.execute(f"INSERT INTO is_emri ({', '.join(kol)}) VALUES ({', '.join('?' * len(kol))})", list(acik.values()))
        olay_yaz(conn, is_no, "olustu", k, yeni={"durum": durum, "kaynak": "bayi", "_surum": 1},
                 notu=str(veri.get("aciklama") or "")[:1000] or "Bayi işi açıldı", istemci_id=istemci_id)
    _sonra_oneri(conn, [is_no])
    return {"is_no": is_no, "is": gorunum.ayrinti(conn, is_no, k)}


# ============================================================================= teknik
def teknik_gordu(conn: sqlite3.Connection, k: dict, is_nolar) -> int:
    n = 0
    with islem(conn):
        for is_no in is_nolar or []:
            c = conn.execute("UPDATE is_emri SET teknik_gordu=? WHERE is_no=? AND atanan_id=? AND teknik_gordu IS NULL",
                             (zaman.metin(), is_no, k.get("id"))).rowcount
            if c:
                olay_yaz(conn, is_no, "teknik_gordu", k, notu="Teknisyen gördü")
                n += c
    return n


def sira_degistir(conn: sqlite3.Connection, k: dict, is_no: str, yeni_sira: int, neden: str,
                  istemci_id: str | None) -> dict:
    """Teknisyen kendi gün sırasını değiştirir ("yakındaydım", "müşteri aradı")."""
    from . import gorunum
    with islem(conn):
        r = is_getir(conn, is_no)
        if r["atanan_id"] != k.get("id"):
            raise _H().IsYok()
        if _istemci_tekrar(conn, k, istemci_id):
            return gorunum.ayrinti(conn, is_no, k)
        isler = [x[0] for x in conn.execute(
            "SELECT is_no FROM is_emri WHERE atanan_id=? AND durum IN ('atandi','yolda','sahada') "
            "ORDER BY COALESCE(sira, 999), randevu_bas, son24", (k["id"],)) if x[0] != is_no]
        yer = max(0, min(int(yeni_sira) - 1, len(isler)))
        isler.insert(yer, is_no)
        for i, no in enumerate(isler, start=1):
            if no != is_no:
                conn.execute("UPDATE is_emri SET sira=? WHERE is_no=?", (i, no))
        yaz(conn, r, {"sira": yer + 1}, k, "sira", istemci_id=istemci_id,
            notu={"yakindaydim": "Yakındaydım", "musteri_aradi": "Müşteri aradı"}.get(neden, "Sıra değişti"))
    return gorunum.ayrinti(conn, is_no, k)


# ============================================================================= BOSS ekip eşleme / iş aktarma
def boss_ekip_esle(conn: sqlite3.Connection, boss_ekip: str, teknik_id: int, k: dict | None) -> dict:
    """"Bu ekip kim?": kişinin boss_ekip'i yazılır, o ekibin atanmamış açık işleri tek hamlede atanır."""
    from . import kisi
    H = _H()
    t = teknik_denetle(conn, teknik_id)
    anahtar = ie.anahtar(boss_ekip or "")
    if not anahtar:
        raise H.AlanEksik("BOSS ekip adı gerekli.")
    with islem(conn):
        if "boss_ekip" in kisi.sutunlar(conn, "kullanici"):
            conn.execute("UPDATE kullanici SET boss_ekip=? WHERE id=?", (str(boss_ekip).strip(), t["id"]))
        conn.execute("INSERT INTO yonetim_kaydi (zaman, kullanici_id, kullanici_ad, eylem, hedef, ozet) "
                     "VALUES (?,?,?,?,?,?)", (zaman.metin(), (k or {}).get("id"), (k or {}).get("ad"), "boss_ekip",
                                              f"kullanici:{t['id']}", json.dumps({"boss_ekip_eslendi": True})))
    isler = [r["is_no"] for r in conn.execute(
        "SELECT is_no, boss_ekip FROM is_emri WHERE atanan_id IS NULL AND durum IN ('bekliyor','randevulu','triyaj') "
        "AND boss_ekip IS NOT NULL").fetchall() if ie.anahtar(r["boss_ekip"]) == anahtar]

    def tek(oge, toplu_id):
        ata(conn, oge[0], t["id"], k, toplu_id=toplu_id, kaynak="boss")

    s = _toplu(conn, [(no, None) for no in isler], tek)
    return {"toplu_id": s["toplu_id"], "atanan": len(s["atanan"]), "atlanan": s["atlanan"]}


def is_aktar(conn: sqlite3.Connection, kaynak_id: int, hedef_id: int, k: dict | None) -> dict:
    """Ekip: bir kişinin açık işleri başka teknik kişiye (her biri olaylı). WP-A'nın ucu bunu çağırır."""
    teknik_denetle(conn, hedef_id)
    isler = [r[0] for r in conn.execute("SELECT is_no FROM is_emri WHERE atanan_id=? AND durum IN "
                                        "('atandi','yolda','sahada','ulasilamadi')", (kaynak_id,))]

    def tek(oge, toplu_id):
        r = is_getir(conn, oge[0])
        # Ulaşılamadı işinde aynı işe habersiz ikinci gidiş yok (kural 8): teyitli randevusu yoksa aktarılmaz,
        # Aranacaklar'da kalır (atlanan listesinde 'teyit_gerekli' görünür).
        rv = {"bas": r["randevu_bas"], "bit": r["randevu_bit"], "teyitli": bool(r["randevu_teyitli"])} \
            if r["durum"] == "ulasilamadi" and r["randevu_bas"] else None
        ata(conn, oge[0], hedef_id, k, toplu_id=toplu_id, kaynak="elle", yine_de=True, randevu=rv,
            notu="İş aktarıldı")

    s = _toplu(conn, [(no, None) for no in isler], tek)
    return {"toplu_id": s["toplu_id"], "aktarilan": len(s["atanan"]), "atlanan": s["atlanan"]}
