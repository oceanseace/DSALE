"""Bölge planlayıcı — "8 ekipten 14 ekibe çıkınca bölgeler dinamik bölünsün".

Excel bunu yapamıyordu: bölge sayısı değişince binaları yeniden dağıtmak, satışçıları
yeni bölgelere oturtmak ve kimin elinden kaç binanın çıktığını görmek elle günler
sürer. Burada dört adım:

    durum      bugünkü N, bölge başına canlı sayılar (bina, RES HP, fırsat, dokunulan %)
               ve bölgenin satışçısı
    önizle(N)  hazır plan (sunum paketi ``planlar.json`` ya da ``cikti/_onbellek``)
               yoksa arka planda ``dsale.partition.bolgele`` ile hesap; yeni bölgelerin
               sayıları, sınırları ve FARK: kaç bina / ziyaret el değiştirir
    uygula     tek işlem: plan geçmişine yazılır, ``bina.bolge`` güncellenir, satışçılar
               eşleşen bölgeye taşınır, satışçısı olmayan yeni bölgeye yer tutucu hesap
               ve davet kodu açılır, harita önbellekleri tazelenir
    geri al    bir önceki plana döner (satışçı bölgeleri dahil); hiçbir hesap silinmez

ZİYARET GEÇMİŞİNE HİÇ DOKUNULMAZ. Bölge yalnız binanın "şu an kimin işi" olduğunu söyler.

Numaralandırma kuralı: yeni plandaki her bölge, binalarının (ziyaret edilmiş olanlar
daha ağır) en çoğunu devraldığı eski bölgeyle eşleştirilir (Macar yöntemi). Eşleşen
bölge eski numarasını ve satışçısını korur: 8 → 14'te 1-8 yerinde kalır, 9-14 yeni
açılır. 14 → 8'de numaralar 1-8'e sıkışır, satışçılar binalarının çoğunun gittiği
bölgeye taşınır; bölgesi kalmayan satışçı "bölgesiz" (0) olur, yönetici onaylarsa pasife alınır.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import secrets
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import yollar

from . import ayarlar, db, guvenlik

_gunluk = logging.getLogger("saha.bolgeleme")

HAZIR_PLANLAR = yollar.SUNUM_URETILEN / "planlar.json"
HAZIR_BINALAR = yollar.SUNUM_URETILEN / "binalar.json"
DSALE_ONBELLEK = yollar.CIKTI / "_onbellek"          # bolge.py'nin önbelleği (yalnız okunur)
MASTER_CSV = yollar.VERI / "master" / "bina_master.csv"


def _saha_onbellek() -> Path:
    """Sunucunun hesapladığı planlar: <çalışma>/cikti/_onbellek/saha/<veri imzası>/plan_NXX_<ölçü>.json"""
    return ayarlar.cikti_dizini() / "_onbellek" / "saha"


def _excel_dizini() -> Path:
    return ayarlar.cikti_dizini() / "saha_bolgeleme"


OLCULER =("res_hp", "firsat", "toplam_hp", "bina")
EN_AZ_N, EN_COK_N = 2, 60
# Hazır plan, veritabanındaki binaların bu kadarını birebir tanımıyorsa (çok yeni bina
# eklendiyse) eskimiş sayılır ve güncel veriyle yeniden hesaplanır.
HAZIR_KAPSAMA_ESIGI = 0.97
# Hazır planın güncel HP ile dengesi bu kadar bozulduysa önizlemede uyarı çıkar.
DENGE_UYARI = 0.03


class PlanHatasi(Exception):
    """Kullanıcıya gösterilecek Türkçe mesaj + kod (API bunu HTTP hatasına çevirir)."""

    def __init__(self, durum: int, mesaj: str, kod: str):
        super().__init__(mesaj)
        self.durum, self.mesaj, self.kod = durum, mesaj, kod


@dataclass
class Plan:
    kaynak: str                      # 'hazir' | 'onbellek' | 'hesap'
    n: int
    olcu: str
    atama: dict[str, int]            # veritabanındaki HER bina → planın kendi bölge numarası
    bolgeler: dict[int, dict]        # planın kendi numarasıyla: ad, kisa_ad, poligon, merkez, etiket
    parametreler: dict = field(default_factory=dict)
    dogrudan: int = 0                # plandan birebir gelen bina (kalanı en yakın komşuyla)
    imza: str = ""

    @property
    def ref(self) -> str:
        return f"{self.kaynak}:{self.n}:{self.olcu}:{self.imza}"


# ============================================================================= veri
_BINA_SQL = (
    "SELECT b.bina_serial, b.lat, b.lon, b.site_grup, b.bolge, b.pasif, b.res_hp, b.aktif_res, "
    "       b.firsat, b.toplam_hp, b.il, b.ilce, b.mahalle, "
    "       d.son_ziyaret, d.toplam_satis, d.ziyaret_sayisi "
    "FROM bina b LEFT JOIN bina_durum d USING(bina_serial) ORDER BY b.bina_serial"
)


def _binalar(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(_BINA_SQL).fetchall()]


def _olcu_degeri(b: dict, olcu: str) -> float:
    return 1.0 if olcu == "bina" else float(b.get(olcu) or 0)


_master_ek: dict = {}


def _master_ekleri():
    """Veritabanında olmayan sütunlar (Excel ve bölge adları için): master CSV'den."""
    import pandas as pd

    if not MASTER_CSV.exists():
        return None
    imza = (MASTER_CSV.stat().st_size, int(MASTER_CSV.stat().st_mtime))
    if _master_ek.get("imza") != imza:
        sutunlar = ["bina_serial", "aktif_toplam", "kurulum_son_ay", "churn_son_ay", "tv"]
        _master_ek["df"] = pd.read_csv(MASTER_CSV, encoding="utf-8-sig", usecols=sutunlar)
        _master_ek["imza"] = imza
    return _master_ek["df"]


def veri_cercevesi(conn: sqlite3.Connection, sadece_aktif: bool = True):
    """Bölgeleme ve Excel için veritabanından (güncel HP/abone ile) DataFrame."""
    import numpy as np
    import pandas as pd

    kosul = " WHERE b.pasif=0" if sadece_aktif else ""
    df = pd.read_sql_query(
        "SELECT b.bina_serial, b.tellcordia_id, b.location_id, b.ad, b.site_adi, b.blok_adi, b.kapi_no, "
        "       b.mahalle, b.cadde, b.sokak, b.ilce, b.il, b.obek, b.site_grup, b.lat, b.lon, b.kat, "
        "       b.toplam_hp, b.soho_hp, b.res_hp, b.aktif_res, b.firsat, b.bolge "
        f"FROM bina b{kosul} ORDER BY b.bina_serial", conn)
    for c in ("toplam_hp", "soho_hp", "res_hp", "aktif_res", "firsat", "kat"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["site_grup"] = df["site_grup"].fillna("").astype(str)
    bos = df["site_grup"] == ""
    df.loc[bos, "site_grup"] = "B:" + df.loc[bos, "bina_serial"]
    ek = _master_ekleri()
    if ek is not None:
        df = df.merge(ek, on="bina_serial", how="left")
    for c in ("aktif_toplam", "kurulum_son_ay", "churn_son_ay", "tv"):
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["bina"] = 1
    df["penetrasyon"] = np.where(df["res_hp"] > 0, df["aktif_res"] / df["res_hp"].where(df["res_hp"] > 0, 1),
                                 np.nan)
    return df


def _veri_imzasi(binalar: list[dict], olcu: str) -> str:
    """Bölgeleme girdisinin özeti: aynı veri + aynı ölçü → aynı plan dosyası."""
    from dsale.partition import ALGORITMA_SURUMU

    h = hashlib.sha1(f"{ALGORITMA_SURUMU}|{olcu}".encode())
    for b in binalar:
        if b.get("pasif"):
            continue
        h.update(f"{b['bina_serial']}|{b.get('site_grup') or ''}|{float(b['lat']):.6f}|"
                 f"{float(b['lon']):.6f}|{_olcu_degeri(b, olcu):.0f};".encode())
    return h.hexdigest()[:12]


def _imza(atama: dict[str, int]) -> str:
    h = hashlib.sha1()
    for s in sorted(atama):
        h.update(f"{s}:{atama[s]};".encode())
    return h.hexdigest()[:12]


def _en_yakina_tamamla(binalar: list[dict], atama: dict[str, int]) -> None:
    """Planda karşılığı olmayan binaları (sonradan eklenen) en yakın atanmış binanın bölgesine verir."""
    eksik = [b for b in binalar if b["bina_serial"] not in atama]
    if not eksik:
        return
    import numpy as np
    from scipy.spatial import cKDTree

    atanmis = [b for b in binalar if b["bina_serial"] in atama]
    if not atanmis:
        return
    lat0 = math.radians(sum(float(b["lat"]) for b in atanmis) / len(atanmis))
    xy = np.array([[float(b["lon"]) * math.cos(lat0), float(b["lat"])] for b in atanmis])
    agac = cKDTree(xy)
    sorgu = np.array([[float(b["lon"]) * math.cos(lat0), float(b["lat"])] for b in eksik])
    _, idx = agac.query(sorgu, k=1)
    for b, i in zip(eksik, np.atleast_1d(idx)):
        atama[b["bina_serial"]] = atama[atanmis[int(i)]["bina_serial"]]


def _plan_kur(kaynak: str, n: int, olcu: str, binalar: list[dict], seri_bolge: dict[str, int] | None,
              birim_bolge: dict[str, int] | None, bolge_listesi: list[dict], parametreler: dict) -> Plan:
    atama: dict[str, int] = {}
    for b in binalar:
        k = None
        if seri_bolge:
            k = seri_bolge.get(b["bina_serial"])
        if not k and birim_bolge:
            k = birim_bolge.get(b.get("site_grup") or "")
        if k and 1 <= int(k) <= n:
            atama[b["bina_serial"]] = int(k)
    dogrudan = len(atama)
    _en_yakina_tamamla(binalar, atama)
    bolgeler = {}
    for r in bolge_listesi or []:
        if r.get("bos") or not r.get("bolge"):
            continue
        bolgeler[int(r["bolge"])] = {a: r.get(a) for a in (
            "ad", "kisa_ad", "renk", "poligon", "merkez", "etiket", "alan_km2", "sapma")}
    plan = Plan(kaynak=kaynak, n=n, olcu=olcu, atama=atama, bolgeler=bolgeler,
                parametreler=parametreler or {}, dogrudan=dogrudan)
    plan.imza = _imza(atama)
    return plan


# ============================================================================= plan kaynakları
_hazir: dict = {}


def _hazir_oku():
    """Sunum paketindeki planlar.json + birim sözlüğü (binalar.json). Dosya değişmedikçe bellekte."""
    if not (HAZIR_PLANLAR.exists() and HAZIR_BINALAR.exists()):
        return None
    imza = tuple(int(p.stat().st_mtime) for p in (HAZIR_PLANLAR, HAZIR_BINALAR))
    if _hazir.get("imza") != imza:
        planlar = json.load(open(HAZIR_PLANLAR, encoding="utf-8"))
        birim = json.load(open(HAZIR_BINALAR, encoding="utf-8"))["sozluk"]["birim"]
        _hazir.update(imza=imza, planlar=planlar, birim=birim)
    return _hazir


def hazir_nler() -> list[int]:
    try:
        h = _hazir_oku()
    except (OSError, ValueError, KeyError):
        return []
    if not h:
        return []
    return sorted(int(k) for k in h["planlar"].get("planlar", {}))


def _plan_hazir(binalar: list[dict], n: int, olcu: str) -> Plan | None:
    try:
        h = _hazir_oku()
    except (OSError, ValueError, KeyError) as exc:
        _gunluk.warning("Hazır planlar okunamadı: %s", exc)
        return None
    if not h or h["planlar"].get("olcu") != olcu:
        return None
    p = h["planlar"].get("planlar", {}).get(str(n))
    if not p or len(p.get("birim_bolge", [])) != len(h["birim"]):
        return None
    birim_bolge = dict(zip(h["birim"], p["birim_bolge"]))
    plan = _plan_kur("hazir", n, olcu, binalar, None, birim_bolge, p.get("bolgeler", []),
                     {**(p.get("parametreler") or {}), "kaynak_dosya": HAZIR_PLANLAR.relative_to(yollar.KOK).as_posix()})
    aktif = sum(1 for b in binalar if not b.get("pasif"))
    if aktif and plan.dogrudan / max(len(binalar), 1) < HAZIR_KAPSAMA_ESIGI:
        return None                    # veri çok değişmiş: güncel veriyle hesaplanmalı
    return plan


def _plan_dsale_onbellek(binalar: list[dict], n: int, olcu: str) -> Plan | None:
    """``python bolge.py`` çalıştırmasının önbelleği (cikti/_onbellek/<anahtar>/plan_NXX.json).

    Anahtar master CSV'nin boyut/zamanını içerir; yalnız bugünkü master ile üretilmiş
    plan kullanılır ve birim sözlüğü bugünkü masterdan kurulur (birebir aynı dosya).
    """
    try:
        import bolge as bolge_komutu          # repo kökündeki bolge.py

        anahtar = bolge_komutu._onbellek_anahtari(olcu, [])
    except Exception:
        return None
    yol = DSALE_ONBELLEK / anahtar / f"plan_N{n:02d}.json"
    if not yol.exists():
        return None
    try:
        import pandas as pd

        p = json.load(open(yol, encoding="utf-8"))
        birim = sorted(pd.read_csv(MASTER_CSV, encoding="utf-8-sig", usecols=["site_grup"])["site_grup"]
                       .fillna("").astype(str).unique().tolist())
    except (OSError, ValueError, KeyError):
        return None
    if len(p.get("birim_bolge", [])) != len(birim):
        return None
    return _plan_kur("onbellek", n, olcu, binalar, None, dict(zip(birim, p["birim_bolge"])),
                     p.get("bolgeler", []), {**(p.get("parametreler") or {}),
                                              "kaynak_dosya": yol.relative_to(yollar.KOK).as_posix()})


def _hesap_yolu(imza: str, n: int, olcu: str) -> Path:
    return _saha_onbellek() / imza / f"plan_N{n:02d}_{olcu}.json"


def _plan_hesap(binalar: list[dict], n: int, olcu: str) -> Plan | None:
    yol = _hesap_yolu(_veri_imzasi(binalar, olcu), n, olcu)
    if not yol.exists():
        return None
    try:
        p = json.load(open(yol, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _plan_kur("hesap", n, olcu, binalar, {k: int(v) for k, v in p["atama"].items()}, None,
                     p.get("bolgeler", []), {**(p.get("parametreler") or {}),
                                              "kaynak_dosya": yol.name})


def plan_bul(binalar: list[dict], n: int, olcu: str, kaynak: str | None = None) -> Plan | None:
    """Sıra: bu veriyle sunucuda hesaplanmış plan → sunum paketi → bolge.py önbelleği."""
    kaynaklar = {"hesap": _plan_hesap, "hazir": _plan_hazir, "onbellek": _plan_dsale_onbellek}
    sira = [kaynak] if kaynak else ["hesap", "hazir", "onbellek"]
    for k in sira:
        f = kaynaklar.get(k)
        plan = f(binalar, n, olcu) if f else None
        if plan:
            return plan
    return None


# ============================================================================= arka plan hesabı
_isler: dict[str, dict] = {}
_is_kilidi = threading.Lock()


def _beklenen_sure(n: int) -> float:
    """Kaba süre tahmini (sn): bu bilgisayarda N=8 ~7 sn, N=14 ~20 sn, N=30 ~60 sn."""
    return 4.0 + 1.9 * n


def is_durumu(is_id: str) -> dict | None:
    j = _isler.get(is_id)
    return dict(j) if j else None


def calisan_is() -> dict | None:
    for j in _isler.values():
        if j["durum"] in ("bekliyor", "calisiyor"):
            return dict(j)
    return None


def hesap_baslat(n: int, olcu: str, db_yolu: Path | None = None) -> dict:
    """Arka planda plan hesabı başlatır. Aynı N zaten hesaplanıyorsa o işi döndürür."""
    with _is_kilidi:
        for j in _isler.values():
            if j["durum"] in ("bekliyor", "calisiyor"):
                if (j["n"], j["olcu"]) == (n, olcu):
                    return dict(j)
                raise PlanHatasi(409, f"Şu an {j['n']} bölgelik plan hesaplanıyor. Bitince tekrar deneyin.",
                                 "hesap_suruyor")
        is_id = secrets.token_hex(6)
        j = {"is_id": is_id, "n": n, "olcu": olcu, "durum": "bekliyor", "ilerleme": 0.0,
             "asama": "Sırada", "mesaj": None, "plan_ref": None, "baslangic": ayarlar.zaman_metni(),
             "bitis": None, "tahmini_sn": round(_beklenen_sure(n))}
        _isler[is_id] = j
        # Geçmiş sınırlı: en eski bitmiş işler atılır.
        bitmis = [k for k, v in _isler.items() if v["durum"] in ("bitti", "hata")]
        for k in bitmis[:-20]:
            _isler.pop(k, None)
    th = threading.Thread(target=_hesapla, args=(is_id, n, olcu, db_yolu or db.db_yolu()),
                          name=f"bolgeleme-{n}", daemon=True)
    th.start()
    return dict(j)


def _hesapla(is_id: str, n: int, olcu: str, yol: Path) -> None:
    j = _isler[is_id]
    j.update(durum="calisiyor", asama="Veri hazırlanıyor", ilerleme=0.05)
    bitti = threading.Event()
    try:
        from dsale import metrics, partition

        conn = db.baglan(yol)
        try:
            binalar = _binalar(conn)
            df = veri_cercevesi(conn, sadece_aktif=True)
        finally:
            conn.close()
        imza = _veri_imzasi(binalar, olcu)

        t0 = time.time()
        beklenen = _beklenen_sure(n)

        def saat():
            # bolgele() ilerleme bildirmiyor: süre tahmininden TAHMİNİ yüzde (en çok %80).
            while not bitti.wait(0.5):
                if j["asama"] == "Bölgeler hesaplanıyor":
                    j["ilerleme"] = round(0.10 + 0.70 * min((time.time() - t0) / beklenen, 0.97), 3)

        threading.Thread(target=saat, daemon=True).start()
        j.update(asama="Bölgeler hesaplanıyor", ilerleme=0.10)
        s = partition.bolgele(df, n, olcu=olcu)
        j.update(asama="Bölge sınırları ve adları", ilerleme=0.82)
        bolgeler = metrics.bolge_ozetleri(df, s.atama, olcu, s.hedef)
        j.update(asama="Kaydediliyor", ilerleme=0.95)
        kayit = {
            "n": n, "olcu": olcu, "hedef": round(float(s.hedef), 2), "veri_imzasi": imza,
            "uretim": ayarlar.zaman_metni(), "sure_sn": s.sure_sn,
            "parametreler": s.parametreler,
            "atama": {str(k): int(v) for k, v in s.atama.items()},
            "bolgeler": [{a: b.get(a) for a in ("bolge", "ad", "kisa_ad", "renk", "poligon", "merkez",
                                                 "etiket", "alan_km2", "sapma", "bos")} for b in bolgeler],
        }
        hedef = _hesap_yolu(imza, n, olcu)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        gecici = hedef.with_suffix(".tmp")
        json.dump(kayit, open(gecici, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        gecici.replace(hedef)
        j.update(durum="bitti", asama="Hazır", ilerleme=1.0, bitis=ayarlar.zaman_metni(),
                 sure_sn=round(time.time() - t0, 1),
                 mesaj=f"{n} bölgelik plan {round(time.time() - t0)} saniyede hesaplandı.")
    except Exception as exc:  # işçi iş parçacığı çökerse sunucu çökmemeli; sebep kayda geçer
        _gunluk.exception("Bölgeleme hesabı başarısız: %s", exc)
        j.update(durum="hata", asama="Hata", bitis=ayarlar.zaman_metni(),
                 mesaj=f"Plan hesaplanamadı: {exc}. Tekrar deneyin; sürerse BT'ye günlük dosyasını gönderin.")
    finally:
        bitti.set()


# ============================================================================= eşleştirme ve önizleme
def _eslestir(binalar: list[dict], plan: Plan) -> tuple[dict[int, int], dict[int, int], list[int]]:
    """Planın bölgelerini bugünkü bölgelerle eşleştirir.

    Dönüş: (plan_no → son numara, eski bölge → son numara, eşi olmayan eski bölgeler).
    Ağırlık = 1 + ziyaret sayısı: ziyaret edilmiş bina, geçmişini bilen satışçıda kalsın.
    """
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    n = plan.n
    ortak: dict[tuple[int, int], float] = defaultdict(float)
    for b in binalar:
        eski = int(b.get("bolge") or 0)
        if eski <= 0 or b.get("pasif"):
            continue
        ortak[(eski, plan.atama[b["bina_serial"]])] += 1.0 + float(b.get("ziyaret_sayisi") or 0)
    eskiler = sorted({e for e, _ in ortak})
    ciftler: list[tuple[int, int]] = []
    if eskiler:
        M = np.zeros((len(eskiler), n))
        for (e, y), w in ortak.items():
            M[eskiler.index(e), y - 1] = w
        satir, sutun = linear_sum_assignment(M, maximize=True)
        ciftler = [(eskiler[r], int(c) + 1) for r, c in zip(satir, sutun) if M[r, c] > 0]
    numara: dict[int, int] = {}
    kullanilan: set[int] = set()
    for eski, yeni in ciftler:
        if 1 <= eski <= n:
            numara[yeni] = eski
            kullanilan.add(eski)
    bos = [k for k in range(1, n + 1) if k not in kullanilan]
    for yeni in range(1, n + 1):
        if yeni not in numara:
            numara[yeni] = bos.pop(0)
    tasima = {eski: numara[yeni] for eski, yeni in ciftler}
    kalkan = [e for e in eskiler if e not in tasima]
    return numara, tasima, kalkan


def _satiscilar(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, ad, telefon, bolge, aktif, (pin_hash IS NOT NULL) AS pin_var, davet_kodu "
        "FROM kullanici WHERE rol='satisci' ORDER BY bolge, id").fetchall()]


def _renkler(n: int) -> list[str]:
    try:
        from dsale.metrics import renkler

        return renkler(n)
    except Exception:
        return ["#1FC7FF"] * n


def _bolge_sayilari(binalar: list[dict], atama: dict[str, int], n: int, olcu: str) -> dict[int, dict]:
    """Bölge başına canlı sayılar (pasif binalar hariç)."""
    s: dict[int, dict] = {k: {"bina": 0, "res_hp": 0, "aktif_res": 0, "firsat": 0, "kalan_firsat": 0,
                              "toplam_hp": 0, "dokunulan": 0, "satis": 0, "ziyaret": 0, "_olcu": 0.0}
                          for k in range(1, n + 1)}
    for b in binalar:
        if b.get("pasif"):
            continue
        k = atama.get(b["bina_serial"])
        if k not in s:
            continue
        r = s[k]
        r["bina"] += 1
        r["res_hp"] += int(b.get("res_hp") or 0)
        r["aktif_res"] += int(b.get("aktif_res") or 0)
        r["toplam_hp"] += int(b.get("toplam_hp") or 0)
        firsat = int(b.get("firsat") or 0)
        satis = int(b.get("toplam_satis") or 0)
        r["firsat"] += firsat
        r["kalan_firsat"] += max(firsat - satis, 0)
        r["satis"] += satis
        r["ziyaret"] += int(b.get("ziyaret_sayisi") or 0)
        r["dokunulan"] += 1 if b.get("son_ziyaret") else 0
        r["_olcu"] += _olcu_degeri(b, olcu)
    ort = sum(r["_olcu"] for r in s.values()) / max(n, 1)
    for r in s.values():
        r["dokunulan_oran"] = round(r["dokunulan"] / r["bina"], 4) if r["bina"] else 0.0
        r["penetrasyon"] = round(min(r["aktif_res"] / r["res_hp"], 1.0), 4) if r["res_hp"] else None
        r["sapma"] = round(r["_olcu"] / ort - 1, 4) if ort else 0.0
        r.pop("_olcu")
    return s


def _kart(s: dict) -> dict:
    return {"id": s["id"], "ad": s["ad"], "telefon_goster": guvenlik.telefon_goster(s["telefon"]),
            "aktif": bool(s["aktif"]), "pin_var": bool(s["pin_var"])}


def onizle(conn: sqlite3.Connection, plan: Plan, binalar: list[dict] | None = None) -> dict:
    """Planın bugünkü duruma göre etkisi. Veritabanına hiçbir şey yazmaz."""
    binalar = binalar if binalar is not None else _binalar(conn)
    n = plan.n
    numara, tasima, kalkan = _eslestir(binalar, plan)
    son = {s: numara[k] for s, k in plan.atama.items()}
    satiscilar = _satiscilar(conn)
    mevcut_n = db.bolge_sayisi(conn)

    # --- satışçılar: eşleşen bölgeyle taşınır; bölgesi kalmayan bölgesiz olur
    hareket, bolgesiz = [], []
    sahip: dict[int, list[dict]] = defaultdict(list)
    for s in satiscilar:
        eski = int(s["bolge"] or 0)
        if eski in tasima:
            yeni = tasima[eski]
            if yeni != eski:
                hareket.append({**_kart(s), "eski_bolge": eski, "yeni_bolge": yeni})
            if s["aktif"]:
                sahip[yeni].append(s)
        elif s["aktif"] and eski != 0:
            bolgesiz.append({**_kart(s), "eski_bolge": eski})
    yeni_satisci_gereken = [k for k in range(1, n + 1) if not sahip.get(k)]

    # --- fark: sahibi değişen bina = yeni bölgesi, eski bölgesinin satışçısının gideceği yer değil
    el_bina = el_ziyaret = el_dokunulmus = numara_degisen = 0
    gelen: dict[int, Counter] = defaultdict(Counter)
    for b in binalar:
        s_ = b["bina_serial"]
        eski = int(b.get("bolge") or 0)
        yeni = son[s_]
        if eski != yeni:
            numara_degisen += 1
        if b.get("pasif"):
            continue
        gelen[yeni][eski] += 1
        if tasima.get(eski) != yeni:
            el_bina += 1
            el_ziyaret += int(b.get("ziyaret_sayisi") or 0)
            el_dokunulmus += 1 if b.get("son_ziyaret") else 0
    aktif_bina = sum(1 for b in binalar if not b.get("pasif"))

    # Bugünkü açık listelerde bekleyen ve sahibi değişen binalar
    bugun = ayarlar.bugun().isoformat()
    listede = [r["bina_serial"] for r in conn.execute(
        "SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
        "WHERE g.tarih=? AND g.durum='acik' AND gb.durum='bekliyor'", (bugun,)).fetchall()]
    eski_bolge = {b["bina_serial"]: int(b.get("bolge") or 0) for b in binalar}
    listede_el = sum(1 for x in listede if x in son and tasima.get(eski_bolge.get(x, 0)) != son[x])

    sayilar = _bolge_sayilari(binalar, son, n, plan.olcu)
    renk = _renkler(n)
    ters = {v: k for k, v in numara.items()}        # son numara → planın numarası
    bolgeler = []
    for k in range(1, n + 1):
        pb = plan.bolgeler.get(ters[k], {})
        kaynak = [{"bolge": e or None, "bina": c} for e, c in gelen[k].most_common(4)]
        bolgeler.append({
            "bolge": k, "ad": pb.get("ad") or f"Bölge {k}", "kisa_ad": pb.get("kisa_ad") or f"B{k}",
            "renk": renk[k - 1], **sayilar[k],
            "poligon": pb.get("poligon"), "merkez": pb.get("merkez"), "etiket": pb.get("etiket"),
            "satiscilar": [_kart(s) for s in sahip.get(k, [])],
            "yeni_satisci_acilacak": k in yeni_satisci_gereken,
            "nereden": kaynak,
        })
    sapmalar = [b["sapma"] for b in bolgeler if b["bina"]]
    uyarilar = []
    if el_bina == 0 and numara_degisen == 0:
        uyarilar.append("Bu plan bugünkü bölgelerle aynı; uygulamak bir şey değiştirmez.")
    if sapmalar and max(abs(x) for x in sapmalar) > DENGE_UYARI:
        uyarilar.append(
            "Güncel veriyle bölgeler arası fark %"
            + format(max(abs(x) for x in sapmalar) * 100, ".1f").replace(".", ",") + " oluyor. "
            "Hazır plan eski HP sayılarıyla hesaplanmış olabilir; 'Güncel veriyle yeniden hesapla' deyin.")
    if listede_el:
        uyarilar.append(
            f"Bugünkü listelerde {listede_el} bina el değiştiriyor. Listeler bugün olduğu gibi kalır; "
            "bu binaları bugün eski satışçısı gezebilir. Planı akşam uygulamak en temizi.")
    if bolgesiz:
        uyarilar.append(
            f"{len(bolgesiz)} satışçının bölgesi kalmıyor: {', '.join(s['ad'] for s in bolgesiz[:5])}. "
            "Bölgesiz kalırlar; pasife almak için uygularken onay verin.")
    if yeni_satisci_gereken:
        uyarilar.append(
            f"{len(yeni_satisci_gereken)} yeni bölge için yer tutucu satışçı hesabı ve davet kodu açılacak "
            f"(bölge {', '.join(map(str, yeni_satisci_gereken))}).")
    if plan.dogrudan < len(binalar):
        uyarilar.append(f"{len(binalar) - plan.dogrudan} bina planda yoktu (sonradan eklenmiş); "
                        "en yakın binanın bölgesine verildi.")

    return {
        "n": n, "olcu": plan.olcu, "plan_ref": plan.ref, "kaynak": plan.kaynak,
        "kaynak_ad": {"hazir": "Hazır plan (sunum paketi)", "onbellek": "Hazır plan (bolge.py önbelleği)",
                      "hesap": "Güncel veriyle hesaplandı"}.get(plan.kaynak, plan.kaynak),
        "parametreler": plan.parametreler,
        "mevcut_n": mevcut_n,
        "bolgeler": bolgeler,
        "denge": {"sapma_min": min(sapmalar) if sapmalar else 0.0,
                  "sapma_maks": max(sapmalar) if sapmalar else 0.0},
        "fark": {
            "aktif_bina": aktif_bina,
            "el_degistiren_bina": el_bina,
            "el_degistiren_oran": round(el_bina / aktif_bina, 4) if aktif_bina else 0.0,
            "el_degistiren_ziyaret": el_ziyaret,
            "el_degistiren_dokunulmus_bina": el_dokunulmus,
            "numarasi_degisen_bina": numara_degisen,
            "bugun_listede_el_degistiren": listede_el,
            "satisci_hareketleri": hareket,
            "bolgesiz_kalacak_satiscilar": bolgesiz,
            "yeni_satisci_acilacak_bolgeler": yeni_satisci_gereken,
            "kalkan_bolgeler": kalkan,
        },
        "uyarilar": uyarilar,
        "_son_atama": son, "_tasima": tasima,
    }


def disa(onizleme: dict) -> dict:
    """API yanıtı: iç alanlar (_son_atama ...) atılır."""
    return {k: v for k, v in onizleme.items() if not k.startswith("_")}


def ref_coz(plan_ref: str) -> tuple[str, int, str, str]:
    try:
        kaynak, n, olcu, imza = plan_ref.split(":")
        return kaynak, int(n), olcu, imza
    except (ValueError, AttributeError):
        raise PlanHatasi(400, "Plan kimliği geçersiz. Önce önizleme yapın.", "plan_ref_gecersiz")


# ============================================================================= uygula / geri al
def _aktif_plan(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM bolge_plani WHERE aktif=1 ORDER BY id DESC LIMIT 1").fetchone()


def _bolge_adlari(conn: sqlite3.Connection) -> dict[int, str]:
    try:
        return {int(k): v for k, v in json.loads(db.ayar_oku(conn, "bolge_adlari") or "{}").items()}
    except (ValueError, TypeError):
        return {}


def _baslangic_kaydi(conn: sqlite3.Connection, yapan_id: int | None) -> int:
    """İlk plan uygulanmadan önce bugünkü durum 'baslangic' planı olarak kaydedilir (geri dönülebilsin)."""
    atama = {r[0]: int(r[1] or 0) for r in conn.execute("SELECT bina_serial, bolge FROM bina")}
    n = db.bolge_sayisi(conn)
    adlar = _bolge_adlari(conn)
    renk = _renkler(n)
    bolgeler = [{"bolge": k, "ad": adlar.get(k, f"Bölge {k}"), "renk": renk[k - 1]} for k in range(1, n + 1)]
    imlec = conn.execute(
        "INSERT INTO bolge_plani (n, olcu, kaynak, plan_ref, imza, atama, bolgeler, kullanicilar, ozet, "
        "olusturan_id, zaman, aktif, notu) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?)",
        (n, "res_hp", "baslangic", None, _imza(atama), json.dumps(atama, separators=(",", ":")),
         json.dumps(bolgeler, ensure_ascii=False), "[]", "{}", yapan_id, ayarlar.zaman_metni(),
         "Planlayıcı ilk kez kullanılmadan önceki bölgeler"))
    return int(imlec.lastrowid)


def _yer_tutucu_telefon(conn: sqlite3.Connection, bolge: int) -> str:
    aday = 5_000_000_000 + bolge
    while conn.execute("SELECT 1 FROM kullanici WHERE telefon=?", (str(aday),)).fetchone():
        aday += 100
    return str(aday)


def uygula(conn: sqlite3.Connection, plan_ref: str, n: int, yapan_id: int,
           pasiflestir: bool = False, notu: str | None = None) -> dict:
    kaynak, n_ref, olcu, imza = ref_coz(plan_ref)
    if n_ref != int(n):
        raise PlanHatasi(400, "Plan kimliği ile bölge sayısı uyuşmuyor.", "plan_ref_gecersiz")
    binalar = _binalar(conn)
    plan = plan_bul(binalar, n, olcu, kaynak)
    if plan is None:
        raise PlanHatasi(409, "Bu plan artık bulunamıyor. Lütfen tekrar önizleyin.", "plan_yok")
    if plan.imza != imza:
        raise PlanHatasi(409, "Önizlemeden sonra binalar değişti (yeni tur raporu ya da bina). "
                              "Lütfen tekrar önizleyin.", "plan_degisti")
    on = onizle(conn, plan, binalar)
    son, tasima = on["_son_atama"], on["_tasima"]
    simdi = ayarlar.zaman_metni()

    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        aktif = _aktif_plan(conn)
        onceki_id = int(aktif["id"]) if aktif else _baslangic_kaydi(conn, yapan_id)
        satiscilar = _satiscilar(conn)
        anlik = [{"id": s["id"], "bolge": s["bolge"], "aktif": s["aktif"]} for s in satiscilar]

        eski = {b["bina_serial"]: int(b.get("bolge") or 0) for b in binalar}
        degisen = [(k, s) for s, k in son.items() if eski.get(s) != k]
        conn.executemany("UPDATE bina SET bolge=? WHERE bina_serial=?", degisen)

        tasinan, bosta, pasif_edilen = [], [], []
        for s in satiscilar:
            b0 = int(s["bolge"] or 0)
            if b0 in tasima:
                if tasima[b0] != b0:
                    conn.execute("UPDATE kullanici SET bolge=? WHERE id=?", (tasima[b0], s["id"]))
                    tasinan.append({"id": s["id"], "ad": s["ad"], "eski_bolge": b0, "yeni_bolge": tasima[b0]})
            elif b0 != 0:
                # Bölgesi kalmayan satışçı: "bölgesiz" (0). 0, hiçbir binaya dokunamayan güvenli
                # durumdur; NULL olsaydı satışçı ekranları bütün şehri gösterirdi.
                if pasiflestir and s["aktif"]:
                    conn.execute("UPDATE kullanici SET bolge=0, aktif=0, oturum_no=oturum_no+1 WHERE id=?",
                                 (s["id"],))
                    pasif_edilen.append({"id": s["id"], "ad": s["ad"], "eski_bolge": b0})
                else:
                    conn.execute("UPDATE kullanici SET bolge=0 WHERE id=?", (s["id"],))
                    if s["aktif"]:
                        bosta.append({"id": s["id"], "ad": s["ad"], "eski_bolge": b0})

        # Satışçısı olmayan bölgeye yer tutucu hesap + davet kodu (hesap SİLİNMEZ, yalnız eklenir)
        sahipli = {int(r[0]) for r in conn.execute(
            "SELECT DISTINCT bolge FROM kullanici WHERE rol='satisci' AND aktif=1 AND bolge>0")}
        adlar = {b["bolge"]: b for b in on["bolgeler"]}
        yeni_hesaplar = []
        for k in range(1, n + 1):
            if k in sahipli:
                continue
            kod = guvenlik.davet_kodu_uret()
            ad = f"{k}. Satışçı — {adlar[k].get('kisa_ad') or adlar[k].get('ad')}"[:80]
            tel = _yer_tutucu_telefon(conn, k)
            imlec = conn.execute(
                "INSERT INTO kullanici (ad, telefon, pin_hash, davet_kodu, rol, bolge, aktif, olusturma) "
                "VALUES (?,?,NULL,?,'satisci',?,1,?)", (ad, tel, kod, k, simdi))
            yeni_hesaplar.append({"id": int(imlec.lastrowid), "ad": ad, "bolge": k, "telefon": tel,
                                  "telefon_goster": guvenlik.telefon_goster(tel), "davet_kodu": kod})

        bolge_kaydi = [{a: b.get(a) for a in ("bolge", "ad", "kisa_ad", "renk", "poligon", "merkez", "etiket")}
                       for b in on["bolgeler"]]
        ozet = {**{k: v for k, v in on["fark"].items() if not isinstance(v, list)},
                "tasinan_satiscilar": tasinan, "bolgesiz_kalan": bosta, "pasife_alinan": pasif_edilen,
                "yeni_satiscilar": [{k: v for k, v in h.items() if k != "davet_kodu"} for h in yeni_hesaplar],
                "yeni_satisci_idler": [h["id"] for h in yeni_hesaplar],
                "degisen_bina": len(degisen), "parametreler": plan.parametreler}
        conn.execute("UPDATE bolge_plani SET aktif=0 WHERE aktif=1")
        imlec = conn.execute(
            "INSERT INTO bolge_plani (n, olcu, kaynak, plan_ref, imza, atama, bolgeler, kullanicilar, ozet, "
            "olusturan_id, zaman, aktif, onceki_id, notu) VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (n, olcu, plan.kaynak, plan.ref, plan.imza, json.dumps(son, separators=(",", ":")),
             json.dumps(bolge_kaydi, ensure_ascii=False, separators=(",", ":")),
             json.dumps(anlik), json.dumps(ozet, ensure_ascii=False), yapan_id, simdi, onceki_id,
             (notu or "").strip()[:500] or None))
        plan_id = int(imlec.lastrowid)
        db.ayar_yaz(conn, "bolge_adlari", json.dumps({b["bolge"]: b["ad"] for b in on["bolgeler"]},
                                                     ensure_ascii=False))
        db.bina_surumu_arttir(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "plan_id": plan_id, "n": n, "onceki_plan_id": onceki_id,
        "degisen_bina": len(degisen), "el_degistiren_bina": on["fark"]["el_degistiren_bina"],
        "el_degistiren_ziyaret": on["fark"]["el_degistiren_ziyaret"],
        "tasinan_satiscilar": tasinan, "bolgesiz_kalan": bosta, "pasife_alinan": pasif_edilen,
        "yeni_satiscilar": yeni_hesaplar,
        "mesaj": (f"{n} bölgelik plan uygulandı. {len(degisen):,} binanın bölgesi değişti; ziyaret geçmişi "
                  "olduğu gibi duruyor.").replace(",", "."),
    }


def geri_al(conn: sqlite3.Connection, yapan_id: int) -> dict:
    aktif = _aktif_plan(conn)
    if not aktif or not aktif["onceki_id"]:
        raise PlanHatasi(409, "Geri alınacak bir plan yok.", "geri_alinacak_yok")
    onceki = conn.execute("SELECT * FROM bolge_plani WHERE id=?", (aktif["onceki_id"],)).fetchone()
    if not onceki:
        raise PlanHatasi(409, "Önceki plan kaydı bulunamadı.", "geri_alinacak_yok")
    hedef_atama = {k: int(v) for k, v in json.loads(onceki["atama"]).items()}
    binalar = _binalar(conn)
    _en_yakina_tamamla(binalar, hedef_atama)       # arada eklenen binalar en yakın komşunun bölgesine
    anlik = json.loads(aktif["kullanicilar"] or "[]")
    ozet = json.loads(aktif["ozet"] or "{}")

    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        degisen = [(hedef_atama[b["bina_serial"]], b["bina_serial"]) for b in binalar
                   if hedef_atama.get(b["bina_serial"]) is not None
                   and int(b.get("bolge") or 0) != hedef_atama[b["bina_serial"]]]
        conn.executemany("UPDATE bina SET bolge=? WHERE bina_serial=?", degisen)
        anlik_idler = set()
        for s in anlik:
            anlik_idler.add(int(s["id"]))
            conn.execute("UPDATE kullanici SET bolge=?, aktif=? WHERE id=? AND rol='satisci'",
                         (s["bolge"], s["aktif"], s["id"]))
        kapatilan = []
        for kid in ozet.get("yeni_satisci_idler", []):
            if int(kid) in anlik_idler:
                continue
            r = conn.execute("SELECT id, ad, pin_hash FROM kullanici WHERE id=?", (kid,)).fetchone()
            if r:
                conn.execute("UPDATE kullanici SET aktif=0, oturum_no=oturum_no+1 WHERE id=?", (kid,))
                kapatilan.append({"id": r["id"], "ad": r["ad"], "pin_belirlemisti": bool(r["pin_hash"])})
        conn.execute("UPDATE bolge_plani SET aktif=0, geri_alindi=1 WHERE id=?", (aktif["id"],))
        conn.execute("UPDATE bolge_plani SET aktif=1 WHERE id=?", (onceki["id"],))
        try:
            adlar = {b["bolge"]: b.get("ad") for b in json.loads(onceki["bolgeler"] or "[]")}
            db.ayar_yaz(conn, "bolge_adlari", json.dumps(adlar, ensure_ascii=False))
        except (ValueError, TypeError, KeyError):
            pass
        db.bina_surumu_arttir(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"plan_id": int(onceki["id"]), "geri_alinan_plan_id": int(aktif["id"]), "n": int(onceki["n"]),
            "degisen_bina": len(degisen), "kapatilan_yer_tutucular": kapatilan,
            "mesaj": f"{int(onceki['n'])} bölgelik önceki plana dönüldü. {len(degisen)} binanın bölgesi "
                     "geri alındı; satışçılar eski bölgelerinde."}


# ============================================================================= durum
def durum(conn: sqlite3.Connection) -> dict:
    binalar = _binalar(conn)
    n = db.bolge_sayisi(conn)
    atama = {b["bina_serial"]: int(b.get("bolge") or 0) for b in binalar}
    olcu = "res_hp"
    aktif = _aktif_plan(conn)
    adlar = _bolge_adlari(conn)
    plan_bolgeleri: dict[int, dict] = {}
    if aktif:
        olcu = aktif["olcu"] or "res_hp"
        try:
            plan_bolgeleri = {int(b["bolge"]): b for b in json.loads(aktif["bolgeler"] or "[]")}
        except (ValueError, TypeError, KeyError):
            plan_bolgeleri = {}
    sayilar = _bolge_sayilari(binalar, atama, n, olcu)
    satiscilar = _satiscilar(conn)
    renk = _renkler(n)
    bolgeler = []
    for k in range(1, n + 1):
        pb = plan_bolgeleri.get(k, {})
        bolgeler.append({
            "bolge": k, "ad": pb.get("ad") or adlar.get(k) or f"Bölge {k}",
            "kisa_ad": pb.get("kisa_ad") or f"B{k}", "renk": renk[k - 1], **sayilar[k],
            "poligon": pb.get("poligon"),
            "satiscilar": [_kart(s) for s in satiscilar if int(s["bolge"] or 0) == k],
        })
    bolgesiz = [_kart(s) | {"bolge": s["bolge"]} for s in satiscilar
                if s["aktif"] and not (1 <= int(s["bolge"] or 0) <= n)]
    gecmis = [dict(r) for r in conn.execute(
        "SELECT p.id, p.n, p.olcu, p.kaynak, p.zaman, p.aktif, p.geri_alindi, p.onceki_id, p.notu, "
        "       k.ad AS olusturan FROM bolge_plani p LEFT JOIN kullanici k ON k.id=p.olusturan_id "
        "ORDER BY p.id DESC LIMIT 20").fetchall()]
    toplam = {a: sum(b[a] for b in bolgeler) for a in ("bina", "res_hp", "firsat", "kalan_firsat",
                                                     "dokunulan", "satis")}
    toplam["dokunulan_oran"] = round(toplam["dokunulan"] / toplam["bina"], 4) if toplam["bina"] else 0.0
    return {
        "n": n, "olcu": olcu,
        "plan": ({"id": aktif["id"], "n": aktif["n"], "kaynak": aktif["kaynak"], "zaman": aktif["zaman"],
                  "notu": aktif["notu"]} if aktif else None),
        "geri_alinabilir": bool(aktif and aktif["onceki_id"]),
        "bolgeler": bolgeler,
        "toplam": toplam,
        "bolgesiz_satiscilar": bolgesiz,
        "bolgesiz_bina": sum(1 for b in binalar if not b.get("pasif") and not (1 <= atama[b["bina_serial"]] <= n)),
        "hazir_nler": hazir_nler(),
        "en_az_n": EN_AZ_N, "en_cok_n": EN_COK_N,
        "calisan_is": calisan_is(),
        "gecmis": gecmis,
    }


# ============================================================================= Excel
_excel_kilidi = threading.Lock()


def excel_yolu(conn: sqlite3.Connection, plan_id: int | None = None) -> tuple[Path, str]:
    """Etkin (ya da verilen) plan için açıklayıcı Excel. Yoksa üretir (~20-30 sn), varsa önbellekten."""
    if plan_id is not None:
        satir = conn.execute("SELECT * FROM bolge_plani WHERE id=?", (plan_id,)).fetchone()
        if not satir:
            raise PlanHatasi(404, "Plan bulunamadı.", "plan_yok")
    else:
        satir = _aktif_plan(conn)
    if satir is not None:
        n, olcu, pid = int(satir["n"]), satir["olcu"] or "res_hp", int(satir["id"])
        if satir["aktif"]:
            # Etkin plan: veritabanındaki bölgeler (planın ardından OneMap'le eklenen binalar dahil)
            atama = {r[0]: int(r[1] or 0) for r in conn.execute("SELECT bina_serial, bolge FROM bina")}
        else:
            atama = {k: int(v) for k, v in json.loads(satir["atama"]).items()}
        try:
            plan_bolgeleri = {int(b["bolge"]): b for b in json.loads(satir["bolgeler"] or "[]")}
        except (ValueError, TypeError, KeyError):
            plan_bolgeleri = {}
    else:
        n, olcu, pid = db.bolge_sayisi(conn), "res_hp", 0
        atama = {r[0]: int(r[1] or 0) for r in conn.execute("SELECT bina_serial, bolge FROM bina")}
        plan_bolgeleri = {k: {"ad": v} for k, v in _bolge_adlari(conn).items()}

    sorumlular: dict[int, str] = {}
    for s in _satiscilar(conn):
        if s["aktif"] and 1 <= int(s["bolge"] or 0) <= n:
            sorumlular[int(s["bolge"])] = ", ".join(x for x in (sorumlular.get(int(s["bolge"])), s["ad"]) if x)
    anahtar = hashlib.sha1(json.dumps([pid, db.bina_surum_oku(conn), sorumlular], ensure_ascii=False)
                           .encode()).hexdigest()[:10]
    klasor = _excel_dizini() / f"plan_{pid}_{anahtar}"
    ad = f"Bursa_{n}_Satisci_Bolgeleme.xlsx"
    yol = klasor / ad
    if yol.exists():
        return yol, ad

    with _excel_kilidi:
        if yol.exists():
            return yol, ad
        import pandas as pd

        from dsale import excel_report, metrics

        df = veri_cercevesi(conn, sadece_aktif=True)
        df["bolge"] = df["bina_serial"].map(atama).fillna(0).astype(int)
        df = df[(df["bolge"] >= 1) & (df["bolge"] <= n)].reset_index(drop=True)
        seri = pd.Series(df["bolge"].to_numpy(), index=df["bina_serial"].to_numpy())
        hedef = float(df[olcu].sum()) / n
        sonuc = SimpleNamespace(n=n, olcu=olcu, atama=seri, hedef=hedef, parametreler={
            "algoritma": _algoritma(), "birim_sayisi": int(df["site_grup"].nunique()),
            "kaynak": "Saha Sistemi bölge planlayıcı", "plan_id": pid})
        bolgeler = metrics.bolge_ozetleri(df, seri, olcu, hedef)
        for b in bolgeler:
            pb = plan_bolgeleri.get(int(b["bolge"]), {})
            for a in ("ad", "kisa_ad"):
                if pb.get(a):
                    b[a] = pb[a]
        klasor.mkdir(parents=True, exist_ok=True)
        uretilen = excel_report.build(df, sonuc, bolgeler, klasor, sorumlular=sorumlular)
        if uretilen != yol:
            Path(uretilen).replace(yol)
    return yol, ad


def _algoritma() -> str:
    try:
        from dsale.partition import ALGORITMA_SURUMU

        return ALGORITMA_SURUMU
    except Exception:
        return "?"
