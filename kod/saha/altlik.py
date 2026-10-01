"""Harita altlığı (sokak ve uydu karoları) ayarı + buna göre İçerik Güvenliği Politikası.

Varsayılanlar:
    sokak  OpenStreetMap standart karoları   https://tile.openstreetmap.org/{z}/{x}/{y}.png
    uydu   Esri World Imagery                https://server.arcgisonline.com/.../tile/{z}/{y}/{x}

LİSANS NOTU (yönetici ve BT için — belgeler/SAHA_SOZLESME.md §7.6):
  * OpenStreetMap karoları gönüllü sunuculardır; "ağır kullanım" yasaktır, atıf
    (© OpenStreetMap katkıcıları) her zaman görünmelidir ve tarayıcı istekleri
    Referer taşımalıdır. 8-15 kişilik ekip için kabul edilebilir; daha büyük
    kullanımda ücretli bir sağlayıcı (MapTiler, Mapbox, HERE) ya da Turkcell'in
    kendi altlığı bağlanmalıdır.
  * Esri World Imagery'nin ticari kullanımı ArcGIS hesabı/lisansı gerektirir.
    Kurumsal lisans yoksa uydu katmanı yalnız değerlendirme amaçlıdır.
  * Karo isteği kullanıcının tarayıcısından SAĞLAYICIYA gider (ofis IP'si ve
    bakılan bölge sağlayıcıda görünür). Sistemin bina/müşteri verisi GİTMEZ.
Adresler yönetici ekranından değiştirilebilir (PUT /api/ayar/altlik); sunucu yeniden
başlatılmadan CSP başlığı yeni sağlayıcıya izin verecek şekilde güncellenir.
"""
from __future__ import annotations

import ipaddress
import json
import re
import sqlite3
from urllib.parse import urlsplit

from . import db

AYAR_ANAHTARI = "altlik"

VARSAYILAN = {
    "sokak_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "uydu_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "sokak_atif": "© OpenStreetMap katkıcıları",
    "uydu_atif": "Uydu: Esri, Maxar, Earthstar Geographics ve GIS Kullanıcı Topluluğu",
    "sokak_en_fazla_zoom": 19,
    "uydu_en_fazla_zoom": 19,
}
LISANS_NOTU = (
    "OpenStreetMap karoları yalnız hafif kullanım içindir ve atıf zorunludur; Esri uydu görüntüsünün "
    "ticari kullanımı ArcGIS lisansı ister. Kalıcı çözüm: lisanslı sağlayıcı ya da Turkcell'in kendi altlığı. "
    "Karo istekleri tarayıcıdan sağlayıcıya gider; bina/müşteri verisi gitmez."
)
# Karo adresinde izin verilen yer tutucular
_YER_TUTUCU = re.compile(r"\{(z|x|y|s|r|-y)\}")

_csp_onbellek: dict = {}


def _host_kalibi(url: str) -> str | None:
    """'https://{s}.tile.osm.org/{z}/...' → 'https://*.tile.osm.org' (CSP kaynağı)."""
    try:
        p = urlsplit(url.replace("{s}", "a"))
    except ValueError:
        return None
    if p.scheme not in ("https", "http") or not p.hostname:
        return None
    host = p.hostname
    if "{s}" in url:
        host = "*." + host.split(".", 1)[1] if "." in host else host
    port = f":{p.port}" if p.port else ""
    return f"{p.scheme}://{host}{port}"


def _yerel_mi(host: str) -> bool:
    """Ofis ağı içindeki bir sunucu mu (http'ye yalnız bunlarda izin var)?"""
    if host == "localhost" or host.endswith(".local"):
        return True
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return False


def dogrula(url: str) -> str:
    url = (url or "").strip()
    if len(url) > 400:
        raise ValueError("Adres çok uzun.")
    p = urlsplit(url.replace("{s}", "a"))
    if p.scheme not in ("https", "http") or not p.hostname:
        raise ValueError("Adres https:// ile başlamalı.")
    if p.scheme == "http" and not _yerel_mi(p.hostname):
        raise ValueError("İnternetteki karo sağlayıcısı https:// olmalı (http yalnız ofis içi sunucu için).")
    kalan = _YER_TUTUCU.sub("", url)
    if not all(t in url for t in ("{z}", "{x}")) or ("{y}" not in url and "{-y}" not in url):
        raise ValueError("Adreste {z}, {x} ve {y} yer tutucuları olmalı.")
    if "{" in kalan or "}" in kalan:
        raise ValueError("Tanınmayan yer tutucu var; yalnız {z} {x} {y} {s} kullanılabilir.")
    return url


def oku(conn: sqlite3.Connection) -> dict:
    try:
        kayit = json.loads(db.ayar_oku(conn, AYAR_ANAHTARI) or "{}")
    except (ValueError, TypeError):
        kayit = {}
    ayar = {**VARSAYILAN, **{k: v for k, v in kayit.items() if k in VARSAYILAN and v}}
    return {
        **ayar,
        # Tek satırlık atıf (arayüz tek metin gösterecekse): iki katmanın atfı birlikte.
        "atif": f"{ayar['sokak_atif']} · {ayar['uydu_atif']}",
        "varsayilan": not kayit,
        "lisans_notu": LISANS_NOTU,
        # Karo sağlayıcıları (OSM) istekte Referer ister. Sayfanın politikası yalnız KÖKENİ
        # (http://<ofis-ip>:8080) gönderir; yol ve sorgu asla gitmez.
        "referrer_policy": "strict-origin-when-cross-origin",
    }


def yaz(conn: sqlite3.Connection, degisiklik: dict, varsayilana_don: bool = False) -> dict:
    if varsayilana_don:
        db.ayar_yaz(conn, AYAR_ANAHTARI, "{}")
    else:
        try:
            mevcut = json.loads(db.ayar_oku(conn, AYAR_ANAHTARI) or "{}")
        except (ValueError, TypeError):
            mevcut = {}
        for alan in ("sokak_url", "uydu_url"):
            if degisiklik.get(alan):
                mevcut[alan] = dogrula(degisiklik[alan])
        for alan in ("sokak_atif", "uydu_atif"):
            if degisiklik.get(alan) is not None:
                metin = str(degisiklik[alan]).strip()[:200]
                if not metin:
                    raise ValueError("Atıf metni boş olamaz (sağlayıcıların lisans şartı).")
                mevcut[alan] = metin
        for alan in ("sokak_en_fazla_zoom", "uydu_en_fazla_zoom"):
            if degisiklik.get(alan) is not None:
                z = int(degisiklik[alan])
                if not 1 <= z <= 22:
                    raise ValueError("En fazla yakınlaştırma 1-22 arası olmalı.")
                mevcut[alan] = z
        db.ayar_yaz(conn, AYAR_ANAHTARI, json.dumps(mevcut, ensure_ascii=False))
    conn.commit()
    sonuc = oku(conn)
    csp_tazele(sonuc)
    return sonuc


# ----------------------------------------------------------------------------- CSP
def _csp(ayar: dict) -> str:
    kaynaklar = []
    for alan in ("sokak_url", "uydu_url"):
        k = _host_kalibi(ayar.get(alan) or "")
        if k and k not in kaynaklar:
            kaynaklar.append(k)
    dis = (" " + " ".join(kaynaklar)) if kaynaklar else ""
    return (
        f"default-src 'self'; img-src 'self' data: blob:{dis}; style-src 'self' 'unsafe-inline'; "
        f"script-src 'self'; worker-src 'self' blob:; connect-src 'self'{dis}; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )


def csp_tazele(ayar: dict | None = None, conn: sqlite3.Connection | None = None) -> None:
    if ayar is None:
        if conn is None:
            return
        ayar = oku(conn)
    _csp_onbellek["metin"] = _csp(ayar)


def csp() -> str:
    """Geçerli CSP başlığı (sunucu açılırken ve altlık değişince tazelenir)."""
    return _csp_onbellek.get("metin") or _csp(VARSAYILAN)
