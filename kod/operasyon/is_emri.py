"""BOSS "Teknik Task Detay Raporu"nu makro gibi hazırlar.

1. Temizle: 'Task Adı' (E sütunu) içinde KURULUM ya da 2. DONANIM geçen satırlar çıkar.
2. Mahalle: 'Adres' (G) içinden, 'İl' (M) + 'İlçe' (N) kapsamında çözülür. Anahtar
   (il, ilçe, mahalle) olduğu için Nilüfer/Dumlupınar ile Osmangazi/Dumlupınar ayrı kalır.
3. Konum: Lokasyon → bina · adresteki BN kodu → bina · adresin başındaki site adı → bina
   · bulunamazsa mahalle merkezi.
4. Öbek: kullanıcının tanımı (operasyon/obekler.json): mahalle → öbek adı.

Komut satırı:
    python -m operasyon.is_emri RAPOR.xlsx            → RAPOR_hazir.xlsx (aynı klasöre)
    python -m operasyon.is_emri OBEK_TABLOSU.xlsx     → öbek tanımlarını günceller
      (hazır dosyanın "Mahalleler" sayfasında Öbek sütununu doldurup kaydedilen dosya)
"""
from __future__ import annotations

import difflib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import yollar

MASTER = yollar.VERI / "master" / "bina_master.csv"
MAHALLE_LISTESI = yollar.VERI / "ref" / "BursaStateList.xlsx"
MAHALLE_ONBELLEK = yollar.VERI / "ref" / "mahalle_listesi.json"     # BursaStateList'in hızlı kopyası
ILCE_SINIRLARI = yollar.VERI / "ref" / "osm_ilce.geojson"
# Çalışma verisi (git dışı): öbek tanımları ve yüklenen raporlar. OPERASYON_OBEK / OPERASYON_VERI önce gelir.
OBEK_DOSYASI = yollar.CALISMA_OPERASYON / "obekler.json"
VERI_DIZINI = yollar.CALISMA_OPERASYON / "veri"

# 'Task Adı' içinde bunlardan biri geçen satır çıkarılır (büyük/küçük harf ve Türkçe harf duyarsız;
# noktalama boşluk sayılır: "2.Donanım", "2. DONANIM" → "2 DONANIM"; "12.Donanım" sayılmaz)
CIKARILACAK = {"KURULUM": r"KURULUM", "2 DONANIM": r"(?<![0-9])2 ?DONANIM"}
# C5 / OT §3.1: bu adlar çıkarma kuralından ÖNCE denetlenir ve iş KALIR (sade() biçiminde).
# Uygulamada ayar.filtre_istisnalari'ndan okunur; komut satırı bu varsayılanı kullanır.
VARSAYILAN_ISTISNALAR = ("KURULUM TASKI UREMEMIS",)

SUTUNLAR = {"task": "Task Adı", "adres": "Adres", "il": "İl", "ilce": "İlçe", "lokasyon": "Lokasyon"}
BOLGE_ILLERI = {"BURSA", "YALOVA"}     # bu illerin dışındaki iş "il bölge dışı" diye kontrole düşer

_HARF = "A-Za-z0-9ÇĞİIÖŞÜÂÎÛçğıiöşüâîû\u0307"
_TR = str.maketrans("ÇĞİÖŞÜÂÎÛ", "CGIOSUAIU")
_ISARET = {"MAHALLESI", "MAHALLE", "MAHALESI", "MAH", "MH"}
_GURULTU = {"BBK"}          # "Özden Bbk.Mah.(Kadıköy) Mah." → Özden
# Mahalle adının parçası olamayacak kelimeler (adres içinde mahalleden önce gelen site/apartman sözleri)
_DUR = {"APT", "APARTMANI", "SIT", "SITESI", "SITE", "BLK", "BLOK", "BLOGU", "EVLERI", "KONUTLARI", "KONAKLARI",
        "RESIDENCE", "RESIDANCE", "REZIDANS", "TOKI", "ADA", "PARSEL", "ETAP", "NO", "D", "SK", "SOK", "SOKAK",
        "CD", "CAD", "CADDESI", "BLV", "BULVARI", "KAT", "DAIRE", "PARK", "PLAZA", "IS", "MERKEZI", "SEMTI"}
BIR_BINA_YARICAP_M = 300     # aynı site adlı adaylar bu yarıçapta ise tek konum sayılır


# --------------------------------------------------------------------------- metin
def buyuk(s) -> str:
    return str(s).replace("\u0307", "").replace("i", "İ").replace("ı", "I").upper()


def sade(s) -> str:
    """Türkçe büyük harf → ASCII büyük harf; harf/rakam dışı her şey tek boşluk."""
    return re.sub(r"[^A-Z0-9]+", " ", buyuk(s).translate(_TR)).strip()


def anahtar(s) -> str:
    """Boşluksuz karşılaştırma anahtarı: 'Yüzüncüyıl', 'YÜZÜNCÜ YIL' → 'YUZUNCUYIL'."""
    return sade(s).replace(" ", "")


def baslik(s) -> str:
    """Türkçe baş harfler büyük: 'ADNAN MENDERES' → 'Adnan Menderes'."""
    out = []
    for w in str(s).replace("\u0307", "").split():
        bas = w[:1].replace("i", "İ").replace("ı", "I").upper()
        out.append(bas + w[1:].replace("I", "ı").replace("İ", "i").lower())
    return " ".join(out)


def mahalle_eki_sil(s) -> str:
    return re.sub(r"\s*\b(MAHALLESİ|Mahallesi|MAH\.?|Mah\.?|MH\.?|Mh\.?)$", "", str(s).strip()).strip()


def ilce_anahtari(il, ilce) -> tuple[str, str]:
    """('Yalova', 'Yalova Merkez') ve ('Yalova', 'Merkez') aynı anahtara iner."""
    ik, ck = anahtar(il), anahtar(ilce)
    if ck.startswith(ik) and len(ck) > len(ik):
        ck = ck[len(ik):]
    return ik, ck


def istisna_mi(task_adi, istisnalar=VARSAYILAN_ISTISNALAR) -> bool:
    """C5: 'Kurulum Taskı Ürememiş' mevcut müşteride KALIR (çıkarma kuralından önce denetlenir)."""
    s = sade(task_adi)
    return any(sade(i) and sade(i) in s for i in (istisnalar or ()))


def cikarilacak_mi(task_adi, istisnalar=VARSAYILAN_ISTISNALAR) -> str | None:
    """Çıkarılma nedeni ('KURULUM' / '2 DONANIM') ya da None."""
    if istisna_mi(task_adi, istisnalar):
        return None
    s = sade(task_adi)
    for ad, kalip in CIKARILACAK.items():
        if re.search(kalip, s):
            return ad
    return None


def _koordinat(s) -> tuple[float | None, float | None]:
    sayi = re.findall(r"-?\d+(?:[.,]\d+)?", str(s or ""))
    if len(sayi) >= 2:
        lat, lon = (float(x.replace(",", ".")) for x in sayi[:2])
        if 35 < lat < 43 and 25 < lon < 45:
            return lat, lon
    return None, None


# --------------------------------------------------------------------------- sözlük
@dataclass
class Mahalle:
    il: str
    ilce: str
    ad: str
    lat: float | None = None
    lon: float | None = None


@dataclass
class Sozluk:
    """(il, ilçe) → mahalle adları + bina arama tabloları. Bir kez yüklenir, her raporda kullanılır."""
    mah: dict = field(default_factory=dict)          # (il_k, ilce_k) -> {mah_k: Mahalle}
    maks_kelime: int = 1
    bina: pd.DataFrame | None = None
    loc: dict = field(default_factory=dict)          # location_id -> satır no
    serial: dict = field(default_factory=dict)       # bina_serial -> satır no
    site: dict = field(default_factory=dict)         # anahtar(site adı) -> [satır no]
    tam_liste: set = field(default_factory=set)      # mahalle listesi eksiksiz olan (il_k, ilce_k)
    ilce_merkez: dict = field(default_factory=dict)  # anahtar(ilçe adı) -> (lat, lon)
    a: dict = field(default_factory=dict)            # bina sütunları numpy dizisi olarak (hızlı süzme)

    @classmethod
    def yukle(cls, master: Path = MASTER, liste: Path = MAHALLE_LISTESI) -> "Sozluk":
        m = pd.read_csv(master, dtype=str, usecols=[
            "bina_serial", "location_id", "site_adi_crm", "blok_adi_crm", "ad", "kapi_no",
            "mahalle", "ilce", "il", "lat", "lon", "site_grup"])
        s = cls.kur(m, _mahalle_listesi(liste))
        # 3) İlçe merkezleri (mahalle konumu bilinmeyen işler için kaba konum)
        if ILCE_SINIRLARI.exists():
            from shapely.geometry import shape
            for f in json.loads(ILCE_SINIRLARI.read_text(encoding="utf-8"))["features"]:
                p = shape(f["geometry"]).representative_point()
                s.ilce_merkez[anahtar(f["properties"]["ad"])] = (round(p.y, 6), round(p.x, 6))
        return s

    @classmethod
    def kur(cls, m: pd.DataFrame, liste_satirlari, ek_mahalleler=()) -> "Sozluk":
        """Bina tablosu (CSV ya da veritabanı) + mahalle listesi → sözlük.

        m: bina_serial, location_id, site_adi_crm, blok_adi_crm, ad, kapi_no, mahalle, ilce, il, lat, lon,
        site_grup sütunları. Aynı location_id'de SON satır kazanır (veritabanı pasifleri öne dizer).
        liste_satirlari: [(il, ilçe, mahalle, lat, lon)] — bu ilçelerin listesi eksiksiz sayılır.
        ek_mahalleler: [(il, ilçe, mahalle, lat, lon)] — listeyi tamamlamayan diğer kaynaklar (öbek, rapor, elle).
        """
        s, bina_mahalleleri = cls.bina_kur(m)
        return s.mahalleleri_kur(liste_satirlari, bina_mahalleleri, ek_mahalleler)

    @classmethod
    def bina_kur(cls, m: pd.DataFrame) -> tuple["Sozluk", list[tuple]]:
        """Pahalı yarı (≈0,6 sn / 19.706 bina): bina arama tabloları + binaların mahalleleri. Bina tablosu
        değişmedikçe yeniden kurulmaz (v2 ``sozluk.sozluk_db`` bunu önbellekte tutar; mahalle eklenince yalnız
        ``mahalleleri_kur`` koşar)."""
        s = cls()
        m = m.copy()
        m["lat"] = pd.to_numeric(m["lat"], errors="coerce")
        m["lon"] = pd.to_numeric(m["lon"], errors="coerce")
        m = m.reset_index(drop=True)
        m["_ik"], m["_ck"] = zip(*[ilce_anahtari(a, b) for a, b in zip(m["il"], m["ilce"])]) if len(m) else ((), ())
        m["_mk"] = m["mahalle"].map(lambda x: anahtar(mahalle_eki_sil(x)) if isinstance(x, str) else "")
        s.bina = m
        s.loc = {v: i for i, v in m["location_id"].dropna().items()}
        s.serial = {v: i for i, v in m["bina_serial"].dropna().items()}
        for kol in ("site_adi_crm", "blok_adi_crm"):
            for i, v in m[kol].dropna().items():
                k = anahtar(v)
                if len(k) >= 4:
                    s.site.setdefault(k, set()).add(i)
        s.site = {k: sorted(v) for k, v in s.site.items()}
        s.a = {k: m[k].to_numpy() for k in ("_ik", "_ck", "_mk", "lat", "lon", "site_grup", "bina_serial")}
        s.a["_kapi"] = m["kapi_no"].fillna("").map(anahtar).to_numpy()
        # Bina listesi (OneMap mahalleleri; yazım platformla aynı olsun diye ad önceliği bunda)
        g = m[m["_mk"].ne("") & m["mahalle"].ne("Bilinmiyor")].groupby(["il", "ilce", "mahalle"])
        bina_mahalleleri = [(il, ilce, mahalle_eki_sil(mh), float(grp["lat"].median()), float(grp["lon"].median()))
                            for (il, ilce, mh), grp in g]
        return s, bina_mahalleleri

    def mahalleleri_kur(self, liste_satirlari, bina_mahalleleri, ek_mahalleler=()) -> "Sozluk":
        """Ucuz yarı: bina tablolarını PAYLAŞAN yeni sözlük + mahalleler (liste › bina adı önceliği › ek)."""
        s = type(self)(bina=self.bina, loc=self.loc, serial=self.serial, site=self.site, a=self.a,
                       ilce_merkez=dict(self.ilce_merkez))
        # 1) Bursa mahalle listesi (ilçe başına sayfa, koordinatlı) — bu ilçelerin listesi eksiksiz
        for il, ilce, ad, lat, lon in liste_satirlari:
            s._ekle(il, ilce, ad, lat, lon)
            s.tam_liste.add(ilce_anahtari(il, ilce))
        # 2) Bina listesi
        for il, ilce, ad, lat, lon in bina_mahalleleri:
            s._ekle(il, ilce, ad, lat, lon, ad_oncelikli=True)
        for il, ilce, ad, lat, lon in ek_mahalleler:
            s._ekle(il, ilce, ad, lat, lon)
        return s

    def ilce_merkezi(self, il, ilce):
        ik, ck = ilce_anahtari(il, ilce)
        return self.ilce_merkez.get(ik + ck) or self.ilce_merkez.get(ck)

    def _ekle(self, il, ilce, ad, lat=None, lon=None, ad_oncelikli=False):
        k = anahtar(ad)
        if not k:
            return
        d = self.mah.setdefault(ilce_anahtari(il, ilce), {})
        eski = d.get(k)
        if eski is None:
            d[k] = Mahalle(il, ilce, ad, lat, lon)
        else:
            if ad_oncelikli:
                eski.ad = ad
            if eski.lat is None and lat is not None:
                eski.lat, eski.lon = lat, lon
        self.maks_kelime = max(self.maks_kelime, len(sade(ad).split()))

    def ilce_mahalleleri(self, il, ilce) -> dict:
        return self.mah.get(ilce_anahtari(il, ilce), {})

    def baska_ilcede(self, il, mk) -> list[Mahalle]:
        ik = anahtar(il)
        return [d[mk] for (i, _), d in self.mah.items() if i == ik and mk in d]


def _mahalle_listesi(liste: Path) -> list[tuple]:
    """BursaStateList.xlsx → [(il, ilçe, mahalle, lat, lon)]. Excel yavaş okunduğu için JSON önbelleğe alınır."""
    if MAHALLE_ONBELLEK.exists() and (not liste.exists()
                                      or MAHALLE_ONBELLEK.stat().st_mtime >= liste.stat().st_mtime):
        return [tuple(r) for r in json.loads(MAHALLE_ONBELLEK.read_text(encoding="utf-8"))["mahalleler"]]
    if not liste.exists():
        return []
    satirlar = []
    x = pd.ExcelFile(liste)
    for sayfa in x.sheet_names:
        d = x.parse(sayfa, usecols=lambda c: c in ("Mahalle", "Koordinat")).dropna(how="all")
        for ad, koord in zip(d.get("Mahalle", []), d.get("Koordinat", [None] * len(d))):
            if isinstance(ad, str) and ad.strip():
                lat, lon = _koordinat(koord)
                satirlar.append(("Bursa", sayfa, mahalle_eki_sil(ad), lat, lon))
    MAHALLE_ONBELLEK.write_text(json.dumps({"kaynak": liste.name, "mahalleler": satirlar}, ensure_ascii=False),
                                encoding="utf-8")
    return satirlar


# --------------------------------------------------------------------------- mahalle çözümü
@dataclass
class MahalleSonucu:
    ad: str | None
    kaynak: str        # adres · adres-benzer · adres-yeni · adres-isaretsiz · lokasyon · site · yok
    notlar: str = ""
    mahalle: Mahalle | None = None
    kontrol: bool = False   # notlar gerçekten bakılmalı mı (ör. ilçenin listesinde olmayan mahalle)


def _kelimeler(adres: str) -> tuple[list[str], list[str]]:
    """Adresin kelimeleri (parantez içi atılır): (özgün, sade)."""
    temiz = re.sub(r"\([^)]*\)", " ", str(adres or ""))
    orj = [t for t in re.findall(rf"[{_HARF}]+", temiz) if anahtar(t) not in _GURULTU]
    return orj, [anahtar(t) for t in orj]


def _isaretler(orj: list[str], nt: list[str]):
    """Mahalle işaretleri: 'Görükle Mh.', 'İhsaniye Mah.', bitişik 'ADNAN MENDERESMH.'
    Her biri için (işaretten önceki sade kelimeler, özgün kelimeler, kelime sırası)."""
    for i, t in enumerate(nt):
        if t in _ISARET and i > 0:
            yield nt[:i], orj[:i], i
        elif len(t) > 4 and t.endswith("MH"):
            yield nt[:i] + [t[:-2]], orj[:i] + [orj[i][:-2]], i
        elif len(t) > 5 and t.endswith("MAH") and not t.endswith("SMAH"):
            yield nt[:i] + [t[:-3]], orj[:i] + [orj[i][:-3]], i


def _ham_ad(onceki_orj: list[str]) -> str | None:
    """Sözlükte olmayan mahalle için işaretten geriye doğru ad kelimeleri (en çok 3)."""
    secilen: list[str] = []
    for w in reversed(onceki_orj):
        k = anahtar(w)
        if not k or k in _DUR or k in _ISARET:
            break
        if re.search(r"\d", k) and re.search(r"[A-Z]", k):      # A6, 8G, ABA10 → blok kodu
            break
        if len(k) == 1 and not k.isdigit():                      # tek harf blok adı
            break
        # Başlık yazımlı mahalle adının önünde BÜYÜK HARF site adı varsa orada dur
        if secilen and w.isupper() and not secilen[-1].isupper() and len(k) > 1:
            break
        secilen.append(w)
        if k.isdigit() or len(secilen) == 3:
            break
    return baslik(" ".join(reversed(secilen))) if secilen else None


def mahalle_coz(sozluk: Sozluk, adres: str, il: str, ilce: str) -> MahalleSonucu:
    orj, nt = _kelimeler(adres)
    ilce_d = sozluk.ilce_mahalleleri(il, ilce)
    n_max = sozluk.maks_kelime + 1
    isaretler = list(_isaretler(orj, nt))

    # 1) işaretin hemen önündeki ad sözlükte mi (en uzun eşleşme önce: "30 Ağustos Zafer" > "Zafer")
    for onceki, _, _ in isaretler:
        for n in range(min(len(onceki), n_max), 0, -1):
            k = "".join(onceki[-n:])
            if k in ilce_d:
                return MahalleSonucu(ilce_d[k].ad, "adres", mahalle=ilce_d[k])

    if isaretler:
        onceki, onceki_orj, _ = isaretler[0]
        ham = _ham_ad(onceki_orj)
        # 2) aynı ilde başka ilçede birebir var mı (ilçe N sütunundan kalır, not düşülür)
        if ham:
            hk = anahtar(ham)
            # 3) yakın yazım (Yunusemre / Yunus Emre, Beşevler / Besevler …)
            yakin = difflib.get_close_matches(hk, list(ilce_d), n=1, cutoff=0.86)
            if not yakin and len(hk) >= 5:
                # 4) kısaltılmış ad: "Cumhuriyet Mah. … Demirtaş" → Demirtaş Cumhuriyet
                sonek = [k for k in ilce_d if k.endswith(hk) and k != hk]
                if len(sonek) > 1:
                    tum = "".join(nt)
                    sonek = [k for k in sonek if k[:-len(hk)] in tum]
                yakin = sonek if len(sonek) == 1 else []
            if yakin:
                mh = ilce_d[yakin[0]]
                return MahalleSonucu(mh.ad, "adres-benzer", f"adreste '{ham}'", mahalle=mh)
            notu = ""
            if ilce_anahtari(il, ilce) in sozluk.tam_liste:
                baska = sozluk.baska_ilcede(il, hk)
                notu = f"'{ham}' {ilce} mahalle listesinde yok" + (
                    f" ({', '.join(sorted({b.ilce for b in baska}))} ilçesinde var)" if baska else "")
            return MahalleSonucu(ham, "adres-yeni", notu, kontrol=bool(notu))

    # 4) işaret yok: sözlükteki adlardan biri adreste geçiyor mu (en uzun)
    en_iyi = None
    for i in range(len(nt)):
        for n in range(min(n_max, len(nt) - i), 0, -1):
            k = "".join(nt[i:i + n])
            if k in ilce_d and (en_iyi is None or n > en_iyi[0]):
                en_iyi = (n, ilce_d[k])
                break
    if en_iyi:
        return MahalleSonucu(en_iyi[1].ad, "adres-isaretsiz", "adreste 'Mah.' yok", mahalle=en_iyi[1])
    return MahalleSonucu(None, "yok")


# --------------------------------------------------------------------------- konum
_BN = re.compile(r"BN-?\d{6,}(?:-\d+)?", re.I)
_NO = re.compile(r"\bNo\s*:\s*([0-9]+[A-Za-zÇĞİÖŞÜçğıöşü0-9]*)", re.I)


@dataclass
class KonumSonucu:
    lat: float | None
    lon: float | None
    kaynak: str               # bina (Lokasyon) · bina (BN kodu) · bina (site adı) · site (site adı) · mahalle merkezi · yok
    bina: int | None = None   # master satır no
    yer: str = ""             # bölme birimi: aynı yerdeki işler birlikte kalır


def lokasyon_adaylari(lok: str) -> list[str]:
    """BOSS "Lokasyon" yazımları → denenecek location_id'ler (saha/ticket.py:lokasyondan_bina ile aynı sıra).

    Birebir · 8 haneye sıfırla · baştaki sıfırsız · sondaki '-N' eksiz. Raporda Excel sayıya çevirmişse
    '12345678.0' da düzelir.
    """
    lok = (lok or "").strip()
    if not lok or lok.lower() == "nan":
        return []
    if re.fullmatch(r"\d+\.0", lok):
        lok = lok[:-2]
    adaylar = [lok]
    if lok.isdigit():
        adaylar += [lok.zfill(8), lok.lstrip("0")]
    ekisiz = re.sub(r"-\d{1,2}$", "", lok)
    if ekisiz != lok:
        adaylar.append(ekisiz)
    return list(dict.fromkeys(a for a in adaylar if a))


def _yakin_mi(la: np.ndarray, lo: np.ndarray) -> bool:
    la, lo = la.astype(float), lo.astype(float)
    if np.isnan(la).any():
        return False
    dy = (la.max() - la.min()) * 111_320
    dx = (lo.max() - lo.min()) * 111_320 * np.cos(np.radians(la.mean()))
    return max(dx, dy) <= BIR_BINA_YARICAP_M


def konum_coz(sozluk: Sozluk, adres: str, lokasyon, il: str, ilce: str,
              mahalle: MahalleSonucu) -> KonumSonucu:
    a = sozluk.a

    def bina(i: int, kaynak: str) -> KonumSonucu:
        grup = a["site_grup"][i] if isinstance(a["site_grup"][i], str) else a["bina_serial"][i]
        return KonumSonucu(float(a["lat"][i]), float(a["lon"][i]), kaynak, i, f"B:{grup}")

    lok = str(lokasyon).strip() if isinstance(lokasyon, str) else ""
    for aday in lokasyon_adaylari(lok):
        if aday in sozluk.loc:
            return bina(sozluk.loc[aday], "bina (Lokasyon)")
    bn = _BN.search(str(adres or ""))
    if bn:
        kod = bn.group(0).upper()
        kod = kod if kod.startswith("BN-") else "BN-" + kod[2:]
        if kod in sozluk.serial:
            return bina(sozluk.serial[kod], "bina (BN kodu)")

    # adresin başındaki site adı (mahalle işaretinden önceki kısım)
    orj, nt = _kelimeler(adres)
    isaret = next((i for _, _, i in _isaretler(orj, nt)), len(orj))
    ik, ck = ilce_anahtari(il, ilce)
    mk = anahtar(mahalle.ad) if mahalle.ad else ""
    for n in range(isaret, 0, -1):
        adaylar = sozluk.site.get("".join(nt[:n]))
        if not adaylar:
            continue
        idx = np.asarray(adaylar)
        idx = idx[(a["_ik"][idx] == ik) & (a["_ck"][idx] == ck)]
        if mk and (a["_mk"][idx] == mk).any():
            idx = idx[a["_mk"][idx] == mk]
        if len(idx) == 0:
            continue
        if len(idx) > 1:
            no = _NO.search(str(adres or ""))
            if no:
                b = idx[a["_kapi"][idx] == anahtar(no.group(1))]
                if len(b) == 1:
                    idx = b
        if len(idx) == 1:
            return bina(int(idx[0]), "bina (site adı)")
        if _yakin_mi(a["lat"][idx], a["lon"][idx]):
            return KonumSonucu(float(a["lat"][idx].mean()), float(a["lon"][idx].mean()), "site (site adı)", None,
                               f"S:{a['site_grup'][idx[0]]}")
        break
    return merkez_konumu(sozluk, il, ilce, mahalle)


def merkez_konumu(sozluk: Sozluk, il: str, ilce: str, mahalle: MahalleSonucu) -> KonumSonucu:
    """Bina bulunamayınca: mahalle merkezi, o da yoksa ilçe merkezi (kaba)."""
    ik, ck = ilce_anahtari(il, ilce)
    mk = anahtar(mahalle.ad) if mahalle.ad else ""
    yer = f"M:{ik}/{ck}/{mk}" if mk else f"I:{ik}/{ck}"
    mh = mahalle.mahalle or (sozluk.ilce_mahalleleri(il, ilce).get(mk) if mk else None)
    if mh is not None and mh.lat is not None:
        return KonumSonucu(mh.lat, mh.lon, "mahalle merkezi", None, yer)
    im = sozluk.ilce_merkezi(il, ilce)
    if im:
        return KonumSonucu(im[0], im[1], "ilçe merkezi (kaba)", None, yer)
    return KonumSonucu(None, None, "yok", None, yer)


# --------------------------------------------------------------------------- öbekler
def _ref(il: str, ilce: str, mahalle: str) -> str:
    return f"{il}/{ilce}/{mahalle}"


def _ref_anahtari(ref: str) -> tuple[str, str, str]:
    """'Bursa/Nilüfer/Görükle', 'Nilüfer/Görükle' (il boş), 'Bursa/Mudanya/*' (ilçenin tamamı)."""
    p = [x.strip() for x in str(ref).split("/")]
    if len(p) == 2:
        p = ["", *p]
    il, ilce, mh = (p + ["", "", ""])[:3]
    ik, ck = ilce_anahtari(il, ilce) if il else ("", anahtar(ilce))
    return ik, ck, ("*" if mh == "*" else anahtar(mh))


@dataclass
class Obekler:
    tanimlar: list[dict] = field(default_factory=list)     # [{"ad": ..., "mahalleler": [ref, ...]}]
    _tablo: dict = field(default_factory=dict, repr=False)

    @classmethod
    def yukle(cls, yol: Path = OBEK_DOSYASI) -> "Obekler":
        o = cls()
        if yol.exists():
            o.tanimlar = json.loads(yol.read_text(encoding="utf-8")).get("obekler", [])
        o._derle()
        return o

    def kaydet(self, yol: Path = OBEK_DOSYASI) -> None:
        veri = {"surum": 1,
                "aciklama": "Öbek = kullanıcının mahalle grubu. Mahalle yazımı: 'İl/İlçe/Mahalle'; "
                            "'İl/İlçe/*' ilçenin tamamı; il yazılmazsa 'İlçe/Mahalle' de olur.",
                "obekler": self.tanimlar}
        gecici = yol.with_suffix(".tmp")
        gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        gecici.replace(yol)

    def _derle(self) -> None:
        self._tablo = {}
        for t in self.tanimlar:
            for ref in t.get("mahalleler", []):
                self._tablo[_ref_anahtari(ref)] = t["ad"]

    def bul(self, il: str, ilce: str, mahalle: str | None) -> str | None:
        ik, ck = ilce_anahtari(il, ilce)
        mk = anahtar(mahalle) if mahalle else ""
        for anah in ((ik, ck, mk), ("", ck, mk), (ik, ck, "*"), ("", ck, "*")):
            if anah in self._tablo and (mk or anah[2] == "*"):
                return self._tablo[anah]
        return None

    def ata(self, ad: str, refler: list[str]) -> None:
        """Mahalleleri 'ad' öbeğine taşır (başka öbekteyseler oradan çıkar)."""
        yeni = {_ref_anahtari(r) for r in refler}
        for t in self.tanimlar:
            t["mahalleler"] = [r for r in t["mahalleler"] if _ref_anahtari(r) not in yeni]
        hedef = next((t for t in self.tanimlar if t["ad"] == ad), None)
        if hedef is None:
            hedef = {"ad": ad, "mahalleler": []}
            self.tanimlar.append(hedef)
        hedef["mahalleler"].extend(refler)
        self.tanimlar = [t for t in self.tanimlar if t["mahalleler"]]
        self._derle()

    def cikar(self, refler: list[str]) -> None:
        """Mahalleleri bulundukları öbekten çıkarır (öbeksiz kalırlar)."""
        sil = {_ref_anahtari(r) for r in refler}
        for t in self.tanimlar:
            t["mahalleler"] = [r for r in t["mahalleler"] if _ref_anahtari(r) not in sil]
        self.tanimlar = [t for t in self.tanimlar if t["mahalleler"]]
        self._derle()

    def sil(self, ad: str) -> None:
        self.tanimlar = [t for t in self.tanimlar if t["ad"] != ad]
        self._derle()

    @classmethod
    def veritabanindan(cls, yol: Path) -> "Obekler | None":
        """Uygulamanın öbekleri (v2: kaynak veritabanıdır). Dosya SALT OKUNUR açılır (mode=ro).

        Veritabanı yoksa ya da öbek tablosu henüz kurulmamışsa None (komut satırı obekler.json'a döner).
        """
        import sqlite3
        if not Path(yol).exists():
            return None
        try:
            conn = sqlite3.connect(f"file:{Path(yol).as_posix()}?mode=ro", uri=True, timeout=5)
        except sqlite3.Error:
            return None
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='obek_mahalle'").fetchone():
                return None
            satirlar = conn.execute(
                "SELECT o.id, o.ad, m.ref FROM obek o LEFT JOIN obek_mahalle m ON m.obek_id = o.id "
                "WHERE o.aktif = 1 ORDER BY o.id, m.rowid").fetchall()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        o = cls()
        sira: dict[int, dict] = {}
        for oid, ad, ref in satirlar:
            t = sira.setdefault(oid, {"ad": ad, "mahalleler": []})
            if ref:
                t["mahalleler"].append(ref)
        o.tanimlar = list(sira.values())
        o._derle()
        return o

    def yeniden_adlandir(self, eski: str, yeni: str) -> None:
        hedef = next((t for t in self.tanimlar if t["ad"] == yeni), None)
        for t in [t for t in self.tanimlar if t["ad"] == eski]:
            if hedef is not None and hedef is not t:      # aynı ada birleştir
                hedef["mahalleler"].extend(t["mahalleler"])
                self.tanimlar.remove(t)
            else:
                t["ad"] = yeni
        self._derle()


# --------------------------------------------------------------------------- rapor
@dataclass
class Sonuc:
    isler: pd.DataFrame            # kalan işler + eklenen sütunlar
    cikarilan: pd.DataFrame        # çıkarılan satırlar (neden sütunlu)
    ozet: dict
    sure_sn: float


def raporu_oku(yol) -> pd.DataFrame:
    """'Task Adı' ve 'Adres' başlıklı sayfayı bulur (ilk sayfa özet/pivot olabilir)."""
    x = pd.ExcelFile(yol)
    for sayfa in x.sheet_names:
        on = x.parse(sayfa, header=None, nrows=15, dtype=str)
        for satir in range(len(on)):
            degerler = {str(v).strip() for v in on.iloc[satir].tolist()}
            if {"Task Adı", "Adres"} <= degerler:
                return x.parse(sayfa, header=satir, dtype=str)
    raise ValueError("Dosyada 'Task Adı' ve 'Adres' sütunlu bir sayfa bulunamadı (BOSS Teknik Task Detay Raporu mu?)")


_SOZLUK: Sozluk | None = None


def sozluk() -> Sozluk:
    global _SOZLUK
    if _SOZLUK is None:
        _SOZLUK = Sozluk.yukle()
    return _SOZLUK


def hazirla(df: pd.DataFrame, obekler: Obekler | None = None, szl: Sozluk | None = None,
            istisnalar=VARSAYILAN_ISTISNALAR, mahalle_cozucu=None) -> Sonuc:
    """Rapor → işler. ``mahalle_cozucu(szl, adres, il, ilce)`` verilirse ``mahalle_coz`` yerine o kullanılır
    (v2 hattı köy biçimlerini önce dener); komut satırı makrosu bugünkü davranışla kalır."""
    t0 = time.perf_counter()
    szl = szl or sozluk()
    obekler = obekler if obekler is not None else Obekler.yukle()
    cozucu = mahalle_cozucu or mahalle_coz
    eksik = [v for v in (SUTUNLAR["task"], SUTUNLAR["adres"], SUTUNLAR["il"], SUTUNLAR["ilce"]) if v not in df.columns]
    if eksik:
        raise ValueError(f"Raporda eksik sütun: {', '.join(eksik)}")
    df = df.reset_index(drop=True)
    neden = df[SUTUNLAR["task"]].map(lambda t: cikarilacak_mi(t, istisnalar))
    istisna_tutulan = int(sum(1 for t, n in zip(df[SUTUNLAR["task"]], neden)
                              if pd.isna(n) and cikarilacak_mi(t, ()) is not None))
    cikarilan = df[neden.notna()].assign(**{"Çıkarılma Nedeni": neden[neden.notna()]})
    d = df[neden.isna()].copy()

    lok_kol = SUTUNLAR["lokasyon"] if SUTUNLAR["lokasyon"] in d.columns else None
    girdiler = list(zip(d[SUTUNLAR["adres"]].fillna(""), d[SUTUNLAR["il"]].fillna(""),
                        d[SUTUNLAR["ilce"]].fillna(""), d[lok_kol] if lok_kol else [None] * len(d)))
    mahalleler = [cozucu(szl, adres, il, ilce) for adres, il, ilce, _ in girdiler]
    # 'Mah.' yazılmamış adresler için aynı rapordan öğrenilen adlar (listesi olmayan ilçeler: Yalova, Karacabey …)
    ogrenilen: dict = {}
    for (_, il, ilce, _), ms in zip(girdiler, mahalleler):
        if ms.kaynak == "adres-yeni" and ms.ad:
            ogrenilen.setdefault(ilce_anahtari(il, ilce), {})[anahtar(ms.ad)] = ms.ad
    for j, ((adres, il, ilce, _), ms) in enumerate(zip(girdiler, mahalleler)):
        sozl = ogrenilen.get(ilce_anahtari(il, ilce))
        if ms.kaynak != "yok" or not sozl:
            continue
        _, nt = _kelimeler(adres)
        for i in range(len(nt)):
            bulundu = next((sozl["".join(nt[i:i + n])] for n in range(4, 0, -1) if "".join(nt[i:i + n]) in sozl), None)
            if bulundu:
                mahalleler[j] = MahalleSonucu(bulundu, "adres-isaretsiz", "adreste 'Mah.' yok; ad aynı rapordan")
                break

    satirlar = []
    for (adres, il, ilce, lok), ms in zip(girdiler, mahalleler):
        ks = konum_coz(szl, adres, lok, il, ilce, ms)
        # Kontrol: yalnız gerçekten bakılması gereken (mahalle yok, il bölge dışı, çelişen ilçe …).
        # Bilgi: kontrol gerektirmeyen farklar (adresteki yazım, OneMap'le fark …).
        kontrol = [ms.notlar] if ms.notlar and ms.kontrol else []
        bilgi = [ms.notlar] if ms.notlar and not ms.kontrol else []
        if ks.bina is not None:
            b = szl.bina.loc[ks.bina]
            bmh = mahalle_eki_sil(b["mahalle"]) if isinstance(b["mahalle"], str) else None
            bina_ilcede = (b["_ik"], b["_ck"]) == ilce_anahtari(il, ilce)
            kesin = "Lokasyon" in ks.kaynak or "BN" in ks.kaynak
            if bina_ilcede and bmh and bmh != "Bilinmiyor" and anahtar(bmh) != anahtar(ms.ad or ""):
                # Kullanıcı kuralı: Location Id raporda varsa OneMap'teki binanın mahallesi esastır.
                # Site adından bulunan binada ise adresteki listeli (kesin) mahalle korunur.
                if kesin or ms.kaynak != "adres":
                    bilgi = [f"adreste '{ms.ad}'"] if ms.ad else []
                    ms = MahalleSonucu(bmh, "lokasyon" if kesin else "site")
                    kontrol = []
                else:
                    bilgi.append(f"binanın OneMap mahallesi: {bmh}")
            if not bina_ilcede:
                kontrol.append(f"Lokasyon/site başka ilçede ({b['ilce']}) — konumu kullanılmadı")
                ks = merkez_konumu(szl, il, ilce, ms)
        if not ms.ad:
            kontrol.append("mahalle bulunamadı — öbeğe elle ekleyin")
        if anahtar(il) not in BOLGE_ILLERI:
            kontrol.append(f"il bölge dışı: {il or '—'}")
        if ks.lat is None:
            kontrol.append("konum bulunamadı")
        obek = obekler.bul(il, ilce, ms.ad)
        satirlar.append({
            "Mahalle": ms.ad or "",
            "Öbek": obek or "",
            "Mahalle Kaynağı": ms.kaynak,
            "Enlem": ks.lat, "Boylam": ks.lon,
            "Konum Kaynağı": ks.kaynak,
            "Bina Serial": szl.bina.at[ks.bina, "bina_serial"] if ks.bina is not None else "",
            "Kontrol Notu": "; ".join(n for n in kontrol if n),
            "Bilgi": "; ".join(n for n in bilgi if n),
            "_yer": ks.yer,
        })
    ek = pd.DataFrame(satirlar, index=d.index)
    # Yeni sütunlar İlçe'nin hemen sağına: … İl, İlçe, Mahalle, Öbek, …
    konum = list(d.columns).index(SUTUNLAR["ilce"]) + 1
    for j, kol in enumerate(["Mahalle", "Öbek"]):
        d.insert(konum + j, kol, ek[kol])
    for kol in ["Mahalle Kaynağı", "Enlem", "Boylam", "Konum Kaynağı", "Bina Serial", "Kontrol Notu", "Bilgi", "_yer"]:
        d[kol] = ek[kol]

    kaynak = d["Mahalle Kaynağı"].value_counts().to_dict()
    ozet = {
        "toplam_satir": int(len(df)),
        "cikarilan": int(len(cikarilan)),
        "cikarilan_neden": {k: int(v) for k, v in cikarilan["Çıkarılma Nedeni"].value_counts().items()},
        "istisna_tutulan": istisna_tutulan,
        "kalan": int(len(d)),
        "mahalle_bulunan": int((d["Mahalle"] != "").sum()),
        "mahalle_kaynak": {k: int(v) for k, v in kaynak.items()},
        "konum_kaynak": {k: int(v) for k, v in d["Konum Kaynağı"].value_counts().items()},
        "obekli": int((d["Öbek"] != "").sum()),
        "mahalle_sayisi": int(d.loc[d["Mahalle"] != "", [SUTUNLAR["il"], SUTUNLAR["ilce"], "Mahalle"]]
                              .drop_duplicates().shape[0]),
    }
    return Sonuc(d, cikarilan, ozet, round(time.perf_counter() - t0, 3))


def mahalle_tablosu(isler: pd.DataFrame) -> pd.DataFrame:
    """İl · İlçe · Mahalle · Öbek · iş sayısı (öbek tanımlamak için)."""
    il, ilce = SUTUNLAR["il"], SUTUNLAR["ilce"]
    g = (isler.assign(Mahalle=isler["Mahalle"].replace("", "(bulunamadı)"))
         .groupby([il, ilce, "Mahalle"], dropna=False)
         .agg(**{"İş": ("Mahalle", "size"), "Öbek": ("Öbek", "first")})
         .reset_index())
    return g.sort_values([il, ilce, "İş"], ascending=[True, True, False])[[il, ilce, "Mahalle", "İş", "Öbek"]]


def obek_tablosu(isler: pd.DataFrame) -> pd.DataFrame:
    t = isler.assign(Öbek=isler["Öbek"].replace("", "(öbeksiz)"))
    task = SUTUNLAR["task"]

    def mahalleler(s):
        ad = sorted(set(s) - {""})
        if s.name == "(öbeksiz)" or len(ad) > 12:
            return f"{len(ad)} mahalle — Mahalleler sayfasında Öbek sütununu doldurun" if s.name == "(öbeksiz)" \
                else ", ".join(ad[:12]) + f" … (+{len(ad) - 12})"
        return ", ".join(ad)

    g = t.groupby("Öbek").agg(**{"İş": (task, "size")})
    g["Mahalle"] = t.groupby("Öbek")["Mahalle"].apply(mahalleler)
    tip = pd.crosstab(t["Öbek"], t[task])
    tip = tip[tip.sum().sort_values(ascending=False).index]
    return g.join(tip).sort_values("İş", ascending=False).reset_index()


def excel_yaz(sonuc: Sonuc, yol: Path) -> Path:
    isler = sonuc.isler.drop(columns=["_yer"])
    kontrol = isler[isler["Kontrol Notu"] != ""]
    ozet = pd.DataFrame(
        [("Rapordaki satır", sonuc.ozet["toplam_satir"]),
         *[(f"Çıkarılan: Task Adı'nda '{k.lower()}'", v) for k, v in sonuc.ozet["cikarilan_neden"].items()],
         ("Kalan iş", sonuc.ozet["kalan"]),
         ("Mahallesi bulunan", sonuc.ozet["mahalle_bulunan"]),
         *[(f"  mahalle kaynağı: {k}", v) for k, v in sonuc.ozet["mahalle_kaynak"].items()],
         *[(f"  konum: {k}", v) for k, v in sonuc.ozet["konum_kaynak"].items()],
         ("Öbeği tanımlı iş", sonuc.ozet["obekli"]),
         ("Farklı mahalle", sonuc.ozet["mahalle_sayisi"]),
         ("Süre", f"{sonuc.sure_sn:.1f} sn".replace(".", ","))], columns=["Kalem", "Değer"])
    sayfalar = {
        "İşler": isler,
        "Öbekler": obek_tablosu(isler),
        "Mahalleler": mahalle_tablosu(isler),
        "Kontrol": kontrol,
        "Çıkarılanlar": sonuc.cikarilan,
        "Özet": ozet,
    }
    with pd.ExcelWriter(yol, engine="openpyxl") as w:
        for ad, t in sayfalar.items():
            t.to_excel(w, sheet_name=ad, index=False)
            ws = w.sheets[ad]
            ws.freeze_panes = "A2"
            if len(t):
                ws.auto_filter.ref = ws.dimensions
            for j, kol in enumerate(t.columns, start=1):
                uz = max([len(str(kol))] + [len(str(v)) for v in t[kol].head(200).tolist()])
                ws.column_dimensions[ws.cell(1, j).column_letter].width = min(max(8, uz + 2), 60)
    return yol


def obek_tablosunu_al(yol, obekler: Obekler | None = None) -> tuple[Obekler, int]:
    """'Mahalleler' sayfasında Öbek sütunu doldurulmuş Excel → öbek tanımları."""
    obekler = obekler if obekler is not None else Obekler.yukle()
    x = pd.ExcelFile(yol)
    sayfa = "Mahalleler" if "Mahalleler" in x.sheet_names else x.sheet_names[0]
    t = x.parse(sayfa, dtype=str).fillna("")
    il, ilce = SUTUNLAR["il"], SUTUNLAR["ilce"]
    sayi = 0
    for ad, grp in t[t["Öbek"].str.strip() != ""].groupby(t["Öbek"].str.strip()):
        refler = [_ref(a, b, c) for a, b, c in zip(grp[il], grp[ilce], grp["Mahalle"]) if c and c != "(bulunamadı)"]
        if refler:
            obekler.ata(ad, refler)
            sayi += len(refler)
    return obekler, sayi


def _uygulama_veritabani() -> Path:
    import os
    return Path(os.environ.get("SAHA_DB") or (yollar.CALISMA_SAHA / "saha.db"))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    # v2: öbeklerin kaynağı uygulamanın veritabanıdır (salt okunur). Yoksa bugünkü obekler.json.
    db_obekler = Obekler.veritabanindan(_uygulama_veritabani())
    for dosya in argv:
        yol = Path(dosya)
        try:
            x = pd.ExcelFile(yol)
            ilk = x.parse(x.sheet_names[0], nrows=0, dtype=str)
        except Exception as e:        # noqa: BLE001 — kullanıcıya düz mesaj
            print(f"✗ {yol.name}: okunamadı ({e})")
            continue
        # Hazır dosyanın kendisi (ya da Mahalle + Öbek sütunlu bir tablo) geri bırakılırsa: öbek tanımı
        if "Mahalleler" in x.sheet_names or {"Mahalle", "Öbek"} <= set(ilk.columns):
            if db_obekler is not None:
                print("✗ Öbekler artık uygulamada tutuluyor. Öbekleri uygulamadaki Öbekler ekranından düzenleyin.")
                continue
            o, n = obek_tablosunu_al(yol)
            o.kaydet()
            print(f"✓ Öbek tanımları güncellendi: {n} mahalle, {len(o.tanimlar)} öbek → {OBEK_DOSYASI}")
            continue
        t0 = time.perf_counter()
        try:
            df = raporu_oku(yol)
        except ValueError as e:
            print(f"✗ {yol.name}: {e}")
            continue
        s = hazirla(df, db_obekler)
        cikti = yol.with_name(yol.stem + "_hazir.xlsx")
        excel_yaz(s, cikti)
        o = s.ozet
        print(f"✓ {yol.name}: {o['toplam_satir']} satır → {o['cikarilan']} çıkarıldı "
              f"({', '.join(f'{k.lower()}: {v}' for k, v in o['cikarilan_neden'].items()) or '-'}) → "
              f"{o['kalan']} iş · mahalle bulunan {o['mahalle_bulunan']} · {o['mahalle_sayisi']} mahalle · "
              f"öbekli {o['obekli']} · {time.perf_counter() - t0:.1f} sn")
        print(f"  → {cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
