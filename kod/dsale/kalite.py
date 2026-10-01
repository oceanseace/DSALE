"""Veri kalitesi motoru — raporlardaki mantıksız veriyi açıklanabilir kurallarla bulur.

    python -m dsale.kalite            # kanıtları üretir, kural başına sayıları yazar

Her kural dört şey söyler: NE bulundu (tek cümle, sade Türkçe), NE KADAR önemli
(``bilgi`` / ``uyari``), NE YAPILDI (düzeltildi mi, düzeltildiyse eski → yeni) ve
NEDEN (``KURALLAR[...]["aciklama"]``). Kara kutu yok: her bayrak yeniden
üretilebilir ve kanıtıyla birlikte saklanır.

Düzeltme yalnız GÜVENLİ olduğunda yapılır:
  * sonuç kesinse (Excel'in bilimsel sayıya çevirdiği Tellcordia ID'nin bütün
    basamakları duruyor ve OneMap aynı sayıyı söylüyor; sıfırı düşen Location Id
    OneMap'teki ENTEGRASYON_ID ile birebir aynı),
  * ya da değer yalnız GÖRÜNTÜYÜ etkiliyorsa (1 katlı 38 daireli bina → kat).
Satışı etkileyen sayılara (RES HP, abone) HİÇBİR ZAMAN dokunulmaz; yalnız işaretlenir.
Orijinal değer bayrağın ``duzeltme.eski`` alanında ve kanıtın ``ham`` sözlüğünde kalır.

İki katman:
  ``kanitlar()``  ham kaynaklardan (bina_master.csv, veri_kalitesi.json, OneMap JSON)
                  bina başına kanıt üretir. pandas ister; sonuç
                  ``veri/master/bina_kalite_kanit.json`` dosyasına önbelleklenir.
  ``denetle()``   saf Python: bina + kanıt → (bayraklar, düzeltmeler). Saha sunucusu
                  bir binanın HP'si/abonesi değiştiğinde bunu yeniden çağırır.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import config

KURAL_SURUMU = "K1"
KANIT_JSON = config.MASTER / "bina_kalite_kanit.json"

# Kaynakta "boş" anlamına gelen yazımlar (CRM dışa aktarımı 'Null' yazıyor).
BOS_METINLER = {"", "null", "none", "nan", "-", "yok"}

# Konum sapması eşiği: OneMap'in kendi noktası ile poligon merkezi arası.
KONUM_SAPMA_M = 100.0

KURALLAR: dict[str, dict] = {
    "location_sifir": {
        "ad": "Location Id sıfırları düşmüş",
        "seviye": "uyari",
        "duzeltir": True,
        "aciklama": "Excel rakamdan oluşan Location Id'yi sayıya çevirip baştaki sıfırları siliyor "
                    "(00113680 → 113680). BOSS ve ticket'lar 8 haneli hâli kullanır. OneMap'teki "
                    "ENTEGRASYON_ID birebir aynıysa 8 haneye tamamlanır.",
    },
    "location_uyusmaz": {
        "ad": "Location Id OneMap ile farklı",
        "seviye": "uyari",
        "duzeltir": False,
        "aciklama": "Satış raporundaki Location Id ile OneMap'teki ENTEGRASYON_ID aynı değil. "
                    "Hangisinin doğru olduğu bilinemediği için dokunulmaz.",
    },
    "tellcordia_bozuk": {
        "ad": "Tellcordia ID bozuk",
        "seviye": "uyari",
        "duzeltir": True,
        "aciklama": "Excel uzun sayıyı '1,61623150353E+011' gibi bilimsel yazıma çeviriyor. "
                    "Bütün basamaklar duruyorsa ve OneMap aynı sayıyı söylüyorsa düzeltilir.",
    },
    "abone_hp_asiyor": {
        "ad": "Abone, RES HP'den fazla",
        "seviye": "uyari",
        "duzeltir": False,
        "aciklama": "Aktif abone sayısı binanın RES HP'sini aşıyor: HP kaydı eksik. Boş kapı "
                    "(fırsat) eksi olamayacağı için 0 sayılır; HP'ye dokunulmaz.",
    },
    "hp_sifir_abone_var": {
        "ad": "RES HP 0, abone var",
        "seviye": "uyari",
        "duzeltir": False,
        "aciklama": "RES HP 0 görünüyor ama binada aktif abone var: HP kaydı eksik. Boş kapı 0 "
                    "sayılır; doluluk oranı 'veri yok' gösterilir.",
    },
    "hp_sifir": {
        "ad": "RES HP 0",
        "seviye": "bilgi",
        "duzeltir": False,
        "aciklama": "Binada satılabilir kapı görünmüyor. Bina listeye yine girer (kapsama %100 "
                    "olmalı) ama en sona düşer.",
    },
    "kat_tahmini": {
        "ad": "Kat sayısı tahmin",
        "seviye": "bilgi",
        "duzeltir": False,
        "aciklama": "OneMap'te kat sayısı yok (binaların yarısı). Aynı daire aralığındaki katı "
                    "bilinen binaların ortancasından tahmin edilir; ortalama hata 1,1 kat.",
    },
    "kat_daire_celiski": {
        "ad": "Kat ile daire çelişiyor",
        "seviye": "uyari",
        "duzeltir": True,
        "aciklama": "OneMap'teki kat sayısı daire sayısıyla bir arada olamaz (1 katta 38 daire, "
                    "3 daireli binada 45 kat). Kat yalnız haritadaki bina yüksekliğini etkiler; "
                    "bariz hatalarda tahmin edilen kat kullanılır.",
    },
    "kat_basina_cok_daire": {
        "ad": "Kat başına çok daire",
        "seviye": "bilgi",
        "duzeltir": False,
        "aciklama": "Kat başına 20'den çok daire düşüyor. Büyük bloklarda olabilir; kat ya da "
                    "daire sayısı hatalı olabilir. Dokunulmaz.",
    },
    "daire_bilinmiyor": {
        "ad": "Daire sayısı yok",
        "seviye": "bilgi",
        "duzeltir": False,
        "aciklama": "OneMap'te daire sayısı yok; kartta RES HP gösterilir.",
    },
    "tekrar_satir": {
        "ad": "Raporda iki kez geçiyor",
        "seviye": "uyari",
        "duzeltir": False,
        "aciklama": "Aynı Bina Serial Number satış raporunda birden çok satırda var. Toplam HP'si "
                    "büyük olan satır alınır.",
    },
    "konum_sapmasi": {
        "ad": "Konum şüpheli",
        "seviye": "uyari",
        "duzeltir": False,
        "aciklama": "OneMap'in bina için tuttuğu nokta ile bina poligonunun merkezi 100 m'den "
                    "uzak. Harita poligon merkezini kullanır; sahada doğrulanmalı.",
    },
    "ilce_uyusmazligi": {
        "ad": "İlçe farklı",
        "seviye": "uyari",
        "duzeltir": False,
        "aciklama": "Satış raporundaki ilçe ile OneMap'teki ilçe farklı. Harita ve bölgeleme "
                    "OneMap'i (binanın gerçek yeri) kullanır.",
    },
    "bos_ad": {
        "ad": "Bina adı boş",
        "seviye": "bilgi",
        "duzeltir": True,
        "aciklama": "Bina adı veride boş ya da 'Null' yazıyor. 'Null' yazısı boş sayılır; kartta "
                    "site adı, o da yoksa sokak ve kapı numarası gösterilir.",
    },
}

SEVIYE_SIRASI = {"uyari": 0, "bilgi": 1}


# ----------------------------------------------------------------------------- yardımcılar
def _bos(x) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    return str(x).strip().lower() in BOS_METINLER


def _metin(x) -> str:
    return "" if _bos(x) else str(x).strip()


def _sayi(x, varsayilan: int = 0) -> int:
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return varsayilan
        return int(float(x))
    except (TypeError, ValueError):
        return varsayilan


def _tr(n: float, ondalik: int = 0) -> str:
    """Türkçe sayı yazımı: 1.234 · 12,5"""
    metin = f"{n:,.{ondalik}f}"
    return metin.replace(",", "§").replace(".", ",").replace("§", ".")


def _mesafe_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000.0 * math.asin(math.sqrt(a))


_BILIMSEL = re.compile(r"^\s*(\d)[,.](\d+)\s*[eE]\+?(\d+)\s*$")


def bilimselden_tamsayi(metin: str) -> str | None:
    """'1,61623150353E+011' → '161623150353', yalnız bütün basamaklar biliniyorsa.

    Excel 12 anlamlı basamak yazar; üs, virgülden sonraki basamak sayısından
    büyükse sondaki basamaklar yuvarlanıp kaybolmuştur → None (tahmin yapılmaz).
    """
    m = _BILIMSEL.match(metin or "")
    if not m:
        return None
    bas, ondalik, us = m.group(1), m.group(2), int(m.group(3))
    if us < len(ondalik):
        return None                       # tam sayı değil
    if us > len(ondalik):
        return None                       # sondaki basamaklar kayıp
    return (bas + ondalik).lstrip("0") or "0"


def location_norm(x) -> str:
    """BOSS/OneMap eşleştirme anahtarı: yalnız rakamsa 8 haneye sıfırla tamamlanır."""
    s = _metin(x)
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s.zfill(8) if s.isdigit() and len(s) < 8 else s


# ----------------------------------------------------------------------------- kurallar
def _bayrak(kural: str, mesaj: str, duzeltme: dict | None = None) -> dict:
    b = {"kural": kural, "mesaj": mesaj, "seviye": KURALLAR[kural]["seviye"]}
    if duzeltme:
        b["duzeltme"] = duzeltme
    return b


def denetle(bina: dict, kanit: dict | None = None) -> tuple[list[dict], dict]:
    """Bir binanın kalite bayrakları ve güvenli düzeltmeleri.

    ``bina``: veritabanı satırı (bina_serial, ad, site_adi, crm_site_adi, location_id,
    tellcordia_id, kat, daire, res_hp, aktif_res, lat, lon, ilce).
    ``kanit``: ``kanitlar()`` çıktısındaki o binaya ait sözlük (yoksa yalnız satırdan
    anlaşılan kurallar çalışır).

    Dönüş: (bayraklar, {alan: yeni_değer}). Aynı girdiyle her zaman aynı çıktı;
    düzeltilmiş bir satırı yeniden denetlemek aynı bayrağı üretir (kanıttaki ``ham``
    değerlere bakıldığı için).
    """
    k = kanit or {}
    ham = k.get("ham") or {}
    bayraklar: list[dict] = []
    duzelt: dict = {}

    def ham_deger(alan):
        return ham[alan] if alan in ham else bina.get(alan)

    # --- kimlikler: ticket'a ve BOSS eşleştirmesine giden değerler
    loc_ham = _metin(ham_deger("location_id"))
    if loc_ham.endswith(".0") and loc_ham[:-2].isdigit():
        loc_ham = loc_ham[:-2]
    entegrasyon = _metin(k.get("entegrasyon_id"))
    if loc_ham.isdigit() and len(loc_ham) < 8:
        beklenen = loc_ham.zfill(8)
        if entegrasyon == beklenen:
            duzelt["location_id"] = beklenen
            bayraklar.append(_bayrak(
                "location_sifir",
                f"Location Id Excel'de sayıya dönmüş, baştaki sıfırlar düşmüş: {loc_ham} → {beklenen} "
                "(OneMap ile doğrulandı). BOSS'ta ve ticket'ta bu hâliyle yazılır.",
                {"alan": "location_id", "eski": loc_ham, "yeni": beklenen}))
        else:
            bayraklar.append(_bayrak(
                "location_sifir",
                f"Location Id ({loc_ham}) sıfırlarını kaybetmiş olabilir; BOSS'ta {beklenen} olarak "
                "arayın. OneMap ile doğrulanamadığı için değiştirilmedi."))
    elif loc_ham and entegrasyon and location_norm(loc_ham) != location_norm(entegrasyon):
        bayraklar.append(_bayrak(
            "location_uyusmaz",
            f"Location Id raporda {loc_ham}, OneMap'te {entegrasyon}. Ticket açmadan önce BOSS'tan "
            "kontrol edin."))

    tell_ham = _metin(ham_deger("tellcordia_id"))
    if tell_ham and not tell_ham.isdigit():
        tam = bilimselden_tamsayi(tell_ham)
        om_id = _metin(k.get("om_id"))
        if tam and (not om_id or om_id == tam):
            duzelt["tellcordia_id"] = tam
            kanit_metni = "OneMap ile doğrulandı" if om_id else "bütün basamaklar duruyor"
            bayraklar.append(_bayrak(
                "tellcordia_bozuk",
                f"Tellcordia ID Excel'de bilimsel sayıya dönmüş ({tell_ham}). Doğru hâli {tam} "
                f"({kanit_metni}).",
                {"alan": "tellcordia_id", "eski": tell_ham, "yeni": tam}))
        else:
            ek = f" OneMap'te {om_id}." if om_id else ""
            bayraklar.append(_bayrak(
                "tellcordia_bozuk",
                f"Tellcordia ID geçersiz görünüyor ({tell_ham}).{ek} Ticket'a yazmadan önce BOSS'tan "
                "kontrol edin."))

    # --- HP ve abone: üç durum birbirini dışlar, her bina en çok birine girer
    res_hp = _sayi(bina.get("res_hp"))
    aktif = _sayi(bina.get("aktif_res"))
    daire_kanit = k.get("daire")
    daire = _sayi(daire_kanit) if daire_kanit is not None else 0
    if res_hp == 0 and aktif > 0:
        bayraklar.append(_bayrak(
            "hp_sifir_abone_var",
            f"RES HP 0 görünüyor ama {_tr(aktif)} aktif abone var. HP kaydı eksik; boş kapı 0 sayıldı."))
    elif res_hp == 0:
        ek = f" OneMap'te {_tr(daire)} daire görünüyor; altyapı kaydı eksik olabilir." if daire > 0 else ""
        bayraklar.append(_bayrak("hp_sifir", "RES HP 0: bu binada satılabilir kapı görünmüyor." + ek))
    elif aktif > res_hp:
        bayraklar.append(_bayrak(
            "abone_hp_asiyor",
            f"Aktif abone ({_tr(aktif)}) RES HP'den ({_tr(res_hp)}) fazla. Boş kapı 0 sayıldı; HP "
            "kaydı eksik olabilir."))

    # --- kat ve daire
    kat_ham = _sayi(ham_deger("kat"))
    kat_kaynagi = k.get("kat_kaynagi")
    kat_tahmin = _sayi(k.get("kat_tahmin"))
    isyeri = _sayi(k.get("isyeri"))
    if kat_kaynagi == "Tahmin" and kat_ham > 0:
        if daire > 0:
            mesaj = f"Kat sayısı OneMap'te yok; {_tr(daire)} daireye bakılarak {kat_ham} kat tahmin edildi."
        else:
            mesaj = f"Kat sayısı OneMap'te yok; daire sayısı da bilinmediği için {kat_ham} kat varsayıldı."
        bayraklar.append(_bayrak("kat_tahmini", mesaj))
    elif kat_kaynagi == "OneMap" and kat_ham > 0 and daire > 0:
        dusuk = kat_ham <= 2 and daire / kat_ham > 12
        yuksek = kat_ham >= 8 and kat_ham > 2 * (daire + isyeri)
        if (dusuk or yuksek) and kat_tahmin > 0 and kat_tahmin != kat_ham:
            duzelt["kat"] = kat_tahmin
            bayraklar.append(_bayrak(
                "kat_daire_celiski",
                f"OneMap {kat_ham} kat diyor ama binada {_tr(daire)} daire var. Haritada {kat_tahmin} "
                "kat gösteriliyor.",
                {"alan": "kat", "eski": kat_ham, "yeni": kat_tahmin}))
        elif kat_ham >= 3 and daire / kat_ham > 20:
            bayraklar.append(_bayrak(
                "kat_basina_cok_daire",
                f"Kat başına {_tr(daire / kat_ham, 1)} daire düşüyor ({kat_ham} kat, {_tr(daire)} daire). "
                "Kat ya da daire sayısı hatalı olabilir."))
    if daire_kanit is not None and daire <= 0:
        bayraklar.append(_bayrak(
            "daire_bilinmiyor", f"OneMap'te daire sayısı yok; kartta RES HP ({_tr(res_hp)}) gösteriliyor."))

    # --- kaynak raporda tekrar
    tekrar = k.get("tekrar") or []
    if len(tekrar) >= 2:
        hpler = " ve ".join(_tr(_sayi(t.get("res_hp"))) for t in tekrar[:4])
        bayraklar.append(_bayrak(
            "tekrar_satir",
            f"Satış raporunda bu bina {len(tekrar)} kez geçiyor (RES HP {hpler}); Toplam HP'si büyük "
            "olan satır alındı."))

    # --- konum
    om_lat, om_lon = k.get("om_lat"), k.get("om_lon")
    lat, lon = bina.get("lat"), bina.get("lon")
    if om_lat is not None and om_lon is not None and lat is not None and lon is not None:
        try:
            d = _mesafe_m(float(lat), float(lon), float(om_lat), float(om_lon))
        except (TypeError, ValueError):
            d = 0.0
        if d > KONUM_SAPMA_M:
            uzak = f"{_tr(d / 1000, 1)} km" if d >= 1000 else f"{_tr(d)} m"
            bayraklar.append(_bayrak(
                "konum_sapmasi",
                f"OneMap'teki nokta ile bina poligonunun merkezi {uzak} uzak. Harita poligon merkezini "
                "kullanıyor; sahada bina yerini doğrulayın."))

    ilce_crm = _metin(k.get("ilce_crm"))
    ilce = _metin(bina.get("ilce"))
    if ilce_crm and ilce and ilce_crm != ilce:
        bayraklar.append(_bayrak(
            "ilce_uyusmazligi",
            f"Satış raporunda ilçe {ilce_crm}, OneMap'te {ilce}. Harita ve bölge OneMap'e göre."))

    # --- ad: 'Null' yazısı boş sayılır
    ad_ham = ham_deger("ad")
    site_ham = ham_deger("site_adi")
    crm_ham = ham_deger("crm_site_adi")
    ad_null = ad_ham is not None and str(ad_ham).strip() != "" and _bos(ad_ham)
    if ad_null:
        duzelt["ad"] = ""
    if site_ham is not None and str(site_ham).strip() != "" and _bos(site_ham):
        duzelt["site_adi"] = ""
    crm = str(crm_ham or "")
    crm_temiz = re.sub(r"^\s*null\s+", "", crm, flags=re.IGNORECASE).strip()
    if crm and crm_temiz != crm.strip():
        duzelt["crm_site_adi"] = crm_temiz
    if _bos(ad_ham):
        site = _metin(site_ham) or crm_temiz
        if ad_null:
            mesaj = "Veride bina adı yerine 'Null' yazıyor; boş sayıldı."
        else:
            mesaj = "Bina adı veride boş."
        mesaj += " Kartta site adı gösteriliyor." if site else " Kartta sokak ve kapı no gösteriliyor."
        dz = {"alan": "ad", "eski": str(ad_ham), "yeni": ""} if ad_null else None
        bayraklar.append(_bayrak("bos_ad", mesaj, dz))

    bayraklar.sort(key=lambda b: (SEVIYE_SIRASI.get(b["seviye"], 9), list(KURALLAR).index(b["kural"])))
    return bayraklar, duzelt


# ----------------------------------------------------------------------------- kanıt
def _kaynak_imzasi() -> str:
    parcalar = [KURAL_SURUMU]
    for yol in (config.MASTER_CSV, config.QUALITY_JSON, config.ONEMAP_JSON):
        if yol.exists():
            s = yol.stat()
            parcalar.append(f"{yol.name}:{s.st_size}:{int(s.st_mtime)}")
    return "|".join(parcalar)


def kat_tahminleri(df) -> "object":
    """Her bina için daire sayısından kat tahmini (``enrich._kat_tahmini`` ile aynı kovalar).

    Katı OneMap'ten bilinen binaların kova ortancası; kat bilinse de hesaplanır ki
    bariz hatalı OneMap değerinin yerine konabilsin.
    """
    import pandas as pd

    from .enrich import KAT_KOVALARI

    gecerli = df["kat_kaynagi"].eq("OneMap")
    daire = pd.to_numeric(df["konut_sayisi"], errors="coerce").fillna(0).clip(lower=0)
    kat = pd.to_numeric(df["kat"], errors="coerce")
    kova = pd.cut(daire, KAT_KOVALARI, include_lowest=True)
    bilinen = gecerli & (daire > 0)
    medyan = kat[bilinen].groupby(kova[bilinen], observed=True).median()
    tahmin = kova.map(medyan).astype(float)
    tahmin = tahmin.fillna((daire / 2).round().clip(1, 12)).round().clip(1, 45)
    return tahmin.astype(int)


_KOVA = re.compile(r"^\(\s*(-?[\d.]+)\s*,\s*([\d.]+)\s*\]$")


def kat_tahmini_tek(daire: int | None) -> int:
    """Tek bir bina için daire sayısından kat tahmini (sonradan eklenen binalar).

    ``veri_kalitesi.json``daki kova ortancaları kullanılır (enrich ile aynı tahmin);
    dosya yoksa kat başına 2 daire varsayılır.
    """
    d = max(_sayi(daire), 0)
    try:
        medyan = json.load(open(config.QUALITY_JSON, encoding="utf-8")).get("kat_tahmin_kova_medyanlari") or {}
    except (OSError, ValueError):
        medyan = {}
    for anahtar, deger in medyan.items():
        m = _KOVA.match(str(anahtar))
        if m and float(m.group(1)) < d <= float(m.group(2)):
            return int(min(max(round(float(deger)), 1), 45))
    return int(min(max(round(d / 2), 1), 12))


def onemap_ozellikleri(yol: Path | None = None) -> tuple[dict, dict]:
    """OneMap dökümünden (ID → öznitelik, LOCATION_ID → öznitelik) sözlükleri."""
    yol = Path(yol) if yol else config.ONEMAP_JSON
    if not yol.exists():
        return {}, {}
    j = json.load(open(yol, encoding="utf-8"))
    kimlik, konum = {}, {}
    for f in j.get("features", []):
        a = f.get("a") or f.get("attributes") or {}
        if a.get("ID") is not None:
            try:
                kimlik[str(int(a["ID"]))] = a
            except (TypeError, ValueError):
                pass
        if a.get("LOCATION_ID"):
            konum[str(a["LOCATION_ID"])] = a
    return kimlik, konum


def _float(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def kanitlar(yeniden: bool = False) -> dict[str, dict]:
    """Bina başına kanıt sözlüğü: {bina_serial: {ham, kat_kaynagi, kat_tahmin, daire, ...}}.

    Kaynak dosyalar değişmedikçe önbellekten okunur (``bina_kalite_kanit.json``).
    """
    imza = _kaynak_imzasi()
    if not yeniden and KANIT_JSON.exists():
        try:
            saklanan = json.load(open(KANIT_JSON, encoding="utf-8"))
            if saklanan.get("imza") == imza:
                return saklanan["bina"]
        except (OSError, ValueError, KeyError):
            pass

    import pandas as pd

    df = pd.read_csv(config.MASTER_CSV, encoding="utf-8-sig",
                     dtype={"tellcordia_id": str, "location_id": str, "uavt_bina_kodu": str})
    df["kat_tahmin"] = kat_tahminleri(df)
    kimlik, konum = onemap_ozellikleri()
    rapor = json.load(open(config.QUALITY_JSON, encoding="utf-8")) if config.QUALITY_JSON.exists() else {}
    tekrar: dict[str, list] = {}
    for t in rapor.get("tekrar_eden_satir", []):
        tekrar.setdefault(str(t.get("bina_serial")), []).append(
            {"res_hp": _sayi(t.get("res_hp")), "toplam_hp": _sayi(t.get("toplam_hp"))})
    ilce_crm = {str(r.get("bina_serial")): r.get("ilce_crm") for r in rapor.get("ilce_uyusmazligi", [])}

    sonuc: dict[str, dict] = {}
    for r in df.to_dict("records"):
        serial = str(r["bina_serial"])
        tell = _metin(r.get("tellcordia_id"))
        a = kimlik.get(tell) or konum.get(serial) or {}
        k = {
            "ham": {
                "location_id": _metin(r.get("location_id")),
                "tellcordia_id": tell,
                "kat": _sayi(r.get("kat")),
                "ad": "" if r.get("ad") is None or (isinstance(r.get("ad"), float)) else str(r.get("ad")),
                "site_adi": "" if not isinstance(r.get("site_adi"), str) else r.get("site_adi"),
                "crm_site_adi": "" if not isinstance(r.get("site_adi_crm"), str) else r.get("site_adi_crm"),
            },
            "kat_kaynagi": r.get("kat_kaynagi"),
            "kat_tahmin": int(r["kat_tahmin"]),
            "daire": None if _float(r.get("konut_sayisi")) is None else int(float(r["konut_sayisi"])),
            "isyeri": None if _float(r.get("isyeri_sayisi")) is None else int(float(r["isyeri_sayisi"])),
        }
        if a:
            if a.get("ID") is not None:
                k["om_id"] = str(int(a["ID"]))
            if _float(a.get("LAT")) is not None and _float(a.get("LON")) is not None:
                k["om_lat"], k["om_lon"] = _float(a["LAT"]), _float(a["LON"])
            if a.get("ENTEGRASYON_ID"):
                k["entegrasyon_id"] = str(a["ENTEGRASYON_ID"]).strip()
        if serial in tekrar:
            k["tekrar"] = tekrar[serial]
        if serial in ilce_crm:
            k["ilce_crm"] = ilce_crm[serial]
        sonuc[serial] = k

    try:
        KANIT_JSON.parent.mkdir(parents=True, exist_ok=True)
        json.dump({"imza": imza, "kural_surumu": KURAL_SURUMU, "bina": sonuc},
                  open(KANIT_JSON, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    except OSError:
        pass                          # salt-okunur klasör: önbelleksiz de çalışır
    return sonuc


def kanit_onemap(a: dict, daire: int | None = None, kat_kaynagi: str | None = None,
                 kat_tahmin: int | None = None, ham: dict | None = None) -> dict:
    """Sonradan eklenen (tur raporu + OneMap) bir bina için kanıt sözlüğü."""
    k: dict = {"ham": ham or {}}
    if kat_kaynagi:
        k["kat_kaynagi"] = kat_kaynagi
    if kat_tahmin:
        k["kat_tahmin"] = int(kat_tahmin)
    k["daire"] = daire
    if a.get("ISYERI_SAYISI") is not None:
        k["isyeri"] = _sayi(a.get("ISYERI_SAYISI"))
    if a.get("ID") is not None:
        try:
            k["om_id"] = str(int(a["ID"]))
        except (TypeError, ValueError):
            pass
    if _float(a.get("LAT")) is not None and _float(a.get("LON")) is not None:
        k["om_lat"], k["om_lon"] = _float(a["LAT"]), _float(a["LON"])
    if a.get("ENTEGRASYON_ID"):
        k["entegrasyon_id"] = str(a["ENTEGRASYON_ID"]).strip()
    return k


# ----------------------------------------------------------------------------- toplu
def master_denetle(yeniden: bool = False) -> dict:
    """Master tablonun bütününü denetler; kural başına sayı döndürür (komut satırı için)."""
    import pandas as pd

    df = pd.read_csv(config.MASTER_CSV, encoding="utf-8-sig",
                     dtype={"tellcordia_id": str, "location_id": str})
    kanit = kanitlar(yeniden=yeniden)
    sayac: dict[str, dict] = {k: {"adet": 0, "duzeltilen": 0} for k in KURALLAR}
    bayrakli = 0
    for r in df.to_dict("records"):
        b = {"bina_serial": r["bina_serial"], "ad": r.get("ad"), "site_adi": r.get("site_adi"),
             "crm_site_adi": r.get("site_adi_crm"), "location_id": r.get("location_id"),
             "tellcordia_id": r.get("tellcordia_id"), "kat": r.get("kat"), "res_hp": r.get("res_hp"),
             "aktif_res": r.get("aktif_res"), "lat": r.get("lat"), "lon": r.get("lon"), "ilce": r.get("ilce")}
        bayraklar, _ = denetle(b, kanit.get(str(r["bina_serial"])))
        bayrakli += 1 if bayraklar else 0
        for f in bayraklar:
            sayac[f["kural"]]["adet"] += 1
            sayac[f["kural"]]["duzeltilen"] += 1 if f.get("duzeltme") else 0
    return {"bina": int(len(df)), "bayrakli_bina": bayrakli, "kurallar": sayac}


if __name__ == "__main__":
    import sys

    for akis in (sys.stdout, sys.stderr):
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass
    ozet = master_denetle(yeniden="--yeniden" in sys.argv)
    print(f"{_tr(ozet['bina'])} bina · {_tr(ozet['bayrakli_bina'])} binada en az bir bulgu")
    for kural, s in ozet["kurallar"].items():
        if s["adet"]:
            ek = f" · {_tr(s['duzeltilen'])} düzeltildi" if s["duzeltilen"] else ""
            print(f"  {KURALLAR[kural]['ad']:<32} {_tr(s['adet']):>7}{ek}")
