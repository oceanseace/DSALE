"""N satışçıya dengeli + kompakt coğrafi bölgeleme.

Yöntem: kapasite kısıtlı güç diyagramı (capacity-constrained power diagram,
"dengeli k-means"):

1. Birim: site grubu (aynı sitenin blokları hiç bölünmez) ya da tekil bina.
2. Başlangıç: ağırlıklı k-means++ ile N merkez (birden çok tohumla denenir).
3. Atama: her birim `mesafe² − ψ_k` değeri en küçük olan merkeze gider. ψ_k
   bölgenin "çekim gücü"dür; her bölgenin yükü hedefe eşitlenecek şekilde bulunur.
   Bu kural bölgeleri dışbükey ve iç içe geçmeyen alanlar yapar.
4. Merkezler bölgenin ağırlık merkezine taşınır; merkezler 5 m'den az oynayana
   kadar tekrarlanır.
5. Tohumlar arasından en kısa toplam mesafeli, denge şartını sağlayan sonuç seçilir.
6. N > 12 ise hiyerarşik: önce ≈√N büyük gruba (grup başına bölge sayısıyla orantılı
   hedefle), sonra her grup kendi içinde eşit parçalara bölünür.
7. **Cila (2.5):** sınır birimleri serbest bırakılıp tam bir taşıma LP'si (HiGHS)
   çözülür; kesirli kalan ağır birimler sabitlenip LP yinelenir; kalan sapma
   açgözlü sınır takasıyla kapatılır. Hedef: N=8'de ≤ ±%0,5, her N'de ≤ ±%1.
8. **Ada onarımı (2.5):** bütün yakın komşuları başka bir bölgede olan ve kendi
   bölgesine 1 km'den uzak kalan birim o komşu bölgeye verilir (LP dengeyi korur).

ψ'ler entropik yarı-ayrık optimal taşıma dualinin L-BFGS ile çözülmesiyle bulunur;
son adımda ayrık bir cila (Jacobi) uygulanır.

Aynı veri + aynı parametre => her zaman aynı sonuç (deterministik; HiGHS ve L-BFGS
aynı girdiyle aynı çıktıyı verir).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .enrich import M_PER_DEG_LAT, _m_per_deg_lon

ALGORITMA_SURUMU = "CCPD-2.5"
DOGRUDAN_UST_SINIR = 12

# LP cilası: serbest bırakılan sınır birimi sayısı ve birim başına aday bölge sütunu
LP_SERBEST_TABAN = 400
LP_SERBEST_KATSAYI = 40           # N başına
LP_SERBEST_TAVAN = 1600
LP_SUTUN = 8
LP_SURE_SINIRI = 20.0             # tek LP çözümü için üst süre (sn); aşılırsa cila atlanır
LP_TOPLAM_SURE = 45.0             # yuvarlama turlarının tamamı için üst süre (sn)
DENGE_TOLERANSI = 0.003           # açgözlü takasın durma eşiği (±%0,3)


@dataclass
class Sonuc:
    n: int
    olcu: str
    atama: pd.Series                 # bina_serial -> bölge no (1..N)
    merkezler: np.ndarray            # (N, 2) lon/lat, bölge sırasıyla
    hedef: float
    yukler: np.ndarray               # bölge sırasıyla
    maliyet: float
    sure_sn: float
    parametreler: dict = field(default_factory=dict)
    anlik: list = field(default_factory=list)          # sunum animasyonu: ara adım merkezleri (lon/lat)
    anlik_etiket: list = field(default_factory=list)   # aynı adımların birim→bölge etiketleri (metin)


def _birimler(df: pd.DataFrame, olcu: str, lat0: float, lon0: float) -> pd.DataFrame:
    g = df.groupby("site_grup", sort=True)
    u = pd.DataFrame({
        "lat": g["lat"].mean(),
        "lon": g["lon"].mean(),
        "b": g[olcu].sum().astype(float),
    })
    u["x"] = (u["lon"] - lon0) * _m_per_deg_lon(lat0) / 1000.0
    u["y"] = (u["lat"] - lat0) * M_PER_DEG_LAT / 1000.0
    return u


def _kmeanspp(X: np.ndarray, w: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    C = [X[rng.choice(len(X), p=w / w.sum())]]
    d2 = ((X - C[0]) ** 2).sum(1)
    for _ in range(1, n):
        q = w * d2
        C.append(X[rng.choice(len(X), p=q / q.sum())])
        d2 = np.minimum(d2, ((X - C[-1]) ** 2).sum(1))
    return np.array(C)


def _esik(t: np.ndarray, b: np.ndarray, hedef: float) -> float:
    """t_i < ψ olan birimlerin toplam ağırlığı hedefe en yakın olacak ψ."""
    sira = np.argsort(t, kind="stable")
    kum = np.cumsum(b[sira])
    j = int(np.searchsorted(kum, hedef))
    if j >= len(t):
        return float(t[sira[-1]]) + 1e-6
    once = kum[j - 1] if j > 0 else 0.0
    ust = float(t[sira[j]])
    alt = float(t[sira[j - 1]]) if j > 0 else ust - 1.0
    return ust + 1e-9 if abs(kum[j] - hedef) < abs(once - hedef) else (alt + ust) / 2


def _dengeli_ata(D2: np.ndarray, b: np.ndarray, H: np.ndarray, psi: np.ndarray,
                 max_tur: int, plato: int = 15, tol: float = 0.004):
    """Ayrık cila: ψ'leri bölge bölge tam çözerek (Jacobi, sönümlü) yükleri hedefe yaklaştırır.

    En dengeli atamayı döndürür; `psi` yerinde güncellenir.
    """
    M, N = D2.shape
    satir = np.arange(M)
    sonum = 0.6
    en_iyi = (np.inf, None, None, psi.copy())
    iyilesmeyen = 0
    for _ in range(max_tur):
        C = D2 - psi
        iki = np.argpartition(C, 1, axis=1)[:, :2]
        v = C[satir[:, None], iki]
        ters = v[:, 0] > v[:, 1]
        birinci = np.where(ters, iki[:, 1], iki[:, 0])
        v1 = np.minimum(v[:, 0], v[:, 1])
        v2 = np.maximum(v[:, 0], v[:, 1])
        yuk = np.bincount(birinci, weights=b, minlength=N)
        sapma = float(np.abs(yuk / H - 1).max())
        if sapma < en_iyi[0] - 1e-6:
            en_iyi = (sapma, birinci, yuk, psi.copy())
            iyilesmeyen = 0
        else:
            iyilesmeyen += 1
        if sapma < tol or iyilesmeyen >= plato:
            break
        yeni = np.empty(N)
        for k in range(N):
            diger = np.where(birinci == k, v2, v1)          # k hariç en iyi (D2 − ψ)
            yeni[k] = _esik(D2[:, k] - diger, b, H[k])
        psi += sonum * (yeni - psi)
        psi -= psi.mean()
        if iyilesmeyen >= 5:
            sonum = max(0.15, sonum * 0.8)
    psi[:] = en_iyi[3]
    return en_iyi[1], en_iyi[2], en_iyi[0]


def _dual(D2: np.ndarray, b: np.ndarray, H: np.ndarray, psi: np.ndarray, taus, maxiter: int) -> np.ndarray:
    """Entropik yarı-ayrık optimal taşıma duali: ψ'yi L-BFGS ile maksimize eder.

    g(ψ) = Σ_i b_i · softmin_τ(d²_ik − ψ_k) + Σ_k H_k ψ_k ;  ∇g = H − yük(ψ).
    τ küçüldükçe atama sert güç diyagramına yaklaşır.
    """
    from scipy.optimize import minimize

    for tau in taus:
        def f(p):
            A = (p[None, :] - D2) / tau
            mx = A.max(1, keepdims=True)
            E = np.exp(A - mx)
            S = E.sum(1)
            soft = -tau * (mx[:, 0] + np.log(S))
            g = b @ soft + H @ p
            yuk = (b / S) @ E
            return -g, -(H - yuk)

        psi = minimize(f, psi, jac=True, method="L-BFGS-B",
                       options={"maxiter": maxiter, "gtol": 1e-4, "ftol": 1e-13}).x
        psi = psi - psi.mean()
    return psi


# --------------------------------------------------------------------------- LP cilası (2.5)
def _lp_coz(Ds: np.ndarray, bs: np.ndarray, ws: np.ndarray, Hs: np.ndarray,
            et_s: np.ndarray, sutun: int) -> np.ndarray | None:
    """Dengeli taşıma LP'si (HiGHS). Döner: (Ms, N) atama kesirleri ya da çözülemezse None.

    Kısıtlar:  Σ_k x_ik = 1  (her birim tam dağıtılır),  Σ_i b_i x_ik = H_k  (bölge yükü tam hedefte).
    Amaç:      Σ_ik w_i · d²_ik · x_ik  (en kısa toplam mesafe).
    Sütunlar `sutun` en yakın bölge + birimin mevcut bölgesiyle sınırlanır (hız).
    """
    from scipy.optimize import linprog
    from scipy.sparse import coo_array

    Ms, N = Ds.shape
    if Ms == 0:
        return None
    if sutun >= N:
        sut = np.tile(np.arange(N), (Ms, 1))
    else:
        sut = np.c_[np.argpartition(Ds, sutun - 1, axis=1)[:, :sutun], et_s]
    satir = np.repeat(np.arange(Ms), sut.shape[1])
    kolon = sut.ravel()
    nv = kolon.size
    vi = np.arange(nv)
    A = coo_array((np.concatenate([np.ones(nv), bs[satir]]),
                   (np.concatenate([satir, Ms + kolon]), np.concatenate([vi, vi]))),
                  shape=(Ms + N, nv))
    beq = np.concatenate([np.ones(Ms), Hs])
    r = linprog(ws[satir] * Ds[satir, kolon], A_eq=A, b_eq=beq, bounds=(0, 1), method="highs",
                options={"time_limit": LP_SURE_SINIRI})
    if r.status != 0 or r.x is None:
        return None
    X = np.zeros((Ms, N))
    np.add.at(X, (satir, kolon), r.x)        # aynı sütun iki kez geçebilir (en yakın ∪ mevcut)
    return X


def _serbest_kume(D2: np.ndarray, b: np.ndarray, H: np.ndarray, et: np.ndarray,
                  psi: np.ndarray, kilit: np.ndarray, toplam: int) -> np.ndarray:
    """Bölge başına kota ile sınır birimi seçer.

    Her bölgeden en azından hedefi aşan yük kadarı serbest bırakılır; aksi hâlde sabit
    kalan yük hedefi aşar ve LP hiç çözülemez. Seçim, birimin en iyi iki bölgesi
    arasındaki farka (sınıra yakınlık) göre yapılır.
    """
    M, N = D2.shape
    p = np.partition(D2 - psi, 1, axis=1)[:, :2]
    marj = p[:, 1] - p[:, 0]
    marj[kilit] = np.inf
    yuk = np.bincount(et, weights=b, minlength=N)
    taban = max(8, toplam // max(N, 1))
    secim = []
    for k in range(N):
        idx = np.where((et == k) & ~kilit)[0]
        if idx.size == 0:
            continue
        idx = idx[np.argsort(marj[idx], kind="stable")]
        gerek = 0
        fazla = yuk[k] - H[k]
        if fazla > 0:
            kum = np.cumsum(b[idx])
            gerek = int(np.searchsorted(kum, fazla)) + 2
        secim.append(idx[:min(idx.size, max(taban, gerek))])
    return np.sort(np.concatenate(secim)) if secim else np.empty(0, int)


def _lp_cila(D2: np.ndarray, b: np.ndarray, w: np.ndarray, H: np.ndarray, etiket: np.ndarray,
             psi: np.ndarray | None = None, sabit: dict[int, int] | None = None,
             serbest_ust: int | None = None, tur: int = 6) -> np.ndarray:
    """Sınır birimlerini LP ile yeniden dağıtarak yükleri hedefe oturtur.

    İç birimler (iki en iyi bölge arasındaki farkı büyük olanlar) sabit tutulur; yalnız
    sınır birimleri serbesttir. `sabit` verilen birimleri zorla o bölgede tutar (ada onarımı).
    """
    M, N = D2.shape
    if N < 2 or M == 0:
        return etiket
    et = etiket.copy()
    kilit = np.zeros(M, bool)
    for i, k in (sabit or {}).items():
        et[i] = k
        kilit[i] = True
    if psi is None:
        psi = np.zeros(N)
    toplam = serbest_ust or min(LP_SERBEST_TAVAN, LP_SERBEST_TABAN + LP_SERBEST_KATSAYI * N)
    serbest = _serbest_kume(D2, b, H, et, psi, kilit, toplam)
    if serbest.size == 0:
        return et

    def hedefler(sb):
        maske = np.zeros(M, bool)
        maske[sb] = True
        return maske, H - np.bincount(et[~maske], weights=b[~maske], minlength=N)

    maske, Hs = hedefler(serbest)
    if (Hs < -1e-9).any():
        return et

    bitis = time.time() + LP_TOPLAM_SURE
    sutun = min(N, LP_SUTUN)
    for _ in range(max(1, tur)):
        if time.time() > bitis:
            break
        X = _lp_coz(D2[serbest], b[serbest], w[serbest], Hs, et[serbest], sutun)
        if X is None and sutun < N:         # aday sütunlar yetmedi: hepsini aç
            sutun = N
            X = _lp_coz(D2[serbest], b[serbest], w[serbest], Hs, et[serbest], sutun)
        if X is None:
            break
        et[serbest] = X.argmax(1)
        kesirli = np.where(X.max(1) <= 0.999)[0]
        agir = kesirli[b[serbest][kesirli] > 0.002 * H.mean()]
        if agir.size == 0:
            break
        kalan = np.setdiff1d(serbest, serbest[agir], assume_unique=True)
        if kalan.size == 0:
            break
        serbest = kalan
        maske, Hs = hedefler(serbest)
        if (Hs < -1e-9).any():
            break
    return et


def _takas_onar(D2: np.ndarray, b: np.ndarray, w: np.ndarray, H: np.ndarray, etiket: np.ndarray,
                tol: float = DENGE_TOLERANSI, max_adim: int = 600, aday: int = 48,
                korunan: np.ndarray | None = None) -> np.ndarray:
    """Açgözlü sınır takası: hedefi aşan bölgeden, sınırındaki bir birimi eksik bölgeye verir."""
    M, N = D2.shape
    if N < 2:
        return etiket
    et = etiket.copy()
    oynar = np.ones(M, bool) if korunan is None else ~korunan
    yuk = np.bincount(et, weights=b, minlength=N).astype(float)
    olcek = max(float((w * D2[np.arange(M), et]).sum()) / M, 1e-9)
    for _ in range(max_adim):
        sap = yuk / H - 1
        mevcut = float(np.abs(sap).max())
        if mevcut <= tol:
            break
        k = int(np.argmax(sap))
        if sap[k] <= 0:
            break
        idx = np.where((et == k) & (b > 0) & oynar)[0]
        alt = np.where(sap < 0)[0]
        if idx.size == 0 or alt.size == 0:
            break
        en_iyi = (0.0, None, None)
        for r in alt:
            art_hepsi = w[idx] * (D2[idx, r] - D2[idx, k])
            sec = idx[np.argsort(art_hepsi, kind="stable")[:aday]]
            bi = b[sec]
            diger = np.abs(np.delete(sap, [k, r])).max() if N > 2 else 0.0
            yeni = np.maximum(np.maximum(np.abs((yuk[k] - bi) / H[k] - 1),
                                         np.abs((yuk[r] + bi) / H[r] - 1)), diger)
            kazanc = mevcut - yeni
            art = np.maximum(w[sec] * (D2[sec, r] - D2[sec, k]), 0.0)
            skor = kazanc / (1.0 + art / olcek)
            j = int(np.argmax(skor))
            if kazanc[j] > 1e-12 and skor[j] > en_iyi[0]:
                en_iyi = (float(skor[j]), int(sec[j]), int(r))
        if en_iyi[1] is None:
            break
        i, r = en_iyi[1], en_iyi[2]
        yuk[k] -= b[i]
        yuk[r] += b[i]
        et[i] = r
    return et


def _yerlesik_ada(X: np.ndarray, etiket: np.ndarray, k: int = 5, esik_km: float = 1.0) -> dict[int, int]:
    """Komşularının tamamı başka bir bölgede olan ve kendi bölgesine uzak kalan birimler (ada)."""
    from scipy.spatial import cKDTree

    M = len(X)
    if M <= k + 1:
        return {}
    t = cKDTree(X)
    _, nb = t.query(X, k=k + 1)
    komsu = etiket[nb[:, 1:]]
    tek = (komsu == komsu[:, :1]).all(1) & (komsu[:, 0] != etiket)
    ada: dict[int, int] = {}
    for i in np.where(tek)[0]:
        ayni = np.where(etiket == etiket[i])[0]
        ayni = ayni[ayni != i]
        if ayni.size == 0:
            continue
        if np.sqrt(((X[ayni] - X[i]) ** 2).sum(1)).min() > esik_km:
            ada[int(i)] = int(komsu[i, 0])
    return ada


def _yuk_maliyet(X, b, w, D2, etiket, n):
    yuk = np.bincount(etiket, weights=b, minlength=n)
    maliyet = float((w * D2[np.arange(len(X)), etiket]).sum())
    return yuk, maliyet


def _merkezler(X: np.ndarray, w: np.ndarray, etiket: np.ndarray, C: np.ndarray) -> np.ndarray:
    n = len(C)
    say = np.bincount(etiket, minlength=n)
    return np.array([np.average(X[etiket == k], axis=0, weights=w[etiket == k]) if say[k] else C[k]
                     for k in range(n)])


def _ccpd(X: np.ndarray, b: np.ndarray, H: np.ndarray, tohum_sayisi: int, dis_iter: int, seed: int):
    """Tek seviye dengeli bölümleme. H: bölge başına hedef yük vektörü.

    Döner: (etiket, merkezler, yükler, maliyet, seçilen tohum, ara merkezler, ara etiketler, iterasyon)
    """
    n = len(H)
    w = b + 0.02 * max(b.mean(), 1e-9)          # sıfır ağırlıklı birimler de merkezi hafifçe etkilesin
    if n == 1:
        C = np.average(X, axis=0, weights=w)[None, :]
        return np.zeros(len(X), int), C, np.array([b.sum()]), 0.0, 0, [C.copy()], [np.zeros(len(X), int)], 0
    en_iyi = None
    yedek = None
    for s in range(tohum_sayisi):
        rng = np.random.default_rng(seed + s)
        C = _kmeanspp(X, w, n, rng)
        psi = np.zeros(n)
        anlik, anlik_et = [], []
        it = 0
        for it in range(dis_iter):
            D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
            psi = _dual(D2, b, H, psi, taus=(2.0, 0.3), maxiter=60)
            etiket = (D2 - psi).argmin(1)
            anlik.append(C.copy())
            anlik_et.append(etiket.copy())
            yeni = _merkezler(X, w, etiket, C)
            hareket = float(np.sqrt(((yeni - C) ** 2).sum(1)).max())
            C = yeni
            if hareket < 0.005:          # 5 metre
                break
        D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        psi = _dual(D2, b, H, psi, taus=(0.3, 0.05, 0.01, 0.002, 0.0005), maxiter=400)
        etiket, _, _ = _dengeli_ata(D2, b, H, psi, max_tur=60, plato=15)   # ayrık cila
        etiket = _takas_onar(D2, b, w, H, etiket)
        yuk, maliyet = _yuk_maliyet(X, b, w, D2, etiket, n)
        sapma = float(np.abs(yuk / H - 1).max())
        kayit = (etiket.copy(), C.copy(), yuk.copy(), maliyet, s, anlik, anlik_et, it + 1)
        if yedek is None or sapma < yedek[0]:
            yedek = (sapma, kayit)
        if sapma <= 0.01 and (en_iyi is None or maliyet < en_iyi[0]):
            en_iyi = (maliyet, kayit)
    return (en_iyi[1] if en_iyi is not None else yedek[1])


def _ince_ayar(X: np.ndarray, b: np.ndarray, H: np.ndarray, C: np.ndarray, dis_iter: int = 6):
    """Hiyerarşik sonucun merkezlerinden başlayarak tüm bölgeleri birlikte ince ayarlar."""
    n = len(H)
    w = b + 0.02 * b.mean()
    psi = np.zeros(n)
    for _ in range(dis_iter):
        D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        psi = _dual(D2, b, H, psi, taus=(0.3, 0.05), maxiter=120)
        C = _merkezler(X, w, (D2 - psi).argmin(1), C)
    D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
    psi = _dual(D2, b, H, psi, taus=(0.05, 0.01, 0.002, 0.0005, 0.0001), maxiter=500)
    etiket, _, _ = _dengeli_ata(D2, b, H, psi, max_tur=150, plato=30)
    etiket = _takas_onar(D2, b, w, H, etiket)
    yuk, maliyet = _yuk_maliyet(X, b, w, D2, etiket, n)
    return etiket, C, yuk, maliyet, float(np.abs(yuk / H - 1).max())


def _parcala(n: int, g: int) -> list[int]:
    """n'yi g adet neredeyse eşit tam sayıya böl."""
    return [n // g + (1 if i < n % g else 0) for i in range(g)]


def _secim_skoru(maliyet: float, sapma: float) -> tuple:
    """LP cilasından sonra adaylar zaten dengeli; ±%0,5 içindekiler kısa mesafeye göre sıralanır."""
    return (0, maliyet) if sapma <= 0.005 else (1, sapma)


def _hiyerarsik(X: np.ndarray, b: np.ndarray, n: int, hedef: float, g: int, tohum: int, dis_iter: int, seed: int):
    """Önce g büyük gruba (bölge sayısıyla orantılı hedef), sonra her grubu kendi içinde eşit böl."""
    boy = _parcala(n, g)
    ust = _ccpd(X, b, np.array(boy, float) * hedef, tohum, dis_iter, seed)
    s = ust[4]
    ust = ust[0]
    etiket = np.empty(len(X), int)
    ofs = 0
    for j, m in enumerate(boy):
        idx = np.where(ust == j)[0]
        if m == 1:
            etiket[idx] = ofs
        else:
            bj = b[idx]
            alt = _ccpd(X[idx], bj, np.full(m, bj.sum() / m), tohum, dis_iter, seed + 101 * (j + 1))[0]
            etiket[idx] = ofs + alt
        ofs += m
    w = b + 0.02 * b.mean()
    C = np.array([np.average(X[etiket == k], axis=0, weights=w[etiket == k]) for k in range(n)])
    yuk = np.bincount(etiket, weights=b, minlength=n)
    maliyet = float((w * ((X - C[etiket]) ** 2).sum(1)).sum())
    sapma = float(np.abs(yuk / hedef - 1).max())
    return etiket, C, yuk, maliyet, sapma, {"grup_sayisi": g, "grup_boyutlari": boy, "secilen_tohum": int(s)}


def _cila_ve_onar(X: np.ndarray, b: np.ndarray, w: np.ndarray, H: np.ndarray, C: np.ndarray,
                  etiket: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """LP cilası + ada onarımı + açgözlü takas. Döner: (etiket, merkezler, onarılan ada sayısı)."""
    n = len(H)
    D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
    etiket = _lp_cila(D2, b, w, H, etiket)
    etiket = _takas_onar(D2, b, w, H, etiket)
    ada_toplam = 0
    korunan = np.zeros(len(X), bool)
    for _ in range(2):
        ada = {i: k for i, k in _yerlesik_ada(X, etiket).items() if etiket[i] != k}
        if not ada:
            break
        ada_toplam += len(ada)
        korunan[list(ada)] = True
        C = _merkezler(X, w, etiket, C)
        D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
        etiket = _lp_cila(D2, b, w, H, etiket, sabit=ada)
        etiket = _takas_onar(D2, b, w, H, etiket, korunan=korunan)
    return etiket, _merkezler(X, w, etiket, C), ada_toplam


def bolgele(df: pd.DataFrame, n: int, olcu: str = "res_hp", haric_il: list[str] | None = None,
            tohum_sayisi: int | None = None, dis_iter: int = 25, seed: int = 20260919,
            anlik_kaydet: bool = False) -> Sonuc:
    t0 = time.time()
    if haric_il:
        df = df[~df["il"].isin(haric_il)]
    lat0, lon0 = float(df["lat"].mean()), float(df["lon"].mean())
    u = _birimler(df, olcu, lat0, lon0)
    X = u[["x", "y"]].to_numpy()
    b = u["b"].to_numpy()
    if b.sum() <= 0:
        raise ValueError(f"'{olcu}' ölçüsünün toplamı 0")
    hedef = b.sum() / n
    H = np.full(n, hedef)
    w = b + 0.02 * max(b.mean(), 1e-9)

    def km_to_ll(C):
        return np.c_[C[:, 0] * 1000 / _m_per_deg_lon(lat0) + lon0, C[:, 1] * 1000 / M_PER_DEG_LAT + lat0]

    if n <= DOGRUDAN_UST_SINIR:
        tohum = tohum_sayisi or 3
        etiket, C, _, _, s, anlik, anlik_et, iter_sayisi = _ccpd(X, b, H, tohum, dis_iter, seed)
        mod = {"mod": "doğrudan", "secilen_tohum": int(s), "dis_iterasyon": int(iter_sayisi)}
    else:
        tohum = tohum_sayisi or 2
        g0 = max(2, int(round(np.sqrt(n))))
        adaylar = []
        for g in sorted({max(2, g0 - 1), g0, min(n // 2, g0 + 1)}):
            adaylar.append(_hiyerarsik(X, b, n, hedef, g, tohum, dis_iter, seed))
        etiket, C, yuk, maliyet, sapma, bilgi = min(adaylar, key=lambda a: _secim_skoru(a[3], a[4]))
        # Grup sınırlarını da oynatabilen genel ince ayar; daha iyiyse onu al
        e2, C2, y2, m2, s2 = _ince_ayar(X, b, H, C)
        ince = bool(_secim_skoru(m2, s2) < _secim_skoru(maliyet, sapma))
        if ince:
            etiket, C = e2, C2
        anlik, anlik_et = [], []
        mod = {"mod": "hiyerarşik", **bilgi, "denenen_grup_sayilari": [a[5]["grup_sayisi"] for a in adaylar],
               "ince_ayar": ince}

    # --- son cila: tam LP dengesi + ada onarımı (CCPD-2.5)
    if n >= 2:
        etiket, C, ada_sayisi = _cila_ve_onar(X, b, w, H, C, etiket)
    else:
        ada_sayisi = 0
    D2 = ((X[:, None, :] - C[None, :, :]) ** 2).sum(2)
    yuk, maliyet = _yuk_maliyet(X, b, w, D2, etiket, n)

    # Bölge numaraları: batıdan doğuya (4 km'lik şeritler), şerit içinde kuzeyden güneye
    sira = np.lexsort((-C[:, 1], np.round(C[:, 0] / 4.0)))
    yeni_no = np.empty(n, int)
    yeni_no[sira] = np.arange(1, n + 1)
    u["bolge"] = yeni_no[etiket]
    atama = df["site_grup"].map(u["bolge"])
    atama.index = df["bina_serial"].to_numpy()
    return Sonuc(
        n=n, olcu=olcu, atama=atama.astype(int), merkezler=km_to_ll(C)[sira], hedef=hedef, yukler=yuk[sira],
        maliyet=maliyet, sure_sn=round(time.time() - t0, 2),
        parametreler={"algoritma": ALGORITMA_SURUMU, "olcu": olcu, "haric_il": haric_il or [],
                      "tohum_sayisi": tohum, "birim_sayisi": int(len(u)), "seed": seed,
                      "ada_duzeltme": int(ada_sayisi), **mod},
        anlik=[km_to_ll(a)[sira].round(5).tolist() for a in anlik] if anlik_kaydet else [],
        anlik_etiket=(["".join(chr(48 + int(k)) for k in yeni_no[e]) for e in anlik_et]
                      if anlik_kaydet else []),
    )
