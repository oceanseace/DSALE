"""Öncelik puanı ve günlük tur kurucu.

    oncelik = firsat × yeni_site_carpani × tekrar_carpani × doygunluk_carpani

Yeni açılan siteler genelde daha yüksek potansiyele sahiptir; doygun binalar
(penetrasyon yüksek) geri plana düşer; ziyaret edilmiş bina 30 gün listeye girmez.

SIRALAMA ÜÇ SINIFLIDIR — sistemin ana vaadi ("sudoku gibi boşlukları doldurmak")
buna bağlı:
    0) sözü olan bina (tekrar_gel, günü gelmiş) — müşteriye verilmiş söz
    1) HİÇ DOKUNULMAMIŞ bina — asıl iş
    2) 30 günü dolmuş tekrar ziyaret
Bir sınıf tükenmeden sonraki sınıfa geçilmez. Yalnız puana bakan eski sıralama,
130 iş günlük simülasyonda bölgelerin %26-41'ini gezip aynı binaları döndürüyor,
geri kalanına hiç uğramıyordu.

Fırsatı sıfır olan bina da (666 adet) listeye girer, sadece en sona düşer:
kapsama tavanı %100 olmalı, "kalan" bir gün gerçekten sıfırlanabilmeli.

SEÇİM YAKINLIĞA DUYARLIDIR: aday puanı, o ana kadar seçilmiş kümeye uzaklıkla
bölünür (``ayarlar.YAKINLIK_KM``). Yalnız puana bakan eski seçim, 8. bölge gibi
geniş bölgelerde 25 binayı bölgenin dört bir yanından alıp 78 km'lik — bir günde
gezilemeyecek — turlar kuruyordu.

Her şey belirlenimcidir: aynı veriyle aynı sıra çıkar (eşitlikler bina_serial ile bozulur).
"""
from __future__ import annotations

import datetime as dt
import math
import sqlite3
from collections import OrderedDict

from . import ayarlar

DUNYA_YARICAP_M = 6_371_000.0

BINA_ALANLARI = """
    b.bina_serial, b.ad, b.site_adi, b.mahalle, b.ilce, b.il, b.cadde, b.sokak, b.kapi_no,
    b.lat, b.lon, b.kat, b.daire, b.res_hp, b.aktif_res, b.firsat, b.sales_ready,
    b.bolge, b.obek, b.site_grup,
    b.location_id, b.tellcordia_id, b.uavt_bina_kodu, b.blok_adi, b.bina_turu,
    b.toplam_hp, b.altyapi, b.teknoloji, b.crm_site_adi,
    b.kalite, b.pasif, b.pasif_tarih, b.tur_tarihi,
    d.durum, d.son_ziyaret, d.son_sonuc, d.tekrar_tarih, d.toplam_satis, d.ziyaret_sayisi
"""


# ----------------------------------------------------------------------------- coğrafya
def mesafe_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki nokta arası kuş uçuşu mesafe (metre)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dlat = f2 - f1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dlon / 2) ** 2
    return 2 * DUNYA_YARICAP_M * math.asin(math.sqrt(a))


def _tarih(deger) -> dt.date | None:
    if not deger:
        return None
    if isinstance(deger, dt.datetime):
        return deger.date()
    if isinstance(deger, dt.date):
        return deger
    metin = str(deger).strip()
    if not metin:
        return None
    try:
        return dt.date.fromisoformat(metin[:10])
    except ValueError:
        return None


# ----------------------------------------------------------------------------- çarpanlar
def yeni_site_carpani(sales_ready, bugun: dt.date) -> float:
    """Satışa açılalı 12 aydan az olan siteler en yüksek potansiyeli taşır."""
    acilis = _tarih(sales_ready)
    if acilis is None:
        return 1.0
    ay = (bugun.year - acilis.year) * 12 + (bugun.month - acilis.month)
    if acilis.day > bugun.day:
        ay -= 1
    if ay < 0:            # ileri tarihli kayıt: yeni sayılır
        return 1.6
    if ay < 12:
        return 1.6
    if ay < 24:
        return 1.3
    return 1.0


def tekrar_carpani(durum: str, tekrar_tarih, bugun: dt.date) -> float:
    """Sözü olan bina öne, kapısı kapalı bina geriye."""
    if durum == "tekrar_gel":
        gun = _tarih(tekrar_tarih)
        return 1.4 if (gun is None or gun <= bugun) else 1.0
    if durum == "girilemedi":
        return 0.4
    if durum == "altyapi_sorunu":
        return 0.2
    return 1.0


def doygunluk_carpani(aktif_res, res_hp) -> float:
    """Penetrasyon %60 üstü doygun (0,7) · %30 altı bakir (1,2)."""
    try:
        hp = int(res_hp or 0)
        aktif = int(aktif_res or 0)
    except (TypeError, ValueError):
        return 1.0
    if hp <= 0:
        return 1.0
    pen = aktif / hp
    if pen > 0.60:
        return 0.7
    if pen < 0.30:
        return 1.2
    return 1.0


def oncelik_puani(b: dict, bugun: dt.date) -> float:
    """Binanın ham öncelik puanı.

    Taban ``ayarlar.TABAN_ONCELIK``: fırsatı sıfır olan bina da havuzda kalsın
    diye. Eskiden puanı 0 çıkan 666 bina hiçbir rotaya giremiyor, kapsama
    %96,6'da takılıyordu.
    """
    firsat = float(b.get("firsat") or 0)
    puan = (
        firsat
        * yeni_site_carpani(b.get("sales_ready"), bugun)
        * tekrar_carpani(b.get("durum") or "bekliyor", b.get("tekrar_tarih"), bugun)
        * doygunluk_carpani(b.get("aktif_res"), b.get("res_hp"))
    )
    return max(puan, ayarlar.TABAN_ONCELIK)


def oncelik_sinifi(b: dict) -> int:
    """0 = sözü olan · 1 = hiç dokunulmamış · 2 = tekrar ziyaret.

    Sıralamanın ilk anahtarı budur: bölgede dokunulmamış bina kaldığı sürece
    algoritma tekrar ziyarete geçmez.
    """
    if (b.get("durum") or "bekliyor") == "tekrar_gel":
        return 0
    return 1 if not b.get("son_ziyaret") else 2


def uygun_mu(b: dict, bugun: dt.date) -> bool:
    """Bina bugünün listesine girebilir mi?

    - ``bekliyor``: her zaman.
    - ``tekrar_gel``: tekrar tarihi geldiyse (soğuma kuralından muaf).
    - ``planli``: başka bir listede, girmez.
    - diğerleri: son ziyaretin üstünden 30 gün geçtiyse.
    """
    if b.get("pasif"):
        return False
    durum = b.get("durum") or "bekliyor"
    if durum == "bekliyor":
        return True
    if durum == "planli":
        return False
    if durum == "tekrar_gel":
        gun = _tarih(b.get("tekrar_tarih"))
        return gun is None or gun <= bugun
    son = _tarih(b.get("son_ziyaret"))
    if son is None:
        return True
    return (bugun - son).days >= ayarlar.SOGUMA_GUN


# ----------------------------------------------------------------------------- adaylar
def adaylari_getir(
    conn: sqlite3.Connection,
    bolge: int,
    bugun: dt.date | None = None,
    havuz: int = ayarlar.ADAY_HAVUZU,
    haric: set[str] | None = None,
    en_az: int = ayarlar.VARSAYILAN_ADET,
) -> list[dict]:
    """Bölgedeki uygun binaları öncelik sırasına dizip en iyi ``havuz`` tanesini verir.

    KAPSAMA GÜVENCESİ: bölgede en az ``en_az`` kadar "sözü olan ya da hiç
    dokunulmamış" bina varsa havuza TEKRAR ZİYARET HİÇ KONMAZ. Yani bir bölge
    bitmeden aynı binaya ikinci kez gidilmez. Ancak kalan dokunulmamış bina bir
    günlük işten azsa, satışçı yarım günle kalmasın diye havuz tekrar
    ziyaretlerle tamamlanır.
    """
    gun = bugun or ayarlar.bugun()
    satirlar = conn.execute(
        f"SELECT {BINA_ALANLARI} FROM bina b JOIN bina_durum d USING(bina_serial) "
        # Son tur raporunda olmayan (pasif) bina listeye girmez; geçmişi yerinde durur.
        "WHERE b.bolge=? AND b.pasif=0",
        (bolge,),
    ).fetchall()
    haric = haric or set()
    adaylar: list[dict] = []
    for satir in satirlar:
        b = dict(satir)
        if b["bina_serial"] in haric or not uygun_mu(b, gun):
            continue
        b["oncelik"] = round(oncelik_puani(b, gun), 3)
        b["sinif"] = oncelik_sinifi(b)
        adaylar.append(b)
    adaylar.sort(key=sirala_anahtari)
    oncelikli = [a for a in adaylar if a["sinif"] <= 1]
    if len(oncelikli) >= max(1, en_az):
        return oncelikli[:havuz]
    return adaylar[:havuz]


def sirala_anahtari(b: dict):
    """Önce sınıf (söz → dokunulmamış → tekrar), sonra puan, sonra seri (belirlenimci)."""
    return (b.get("sinif", 1), -float(b.get("oncelik") or 0), b["bina_serial"])


# ----------------------------------------------------------------------------- tur
def _grupla(binalar: list[dict]) -> "OrderedDict[str, list[dict]]":
    """Aynı sitenin blokları tek durak olur; öncelik sırası korunur."""
    gruplar: OrderedDict[str, list[dict]] = OrderedDict()
    for b in binalar:
        grup = (b.get("site_grup") or "").strip() or f"tek:{b['bina_serial']}"
        gruplar.setdefault(grup, []).append(b)
    return gruplar


def _merkez(uyeler: list[dict]) -> tuple[float, float]:
    n = len(uyeler)
    return (sum(u["lat"] for u in uyeler) / n, sum(u["lon"] for u in uyeler) / n)


def _en_yakin_komsu(noktalar: list[tuple[float, float]], bas: tuple[float, float]) -> list[int]:
    kalan = set(range(len(noktalar)))
    sira: list[int] = []
    konum = bas
    while kalan:
        i = min(kalan, key=lambda k: (mesafe_m(*konum, *noktalar[k]), k))
        sira.append(i)
        kalan.discard(i)
        konum = noktalar[i]
    return sira


def _iki_opt(noktalar: list[tuple[float, float]], bas: tuple[float, float], sira: list[int]) -> list[int]:
    """Açık yolda (başlangıç sabit, dönüş yok) 2-opt iyileştirmesi."""
    n = len(sira)
    if n < 4:
        return sira
    d = lambda a, b: mesafe_m(a[0], a[1], b[0], b[1])  # noqa: E731
    gelisti, tur = True, 0
    while gelisti and tur < 60:
        gelisti, tur = False, tur + 1
        for i in range(n - 1):
            onceki = bas if i == 0 else noktalar[sira[i - 1]]
            for j in range(i + 1, n):
                kazanc = d(onceki, noktalar[sira[j]]) - d(onceki, noktalar[sira[i]])
                if j + 1 < n:
                    sonraki = noktalar[sira[j + 1]]
                    kazanc += d(noktalar[sira[i]], sonraki) - d(noktalar[sira[j]], sonraki)
                if kazanc < -0.5:  # yarım metrenin altındaki kazanç sayılmaz
                    sira[i:j + 1] = reversed(sira[i:j + 1])
                    gelisti = True
                    onceki = bas if i == 0 else noktalar[sira[i - 1]]
    return sira


# Sınıf ağırlığı: kesin güvence ``adaylari_getir``'da (havuz sınıfa göre
# doldurulur); burada yalnız tur içinde yön verir.
SINIF_AGIRLIK = {0: 2.5, 1: 1.0, 2: 0.4}
# Kaç farklı başlangıç öbeği denenir (bkz. ``_grup_sec``).
TOHUM_DENEME = 6


def _grup_bilgisi(gruplar: "OrderedDict[str, list[dict]]") -> dict:
    bilgi = {}
    for grup, uyeler in gruplar.items():
        bilgi[grup] = {
            "merkez": _merkez(uyeler),
            "sinif": min(int(u.get("sinif", 1)) for u in uyeler),
            "puan": sum(float(u.get("oncelik") or 0) for u in uyeler) / len(uyeler),
        }
    return bilgi


def _zincir(
    gruplar: "OrderedDict[str, list[dict]]",
    bilgi: dict,
    bas: tuple[float, float],
    adet: int,
    tohum: str | None = None,
) -> tuple["OrderedDict[str, list[dict]]", float, float, float]:
    """Bir tohum duraktan başlayıp zincir gibi büyüyen seçim.

    Dönen: (seçim, zincirin iç maliyeti km, ilk bacak km, toplam öncelik).
    Uzaklık her adımda SEÇİLMİŞ duraklara en yakın olana göre ölçülür; puanın
    karesel uzaklık cezasıyla bölünmesi turu bir öbekte tutar.
    """
    kalanlar = list(gruplar.items())
    secili: "OrderedDict[str, list[dict]]" = OrderedDict()
    noktalar: list[tuple[float, float]] = [bas]
    sayac, maliyet, ilk_km, puan = 0, 0.0, 0.0, 0.0

    # Taşma payı listeye oranlı: 25'lik listede 5 bina, 5'likte 1. Sabit pay
    # küçük listeleri iki katına çıkarıyordu.
    tasma = max(1, min(ayarlar.LISTE_TASMA, adet // 5))

    def _alinacak(n: int, yer: int, bos: bool) -> int | None:
        if n > adet:
            # Tek başına bir günden büyük site (en büyüğü 151 bina) bölünmek
            # zorunda; ama yalnız listenin BAŞINDA alınır, sonunda değil. Aksi
            # halde listenin kuyruğunda da bölünüp adet aşılıyordu.
            return adet if bos else None
        if n > yer + tasma:
            return None                      # sığmıyor, bölmeden geç
        return n

    while kalanlar and sayac < adet:
        yer = adet - sayac
        en_iyi = None
        for i, (grup, uyeler) in enumerate(kalanlar):
            alinacak = _alinacak(len(uyeler), yer, not secili)
            if alinacak is None:
                continue
            b = bilgi[grup]
            km = min(
                mesafe_m(n0[0], n0[1], b["merkez"][0], b["merkez"][1]) for n0 in noktalar
            ) / 1000.0
            if tohum is not None and not secili:
                # İlk durak dışarıdan dayatıldı.
                if grup != tohum:
                    continue
                anahtar = (0.0, grup)
            else:
                # Karesel ceza: 2 km puanı yarıya, 20 km yüzde bire indirir.
                oran = km / ayarlar.YAKINLIK_KM
                skor = b["puan"] * SINIF_AGIRLIK.get(b["sinif"], 1.0) / (1.0 + oran * oran)
                anahtar = (-round(skor, 6), grup)
            if en_iyi is None or anahtar < en_iyi[0]:
                en_iyi = (anahtar, i, alinacak, km)
        if en_iyi is None:
            if tohum is not None and not secili:
                return OrderedDict(), 0.0, 0.0, 0.0     # tohum sığmıyor
            break
        _, idx, alinacak, km = en_iyi
        grup, uyeler = kalanlar.pop(idx)
        alinan = uyeler if alinacak >= len(uyeler) else uyeler[:alinacak]
        secili[grup] = alinan
        sayac += len(alinan)
        puan += sum(float(u.get("oncelik") or 0) for u in alinan)
        if len(secili) == 1:
            ilk_km = km
        else:
            maliyet += km
        noktalar.append(bilgi[grup]["merkez"])
    return secili, maliyet, ilk_km, puan


def _grup_sec(
    gruplar: "OrderedDict[str, list[dict]]",
    bas: tuple[float, float],
    adet: int,
) -> "OrderedDict[str, list[dict]]":
    """Yakınlığa duyarlı, site bütünlüğünü bozmayan seçim.

    Tek bir tohumla açgözlü büyümek yetmiyor: yola çıkılan yere en yakın öbekte
    yalnız 4 uygun bina kalmışsa zincir oradan başlayıp 30 km ötedeki öbeğe
    atlıyor. Bu yüzden birkaç makul tohum denenir ve "çok bina, az yol" ölçütüyle
    en iyisi seçilir.

    Site bütünlüğü: bir site grubu ya tamamen listeye girer ya hiç girmez
    (``ayarlar.LISTE_TASMA`` kadar taşmaya izin var). Tek başına bir günden
    büyük siteler — en büyüğü 151 bina — kaçınılmaz olarak bölünür.
    """
    if not gruplar:
        return OrderedDict()
    bilgi = _grup_bilgisi(gruplar)

    # Tohum adayları: yola çıkılan yere göre puan/uzaklık dengesi en iyi olanlar.
    def _tohum_anahtari(grup: str):
        b = bilgi[grup]
        km = mesafe_m(bas[0], bas[1], b["merkez"][0], b["merkez"][1]) / 1000.0
        # Gidiş yolu bir kerelik maliyet; tur içi atlamalardan daha az cezalandırılır.
        oran = km / (ayarlar.YAKINLIK_KM * 5)
        return (-round(b["puan"] * SINIF_AGIRLIK.get(b["sinif"], 1.0) / (1.0 + oran * oran), 6), grup)

    tohumlar = sorted(gruplar.keys(), key=_tohum_anahtari)[:TOHUM_DENEME]

    en_iyi = None
    for tohum in tohumlar:
        secim, maliyet, ilk_km, puan = _zincir(gruplar, bilgi, bas, adet, tohum)
        if not secim:
            continue
        sayi = sum(len(v) for v in secim.values())
        # "Çok bina, çok fırsat, az yol": tur içi her 5 km ve gidişteki her 25 km
        # puanı yarıya indirir. Eksik dolan liste de cezalandırılır.
        skor = (puan * sayi / adet) / (1.0 + maliyet / 5.0 + ilk_km / 25.0)
        anahtar = (-round(skor, 6), tohum)
        if en_iyi is None or anahtar < en_iyi[0]:
            en_iyi = (anahtar, secim)
    if en_iyi is None:
        return _zincir(gruplar, bilgi, bas, adet)[0]
    return en_iyi[1]


def tur_kur(
    binalar: list[dict],
    baslangic: tuple[float, float] | None = None,
    adet: int = ayarlar.VARSAYILAN_ADET,
) -> list[dict]:
    """Öncelik sırası verilmiş adaylardan ``adet`` binalık sıralı tur kurar.

    Seçim önceliğe VE yakınlığa, sıralama coğrafyaya göredir. Dönen her kayıtta
    ``sira`` ve bir önceki duraktan ``mesafe_m`` bulunur.
    """
    if not binalar or adet <= 0:
        return []
    bas = baslangic or (ayarlar.OFIS["lat"], ayarlar.OFIS["lon"])

    # 1) Öncelik + yakınlık ile, site bütünlüğünü bozmadan adet kadar bina seç.
    secili = _grup_sec(_grupla(binalar), bas, adet)

    # 2) Durakları (siteleri) coğrafi olarak sırala.
    anahtarlar = list(secili.keys())
    merkezler = [_merkez(secili[g]) for g in anahtarlar]
    duzen = _iki_opt(merkezler, bas, _en_yakin_komsu(merkezler, bas))

    # 3) Her durağın içinde blokları da en yakın komşuyla sırala, mesafeleri yaz.
    cikti: list[dict] = []
    konum = bas
    for idx in duzen:
        uyeler = secili[anahtarlar[idx]]
        noktalar = [(u["lat"], u["lon"]) for u in uyeler]
        ic_duzen = _en_yakin_komsu(noktalar, konum) if len(uyeler) > 1 else [0]
        for j in ic_duzen:
            u = dict(uyeler[j])
            u["mesafe_m"] = int(round(mesafe_m(*konum, u["lat"], u["lon"])))
            u["sira"] = len(cikti) + 1
            cikti.append(u)
            konum = (u["lat"], u["lon"])
    return cikti


def gunluk_rota(
    conn: sqlite3.Connection,
    bolge: int,
    baslangic: tuple[float, float] | None = None,
    adet: int = ayarlar.VARSAYILAN_ADET,
    bugun: dt.date | None = None,
    haric: set[str] | None = None,
) -> list[dict]:
    """Bir bölge için bugünün sıralı bina listesi.

    BÖLGENİN SONU AYRI BİR DURUMDUR. Havuzda dokunulmamış bina kaldığı sürece
    tekrar ziyaret havuza hiç girmez (bkz. ``adaylari_getir``). Ama kalan
    dokunulmamış bina bir günlük işin altına düşünce havuz tekrar ziyaretlerle
    doluyor ve son birkaç bina puan yarışını KALICI olarak kaybediyordu: fırsatı
    sıfır ya da öbeğin dışında kalan bir bina, yanındaki "30 günü dolmuş, 40 boş
    kapılı" binaya karşı hiçbir gün kazanamaz. Ölçtük: 1. bölge 88 günde
    1.972/1.973'e geliyor, kalan TEK bina 350 gün daha seçilmiyordu.

    Oysa haritadaki son gri nokta tam da yöneticinin baktığı şey. Bu yüzden
    kalan dokunulmamışlar ÖNCE alınır, günün geri kalanı tekrar ziyaretlerle
    doldurulur.
    """
    gun = bugun or ayarlar.bugun()
    adaylar = adaylari_getir(conn, bolge, gun, haric=haric, en_az=adet)
    oncelikli = [a for a in adaylar if a["sinif"] <= 1]
    if not oncelikli or len(oncelikli) >= adet:
        return tur_kur(adaylar, baslangic, adet)

    liste = tur_kur(oncelikli, baslangic, adet)
    kalan = adet - len(liste)
    if kalan <= 0:
        return liste
    alinan = {b["bina_serial"] for b in liste}
    son = liste[-1]
    ek = tur_kur(
        [a for a in adaylar if a["bina_serial"] not in alinan],
        (son["lat"], son["lon"]),
        kalan,
    )
    for b in ek:
        b["sira"] += len(liste)
    return liste + ek


def toplam_mesafe_m(rota: list[dict]) -> int:
    return int(sum(b.get("mesafe_m", 0) for b in rota))


def tur_uyarisi(rota: list[dict]) -> str | None:
    """Tur bir günde gezilemeyecek kadar uzunsa Türkçe uyarı, değilse None.

    Mesafeler kuş uçuşu; gerçek yol daha da uzundur. Satışçı listeyi alır almaz
    bunu görmeli, akşam yarısında kalmış bir listeyle karşılaşmamalı.
    """
    km = toplam_mesafe_m(rota) / 1000.0
    if km <= ayarlar.UZUN_TUR_KM:
        return None
    return (
        f"Bu tur yaklaşık {km:,.0f} km — bir günde zor yetişir. "
        "Yöneticinden daha dar bir bölge istemen iyi olur."
    ).replace(",", ".")
