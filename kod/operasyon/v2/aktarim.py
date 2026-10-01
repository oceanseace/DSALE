"""Rapor içe aktarım hattı (F4, F5, F18; spec §4).

    AL → KİLİTLE → SAKLA → OKU → FARK → BEKÇİ → YEDEK → UYGULA (tek işlem) → BİLDİR

- Aynı dosya (sha256) ikinci kez: hiçbir şey yazılmaz, ``ayni_dosya`` döner.
- Anahtar BOSS Task No'dur. Bizim alanlarımız (atama, randevu, elle öbek/mahalle, ticket, notlar…) asla ezilmez.
- Eksik/eski rapor bekçisi: çok iş kaybolduysa ya da rapor son yüklenenden eskiyse otomatik uygulanmaz
  (409 ``onay_gerekli``); onayla ``uygula`` farkı yeniden hesaplar. Eski raporda hiçbir iş kapatılmaz.
- Yazmadan önce veritabanının doğrulanmış yedeği alınır; yazma TEK işlemdir (hata → ROLLBACK, hiçbir iş değişmez).
- Ayrıştırma çekirdeği ``operasyon/is_emri.py``'dir (Location-önce kuralı); sözlük ve bina veritabanından gelir.
Kişisel veri (müşteri adı/no/adres) hiçbir günlük, özet ya da fark dosyasına yazılmaz; yalnız sayılar ve Task No.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import io
import json
import os
import sqlite3
import stat
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from operasyon import is_emri as ie

from . import akis, aski, kesinti, kisi, kurallar, obek, sozluk, zaman
from .hatalar import Catisma, Gecersiz, V2Hata
from .islem import islem

AZAMI_BOYUT = 25 * 1024 * 1024
_KILIT = threading.Lock()
AKTARIM_YEDEK_SAKLA = 10

BOLGE_IL_K = {"BURSA", "YALOVA"}
ALTYAPI_KONULARI = ("SİNYAL", "EK SP", "GÜZERGAH", "ALTYAPI")
TICKET_ACIK = ("AÇIK", "HATA", "TRANSFER")
BOSS_DURUM = {"ACIK": "acik", "ASKIYA ALINDI": "askida", "BASLANDI": "basladi", "MERKEZE GONDERILDI": "merkeze",
              "KONUM PAYLASILDI": "konum", "BITIRILDI": "bitti", "KAPALI": "bitti", "IPTAL": "bitti"}

# BOSS sütunları (başlık metinleri birebir)
K = {"no": "Task No", "task": "Task Adı", "musteri_no": "Müşteri No", "musteri_adi": "Müşteri Adı", "ekip": "Ekip",
     "adres": "Adres", "kanal": "Satış Kanalı", "il": "İl", "ilce": "İlçe", "baslangic": "Task Başlangıç Tarihi",
     "durum": "Task Durumu", "randevu_durumu": "Randevu Durumu", "randevu_bas": "Randevu Başlangıç Tarihi",
     "randevu_bit": "Randevu Bitiş Tarihi", "aski": "Askıya Alınma Nedeni", "sl": "SL", "sl_saat": "SL Süresi(Sa)",
     "son_aciklama": "Son Açıklama", "lokasyon": "Lokasyon", "merkeze": "Merkeze Gönder Statüsü",
     "konum_tarihi": "Teknik Ekip Konum Paylaşma Tarihi", "basla_tarihi": "Teknik Ekip İşe Başlama Tarihi"}

KONUM_KAYNAGI = {"bina (Lokasyon)": "bina", "bina (BN kodu)": "bina", "bina (site adı)": "bina",
                 "site (site adı)": "site", "mahalle merkezi": "mahalle_merkezi", "ilçe merkezi (kaba)": "ilce_merkezi"}
# Kişisel veri: olay defterine yalnız alan adı yazılır
KISISEL = {"musteri_no", "musteri_adi", "adres", "musteri_ozet", "musteri_tel"}
BOSS_ALANLARI = ("boss_durum", "boss_randevu_durumu", "boss_randevu_bas", "boss_randevu_bit", "boss_ekip",
                 "boss_aski_nedeni", "boss_sl", "boss_sl_saat", "boss_son_aciklama")
RAPOR_ALANLARI = ("task_adi", "satis_kanali", "kanal_grubu", "serit", "btk_hedef_saat", "musteri_no", "musteri_ozet",
                  "musteri_adi", "adres", "lokasyon", "acilis", "son24", "btk_hedef", *BOSS_ALANLARI)
YER_ALANLARI = ("il", "ilce", "mahalle", "il_k", "ilce_k", "mahalle_k", "mahalle_kaynak", "bina_serial", "lat", "lon",
                "konum_kaynak", "konum_yaklasik")


class RaporTanimadi(Gecersiz):
    kod = "rapor_tanimadi"


# ----------------------------------------------------------------------------- yardımcılar
def veri_dizini() -> Path:
    return sozluk.veri_dizini()


def gelen_dizini() -> Path:
    d = veri_dizini() / "gelen"
    d.mkdir(parents=True, exist_ok=True)
    return d


def musteri_ozeti(musteri_no: str | None) -> str | None:
    """HMAC-SHA256(gizli anahtar, müşteri no): numara silinse de tekrar arıza/kötü geçmiş bununla bulunur."""
    if not musteri_no:
        return None
    from saha import guvenlik
    anahtar = ("musteri-ozet:" + guvenlik.gizli_anahtar()).encode("utf-8")
    return hmac.new(anahtar, str(musteri_no).strip().encode("utf-8"), hashlib.sha256).hexdigest()


def _metin(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return None
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _zaman(v) -> str | None:
    t = zaman.oku(_metin(v))
    return zaman.metin(t) if t else None


def _sayi(v) -> float | None:
    s = _metin(v)
    if s is None:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def dosya_zamani_normal(deger) -> str | None:
    """Tarayıcının File.lastModified'ı (ISO, 'Z' ya da ofsetli) ya da dosya mtime'ı → Türkiye saati metni."""
    if deger is None or deger == "":
        return None
    if isinstance(deger, (int, float)):
        t = dt.datetime.fromtimestamp(float(deger), tz=dt.timezone.utc)
    else:
        s = str(deger).strip()
        if s.isdigit():                                  # milisaniye
            t = dt.datetime.fromtimestamp(int(s) / 1000, tz=dt.timezone.utc)
        else:
            try:
                t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
            except ValueError:
                return _zaman(s)
    if t.tzinfo is None:
        return zaman.metin(t.replace(microsecond=0))
    from saha import ayarlar
    return zaman.metin(t.astimezone(ayarlar.TR).replace(tzinfo=None, microsecond=0))


def _ayar(conn, anahtar, varsayilan=None):
    r = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return r[0] if r and r[0] not in (None, "") else varsayilan


def _ayar_json(conn, anahtar, varsayilan):
    try:
        v = json.loads(_ayar(conn, anahtar, "") or "null")
    except ValueError:
        return varsayilan
    return v if v is not None else varsayilan


def _db_yolu(conn: sqlite3.Connection) -> Path:
    for r in conn.execute("PRAGMA database_list"):
        if r[1] == "main":
            return Path(r[2])
    raise V2Hata("Veritabanı dosyası bulunamadı.", kod="yedek_alinamadi", durum=503)


# ----------------------------------------------------------------------------- OKU
@dataclass
class Hazirlik:
    isler: list[dict]
    ozet: dict
    rapor_en_yeni: str | None
    sozluk_anahtarlari: dict = field(default_factory=dict)     # (il_k, ilce_k) → {mahalle_k}
    yeni_mahalleler: list[tuple] = field(default_factory=list)


def rapor_tablosu(veri: bytes) -> pd.DataFrame:
    """'Task No', 'Task Adı', 'Adres' başlıklı sayfayı bulur; yoksa 422 rapor_tanimadi."""
    try:
        df = ie.raporu_oku(io.BytesIO(veri))
    except Exception:          # noqa: BLE001 — Excel değil / sayfa yok: tek Türkçe cümle
        raise RaporTanimadi("Bu dosya Teknik Task Detay Raporu değil. BOSS'tan doğru raporu indirin.")
    if K["no"] not in df.columns or K["task"] not in df.columns or K["adres"] not in df.columns:
        raise RaporTanimadi("Bu dosya Teknik Task Detay Raporu değil. BOSS'tan doğru raporu indirin.")
    return df


def triyaj_hesapla(conn, *, il, il_k, ilce_k, mahalle_k, mahalle_kaynak, obek_id, obek_elle_id, eski_neden=None,
                   sozluk_anahtarlari: dict | None = None) -> str | None:
    """Kontrol nedeni (spec §4-4). 'Konum yaklaşık' neden DEĞİLDİR; elle öbek verilmiş iş Kontrol'de kalmaz (F5)."""
    if eski_neden == "altyapi_supheli":
        return eski_neden                       # teknisyenin bildirimi; yalnız operasyon kaldırır
    if obek_elle_id:
        return None
    if (il_k or ie.anahtar(il or "")) not in BOLGE_IL_K:
        return "il_disi"
    if not mahalle_k:
        return "mahalle_yok"
    if obek_id is None:
        if mahalle_kaynak in ("adres-yeni", "koy", "adres-isaretsiz"):
            if sozluk_anahtarlari is not None:
                bilinen = sozluk_anahtarlari.get((il_k, ilce_k), set())
            else:
                bilinen = {r[0] for r in conn.execute("SELECT mahalle_k FROM mahalle WHERE il_k=? AND ilce_k=?",
                                                      (il_k, ilce_k))} | {
                    r[0] for r in conn.execute("SELECT esad_k FROM mahalle_esad WHERE il_k=? AND ilce_k=?", (il_k, ilce_k))}
            if mahalle_k not in bilinen and sozluk.benzerler(bilinen, mahalle_k):
                return "mahalle_benzer"
        return "obeksiz"
    return None


def triyaj_metni(neden: str | None, il=None, ilce=None, mahalle=None, benzer: str | None = None) -> str | None:
    if neden == "il_disi":
        return f"Adres {il or '—'} yazıyor; bölgemiz Bursa ve Yalova."
    if neden == "mahalle_yok":
        return "Adreste mahalle bulunamadı."
    if neden == "mahalle_benzer":
        return f"'{mahalle}' yazılmış; '{benzer}' olabilir." if benzer else f"'{mahalle}' listede yok; benzer bir mahalle var."
    if neden == "obeksiz":
        return f"Mahallesi hiçbir öbekte değil: {mahalle} · {ilce}."
    if neden == "altyapi_supheli":
        return "Teknisyen altyapı sorunu bildirdi."
    return None


def hazirla(conn: sqlite3.Connection, df: pd.DataFrame) -> Hazirlik:
    """Rapor tablosu → iş sözlükleri (henüz hiçbir şey yazılmaz)."""
    t0 = time.perf_counter()
    szl = sozluk.sozluk_db(conn)
    ilce_h = sozluk.ilce_haritasi(conn)
    istisnalar = _ayar_json(conn, "filtre_istisnalari", list(ie.VARSAYILAN_ISTISNALAR))
    kr = kurallar.yukle(conn)                      # EK-12: şerit/BTK hedefi ve hedef (SL) saatleri ayardan
    df = df.copy()
    for kol in (K["il"], K["ilce"]):
        if kol not in df.columns:
            df[kol] = ""
    # İlçe eşadları: 'M.Kemalpaşa' → Mustafakemalpaşa, 'Yalova Merkez' → Merkez (asıl yazım)
    asil = [sozluk.ilce_coz(ilce_h, a, b) for a, b in zip(df[K["il"]].fillna(""), df[K["ilce"]].fillna(""))]
    df[K["il"]] = [c[2] if c else a for c, a in zip(asil, df[K["il"]].fillna(""))]
    df[K["ilce"]] = [c[3] if c else b for c, b in zip(asil, df[K["ilce"]].fillna(""))]
    sonuc = ie.hazirla(df, ie.Obekler(), szl, istisnalar=istisnalar, mahalle_cozucu=sozluk.mahalle_coz)
    d = sonuc.isler
    anahtarlar = {ik: set(v) for ik, v in szl.mah.items()}
    isler: list[dict] = []
    tekrar_no = 0
    goruldu: set[str] = set()
    lok_var = lok_eslesen = 0
    yeni_mh: dict[tuple, tuple] = {}
    en_yeni = None
    for _, r in d.iterrows():
        no = _metin(r.get(K["no"]))
        if not no:
            continue
        if no in goruldu:
            tekrar_no += 1
            continue
        goruldu.add(no)
        task = _metin(r.get(K["task"])) or "—"
        serit, btk_saat = akis.serit_bul(task, kr["serit"])
        hedef_saat = kurallar.hedef_saat(kr["hedef"], task)
        il, ilce = _metin(r.get(K["il"])) or "", _metin(r.get(K["ilce"])) or ""
        il_k, ilce_k = ie.ilce_anahtari(il, ilce)
        c = sozluk.ilce_coz(ilce_h, il, ilce)
        if c:
            il_k, ilce_k = c[0], c[1]
        mahalle = _metin(r.get("Mahalle"))
        mk = ie.anahtar(mahalle) if mahalle else ""
        mkaynak = r.get("Mahalle Kaynağı") or None
        # eşad → asıl mahalle adı
        mh_obj = szl.mah.get(ie.ilce_anahtari(il, ilce), {}).get(mk) if mk else None
        if mh_obj is not None:
            mahalle, mk = mh_obj.ad, ie.anahtar(mh_obj.ad)
        lok = _metin(r.get(K["lokasyon"]))
        kk = r.get("Konum Kaynağı") or "yok"
        if lok:
            lok_var += 1
            lok_eslesen += 1 if kk == "bina (Lokasyon)" else 0
        acilis = _zaman(r.get(K["baslangic"])) or zaman.metin()
        acilis_t = zaman.oku(acilis)
        en_yeni = max(en_yeni or acilis, acilis)
        lat, lon = r.get("Enlem"), r.get("Boylam")
        lat = None if lat is None or pd.isna(lat) else float(lat)
        lon = None if lon is None or pd.isna(lon) else float(lon)
        musteri_no = _metin(r.get(K["musteri_no"]))
        is_ = {
            "boss_task_no": no, "task_adi": task, "satis_kanali": _metin(r.get(K["kanal"])),
            "kanal_grubu": akis.kanal_grubu(r.get(K["kanal"])), "serit": serit, "btk_hedef_saat": btk_saat,
            "musteri_no": musteri_no, "musteri_ozet": musteri_ozeti(musteri_no),
            "musteri_adi": _metin(r.get(K["musteri_adi"])), "adres": _metin(r.get(K["adres"])),
            "il": il or None, "ilce": ilce or None, "mahalle": mahalle or None, "il_k": il_k, "ilce_k": ilce_k,
            "mahalle_k": mk or None, "mahalle_kaynak": mkaynak if mahalle else None, "lokasyon": lok,
            "bina_serial": _metin(r.get("Bina Serial")), "lat": lat, "lon": lon,
            "konum_kaynak": KONUM_KAYNAGI.get(kk), "konum_yaklasik": 0 if KONUM_KAYNAGI.get(kk) in ("bina", "site") else 1,
            "acilis": acilis, "son24": zaman.metin(acilis_t + dt.timedelta(hours=hedef_saat)),
            "btk_hedef": zaman.metin(acilis_t + dt.timedelta(hours=btk_saat)) if btk_saat else None,
            "boss_durum": _metin(r.get(K["durum"])), "boss_randevu_durumu": _metin(r.get(K["randevu_durumu"])),
            "boss_randevu_bas": _zaman(r.get(K["randevu_bas"])), "boss_randevu_bit": _zaman(r.get(K["randevu_bit"])),
            "boss_ekip": _metin(r.get(K["ekip"])),
            "boss_aski_nedeni": _metin(r.get(K["aski"])) if aski.boss_askida_mi(r.get(K["durum"])) else None,
            "boss_sl": _metin(r.get(K["sl"])), "boss_sl_saat": _sayi(r.get(K["sl_saat"])),
            "boss_son_aciklama": _metin(r.get(K["son_aciklama"])),
            "_merkeze": _metin(r.get(K["merkeze"])), "_konum_tarihi": _zaman(r.get(K["konum_tarihi"])),
            "_basla_tarihi": _zaman(r.get(K["basla_tarihi"])), "_alt_yer": r.get("Bilgi") or "",
        }
        is_["boss_ozet"] = boss_ozeti(is_)
        isler.append(is_)
        # sözlük: raporda görülen yeni mahalle (benzeri yoksa) 'rapor' kaynağıyla eklenecek
        if mk and il_k in BOLGE_IL_K and c and mkaynak in ("adres-yeni", "adres-isaretsiz", "koy"):
            bilinen = anahtarlar.get(ie.ilce_anahtari(il, ilce), set())
            if mk not in bilinen and not sozluk.benzerler(bilinen, mk):
                yeni_mh[(il_k, ilce_k, mk)] = (il, ilce, mahalle)
    cikarilan_adlar = {str(k): int(v) for k, v in sonuc.cikarilan[K["task"]].value_counts().items()} \
        if len(sonuc.cikarilan) else {}
    ozet = {
        "satir": int(sonuc.ozet["toplam_satir"]),
        "cikarilan": int(sonuc.ozet["cikarilan"]),
        "kurulum": int(sonuc.ozet["cikarilan_neden"].get("KURULUM", 0)),
        "ikinci_donanim": int(sonuc.ozet["cikarilan_neden"].get("2 DONANIM", 0)),
        "istisna_tutulan": int(sonuc.ozet.get("istisna_tutulan", 0)),
        "cikarilan_adlar": cikarilan_adlar,
        "is_sayisi": len(isler), "tekrar_task_no": tekrar_no,
        "lokasyon": {"var": lok_var, "eslesen": lok_eslesen},
        "mahalle_kaynak": {str(k): int(v) for k, v in sonuc.ozet["mahalle_kaynak"].items()},
        "konum_kaynak": {str(k): int(v) for k, v in sonuc.ozet["konum_kaynak"].items()},
        "okuma_sn": round(time.perf_counter() - t0, 3),
    }
    # anahtarlar (ilçe_anahtari biçimi) → (il_k, ilce_k) biçimine: asıl ilçe anahtarıyla aynı
    duz = {}
    for (ik, ck), v in anahtarlar.items():
        c = sozluk.ilce_coz(ilce_h, ik, ck) if ik else None
        duz[(c[0], c[1]) if c else (ik, ck)] = set(v) | duz.get((c[0], c[1]) if c else (ik, ck), set())
    return Hazirlik(isler, ozet, en_yeni, duz, [(a, b, c_, *yeni_mh[(a, b, c_)]) for (a, b, c_) in yeni_mh])


def boss_ozeti(is_: dict) -> str:
    """"Değişti mi" özeti: BOSS alanları + task + adres + lokasyon + müşteri alanları (sha1)."""
    parca = [str(is_.get(a) if is_.get(a) is not None else "") for a in
             (*BOSS_ALANLARI, "task_adi", "adres", "lokasyon", "musteri_no", "musteri_adi", "acilis", "satis_kanali",
              "il", "ilce")]
    return hashlib.sha1("\x1f".join(parca).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------------------- FARK + BEKÇİ
@dataclass
class Fark:
    yeni: list[dict]
    degisen: list[tuple[dict, sqlite3.Row]]
    degismeyen: list[tuple[dict, sqlite3.Row]]
    yeniden_acilan: list[tuple[dict, sqlite3.Row]]
    kaybolan: list[sqlite3.Row]
    acik: int

    def sayilar(self) -> dict:
        return {"yeni": len(self.yeni), "degisen": len(self.degisen), "kaybolan": len(self.kaybolan),
                "yeniden_acilan": len(self.yeniden_acilan), "degismeyen": len(self.degismeyen)}

    def numaralar(self) -> dict:
        return {"yeni": [x["boss_task_no"] for x in self.yeni],
                "degisen": [r["is_no"] for _, r in self.degisen],
                "yeniden_acilan": [r["is_no"] for _, r in self.yeniden_acilan],
                "kaybolan": [r["is_no"] for r in self.kaybolan]}


def fark_hesapla(conn: sqlite3.Connection, isler: list[dict]) -> Fark:
    mevcut = {r["boss_task_no"]: r for r in conn.execute("SELECT * FROM is_emri WHERE boss_task_no IS NOT NULL")}
    dosyada = {x["boss_task_no"] for x in isler}
    yeni, degisen, degismeyen, yeniden = [], [], [], []
    for x in isler:
        r = mevcut.get(x["boss_task_no"])
        if r is None:
            yeni.append(x)
        elif r["durum"] == "kapandi":
            yeniden.append((x, r))
        elif r["boss_ozet"] != x["boss_ozet"]:
            degisen.append((x, r))
        else:
            degismeyen.append((x, r))
    kaybolan = [r for no, r in mevcut.items() if r["durum"] != "kapandi" and no not in dosyada]
    acik = sum(1 for r in mevcut.values() if r["durum"] != "kapandi")
    return Fark(yeni, degisen, degismeyen, yeniden, kaybolan, acik)


def bekci(conn: sqlite3.Connection, fark: Fark, dosya_zamani: str | None, rapor_en_yeni: str | None) -> tuple[list, dict]:
    esik = _ayar_json(conn, "aktarim_esik", {"kaybolan_oran": 0.25, "kaybolan_min": 50})
    nedenler = []
    sinir = max(int(esik.get("kaybolan_min", 50)), fark.acik * float(esik.get("kaybolan_oran", 0.25)))
    if len(fark.kaybolan) > sinir:
        nedenler.append("cok_kaybolan")
    son = conn.execute("SELECT dosya_zamani, rapor_en_yeni, bitis FROM ie_aktarim WHERE durum='uygulandi' "
                       "ORDER BY id DESC LIMIT 1").fetchone()
    if son is not None:
        eski = False
        if dosya_zamani and son["dosya_zamani"] and dosya_zamani < son["dosya_zamani"]:
            eski = True
        if rapor_en_yeni and son["rapor_en_yeni"]:
            if zaman.oku(rapor_en_yeni) < zaman.oku(son["rapor_en_yeni"]) - dt.timedelta(hours=1):
                eski = True
        if eski:
            nedenler.append("eski_rapor")
    bilgi = {"acik": fark.acik, "kaybolan_oran": round(len(fark.kaybolan) / fark.acik, 3) if fark.acik else 0.0,
             "son_rapor_zamani": (son["bitis"] if son else None)}
    return nedenler, bilgi


def bekci_mesaji(nedenler: list[str], fark: Fark, bilgi: dict) -> str:
    parca = []
    if "cok_kaybolan" in nedenler:
        oran = round(bilgi["kaybolan_oran"] * 100)
        parca.append(f"Bu raporda {len(fark.kaybolan)} açık iş yok (açık işlerin %{oran}'i). "
                     "Rapor süzgeçli ya da tek ilçe indirilmiş olabilir.")
    if "eski_rapor" in nedenler:
        saat = zaman.saat_dk(bilgi.get("son_rapor_zamani")) or "—"
        parca.append(f"Bu rapor en son yüklenenden ({saat}) eski görünüyor. İşlenirse hiçbir iş kapatılmaz, "
                     "yalnız eklenir ve güncellenir.")
    return " ".join(parca)


# ----------------------------------------------------------------------------- YEDEK
def aktarim_yedegi(db_yol: Path) -> Path:
    """saha.yedekle.aktarim_yedegi (WP-A) varsa o; yoksa aynı yöntem: salt okunur kaynak + backup API + doğrulama."""
    try:
        from saha import yedekle
        f = getattr(yedekle, "aktarim_yedegi", None)
    except ImportError:
        f = None
    if f is not None:
        return Path(f(Path(db_yol)))
    hedef_dizin = Path(db_yol).parent / "yedek" / "aktarim"
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    an = zaman.simdi()
    hedef = hedef_dizin / f"saha-aktarim-{an:%Y%m%d-%H%M%S}.db"
    n = 1
    while hedef.exists():
        hedef = hedef_dizin / f"saha-aktarim-{an:%Y%m%d-%H%M%S}-{n}.db"
        n += 1
    gecici = hedef.with_suffix(".yaziliyor")
    kaynak = sqlite3.connect(f"file:{Path(db_yol).as_posix()}?mode=ro", uri=True, timeout=30)
    try:
        hedef_conn = sqlite3.connect(gecici)
        try:
            kaynak.backup(hedef_conn)
            if hedef_conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise OSError("yedek bütünlük denetiminden geçmedi")
            for (t,) in kaynak.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                                       "('kullanici','is_emri','obek','ziyaret')"):
                if kaynak.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0] != \
                        hedef_conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]:
                    raise OSError(f"yedekte {t} satır sayısı tutmadı")
            hedef_conn.execute("PRAGMA journal_mode=DELETE")
        finally:
            hedef_conn.close()
    except Exception:
        gecici.unlink(missing_ok=True)
        raise
    finally:
        kaynak.close()
    os.replace(gecici, hedef)
    try:
        os.chmod(hedef, stat.S_IREAD)
    except OSError:
        pass
    eskiler = sorted(hedef_dizin.glob("saha-aktarim-*.db"))
    for p in eskiler[:-AKTARIM_YEDEK_SAKLA]:
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            p.unlink()
        except OSError:
            pass
    return hedef


# ----------------------------------------------------------------------------- UYGULA
_SUTUNLAR_EKLE = ("is_no", "boss_task_no", "kaynak", "satis_kanali", "kanal_grubu", "task_adi", "serit",
                  "btk_hedef_saat", "musteri_no", "musteri_ozet", "musteri_adi", "adres", "il", "ilce", "mahalle",
                  "il_k", "ilce_k", "mahalle_k", "mahalle_kaynak", "lokasyon", "bina_serial", "lat", "lon",
                  "konum_kaynak", "konum_yaklasik", "obek_id", "triyaj_nedeni", *BOSS_ALANLARI, "boss_ozet",
                  "durum", "durum_zamani", "atanan_id", "atama_kaynagi", "ticket_id", "askida_neden", "masa_vade",
                  "kotu_gecmis", "tekrar7g", "acilis", "son24", "btk_hedef", "ilk_gorulme", "gorulme_zamani",
                  "ilk_atama_zamani", "atama_zamani", "yolda_zamani", "sahada_zamani", "son_gorulme",
                  "son_aktarim_id", "guncelleme", "boss_bekleyen", "oneri_teknik_id", "uyanma")


@dataclass
class _Baglam:
    conn: sqlite3.Connection
    aktarim_id: int
    simdi: str
    obek_h: dict
    boss_h: dict
    kisiler: dict
    ticketlar: dict                 # bina_serial → [ticket satırı] (açık altyapı)
    kapanan_7g: set                 # (musteri_ozet, task_adi)
    kotu: set                       # musteri_ozet
    sozluk_anahtarlari: dict
    kesinti_h: dict = field(default_factory=dict)          # (il_k, ilce_k) → etkin bülten (EK-12.6)
    kesinti_kural: list = field(default_factory=list)
    boss_atamasi: int = 0
    yeni_satirlar: list = field(default_factory=list)
    yeni_olaylar: list = field(default_factory=list)
    kesinti_askilari: list = field(default_factory=list)   # [(is_no, neden)] → işlemin sonunda is_aski açılır


def _baglam(conn, aktarim_id, simdi, hz: Hazirlik) -> _Baglam:
    t = {}
    try:
        for r in conn.execute("SELECT id, bina_serial, konu, durum, acilis, olusturma FROM ticket WHERE durum IN "
                              f"({','.join('?' * len(TICKET_ACIK))}) AND konu IN ({','.join('?' * len(ALTYAPI_KONULARI))}) "
                              "AND bina_serial IS NOT NULL ORDER BY id", (*TICKET_ACIK, *ALTYAPI_KONULARI)):
            t.setdefault(r["bina_serial"], []).append(dict(r))
    except sqlite3.OperationalError:
        t = {}
    an = zaman.oku(simdi)
    y7 = zaman.metin(an - dt.timedelta(days=7))
    y30 = zaman.metin(an - dt.timedelta(days=30))
    kapanan = {(r[0], r[1]) for r in conn.execute(
        "SELECT musteri_ozet, task_adi FROM is_emri WHERE musteri_ozet IS NOT NULL AND durum IN ('cozuldu','kapandi') "
        "AND COALESCE(cozum_zamani, kapanis) >= ?", (y7,))}
    kotu = {r[0] for r in conn.execute(
        "SELECT DISTINCT musteri_ozet FROM is_emri WHERE musteri_ozet IS NOT NULL AND ilk_gorulme >= ? AND "
        "(evde_yok_sayisi > 0 OR teshis_sonucu IN ('cevapsiz','kapali','yanlis_no'))", (y30,))}
    return _Baglam(conn, aktarim_id, simdi, obek.harita(conn), kisi.boss_ekip_haritasi(conn), kisi.kisiler(conn),
                   t, kapanan, kotu, hz.sozluk_anahtarlari, kesinti.ilce_haritasi(conn),
                   kurallar.oku(conn, "kesinti_etkilenen"))


def _olay(b: _Baglam, is_no, tur, eski=None, yeni=None, notu=None):
    b.conn.execute(
        "INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, kullanici_id, kullanici_ad, tur, eski, yeni, notu, "
        "aktarim_id) VALUES (?,?,?,NULL,NULL,?,?,?,?,?)",
        (is_no, b.simdi, b.simdi, tur, json.dumps(eski, ensure_ascii=False) if eski is not None else None,
         json.dumps(yeni, ensure_ascii=False) if yeni is not None else None, notu, b.aktarim_id))


def _boss_kod(boss_durum) -> str:
    return BOSS_DURUM.get(ie.sade(boss_durum or ""), "acik")


def _altyapi_ticketi(b: _Baglam, bina_serial) -> dict | None:
    liste = b.ticketlar.get(bina_serial) if bina_serial else None
    return liste[0] if liste else None


def _ekip_eslesen(b: _Baglam, boss_ekip) -> int | None:
    return b.boss_h.get(ie.anahtar(boss_ekip)) if boss_ekip else None


def _boss_bekleyen(b: _Baglam, x: dict, atanan_id, randevu_bas, randevu_bit, eski_bekleyen=None,
                   islendi=None) -> str | None:
    """Giden kutusu (§3.4-4): bizdeki atama/randevu BOSS'takinden farklıysa ne işlenecek. "Talep Ulaşamama SMS"
    (EK-12.4) raporla doğrulanamaz: işlendi denene kadar kalır."""
    parca = []
    if atanan_id is not None:
        esl = _ekip_eslesen(b, x.get("boss_ekip"))
        if esl != atanan_id:
            parca.append("ekip")
    if randevu_bas and (randevu_bas, randevu_bit) != (x.get("boss_randevu_bas"), x.get("boss_randevu_bit")):
        parca.append("randevu")
    if eski_bekleyen and "aski" in eski_bekleyen.split(",") and not aski.boss_askida_mi(x.get("boss_durum")):
        parca.append("aski")
    if eski_bekleyen and "sms" in eski_bekleyen.split(",") and not islendi:
        parca.append("sms")
    return ",".join(parca) or None


def _yeni_durum(b: _Baglam, x: dict, triyaj: str | None, is_no: str | None = None) -> dict:
    """Yeni (ya da yeniden açılan) işin başlangıç durumu: §3.4 kuralları 1–3 + kural 11 (ticket)."""
    d = {"durum": "triyaj" if triyaj else "bekliyor", "atanan_id": None, "atama_kaynagi": None, "ticket_id": None,
         "askida_neden": None, "atama_zamani": None, "ilk_atama_zamani": None, "yolda_zamani": None,
         "sahada_zamani": None, "notu": None, "uyanma": None}
    t = _altyapi_ticketi(b, x.get("bina_serial"))
    if t is not None:
        d.update(durum="altyapi", ticket_id=t["id"], ilk_atama_zamani=b.simdi,
                 notu=f"Binada açık {t['konu']} ticket'ı var (#{t['id']}); teknisyen gönderilmez.")
        return d
    esl = _ekip_eslesen(b, x.get("boss_ekip"))
    if esl is not None:
        d.update(durum="atandi", atanan_id=esl, atama_kaynagi="boss", atama_zamani=b.simdi,
                 ilk_atama_zamani=b.simdi, notu="BOSS'ta atanmış")
        b.boss_atamasi += 1
        kod = _boss_kod(x.get("boss_durum"))
        if kod == "konum":
            d.update(durum="yolda", yolda_zamani=x.get("_konum_tarihi") or b.simdi)
        elif kod == "basladi":
            d.update(durum="sahada", yolda_zamani=x.get("_konum_tarihi"), sahada_zamani=x.get("_basla_tarihi") or b.simdi)
    kod = _boss_kod(x.get("boss_durum"))
    if kod == "askida" and d["durum"] in ("triyaj", "bekliyor", "randevulu", "atandi"):
        d.update(durum="askida", askida_neden=x.get("boss_aski_nedeni"))
    elif kod == "merkeze" and d["durum"] not in ("cozuldu", "altyapi"):
        d.update(durum="merkeze", askida_neden=x.get("_merkeze"))
    # EK-12.6: bülteni süren ilçede bağlantı/TV işi "Genel arıza — sevk etme" (uyanma bülten bitince ya da +24 s)
    bulten = b.kesinti_h.get((x.get("il_k"), x.get("ilce_k")))
    if bulten and d["durum"] in ("triyaj", "bekliyor", "randevulu", "atandi") \
            and kesinti.etkilenir_mi(b.kesinti_kural, x.get("task_adi") or ""):
        neden = kesinti.neden_metni(bulten)
        d.update(durum="askida", askida_neden=neden,
                 uyanma=zaman.metin(zaman.oku(b.simdi) + dt.timedelta(hours=kesinti.UYANMA_SAAT)),
                 notu="Genel arıza — sevk etme")
        b.kesinti_askilari.append((is_no or x["boss_task_no"], neden))
    return d


def _ekle(b: _Baglam, x: dict) -> None:
    obek_id = obek.haritadan(b.obek_h, x["il_k"], x["ilce_k"], x["mahalle_k"])
    triyaj = triyaj_hesapla(b.conn, il=x["il"], il_k=x["il_k"], ilce_k=x["ilce_k"], mahalle_k=x["mahalle_k"],
                            mahalle_kaynak=x["mahalle_kaynak"], obek_id=obek_id, obek_elle_id=None,
                            sozluk_anahtarlari=b.sozluk_anahtarlari)
    d = _yeni_durum(b, x, triyaj)
    kotu = 1 if x["musteri_ozet"] in b.kotu else 0
    satir = {**{k: x.get(k) for k in _SUTUNLAR_EKLE if k in x},
             "is_no": x["boss_task_no"], "kaynak": "boss", "obek_id": obek_id, "triyaj_nedeni": triyaj,
             "durum": d["durum"], "durum_zamani": b.simdi, "atanan_id": d["atanan_id"],
             "atama_kaynagi": d["atama_kaynagi"], "ticket_id": d["ticket_id"], "askida_neden": d["askida_neden"],
             "masa_vade": zaman.metin(zaman.oku(b.simdi) + dt.timedelta(minutes=45)) if x["serit"] == "BTK" and not kotu else None,
             "kotu_gecmis": kotu, "tekrar7g": 1 if (x["musteri_ozet"], x["task_adi"]) in b.kapanan_7g else 0,
             "ilk_gorulme": b.simdi, "gorulme_zamani": b.simdi, "ilk_atama_zamani": d["ilk_atama_zamani"],
             "atama_zamani": d["atama_zamani"], "yolda_zamani": d["yolda_zamani"], "sahada_zamani": d["sahada_zamani"],
             "son_gorulme": b.simdi, "son_aktarim_id": b.aktarim_id, "guncelleme": b.simdi,
             "boss_bekleyen": None, "oneri_teknik_id": None, "uyanma": d["uyanma"]}
    b.yeni_satirlar.append([satir.get(k) for k in _SUTUNLAR_EKLE])
    b.yeni_olaylar.append((satir["is_no"], b.simdi, b.simdi, "olustu", None,
                           json.dumps({"durum": d["durum"], "obek_id": obek_id, "triyaj": triyaj, "serit": x["serit"],
                                       "_surum": 1}, ensure_ascii=False), d["notu"], b.aktarim_id))


def _yenileri_yaz(b: _Baglam) -> None:
    """Yeni işler toplu yazılır (ilk aktarımda 437 satır: tek tek INSERT'ten belirgin hızlı)."""
    if not b.yeni_satirlar:
        return
    b.conn.executemany(f"INSERT INTO is_emri ({', '.join(_SUTUNLAR_EKLE)}) VALUES ({', '.join('?' * len(_SUTUNLAR_EKLE))})",
                       b.yeni_satirlar)
    b.conn.executemany("INSERT INTO is_emri_olay (is_no, zaman, kayit_zamani, kullanici_id, kullanici_ad, tur, eski, yeni, "
                       "notu, aktarim_id) VALUES (?,?,?,NULL,NULL,?,?,?,?,?)", b.yeni_olaylar)
    b.yeni_satirlar.clear()
    b.yeni_olaylar.clear()


def _alan_farki(eski: sqlite3.Row, yeni: dict, alanlar) -> tuple[dict, dict]:
    e, y = {}, {}
    for a in alanlar:
        if a not in yeni:
            continue
        ev, yv = eski[a], yeni[a]
        if isinstance(ev, float) or isinstance(yv, float):
            if ev is not None and yv is not None and abs(float(ev) - float(yv)) < 1e-9:
                continue
        if ev != yv:
            if a in KISISEL:
                e[a], y[a] = "değişti", "değişti"
            else:
                e[a], y[a] = ev, yv
    return e, y


def _guncelle(b: _Baglam, x: dict, r: sqlite3.Row, yeniden: bool) -> None:
    """Değişen ya da yeniden açılan iş: BOSS alanları yazılır; bizim alanlarımız korunur (§3.4)."""
    alanlar = {a: x.get(a) for a in RAPOR_ALANLARI}
    alanlar["boss_ozet"] = x["boss_ozet"]
    if not r["mahalle_elle"]:
        alanlar.update({a: x.get(a) for a in YER_ALANLARI})
    il_k = alanlar.get("il_k", r["il_k"])
    ilce_k = alanlar.get("ilce_k", r["ilce_k"])
    mk = alanlar.get("mahalle_k", r["mahalle_k"])
    obek_id = obek.haritadan(b.obek_h, il_k, ilce_k, mk)
    alanlar["obek_id"] = obek_id
    triyaj = triyaj_hesapla(b.conn, il=alanlar.get("il", r["il"]), il_k=il_k, ilce_k=ilce_k, mahalle_k=mk,
                            mahalle_kaynak=alanlar.get("mahalle_kaynak", r["mahalle_kaynak"]), obek_id=obek_id,
                            obek_elle_id=r["obek_elle_id"], eski_neden=r["triyaj_nedeni"],
                            sozluk_anahtarlari=b.sozluk_anahtarlari)
    alanlar["triyaj_nedeni"] = triyaj
    durum = r["durum"]
    notlar: list[str] = []
    ek: dict = {}
    kod = _boss_kod(x.get("boss_durum"))
    if yeniden:
        d = _yeni_durum(b, x, triyaj, r["is_no"])
        durum = d["durum"]
        ek.update(atanan_id=d["atanan_id"], atama_kaynagi=d["atama_kaynagi"], ticket_id=d["ticket_id"],
                  askida_neden=d["askida_neden"], atama_zamani=d["atama_zamani"],
                  ilk_atama_zamani=d["ilk_atama_zamani"], yolda_zamani=d["yolda_zamani"],
                  sahada_zamani=d["sahada_zamani"], randevu_bas=None, randevu_bit=None, randevu_teyitli=0,
                  kapanis=None, kapanis_nedeni=None, kapanis_kesin=1, cozum_zamani=None, gorulme_zamani=b.simdi,
                  acilma_sayisi=r["acilma_sayisi"] + 1, boss_kapanmadi=0, boss_islendi=None, uyanma=d["uyanma"],
                  sira=None, evde_yok_sayisi=0, teshis_sonucu=None, sonuc_kodu=None, evde_miydi=None,
                  oneri_teknik_id=r["atanan_id"], teknik_gordu=None, parca=None,
                  masa_vade=zaman.metin(zaman.oku(b.simdi) + dt.timedelta(minutes=45)) if x["serit"] == "BTK" else None)
        if d["notu"]:
            notlar.append(d["notu"])
    else:
        atanan = r["atanan_id"]
        # 3) ekip eşleşmesi: atanmamış iş BOSS'ta tanıdığımız bir teknisyene atanmışsa
        esl = _ekip_eslesen(b, x.get("boss_ekip"))
        if atanan is None and esl is not None and durum in akis.ATANMADI:
            durum = "atandi"
            atanan = esl
            ek.update(atanan_id=esl, atama_kaynagi="boss", atama_zamani=b.simdi,
                      ilk_atama_zamani=r["ilk_atama_zamani"] or b.simdi)
            b.boss_atamasi += 1
            notlar.append("BOSS'ta atanmış")
        # 1) ileri kuralı: yalnız atanmış işte, geri gitmez
        if atanan is not None and durum in akis.ILERI_SIRA:
            hedef = {"konum": "yolda", "basladi": "sahada"}.get(kod)
            if hedef and akis.ILERI_SIRA[hedef] > akis.ILERI_SIRA[durum]:
                if hedef == "yolda" and not r["yolda_zamani"]:
                    ek["yolda_zamani"] = x.get("_konum_tarihi") or b.simdi
                if hedef == "sahada":
                    ek.setdefault("yolda_zamani", r["yolda_zamani"] or x.get("_konum_tarihi"))
                    ek["sahada_zamani"] = r["sahada_zamani"] or x.get("_basla_tarihi") or b.simdi
                durum = hedef
        # 2) istisnalar; bizde ulaşılamadı / altyapı / askı bilgisi korunur
        if kod == "askida" and durum in ("triyaj", "bekliyor", "randevulu", "atandi"):
            durum = "askida"
            ek["askida_neden"] = x.get("boss_aski_nedeni")
            notlar.append("BOSS'ta askıya alındı")
        elif kod == "merkeze" and durum not in ("cozuldu", "altyapi", "ulasilamadi", "askida", "merkeze"):
            durum = "merkeze"
            ek["askida_neden"] = x.get("_merkeze")
            notlar.append("BOSS'ta merkeze gönderildi")
        elif kod != "askida" and durum == "askida" and _askiya_sistem_mi_aldi(b.conn, r["is_no"]):
            durum = "bekliyor" if not triyaj else "triyaj"
            ek.update(askida_neden=None, uyanma=None)
            notlar.append("BOSS'ta askıdan çıktı")
        # durum bekliyor ↔ triyaj (öbek/mahalle belli oldu ya da kayboldu)
        if durum == "bekliyor" and triyaj:
            durum = "triyaj"
        elif durum == "triyaj" and not triyaj:
            durum = "bekliyor"
        # 7) çelişki: bizde çözüldü, iki raporda BOSS'ta hâlâ açık
        if durum == "cozuldu" and r["cozum_zamani"] and r["son_gorulme"] and r["son_gorulme"] >= r["cozum_zamani"]:
            ek["boss_kapanmadi"] = 1
        # giden kutusu yeniden hesaplanır; BOSS eşleşirse bayrak kalkar ("BOSS'ta doğrulandı")
        bekleyen = _boss_bekleyen(b, x, atanan if ek.get("atama_kaynagi") != "boss" else None,
                                  r["randevu_bas"], r["randevu_bit"], r["boss_bekleyen"], r["boss_islendi"])
        if r["boss_bekleyen"] and not bekleyen:
            notlar.append("BOSS'ta doğrulandı")
            ek["boss_islendi"] = r["boss_islendi"] or b.simdi
        ek["boss_bekleyen"] = bekleyen
    alanlar.update(ek)
    alanlar["durum"] = durum
    alanlar["son_gorulme"] = b.simdi
    alanlar["son_aktarim_id"] = b.aktarim_id
    alanlar["guncelleme"] = b.simdi
    durum_degisti = durum != r["durum"]
    operasyon_degisti = durum_degisti or any(
        a in ek and ek[a] != r[a] for a in ("atanan_id", "ticket_id", "randevu_bas"))
    if durum_degisti:
        alanlar["durum_zamani"] = b.simdi
    set_ = ", ".join(f"{a}=?" for a in alanlar)
    b.conn.execute(f"UPDATE is_emri SET {set_}, surum = surum + ? WHERE is_no = ?",
                   (*alanlar.values(), 1 if operasyon_degisti else 0, r["is_no"]))
    eski, yeni = _alan_farki(r, {a: v for a, v in alanlar.items() if a not in ("son_gorulme", "son_aktarim_id",
                                                                             "guncelleme", "durum_zamani", "boss_ozet")},
                             [a for a in alanlar if a not in ("son_gorulme", "son_aktarim_id", "guncelleme",
                                                              "durum_zamani", "boss_ozet")])
    yeni["_surum"] = r["surum"] + (1 if operasyon_degisti else 0)
    _olay(b, r["is_no"], "yeniden_acildi" if yeniden else "aktarim_degisti", eski, yeni,
          notu="; ".join(notlar) or None)


def _askiya_sistem_mi_aldi(conn, is_no) -> bool:
    """Son askıya alma sistemden (rapordan) mı geldi: operatörün elle askısı rapora bırakılmaz."""
    if conn.execute("SELECT 1 FROM is_aski WHERE is_no=? AND bitis IS NULL AND kaynak='elle'", (is_no,)).fetchone():
        return False
    r = conn.execute("SELECT kullanici_id FROM is_emri_olay WHERE is_no=? AND yeni LIKE '%\"durum\": \"askida\"%' "
                     "ORDER BY id DESC LIMIT 1", (is_no,)).fetchone()
    return r is None or r[0] is None


def _kapat(b: _Baglam, r: sqlite3.Row) -> None:
    neden = "cozuldu_dogrulandi" if r["durum"] == "cozuldu" else "boss_listeden_dustu"
    b.conn.execute("UPDATE is_emri SET durum='kapandi', durum_zamani=?, kapanis=?, kapanis_kesin=0, kapanis_nedeni=?, "
                   "boss_kapanmadi=0, surum=surum+1, guncelleme=? WHERE is_no=?",
                   (b.simdi, b.simdi, neden, b.simdi, r["is_no"]))
    aski.kapat(b.conn, r["is_no"], b.simdi)
    _olay(b, r["is_no"], "kayboldu", {"durum": r["durum"]},
          {"durum": "kapandi", "kapanis_nedeni": neden, "_surum": r["surum"] + 1},
          notu="BOSS'ta kapandı (çözüm doğrulandı)" if neden == "cozuldu_dogrulandi" else "BOSS listesinden düştü")


def _degismeyen(b: _Baglam, liste) -> None:
    b.conn.executemany("UPDATE is_emri SET son_gorulme=?, son_aktarim_id=? WHERE is_no=?",
                       [(b.simdi, b.aktarim_id, r["is_no"]) for _, r in liste])
    # 7) çelişki bayrağı değişmeyen işte de: bizde çözüldü, BOSS ikinci raporda da açık
    for _, r in liste:
        if r["durum"] == "cozuldu" and r["cozum_zamani"] and r["son_gorulme"] and r["son_gorulme"] >= r["cozum_zamani"] \
                and not r["boss_kapanmadi"]:
            b.conn.execute("UPDATE is_emri SET boss_kapanmadi=1 WHERE is_no=?", (r["is_no"],))


def _uygula(conn: sqlite3.Connection, aktarim_id: int, hz: Hazirlik, fark: Fark, tam_kapsam: bool,
            dosya_zamani: str | None) -> dict:
    """UYGULA: tek işlem. Çağıran yedeği aldı ve kilidi tutuyor."""
    t0 = time.perf_counter()
    simdi = zaman.metin()
    with islem(conn):
        b = _baglam(conn, aktarim_id, simdi, hz)
        for x in fark.yeni:
            _ekle(b, x)
        _yenileri_yaz(b)
        for x, r in fark.yeniden_acilan:
            _guncelle(b, x, r, yeniden=True)
        for x, r in fark.degisen:
            _guncelle(b, x, r, yeniden=False)
        _degismeyen(b, fark.degismeyen)
        for no, neden in b.kesinti_askilari:           # EK-12.6: genel arıza askısı (bizden; saat kuraldan)
            aski.ac(conn, no, simdi, neden, "elle")
        kapanan = 0
        if tam_kapsam:
            for r in fark.kaybolan:
                _kapat(b, r)
                kapanan += 1
        # EK-3: askı aralıkları (rapor zamanı = dosyanın indirildiği an; yoksa aktarım anı)
        is_no_haritasi = {r[0]: r[1] for r in conn.execute("SELECT boss_task_no, is_no FROM is_emri "
                                                           "WHERE boss_task_no IS NOT NULL")}
        rapor_zamani = min(dosya_zamani or simdi, simdi)
        aski_sonuc = aski.aktarim_uzlas(conn, [(is_no_haritasi.get(x["boss_task_no"], x["boss_task_no"]),
                                                x.get("boss_durum"), x.get("boss_aski_nedeni")) for x in hz.isler],
                                        rapor_zamani)
        # sözlük: raporda görülen yeni mahalleler
        ilce_h = sozluk.ilce_haritasi(conn)
        yeni_mahalle = 0
        for il_k, ilce_k, mk, il, ilce, ad in hz.yeni_mahalleler:
            yeni_mahalle += sozluk._mahalle_ekle(conn, ilce_h, il, ilce, ad, None, None, "rapor", simdi)
        if yeni_mahalle:
            sozluk.onbellegi_bosalt()
        conn.execute("INSERT OR IGNORE INTO ayar(anahtar, deger) VALUES ('ilk_aktarim', ?)", (simdi,))
        sayi = _anlik_sayilar(conn, simdi)
        conn.execute("INSERT INTO takip_anlik (zaman, aktarim_id, acik, asan24, btk_asan48, atanmamis, altyapi) "
                     "VALUES (?,?,?,?,?,?,?)", (simdi, aktarim_id, sayi["acik"], sayi["asan24"], sayi["btk48"],
                                                sayi["atanmamis"], sayi["altyapi"]))
        kontrol = conn.execute("SELECT COUNT(*) FROM is_emri WHERE durum='triyaj'").fetchone()[0]
        yazma_sn = round(time.perf_counter() - t0, 3)
        ozet = {**hz.ozet, "yazma_sn": yazma_sn, "aski": aski_sonuc, "yeni_mahalle": yeni_mahalle}
        s = fark.sayilar()
        conn.execute(
            "UPDATE ie_aktarim SET durum='uygulandi', bitis=?, tam_kapsam=?, satir=?, cikarilan=?, is_sayisi=?, "
            "yeni=?, degisen=?, kaybolan=?, yeniden_acilan=?, degismeyen=?, kontrol=?, boss_atamasi=?, ozet=?, "
            "rapor_en_yeni=?, hata=NULL WHERE id=?",
            (simdi, 1 if tam_kapsam else 0, hz.ozet["satir"], hz.ozet["cikarilan"], hz.ozet["is_sayisi"],
             s["yeni"], s["degisen"], kapanan if tam_kapsam else 0, s["yeniden_acilan"], s["degismeyen"], kontrol,
             b.boss_atamasi, json.dumps(ozet, ensure_ascii=False), hz.rapor_en_yeni, aktarim_id))
    return {"yazma_sn": yazma_sn, "kontrol": kontrol, "boss_atamasi": b.boss_atamasi, "aski": aski_sonuc,
            "kapanan": kapanan}


def _anlik_sayilar(conn, simdi: str) -> dict:
    y48 = zaman.metin(zaman.oku(simdi) - dt.timedelta(hours=48))
    r = conn.execute(
        "SELECT COUNT(*), SUM(son24 < ?), SUM(serit='BTK' AND acilis < ?), "
        "SUM(durum IN ('triyaj','bekliyor','randevulu')), SUM(durum='altyapi') "
        "FROM is_emri WHERE durum NOT IN ('cozuldu','kapandi')", (simdi, y48)).fetchone()
    return {"acik": r[0] or 0, "asan24": r[1] or 0, "btk48": r[2] or 0, "atanmamis": r[3] or 0, "altyapi": r[4] or 0}


def _sonrasi(conn: sqlite3.Connection) -> None:
    """COMMIT'ten sonra, işlem dışında: öneriler, saklama, ticket ve uyanma denetimleri."""
    from . import saklama, siralama
    try:
        akis.ticket_denetimi(conn)
        akis.uyananlari_isle(conn, zaman.simdi())
        sozluk.isit(conn)
        siralama.oneri_hesapla(conn)
        saklama.uygula(conn, zaman.simdi())
    except Exception:          # noqa: BLE001 — aktarım uygulandı; yan işler bir sonraki turda tekrar denenir
        import logging
        logging.getLogger("operasyon.aktarim").exception("Aktarım sonrası işler tamamlanamadı")


# ----------------------------------------------------------------------------- dış yüz
def aktar(conn_fabrikasi, veri: bytes, dosya_adi: str, dosya_zamani, k: dict | None,
          yontem: str = "surukle") -> dict:
    """Spec §4 1–9. Dönüş: 200 gövdesi. Hata → V2Hata (409 onay_gerekli / aktarim_suruyor, 413, 422, 503)."""
    if len(veri) > AZAMI_BOYUT:
        raise V2Hata("Dosya çok büyük (en çok 25 MB).", kod="buyuk_dosya", durum=413)
    sha = hashlib.sha256(veri).hexdigest()
    dosya_zamani = dosya_zamani_normal(dosya_zamani)
    conn = conn_fabrikasi()
    try:
        ayni = conn.execute("SELECT id, bitis FROM ie_aktarim WHERE dosya_sha256=? AND durum='uygulandi' "
                            "ORDER BY id DESC LIMIT 1", (sha,)).fetchone()
        if ayni:
            return {"ayni_dosya": True, "aktarim_id": ayni["id"], "zaman": ayni["bitis"],
                    "mesaj": f"Bu dosya {zaman.saat_dk(ayni['bitis'])}'de zaten yüklenmişti. Hiçbir şey değişmedi."}
        if not _KILIT.acquire(blocking=False):
            raise Catisma("Şu an başka bir rapor işleniyor. Bir dakika sonra deneyin.", kod="aktarim_suruyor")
        # İçe aktarım işlemci yoğundur (openpyxl, pandas): başka isteklerin GIL için sıra beklemesi kısalsın diye
        # aktarım süresince geçiş aralığı 5 ms → 0,5 ms (spec §5.6: aktarım sürerken /api/saglik < 300 ms).
        eski_aralik = sys.getswitchinterval()
        sys.setswitchinterval(min(eski_aralik, 0.0005))
        try:
            baslama = zaman.metin()
            with islem(conn):
                aid = conn.execute(
                    "INSERT INTO ie_aktarim (kaynak, yontem, dosya_adi, dosya_sha256, dosya_zamani, yukleyen_id, "
                    "yukleyen_ad, baslama, durum) VALUES ('boss_teknik_task', ?, ?, ?, ?, ?, ?, ?, 'isleniyor')",
                    (yontem, str(dosya_adi or "rapor.xlsx")[:200], sha, dosya_zamani, (k or {}).get("id"),
                     (k or {}).get("ad"), baslama)).lastrowid
            try:
                (gelen_dizini() / f"{sha}.xlsx").write_bytes(veri)
            except OSError:
                pass
            return _isle(conn, aid, veri, dosya_zamani, mod=None)
        finally:
            sys.setswitchinterval(eski_aralik)
            _KILIT.release()
    finally:
        conn.close()


def _hata_yaz(conn, aid: int, mesaj: str) -> None:
    try:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        with islem(conn):
            conn.execute("UPDATE ie_aktarim SET durum='hata', bitis=?, hata=? WHERE id=?", (zaman.metin(), mesaj[:500], aid))
    except sqlite3.Error:
        pass


def _isle(conn: sqlite3.Connection, aid: int, veri: bytes, dosya_zamani: str | None, mod: str | None) -> dict:
    t0 = time.perf_counter()
    try:
        df = rapor_tablosu(veri)
        hz = hazirla(conn, df)
    except V2Hata as e:
        _hata_yaz(conn, aid, e.mesaj)
        raise
    except Exception as e:     # noqa: BLE001
        _hata_yaz(conn, aid, f"Rapor okunamadı: {type(e).__name__}")
        raise V2Hata("Rapor okunamadı; hiçbir şey değişmedi.", kod="rapor_okunamadi", durum=422)
    fark = fark_hesapla(conn, hz.isler)
    nedenler, bilgi = bekci(conn, fark, dosya_zamani, hz.rapor_en_yeni)
    if mod is None and nedenler:
        mesaj = bekci_mesaji(nedenler, fark, bilgi)
        with islem(conn):
            conn.execute("UPDATE ie_aktarim SET durum='onay_bekliyor', onay_nedeni=?, rapor_en_yeni=?, satir=?, "
                         "cikarilan=?, is_sayisi=?, yeni=?, degisen=?, kaybolan=?, yeniden_acilan=?, degismeyen=?, "
                         "ozet=? WHERE id=?",
                         (json.dumps(nedenler), hz.rapor_en_yeni, hz.ozet["satir"], hz.ozet["cikarilan"],
                          hz.ozet["is_sayisi"], *fark.sayilar().values(),
                          json.dumps({**hz.ozet, "mesaj": mesaj, **bilgi}, ensure_ascii=False), aid))
        try:
            (gelen_dizini() / f"{aid}.fark.json").write_text(
                json.dumps({"aktarim_id": aid, "sayilar": fark.sayilar(), "nedenler": nedenler, **fark.numaralar()},
                           ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        raise Catisma(mesaj, kod="onay_gerekli", aktarim_id=aid, fark=fark.sayilar(), nedenler=nedenler, **bilgi)
    tam_kapsam = True
    if mod is not None:
        onceki = conn.execute("SELECT onay_nedeni FROM ie_aktarim WHERE id=?", (aid,)).fetchone()
        onceki_nedenler = json.loads(onceki[0] or "[]") if onceki else []
        tam_kapsam = mod == "tam" and "eski_rapor" not in onceki_nedenler and "eski_rapor" not in nedenler
    # 7) YEDEK
    try:
        yedek = aktarim_yedegi(_db_yolu(conn))
    except Exception:          # noqa: BLE001
        _hata_yaz(conn, aid, "Güvenlik yedeği alınamadı")
        raise V2Hata("Güvenlik yedeği alınamadı; hiçbir şey değiştirilmedi. Diskte yer var mı?",
                     kod="yedek_alinamadi", durum=503)
    with islem(conn):
        conn.execute("UPDATE ie_aktarim SET yedek_yolu=? WHERE id=?", (yedek.name, aid))
    # 8) UYGULA
    try:
        sonuc = _uygula(conn, aid, hz, fark, tam_kapsam, dosya_zamani)
    except sqlite3.IntegrityError as e:
        if "ux_aktarim_sha" in str(e) or "dosya_sha256" in str(e):
            _hata_yaz(conn, aid, "Aynı dosya bu arada uygulandı")
            ayni = conn.execute("SELECT id, bitis FROM ie_aktarim WHERE dosya_sha256=(SELECT dosya_sha256 FROM "
                                "ie_aktarim WHERE id=?) AND durum='uygulandi'", (aid,)).fetchone()
            return {"ayni_dosya": True, "aktarim_id": ayni["id"] if ayni else aid, "zaman": ayni["bitis"] if ayni else None}
        _hata_yaz(conn, aid, f"Yazılamadı: {type(e).__name__}")
        raise
    except Exception as e:     # noqa: BLE001
        _hata_yaz(conn, aid, f"Yazılamadı: {type(e).__name__}")
        raise
    _sonrasi(conn)
    s = fark.sayilar()
    if not tam_kapsam:
        s["kaybolan"] = 0
    return {"aktarim_id": aid, "fark": s,
            "cikarilan": {"kurulum": hz.ozet["kurulum"], "ikinci_donanim": hz.ozet["ikinci_donanim"],
                          "istisna_tutulan": hz.ozet["istisna_tutulan"], "satir": hz.ozet["satir"],
                          "adlar": hz.ozet["cikarilan_adlar"]},
            "kontrol": sonuc["kontrol"], "boss_atamasi": sonuc["boss_atamasi"],
            "sure_sn": round(time.perf_counter() - t0, 3), "yazma_sn": sonuc["yazma_sn"], "yedek": yedek.name,
            "tam_kapsam": tam_kapsam, "aski": sonuc["aski"], "lokasyon": hz.ozet["lokasyon"]}


def uygula(conn_fabrikasi, aktarim_id: int, mod: str, k: dict | None) -> dict:
    """Onay bekleyen raporu uygular: fark YENİDEN hesaplanır; eski raporda ``mod`` zorla 'kismi'."""
    if mod not in ("tam", "kismi"):
        raise Gecersiz("Mod 'tam' ya da 'kismi' olmalı.", kod="alan_eksik")
    conn = conn_fabrikasi()
    try:
        r = conn.execute("SELECT * FROM ie_aktarim WHERE id=?", (aktarim_id,)).fetchone()
        if r is None or r["durum"] != "onay_bekliyor":
            raise Catisma("Bu rapor onay beklemiyor.", kod="durum_gecersiz")
        ham = gelen_dizini() / f"{r['dosya_sha256']}.xlsx"
        if not ham.exists():
            raise Catisma("Raporun dosyası artık yok; raporu yeniden bırakın.", kod="durum_gecersiz")
        if not _KILIT.acquire(blocking=False):
            raise Catisma("Şu an başka bir rapor işleniyor. Bir dakika sonra deneyin.", kod="aktarim_suruyor")
        try:
            ayni = conn.execute("SELECT id, bitis FROM ie_aktarim WHERE dosya_sha256=? AND durum='uygulandi'",
                                (r["dosya_sha256"],)).fetchone()
            if ayni:
                with islem(conn):
                    conn.execute("UPDATE ie_aktarim SET durum='vazgecildi', bitis=? WHERE id=?", (zaman.metin(), aktarim_id))
                return {"ayni_dosya": True, "aktarim_id": ayni["id"], "zaman": ayni["bitis"]}
            with islem(conn):
                conn.execute("UPDATE ie_aktarim SET yukleyen_id=COALESCE(yukleyen_id, ?), "
                             "yukleyen_ad=COALESCE(yukleyen_ad, ?) WHERE id=?",
                             ((k or {}).get("id"), (k or {}).get("ad"), aktarim_id))
            eski_aralik = sys.getswitchinterval()
            sys.setswitchinterval(min(eski_aralik, 0.0005))
            try:
                sonuc = _isle(conn, aktarim_id, ham.read_bytes(), r["dosya_zamani"], mod=mod)
            finally:
                sys.setswitchinterval(eski_aralik)
            (gelen_dizini() / f"{aktarim_id}.fark.json").unlink(missing_ok=True)
            return sonuc
        finally:
            _KILIT.release()
    finally:
        conn.close()


def vazgec(conn_fabrikasi, aktarim_id: int, k: dict | None) -> dict:
    conn = conn_fabrikasi()
    try:
        with islem(conn):
            n = conn.execute("UPDATE ie_aktarim SET durum='vazgecildi', bitis=? WHERE id=? AND durum='onay_bekliyor'",
                             (zaman.metin(), aktarim_id)).rowcount
        if not n:
            raise Catisma("Bu rapor onay beklemiyor.", kod="durum_gecersiz")
        (gelen_dizini() / f"{aktarim_id}.fark.json").unlink(missing_ok=True)
        return {"aktarim_id": aktarim_id, "durum": "vazgecildi"}
    finally:
        conn.close()


def gecmis(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM ie_aktarim ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 200)),)):
        out.append({"id": r["id"], "zaman": r["bitis"] or r["baslama"], "yukleyen": r["yukleyen_ad"],
                    "dosya_adi": r["dosya_adi"], "yontem": r["yontem"], "is_sayisi": r["is_sayisi"], "yeni": r["yeni"],
                    "degisen": r["degisen"], "kaybolan": r["kaybolan"], "yeniden_acilan": r["yeniden_acilan"],
                    "degismeyen": r["degismeyen"], "cikarilan": r["cikarilan"], "durum": r["durum"],
                    "tam_kapsam": bool(r["tam_kapsam"]), "yedek": r["yedek_yolu"], "hata": r["hata"]})
    return out


def son_uygulanan(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM ie_aktarim WHERE durum='uygulandi' ORDER BY id DESC LIMIT 1").fetchone()


def onay_bekleyenler(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM ie_aktarim WHERE durum='onay_bekliyor' ORDER BY id DESC LIMIT 5"):
        try:
            o = json.loads(r["ozet"] or "{}")
        except ValueError:
            o = {}
        out.append({"aktarim_id": r["id"], "zaman": r["baslama"], "dosya_adi": r["dosya_adi"], "yontem": r["yontem"],
                    "nedenler": json.loads(r["onay_nedeni"] or "[]"),
                    "fark": {"yeni": r["yeni"] or 0, "degisen": r["degisen"] or 0, "kaybolan": r["kaybolan"] or 0,
                             "yeniden_acilan": r["yeniden_acilan"] or 0, "degismeyen": r["degismeyen"] or 0},
                    "mesaj": o.get("mesaj", "")})
    return out
