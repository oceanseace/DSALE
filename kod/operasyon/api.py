"""İş emri uçları — /api/is-emri/*  (yalnız yönetici).

BOSS "Teknik Task Detay Raporu" yüklenir → kurulum / 2. donanım satırları çıkar → mahalle ve konum
çözülür → kullanıcının öbekleri uygulanır. Öbekler burada tanımlanır; filtrelenen işler yakınlığa
göre dengeli parçalara bölünür; sonuç Excel olarak alınır.

saha/api.py bağlar (statik PWA bağlamasından ÖNCE):
    from operasyon.api import yonlendirici as is_emri_yonlendirici
    uygulama.include_router(is_emri_yonlendirici(yonetici))

Kişisel veri: müşteri adı / numarası / telefonu API yanıtına konmaz; adres yalnız yönetici
ekranında kontrol için gider. Son yükleme yerel diskte tutulur (operasyon/veri/, git dışı).
"""
from __future__ import annotations

import datetime as dt
import io
import os
import pickle
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import is_emri as ie
from . import yakinlik

VERI_DIZINI = Path(os.environ.get("OPERASYON_VERI") or ie.VERI_DIZINI)
OBEK_DOSYASI = Path(os.environ.get("OPERASYON_OBEK") or ie.OBEK_DOSYASI)
AZAMI_BOYUT = 25 * 1024 * 1024
AZAMI_PARCA = 30


def _hata(durum: int, mesaj: str, kod: str) -> HTTPException:
    return HTTPException(status_code=durum, detail={"hata": mesaj, "kod": kod})


@dataclass
class Yukleme:
    dosya: str
    zaman: str
    sonuc: ie.Sonuc
    parca: dict = field(default_factory=dict)      # iş id -> parça adı (bugünkü bölme)


class _Depo:
    """Son yükleme + öbek tanımları. Tek yönetici ekranı için basit kilitli bellek + disk."""

    def __init__(self):
        self.kilit = threading.RLock()
        self._yukleme: Yukleme | None = None
        self._okundu = False

    @property
    def dosya(self) -> Path:
        return VERI_DIZINI / "son_yukleme.pkl"

    def yukleme(self) -> Yukleme | None:
        with self.kilit:
            if not self._okundu:
                self._okundu = True
                try:
                    if self.dosya.exists():
                        self._yukleme = pickle.loads(self.dosya.read_bytes())
                except Exception:              # noqa: BLE001 — bozuk/eski dosya: yok say
                    self._yukleme = None
            return self._yukleme

    def kaydet(self, y: Yukleme | None) -> None:
        with self.kilit:
            self._yukleme, self._okundu = y, True
            VERI_DIZINI.mkdir(parents=True, exist_ok=True)
            if y is None:
                self.dosya.unlink(missing_ok=True)
                return
            gecici = tempfile.NamedTemporaryFile(dir=VERI_DIZINI, delete=False, suffix=".tmp")
            with gecici:
                gecici.write(pickle.dumps(y))
            os.replace(gecici.name, self.dosya)

    def obekler(self) -> ie.Obekler:
        return ie.Obekler.yukle(OBEK_DOSYASI)


DEPO = _Depo()


# --------------------------------------------------------------------------- yardımcılar
def _obekleri_uygula(y: Yukleme, o: ie.Obekler) -> None:
    d = y.sonuc.isler
    d["Öbek"] = [o.bul(il, ilce, mh) or "" for il, ilce, mh in
                 zip(d[ie.SUTUNLAR["il"]].fillna(""), d[ie.SUTUNLAR["ilce"]].fillna(""), d["Mahalle"])]
    y.sonuc.ozet["obekli"] = int((d["Öbek"] != "").sum())


def _tarih(v) -> str | None:
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return None
    return str(v)[:16]


def _sayi(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else round(float(v), 6)


def _yanit(y: Yukleme | None, o: ie.Obekler) -> dict:
    if y is None:
        return {"yukleme": None, "isler": [], "obekler": o.tanimlar, "mahalleler": []}
    d = y.sonuc.isler
    S = ie.SUTUNLAR

    def kol(ad):
        return d[ad] if ad in d.columns else pd.Series([None] * len(d), index=d.index)

    isler = []
    for i, task_no, task, durum, ekip, il, ilce, mh, obek, lat, lon, kk, mk, notu, bilgi, yer, bas, rnd, adres, lok in zip(
            d.index, kol("Task No"), d[S["task"]], kol("Task Durumu"), kol("Ekip"), d[S["il"]], d[S["ilce"]],
            d["Mahalle"], d["Öbek"], d["Enlem"], d["Boylam"], d["Konum Kaynağı"], d["Mahalle Kaynağı"],
            d["Kontrol Notu"], kol("Bilgi"), d["_yer"], kol("Task Başlangıç Tarihi"), kol("Randevu Başlangıç Tarihi"),
            d[S["adres"]], kol(S["lokasyon"])):
        isler.append({
            "id": int(i), "task_no": task_no if isinstance(task_no, str) else None, "task": task or "",
            "durum": durum if isinstance(durum, str) else "", "ekip": ekip if isinstance(ekip, str) else "",
            "il": il or "", "ilce": ilce or "", "mahalle": mh, "obek": obek,
            "lat": _sayi(lat), "lon": _sayi(lon), "konum": kk, "mahalle_kaynak": mk, "not": notu,
            "bilgi": bilgi if isinstance(bilgi, str) else "", "yer": yer,
            "baslangic": _tarih(bas), "randevu": _tarih(rnd),
            "adres": adres if isinstance(adres, str) else "", "lokasyon": lok if isinstance(lok, str) else None,
            "parca": y.parca.get(int(i)),
        })
    # mahalle tablosu (öbek tanımlamak için)
    g = {}
    for j in isler:
        if not j["mahalle"]:
            continue
        k = (j["il"], j["ilce"], j["mahalle"])
        r = g.setdefault(k, {"il": k[0], "ilce": k[1], "mahalle": k[2], "is": 0, "obek": j["obek"],
                             "_lat": [], "_lon": []})
        r["is"] += 1
        if j["lat"] is not None:
            r["_lat"].append(j["lat"])
            r["_lon"].append(j["lon"])
    mahalleler = []
    for r in g.values():
        la, lo = r.pop("_lat"), r.pop("_lon")
        r["lat"] = round(float(np.mean(la)), 6) if la else None
        r["lon"] = round(float(np.mean(lo)), 6) if lo else None
        mahalleler.append(r)
    mahalleler.sort(key=lambda r: (r["il"], r["ilce"], -r["is"]))
    return {
        "yukleme": {"dosya": y.dosya, "zaman": y.zaman, "ozet": y.sonuc.ozet, "sure_sn": y.sonuc.sure_sn},
        "isler": isler,
        "obekler": o.tanimlar,
        "mahalleler": mahalleler,
    }


# --------------------------------------------------------------------------- girdiler
class ObekIslemi(BaseModel):
    islem: str = Field(pattern="^(ata|cikar|sil|ad)$")
    ad: str | None = Field(default=None, max_length=80)
    yeni_ad: str | None = Field(default=None, max_length=80)
    mahalleler: list[str] = Field(default_factory=list, max_length=2000)   # "İl/İlçe/Mahalle"


class BolmeIstegi(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=20000)
    k: int = Field(ge=1, le=AZAMI_PARCA)
    birim: str = Field(default="bina", pattern="^(bina|mahalle)$")
    ad: str | None = Field(default=None, max_length=80)


class ParcaKaydi(BaseModel):
    atama: dict[int, str | None] = Field(default_factory=dict)   # iş id -> parça adı (None: temizle)
    temizle: bool = False                                          # önce bütün parçaları sil
    obek_olarak: list[dict] | None = None      # birim=mahalle bölmesinde: [{"ad":..., "mahalleler":[ref]}]
    eski_obek: str | None = None               # obek_olarak verilirse bu öbek silinir (yerine parçalar gelir)


# --------------------------------------------------------------------------- uçlar
def yonlendirici(yonetici_bagimliligi) -> APIRouter:
    r = APIRouter(prefix="/api/is-emri", dependencies=[Depends(yonetici_bagimliligi)])

    @r.get("")
    def durum():
        return _yanit(DEPO.yukleme(), DEPO.obekler())

    @r.post("/yukle")
    async def yukle(istek: Request):
        govde = await istek.body()
        if not govde:
            raise _hata(400, "Dosya boş.", "bos_dosya")
        if len(govde) > AZAMI_BOYUT:
            raise _hata(413, "Dosya 25 MB'tan büyük.", "buyuk_dosya")
        ad = unquote(istek.headers.get("x-dosya-adi", "rapor.xlsx"))[:200]
        try:
            df = ie.raporu_oku(io.BytesIO(govde))
        except ValueError as e:
            raise _hata(400, str(e), "rapor_tanınmadı") from e
        except Exception as e:                 # noqa: BLE001 — Excel değil / bozuk
            raise _hata(400, "Dosya okunamadı. BOSS'tan indirilen .xlsx dosyasını seçin.", "okunamadi") from e
        with DEPO.kilit:
            o = DEPO.obekler()
            s = ie.hazirla(df, o)
            y = Yukleme(dosya=ad, zaman=dt.datetime.now().isoformat(timespec="seconds"), sonuc=s)
            DEPO.kaydet(y)
            return _yanit(y, o)

    @r.post("/obek")
    def obek(girdi: ObekIslemi):
        with DEPO.kilit:
            o = DEPO.obekler()
            ad = (girdi.ad or "").strip()
            if girdi.islem == "ata":
                if not ad or not girdi.mahalleler:
                    raise _hata(400, "Öbek adı ve en az bir mahalle gerekli.", "eksik")
                o.ata(ad, girdi.mahalleler)
            elif girdi.islem == "cikar":
                o.cikar(girdi.mahalleler)
            elif girdi.islem == "sil":
                o.sil(ad)
            elif girdi.islem == "ad":
                yeni = (girdi.yeni_ad or "").strip()
                if not ad or not yeni:
                    raise _hata(400, "Eski ve yeni ad gerekli.", "eksik")
                o.yeniden_adlandir(ad, yeni)
            o.kaydet(OBEK_DOSYASI)
            y = DEPO.yukleme()
            if y is not None:
                _obekleri_uygula(y, o)
                DEPO.kaydet(y)
            return _yanit(y, o)

    @r.post("/bol")
    def bol(girdi: BolmeIstegi):
        y = DEPO.yukleme()
        if y is None:
            raise _hata(404, "Önce BOSS raporunu yükleyin.", "yukleme_yok")
        d = y.sonuc.isler
        ids = [i for i in dict.fromkeys(girdi.ids) if i in d.index]
        if not ids:
            raise _hata(400, "Seçili iş yok.", "bos")
        x = d.loc[ids]
        grup = x["_yer"] if girdi.birim == "bina" else (
            x[ie.SUTUNLAR["il"]].fillna("") + "/" + x[ie.SUTUNLAR["ilce"]].fillna("") + "/" + x["Mahalle"])
        grup = [g or f"tek:{i}" for g, i in zip(grup, x.index)]
        et = yakinlik.dengeli_bol(x["Enlem"].to_numpy(float), x["Boylam"].to_numpy(float), girdi.k, grup=grup)
        oz = {p["parca"]: p for p in yakinlik.parca_ozeti(x["Enlem"].to_numpy(float),
                                                          x["Boylam"].to_numpy(float), et)}
        kok = (girdi.ad or "Parça").strip()
        parcalar = []
        for p in sorted(set(et.tolist())):
            s = et == p
            mh = x.loc[s, [ie.SUTUNLAR["il"], ie.SUTUNLAR["ilce"], "Mahalle"]].fillna("")
            refler = sorted({ie._ref(a, b, c) for a, b, c in mh.itertuples(index=False, name=None) if c})
            parcalar.append({
                "parca": int(p), "ad": f"{kok}-{p}" if p else "Konumsuz",
                "is": int(s.sum()), "mahalleler": refler,
                "merkez": oz.get(p, {}).get("merkez"), "yaricap_km": oz.get(p, {}).get("yaricap_km"),
                "ort_km": oz.get(p, {}).get("ort_km"),
            })
        return {"atama": {int(i): int(p) for i, p in zip(x.index, et)}, "parcalar": parcalar,
                "birim": girdi.birim, "k": girdi.k}

    @r.post("/parca")
    def parca(girdi: ParcaKaydi):
        with DEPO.kilit:
            y = DEPO.yukleme()
            if y is None:
                raise _hata(404, "Önce BOSS raporunu yükleyin.", "yukleme_yok")
            if girdi.temizle:
                y.parca = {}
            for i, ad in girdi.atama.items():
                if ad:
                    y.parca[int(i)] = ad.strip()[:80]
                else:
                    y.parca.pop(int(i), None)
            o = DEPO.obekler()
            if girdi.obek_olarak:
                if girdi.eski_obek:
                    o.sil(girdi.eski_obek)
                for t in girdi.obek_olarak:
                    if t.get("ad") and t.get("mahalleler"):
                        o.ata(str(t["ad"]).strip()[:80], [str(m) for m in t["mahalleler"]])
                o.kaydet(OBEK_DOSYASI)
                _obekleri_uygula(y, o)
            DEPO.kaydet(y)
            return _yanit(y, o)

    @r.get("/excel")
    def excel():
        y = DEPO.yukleme()
        if y is None:
            raise _hata(404, "Önce BOSS raporunu yükleyin.", "yukleme_yok")
        s = y.sonuc
        isler = s.isler.copy()
        if y.parca:
            isler.insert(list(isler.columns).index("Öbek") + 1, "Parça",
                         [y.parca.get(int(i), "") for i in isler.index])
        tampon = io.BytesIO()
        ie.excel_yaz(ie.Sonuc(isler, s.cikarilan, s.ozet, s.sure_sn), tampon)
        ad = Path(y.dosya).stem + "_hazir.xlsx"
        return Response(tampon.getvalue(),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{_url(ad)}",
                                 "Cache-Control": "no-store"})

    return r


def _url(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")
