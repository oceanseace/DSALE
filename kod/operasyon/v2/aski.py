"""EK-3 · BTK saati abone kaynaklı askıda durur (G2).

Her iş için askı aralıkları ``is_aski`` tablosunda tutulur:
- Rapordan (kaynak 'boss'): BOSS "Task Durumu" 'Askıya alındı'ya geçmişse aralık açılır, çıkmışsa kapanır.
  BOSS raporunda askı saati yoktur; başlangıç/bitiş raporun indirildiği ana yuvarlanır → ekranda "yaklaşık".
- Bizden (kaynak 'elle'): operatör "Askıya al" dediğinde kesin zamanla açılır, iş askıdan çıkınca kapanır.

Bir aralığın BTK saatini durdurup durdurmadığı ``ayar.btk_durduran_aski`` kuralından gelir (EK-12.3 varsayılanı:
abone kaynaklı, abone kaynaklı (akşam), BTK "Bilgi & Belge", genel arıza; TT kaynaklı teyit bekliyor → durdurmaz).
Elle açılan ABONE askısı ayrıca geçerli olmalıdır (Webphone + SMS + 2 farklı gün arama; ``kurallar.aski_gecerlilik``);
değilse süre saate eklenmez (``durdurur=0``) ve ekranda "geçersiz askı" uyarısı çıkar.
``btk_net_gecen = (şimdi − açılış) − Σ durduran askı`` ; ``btk_hedef_net = btk_hedef + Σ``.
24 saatlik söz takvim saatidir; ``ayar.son24_askida_durur`` açılırsa aynı kural ona da uygulanır.
Kurallar süreç araştırması (belgeler/TURKCELL_SUREC_BILGISI.md) netleşince ayardan değişir; koda gömülmez.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from operasyon import is_emri as ie

from . import zaman

BOSS_ASKI = "ASKIYA ALINDI"          # sade("Askıya alındı")
VARSAYILAN_KURAL = ["abone", "bilgi belge", "btk sureci", "genel ariza"]     # kurallar.VARSAYILAN ile aynı
# Elle askıda seçilen nedenler (ekranda liste; Backoffice Askı Kuralları §2.4). Durdurup durdurmadığı kuraldan hesaplanır.
VARSAYILAN_NEDENLER = [
    {"kod": "abone", "metin": "Abone kaynaklı (müşteriye ulaşılamadı / müşteri istedi)"},
    {"kod": "abone_aksam", "metin": "Abone kaynaklı (akşam araması)"},
    {"kod": "malzeme", "metin": "Malzeme bekleniyor"},
    {"kod": "genel_ariza", "metin": "Genel arıza (SOL kaynaklı)"},
    {"kod": "bilgi_belge", "metin": "BTK süreci kaynaklı (Bilgi & Belge)"},
    {"kod": "tt", "metin": "TT kaynaklı"},
    {"kod": "altyapi", "metin": "Altyapı / şebeke kaynaklı"},
    {"kod": "ata", "metin": "İrtibat hatalı (ATA havuzu)"},
    {"kod": "diger", "metin": "Diğer"},
]


def _ayar(conn, anahtar, varsayilan=None):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else varsayilan


def kural(conn: sqlite3.Connection) -> list[str]:
    try:
        v = json.loads(_ayar(conn, "btk_durduran_aski", "") or "null")
    except ValueError:
        v = None
    if not isinstance(v, list):
        v = VARSAYILAN_KURAL
    return [ie.sade(x) for x in v if ie.sade(x)]


def son24_durur(conn: sqlite3.Connection) -> bool:
    return str(_ayar(conn, "son24_askida_durur", "false")).lower() in ("1", "true", "evet", "acik")


def nedenler(conn: sqlite3.Connection) -> list[dict]:
    try:
        v = json.loads(_ayar(conn, "aski_nedenleri", "") or "null")
    except ValueError:
        v = None
    liste = v if isinstance(v, list) and v else VARSAYILAN_NEDENLER
    k = kural(conn)
    return [{"kod": n.get("kod"), "metin": n.get("metin"), "durdurur": durdurur_mu(n.get("metin"), k)} for n in liste]


def neden_metni(conn, neden: str | None) -> str | None:
    """Elle askıda gelen kod ('abone') → ekrandaki metin; serbest metin olduğu gibi kalır."""
    if not neden:
        return None
    for n in nedenler(conn):
        if n["kod"] == neden:
            return n["metin"]
    return str(neden)


def durdurur_mu(neden: str | None, kurallar: list[str]) -> bool:
    s = ie.sade(neden or "")
    return bool(s) and any(k in s for k in kurallar)


def boss_askida_mi(boss_durum) -> bool:
    return ie.sade(boss_durum or "") == BOSS_ASKI


# ----------------------------------------------------------------------------- yazma
def acik_aralik(conn, is_no) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM is_aski WHERE is_no=? AND bitis IS NULL ORDER BY id DESC LIMIT 1",
                        (is_no,)).fetchone()


def ac(conn, is_no: str, baslama: str, neden: str | None, kaynak: str, kurallar: list[str] | None = None,
       durdurur: bool | None = None) -> int | None:
    """Açık aralık yoksa açar. ``durdurur`` verilirse kuralın yerine o yazılır (geçersiz abone askısı → False).
    Dönüş: yeni aralığın id'si (zaten açıksa None)."""
    if acik_aralik(conn, is_no) is not None:
        return None
    k = kurallar if kurallar is not None else kural(conn)
    d = durdurur_mu(neden, k) if durdurur is None else bool(durdurur and durdurur_mu(neden, k))
    return conn.execute("INSERT INTO is_aski (is_no, baslama, bitis, neden, kaynak, durdurur) VALUES (?,?,NULL,?,?,?)",
                        (is_no, baslama, neden, kaynak, 1 if d else 0)).lastrowid


def gecerlilik_yenile(conn, is_no: str, gecerli: bool) -> int:
    """Açık ELLE abone askısında arama kaydı gelince geçerlilik yeniden değerlendirilir (durdurur 0 ↔ 1)."""
    r = acik_aralik(conn, is_no)
    if r is None or r["kaynak"] != "elle":
        return 0
    from . import kurallar
    if kurallar.aski_turu(r["neden"]) != "abone":
        return 0
    yeni = 1 if gecerli and durdurur_mu(r["neden"], kural(conn)) else 0
    if yeni == r["durdurur"]:
        return 0
    return conn.execute("UPDATE is_aski SET durdurur=? WHERE id=?", (yeni, r["id"])).rowcount


def kapat(conn, is_no: str, bitis: str, kaynak: str | None = None) -> int:
    """Açık aralığı kapatır (kaynak verilirse yalnız o kaynaktan açılmışsa). Bitiş başlangıçtan önce olamaz."""
    r = acik_aralik(conn, is_no)
    if r is None or (kaynak and r["kaynak"] != kaynak):
        return 0
    bitis = max(bitis, r["baslama"])
    return conn.execute("UPDATE is_aski SET bitis=? WHERE id=?", (bitis, r["id"])).rowcount


def aktarim_uzlas(conn, durumlar: list[tuple[str, str | None, str | None]], rapor_zamani: str,
                  kurallar: list[str] | None = None) -> dict:
    """Her rapordan sonra: [(is_no, boss_durum, askı nedeni)] → aralıkları aç/kapat.

    'elle' açılmış aralığa rapor dokunmaz (operatörün kesin zamanı korunur; iş askıdan çıkınca kapanır).
    """
    k = kurallar if kurallar is not None else kural(conn)
    from . import kurallar as kr
    guven = kr.oku(conn, "aski_gecerlilik")
    # BOSS'taki abone askısının aramaları bizde görünmez: güven kapalıysa rapordan gelen abone askısı saati durdurmaz.
    boss_abone_durdurur = bool(guven.get("boss_askisina_guven", True) or not guven.get("acik", True))
    acik = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT is_no, id, kaynak FROM is_aski WHERE bitis IS NULL")}
    acilan = kapanan = 0
    for is_no, boss_durum, neden in durumlar:
        askida = boss_askida_mi(boss_durum)
        mevcut = acik.get(is_no)
        if askida and mevcut is None:
            d = durdurur_mu(neden, k) and (boss_abone_durdurur or kr.aski_turu(neden) != "abone")
            conn.execute("INSERT INTO is_aski (is_no, baslama, bitis, neden, kaynak, durdurur) VALUES (?,?,NULL,?,'boss',?)",
                         (is_no, rapor_zamani, neden, 1 if d else 0))
            acilan += 1
        elif not askida and mevcut is not None and mevcut[1] == "boss":
            kapanan += conn.execute("UPDATE is_aski SET bitis=MAX(?, baslama) WHERE id=?", (rapor_zamani, mevcut[0])).rowcount
    return {"acilan": acilan, "kapanan": kapanan}


def kurali_yeniden_uygula(conn) -> int:
    """Ayar değişince kapanmamış işlerin aralıklarında ``durdurur`` yeniden hesaplanır (geçerlilik kuralı dahil)."""
    from . import kurallar as kr
    k = kural(conn)
    gk = kr.oku(conn, "aski_gecerlilik")
    boss_guven = bool(gk.get("boss_askisina_guven", True) or not gk.get("acik", True))
    satirlar = conn.execute("SELECT a.id, a.is_no, a.neden, a.durdurur, a.kaynak FROM is_aski a JOIN is_emri e "
                            "ON e.is_no = a.is_no WHERE e.durum <> 'kapandi'").fetchall()
    arama = aramalar(conn, sorted({r["is_no"] for r in satirlar if r["kaynak"] == "elle"}))
    n = 0
    for r in satirlar:
        yeni = durdurur_mu(r["neden"], k)
        if yeni and kr.aski_turu(r["neden"]) == "abone":
            yeni = kr.abone_aski_gecerli(arama.get(r["is_no"], []), gk)[0] if r["kaynak"] == "elle" else boss_guven
        yeni = 1 if yeni else 0
        if yeni != r["durdurur"]:
            n += conn.execute("UPDATE is_aski SET durdurur=? WHERE id=?", (yeni, r["id"])).rowcount
    return n


def aramalar(conn, is_nolar=None) -> dict[str, list[dict]]:
    """Arama kayıtları (olay 'arama'; eskiden yeniye): [{zaman, sonuc, sure_sn, webphone, sms, yeni_numara, kisi}].

    Sonradan "BOSS'a işlendi" ile gönderilen Talep Ulaşamama SMS'i (olay 'arama_sms') en yakın önceki SMS'siz
    ulaşılamadı aramasına işlenir.
    """
    sql = "SELECT is_no, tur, zaman, yeni, kullanici_ad FROM is_emri_olay WHERE tur IN ('arama','arama_sms')"
    param: list = []
    if is_nolar is not None:
        is_nolar = list(is_nolar)
        if not is_nolar:
            return {}
        if len(is_nolar) > 500:
            sql += " AND is_no IN (SELECT is_no FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi'))"
        else:
            sql += f" AND is_no IN ({','.join('?' * len(is_nolar))})"
            param = is_nolar
    out: dict[str, list[dict]] = {}
    for r in conn.execute(sql + " ORDER BY id", param):
        try:
            y = json.loads(r["yeni"] or "{}")
        except ValueError:
            y = {}
        liste = out.setdefault(r["is_no"], [])
        if r["tur"] == "arama_sms":
            for a in reversed(liste):
                if not a["sms"] and a["sonuc"] != "ulasildi":
                    a["sms"] = True
                    break
            continue
        liste.append({"zaman": r["zaman"], "sonuc": y.get("sonuc"), "sure_sn": y.get("sure_sn"),
                      "webphone": bool(y.get("webphone", True)), "sms": bool(y.get("sms")),
                      "yeni_numara": bool(y.get("yeni_numara")), "kisi": r["kullanici_ad"]})
    return out


# ----------------------------------------------------------------------------- okuma / hesap
def araliklar(conn, is_nolar=None) -> dict[str, list[dict]]:
    sql = "SELECT * FROM is_aski"
    param: list = []
    if is_nolar is not None:
        is_nolar = list(is_nolar)
        if not is_nolar:
            return {}
        if len(is_nolar) > 500:
            sql += " WHERE is_no IN (SELECT is_no FROM is_emri WHERE durum <> 'kapandi')"
        else:
            sql += f" WHERE is_no IN ({','.join('?' * len(is_nolar))})"
            param = is_nolar
    out: dict[str, list[dict]] = {}
    for r in conn.execute(sql + " ORDER BY baslama, id", param):
        out.setdefault(r["is_no"], []).append(dict(r))
    return out


def hesap(aralik_listesi: list[dict] | None, acilis: str, btk_hedef: str | None, simdi: dt.datetime,
          son24: str | None = None, son24_durur_ayar: bool = False) -> dict:
    """Net BTK saati. Aralıklar açılıştan önce başlasa bile yalnız açılıştan sonrası sayılır."""
    ac_t = zaman.oku(acilis)
    durdu = 0.0
    btk_durdu = False
    for a in aralik_listesi or ():
        if not a.get("durdurur"):
            continue
        bas = zaman.oku(a["baslama"])
        bit = zaman.oku(a["bitis"]) if a.get("bitis") else simdi
        if a.get("bitis") is None:
            btk_durdu = True
        if ac_t and bas and bas < ac_t:
            bas = ac_t
        if bas and bit and bit > bas:
            durdu += (bit - bas).total_seconds() / 60
    durdu_dk = int(round(durdu))
    sonuc = {"durdu_dk": durdu_dk, "btk_durdu": btk_durdu, "btk_hedef_net": None, "btk_net_gecen_dk": None,
             "btk_kalan_dk": None, "son24_net": son24}
    if btk_hedef:
        net = zaman.oku(btk_hedef) + dt.timedelta(minutes=durdu)
        sonuc["btk_hedef_net"] = zaman.metin(net)
        sonuc["btk_kalan_dk"] = int(round((net - simdi).total_seconds() / 60))
        if ac_t:
            sonuc["btk_net_gecen_dk"] = int(round((simdi - ac_t).total_seconds() / 60 - durdu))
    if son24 and son24_durur_ayar and durdu:
        sonuc["son24_net"] = zaman.metin(zaman.oku(son24) + dt.timedelta(minutes=durdu))
    return sonuc


def gorunum(a: dict, simdi: dt.datetime) -> dict:
    """Arayüze giden ``AskiAraligi``."""
    bas = zaman.oku(a["baslama"])
    bit = zaman.oku(a["bitis"]) if a.get("bitis") else simdi
    return {"id": a["id"], "baslama": a["baslama"], "bitis": a.get("bitis"), "neden": a.get("neden"),
            "kaynak": a["kaynak"], "durdurur": bool(a.get("durdurur")), "yaklasik": a["kaynak"] == "boss",
            "sure_dk": max(0, int(round((bit - bas).total_seconds() / 60))) if bas and bit else 0}
