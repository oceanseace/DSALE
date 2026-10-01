/**
 * Yönetici ekranlarının ortak verisi.
 *
 * Üç şey pahalıdır ve ekranlar arasında paylaşılır:
 *   1. bugünün gün özeti (45 sn'de bir kendi kendine tazelenir — "canlı" olan bu),
 *   2. ekip listesi,
 *   3. 19.706 binanın harita noktaları (yalnız haritalı bir ekran açılınca indirilir).
 *
 * Sekme değiştirmek bunları yeniden indirmez; yönetici konsolu bu yüzden hızlı hissettirir.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { SahaHatasi } from '../api/istemci';
import { useOturum } from '../depo/oturum';
import { gunOzeti, harita as haritaUcu, kullanicilar as kullanicilarUcu } from './api';
import type { GunOzetiYaniti, YoneticiHaritaVerisi, YoneticiKullanici } from './tipler';
import type { HaritaNoktasi } from './ortak/HaritaTuval';
import type { BinaDurumu } from '../api/tipler';

const TAZELEME_MS = 45000;

interface YonetimDurumu {
  /** Bugünün gün özeti (canlı). */
  gun: GunOzetiYaniti | null;
  gunYukleniyor: boolean;
  gunHatasi: string | null;
  gunTazele: () => void;
  sonGuncelleme: Date | null;

  ekip: YoneticiKullanici[] | null;
  ekipYukleniyor: boolean;
  ekipTazele: () => void;

  noktalar: HaritaNoktasi[] | null;
  haritaYukleniyor: boolean;
  haritaHatasi: string | null;
  /** Haritalı ekranlar açılışta bunu çağırır; veri bir kez indirilir. */
  haritayiIste: () => void;
  haritayiTazele: () => void;
  ofis: { ad: string; lat: number; lon: number } | null;
}

const Baglam = createContext<YonetimDurumu | null>(null);

function noktalaraCevir(veri: YoneticiHaritaVerisi): HaritaNoktasi[] {
  const uzunluk = Math.min(veri.serial.length, veri.lat.length, veri.lon.length);
  const liste: HaritaNoktasi[] = new Array(uzunluk);
  for (let i = 0; i < uzunluk; i++) {
    liste[i] = {
      serial: veri.serial[i],
      ad: veri.ad?.[i] || undefined,
      loc: veri.loc?.[i] || undefined,
      konum: [veri.lon[i], veri.lat[i]],
      durum: (veri.durum[i] ?? 'bekliyor') as BinaDurumu,
      firsat: veri.firsat?.[i] ?? 0,
      bolge: veri.bolge?.[i] ?? null,
    };
  }
  return liste;
}

export function YonetimSaglayici({ children }: { children: ReactNode }) {
  /* Yalnız izinli olunan veri istenir: operasyon satış özetini ve ekip
     listesini göremez (403); boşuna istek atıp konsolu kirletmeyiz. */
  const { izinli } = useOturum();
  const satisIzni = izinli('satis.izle');
  const ekipIzni = izinli('ekip.yonet');
  const haritaIzni = izinli('satis.kendi');
  const [gun, setGun] = useState<GunOzetiYaniti | null>(null);
  const [gunYukleniyor, setGunYukleniyor] = useState(true);
  const [gunHatasi, setGunHatasi] = useState<string | null>(null);
  const [sonGuncelleme, setSonGuncelleme] = useState<Date | null>(null);

  const [ekip, setEkip] = useState<YoneticiKullanici[] | null>(null);
  const [ekipYukleniyor, setEkipYukleniyor] = useState(true);

  const [noktalar, setNoktalar] = useState<HaritaNoktasi[] | null>(null);
  const [ofis, setOfis] = useState<YonetimDurumu['ofis']>(null);
  const [haritaYukleniyor, setHaritaYukleniyor] = useState(false);
  const [haritaHatasi, setHaritaHatasi] = useState<string | null>(null);
  const haritaIstendi = useRef(false);

  const canli = useRef(true);
  useEffect(() => {
    canli.current = true;
    return () => {
      canli.current = false;
    };
  }, []);

  const gunCek = useCallback(async (ilk: boolean) => {
    if (!satisIzni) {
      setGunYukleniyor(false);
      return;
    }
    if (ilk) setGunYukleniyor(true);
    try {
      const veri = await gunOzeti();
      if (!canli.current) return;
      setGun(veri);
      setGunHatasi(null);
      setSonGuncelleme(new Date());
    } catch (h) {
      if (canli.current) setGunHatasi(h instanceof SahaHatasi ? h.message : 'Gün özeti alınamadı.');
    } finally {
      if (canli.current) setGunYukleniyor(false);
    }
  }, [satisIzni]);

  const ekipCek = useCallback(async (ilk: boolean) => {
    if (!ekipIzni) {
      setEkipYukleniyor(false);
      return;
    }
    if (ilk) setEkipYukleniyor(true);
    try {
      const veri = await kullanicilarUcu();
      if (canli.current) setEkip(veri);
    } catch {
      /* ekip listesi alınamazsa ekranlar kendi hatasını gösterir */
    } finally {
      if (canli.current) setEkipYukleniyor(false);
    }
  }, [ekipIzni]);

  const haritaCek = useCallback(async () => {
    // Bina noktaları satış izniyle gelir (/api/harita); operasyon bina aramasını
    // sunucuda yapar (ekranlar `noktalar` null iken sunucu aramasına düşer).
    if (!haritaIzni) return;
    setHaritaYukleniyor(true);
    setHaritaHatasi(null);
    try {
      const veri = await haritaUcu();
      if (!canli.current) return;
      setNoktalar(noktalaraCevir(veri));
      setOfis(veri.ofis ?? null);
    } catch (h) {
      if (canli.current) {
        setHaritaHatasi(h instanceof SahaHatasi ? h.message : 'Harita verisi alınamadı.');
        haritaIstendi.current = false; // tekrar denenebilsin
      }
    } finally {
      if (canli.current) setHaritaYukleniyor(false);
    }
  }, [haritaIzni]);

  useEffect(() => {
    void gunCek(true);
    void ekipCek(true);
  }, [gunCek, ekipCek]);

  /* Canlı tazeleme — sekme arkadayken boşuna istek atılmaz. */
  useEffect(() => {
    const sayac = setInterval(() => {
      if (document.visibilityState === 'visible') void gunCek(false);
    }, TAZELEME_MS);
    const gorunurluk = () => {
      if (document.visibilityState === 'visible') void gunCek(false);
    };
    document.addEventListener('visibilitychange', gorunurluk);
    return () => {
      clearInterval(sayac);
      document.removeEventListener('visibilitychange', gorunurluk);
    };
  }, [gunCek]);

  const haritayiIste = useCallback(() => {
    if (haritaIstendi.current) return;
    haritaIstendi.current = true;
    void haritaCek();
  }, [haritaCek]);

  const haritayiTazele = useCallback(() => {
    haritaIstendi.current = true;
    void haritaCek();
  }, [haritaCek]);

  const deger = useMemo<YonetimDurumu>(
    () => ({
      gun,
      gunYukleniyor,
      gunHatasi,
      gunTazele: () => void gunCek(false),
      sonGuncelleme,
      ekip,
      ekipYukleniyor,
      ekipTazele: () => void ekipCek(false),
      noktalar,
      haritaYukleniyor,
      haritaHatasi,
      haritayiIste,
      haritayiTazele,
      ofis,
    }),
    [
      gun,
      gunYukleniyor,
      gunHatasi,
      gunCek,
      sonGuncelleme,
      ekip,
      ekipYukleniyor,
      ekipCek,
      noktalar,
      haritaYukleniyor,
      haritaHatasi,
      haritayiIste,
      haritayiTazele,
      ofis,
    ],
  );

  return <Baglam.Provider value={deger}>{children}</Baglam.Provider>;
}

export function useYonetim() {
  const deger = useContext(Baglam);
  if (!deger) throw new Error('YonetimSaglayici bulunamadı');
  return deger;
}

/** Sadece satışçılar, bölge sırasıyla. */
export function satiscilar(ekip: YoneticiKullanici[] | null): YoneticiKullanici[] {
  return (ekip ?? [])
    .filter((k) => k.rol === 'satisci')
    .sort((a, b) => (a.bolge ?? 99) - (b.bolge ?? 99) || a.id - b.id);
}
