"""Sıra, kapasite modu, öneri ve dilim — KARMA-2'nin yalın hâli (spec §3.6).

- Kapasite modu: günün talebi teknik kapasitesini aşıyorsa "aşırı yük"; esnek öneri = min(8, ⌈(talep − kapasite)/15⌉).
- Sıra (deterministik): öncelikli iş tipleri (EK-12.5, ``ayar.oncelikli_isler``: 40 Kanal Şikâyeti — süresi zaten
  kaçmış) en üstte; sonra Kontrol gerekli; normal modda BTK'lar BTK hedefine, diğerleri hedef saatine göre;
  aşırı yükte T/Gb/Gd/Y kümeleri arasında dönüşümlü seçim (gecikenleri gömmeden, yetişebileceği kurtarılarak).
- Öneri: işin öbeğinin ev teknisyeni (bugünkü yükü kapasitesinin altındaysa) → yedeği → yok. Binada açık ticket
  varsa (kural 11) ve ulaşılamayan işte (kural 8) öneri yazılmaz. Öneri alanları ``surum`` artırmaz.
- Dilim: teknisyenin sıradaki boş 2 saatlik dilimi; bugün dolunca ertesi günün ilk diliminden devam. 11:00 damgası yok.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sqlite3

from . import kisi, kurallar, zaman

ASIRI_YUK_BOLLUK_DK = 90
ESNEK_TAVAN = 8


def _ayar(conn, anahtar, varsayilan=None):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else varsayilan


def dilimler(conn: sqlite3.Connection) -> list[tuple[int, int]]:
    """ayar.dilimler "08-10,10-12,…" → [(8, 10), (10, 12), …] (saat)."""
    out = []
    for parca in str(_ayar(conn, "dilimler", "08-10,10-12,12-14,14-16,16-18,18-20")).split(","):
        try:
            a, b = (int(x.strip()[:2]) for x in parca.split("-"))
            if 0 <= a < b <= 24:
                out.append((a, b))
        except ValueError:
            continue
    return out or [(8, 10), (10, 12), (12, 14), (14, 16), (16, 18), (18, 20)]


def varsayilan_kapasite(conn) -> int:
    try:
        return max(1, int(_ayar(conn, "teknik_kapasite", "15")))
    except ValueError:
        return 15


def kisi_kapasitesi(conn, t: dict, varsayilan: int | None = None) -> int:
    try:
        return int(t.get("kapasite")) if t.get("kapasite") else (varsayilan or varsayilan_kapasite(conn))
    except (TypeError, ValueError):
        return varsayilan or varsayilan_kapasite(conn)


# ----------------------------------------------------------------------------- kapasite modu
def mod(conn: sqlite3.Connection, simdi: dt.datetime | None = None) -> dict:
    simdi = simdi or zaman.simdi()
    gun_sonu = zaman.metin(simdi.replace(hour=23, minute=59, second=59))
    talep = conn.execute(
        "SELECT COUNT(*) FROM is_emri WHERE serit IN ('SAHA','BTK') AND durum IN "
        "('triyaj','bekliyor','randevulu','atandi','yolda','sahada') AND (son24 <= ? OR atanan_id IS NULL)",
        (gun_sonu,)).fetchone()[0]
    teknikler = kisi.teknikler(conn)
    vars_ = varsayilan_kapasite(conn)
    elle = _ayar(conn, f"kapasite_{simdi:%Y-%m-%d}")
    bugun = simdi.strftime("%Y-%m-%d")
    isi_olan = {r[0] for r in conn.execute(
        "SELECT DISTINCT atanan_id FROM is_emri WHERE atanan_id IS NOT NULL AND (durum IN ('atandi','yolda','sahada') "
        "OR substr(COALESCE(cozum_zamani, ''), 1, 10) = ?)", (bugun,))}
    if elle is not None:
        try:
            aktif = max(0, int(elle))
        except ValueError:
            aktif = 0
        kapasite = aktif * vars_
    else:
        aktif_kisiler = [t for i, t in teknikler.items() if i in isi_olan]
        aktif = len(aktif_kisiler)
        kapasite = sum(kisi_kapasitesi(conn, t, vars_) for t in aktif_kisiler)
    m = "asiri_yuk" if talep > kapasite else "normal"
    esnek = min(ESNEK_TAVAN, math.ceil((talep - kapasite) / vars_)) if m == "asiri_yuk" else 0
    return {"mod": m, "talep": talep, "aktif": aktif, "kapasite": kapasite, "esnek_oneri": max(0, esnek),
            "elle": elle is not None, "teknik_sayisi": len(teknikler),
            "mesaj": None if teknikler else "Ekip'ten Teknik görevli kişi ekleyin."}


# ----------------------------------------------------------------------------- sıra
def _anahtar_zaman(x: dict, alan: str) -> str:
    return x.get(alan) or "9999"


def sirala(isler: list[dict], mod_: str, simdi: dt.datetime) -> list[str]:
    """Deterministik sıra (operasyon listesinin varsayılanı ve teknisyenin sırası).

    ``isler``: is_no, durum, serit, btk_hedef (net varsa ``btk_hedef_net``), son24, acilis, btk_hedef_saat;
    ``oncelik`` (EK-12.5 neden metni) doluysa iş en üste çıkar (kendi içinde açılış sırasıyla).
    """
    s_simdi = zaman.metin(simdi)
    oncelikli = sorted((x for x in isler if x.get("oncelik")), key=lambda x: (_anahtar_zaman(x, "acilis"), x["is_no"]))
    isler = [x for x in isler if not x.get("oncelik")]
    triyaj = sorted((x for x in isler if x["durum"] == "triyaj"), key=lambda x: (_anahtar_zaman(x, "son24"), x["is_no"]))
    diger = [x for x in isler if x["durum"] != "triyaj"]
    if mod_ != "asiri_yuk":
        btk = sorted((x for x in diger if x["serit"] == "BTK"),
                     key=lambda x: (x.get("btk_hedef_net") or x.get("btk_hedef") or x["son24"], x["is_no"]))
        obur = sorted((x for x in diger if x["serit"] != "BTK"), key=lambda x: (x["son24"], x["is_no"]))
        return [x["is_no"] for x in oncelikli + triyaj + btk + obur]

    def t_anahtar(x):
        s = x["son24"]
        if x.get("btk_hedef_saat") == 6:            # TV+: 24 saatinden 2 saat önce
            t = zaman.oku(s)
            s = zaman.metin(t - dt.timedelta(hours=2)) if t else s
        return (s, x["is_no"])

    T = sorted((x for x in diger if x["serit"] == "BTK" and x["son24"] > s_simdi), key=t_anahtar)
    Gb = sorted((x for x in diger if x["serit"] == "BTK" and x["son24"] <= s_simdi), key=lambda x: (x["acilis"], x["is_no"]))
    Gd = sorted((x for x in diger if x["serit"] != "BTK" and x["son24"] <= s_simdi), key=lambda x: (x["acilis"], x["is_no"]))
    Y = sorted((x for x in diger if x["serit"] != "BTK" and x["son24"] > s_simdi), key=lambda x: (x["son24"], x["is_no"]))
    esik = zaman.metin(simdi + dt.timedelta(minutes=ASIRI_YUK_BOLLUK_DK))
    out: list[dict] = []
    i = 0
    while T or Y or Gb or Gd:
        i += 1
        sikisan = [x for x in T + Y if x["son24"] < esik]
        if sikisan:
            sec = min(sikisan, key=lambda x: (x["son24"], x["is_no"]))
            (T if sec in T else Y).remove(sec)
        elif i % 3 == 0 and Gb:
            sec = Gb.pop(0)
        elif i % 4 == 0 and Gd:
            sec = Gd.pop(0)
        elif T:
            sec = T.pop(0)
        elif Y:
            sec = Y.pop(0)
        elif Gb:
            sec = Gb.pop(0)
        else:
            sec = Gd.pop(0)
        out.append(sec)
    return [x["is_no"] for x in oncelikli + triyaj + out]


# ----------------------------------------------------------------------------- dilim
def _gun_dilimleri(conn, gun: dt.date) -> list[tuple[dt.datetime, dt.datetime]]:
    return [(dt.datetime.combine(gun, dt.time(a)), dt.datetime.combine(gun, dt.time(b % 24)) if b < 24
             else dt.datetime.combine(gun + dt.timedelta(days=1), dt.time(0))) for a, b in dilimler(conn)]


def _dilim_doluluk(conn, teknik_id, haric=None) -> dict[str, int]:
    d: dict[str, int] = {}
    for (bas,) in conn.execute("SELECT randevu_bas FROM is_emri WHERE atanan_id=? AND durum IN ('atandi','yolda','sahada') "
                               "AND randevu_bas IS NOT NULL AND is_no IS NOT ?", (teknik_id, haric)):
        d[bas[:13]] = d.get(bas[:13], 0) + 1
    return d


def dilim_oner(conn: sqlite3.Connection, teknik_id: int, simdi: dt.datetime, haric: str | None = None,
               ek_doluluk: dict | None = None, kapasite: int | None = None) -> tuple[str, str]:
    """Teknisyenin sıradaki boş dilimi. Dilim kapasitesi = ⌈kapasite / dilim sayısı⌉.

    Seçilen dilim randevu kurallarına uyar: başlangıç ≥ şimdi − 1 s ve bitişe en az 60 dk var.
    """
    if kapasite is None:
        t = kisi.kisiler(conn, [teknik_id]).get(teknik_id) or {}
        kapasite = kisi_kapasitesi(conn, t)
    sayi = max(1, len(dilimler(conn)))
    tavan = max(1, math.ceil(kapasite / sayi))
    dolu = _dilim_doluluk(conn, teknik_id, haric)
    for k_, v in (ek_doluluk or {}).items():
        dolu[k_] = dolu.get(k_, 0) + v
    for g in range(0, 8):
        gun = (simdi + dt.timedelta(days=g)).date()
        for bas, bit in _gun_dilimleri(conn, gun):
            if bas < simdi - dt.timedelta(hours=1) or bit < simdi + dt.timedelta(minutes=60):
                continue
            if bas > simdi + dt.timedelta(days=7):
                continue
            if dolu.get(zaman.metin(bas)[:13], 0) < tavan:
                return zaman.metin(bas), zaman.metin(bit)
    son = _gun_dilimleri(conn, (simdi + dt.timedelta(days=1)).date())[0]
    return zaman.metin(son[0]), zaman.metin(son[1])


# ----------------------------------------------------------------------------- öneri
def _bugunku_yuk(conn, simdi: dt.datetime) -> dict[int, int]:
    bugun = simdi.strftime("%Y-%m-%d")
    y: dict[int, int] = {}
    for (tid,) in conn.execute("SELECT atanan_id FROM is_emri WHERE atanan_id IS NOT NULL AND durum IN "
                               "('atandi','yolda','sahada') AND (randevu_bas IS NULL OR substr(randevu_bas,1,10) <= ?)",
                               (bugun,)):
        y[tid] = y.get(tid, 0) + 1
    return y


def _son_teknik(conn, is_no) -> int | None:
    """Yeniden açılan işte önceki teknisyen (öneride öne alınır, §3.4-6)."""
    r = conn.execute("SELECT yeni FROM is_emri_olay WHERE is_no=? AND tur='atama' ORDER BY id DESC LIMIT 1",
                     (is_no,)).fetchone()
    try:
        return json.loads(r[0]).get("atanan_id") if r and r[0] else None
    except ValueError:
        return None


def oneri_hesapla(conn: sqlite3.Connection, is_nolar=None, simdi: dt.datetime | None = None) -> int:
    """Atanmamış işlere teknisyen + dilim önerisi yazar; uygun olmayanların önerisi silinir. Dönüş: öneri yazılan iş.

    Tek işlem; işlemin içinden de çağrılabilir (SAVEPOINT). ``surum`` ARTMAZ (öneri iz değildir).
    """
    from .islem import islem
    simdi = simdi or zaman.simdi()
    teknikler = kisi.teknikler(conn)
    vars_ = varsayilan_kapasite(conn)
    yuk = _bugunku_yuk(conn, simdi)
    obekler = {r[0]: dict(r) for r in conn.execute("SELECT id, ad, sahip_id, yedek_id FROM obek WHERE aktif=1")}
    acik_ticketli = {r[0] for r in conn.execute(
        "SELECT DISTINCT bina_serial FROM ticket WHERE bina_serial IS NOT NULL AND durum IN ('AÇIK','HATA','TRANSFER')")} \
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='ticket'").fetchone() else set()
    sql = ("SELECT is_no, durum, serit, btk_hedef, son24, acilis, btk_hedef_saat, obek_id, obek_elle_id, bina_serial, "
           "acilma_sayisi, oneri_teknik_id, oneri_bas, oneri_bit, oneri_neden, task_adi, parca, parca_tarih FROM is_emri "
           "WHERE atanan_id IS NULL AND durum NOT IN ('cozuldu','kapandi')")
    satirlar = [dict(r) for r in conn.execute(sql)]
    oncelik_kural = kurallar.oku(conn, "oncelikli_isler")
    for x in satirlar:
        x["oncelik"] = kurallar.oncelik(oncelik_kural, x["task_adi"])
    bugun = simdi.strftime("%Y-%m-%d")
    if is_nolar is not None:
        hedef = set(is_nolar)
        # dilim sırası bütün atanmamış işlere göre hesaplanır, yazılan yalnız istenenler
    else:
        hedef = None
    m = mod(conn, simdi)["mod"]
    sira = {no: i for i, no in enumerate(sirala(satirlar, m, simdi))}
    satirlar.sort(key=lambda x: sira.get(x["is_no"], 10 ** 6))
    ek_doluluk: dict[int, dict[str, int]] = {}
    yazilacak = []
    for x in satirlar:
        oneri = None
        uygun = x["durum"] in ("bekliyor", "randevulu") and x["bina_serial"] not in acik_ticketli
        oid = x["obek_elle_id"] or x["obek_id"]
        o = obekler.get(oid) if oid else None
        if uygun and x["parca_tarih"] == bugun and x["oneri_teknik_id"] in teknikler                 and str(x["oneri_neden"] or "").startswith("Ekiplere dağıtıldı"):
            # "Ekiplere dağıt"ın bugünkü önerisi korunur (atama "Önerileri onayla" ile; §5.3.2 dagit/uygula)
            d = ek_doluluk.setdefault(x["oneri_teknik_id"], {})
            if x["oneri_bas"]:
                d[x["oneri_bas"][:13]] = d.get(x["oneri_bas"][:13], 0) + 1
            continue
        if uygun:
            adaylar = []
            if (x["acilma_sayisi"] or 1) > 1:
                onceki = _son_teknik(conn, x["is_no"])
                if onceki:
                    adaylar.append((onceki, "önceki teknisyeni"))
            if o:
                adaylar += [(o["sahip_id"], f"{o['ad']} öbeğinin teknisyeni"), (o["yedek_id"], f"{o['ad']} öbeğinin yedek teknisyeni")]
            for tid, neden in adaylar:
                t = teknikler.get(tid) if tid else None
                if not t:
                    continue
                kap = kisi_kapasitesi(conn, t, vars_)
                if yuk.get(tid, 0) >= kap:
                    continue
                d = ek_doluluk.setdefault(tid, {})
                if x["durum"] == "randevulu":
                    bas = bit = None
                    r = conn.execute("SELECT randevu_bas, randevu_bit FROM is_emri WHERE is_no=?", (x["is_no"],)).fetchone()
                    bas, bit = r[0], r[1]
                else:
                    bas, bit = dilim_oner(conn, tid, simdi, haric=x["is_no"], ek_doluluk=d, kapasite=kap)
                if bas:
                    d[bas[:13]] = d.get(bas[:13], 0) + 1
                oneri = (tid, bas, bit, f"{neden} · bugün {yuk.get(tid, 0)}/{kap}")
                break
        yeni = oneri or (None, None, None, None)
        eski = (x["oneri_teknik_id"], x["oneri_bas"], x["oneri_bit"], x["oneri_neden"])
        if (hedef is None or x["is_no"] in hedef) and yeni != eski:
            yazilacak.append((*yeni, x["is_no"]))
    if yazilacak:
        with islem(conn):
            conn.executemany("UPDATE is_emri SET oneri_teknik_id=?, oneri_bas=?, oneri_bit=?, oneri_neden=? WHERE is_no=?",
                             yazilacak)
    return sum(1 for y in yazilacak if y[0] is not None)


def teknik_sirasi(isler: list[dict]) -> list[dict]:
    """İşlerim sırası: teknisyenin elle sırası önce, sonra randevu, sonra BTK hedefi / 24 saat."""
    return sorted(isler, key=lambda x: (x.get("sira") if x.get("sira") is not None else 10 ** 6,
                                        x.get("randevu_bas") or "9999",
                                        x.get("btk_hedef") or x.get("son24") or "9999", x["is_no"]))
