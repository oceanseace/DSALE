/**
 * Uygulama bağlamı (context): mod, etkin plan, plan yükleme ve hazır bildirimi.
 * Sunum ve Keşif yalnız bu kancayı (`useUygulama`) kullanır; doğrudan window'a yazmaz.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { planDinle, planEkle, planGetir, planNleri, planSurumu, planVeyaVarsayilan, varsayilanN, veri } from '../data/load';
import type { Meta, Plan } from '../data/types';
import { hazirBildir as kontratHazir, kontratGuncelle } from './kontrat';
import { onModDegistir, onPlanYuklendi, planDosyasiAc, surukleBirak, type PlanDosyasi } from './platform';
import { urlYaz, type Mod } from './url';

export interface Bildirim {
  metin: string;
  tur: 'bilgi' | 'basari' | 'hata';
  /** artan sayaç — aynı metin tekrar gelse de yeniden gösterilsin */
  no: number;
}

export interface UygulamaDegeri {
  mod: Mod;
  setMod: (m: Mod) => void;
  /** etkin plan N */
  n: number;
  setN: (n: number) => void;
  /** etkin plan nesnesi */
  plan: Plan;
  /** paketteki + dışarıdan yüklenen plan N'leri (artan) */
  nListesi: number[];
  /** dış plan yüklendikçe artar (useMemo bağımlılığı) */
  planSurum: number;
  meta: Meta;
  /** Dosyadan plan açar (Electron iletişim kutusu ya da gizli input). */
  planAc: () => Promise<void>;
  /** Hazır JSON metnini plan olarak yükler (sürükle-bırak, menü, QA). */
  planMetniYukle: (icerik: string, ad?: string) => boolean;
  bildirim: Bildirim | null;
  bildir: (metin: string, tur?: Bildirim['tur']) => void;
  /** İlk kare çizildiğinde çağrılır; `__DSALE__.hazir` olur. */
  hazirBildir: () => void;
}

const Baglam = createContext<UygulamaDegeri | null>(null);

export interface UygulamaSaglayiciProps {
  ilkMod: Mod;
  ilkN?: number | null;
  children: ReactNode;
}

export function UygulamaSaglayici({ ilkMod, ilkN, children }: UygulamaSaglayiciProps) {
  const meta = veri().meta;
  const [mod, setModDurum] = useState<Mod>(ilkMod);
  const [n, setNDurum] = useState<number>(() => (ilkN && planGetir(ilkN) ? ilkN : varsayilanN()));
  const [planSurum, setPlanSurum] = useState(() => planSurumu());
  const [bildirim, setBildirim] = useState<Bildirim | null>(null);
  const bildirimNo = useRef(0);

  useEffect(() => planDinle(() => setPlanSurum(planSurumu())), []);

  const bildir = useCallback((metin: string, tur: Bildirim['tur'] = 'bilgi') => {
    setBildirim({ metin, tur, no: ++bildirimNo.current });
  }, []);

  // Bildirim kendiliğinden kapansın — sunumda ekranın altında asılı kalmasın.
  // Hata mesajı biraz daha uzun durur, okunacak vakit olsun diye.
  useEffect(() => {
    if (!bildirim) return;
    const no = bildirim.no;
    const s = window.setTimeout(() => setBildirim((b) => (b && b.no === no ? null : b)), bildirim.tur === 'hata' ? 7000 : 4500);
    return () => window.clearTimeout(s);
  }, [bildirim]);

  const setMod = useCallback((m: Mod) => {
    setModDurum(m);
    kontratGuncelle({ mod: m });
    urlYaz({ mod: m });
  }, []);

  const setN = useCallback((yeni: number) => {
    setNDurum(yeni);
    kontratGuncelle({ n: yeni });
    urlYaz({ n: yeni });
  }, []);

  const planMetniYukle = useCallback(
    (icerik: string, ad = 'plan.json') => {
      let ham: unknown;
      try {
        ham = JSON.parse(icerik);
      } catch {
        bildir(`${ad} okunamadı: geçerli JSON değil.`, 'hata');
        return false;
      }
      const s = planEkle(ham);
      if (!s.tamam) {
        bildir(s.hata, 'hata');
        return false;
      }
      setNDurum(s.plan.n);
      kontratGuncelle({ n: s.plan.n });
      urlYaz({ n: s.plan.n });
      bildir(`Plan yüklendi · ${s.plan.n} bölge`, 'basari');
      return true;
    },
    [bildir],
  );

  const planAc = useCallback(async () => {
    const d = await planDosyasiAc();
    if (!d) return;
    planMetniYukle(d.icerik, d.ad);
  }, [planMetniYukle]);

  // Electron menüsü ve sürükle-bırak
  useEffect(() => {
    const cb = (d: PlanDosyasi) => planMetniYukle(d.icerik, d.ad);
    const b1 = onPlanYuklendi(cb);
    const b2 = surukleBirak(cb);
    const b3 = onModDegistir((m) => setMod(m === 'kesif' ? 'kesif' : 'sunum'));
    return () => {
      b1();
      b2();
      b3();
    };
  }, [planMetniYukle, setMod]);

  const plan = useMemo(() => planVeyaVarsayilan(n), [n, planSurum]);
  const nListesi = useMemo(() => planNleri(), [planSurum]);

  const deger = useMemo<UygulamaDegeri>(
    () => ({
      mod,
      setMod,
      n,
      setN,
      plan,
      nListesi,
      planSurum,
      meta,
      planAc,
      planMetniYukle,
      bildirim,
      bildir,
      hazirBildir: kontratHazir,
    }),
    [mod, setMod, n, setN, plan, nListesi, planSurum, meta, planAc, planMetniYukle, bildirim, bildir],
  );

  return <Baglam.Provider value={deger}>{children}</Baglam.Provider>;
}

/** Uygulama bağlamı. Saygılayıcı dışında çağrılırsa hata verir. */
export function useUygulama(): UygulamaDegeri {
  const v = useContext(Baglam);
  if (!v) throw new Error('useUygulama: <UygulamaSaglayici> içinde çağrılmalı');
  return v;
}
