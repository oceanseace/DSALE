/**
 * Bugünün listesi.
 *
 * Önce telefondaki kopya gösterilir (anında açılır), arkadan sunucudan tazelenir.
 * Bir bina işlendiğinde liste beklemeden güncellenir ve bu değişiklik telefona
 * yazılır; uygulama kapanıp çevrimdışı açılsa bile bina "bitti" görünür.
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
import { bugunGorevi, gorevOlustur } from '../api/uclar';
import { jetonuAl } from '../api/istemci';
import { kuyruguOku, onbellegeYaz, onbellektenOku } from './db';
import type { BugunGorevi, GorevBinaDurumu, GorevBinasi } from '../api/tipler';

const ONBELLEK_ANAHTARI = 'gorev.bugun';

/**
 * Sunucudan gelen liste ile telefondaki kuyruğu birleştirir.
 *
 * Neden gerekli: satışçı bir binayı işledi, kayıt henüz gönderilmedi. Bu
 * sırada liste tazelenirse sunucu o binayı hâlâ "bekliyor" gösterir ve bina
 * yeniden "Sıradakiler"e düşer. Kullanıcı için bu, "kaydım gitmedi mi?"
 * demektir ve uygulamaya olan güveni bitirir. Bu yüzden kuyrukta bekleyen her
 * bina, sunucu ne derse desin, listede "tamam" kalır.
 */
async function bekleyenleriUygula(gorev: BugunGorevi | null): Promise<BugunGorevi | null> {
  if (!gorev) return gorev;
  const kuyruk = await kuyruguOku();
  if (!kuyruk.length) return gorev;
  const islenenler = new Set(kuyruk.map((k) => k.bina_serial));
  return {
    ...gorev,
    binalar: gorev.binalar.map((b) =>
      islenenler.has(b.bina_serial) ? { ...b, gorev_durum: 'tamam' as GorevBinaDurumu } : b,
    ),
  };
}

/**
 * Günün TAMAMINI gösterir: yeni liste alındığında o güne kadar bitirilen
 * binalar ekrandan kaybolmaz.
 *
 * Eskiden "Yeni liste al"a basınca ilerleme kartı 0/25'e dönüyor, "BİTENLER"
 * bölümü yok oluyordu; satışçı bugün 25 bina gezmişken ekranda "0 / 25 bina"
 * yazıyordu. Aynı günün önceki binaları yeni listenin başına eklenir.
 */
function gunuBirlestir(eski: BugunGorevi | null, yeni: BugunGorevi | null): BugunGorevi | null {
  if (!yeni) return yeni;
  if (!eski || eski.tarih !== yeni.tarih) return yeni;
  // Günün önceki binalarını artık SUNUCU veriyor (`onceki_binalar`), yani bilgi
  // sayfa yenilense de kaybolmuyor. Buradaki iş yalnız ağ kesintisinde elde
  // kalanı korumak: sunucu bu alanı göndermediyse eldeki listeden tamamla.
  if (yeni.onceki_binalar?.length) return yeni;
  const yenidekiler = new Set(yeni.binalar.map((b) => b.bina_serial));
  const devredenler = [...(eski.onceki_binalar ?? []), ...eski.binalar].filter(
    (b) => b.gorev_durum !== 'bekliyor' && !yenidekiler.has(b.bina_serial),
  );
  if (!devredenler.length) return yeni;
  // `binalar`a KARIŞTIRILMAZ: ilerleme sayacı açık listeyi saymalı, yoksa
  // ikinci listede "25 / 50" gibi bir sayı çıkar.
  return { ...yeni, onceki_binalar: devredenler };
}

type Asama = 'yukleniyor' | 'hazir' | 'hata';

interface BugunDurumu {
  asama: Asama;
  gorev: BugunGorevi | null;
  hata: string | null;
  /** Ekrandaki veri sunucudan mı, telefondaki kopyadan mı geldi. */
  onbellekten: boolean;
  yenile: () => Promise<void>;
  yeniListe: (adet?: number) => Promise<void>;
  listeOlusturuluyor: boolean;
  binaBul: (serial: string) => GorevBinasi | null;
  binaDurumunuDegistir: (serial: string, durum: GorevBinaDurumu) => void;
}

const Baglam = createContext<BugunDurumu | null>(null);

/**
 * `etkin=false`: kişinin satış listesi yok (operasyon, teknik bina kartında).
 * Sağlayıcı yine kurulur (bina kartı `useBugun` ister) ama sunucuya hiç
 * gidilmez: izinsiz uca boşuna 403 atılmaz, liste boş ve "hazır" durur.
 */
export function BugunSaglayici({ children, etkin = true }: { children: ReactNode; etkin?: boolean }) {
  const [gorev, setGorev] = useState<BugunGorevi | null>(null);
  const [asama, setAsama] = useState<Asama>(etkin ? 'yukleniyor' : 'hazir');
  const [hata, setHata] = useState<string | null>(null);
  const [onbellekten, setOnbellekten] = useState(false);
  const [listeOlusturuluyor, setListeOlusturuluyor] = useState(false);

  /* Ekrandaki listeyi birleştirmek için son hâli okuyan sabit bir kapı. */
  const gorevRef = useRef<BugunGorevi | null>(null);
  gorevRef.current = gorev;
  const gunuBirlestirRef = useRef((yeni: BugunGorevi | null) => yeni);
  gunuBirlestirRef.current = (yeni: BugunGorevi | null) =>
    gunuBirlestir(gorevRef.current, yeni);

  const yenile = useCallback(async () => {
    if (!etkin || !jetonuAl()) return;
    try {
      const gelen = await bekleyenleriUygula(await bugunGorevi());
      const veri = gunuBirlestirRef.current(gelen);
      setGorev(veri);
      // Sunucudan taze veri geldi: "Kayıtlı liste gösteriliyor" yazısı kalkmalı.
      setOnbellekten(false);
      setHata(null);
      setAsama('hazir');
      void onbellegeYaz(ONBELLEK_ANAHTARI, veri);
    } catch (h) {
      const mesaj = h instanceof Error ? h.message : 'Liste alınamadı.';
      setHata(mesaj);
      // Elimizde bir kopya varsa ekranı boşaltmıyoruz.
      setAsama((onceki) => (onceki === 'hazir' ? 'hazir' : 'hata'));
    }
  }, [etkin]);

  /* Açılış: önce telefondaki kopya, sonra sunucu. */
  useEffect(() => {
    if (!etkin) {
      setGorev(null);
      setAsama('hazir');
      return undefined;
    }
    let iptal = false;
    (async () => {
      const saklanan = await onbellektenOku<BugunGorevi | null>(ONBELLEK_ANAHTARI);
      if (iptal) return;
      if (saklanan) {
        setGorev(saklanan);
        setOnbellekten(true);
        setAsama('hazir');
      }
      await yenile();
    })();
    return () => {
      iptal = true;
    };
  }, [yenile, etkin]);

  const binaDurumunuDegistir = useCallback((serial: string, durum: GorevBinaDurumu) => {
    setGorev((onceki) => {
      if (!onceki) return onceki;
      const binalar = onceki.binalar.map((b) =>
        b.bina_serial === serial ? { ...b, gorev_durum: durum } : b,
      );
      const yeni = { ...onceki, binalar };
      void onbellegeYaz(ONBELLEK_ANAHTARI, yeni);
      return yeni;
    });
  }, []);

  const yeniListe = useCallback(async (adet?: number) => {
    // İnternet yokken sunucuya gitmenin anlamı yok; kullanıcı sebebini bilmeli.
    if (!navigator.onLine) {
      throw new Error('İnternet yok — liste alınamıyor. Bağlantı gelince tekrar deneyin.');
    }
    setListeOlusturuluyor(true);
    try {
      const konum = await konumuDene();
      const gelen = await bekleyenleriUygula(await gorevOlustur(adet, konum));
      const veri = gunuBirlestirRef.current(gelen);
      setGorev(veri);
      setOnbellekten(false);
      setHata(null);
      setAsama('hazir');
      void onbellegeYaz(ONBELLEK_ANAHTARI, veri);
    } catch (h) {
      setHata(h instanceof Error ? h.message : 'Liste oluşturulamadı.');
      throw h;
    } finally {
      setListeOlusturuluyor(false);
    }
  }, []);

  const binaBul = useCallback(
    (serial: string) => gorev?.binalar.find((b) => b.bina_serial === serial) ?? null,
    [gorev],
  );

  const deger = useMemo<BugunDurumu>(
    () => ({
      asama,
      gorev,
      hata,
      onbellekten,
      yenile,
      yeniListe,
      listeOlusturuluyor,
      binaBul,
      binaDurumunuDegistir,
    }),
    [
      asama,
      gorev,
      hata,
      onbellekten,
      yenile,
      yeniListe,
      listeOlusturuluyor,
      binaBul,
      binaDurumunuDegistir,
    ],
  );

  return <Baglam.Provider value={deger}>{children}</Baglam.Provider>;
}

export function useBugun() {
  const deger = useContext(Baglam);
  if (!deger) throw new Error('BugunSaglayici bulunamadı');
  return deger;
}

/** Konum izni varsa rotayı satışçının bulunduğu yerden başlatırız. */
export function konumuDene(zamanAsimiMs = 6000): Promise<[number, number] | undefined> {
  return new Promise((coz) => {
    if (!('geolocation' in navigator)) {
      coz(undefined);
      return;
    }
    let bitti = false;
    const sayac = setTimeout(() => {
      if (!bitti) {
        bitti = true;
        coz(undefined);
      }
    }, zamanAsimiMs);
    navigator.geolocation.getCurrentPosition(
      (konum) => {
        if (bitti) return;
        bitti = true;
        clearTimeout(sayac);
        coz([konum.coords.latitude, konum.coords.longitude]);
      },
      () => {
        if (bitti) return;
        bitti = true;
        clearTimeout(sayac);
        coz(undefined);
      },
      { enableHighAccuracy: true, timeout: zamanAsimiMs, maximumAge: 60000 },
    );
  });
}
