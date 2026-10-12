/**
 * İşler panosunun veri deposu (OPERASYON_V2_SPEC §5.3.2, §5.5 "Canlı pano").
 *
 *   · İlk açılışta bütün açık işler tek istekte gelir (437 iş < 150 ms); süzme,
 *     sayma, öbek sayıları istemcide yapılır — sayılar listeyle hep aynıdır.
 *   · Sekme görünürken 20 sn'de bir `GET /api/isler/degisim?imlec=` : yalnız
 *     değişen işler gelir ve YERİNDE güncellenir (liste zıplamaz, klavyedeki
 *     imleç kaçmaz). Yeni gelen iş Excel'de satır eklenir gibi listenin SONUNA eklenir
 *     (üstteki satırlar kaymaz; kaydırma ve seçim yerinde kalır). Tam tazelemede sıra yine sunucununkidir.
 *   · Öbek tanımları (`/api/obekler`) yalnız `obek_surumu` değişince yeniden okunur.
 *   · Ekran değişip geri gelince son hâl modül önbelleğinden anında çizilir,
 *     arkada tazelenir.
 *   · `ek` (TASKS tablosu): satırlar BOSS listesinin bütün alanlarıyla gelir
 *     (`?ek=1`). Satırda `ek` yoksa eskisi korunur; eylem yanıtında (IsAyrinti)
 *     `isaret` / `uyarilar` yoksa onlar da.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  degisimGetir,
  hataMetni,
  isAyarlari as isAyarlariGetir,
  islerGetir,
  obeklerGetir,
  teknikler as teknikleriGetir,
} from '../../../cekirdek/is/api';
import type { IsAyarlari, IsSatir, IslerYanit, Obek, ObeklerYanit, TeknikOzet } from '../../../cekirdek/is/tipler';
import { sunucuFarki } from '../../../cekirdek/ortak/Saat';
import { durumRenkleriniKur } from '../../../cekirdek/is/durumRenk';
import { useAcilisTut } from '../../../cekirdek/ortak/acilis';

export type IslerMeta = Omit<IslerYanit, 'isler'>;

interface Onbellek {
  meta: IslerMeta | null;
  isler: IsSatir[];
  obekler: ObeklerYanit | null;
  teknikler: TeknikOzet[];
  ayarlar: IsAyarlari | null;
}

/** Ekranlar arası anlık önbellek (yalnız bellekte; müşteri verisi diske yazılmaz). */
let ONBELLEK: Onbellek | null = null;

export interface IslerDeposu {
  durum: 'yukleniyor' | 'hazir' | 'hata';
  hata: string | null;
  meta: IslerMeta | null;
  isler: IsSatir[];
  harita: Map<string, IsSatir>;
  obekler: ObeklerYanit | null;
  teknikler: TeknikOzet[];
  ayarlar: IsAyarlari | null;
  sunucuFarkMs: number;
  /** Bütün listeyi yeniden oku (rapor yüklendikten sonra). */
  tazele: () => Promise<void>;
  /** Değişim imlecinden hemen oku (bir eylemden sonra sayaçlar tazelensin). */
  simdiYokla: () => Promise<void>;
  /** Tek işi yerinde güncelle (eylem yanıtı). Biten iş açık listeden düşer. */
  isYaz: (s: IsSatir) => void;
  /** Satırların hücre dolgularını yerinde değiştir (is_no → hucre_renk); öteki alanlara dokunmaz. */
  hucreRenkleriYaz: (m: Record<string, IsSatir['hucre_renk']>) => void;
  obekleriTazele: () => Promise<void>;
  obekleriYaz: (obekler: Obek[], surum: number) => void;
  teknikleriTazele: () => void;
}

const Baglam = createContext<IslerDeposu | null>(null);

/* ------------------------------ sıra ------------------------------ */

function an(metin: string | null | undefined): number {
  if (!metin) return Number.POSITIVE_INFINITY;
  const m = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/.exec(metin);
  if (!m) return Number.POSITIVE_INFINITY;
  return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0)).getTime();
}

/**
 * Sunucu sırasının (§3.6 normal mod) istemcideki yalın karşılığı. Listenin kendisi sunucu sırasıdır; yeni gelen
 * iş artık sona eklenir (birlestir), bu karşılaştırıcı yalnız dışarıdan sıralamak isteyenler için kalır.
 */
export function siraKarsilastir(a: IsSatir, b: IsSatir): number {
  const k = (x: IsSatir) => (x.oncelik ? 0 : x.durum === 'triyaj' ? 1 : 2);
  if (k(a) !== k(b)) return k(a) - k(b);
  const btkA = a.serit === 'BTK' ? 0 : 1;
  const btkB = b.serit === 'BTK' ? 0 : 1;
  if (btkA !== btkB) return btkA - btkB;
  const hedefA = a.serit === 'BTK' ? an(a.btk_hedef_net ?? a.btk_hedef) : an(a.son24);
  const hedefB = b.serit === 'BTK' ? an(b.btk_hedef_net ?? b.btk_hedef) : an(b.son24);
  return hedefA - hedefB;
}

/* ------------------------------ sağlayıcı ------------------------------ */

export function IslerSaglayici({ children, ek = false }: { children: ReactNode; ek?: boolean }) {
  const [durum, setDurum] = useState<IslerDeposu['durum']>(ONBELLEK?.meta ? 'hazir' : 'yukleniyor');
  const [hata, setHata] = useState<string | null>(null);
  const [meta, setMeta] = useState<IslerMeta | null>(ONBELLEK?.meta ?? null);
  const [isler, setIsler] = useState<IsSatir[]>(ONBELLEK?.isler ?? []);
  const [obekler, setObekler] = useState<ObeklerYanit | null>(ONBELLEK?.obekler ?? null);
  const [teknikler, setTeknikler] = useState<TeknikOzet[]>(ONBELLEK?.teknikler ?? []);
  const [ayarlar, setAyarlar] = useState<IsAyarlari | null>(ONBELLEK?.ayarlar ?? null);
  const imlec = useRef<number>(ONBELLEK?.meta?.imlec ?? 0);
  const obekSurumu = useRef<number | null>(ONBELLEK?.obekler?.surum ?? null);
  const yoklaniyor = useRef(false);
  const tekTimer = useRef<number | null>(null);

  useEffect(() => {
    ONBELLEK = { meta, isler, obekler, teknikler, ayarlar };
  }, [meta, isler, obekler, teknikler, ayarlar]);

  const obekleriTazele = useCallback(async () => {
    try {
      const o = await obeklerGetir();
      obekSurumu.current = o.surum;
      setObekler(o);
    } catch {
      /* öbek listesi alınamazsa pano yine çalışır; bir sonraki yoklamada denenir */
    }
  }, []);

  const teknikleriTazele = useCallback(() => {
    if (tekTimer.current) window.clearTimeout(tekTimer.current);
    tekTimer.current = window.setTimeout(() => {
      teknikleriGetir()
        .then(setTeknikler)
        .catch(() => undefined);
    }, 250);
  }, []);

  const tazele = useCallback(async () => {
    try {
      const y = await islerGetir('acik', { ek });
      const { isler: liste, ...m } = y;
      imlec.current = y.imlec;
      setMeta(m);
      setIsler(liste);
      setHata(null);
      setDurum('hazir');
      if (obekSurumu.current !== y.obek_surumu) void obekleriTazele();
    } catch (e) {
      setHata(hataMetni(e));
      setDurum((d) => (d === 'hazir' ? d : 'hata'));
    }
  }, [obekleriTazele, ek]);

  const simdiYokla = useCallback(async () => {
    if (yoklaniyor.current || !imlec.current) return;
    yoklaniyor.current = true;
    try {
      const d = await degisimGetir(imlec.current, ek);
      imlec.current = d.imlec;
      setMeta((m) =>
        m
          ? {
              ...m,
              imlec: d.imlec,
              sayac: d.sayac,
              son_aktarim: d.son_aktarim,
              sunucu_zamani: d.sunucu_zamani,
              obek_surumu: d.obek_surumu,
              onay_bekleyen: d.onay_bekleyen ?? [],
              ek_etiketler: d.ek_etiketler ? { ...m.ek_etiketler, ...d.ek_etiketler } : m.ek_etiketler,
            }
          : m,
      );
      if (d.isler.length || d.gorunmez.length) {
        setIsler((eski) => birlestir(eski, d.isler, d.gorunmez));
        teknikleriTazele();
      }
      if (obekSurumu.current !== null && d.obek_surumu !== obekSurumu.current) void obekleriTazele();
      setHata(null);
    } catch (e) {
      setHata(hataMetni(e));
    } finally {
      yoklaniyor.current = false;
    }
  }, [obekleriTazele, teknikleriTazele, ek]);

  /* İlk yükleme: açılış perdesi ilk liste (ya da hatası) gelene dek durur. */
  useAcilisTut(durum === 'yukleniyor');
  useEffect(() => {
    void tazele();
    void obekleriTazele();
    teknikleriGetir()
      .then(setTeknikler)
      .catch(() => undefined);
    isAyarlariGetir()
      .then((a) => {
        setAyarlar(a);
        durumRenkleriniKur(a.durum_renkleri); // MAP nokta renkleri (Administrator'ın eşlemesi)
      })
      .catch(() => undefined);
  }, [tazele, obekleriTazele]);

  /* Canlı pano: sekme görünürken 20 sn'de bir; sekmeye dönünce hemen. */
  useEffect(() => {
    const sayac = window.setInterval(() => {
      if (document.visibilityState === 'visible') void simdiYokla();
    }, 20000);
    const gorunur = () => {
      if (document.visibilityState === 'visible') void simdiYokla();
    };
    document.addEventListener('visibilitychange', gorunur);
    return () => {
      window.clearInterval(sayac);
      document.removeEventListener('visibilitychange', gorunur);
    };
  }, [simdiYokla]);

  const isYaz = useCallback((s: IsSatir) => {
    setIsler((eski) => birlestir(eski, [s], [], EYLEMDE));
  }, []);

  const hucreRenkleriYaz = useCallback((m: Record<string, IsSatir['hucre_renk']>) => {
    setIsler((eski) => eski.map((x) => (x.is_no in m ? { ...x, hucre_renk: m[x.is_no] } : x)));
  }, []);

  const obekleriYaz = useCallback((liste: Obek[], surum: number) => {
    obekSurumu.current = surum;
    setObekler((o) => ({ surum, obekler: liste, obeksiz: o?.obeksiz ?? [] }));
    // öbeğe bağlı işler yeniden çözüldü: sayılar ve rozetler hemen gelsin
    void obeklerGetir()
      .then((o) => {
        obekSurumu.current = o.surum;
        setObekler(o);
      })
      .catch(() => undefined);
  }, []);

  const harita = useMemo(() => new Map(isler.map((x) => [x.is_no, x])), [isler]);
  const sunucuFarkMs = useMemo(() => sunucuFarki(meta?.sunucu_zamani), [meta?.sunucu_zamani]);

  const deger = useMemo<IslerDeposu>(
    () => ({
      durum,
      hata,
      meta,
      isler,
      harita,
      obekler,
      teknikler,
      ayarlar,
      sunucuFarkMs,
      tazele,
      simdiYokla,
      isYaz,
      hucreRenkleriYaz,
      obekleriTazele,
      obekleriYaz,
      teknikleriTazele,
    }),
    [durum, hata, meta, isler, harita, obekler, teknikler, ayarlar, sunucuFarkMs, tazele, simdiYokla, isYaz, hucreRenkleriYaz, obekleriTazele, obekleriYaz, teknikleriTazele],
  );

  return <Baglam.Provider value={deger}>{children}</Baglam.Provider>;
}

/** Gelen satırda olmayabilen liste alanları. Değişim yoklamasında yalnız `ek`; eylem yanıtında hepsi. */
type Korunan = 'ek' | 'isaret' | 'hucre_renk' | 'uyarilar' | 'boss_durum' | 'boss_randevu_durumu' | 'boss_ekip';
const DEGISIMDE: Korunan[] = ['ek'];
/** Eylem yanıtı (IsAyrinti) BOSS alanlarını taşımayabilir: eskisi korunur, MAP rengi kaybolmaz. Değişim yoklamasında
 *  ve tam tazelemede ise sunucunun satırı KESİN kaynaktır (BOSS durumu / randevu / ekip değişikliği olduğu gibi gelir). */
export const EYLEMDE: Korunan[] = ['ek', 'isaret', 'hucre_renk', 'uyarilar', 'boss_durum', 'boss_randevu_durumu', 'boss_ekip'];
function koru(yeni: IsSatir, eski: IsSatir, alanlar: Korunan[]): IsSatir {
  if (alanlar.every((k) => yeni[k] !== undefined || eski[k] === undefined)) return yeni;
  const y = { ...yeni };
  for (const k of alanlar) if (y[k] === undefined && eski[k] !== undefined) Object.assign(y, { [k]: eski[k] });
  return y;
}

/**
 * Değişen işleri listeye yerinde işler; biten ve görünmeyen düşer, yeni olan SONA eklenir (Excel'deki gibi).
 * Gelen satırda olmayan `korunan` alanlar eski satırdan kalır — TASKS'ın BOSS sütunları ve renkleri boşalmasın.
 */
export function birlestir(eski: IsSatir[], gelen: IsSatir[], gorunmez: string[], korunan: Korunan[] = DEGISIMDE): IsSatir[] {
  const cikacak = new Set(gorunmez);
  const guncel = new Map<string, IsSatir>();
  for (const s of gelen) {
    if (s.kova === 'biten' || s.durum === 'kapandi') cikacak.add(s.is_no);
    else guncel.set(s.is_no, s);
  }
  const liste: IsSatir[] = [];
  for (const x of eski) {
    if (cikacak.has(x.is_no)) continue;
    const g = guncel.get(x.is_no);
    if (g) {
      liste.push(koru(g, x, korunan));
      guncel.delete(x.is_no);
    } else liste.push(x);
  }
  for (const yeni of guncel.values()) liste.push(yeni);
  return liste;
}

export function useIsler(): IslerDeposu {
  const d = useContext(Baglam);
  if (!d) throw new Error('IslerSaglayici bulunamadı');
  return d;
}
