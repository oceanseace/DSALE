"""Ofis bilgisayarında sunucuyu başlatır (geliştirmede ``kod/saha/GELISTIRME_BASLAT.bat`` çağırır).

    PYTHONPATH=kod .venv/Scripts/python.exe -m saha.sunucu                 # 0.0.0.0:8080 (ofis ağı)
    PYTHONPATH=kod .venv/Scripts/python.exe -m saha.sunucu --host 127.0.0.1 --port 8090

Ekrana telefonlardan yazılacak adresi basar, dönüşümlü günlük tutar
(çalışma klasöründe ``saha/kayit/saha.log``, 2 MB × 5 dosya). Dışarı hiçbir şey açılmaz: bağlanılacak
adres ofis ağındaki yerel IP'dir.
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys
from logging.handlers import RotatingFileHandler

from . import SURUM, ayarlar, db, goc


def yerel_ipler() -> list[str]:
    """Bu bilgisayarın ofis ağındaki IPv4 adresleri."""
    adresler: list[str] = []
    try:  # varsayılan çıkış arabirimi (paket gönderilmez)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            adresler.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for bilgi in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = bilgi[4][0]
            if ip not in adresler and not ip.startswith("127."):
                adresler.append(ip)
    except OSError:
        pass
    return adresler or ["127.0.0.1"]


def port_dolu_mu(port: int) -> bool:
    """Bu portta zaten bir şey dinliyor mu?

    Amaç, "iki kez tıklandı" durumunu uvicorn çökmeden önce yakalamak.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.6)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def kaydi_kur(seviye: str = "info") -> None:
    """Kök günlüğü kurar: dönüşümlü dosya + konsol.

    uvicorn ``log_config=None`` ile çağrıldığı için kendi ayarını dayatmaz;
    uvicorn'un kayıtları da buraya düşer.
    """
    ayarlar.KAYIT_DIZINI.mkdir(parents=True, exist_ok=True)
    bicim = logging.Formatter("%(asctime)s  %(levelname)-7s %(name)-18s %(message)s")

    dosya = RotatingFileHandler(
        ayarlar.KAYIT_DIZINI / "saha.log", maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    dosya.setFormatter(bicim)
    konsol = logging.StreamHandler()
    konsol.setFormatter(bicim)

    kok = logging.getLogger()
    kok.setLevel(getattr(logging, seviye.upper(), logging.INFO))
    for eski in list(kok.handlers):
        kok.removeHandler(eski)
    kok.addHandler(dosya)
    kok.addHandler(konsol)
    for ad in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        gunluk = logging.getLogger(ad)
        gunluk.handlers.clear()
        gunluk.propagate = True


def yaz(*parcalar) -> None:
    """Ekrana basar ve tamponu HEMEN boşaltır.

    Ofis bilgisayarında bu pencerede okunacak tek şey telefonlara yazılacak
    adrestir; çıktı bir dosyaya yönlendirilmişse tamponda kalıp görünmemesi
    kabul edilemez.
    """
    print(*parcalar, flush=True)


def _veritabani_kontrol() -> bool:
    yol = db.db_yolu()
    if not yol.exists():
        yaz("Veritabanı yok. Önce şunu çalıştırın:  python -m saha.kur")
        return False
    conn = db.baglan(yol)
    try:
        sayi = conn.execute("SELECT COUNT(*) FROM bina").fetchone()[0]
    except Exception:
        yaz("Veritabanı okunamadı. Şunu çalıştırın:  python -m saha.kur")
        return False
    finally:
        conn.close()
    if sayi == 0:
        yaz("Veritabanında bina yok. Şunu çalıştırın:  python -m saha.kur")
        return False
    # Göç BURADA yapılmaz: port denetiminden sonra, doğrulanmış yedekle ``_guncelle`` yapar.
    yaz(f"Veritabanı hazır: {sayi:,} bina".replace(",", "."))
    return True


def _guncelle() -> bool:
    """Şemayı hedef sürüme taşır (spec §1.2): kilit → yedek → göç → son denetim.

    Hata olursa sunucu AÇILMAZ; çerçeveli Türkçe mesaj veritabanının değişip değişmediğini söyler.
    """
    try:
        rapor = goc.hazirla(db.db_yolu())
    except goc.GocHatasi as exc:
        yaz("\n" + goc.hata_metni(exc) + "\n")
        logging.getLogger("saha.sunucu").error("Güncelleme durdu: %s", exc.mesaj)
        return False
    for satir in rapor.satirlar:
        yaz(satir)
        logging.getLogger("saha.sunucu").info(satir)
    return True


def _adres_yaz(host: str, port: int) -> None:
    """Telefonlara yazılacak adresi hem ekrana hem günlüğe basar."""
    cizgi = "=" * 62
    satirlar = [cizgi, f"  SAHA SİSTEMİ {SURUM} — sunucu çalışıyor", cizgi]
    adresler = []
    if host in ("0.0.0.0", "::"):
        adresler = [f"http://{ip}:{port}" for ip in yerel_ipler()]
        satirlar.append("  Telefonlardan açılacak adres (ofis wifi'sine bağlıyken):")
        satirlar += [f"      {a}" for a in adresler]
        satirlar += ["", "  Bu bilgisayardan:", f"      http://localhost:{port}"]
        if len(adresler) > 1:
            satirlar += [
                "",
                "  DİKKAT: bu bilgisayarda birden çok ağ arayüzü var; sunucu",
                "  HEPSİNDE dinliyor. Yalnız ofis ağında görünmesini istiyorsanız:",
                f"      python -m saha.sunucu --host <ofis-ip> --port {port}",
            ]
        satirlar += [
            "",
            "  Bağlantı şifresiz (http). Ofis ağı dışına AÇMAYIN; sahadan erişim",
            "  gerekiyorsa belgeler/SAHA_KULLANIM.md §8'deki VPN yolunu izleyin.",
        ]
    else:
        adresler = [f"http://{host}:{port}"]
        satirlar.append(f"  Adres: http://{host}:{port}")
    satirlar += [
        "",
        "  Telefonda: adresi aç, paylaş menüsünden 'Ana Ekrana Ekle' deyin.",
        "  Kapatmak için bu pencerede Ctrl+C (ya da saha\\DURDUR.bat).",
        f"  Günlük: {ayarlar.KAYIT_DIZINI / 'saha.log'}",
        cizgi,
    ]
    yaz("\n" + "\n".join(satirlar) + "\n")
    # Pencere kapanırsa ya da metin yukarı kayarsa adres günlükte kalsın.
    logging.getLogger("saha.sunucu").info(
        "Sunucu açıldı — telefon adresi: %s", " | ".join(adresler) or f"{host}:{port}"
    )


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Saha Sistemi sunucusu")
    ayrac.add_argument("--host", default="0.0.0.0", help="Dinlenecek adres (varsayılan: ofis ağı)")
    ayrac.add_argument("--port", type=int, default=8080)
    ayrac.add_argument("--seviye", default="info", help="Günlük seviyesi: debug|info|warning")
    a = ayrac.parse_args(argv)
    ayarlar.konsolu_hazirla()

    # 1) Port: sunucu zaten açıksa veritabanına HİÇ dokunulmaz (göç dahil).
    if port_dolu_mu(a.port):
        cizgi = "=" * 62
        yaz(f"\n{cizgi}")
        yaz("  SAHA SİSTEMİ ZATEN ÇALIŞIYOR — yeni bir tane açmaya gerek yok.")
        yaz(cizgi)
        if a.host in ("0.0.0.0", "::"):
            for ip in yerel_ipler():
                yaz(f"      http://{ip}:{a.port}")
        else:
            yaz(f"      http://{a.host}:{a.port}")
        yaz("\n  Bu pencereyi kapatabilirsiniz.")
        yaz("  Sunucuyu gerçekten durdurmak için:  saha\\DURDUR.bat")
        yaz(f"{cizgi}\n")
        return 2            # baslat.bat bunu "hata" değil "zaten açık" sayar

    # 2) Dosya var mı, bina var mı.
    if not _veritabani_kontrol():
        return 1

    # 3) Şema güncellemesi (yalnız burada; tek uvicorn süreci, --workers yok).
    kaydi_kur(a.seviye)
    if not _guncelle():
        return 3
    _adres_yaz(a.host, a.port)

    import uvicorn  # ağır; yalnız sunucu başlarken yüklenir

    uvicorn.run("saha.api:app", host=a.host, port=a.port, log_level=a.seviye,
                access_log=True, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
