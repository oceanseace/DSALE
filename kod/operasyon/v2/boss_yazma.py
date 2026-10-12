"""BOSS'a yazma: şablonlar (TEK yer), değer eşlemesi, kuyruk, önizleme, tek iş denemesi ve askı nedenleri.

Akış: uygulamada Ata / Askıya al / Not (akis.py) → ``kuyruga_ekle`` (``boss_yazma`` tablosu, durum 'bekliyor') →
eklenti ``GET /api/boss/yazilacaklar`` ile yoklar (``verilecekler``; yanıtta ``paralel`` = ``ayar.boss_yazma_paralel``,
varsayılan 6, 1–10) → kanca.js yürütücüsü (sınırlı havuz: aynı anda en çok ``paralel`` istek, 429/502/503/504'te
üstel geri çekilmeyle yeniden dener) →
``POST /api/boss/yazma-sonucu`` (``sonuc_al``: HTTP + BOSS returnCode/returnMessage).
Gerçek gönderim üç yoldan biriyle olur, başka hiçbir yoldan olmaz (her durumda şablon doğrulanmış olmalı:
``SABLONLAR[..]['dogrulandi']`` + ``TAHMINI`` boş):
  1) Eylemin kendi anahtarı (``EYLEM_ANAHTARI``): NOT ``ayar.boss_yazma_not`` ve ATAMA (+ randevu)
     ``ayar.boss_yazma_atama``, ikisi de varsayılan 'acik' (şablonlar 07.10'da gerçek BOSS istekleriyle, returnCode 0,
     doğrulandı) — genel anahtardan bağımsız;
  2) diğer eylemler (askı: alt neden kaynağı bilinmiyor, yalnız önizleme) için genel ``ayar.boss_yazma = 'acik'``
     (varsayılan 'kapali'; yalnız Administrator açar: ``yazma_ayarla``) VE şablon doğrulanmış olmalı;
  3) Administrator'ın TEK İŞ DENEMESİ (``deneme_baslat``; POST /api/boss/yazma-dene): anahtar kapalıyken bile
     yalnız o tek kayıt, yalnız bir kez verilir.
Notun BOSS durumu işin olaylarında görünür (``not_durumlari``: gonderiliyor / gonderildi / hata / kapali); atamanınki
çekmecede önizleme kayıtlarından (``onizleme`` → ``eylemler``).
Verilen gerçek istek 'gonderiliyor' olur ve KENDİLİĞİNDEN YENİDEN VERİLMEZ (çift yazma olmasın); sonucu
``YAZ_SONUC_SN`` içinde gelmezse 'hata' (sonuc_gelmedi, belirsiz) olur — BOSS'ta elle bakılır.
Önizleme: ``onizleme`` (GET /api/isler/{is_no}/boss-yazma-onizleme; kişisel alanlar maskeli); ``durum_ozeti``.
Askı nedenleri işe göre değişir (görevin ``taskCategoryType`` + ``productCode``): ``neden_yolu`` → eklentiye
``okunacaklar`` → kanca o tek GET'i yapar → tanı ``aski_nedenleri`` → ``nedenleri_yaz`` (işe göre katalog).
Gövde kalıcı yazılmaz: tabloda yalnız eylemin girdisi durur; gövde her verilişte şablondan yeniden kurulur.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import sqlite3
import time

from operasyon import is_emri as ie

from . import boss_ham, ek_sema, zaman
from .hatalar import Catisma, Gecersiz
from .islem import islem

_log = logging.getLogger("operasyon.boss_yazma")

# ----------------------------------------------------------------------------- şablonlar (TEK yer)
# Biçimler 07.10'da BOSS'ta elle yapılan BAŞARILI isteklerden (returnCode 0) birebir alındı. "dogrulandi": gövde
# biçimi gerçek istekle teyit edildi mi. Askıda alt neden (suspendSubReasonId) kaynağı henüz bilinmiyor → False.
SABLONLAR: dict[str, dict] = {
    "atama": {"ad": "Atama + randevu", "yontem": "POST", "dizi": True, "dogrulandi": True,
              "yol": "/boss-gateway-service/appointment-service/api/v1/appointment"},
    "aski": {"ad": "Askıya al", "yontem": "POST", "dizi": False, "dogrulandi": False,
             "yol": "/boss-gateway-service/task-service/api/v1/task/suspend"},
    "not": {"ad": "Not", "yontem": "POST", "dizi": False, "dogrulandi": True,
            "yol": "/boss-gateway-service/task-service/api/v1/task/note"},
}

# Değer biçimleri (teyitli). appointmentDate BOSS'un kendi isteğinde hep bu sabittir.
BICIM = {"an": "%Y-%m-%d %H:%M:00", "aski_bitis": "%d.%m.%Y %H:%M"}
RANDEVU_SABIT = "2001-02-01 00:00:00"
# Teyit edilmemiş alanlar: şablon bunlar boşalana kadar genel anahtarla gönderilmez (yalnız tek iş denemesi).
TAHMINI = {"atama": (), "aski": ("suspendSubReasonId",), "not": ()}

DURUMLAR = ("bekliyor", "gonderiliyor", "onizleme", "gonderildi", "hata", "eksik", "yerine_yeni", "zaman_asimi")
SONUC_DURUMLARI = ("onizleme", "gonderildi", "hata", "ertelendi", "alindi")
YENIDEN_VER_SN = 60                     # önizleme/ertelenen kayıt bu kadar sonra yeniden verilir
EKSIK_YOKLA_SN = 300                    # eksik alanlı kayıt (ör. BOSS kimliği henüz yok) 5 dk'da bir yeniden denenir
YAZ_SONUC_SN = 300                      # gerçek istek verildi, sonucu bu kadar sürede gelmezse 'hata' (belirsiz)
DENEME_BEKLE_SN = 600                   # tek iş denemesi eklentiye bu süre içinde verilemezse düşer (hiçbir şey gitmez)
NEDEN_OKU_SN = 60                       # aynı katalog eklentiden en sık bu aralıkla istenir
NEDEN_ISTEK_SN = 600                    # katalog isteği bu kadar süre açık kalır
EN_COK_ISTEK = 20
EN_COK_TOPLU_ATAMA = 10                 # BOSS'un kendi çoklu ataması 7'liydi; 20'lik dizide 500 görüldü (07.10)
# Eklentinin BOSS'a aynı anda en çok kaç yazma isteği gönderdiği (``ayar.boss_yazma_paralel``; Ayarlar). Askı/not
# isteği tek görev taşır; atama dizisi zaten ≤ 10. 10'dan fazlası YOK (BOSS hız sınırı / hesap işaretlenmesi riski).
PARALEL_VARSAYILAN = 6
PARALEL_EN_COK = 10
VARSAYILAN_ACIKLAMA = "Teknik ekibe iletildi"   # açıklama boşsa (randevu ve askı); BOSS'un elle isteklerinde hep doluydu
YANIT_EN_COK = 400                      # 2xx olmayan yanıtın (maskeli) metni bu kadar saklanır
BEKLEME_GUN = 7
_VERILDI: dict[int, float] = {}         # kayıt id → eklentiye son verilme / son eksik denemesi (bellekte)
_NEDEN_ISTE: dict[str, list[float]] = {}  # katalog yolu → [istenme, son veriliş] (bellekte)
# Teslim onayı (09.10): kanca isteği kuyruğuna alınca "alindi" der. Eklentiye verilmiş ('gonderiliyor') ama kancaya hiç
# ulaşmamış kayıt (BOSS sekmesi kapalı/uyutulmuş, köprü yok, sayfa yenilendi) eskiden 5 dk sonra belirsiz "Sonuç
# gelmedi" oluyordu — hiçbir şey gönderilmemişken. Kanca onay veriyorsa (son ``ONAY_GECERLI_SN`` içinde en az bir
# "alindi" görüldü) onaysız kayıt ``ALINDI_BEKLE_SN`` sonra 'bekliyor'a döner ve yeniden verilir.
ALINDI_BEKLE_SN = 90
ONAY_GECERLI_SN = 30 * 60
_ALINDI_SON: list[float] = [0.0]         # son "alindi" (bellekte; eski kanca hiç demez → geri dönüş yapılmaz)


def sifirla() -> None:
    """Testler için bellek durumunu temizler."""
    _VERILDI.clear()
    _NEDEN_ISTE.clear()
    _ALINDI_SON[0] = 0.0


def paralel(conn: sqlite3.Connection) -> int:
    """Eşzamanlı BOSS yazma isteği sayısı (1–10; kayıt yoksa ya da bozuksa 6)."""
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='boss_yazma_paralel'").fetchone()
    try:
        n = int(str(r[0]).strip()) if r and r[0] not in (None, "") else PARALEL_VARSAYILAN
    except ValueError:
        n = PARALEL_VARSAYILAN
    return max(1, min(PARALEL_EN_COK, n))


def yazma_acik(conn: sqlite3.Connection) -> bool:
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar='boss_yazma'").fetchone()
    return bool(r) and r[0] == "acik"


# Kendi anahtarı olan eylemler → varsayılan. Burada olmayan eylem yalnız genel anahtarla (boss_yazma) gider.
# Askı kendi anahtarıyla varsayılan açık; ama alt neden kaynağı (``aski_alt_durumu``) bilinene dek şablon tahmini
# sayılır ve yalnız önizlenir.
EYLEM_ANAHTARI: dict[str, str] = {"not": "acik", "atama": "acik", "aski": "acik"}


def _aski_basarili_var(conn: sqlite3.Connection) -> bool:
    """BOSS'a gerçekten gitmiş ve returnCode 0 almış bir askı var mı (09.10 canlı: 82 kez ABONE > Aboneye Ulaşılamadı)."""
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return False
    return conn.execute("SELECT 1 FROM boss_yazma WHERE tur='aski' AND durum='gonderildi' AND sonuc LIKE "
                        "'%\"return_kodu\": 0%' LIMIT 1").fetchone() is not None


def tahmini(conn: sqlite3.Connection, tur: str) -> tuple:
    """Teyit edilmemiş alanlar. Askıda alt neden kimliği BOSS'tan (kayıt modu) okununca ya da gerçek bir askı
    BOSS'ta başarılı olunca boşalır."""
    if tur == "aski" and (aski_alt_durumu(conn)["biliniyor"] or _aski_basarili_var(conn)):
        return ()
    return tuple(TAHMINI.get(tur, ()))


def dogrulandi(conn: sqlite3.Connection, tur: str) -> bool:
    s = SABLONLAR.get(tur) or {}
    teyit = bool(s.get("dogrulandi") or (tur == "aski" and (aski_alt_durumu(conn)["biliniyor"]
                                                             or _aski_basarili_var(conn))))
    return teyit and not tahmini(conn, tur)


def eylem_acik(conn: sqlite3.Connection, tur: str) -> bool:
    """Bu eylem BOSS'a gerçekten gönderilir mi (şablon doğrulaması ayrıca aranır)."""
    if tur in EYLEM_ANAHTARI:
        r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (f"boss_yazma_{tur}",)).fetchone()
        return ((r[0] if r and r[0] else None) or EYLEM_ANAHTARI[tur]) == "acik"
    return yazma_acik(conn)


def gonderilir(conn: sqlite3.Connection, tur: str) -> bool:
    """Bu eylemin kaydı (tek iş denemesi dışında) BOSS'a gerçekten gider mi: anahtar açık + şablon doğrulanmış."""
    return dogrulandi(conn, tur) and eylem_acik(conn, tur)


def yazma_ayarla(conn: sqlite3.Connection, acik: bool) -> dict:
    """Genel anahtar (yalnız Administrator; yönetim kaydı çağıranda). Dönüş: durum özeti."""
    with islem(conn):
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES('boss_yazma', ?) ON CONFLICT(anahtar) DO UPDATE SET "
                     "deger=excluded.deger", ("acik" if acik else "kapali",))
    return durum_ozeti(conn)


def _ayar_json(conn, anahtar):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    try:
        return json.loads(r[0]) if r and r[0] else None
    except ValueError:
        return None


def _ayar_yaz(conn, anahtar, deger) -> None:
    if deger is None:
        conn.execute("DELETE FROM ayar WHERE anahtar=?", (anahtar,))
    else:
        conn.execute("INSERT INTO ayar(anahtar, deger) VALUES(?,?) ON CONFLICT(anahtar) DO UPDATE SET "
                     "deger=excluded.deger", (anahtar, json.dumps(deger, ensure_ascii=False)))


# ----------------------------------------------------------------------------- kuyruk
def kuyruga_ekle(conn: sqlite3.Connection, tur: str, is_no: str, girdi: dict, k: dict | None) -> int | None:
    """Uygulama eylemi → BOSS'a yazılacak kayıt. Yalnız BOSS işi (boss_task_no var). ASLA hata fırlatmaz: kuyruk
    kolaylıktır, eylemi bozmaz. Aynı işte bekleyen aynı türden atama/askı varsa eskisi 'yerine_yeni' olur."""
    try:
        if tur not in SABLONLAR:
            raise ValueError(tur)
        r = conn.execute("SELECT boss_task_no FROM is_emri WHERE is_no=?", (is_no,)).fetchone()
        if r is None or not r[0]:
            return None
        ek_sema.hazirla(conn)
        simdi = zaman.metin()
        with islem(conn):
            if tur in ("atama", "aski"):
                conn.execute("UPDATE boss_yazma SET durum='yerine_yeni', guncelleme=? WHERE is_no=? AND tur=? AND "
                             "durum='bekliyor'", (simdi, is_no, tur))
            return conn.execute(
                "INSERT INTO boss_yazma(tur, is_no, task_no, girdi, durum, olusturma, guncelleme, kullanici_id, "
                "kullanici_ad) VALUES(?,?,?,?,'bekliyor',?,?,?,?)",
                (tur, is_no, r[0], json.dumps(girdi or {}, ensure_ascii=False, default=str), simdi, simdi,
                 (k or {}).get("id"), (k or {}).get("ad"))).lastrowid
    except Exception:          # noqa: BLE001
        _log.exception("BOSS yazma kuyruğuna eklenemedi (%s)", tur)
        return None


def _bicim(an, bicim: str) -> str | None:
    t = zaman.oku(an)
    return t.strftime(BICIM[bicim]) if t else None


def _tarih(an, bicim: str) -> str | None:
    t = zaman.oku(an)
    return t.strftime(bicim) if t else None


def _ekip_kimligi(conn, teknik_id) -> str | None:
    try:
        r = conn.execute("SELECT boss_ekip_id FROM kullanici WHERE id=?", (teknik_id,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return str(r[0]) if r and r[0] not in (None, "") else None


def _uuid(conn, task_no, ham: dict | None = None) -> str | None:
    try:
        r = conn.execute("SELECT uuid FROM boss_gorev_kimlik WHERE task_no=?", (task_no,)).fetchone()
    except sqlite3.OperationalError:
        r = None
    if r and r[0]:
        return r[0]
    u = (ham or {}).get("id")
    return u if isinstance(u, str) and re.fullmatch(r"[0-9a-fA-F-]{36}", u) else None


def _metin(v) -> str | None:
    if v in (None, ""):
        return None
    s = str(v).strip()
    return s or None


def _gorev_no(v) -> str | None:
    """autoId = BOSS'un 9 haneli görev numarası (crmTaskId); başka biçim gönderilmez (eksik sayılır)."""
    s = _metin(v)
    return s if s and re.fullmatch(r"\d{9}", s) else None


def _sikayet_mi(ham: dict) -> bool:
    """isComplaint: BOSS'un bayrağı (null gelebilir) ya da task adı şikâyet (ör. "Kanal Şikayeti")."""
    return ham.get("isComplaint") is True or "SIKAYET" in ie.sade(ham.get("taskCategory") or "")


_YAPILACAK = {"atama": "atayın (randevuyla)", "aski": "askıya alın", "not": "not düşün"}


def _bekleme_sn(kayit) -> float:
    """Kaydın kuyrukta beklediği süre (sn; oluşturma bilinmiyorsa 0)."""
    try:
        t = zaman.oku(kayit["olusturma"])
    except (KeyError, IndexError):
        t = None
    return max(0.0, (zaman.simdi() - t).total_seconds()) if t else 0.0


def govde_kur(conn: sqlite3.Connection, kayit) -> tuple[dict, list[str]]:
    """Kayıt → (BOSS gövdesi ya da dizi gövdenin bir ÖĞESİ, eksik alanlar). Değerler şu anki iş satırından + BOSS'un
    ham alanlarından. Alan SIRASI BOSS'un kendi isteğindekiyle aynıdır."""
    girdi = json.loads(kayit["girdi"] or "{}")
    is_ = conn.execute("SELECT musteri_adi, musteri_no, askida_neden, uyanma FROM is_emri WHERE is_no=?",
                       (kayit["is_no"],)).fetchone()
    ham = boss_ham.oku(conn, [kayit["task_no"]]).get(kayit["task_no"]) or {}
    task_id = _uuid(conn, kayit["task_no"], ham)
    tur = kayit["tur"]
    if tur == "atama":
        # taskStatus: işin BOSS'taki gerçek durum kodu (OPEN, SUSPENDED, SEND_TO_CENTER …); BOSS'un kendi isteği de
        # listedeki durumu gönderir. 07.10'da askıdaki işlere "OPEN" gönderilince 38/38 HTTP 500 alındı.
        g = {"taskStatus": _metin(ham.get("taskStatus")) or "OPEN",
             "customerFullName": _metin(ham.get("customerName")) or (_metin(is_["musteri_adi"]) if is_ else None),
             "customerNo": _metin(ham.get("customerNo")) or (_metin(is_["musteri_no"]) if is_ else None),
             "taskId": task_id,
             "start": _bicim(girdi.get("randevu_bas"), "an"), "end": _bicim(girdi.get("randevu_bit"), "an"),
             "description": _metin(girdi.get("notu")) or VARSAYILAN_ACIKLAMA,
             "autoId": _gorev_no(ham.get("crmTaskId")) or _gorev_no(kayit["task_no"]),
             "isComplaint": _sikayet_mi(ham), "type": "TECH", "isRetailerTask": True,
             "resourceId": _ekip_kimligi(conn, girdi.get("teknik_id")), "appointmentDate": RANDEVU_SABIT}
        zorunlu = ("customerFullName", "customerNo", "taskId", "start", "end", "autoId", "resourceId")
    elif tur == "aski":
        neden, alt = girdi.get("boss_neden_id"), girdi.get("boss_alt_neden_id")
        varsayilan = not girdi.get("boss_kimlik_elle") and (
            "boss_alt_otomatik" in girdi                      # eski ticket askısı kaydı (NETWORK): artık varsayılan çift
            or (girdi.get("boss_alt_ad") and varsayilan_mi(girdi.get("boss_neden_ad") or neden, girdi["boss_alt_ad"])))
        if varsayilan:
            # varsayılan çift (ABONE > Ulaşılamadı): kimlikler HER ZAMAN işin kendi kategorisinden yeniden çözülür
            # (kayıttaki kimlik başka kategoriden olabilir); liste yoksa alt boş kalır → kayıt bekler
            neden, alt, _e = varsayilan_kimlikler(conn, kayit["task_no"], _bekleme_sn(kayit))
        elif not alt and girdi.get("boss_alt_ad"):            # toplu askı: alt neden adı, kimlik liste gelince çözülür
            n2, a2, _e = aski_kimlikleri(conn, kayit["task_no"], girdi.get("boss_neden_ad"), girdi["boss_alt_ad"])
            neden, alt = neden or n2, a2
        if not neden:
            neden, alt = neden_esle(conn, girdi.get("neden") or (is_["askida_neden"] if is_ else None),
                                    katalog_anahtari(ham))
        g = {"taskId": task_id,
             "suspendStatusEndDate": _tarih(girdi.get("boss_bitis") or girdi.get("uyanma")
                                            or (is_["uyanma"] if is_ else None), aski_bitis_bicimi(conn)),
             "suspendReasonId": neden, "suspendSubReasonId": alt,
             "description": _metin(girdi.get("notu")) or VARSAYILAN_ACIKLAMA}
        zorunlu = ("taskId", "suspendStatusEndDate", "suspendReasonId", "suspendSubReasonId", "description")
    else:
        g = {"description": girdi.get("metin") or "", "taskId": task_id}
        zorunlu = ("description", "taskId")
    return g, [a for a in zorunlu if g.get(a) in (None, "")]


def _maskele(g):
    if isinstance(g, list):
        return [_maskele(x) for x in g]
    if isinstance(g, dict):
        return {a: (f"•••({len(str(v))})" if boss_ham.kisisel_mi(a) and v not in (None, "") else _maskele(v))
                for a, v in g.items()}
    return g


def _sonuc_yaz(conn, kayit_id: int, durum: str, sonuc: dict) -> None:
    conn.execute("UPDATE boss_yazma SET durum=?, sonuc=?, guncelleme=? WHERE id=?",
                 (durum, json.dumps(sonuc, ensure_ascii=False), sonuc["zaman"], kayit_id))


def _bayatlari_kapat(conn) -> None:
    """7 günden eski bekleyen kayıt 'zaman_asimi'; sonucu gelmeyen gerçek istek 'hata' (belirsiz, yeniden verilmez).
    Yoklama her 2,5 sn'de: yalnız varsa yazılır."""
    simdi = zaman.simdi()
    sinir = zaman.metin(simdi - dt.timedelta(days=BEKLEME_GUN))
    if conn.execute("SELECT 1 FROM boss_yazma WHERE durum='bekliyor' AND olusturma < ? LIMIT 1", (sinir,)).fetchone():
        with islem(conn):
            conn.execute("UPDATE boss_yazma SET durum='zaman_asimi', guncelleme=? WHERE durum='bekliyor' AND "
                         "olusturma < ?", (zaman.metin(), sinir))
    if time.time() - _ALINDI_SON[0] < ONAY_GECERLI_SN:
        _ulasmayanlari_geri_al(conn, simdi)
    sinir2 = zaman.metin(simdi - dt.timedelta(seconds=YAZ_SONUC_SN))
    eski = conn.execute("SELECT id FROM boss_yazma WHERE durum='gonderiliyor' AND guncelleme < ?", (sinir2,)).fetchall()
    if eski:
        with islem(conn):
            for (i,) in eski:
                _sonuc_yaz(conn, i, "hata", {"durum": "hata", "hata": "sonuc_gelmedi", "belirsiz": True,
                                             "zaman": zaman.metin()})
                _deneme_bitir(conn, i, {"durum": "hata", "hata": "sonuc_gelmedi", "belirsiz": True})


def _sonuc_json(metin) -> dict:
    try:
        j = json.loads(metin) if metin else {}
    except (ValueError, TypeError):
        return {}
    return j if isinstance(j, dict) else {}


def _ulasmayanlari_geri_al(conn, simdi: dt.datetime) -> int:
    """Eklentiye verilmiş ama kancanın "alindi" demediği kayıtlar (``ALINDI_BEKLE_SN`` geçti) 'bekliyor'a döner:
    BOSS'a hiçbir şey gitmedi, yeniden verilir. Tek iş denemesine dokunulmaz (kendi akışı var)."""
    sinir = zaman.metin(simdi - dt.timedelta(seconds=ALINDI_BEKLE_SN))
    d = _deneme(conn)
    deneme_id = d.get("id") if d else None
    geri = []
    for r in conn.execute("SELECT id, sonuc FROM boss_yazma WHERE durum='gonderiliyor' AND guncelleme < ?",
                          (sinir,)).fetchall():
        sn = _sonuc_json(r["sonuc"])
        if r["id"] != deneme_id and sn.get("verildi") and not sn.get("alindi"):
            geri.append(r["id"])
    if geri:
        an = zaman.metin()
        with islem(conn):
            for i in geri:
                conn.execute("UPDATE boss_yazma SET durum='bekliyor', sonuc=?, guncelleme=? WHERE id=? AND "
                             "durum='gonderiliyor'", (json.dumps({"geri": "kancaya_ulasmadi", "zaman": an}), an, i))
                _VERILDI.pop(i, None)
        _log.info("BOSS yazma: kancaya ulaşmayan %d kayıt yeniden kuyrukta", len(geri))
    return len(geri)


def boss_goruntusuyle_dogrula(conn: sqlite3.Connection) -> dict:
    """Sonucu gelmemiş yazma (belirsiz 'hata' sonuc_gelmedi ya da 1 dk'dan eski 'gonderiliyor') BOSS'un kendi
    görüntüsünde yapılmış görünüyorsa 'gonderildi' olur (sonuç: dogrulama=boss_goruntusu). 09.10 incelemesi: 306
    "Sonuç gelmedi" atamasının ≥ 209'u BOSS'ta aynı ekipte, 162'si aynı dilimde duruyordu (yazılmış, sonucu düşmüş).
    Atama: işin BOSS ekibi atanan teknisyene eşli ve (ikisi de varsa) BOSS randevu başlangıcı aynı dakika.
    Askı: BOSS durumu SUSPENDED. Yalnız işin o türden SON kaydı; son 7 gün. Her eşitlemenin sonunda (``boss.esitle``)."""
    from . import kisi
    out = {"atama": 0, "aski": 0}
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return out
    simdi = zaman.simdi()
    sinir = zaman.metin(simdi - dt.timedelta(days=BEKLEME_GUN))
    sinir_gonderiliyor = zaman.metin(simdi - dt.timedelta(seconds=60))
    adaylar = conn.execute(
        "SELECT y.* FROM boss_yazma y JOIN (SELECT is_no, tur, MAX(id) AS id FROM boss_yazma WHERE tur IN "
        "('atama','aski') AND durum <> 'yerine_yeni' GROUP BY is_no, tur) s ON s.id = y.id WHERE y.olusturma >= ? AND "
        "((y.durum='hata' AND y.sonuc LIKE '%\"sonuc_gelmedi\"%') OR (y.durum='gonderiliyor' AND y.guncelleme < ?))",
        (sinir, sinir_gonderiliyor)).fetchall()
    if not adaylar:
        return out
    harita = kisi.boss_ekip_haritasi(conn)
    hamlar = boss_ham.oku(conn, [a["task_no"] for a in adaylar if a["tur"] == "aski"])
    tamam = []
    for kayit in adaylar:
        r = conn.execute("SELECT boss_ekip, boss_randevu_bas FROM is_emri WHERE is_no=?", (kayit["is_no"],)).fetchone()
        if r is None:
            continue
        g = _girdi(kayit)
        if kayit["tur"] == "atama":
            ekip = str(r["boss_ekip"] or "").strip()
            if not ekip or harita.get(ie.anahtar(ekip)) != g.get("teknik_id"):
                continue
            bas_boss = str(r["boss_randevu_bas"] or "").replace("T", " ")[:16]
            bas_biz = str(g.get("randevu_bas") or "").replace("T", " ")[:16]
            if bas_boss and bas_biz and bas_boss != bas_biz:
                continue
        elif _metin((hamlar.get(kayit["task_no"]) or {}).get("taskStatus")) != "SUSPENDED":
            continue
        tamam.append(kayit)
    if tamam:
        with islem(conn):
            for kayit in tamam:
                _sonuc_yaz(conn, kayit["id"], "gonderildi", {"durum": "gonderildi", "dogrulama": "boss_goruntusu",
                                                             "onceki": kayit["durum"], "zaman": zaman.metin()})
                out[kayit["tur"]] += 1
    return out


# ----------------------------------------------------------------------------- tek iş denemesi (Administrator)
def _deneme(conn) -> dict | None:
    return _ayar_json(conn, "boss_yazma_deneme")


def _deneme_bitir(conn, kayit_id: int, sonuc: dict) -> None:
    """Deneme kaydının sonucu geldi (ya da zaman aştı): bekleyen deneme silinir, son deneme saklanır."""
    d = _deneme(conn)
    if not d or d.get("id") != kayit_id:
        return
    _ayar_yaz(conn, "boss_yazma_deneme", None)
    _ayar_yaz(conn, "boss_yazma_son_deneme", {**d, "sonuc": sonuc, "bitis": zaman.metin()})


def deneme_baslat(conn: sqlite3.Connection, is_no: str, eylem: str, k: dict | None,
                  neden_id: str | None = None, alt_neden_id: str | None = None) -> dict:
    """Bu işin bu eylemdeki SON kaydı, genel anahtar kapalı olsa da, eklentiye bir kez gerçek istek olarak verilir.
    Kayıt uygulamada eylem yapılınca oluşur (Ata / Askıya al / Not); burada yalnız seçilir. Aynı anda tek deneme."""
    if eylem not in SABLONLAR:
        raise Gecersiz("Eylem tanınmadı.", kod="alan_eksik", secenekler=list(SABLONLAR))
    if not ek_sema.var_mi(conn, "boss_yazma"):
        raise Gecersiz("Bu işte BOSS'a yazılacak kayıt yok.", kod="kayit_yok")
    _bayatlari_kapat(conn)
    d = _deneme(conn)
    if d:
        r = conn.execute("SELECT durum FROM boss_yazma WHERE id=?", (d.get("id"),)).fetchone()
        if r and r[0] in ("bekliyor", "gonderiliyor") and (time.time() - float(d.get("an") or 0)) < DENEME_BEKLE_SN:
            raise Catisma("Bir deneme zaten sürüyor; sonucunu bekleyin.", kod="deneme_suruyor", kayit_id=d.get("id"))
    kayit = conn.execute("SELECT * FROM boss_yazma WHERE is_no=? AND tur=? AND durum IN "
                         "('bekliyor','onizleme','hata','eksik') ORDER BY id DESC LIMIT 1", (is_no, eylem)).fetchone()
    if kayit is None:
        raise Gecersiz(f"Bu işte BOSS'a yazılacak '{SABLONLAR[eylem]['ad']}' kaydı yok. Önce uygulamada bu işi "
                       f"{_YAPILACAK[eylem]}.", kod="kayit_yok")
    kayit = dict(kayit)
    if eylem == "aski" and (neden_id or alt_neden_id):
        girdi = json.loads(kayit["girdi"] or "{}")
        girdi.update({"boss_neden_id": str(neden_id or "")[:64] or None,
                      "boss_alt_neden_id": str(alt_neden_id or "")[:64] or None,
                      "boss_kimlik_elle": True})               # Administrator'ın seçtiği kimlik yeniden çözülmez
        kayit["girdi"] = json.dumps(girdi, ensure_ascii=False)
    g, eksik = govde_kur(conn, kayit)
    if eksik:
        raise Gecersiz("Gövdede eksik alan var; deneme gönderilmedi.", kod="alan_eksik", eksik=eksik)
    s = SABLONLAR[eylem]
    with islem(conn):
        conn.execute("UPDATE boss_yazma SET durum='bekliyor', girdi=?, sonuc=NULL, guncelleme=? WHERE id=?",
                     (kayit["girdi"], zaman.metin(), kayit["id"]))
        _ayar_yaz(conn, "boss_yazma_deneme", {"id": kayit["id"], "is_no": is_no, "tur": eylem, "an": time.time(),
                                              "zaman": zaman.metin(), "kullanici_id": (k or {}).get("id"),
                                              "kullanici_ad": (k or {}).get("ad")})
    _VERILDI.pop(kayit["id"], None)
    return {"kayit_id": kayit["id"], "is_no": is_no, "tur": eylem, "yontem": s["yontem"], "yol": s["yol"],
            "govde": _maskele([g] if s["dizi"] else g), "dogrulandi": dogrulandi(conn, eylem),
            "aciklama": "Eklenti bu tek isteği BOSS sekmesinden bir kez gönderecek (genel anahtar kapalı kalır). "
                        "Sonuç bu işin BOSS yazma önizlemesinde ve BOSS bağlantısı ekranında görünür."}


# ----------------------------------------------------------------------------- eklentiye verilecekler
def verilecekler(conn: sqlite3.Connection) -> dict:
    """Eklentinin yürüteceği istekler (en eskisi önce) + okunacak askı nedeni katalogları. Atamalar tek dizi gövdede
    toplanır (BOSS çoklu atamayı kabul ediyor). Eksik alanı olan kayıt verilmez (bir sonraki eşitleme tamamlayabilir).
    Gerçek istek (yaz=true) verilince kayıt 'gonderiliyor' olur ve bir daha verilmez."""
    acik = yazma_acik(conn)
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return {"yazma": "acik" if acik else "kapali", "istekler": [], "okunacaklar": _okunacaklar(),
                "paralel": paralel(conn)}
    _bayatlari_kapat(conn)
    simdi = time.time()
    for i in [i for i, t in _VERILDI.items() if simdi - t > 24 * 3600]:
        del _VERILDI[i]
    istekler = []

    def gercege(kayitlar, govde=None):
        an = zaman.metin()
        with islem(conn):
            for kk in kayitlar:
                sn = {"verildi": an}
                if kk["tur"] == "aski" and isinstance(govde, dict):   # başarılı olursa kategorinin alt kimliği öğrenilir
                    sn.update(alt_id=govde.get("suspendSubReasonId"),
                              anahtar=katalog_anahtari(boss_ham.oku(conn, [kk["task_no"]]).get(kk["task_no"]) or {}))
                conn.execute("UPDATE boss_yazma SET durum='gonderiliyor', sonuc=?, guncelleme=? WHERE id=? AND "
                             "durum='bekliyor'", (json.dumps(sn), an, kk["id"]))

    # 1) tek iş denemesi (anahtar kapalı olsa da; yalnız bir kez)
    d = _deneme(conn)
    deneme_id = d.get("id") if d else None
    if d:
        kayit = conn.execute("SELECT * FROM boss_yazma WHERE id=?", (deneme_id,)).fetchone()
        if kayit is None or kayit["durum"] not in ("bekliyor", "gonderiliyor"):
            with islem(conn):
                _ayar_yaz(conn, "boss_yazma_deneme", None)
        elif kayit["durum"] == "bekliyor":
            if simdi - float(d.get("an") or 0) > DENEME_BEKLE_SN:
                with islem(conn):
                    _deneme_bitir(conn, deneme_id, {"durum": "dusuruldu", "hata": "eklenti_almadi"})
            elif simdi - _VERILDI.get(deneme_id, 0) >= YENIDEN_VER_SN:
                g, eksik = govde_kur(conn, kayit)
                if not eksik:
                    s = SABLONLAR[kayit["tur"]]
                    _VERILDI[deneme_id] = simdi
                    istekler.append({"istek_id": f"d{deneme_id}", "tur": kayit["tur"], "kayitlar": [deneme_id],
                                     "yontem": s["yontem"], "yol": s["yol"], "govde": [g] if s["dizi"] else g,
                                     "dogrulandi": dogrulandi(conn, kayit["tur"]),
                                     "yaz": True, "deneme": True})
                    gercege([kayit], g)

    # 2) olağan kuyruk
    atama, tekil = [], []
    for kayit in conn.execute("SELECT * FROM boss_yazma WHERE durum='bekliyor' ORDER BY id LIMIT 500").fetchall():
        if kayit["id"] == deneme_id:
            continue
        if len(tekil) + len(atama_gruplari(atama)) >= EN_COK_ISTEK:
            break                                       # bu yoklamaya yeter; kalanı sonraki yoklamada
        if simdi - _VERILDI.get(kayit["id"], 0) < YENIDEN_VER_SN:
            continue
        g, eksik = govde_kur(conn, kayit)
        if kayit["tur"] == "aski" and "suspendReasonId" in eksik:
            neden_iste(conn, kayit["task_no"])           # işe özgü katalog yoksa eklentiden istenir
        elif kayit["tur"] == "aski" and "suspendSubReasonId" in eksik and g.get("suspendReasonId"):
            # alt liste kalıbı biliniyorsa eklentiden okunur — yalnız işin kendi kategorisiyle
            _alt_iste(conn, [g["suspendReasonId"]],
                      katalog_anahtari(boss_ham.oku(conn, [kayit["task_no"]]).get(kayit["task_no"]) or {}))
        if eksik:
            _VERILDI[kayit["id"]] = simdi + EKSIK_YOKLA_SN - YENIDEN_VER_SN
            continue
        (atama if kayit["tur"] == "atama" else tekil).append((kayit, g))

    def istek(tur, kayitlar, govde):
        if len(istekler) >= EN_COK_ISTEK:
            return
        s = SABLONLAR[tur]
        dogru = dogrulandi(conn, tur)
        e_acik = eylem_acik(conn, tur)
        yaz = bool(e_acik and dogru)
        for kk in kayitlar:
            _VERILDI[kk["id"]] = simdi
        # gönderilmeyecek istekte kişisel alanlar eklentiye de maskeli gider (yalnız önizleme yapılır)
        istekler.append({"istek_id": "y" + "-".join(str(kk["id"]) for kk in kayitlar), "tur": tur,
                         "kayitlar": [kk["id"] for kk in kayitlar], "yontem": s["yontem"], "yol": s["yol"],
                         "govde": govde if yaz else _maskele(govde), "dogrulandi": dogru, "yaz": yaz,
                         "eylem_acik": e_acik})
        if yaz:
            gercege(kayitlar, govde)

    for grup in atama_gruplari(atama):
        istek("atama", [kk for kk, _ in grup], [g for _, g in grup])
    for kk, g in tekil:
        istek(kk["tur"], [kk], g)
    return {"yazma": "acik" if acik else "kapali", "istekler": istekler, "okunacaklar": _okunacaklar(),
            "paralel": paralel(conn)}


def _girdi(kayit) -> dict:
    try:
        g = json.loads(kayit["girdi"] or "{}")
    except (ValueError, TypeError, KeyError, IndexError):
        return {}
    return g if isinstance(g, dict) else {}


def atama_gruplari(atama: list[tuple]) -> list[list[tuple]]:
    """Atama öğeleri (kayıt, gövde) → BOSS isteği başına gruplar: aynı ekip + aynı randevu dilimi bir gövdede
    (BOSS dizi gövdeyi kabul ediyor), grup başına en çok ``EN_COK_TOPLU_ATAMA``. Sıra: grubun ilk kaydı (en eski önce)."""
    gruplar: dict[tuple, list[tuple]] = {}
    for kk, g in atama:
        # aynı BOSS durumundakiler bir arada (askıdaki iş açık işin isteğini düşürmesin); "Yeniden dene" kaydı tek başına
        tek = _girdi(kk).get("tekli") and kk["id"]
        gruplar.setdefault((g.get("resourceId"), g.get("start"), g.get("end"), g.get("taskStatus"), tek or None),
                           []).append((kk, g))
    out = []
    for liste in gruplar.values():
        for i in range(0, len(liste), EN_COK_TOPLU_ATAMA):
            out.append(liste[i:i + EN_COK_TOPLU_ATAMA])
    return out


# Toplu atamanın BOSS hâli (ekranın özet satırı): kayıt durumu → dört durum
_ATAMA_DURUMU = {"bekliyor": "gidiyor", "gonderiliyor": "gidiyor", "gonderildi": "tamam", "hata": "hata",
                 "eksik": "hata", "zaman_asimi": "hata", "onizleme": "kapali"}
_EKSIK_METNI = {"resourceId": "teknisyenin BOSS ekibi yok", "taskId": "işin BOSS kimliği henüz gelmedi",
                "autoId": "BOSS task no 9 haneli değil", "start": "randevu saati yok", "end": "randevu saati yok",
                "customerFullName": "müşteri adı yok", "customerNo": "müşteri no yok"}


def atama_durumlari(conn: sqlite3.Connection, is_nolar: list[str]) -> dict[str, dict]:
    """İş no → son atama kaydının BOSS hâli {durum: gidiyor|tamam|hata|kapali|yok, hata?}. Bekleyen kayıtta eksik
    alan varsa (ör. teknisyenin BOSS ekibi yok) 'hata' + nedeni; atama anahtarı kapalıysa 'kapali'. Kişisel veri yok."""
    nolar = [str(n) for n in (is_nolar or [])][:500]
    out = {n: {"durum": "yok"} for n in nolar}
    if not nolar or not ek_sema.var_mi(conn, "boss_yazma"):
        return out
    acik = gonderilir(conn, "atama")
    for parca in range(0, len(nolar), 200):
        dilim = nolar[parca:parca + 200]
        satirlar = conn.execute(
            f"SELECT * FROM boss_yazma WHERE tur='atama' AND durum<>'yerine_yeni' AND is_no IN "
            f"({','.join('?' * len(dilim))}) ORDER BY id", dilim).fetchall()
        for kayit in satirlar:                                   # en yenisi sona: üstüne yazar
            d = _ATAMA_DURUMU.get(kayit["durum"], "hata")
            o: dict = {"durum": d}
            if kayit["durum"] == "bekliyor":
                if not acik:
                    o["durum"] = "kapali"
                else:
                    _g, eksik = govde_kur(conn, kayit)
                    if eksik:
                        o = {"durum": "hata", "hata": " · ".join(dict.fromkeys(_EKSIK_METNI.get(a, a) for a in eksik))}
            elif d == "hata" or kayit["durum"] == "gonderildi":
                try:
                    sn = json.loads(kayit["sonuc"]) if kayit["sonuc"] else {}
                except ValueError:
                    sn = {}
                rk = sn.get("return_kodu")
                if kayit["durum"] == "gonderildi" and rk not in (None, 0, "0"):
                    o = {"durum": "hata", "hata": sn.get("return_mesaji") or f"returnCode {rk}"}
                elif d == "hata":
                    o["hata"] = hata_metni(conn, kayit, sn)
                if o["durum"] == "hata":
                    o["yeniden"] = True                         # "Yeniden dene" ile tekrar kuyruğa alınabilir
            out[kayit["is_no"]] = o
    return out


def hata_metni(conn: sqlite3.Connection, kayit, sn: dict) -> str:
    """Hatalı kaydın okunur nedeni: BOSS returnMessage → yanıt gövdesinin (maskeli) iletisi → HTTP kodu; BOSS'un
    yanıt vermediği 5xx'te işin şu anki BOSS durumu ipucu olarak eklenir (ör. askıdaki işe randevu)."""
    m = sn.get("return_mesaji") or _yanit_iletisi(sn.get("yanit"))
    if not m:
        if sn.get("belirsiz"):
            m = "Sonuç gelmedi; BOSS'ta bakın."
        elif kayit["durum"] == "zaman_asimi":
            m = "Zaman aşımı"
        elif sn.get("http"):
            m = f"BOSS HTTP {sn['http']} (açıklama dönmedi)"
        else:
            m = sn.get("hata") or "BOSS'a yazılamadı"
    if (sn.get("http") or 0) >= 500:
        ham = boss_ham.oku(conn, [kayit["task_no"]]).get(kayit["task_no"]) or {}
        d = _metin(ham.get("taskStatus"))
        if d and d != "OPEN":
            m += f" · BOSS durumu: {_metin(ham.get('taskStatusDesc')) or d}"
    return m[:240]


def _yanit_iletisi(metin) -> str | None:
    """Saklanan yanıt metninden kısa ileti: JSON ise message/error/returnMessage, değilse metnin başı."""
    if not metin:
        return None
    try:
        j = json.loads(metin)
    except (ValueError, TypeError):
        j = None
    if isinstance(j, dict):
        for a in ("returnMessage", "message", "errorMessage", "error_description", "detail", "error", "title"):
            v = j.get(a)
            if isinstance(v, str) and v.strip():
                return v.strip()[:200]
        r = j.get("result")
        if isinstance(r, dict) and isinstance(r.get("returnMessage"), str):
            return r["returnMessage"][:200]
    t = re.sub(r"<[^>]+>", " ", str(metin))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:200] or None


_UZUN_SAYI = re.compile(r"\+?\d[\d\s]{8,}\d")


def yanit_maskele(metin) -> str | None:
    """2xx olmayan yanıtın metni (eklenti zaten maskeler; burada ikinci kez): JSON ise kişisel alanlar gizlenir,
    ≥ 10 haneli sayılar (telefon, TCKN, abone no) her durumda gizlenir. En çok ``YANIT_EN_COK`` karakter."""
    if metin in (None, ""):
        return None
    t = str(metin)[:4000]
    try:
        j = json.loads(t)
        t = json.dumps(_maskele(j), ensure_ascii=False)
    except (ValueError, TypeError):
        pass
    t = _UZUN_SAYI.sub(lambda x: "•••" if len(re.sub(r"\D", "", x.group(0))) >= 10 else x.group(0), t)
    return t[:YANIT_EN_COK]


def yeniden_dene(conn: sqlite3.Connection, is_nolar: list[str], k: dict | None) -> dict:
    """Toplu atamanın BOSS'a yazılamayan kayıtları (hata / zaman aşımı) aynı girdiyle yeniden kuyruğa alınır; her biri
    TEK BAŞINA istekte gider (bozuk bir iş diğerlerini düşürmesin). Kendiliğinden hiçbir şey yeniden gönderilmez."""
    nolar = [str(n) for n in (is_nolar or [])][:500]
    yeniden, atlanan = [], []
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return {"yeniden": yeniden, "atlanan": [{"is_no": n, "neden": "kayıt yok"} for n in nolar]}
    for no in nolar:
        r = conn.execute("SELECT * FROM boss_yazma WHERE is_no=? AND tur='atama' AND durum<>'yerine_yeni' "
                         "ORDER BY id DESC LIMIT 1", (no,)).fetchone()
        if r is None:
            atlanan.append({"is_no": no, "neden": "atama kaydı yok"})
            continue
        if r["durum"] in ("bekliyor", "gonderiliyor"):
            atlanan.append({"is_no": no, "neden": "zaten gidiyor"})
            continue
        if r["durum"] not in ("hata", "zaman_asimi", "eksik"):
            atlanan.append({"is_no": no, "neden": "hatalı değil"})
            continue
        girdi = {**_girdi(r), "tekli": True, "yeniden_of": r["id"]}
        if kuyruga_ekle(conn, "atama", no, girdi, k):
            yeniden.append(no)
        else:
            atlanan.append({"is_no": no, "neden": "BOSS işi değil"})
    return {"yeniden": yeniden, "atlanan": atlanan}


# ----------------------------------------------------------------------------- yazma kuyruğu (hata ayıklama ekranı)
KUYRUK_GUN = 7
_ASKI_EKSIK_METNI = {"taskId": "işin BOSS kimliği henüz gelmedi",
                     "suspendReasonId": "BOSS askı nedeni listesi okunuyor",
                     "suspendSubReasonId": "BOSS alt neden listesi bekleniyor (işin kategorisi)",
                     "suspendStatusEndDate": "bitiş zamanı yok", "description": "açıklama yok"}
_NOT_EKSIK_METNI = {"description": "not metni yok", "taskId": "işin BOSS kimliği henüz gelmedi"}
YENIDEN_DENENIR = ("hata", "zaman_asimi", "eksik")


def _eksik_metni(tur: str, eksik: list[str]) -> list[str]:
    t = {"atama": _EKSIK_METNI, "aski": _ASKI_EKSIK_METNI, "not": _NOT_EKSIK_METNI}.get(tur, {})
    return list(dict.fromkeys(t.get(a, a) for a in eksik))


def _kuyruk_satiri(conn, r) -> dict:
    """Kişisel veri YOK: yalnız kayıt no, zaman, eylem, task no, durum, BOSS/eklenti mesajı, eksik alan nedeni."""
    sn = _sonuc_json(r["sonuc"])
    durum, mesaj, eksik = r["durum"], None, []
    if durum == "bekliyor":
        _g, e = govde_kur(conn, r)
        if e:
            durum, eksik = "eksik", _eksik_metni(r["tur"], e)
    elif durum in ("hata", "zaman_asimi"):
        mesaj = hata_metni(conn, r, sn)
    elif durum == "gonderildi":
        rk = sn.get("return_kodu")
        if rk not in (None, 0, "0"):
            durum, mesaj = "hata", (sn.get("return_mesaji") or f"returnCode {rk}")[:240]
        elif sn.get("dogrulama") == "boss_goruntusu":
            mesaj = "Sonuç gelmedi; BOSS görüntüsünde yapılmış görüldü"
    elif durum == "onizleme":
        mesaj = "Yazma kapalı: yalnız önizlendi"
    return {"id": r["id"], "zaman": r["olusturma"], "guncelleme": r["guncelleme"], "tur": r["tur"],
            "eylem": SABLONLAR.get(r["tur"], {}).get("ad", r["tur"]), "task_no": r["task_no"], "is_no": r["is_no"],
            "durum": durum, "mesaj": mesaj, "eksik": eksik, "http": sn.get("http"),
            "return_kodu": sn.get("return_kodu"),
            "yeniden": durum in YENIDEN_DENENIR or (r["durum"] == "gonderildi" and durum == "hata")}


def kuyruk(conn: sqlite3.Connection, durum: str | None = None, tur: str | None = None, ara: str | None = None,
           gun: int = KUYRUK_GUN, limit: int = 500) -> dict:
    """Son ``gun`` günün BOSS yazma kayıtları (en yenisi önce; 'yerine_yeni' hariç) — hata ayıklama ekranı.
    Süzgeç: ``durum`` (bekliyor/gonderiliyor/gonderildi/hata/onizleme/eksik; hata zaman aşımını da kapsar), ``tur``
    (atama/aski/not), ``ara`` (task no ya da iş no parçası). Dönüş: {kayitlar, sayilar, toplam}."""
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return {"kayitlar": [], "sayilar": {}, "toplam": 0, "gun": gun}
    _bayatlari_kapat(conn)
    sinir = zaman.metin(zaman.simdi() - dt.timedelta(days=max(1, min(int(gun or KUYRUK_GUN), 30))))
    sql = "SELECT * FROM boss_yazma WHERE olusturma >= ? AND durum <> 'yerine_yeni'"
    p: list = [sinir]
    if tur in SABLONLAR:
        sql += " AND tur=?"
        p.append(tur)
    a = re.sub(r"[^\w-]", "", str(ara or ""))[:40]
    if a:
        sql += " AND (task_no LIKE ? OR is_no LIKE ?)"
        p += [f"%{a}%", f"%{a}%"]
    satirlar = [_kuyruk_satiri(conn, r) for r in conn.execute(sql + " ORDER BY id DESC LIMIT 2000", p).fetchall()]
    sayilar: dict[str, int] = {}
    for s in satirlar:
        k = "hata" if s["durum"] == "zaman_asimi" else s["durum"]
        sayilar[k] = sayilar.get(k, 0) + 1
    if durum:
        satirlar = [s for s in satirlar if s["durum"] == durum or (durum == "hata" and s["durum"] == "zaman_asimi")]
    return {"kayitlar": satirlar[:max(1, min(int(limit or 500), 2000))], "sayilar": sayilar,
            "toplam": len(satirlar), "gun": gun}


def kayit_yeniden(conn: sqlite3.Connection, kayit_id: int, k: dict | None) -> dict:
    """Kuyruk ekranındaki "Yeniden dene" (tek kayıt): hatalı / zaman aşımı / BOSS returnCode≠0 kayıt aynı girdiyle
    yeniden kuyruğa alınır (tek başına istekte); eksik alanlı bekleyen kayıt hemen yeniden değerlendirilir (eksik
    tamamlandıysa bir sonraki yoklamada gider). Gidiyor/başarılı kayıt yeniden gönderilmez (çift yazma olmasın)."""
    if not ek_sema.var_mi(conn, "boss_yazma"):
        raise Gecersiz("Kayıt yok.", kod="kayit_yok")
    r = conn.execute("SELECT * FROM boss_yazma WHERE id=?", (int(kayit_id),)).fetchone()
    if r is None:
        raise Gecersiz("Kayıt yok.", kod="kayit_yok")
    s = _kuyruk_satiri(conn, r)
    if s["durum"] == "eksik":
        _VERILDI.pop(r["id"], None)
        return {"kayit_id": r["id"], "yeni_id": None, "durum": "eksik", "eksik": s["eksik"],
                "aciklama": "Eksik bilgi tamamlanınca kendiliğinden gider; şimdi yeniden denenecek."}
    if not s["yeniden"]:
        raise Catisma("Bu kayıt yeniden denenmez (gidiyor ya da BOSS'ta başarılı).", kod="yeniden_olmaz",
                      kayit_durumu=s["durum"])
    if r["tur"] in ("atama", "aski"):
        son = conn.execute("SELECT MAX(id) FROM boss_yazma WHERE is_no=? AND tur=? AND durum<>'yerine_yeni'",
                           (r["is_no"], r["tur"])).fetchone()[0]
        if son and son != r["id"]:
            raise Catisma("Bu işin daha yeni bir kaydı var; yenisi geçerli.", kod="yeni_kayit_var", yeni_id=son)
    girdi = {**_girdi(r), "yeniden_of": r["id"]}
    if r["tur"] == "atama":
        girdi["tekli"] = True
    yeni = kuyruga_ekle(conn, r["tur"], r["is_no"], girdi, k)
    if not yeni:
        raise Gecersiz("BOSS işi değil.", kod="boss_disi")
    return {"kayit_id": r["id"], "yeni_id": yeni, "durum": "bekliyor", "eksik": [], "aciklama": "Yeniden kuyruğa alındı."}


def sonuc_al(conn: sqlite3.Connection, govde: dict) -> dict:
    """Eklentinin yürütme sonucu: {istek_id, kayitlar:[id], durum: onizleme|gonderildi|hata|ertelendi, http?, hata?,
    hazir?, return_kodu?, return_mesaji?}. 'ertelendi' = hiçbir şey gönderilmedi (BOSS başlıkları henüz yok): kayıt
    'bekliyor'a döner. Başarılı yanıtın gövdesi saklanmaz (yalnız durum, HTTP, returnCode/returnMessage); hatalı
    yanıtın metni (``yanit_metni``) maskelenip kısaltılarak saklanır."""
    if not isinstance(govde, dict) or not isinstance(govde.get("kayitlar"), list):
        raise Gecersiz("kayitlar listesi gerekli.", kod="alan_eksik")
    durum = govde.get("durum")
    if durum not in SONUC_DURUMLARI:
        raise Gecersiz("Durum tanınmadı.", kod="alan_eksik", secenekler=list(SONUC_DURUMLARI))
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return {"ok": True, "guncellenen": 0}
    idler = [int(x) for x in govde["kayitlar"][:100] if str(x).isdigit()]
    rk = govde.get("return_kodu")
    sonuc = {"durum": durum, "http": govde.get("http") if isinstance(govde.get("http"), int) else None,
             "hata": str(govde.get("hata"))[:200] if govde.get("hata") else None, "hazir": bool(govde.get("hazir")),
             "return_kodu": rk if isinstance(rk, int) and not isinstance(rk, bool)
             else (str(rk)[:40] if rk not in (None, "") else None),
             "return_mesaji": str(govde.get("return_mesaji"))[:200] if govde.get("return_mesaji") else None,
             # 2xx olmayan yanıtın (maskeli) metni: returnMessage dönmeyen 500'lerde nedeni görmek için
             "yanit": yanit_maskele(govde.get("yanit_metni")) if durum == "hata" else None,
             "zaman": zaman.metin()}
    n = 0
    if durum == "alindi":                          # kanca isteği kuyruğuna aldı (BOSS'a henüz gitmemiş olabilir)
        _ALINDI_SON[0] = time.time()
        with islem(conn):
            for i in idler:
                r = conn.execute("SELECT sonuc FROM boss_yazma WHERE id=? AND durum='gonderiliyor'", (i,)).fetchone()
                if r is not None:
                    sn = _sonuc_json(r[0])
                    sn["alindi"] = sonuc["zaman"]
                    n += conn.execute("UPDATE boss_yazma SET sonuc=? WHERE id=?",
                                      (json.dumps(sn, ensure_ascii=False), i)).rowcount
        return {"ok": True, "guncellenen": n}
    with islem(conn):
        for i in idler:
            if durum == "ertelendi":
                n += conn.execute("UPDATE boss_yazma SET durum='bekliyor', guncelleme=? WHERE id=? AND durum IN "
                                  "('bekliyor','gonderiliyor')", (sonuc["zaman"], i)).rowcount
                _VERILDI[i] = time.time()                     # bir dakika sonra yeniden verilir
                continue
            if durum == "gonderildi" and sonuc["return_kodu"] == 0:   # askı: bu kategorinin alt kimliği teyitli
                r = conn.execute("SELECT tur, sonuc FROM boss_yazma WHERE id=?", (i,)).fetchone()
                if r is not None and r[0] == "aski":
                    sn = _sonuc_json(r[1])
                    _basarili_alt_yaz(conn, sn.get("anahtar"), sn.get("alt_id"))
            # geç gelen sonuç: "sonucu gelmedi" (belirsiz) diye kapatılmış kayıt gerçek sonucunu alır (08.10: eşitleme
            # sürerken bekleyen yazmanın sonucu 5 dk'dan sonra geliyordu; BOSS'ta yazılmış iş uygulamada "Hata" kalıyordu)
            n += conn.execute("UPDATE boss_yazma SET durum=?, sonuc=?, guncelleme=? WHERE id=? AND (durum IN "
                              "('bekliyor','gonderiliyor') OR (durum='hata' AND sonuc LIKE '%\"sonuc_gelmedi\"%'))",
                              (durum, json.dumps(sonuc, ensure_ascii=False), sonuc["zaman"], i)).rowcount
            _VERILDI.pop(i, None)
            _deneme_bitir(conn, i, {k_: v for k_, v in sonuc.items() if k_ != "zaman"})
    return {"ok": True, "guncellenen": n}


def onizleme(conn: sqlite3.Connection, is_no: str) -> dict:
    """İşin BOSS'a yazılacak/yazılmış kayıtları (son 20): gövde (kişisel alanlar maskeli), eksik ve tahmini alanlar,
    eklentinin sonucu (BOSS returnCode/returnMessage dahil)."""
    acik = yazma_acik(conn)
    kayitlar = []
    d = _deneme(conn)
    if ek_sema.var_mi(conn, "boss_yazma"):
        for kayit in conn.execute("SELECT * FROM boss_yazma WHERE is_no=? ORDER BY id DESC LIMIT 20", (is_no,)).fetchall():
            s = SABLONLAR.get(kayit["tur"], {})
            g, eksik = govde_kur(conn, kayit)
            try:
                sonuc = json.loads(kayit["sonuc"]) if kayit["sonuc"] else None
            except ValueError:
                sonuc = None
            kayitlar.append({"id": kayit["id"], "tur": kayit["tur"], "ad": s.get("ad"), "durum": kayit["durum"],
                             "olusturma": kayit["olusturma"], "guncelleme": kayit["guncelleme"],
                             "kisi": kayit["kullanici_ad"], "yontem": s.get("yontem"), "yol": s.get("yol"),
                             "govde": _maskele([g] if s.get("dizi") else g), "eksik": eksik,
                             "tahmini": list(tahmini(conn, kayit["tur"])),
                             "dogrulandi": dogrulandi(conn, kayit["tur"]),
                             "deneme": bool(d and d.get("id") == kayit["id"]), "eklenti": sonuc})
    return {"is_no": is_no, "yazma": "acik" if acik else "kapali", "kayitlar": kayitlar,
            # eylem bu işte BOSS'a gerçekten gönderilir mi (anahtar + doğrulanmış şablon); çekmecedeki hâl buna bakar
            "eylemler": {t: "acik" if gonderilir(conn, t) else "kapali" for t in SABLONLAR},
            "aciklama": _aciklama(conn)}


def _aciklama(conn) -> str:
    giden = [SABLONLAR[t]["ad"].lower() for t in SABLONLAR if gonderilir(conn, t)]
    kalan = [SABLONLAR[t]["ad"].lower() for t in SABLONLAR if not gonderilir(conn, t)]
    if not giden:
        return "BOSS'a yazma kapalı: hiçbir şey gönderilmez (yalnız yöneticinin tek iş denemesi); gövde gösterilir."
    return (f"BOSS'a kendiliğinden yazılır: {', '.join(giden)}."
            + (f" Yalnız önizlenir: {', '.join(kalan)}." if kalan else ""))


def durum_ozeti(conn: sqlite3.Connection) -> dict:
    """BOSS bağlantısı ekranı için: ayar + şablonlar + duruma göre sayılar + son kayıt + deneme (kişisel veri yok)."""
    out = {"ayar": "acik" if yazma_acik(conn) else "kapali", "sayilar": {}, "son": None,
           "sablonlar": {t: {"ad": s["ad"], "dogrulandi": dogrulandi(conn, t),
                             "tahmini": list(tahmini(conn, t)), "acik": eylem_acik(conn, t),
                             "kendi_anahtari": t in EYLEM_ANAHTARI} for t, s in SABLONLAR.items()},
           "aski_alt": aski_alt_durumu(conn),
           "deneme": _deneme(conn), "son_deneme": _ayar_json(conn, "boss_yazma_son_deneme")}
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return out
    out["sayilar"] = {r[0]: r[1] for r in conn.execute("SELECT durum, COUNT(*) FROM boss_yazma GROUP BY durum")}
    r = conn.execute("SELECT id, tur, is_no, durum, guncelleme FROM boss_yazma ORDER BY id DESC LIMIT 1").fetchone()
    out["son"] = dict(r) if r else None
    return out


# Uygulamanın gördüğü not durumu (kayıt durumu → üç durum + kapalı)
_NOT_DURUMU = {"bekliyor": "gonderiliyor", "gonderiliyor": "gonderiliyor", "gonderildi": "gonderildi",
               "hata": "hata", "eksik": "hata", "zaman_asimi": "hata", "onizleme": "kapali", "yerine_yeni": "kapali"}


def not_durumlari(conn: sqlite3.Connection, is_no: str) -> dict[int, dict]:
    """İşin notları (olay id) → BOSS durumu {durum: gonderiliyor|gonderildi|hata|kapali, zaman, hata?}.
    'bekliyor' kayıt not anahtarı kapalıysa 'kapali' (gönderilmeyecek) sayılır. Kişisel veri yok."""
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return {}
    acik = gonderilir(conn, "not")
    out: dict[int, dict] = {}
    for kayit in conn.execute("SELECT id, girdi, durum, guncelleme, sonuc FROM boss_yazma WHERE is_no=? AND tur='not' "
                              "ORDER BY id", (is_no,)).fetchall():
        try:
            olay_id = int(json.loads(kayit["girdi"] or "{}").get("olay_id") or 0)
        except (ValueError, TypeError, AttributeError):
            continue
        if not olay_id:
            continue
        d = _NOT_DURUMU.get(kayit["durum"], "hata")
        if kayit["durum"] == "bekliyor" and not acik:
            d = "kapali"
        o = {"durum": d, "zaman": kayit["guncelleme"]}
        if d == "hata":
            try:
                sn = json.loads(kayit["sonuc"]) if kayit["sonuc"] else {}
            except ValueError:
                sn = {}
            o["hata"] = sn.get("return_mesaji") or sn.get("hata") or kayit["durum"]
        out[olay_id] = o
    return out


def eskileri_sil(conn: sqlite3.Connection, gun: int) -> int:
    """Saklama: ``gun``den eski, bekleyen olmayan kayıtlar silinir (girdide not metni olabilir)."""
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return 0
    sinir = zaman.metin(zaman.simdi() - dt.timedelta(days=gun))
    with islem(conn):
        return conn.execute("DELETE FROM boss_yazma WHERE durum NOT IN ('bekliyor','gonderiliyor') AND guncelleme < ?",
                            (sinir,)).rowcount


# ----------------------------------------------------------------------------- askı nedenleri (BOSS kataloğu)
# Katalog işe göre değişir: GET .../task/reasons/task-category/{taskCategoryType}/record-type/SUSPEND_REASONS/
# product-code/{productCode} (ikisi de görev listesinin ham alanı). Yanıt: content[{reasonId, code, description}].
# Alt nedenler (suspendSubReasonId) bu yanıtta GELMİYOR (07.10 canlı: alt=[]). BOSS'un askı penceresi üst neden
# seçilince ayrı bir GET ile alt nedenleri yükler (kapanış nedenlerinde: .../task/profix/reason/id/{GUID}/sub/reasons).
# Kanca "sub reason" geçen her GET'i (aski_alt_nedenleri) üst neden kimliğinin altına saklar. Üst kimlik bir ASKI
# kataloğu nedeniyse alt neden kaynağı BİLİNİR (``aski_alt_durumu``): askı şablonu doğrulanmış sayılır ve aynı yolun
# kalıbı (``alt_sablon``) öbür üst nedenlerin alt listelerini okumak için kullanılır. Kayıt modunda elle yapılan askı
# isteğinin (POST .../task/suspend) maskeli örneği ``ayar.boss_aski_ornek``'e yazılır (bitiş tarihi biçimi ondan).
NEDEN_YOLU = ("/boss-gateway-service/task-service/api/v1/task/reasons/task-category/{kategori}/record-type/"
              "SUSPEND_REASONS/product-code/{urun}")
_NEDEN_YOL_RE = re.compile(r"/task-category/([\w.-]{1,40})/record-type/SUSPEND_REASONS/product-code/([\w.-]{1,80})$")
_ALT_YOL_RE = re.compile(r"sub.?reason", re.I)
_GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_ALT = ("subReasons", "subReasonList", "suspendSubReasons", "children", "subList", "altNedenler", "items")
_PARCA = re.compile(r"[\w.-]{1,80}")
# Alt neden yolunun kalıbı. Gerçek yol (08.10 canlı): .../task/reason/id/{GUID}/sub/reasons/task-category/560/
# product-code/Tell_FiberInternetProduct — kategori + ürün işe göre; kalıpta {kategori} / {urun} olur. (Eskiden sonek
# en çok 40 karakterdi: bu yol kalıp sayılmıyor, NETWORK gibi öbür üst nedenlerin alt listeleri istenemiyordu.)
_ALT_SABLON_RE = re.compile(r"^/boss-gateway-service/task-service/api/v\d+/task/[\w/.-]{0,80}\{id\}[\w/.{}-]{0,120}$")
_ALT_KAT_RE = re.compile(r"(/task-category/)([\w.-]{1,40})")
_ALT_URUN_RE = re.compile(r"(/product-code/)([\w.-]{1,80})")


def _alt_kalibi(yol: str, guid: str) -> str | None:
    """Gerçek alt neden yolu → kalıp ({id}, varsa {kategori} ve {urun}); kalıba uymazsa None."""
    sab = _ALT_URUN_RE.sub(r"\1{urun}", _ALT_KAT_RE.sub(r"\1{kategori}", yol.replace(guid, "{id}")))
    return sab if _ALT_SABLON_RE.fullmatch(sab) else None


def katalog_anahtari(ham: dict) -> str | None:
    """Görevin askı nedeni kataloğu anahtarı "kategori|ürün" (``taskCategoryType`` + ``productCode``). Ürün kodu boş
    görevlerde (ör. kategori 40 Kanal Şikayeti) BOSS'un kendi isteği ``product-code/null`` gönderir → "40|null"."""
    kat, urun = _metin(ham.get("taskCategoryType")), _metin(ham.get("productCode")) or "null"
    if not kat or not _PARCA.fullmatch(kat) or not _PARCA.fullmatch(urun):
        return None
    return f"{kat}|{urun}"


# Alt neden listesi bir askı üst nedeninin ALTINDA ve kategori + ürüne göre değişir (09.10 canlı: ABONE kimliği her
# katalogda aynı, ama alt listesi kategori 40'ta "Ulaşılamadı" 9d1770dd…, 106'da başka). Bu yüzden alt listeler
# "kategori|ürün#ÜST" anahtarıyla (``alt_kat``) saklanır; yolunda kategori olmayan liste kategoriye bağlı değildir ("*").
_HER_KATEGORI = "*"


def _alt_yol_anahtari(yol: str | None) -> str:
    """Alt neden yolundaki kategori + ürün → "kategori|ürün"; yolda kategori yoksa "*"."""
    k = _ALT_KAT_RE.search(str(yol or ""))
    if not k:
        return _HER_KATEGORI
    u = _ALT_URUN_RE.search(str(yol))
    return f"{k.group(2)}|{u.group(2) if u else 'null'}"


def _kategori_alt(d: dict, anahtar: str | None, ust) -> list[dict] | None:
    """Bu kategorinin (``anahtar``) bu üst nedeninin alt listesi; bilinmiyorsa None. BAŞKA kategorinin listesi asla
    dönmez (yalnız aynı kategori ya da kategoriye bağlı olmayan "*" liste)."""
    u = str(ust or "").upper()
    if not u:
        return None
    ak = d.get("alt_kat") if isinstance(d.get("alt_kat"), dict) else {}
    for a in ((anahtar,) if anahtar else ()) + (_HER_KATEGORI,):
        v = ak.get(f"{a}#{u}")
        if isinstance(v, dict) and v.get("alt"):
            return v["alt"]
    eski = (d.get("alt") or {}).get(u) if isinstance(d.get("alt"), dict) else None      # alt_kat öncesi kayıt
    if isinstance(eski, dict) and eski.get("alt"):
        ya = _alt_yol_anahtari(eski.get("yol"))
        if ya == _HER_KATEGORI or (anahtar and ya == anahtar):
            return eski["alt"]
    if anahtar:                                       # katalog yanıtının kendi içindeki alt liste (o kategorinin)
        k = d.get("katalog") if isinstance(d.get("katalog"), dict) else {}
        for n in (k.get(anahtar) or {}).get("nedenler") or []:
            if isinstance(n, dict) and str(n.get("id") or "").upper() == u and n.get("alt"):
                return n["alt"]
    return None


def _yol(anahtar: str) -> str:
    kat, urun = anahtar.split("|", 1)
    return NEDEN_YOLU.format(kategori=kat, urun=urun)


def neden_yolu(conn: sqlite3.Connection, task_no: str) -> str | None:
    a = katalog_anahtari(boss_ham.oku(conn, [task_no]).get(task_no) or {})
    return _yol(a) if a else None


def neden_iste(conn: sqlite3.Connection, task_no: str) -> str | None:
    """İşin kataloğu yoksa eklentiden okunması istenir (bir sonraki yoklamada ``okunacaklar``). Dönüş: yol."""
    a = katalog_anahtari(boss_ham.oku(conn, [task_no]).get(task_no) or {})
    if not a:
        return None
    yol = _yol(a)
    if a not in _katalog(conn):
        _NEDEN_ISTE.setdefault(yol, [0.0, 0.0])[0] = time.time()
    return yol


def _okunacaklar() -> list[str]:
    simdi = time.time()
    out = []
    for yol, (istendi, verildi) in list(_NEDEN_ISTE.items()):
        if simdi - istendi > NEDEN_ISTEK_SN:
            del _NEDEN_ISTE[yol]
        elif simdi - verildi >= NEDEN_OKU_SN and len(out) < 5:
            _NEDEN_ISTE[yol][1] = simdi
            out.append(yol)
    return out


def _ad(o: dict):
    for a in ("name", "description", "reasonName", "reasonDesc", "label", "text", "value"):
        if isinstance(o.get(a), str) and o[a].strip():
            return o[a].strip()[:200]
    return None


def _kimlik(o: dict):
    for a in ("reasonId", "subReasonId", "suspendReasonId", "id", "code", "key"):
        if o.get(a) not in (None, "") and not isinstance(o[a], (dict, list)):
            return o[a]
    return None


def _dizi(veri) -> list:
    if isinstance(veri, list):
        return veri
    if isinstance(veri, dict):
        for a in ("content", "data", "items", "list", "result", "reasons", "body"):
            if isinstance(veri.get(a), list):
                return veri[a]
        for v in veri.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    return []


def nedenleri_cozumle(veri) -> list[dict]:
    """BOSS askı nedeni yanıtı → [{id, ad, kod, alt: [{id, ad}]}] (yalnız kimlik + ad + kod; başka alan saklanmaz).
    Alt nedenler bilinen adlı ya da herhangi bir iç nesne dizisinden alınır."""
    out = []
    for o in _dizi(veri)[:300]:
        if not isinstance(o, dict) or _ad(o) is None:
            continue
        alt = next((o[a] for a in _ALT if isinstance(o.get(a), list)), None)
        if alt is None:
            alt = next((v for v in o.values() if isinstance(v, list) and v and isinstance(v[0], dict)), [])
        kod = o.get("code") if isinstance(o.get("code"), str) else None
        out.append({"id": _kimlik(o), "ad": _ad(o), "kod": kod,
                    "alt": [{"id": _kimlik(x), "ad": _ad(x)} for x in alt[:300] if isinstance(x, dict) and _ad(x)]})
    return out


def _veri(conn) -> dict:
    d = _ayar_json(conn, "boss_aski_nedenleri")
    return d if isinstance(d, dict) else {}


def _katalog(conn) -> dict:
    k = _veri(conn).get("katalog")
    return k if isinstance(k, dict) else {}


def nedenleri_yaz(conn: sqlite3.Connection, yol: str | None, veri) -> int:
    """Kancadan gelen askı nedeni (ya da alt neden) listesi → ``ayar.boss_aski_nedenleri`` (boşsa dokunulmaz).
    Katalog yolundan işe özgü anahtar (kategori|ürün) çıkarılır. Dönüş: neden sayısı."""
    nedenler_ = nedenleri_cozumle(veri)
    if not nedenler_:
        return 0
    yol = str(yol or "")[:300]
    d = _veri(conn)
    simdi = zaman.metin()
    if _ALT_YOL_RE.search(yol):
        g = _GUID_RE.search(yol)
        if not g:
            return 0
        alt = d.get("alt") if isinstance(d.get("alt"), dict) else {}
        ust = g.group(0).upper()
        liste = [{"id": n["id"], "ad": n["ad"], "kod": n.get("kod")} for n in nedenler_]
        alt.pop(ust, None)
        alt[ust] = {"zaman": simdi, "yol": yol, "alt": liste}
        d["alt"] = dict(list(alt.items())[-200:])
        ak = d.get("alt_kat") if isinstance(d.get("alt_kat"), dict) else {}
        anah = f"{_alt_yol_anahtari(yol)}#{ust}"
        ak.pop(anah, None)
        ak[anah] = {"zaman": simdi, "yol": yol, "alt": liste}
        d["alt_kat"] = dict(list(ak.items())[-400:])
        if ust in _aski_ust_idleri(d):                      # askı nedeninin alt listesi: kaynak artık biliniyor
            sab = _alt_kalibi(yol, g.group(0))
            if sab:
                d["alt_sablon"] = sab
        _NEDEN_ISTE.pop(yol, None)
    else:
        m = _NEDEN_YOL_RE.search(yol)
        if m:
            k = _katalog(conn)
            k[f"{m.group(1)}|{m.group(2)}"] = {"zaman": simdi, "nedenler": nedenler_}
            d["katalog"] = dict(list(k.items())[-100:])
            _NEDEN_ISTE.pop(yol, None)
        d.update({"zaman": simdi, "yol": yol, "nedenler": nedenler_})
    with islem(conn):
        _ayar_yaz(conn, "boss_aski_nedenleri", d)
    simdi_sn = time.time()                            # liste bekleyen (eksik) kayıtlar bir sonraki yoklamada denenir
    for i in [i for i, t in _VERILDI.items() if t > simdi_sn]:
        _VERILDI.pop(i, None)
    return len(nedenler_)


def _aski_ust_idleri(d: dict) -> set[str]:
    """Askı kataloglarındaki (ve son okunan listedeki) üst neden kimlikleri (büyük harf)."""
    out = {str(n.get("id") or "").upper() for n in (d.get("nedenler") or []) if isinstance(n, dict)}
    k = d.get("katalog") if isinstance(d.get("katalog"), dict) else {}
    for v in k.values():
        for n in (v or {}).get("nedenler") or []:
            if isinstance(n, dict):
                out.add(str(n.get("id") or "").upper())
    out.discard("")
    return out


def aski_alt_durumu(conn: sqlite3.Connection) -> dict:
    """Askı alt nedeni kaynağı bilinir mi: bir askı üst nedeninin alt listesi BOSS'tan okunmuşsa evet. Ek olarak
    kayıt modunda yakalanan elle askı isteğinin örneği (alan adları, alt neden kimliği listede mi)."""
    d = _veri(conn)
    alt = d.get("alt") if isinstance(d.get("alt"), dict) else {}
    ustler = _aski_ust_idleri(d)
    dolu = {u: v for u, v in alt.items() if u in ustler and (v or {}).get("alt")}
    ornek = _ayar_json(conn, "boss_aski_ornek")
    eslesti = None
    if isinstance(ornek, dict) and ornek.get("alt_id"):
        eslesti = any(str(a.get("id") or "").upper() == str(ornek["alt_id"]).upper()
                      for v in alt.values() for a in (v or {}).get("alt") or [])
    return {"biliniyor": bool(dolu), "ust_sayisi": len(dolu), "alt_sayisi": sum(len(v["alt"]) for v in dolu.values()),
            "sablon": d.get("alt_sablon"), "ornek": ornek if isinstance(ornek, dict) else None,
            "ornek_eslesti": eslesti,
            "aciklama": None if dolu else ("Alt neden listesi bekleniyor: BOSS'ta bir işi elle askıya alırken Abone "
                                           "kaynaklı'yı seçin; eklenti alt nedenleri buraya getirir.")}


_TARIH_BICIMLERI = (("%d.%m.%Y %H:%M", re.compile(r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$")),
                    ("%d.%m.%Y %H:%M:%S", re.compile(r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}$")),
                    ("%Y-%m-%d %H:%M:%S", re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")),
                    ("%Y-%m-%dT%H:%M:%S", re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")),
                    ("%Y-%m-%d %H:%M", re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")))


def aski_ornek_yaz(conn: sqlite3.Connection, yol: str | None, govde) -> bool:
    """Kayıt modunda yakalanan elle askı isteği (POST .../task/suspend; eklentide maskeli) → ``ayar.boss_aski_ornek``:
    alan adları, üst/alt neden kimliği, bitiş tarihi BİÇİMİ (değeri değil). Kişisel veri saklanmaz."""
    if not re.search(r"/task/suspend$", str(yol or "")) or not isinstance(govde, dict):
        return False
    bitis = govde.get("suspendStatusEndDate")
    bicim = next((b for b, r in _TARIH_BICIMLERI if isinstance(bitis, str) and r.match(bitis.strip())), None)

    def kimlik(v):
        return str(v).strip()[:64] if isinstance(v, str) and _GUID_RE.fullmatch(v.strip()) else None

    o = {"zaman": zaman.metin(), "alanlar": sorted(str(a)[:60] for a in govde)[:30],
         "neden_id": kimlik(govde.get("suspendReasonId")), "alt_id": kimlik(govde.get("suspendSubReasonId")),
         "bitis_bicimi": bicim}
    with islem(conn):
        _ayar_yaz(conn, "boss_aski_ornek", o)
    return True


def aski_bitis_bicimi(conn: sqlite3.Connection) -> str:
    o = _ayar_json(conn, "boss_aski_ornek")
    b = o.get("bitis_bicimi") if isinstance(o, dict) else None
    return b if b in {x for x, _ in _TARIH_BICIMLERI} else BICIM["aski_bitis"]


def _alt_sablonu(d: dict) -> str | None:
    """Kayıtlı kalıp; yoksa daha önce görülmüş bir askı alt listesinin yolundan çıkarılır (08.10'da görülen ABONE
    alt yolu eski kurala uymadığı için kalıp hiç kaydedilmemişti)."""
    sab = d.get("alt_sablon")
    if sab and _ALT_SABLON_RE.fullmatch(sab):
        return sab
    ustler = _aski_ust_idleri(d)
    alt = d.get("alt") if isinstance(d.get("alt"), dict) else {}
    for u, v in alt.items():
        yol = str((v or {}).get("yol") or "")
        g = _GUID_RE.search(yol)
        if u in ustler and g and g.group(0).upper() == u:
            k = _alt_kalibi(yol, g.group(0))
            if k:
                return k
    return None


def _alt_iste(conn: sqlite3.Connection, ust_idler, anahtar: str | None = None) -> None:
    """Bu kategoride (``anahtar`` "kategori|ürün") alt listesi bilinmeyen askı üst nedenleri için (kalıp biliniyorsa)
    eklentiden okuma istenir. Kalıpta kategori/ürün varsa YALNIZ işin kendi kategorisiyle istenir (anahtar yoksa hiç)."""
    d = _veri(conn)
    sab = _alt_sablonu(d)
    if not sab:
        return
    if "{kategori}" in sab or "{urun}" in sab:
        if not anahtar or "|" not in anahtar:
            return
        kat, urun = anahtar.split("|", 1)
        sab = sab.replace("{kategori}", kat).replace("{urun}", urun)
    for u in list(ust_idler)[:20]:
        u = str(u or "")
        if _GUID_RE.fullmatch(u) and _kategori_alt(d, anahtar, u) is None:
            _NEDEN_ISTE.setdefault(sab.replace("{id}", u), [0.0, 0.0])[0] = time.time()


# Varsayılan askı (kullanıcı kararı 09.10, düzeltme): BÜTÜN askılar — tek iş, toplu, MAP, ticket otomatik askısı — ana
# neden ABONE ("Abone Kaynaklı") > alt neden "Ulaşılamadı"; açıklama boşsa "Teknik ekibe iletildi" (ticket askısında
# ticket notu). ABONE kimliği bütün kataloglarda aynı; ALT NEDEN KİMLİĞİ KATEGORİYE GÖRE DEĞİŞİR (kategori 40:
# "Ulaşılamadı" 9d1770dd…; başka kategoride "Aboneye Ulaşılamadı" …). Bu yüzden alt neden her iş için kendi
# kategorisinin listesinden seçilir (``varsayilan_kimlikler``): adı tam "Ulaşılamadı" olan, yoksa kodu ULASILAMADI olan.
# Liste yoksa eklentiden istenir ve kayıt BEKLER (eksik; hata değil). En son çare: aynı kategoride daha önce BAŞARILI
# (returnCode 0) gitmiş askının alt neden kimliği. Başka kategorinin kimliği hiçbir zaman gönderilmez.
VARSAYILAN_ASKI = {"neden_kod": "ABONE", "neden_ad": "Abone Kaynaklı",
                   "neden_id": "26CDE1BE-1B03-8A0A-5384-F0273F623CE7",
                   "alt_ad": "Ulaşılamadı", "alt_kod": "ULASILAMADI"}
OTOMATIK_NEDEN = VARSAYILAN_ASKI["neden_kod"]          # ticket askısı da aynı çifti kullanır
# Varsayılan sayılan alt neden adları (eski kayıtlar ve formlar "Aboneye Ulaşılamadı" gönderiyordu) ve eski sabit kimlik
# (yalnız TANINIR; gönderilmez — kimlik her iş için yeniden çözülür).
_VARSAYILAN_ALT_ADLARI = ("Ulaşılamadı", "Aboneye Ulaşılamadı")
_ESKI_ALT_ID = "7d5df9a2-6512-47e2-84de-20871862a531"
ALT_SON_CARE_SN = 15 * 60               # alt liste bu kadar beklenir; sonra aynı kategorinin başarılı kimliği denenir


def varsayilan_mi(neden: str | None, alt: str | None) -> bool:
    """Seçim varsayılan çift mi (üst: kod, ad ya da kimlik; alt: "Ulaşılamadı" / "Aboneye Ulaşılamadı")."""
    v = VARSAYILAN_ASKI
    n = ie.sade(neden or "")
    a = str(alt or "").strip()
    return (n in (ie.sade(v["neden_kod"]), ie.sade(v["neden_ad"]), ie.sade(v["neden_id"]))
            and (ie.sade(a) in {ie.sade(x) for x in _VARSAYILAN_ALT_ADLARI} or a.upper() == _ESKI_ALT_ID.upper()))


def ulasilamadi_sec(alt) -> dict | None:
    """Bir kategorinin alt listesinden varsayılan alt neden: adı tam "Ulaşılamadı" (Türkçe sadeleştirilmiş), yoksa kodu
    ULASILAMADI olan (ör. "Aboneye Ulaşılamadı"). Yoksa None."""
    liste = [x for x in alt or [] if isinstance(x, dict) and x.get("id")]
    ad, kod = ie.sade(VARSAYILAN_ASKI["alt_ad"]), ie.sade(VARSAYILAN_ASKI["alt_kod"])
    return (next((x for x in liste if ie.sade(x.get("ad") or "") == ad), None)
            or next((x for x in liste if ie.sade(x.get("kod") or "") == kod), None))


def _basarili_alt(conn: sqlite3.Connection, anahtar: str) -> str | None:
    """Bu kategoride (``anahtar``) BOSS'ta başarılı (returnCode 0) gitmiş varsayılan askının alt neden kimliği:
    ``ayar.boss_aski_alt_basarili`` (gönderimde kaydedilir) ya da eski başarılı kayıtların girdisi (görev aynı kategori)."""
    m = _ayar_json(conn, "boss_aski_alt_basarili")
    if isinstance(m, dict) and isinstance(m.get(anahtar), dict) and m[anahtar].get("alt_id"):
        return str(m[anahtar]["alt_id"])
    if not ek_sema.var_mi(conn, "boss_yazma"):
        return None
    satirlar = conn.execute("SELECT task_no, girdi FROM boss_yazma WHERE tur='aski' AND durum='gonderildi' AND sonuc "
                            "LIKE '%\"return_kodu\": 0%' ORDER BY id DESC LIMIT 300").fetchall()
    hamlar = boss_ham.oku(conn, [r[0] for r in satirlar])
    for r in satirlar:
        g = _sonuc_json(r[1])                         # girdi JSON'u (bozuksa {})
        a = str(g.get("boss_alt_neden_id") or "")
        if (_GUID_RE.fullmatch(a)
                and varsayilan_mi(g.get("boss_neden_ad") or g.get("boss_neden_id"), g.get("boss_alt_ad") or a)
                and katalog_anahtari(hamlar.get(r[0]) or {}) == anahtar):
            return a
    return None


def _basarili_alt_yaz(conn: sqlite3.Connection, anahtar: str | None, alt_id: str | None) -> None:
    if not anahtar or not alt_id:
        return
    m = _ayar_json(conn, "boss_aski_alt_basarili")
    m = m if isinstance(m, dict) else {}
    m.pop(anahtar, None)
    m[anahtar] = {"alt_id": str(alt_id)[:64], "zaman": zaman.metin()}
    _ayar_yaz(conn, "boss_aski_alt_basarili", dict(list(m.items())[-200:]))


def varsayilan_kimlikler(conn: sqlite3.Connection, task_no: str, bekleme_sn: float = 0,
                         iste: bool = True) -> tuple[str | None, str | None, str | None]:
    """Varsayılan çiftin BU İŞTEKİ (neden, alt neden, eksik metni). Alt neden yalnız işin kendi kategorisinin
    listesinden (``ulasilamadi_sec``). Liste yoksa eklentiden istenir (``iste``) ve alt None döner (kayıt bekler);
    ``bekleme_sn`` ≥ ``ALT_SON_CARE_SN`` ise (ya da liste istenemiyorsa) aynı kategorinin başarılı kimliği kullanılır."""
    v = VARSAYILAN_ASKI
    anahtar = katalog_anahtari(boss_ham.oku(conn, [task_no]).get(task_no) or {})
    if not anahtar:
        return v["neden_id"], None, "işin BOSS kategorisi bilinmiyor (eşitlemeyi bekleyin)"
    d = _veri(conn)
    k = d.get("katalog") if isinstance(d.get("katalog"), dict) else {}
    kat = (k.get(anahtar) or {}).get("nedenler") or []
    n = next((x for x in kat if isinstance(x, dict) and (ie.sade(x.get("kod") or "") == ie.sade(v["neden_kod"])
                                                        or ie.sade(x.get("ad") or "") == ie.sade(v["neden_ad"]))), None)
    n_id = (n or {}).get("id") or v["neden_id"]
    alt = _kategori_alt(d, anahtar, n_id)
    if alt is not None:
        a = ulasilamadi_sec(alt)
        if a:
            return n_id, a["id"], None
        return n_id, None, "bu işin BOSS kataloğunda Ulaşılamadı alt nedeni yok"
    if iste:
        if not kat:
            neden_iste(conn, task_no)
        _alt_iste(conn, [n_id], anahtar)
    if bekleme_sn >= ALT_SON_CARE_SN or not _alt_sablonu(d):
        b = _basarili_alt(conn, anahtar)
        if b:
            return n_id, b, None
    return n_id, None, "alt neden listesi bekleniyor"


def varsayilan_aski() -> dict:
    """Ayarlar ve formlar için: varsayılan çiftin adları + açıklama (kişisel veri yok)."""
    v = VARSAYILAN_ASKI
    return {**v, "aciklama": VARSAYILAN_ACIKLAMA, "etiket": f"{v['neden_ad']} > {v['alt_ad']}"}


def otomatik_alt(conn: sqlite3.Connection, task_no: str, ipucu: str | None,
                 bekleme_sn: float = 0) -> tuple[str | None, str | None, str | None]:
    """Ticket askısının (neden, alt neden, eksik) kimlikleri: varsayılan çift (``ipucu`` artık kullanılmaz)."""
    return varsayilan_kimlikler(conn, task_no, bekleme_sn)


def aski_kimlikleri(conn: sqlite3.Connection, task_no: str, neden: str | None, alt: str | None,
                    bekleme_sn: float = 0) -> tuple[str | None, str | None, str | None]:
    """Toplu askı seçimi (üst neden kodu ya da adı + alt neden adı) → bu işin kataloğundaki (neden kimliği, alt neden
    kimliği, eksik metni). Katalog işe göre (kategori + ürün) değişir; kimlikler her iş için ayrı bulunur. Varsayılan
    çift (ABONE > Ulaşılamadı) ``varsayilan_kimlikler`` ile (liste yoksa bekler)."""
    if varsayilan_mi(neden, alt):
        return varsayilan_kimlikler(conn, task_no, bekleme_sn)
    return _katalog_kimlikleri(conn, task_no, neden, alt)


def _is_listesi(conn: sqlite3.Connection, anahtar: str | None) -> tuple[list[dict], bool]:
    """İşin askı nedenleri: kendi kataloğu (yoksa son okunan liste — üst neden kimlikleri kataloglarda aynı); alt
    nedenler YALNIZ işin kategorisinden (``_kategori_alt``). Dönüş: (liste, işin kendi kataloğu mu)."""
    d = _veri(conn)
    k = d.get("katalog") if isinstance(d.get("katalog"), dict) else {}
    kendi = (k.get(anahtar) or {}).get("nedenler") if anahtar else None
    ham = kendi or d.get("nedenler") or []
    return [{**n, "alt": _kategori_alt(d, anahtar, n.get("id")) or []} for n in ham if isinstance(n, dict)], bool(kendi)


def _katalog_kimlikleri(conn: sqlite3.Connection, task_no: str, neden: str | None, alt: str | None,
                        iste: bool = True) -> tuple[str | None, str | None, str | None]:
    anahtar = katalog_anahtari(boss_ham.oku(conn, [task_no]).get(task_no) or {})
    liste, kendi = _is_listesi(conn, anahtar)
    if iste and not kendi and anahtar:
        neden_iste(conn, task_no)
    if not liste:
        return None, None, "BOSS askı nedenleri henüz okunmadı"
    s = ie.sade(neden or "")
    n = next((x for x in liste if s and (ie.sade(x.get("kod") or "") == s or ie.sade(x.get("ad") or "") == s)), None)
    if n is None:
        return None, None, "bu işin BOSS kataloğunda bu neden yok"
    if not alt:
        return n["id"], None, None
    sa = ie.sade(alt)
    a = next((x for x in n.get("alt") or [] if ie.sade(x.get("ad") or "") == sa or ie.sade(x.get("kod") or "") == sa),
             None)
    if a is None:
        if iste:
            _alt_iste(conn, [n["id"]], anahtar)
        return n["id"], None, "alt neden listesi bekleniyor" if not n.get("alt") else "bu alt neden bu işte yok"
    return n["id"], a["id"], None


def toplu_nedenler(conn: sqlite3.Connection, is_nolar: list[str]) -> dict:
    """Seçili işlerin askı nedenleri (kataloglarının birleşimi; neden kodu/adına göre, alt nedenler adına göre) — toplu
    askı penceresi için. Kataloğu okunmamış işler için eklentiden okuma istenir."""
    nolar = [str(n) for n in (is_nolar or [])][:2000]
    task = {}
    for i in range(0, len(nolar), 500):
        dilim = nolar[i:i + 500]
        for r in conn.execute(f"SELECT is_no, boss_task_no FROM is_emri WHERE is_no IN ({','.join('?' * len(dilim))})",
                              dilim):
            if r[1]:
                task[r[0]] = r[1]
    hamlar = boss_ham.oku(conn, list(task.values()))
    katalog = _katalog(conn)
    v = VARSAYILAN_ASKI
    anahtarlar: dict[str, str] = {}
    katalogsuz = 0
    for t in task.values():
        a = katalog_anahtari(hamlar.get(t) or {})
        if a and a in katalog:
            anahtarlar.setdefault(a, t)
        else:
            katalogsuz += 1
            if katalogsuz <= 5:
                neden_iste(conn, t)
                if a:
                    _alt_iste(conn, [v["neden_id"]], a)          # varsayılan çiftin bu kategorideki alt listesi
    birlesik: dict[str, dict] = {}

    def ekle(n, katalog_sayilir):
        k = ie.sade(n.get("kod") or n.get("ad") or "")
        if not k:
            return
        b = birlesik.setdefault(k, {"kod": n.get("kod"), "ad": n.get("ad"), "alt": {}, "katalog": 0})
        b["katalog"] += 1 if katalog_sayilir else 0
        for x in n.get("alt") or []:
            if x.get("ad"):
                b["alt"].setdefault(ie.sade(x["ad"]), x["ad"])

    for a in anahtarlar:                                        # alt nedenler her katalogda KENDİ kategorisinden
        liste = nedenler(conn, a)["nedenler"]
        for n in liste:
            ekle(n, True)
        _alt_iste(conn, [n.get("id") for n in liste], a)
    if not birlesik:
        for n in nedenler(conn)["nedenler"]:                    # hiç işe özgü katalog yoksa son okunan
            ekle(n, False)
    b = birlesik.setdefault(ie.sade(v["neden_kod"]), {"kod": v["neden_kod"], "ad": v["neden_ad"], "alt": {},
                                                      "katalog": 0})
    b["alt"].setdefault(ie.sade(v["alt_ad"]), v["alt_ad"])          # varsayılan alt neden hep seçilebilir
    liste = [{"kod": x["kod"], "ad": x["ad"], "katalog": x["katalog"], "alt": sorted(x["alt"].values())}
             for x in birlesik.values()]
    durum = aski_alt_durumu(conn)
    return {"nedenler": liste, "is_sayisi": len(nolar), "boss_disi": len(nolar) - len(task),
            "katalogsuz": katalogsuz, "bekleniyor": False,
            "alt_biliniyor": durum["biliniyor"], "gonderilir": gonderilir(conn, "aski"),
            "varsayilan": {"neden": v["neden_kod"], "alt": v["alt_ad"]},
            "aciklama": durum["aciklama"]}


def _alt_ekle(d: dict, liste: list[dict], anahtar: str | None = None) -> list[dict]:
    """Nedenlere alt listeleri: ``anahtar`` verilirse YALNIZ o kategorinin (``_kategori_alt``); verilmezse (genel
    görünüm, yalnız gösterim) üst neden kimliğiyle son okunan liste."""
    if anahtar:
        return [{**n, "alt": _kategori_alt(d, anahtar, n.get("id")) or []} for n in liste]
    alt = d.get("alt") if isinstance(d.get("alt"), dict) else {}
    return [{**n, "alt": n.get("alt") or (alt.get(str(n.get("id") or "").upper()) or {}).get("alt") or []}
            for n in liste]


def nedenler(conn: sqlite3.Connection, anahtar: str | None = None) -> dict:
    """Askı nedenleri: ``anahtar`` (kategori|ürün) verilirse o işe özgü katalog, yoksa son okunan."""
    d = _veri(conn)
    if anahtar:
        k = _katalog(conn).get(anahtar) or {}
        liste, an = k.get("nedenler") or [], k.get("zaman")
    else:
        liste, an = d.get("nedenler") or [], d.get("zaman")
    durum = aski_alt_durumu(conn)
    out = {"zaman": an, "yol": d.get("yol"), "nedenler": _alt_ekle(d, liste, anahtar), "alt_dogrulandi": durum["biliniyor"],
           "alt": durum,
           "aciklama": (None if liste else "BOSS'ta bir işi elle askıya alma penceresini bir kez açın; "
                                           "eklenti neden listesini buraya getirir.") or durum["aciklama"]}
    if not anahtar:                                    # bütün kataloglar (kategori|ürün → nedenler + alt nedenler)
        out["kataloglar"] = {a: {"zaman": (v or {}).get("zaman"),
                                 "nedenler": _alt_ekle(d, (v or {}).get("nedenler") or [], a)}
                             for a, v in _katalog(conn).items()}
    return out


def is_nedenleri(conn: sqlite3.Connection, is_no: str) -> dict:
    """Bir işin BOSS askı nedenleri (işin kategori + ürün koduna göre). Katalog yoksa eklentiden istenir
    (birkaç saniye sonra yeniden sorulur). Alt nedenler yalnız önbellekte varsa gelir, DOĞRULANMAMIŞTIR."""
    bos = {"is_no": is_no, "anahtar": None, "yol": None, "nedenler": [], "zaman": None, "bekleniyor": False,
           "alt_dogrulandi": aski_alt_durumu(conn)["biliniyor"]}
    r = conn.execute("SELECT boss_task_no FROM is_emri WHERE is_no=?", (is_no,)).fetchone()
    if r is None or not r[0]:
        return {**bos, "aciklama": "BOSS işi değil."}
    anahtar = katalog_anahtari(boss_ham.oku(conn, [r[0]]).get(r[0]) or {})
    if not anahtar:
        return {**bos, "aciklama": "İşin BOSS kategori / ürün kodu bilinmiyor (eşitlemeyi bekleyin)."}
    n = nedenler(conn, anahtar)
    if not n["nedenler"]:
        neden_iste(conn, r[0])
    return {**bos, "anahtar": anahtar, "yol": _yol(anahtar), "nedenler": n["nedenler"], "zaman": n["zaman"],
            "bekleniyor": not n["nedenler"],
            "aciklama": None if n["nedenler"] else "BOSS'tan okunuyor; birkaç saniye sonra yeniden bakın."}


def neden_esle(conn: sqlite3.Connection, metin: str | None, anahtar: str | None = None) -> tuple:
    """Uygulamadaki askı nedeni metni → (BOSS neden kimliği, alt neden kimliği). Bulunamazsa (None, None).
    Önce işin kendi kataloğu (``anahtar``), yoksa son okunan katalog."""
    s = ie.sade(metin or "")
    if not s:
        return None, None
    liste, _kendi = _is_listesi(conn, anahtar)        # alt nedenler yalnız işin kategorisinden
    for n in liste:                                   # önce birebir (üst ya da alt ad)
        for a in n["alt"]:
            if ie.sade(a["ad"]) == s:
                return n["id"], a["id"]
        if ie.sade(n["ad"]) == s:
            return n["id"], None
    for n in liste:                                   # sonra içerme
        for a in n["alt"]:
            if ie.sade(a["ad"]) and (ie.sade(a["ad"]) in s or s in ie.sade(a["ad"])):
                return n["id"], a["id"]
        if ie.sade(n["ad"]) and (ie.sade(n["ad"]) in s or s in ie.sade(n["ad"])):
            return n["id"], None
    return None, None
