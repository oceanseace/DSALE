"""Ofis bilgisayarında komut satırından veri işleri (yönetici ekranı hazır olmasa da çalışır).

    .venv\\Scripts\\python.exe -m saha.veri_araci tur  D:\\indirilen\\data.xlsx          # farkı göster
    .venv\\Scripts\\python.exe -m saha.veri_araci tur  D:\\indirilen\\data.xlsx --uygula # uygula
    .venv\\Scripts\\python.exe -m saha.veri_araci bekleyen                              # bekleyen_idler.txt
    .venv\\Scripts\\python.exe -m saha.veri_araci onemap D:\\indirilen\\onemap_yeni.json  # yeni binaları ekle
    .venv\\Scripts\\python.exe -m saha.veri_araci bolge 14                              # 14 bölgelik önizleme
    .venv\\Scripts\\python.exe -m saha.veri_araci bolge 14 --uygula                     # uygula
    .venv\\Scripts\\python.exe -m saha.veri_araci bolge --geri-al                       # önceki plana dön
    .venv\\Scripts\\python.exe -m saha.veri_araci excel                                 # bölgeleme Excel'i
    .venv\\Scripts\\python.exe -m saha.veri_araci kalite                                # veri kalitesi özeti

API'deki uçlarla (belgeler/SAHA_SOZLESME.md §7) BİREBİR aynı işlevleri çağırır; sunucu
açıkken de güvenle çalışır (SQLite WAL, her yazma tek işlem).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import ayarlar, bolgeleme, db, tur_raporu, veri_kalitesi


def _b(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _y(oran: float, ondalik: int = 1, isaret: bool = False) -> str:
    """Türkçe yüzde: 0.465 → %46,5 · -0.0008 → %-0,08"""
    bicim = ("+" if isaret else "") + f".{ondalik}f"
    return "%" + format(oran * 100, bicim).replace(".", ",")


def _yonetici_id(conn) -> int | None:
    r = conn.execute("SELECT id FROM kullanici WHERE rol='yonetici' AND aktif=1 ORDER BY id LIMIT 1").fetchone()
    return int(r[0]) if r else None


def tur(conn, yol: Path, uygula: bool, pasif_onay: bool) -> int:
    p = tur_raporu.yukle(conn, yol.read_bytes(), yol.name, _yonetici_id(conn))
    f = p["fark"]
    print(f"Tur raporu okundu: {_b(p['okuma']['tekil_bina'])} bina ({p['okuma']['sayfa']} sayfası) · kayıt no {p['tur_id']}")
    print(f"  Yeni bina        : {_b(f['yeni_bina'])}   (hizmet dışı il: {_b(f['yeni_bina_il_disi'])})")
    print(f"  Rapordan çıkan   : {_b(f['cikan_bina'])}   (pasife alınacak)")
    print(f"  Sayısı değişen   : {_b(f['degisen_bina'])}")
    print(f"  Geri dönen       : {_b(f['geri_donen_bina'])}")
    for a in ("bina", "res_hp", "aktif_res", "firsat"):
        print(f"  {a:<16} : {_b(f['once'][a])} → {_b(f['sonra'][a])}")
    for u in f["uyarilar"]:
        print(f"  ! {u}")
    if not uygula:
        print("\nHenüz hiçbir şey değişmedi. Uygulamak için aynı komutu --uygula ile çalıştırın.")
        return 0
    s = tur_raporu.uygula(conn, p["tur_id"], _yonetici_id(conn), pasif_onay=pasif_onay)
    print("\n" + s["mesaj"])
    return 0


def bekleyen(conn, cikti: Path) -> int:
    kimlikler = tur_raporu.bekleyen_kimlikler(conn)
    cikti.write_text("\n".join(kimlikler) + ("\n" if kimlikler else ""), encoding="utf-8")
    print(f"{len(kimlikler)} bina konum bekliyor → {cikti}")
    if kimlikler:
        print("Sıradaki adım: belgeler/SAHA_KULLANIM.md §12 (OneMap aracı).")
    return 0


def onemap(conn, yol: Path) -> int:
    ham = yol.read_bytes()
    s = tur_raporu.onemap_yukle(conn, json.loads(ham.decode("utf-8-sig")), _yonetici_id(conn), ham)
    print(s["mesaj"])
    if s["eslesmeyen"]:
        print(f"  {s['eslesmeyen']} OneMap kaydı bekleyen hiçbir binayla eşleşmedi (yok sayıldı).")
    return 0


def bolge(conn, n: int | None, olcu: str, uygula: bool, pasiflestir: bool, geri: bool) -> int:
    if geri:
        print(bolgeleme.geri_al(conn, _yonetici_id(conn))["mesaj"])
        return 0
    if not n:
        d = bolgeleme.durum(conn)
        print(f"Bugün {d['n']} bölge. " + " · ".join(
            f"{b['bolge']}: {_b(b['bina'])} bina, {_y(b['dokunulan_oran'], 0)} dokunuldu" for b in d["bolgeler"]))
        return 0
    binalar = bolgeleme._binalar(conn)
    plan = bolgeleme.plan_bul(binalar, n, olcu)
    if plan is None:
        print(f"{n} bölgelik hazır plan yok; güncel veriyle hesaplanıyor (yaklaşık "
              f"{round(bolgeleme._beklenen_sure(n))} sn)...")
        is_ = bolgeleme.hesap_baslat(n, olcu)
        while (j := bolgeleme.is_durumu(is_["is_id"]))["durum"] not in ("bitti", "hata"):
            time.sleep(1)
        if j["durum"] == "hata":
            print(j["mesaj"])
            return 1
        binalar = bolgeleme._binalar(conn)
        plan = bolgeleme.plan_bul(binalar, n, olcu)
    on = bolgeleme.onizle(conn, plan, binalar)
    f = on["fark"]
    print(f"{n} bölgelik plan ({on['kaynak_ad']}) · denge {_y(on['denge']['sapma_min'], 2, True)} / "
          f"{_y(on['denge']['sapma_maks'], 2, True)}")
    for b in on["bolgeler"]:
        kim = ", ".join(s["ad"] for s in b["satiscilar"]) or "(yeni satışçı açılacak)"
        print(f"  {b['bolge']:>2}. {b['ad'][:44]:<44} {_b(b['bina']):>6} bina  {_b(b['res_hp']):>7} RES HP  {kim}")
    print(f"  El değiştiren bina: {_b(f['el_degistiren_bina'])} ({_y(f['el_degistiren_oran'])}) · "
          f"ziyaret geçmişi olan: {_b(f['el_degistiren_dokunulmus_bina'])}")
    for u in on["uyarilar"]:
        print(f"  ! {u}")
    if not uygula:
        print("\nHenüz hiçbir şey değişmedi. Uygulamak için --uygula ekleyin.")
        return 0
    s = bolgeleme.uygula(conn, on["plan_ref"], n, _yonetici_id(conn), pasiflestir=pasiflestir)
    print("\n" + s["mesaj"])
    for h in s["yeni_satiscilar"]:
        print(f"  Yeni yer tutucu: {h['ad']} · {h['telefon_goster']} · davet kodu {h['davet_kodu']}")
    for h in s["bolgesiz_kalan"]:
        print(f"  Bölgesiz kaldı: {h['ad']} (eski bölge {h['eski_bolge']}) — Ekip ekranından bölge verin.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ayrac = argparse.ArgumentParser(description="Saha Sistemi veri işleri (tur raporu, OneMap, bölge planı).")
    ayrac.add_argument("--db", default=None, help="Veritabanı (varsayılan: saha/saha.db)")
    alt = ayrac.add_subparsers(dest="komut", required=True)
    t = alt.add_parser("tur", help="Tur raporunu (data.xlsx) karşılaştır / uygula")
    t.add_argument("dosya")
    t.add_argument("--uygula", action="store_true")
    t.add_argument("--pasif-onay", action="store_true", help="Raporda olmayan binaların %%10'dan fazlası pasife alınacaksa")
    b = alt.add_parser("bekleyen", help="Konum bekleyen binaların kimlik listesini yaz")
    b.add_argument("--cikti", default="bekleyen_idler.txt")
    o = alt.add_parser("onemap", help="OneMap aracının indirdiği onemap_yeni.json'u yükle")
    o.add_argument("dosya")
    g = alt.add_parser("bolge", help="Bölge planı: önizle / uygula / geri al")
    g.add_argument("n", nargs="?", type=int)
    g.add_argument("--olcu", default="res_hp", choices=bolgeleme.OLCULER)
    g.add_argument("--uygula", action="store_true")
    g.add_argument("--pasiflestir", action="store_true", help="Bölgesi kalmayan satışçıları pasife al")
    g.add_argument("--geri-al", action="store_true")
    alt.add_parser("excel", help="Etkin bölge planının açıklayıcı Excel'i")
    alt.add_parser("kalite", help="Veri kalitesi özeti")
    a = ayrac.parse_args(argv)
    ayarlar.konsolu_hazirla()
    from . import goc

    conn = db.baglan(Path(a.db) if a.db else None)
    try:
        # Göç burada YAPILMAZ (yalnız sunucu açılışında); sürüm uymuyorsa araç durur.
        try:
            db.semayi_kur(conn)
        except goc.SurumUyumsuz as exc:
            print(exc.mesaj)
            return 3
        veri_kalitesi.hazirla(conn)
        if a.komut == "tur":
            return tur(conn, Path(a.dosya), a.uygula, a.pasif_onay)
        if a.komut == "bekleyen":
            return bekleyen(conn, Path(a.cikti))
        if a.komut == "onemap":
            return onemap(conn, Path(a.dosya))
        if a.komut == "bolge":
            return bolge(conn, a.n, a.olcu, a.uygula, a.pasiflestir, a.geri_al)
        if a.komut == "excel":
            yol, _ = bolgeleme.excel_yolu(conn)
            print(f"Excel hazır: {yol}")
            return 0
        if a.komut == "kalite":
            o = veri_kalitesi.ozet(conn)
            print(f"{_b(o['toplam_bina'])} bina · {_b(o['bayrakli_bina'])} binada bulgu")
            for k in o["kurallar"]:
                if k["adet"]:
                    ek = f" · {_b(k['duzeltilen'])} düzeltildi" if k["duzeltilen"] else ""
                    print(f"  {k['ad']:<32} {_b(k['adet']):>7}{ek}")
            return 0
    except (bolgeleme.PlanHatasi, tur_raporu.TurHatasi) as exc:
        print(f"HATA: {exc.mesaj}")
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
