"""Gösterim (demo) verisini tamamen geri alır — tek komut.

    .venv/Scripts/python.exe -m saha.demo_temizle
    .venv/Scripts/python.exe -m saha.demo_temizle --evet     # soru sormadan

Ne siler
    * ``offline_id`` değeri ``demo-`` ile başlayan bütün ziyaretler
    * bu ziyaretlerin açtığı bugünkü görev listeleri (``notu='Gösterim verisi'``)
    * ``ayar`` tablosundaki ``demo`` anahtarı

Ne silmez
    * binalar, bölgeleme, kullanıcı hesapları ve PIN'ler
    * sahadan gelmiş GERÇEK ziyaretler

Silme bitince ``bina_durum`` tablosu kalan gerçek ziyaretlerden yeniden
hesaplanır: hiç gerçek ziyareti olmayan bina ``bekliyor``a döner, olanların
son durumu son gerçek ziyaretine göre yazılır. Yani gösterim yapıldıktan sonra
sistem, hiç gösterim yapılmamış gibi temiz kalır.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

from . import ayarlar, db
from .demo import AYAR_ANAHTARI, ONEK


def _nokta(n: int) -> str:
    """1257 → "1.257" (Türkçe binlik ayracı)."""
    return f"{n:,}".replace(",", ".")


def _durumlari_yeniden_hesapla(conn: sqlite3.Connection) -> int:
    """``bina_durum`` tablosunu kalan gerçek ziyaretlerden yeniden kurar."""
    etkilenen = conn.execute(
        "UPDATE bina_durum SET durum='bekliyor', son_ziyaret=NULL, son_kullanici_id=NULL, "
        "son_sonuc=NULL, tekrar_tarih=NULL, toplam_satis=0, ziyaret_sayisi=0"
    ).rowcount

    conn.execute(
        "UPDATE bina_durum SET "
        "  toplam_satis  = COALESCE((SELECT SUM(z.satis_adedi) FROM ziyaret z "
        "                            WHERE z.bina_serial=bina_durum.bina_serial AND z.iptal=0), 0), "
        "  ziyaret_sayisi= COALESCE((SELECT COUNT(*) FROM ziyaret z "
        "                            WHERE z.bina_serial=bina_durum.bina_serial AND z.iptal=0), 0)"
    )
    # Her binanın en son gerçek ziyareti (eşitlikte en büyük id).
    conn.execute(
        "UPDATE bina_durum SET "
        "  son_ziyaret      = (SELECT z.zaman        FROM ziyaret z WHERE z.bina_serial=bina_durum.bina_serial AND z.iptal=0 ORDER BY z.zaman DESC, z.id DESC LIMIT 1), "
        "  son_kullanici_id = (SELECT z.kullanici_id FROM ziyaret z WHERE z.bina_serial=bina_durum.bina_serial AND z.iptal=0 ORDER BY z.zaman DESC, z.id DESC LIMIT 1), "
        "  son_sonuc        = (SELECT z.sonuc        FROM ziyaret z WHERE z.bina_serial=bina_durum.bina_serial AND z.iptal=0 ORDER BY z.zaman DESC, z.id DESC LIMIT 1) "
        "WHERE ziyaret_sayisi > 0"
    )
    for sonuc, durum in ayarlar.SONUC_DURUM.items():
        conn.execute("UPDATE bina_durum SET durum=? WHERE son_sonuc=?", (durum, sonuc))
    # Hâlâ açık bir görev listesinde duran binalar "planlı" görünmeli.
    conn.execute(
        "UPDATE bina_durum SET durum='planli' WHERE durum='bekliyor' AND bina_serial IN "
        "(SELECT gb.bina_serial FROM gorev_bina gb JOIN gorev g ON g.id=gb.gorev_id "
        " WHERE g.durum='acik' AND gb.durum='bekliyor')"
    )
    return etkilenen


def temizle(sor: bool = True) -> dict:
    """Otomatik ÇALIŞMAZ (kullanıcı kararı, spec §1.13): silmeden önce doğrulanmış yedek alınır
    ve ``yonetim_kaydi``'na yazılır."""
    from . import goc, yedekle

    ayarlar.konsolu_hazirla()
    conn = db.baglan()
    try:
        try:
            db.semayi_kur(conn)
        except goc.SurumUyumsuz as exc:
            raise SystemExit(exc.mesaj) from exc
        demo_ziyaret = conn.execute(
            "SELECT COUNT(*) FROM ziyaret WHERE offline_id LIKE ?", (ONEK + "%",)
        ).fetchone()[0]
        gercek_ziyaret = conn.execute(
            "SELECT COUNT(*) FROM ziyaret WHERE offline_id NOT LIKE ?", (ONEK + "%",)
        ).fetchone()[0]
        isaret = db.ayar_oku(conn, AYAR_ANAHTARI)

        if not demo_ziyaret and not isaret:
            print("Gösterim verisi bulunamadı — silinecek bir şey yok.")
            return {"ziyaret": 0, "gorev": 0}

        print(f"\n  Silinecek gösterim ziyareti : {demo_ziyaret:,}".replace(",", "."))
        print(f"  Korunacak gerçek ziyaret    : {_nokta(gercek_ziyaret)}")
        if sor:
            cevap = input("\n  Devam edilsin mi? (e/h) ").strip().lower()
            if cevap not in ("e", "evet", "y", "yes"):
                print("  Vazgeçildi — hiçbir şey silinmedi.")
                return {"ziyaret": 0, "gorev": 0, "iptal": True}

        surum = goc.user_version(conn)
        try:
            yedek = yedekle.goc_yedegi(db.db_yolu(), eski=surum, yeni=surum, etiket="demo-temizle")
        except yedekle.YedekHatasi as exc:
            raise SystemExit(f"Yedek alınamadı; hiçbir şey silinmedi. ({exc.mesaj})") from exc
        print(f"  Yedek alındı: {yedek.name}")

        conn.execute("DELETE FROM ziyaret WHERE offline_id LIKE ?", (ONEK + "%",))
        gorevler = [
            s["id"]
            for s in conn.execute(
                "SELECT id FROM gorev WHERE notu='Gösterim verisi'"
            ).fetchall()
        ]
        if gorevler:
            isaretler = ",".join("?" * len(gorevler))
            conn.execute(f"DELETE FROM gorev_bina WHERE gorev_id IN ({isaretler})", gorevler)
            conn.execute(f"DELETE FROM gorev WHERE id IN ({isaretler})", gorevler)

        _durumlari_yeniden_hesapla(conn)
        conn.execute("DELETE FROM ayar WHERE anahtar=?", (AYAR_ANAHTARI,))
        db.yonetim_kaydi(conn, None, "demo_temizle", None,
                         {"ziyaret": demo_ziyaret, "gorev": len(gorevler), "yedek": yedek.name})
        conn.commit()

        kalan_dokunulan = conn.execute(
            "SELECT COUNT(*) FROM bina_durum WHERE son_ziyaret IS NOT NULL"
        ).fetchone()[0]
        ozet = {"ziyaret": demo_ziyaret, "gorev": len(gorevler), "dokunulan": kalan_dokunulan}
    finally:
        conn.close()

    print(f"\n  Temizlendi: {_nokta(ozet['ziyaret'])} ziyaret, "
          f"{ozet['gorev']} görev listesi.")
    print(f"  Dokunulmuş bina (gerçek): {_nokta(ozet['dokunulan'])}\n")
    return ozet


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Saha Sistemi gösterim verisini siler")
    ayrac.add_argument("--evet", action="store_true", help="Onay sormadan siler")
    a = ayrac.parse_args(argv)
    temizle(sor=not a.evet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
