/**
 * Oturum: kim girdi, jetonu ne, bugünkü özeti ne, hangi bölümler açık.
 *
 * Çevrimdışı açılışta sunucuya hiç gidilmez; en son bilinen kullanıcı ve özet
 * telefondan okunur. Böylece uygulama sinyal olmadan da aynı şekilde açılır.
 *
 * v2 (OPERASYON_V2_SPEC §2, EK-1): menü ve adres kapıları `izinler`den çizilir.
 * Sunucu `/api/ben.izinler` gönderir; eski sunucuda liste rolden türetilir
 * (`ortak/yetki.ts`). Girişten sonra kişi kendi ANA EKRANINA gider; yöneticiye
 * o cihazdaki ilk girişte bir kez "Bu cihazda nereden başlayalım?" sorulur.
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
import { jetonuAl, jetonuYaz, oturumBitinceDinle } from '../api/istemci';
import { ben as benUcu } from '../api/uclar';
import { onbellegeYaz, onbellektenOku, hepsiniTemizle, apiOnbelleginiTemizle } from './db';
import { etiketleriYaz } from '../ortak/bicim';
import { git } from '../yol/rota';
import { yerelOku, yerelYaz } from '../ortak/yerel';
import {
  anaEkranCoz,
  anaEkranYolu,
  gorevEtiketi,
  gorevleriCoz,
  izinleriCoz,
} from '../ortak/yetki';
import type { AnaEkran, BenYaniti, Kullanici, Rol } from '../api/tipler';

const ONBELLEK_ANAHTARI = 'ben';
/** Yöneticinin bu cihazdaki başlangıç ekranı (§2.1): 'isler' | 'takip' | 'bugun'. */
export const BASLANGIC_ANAHTARI = 'saha.baslangic';
export type Baslangic = 'isler' | 'takip' | 'bugun';

type Asama = 'baslatiliyor' | 'kapali' | 'acik';

interface OturumDurumu {
  asama: Asama;
  kullanici: Kullanici | null;
  ozet: BenYaniti | null;
  /** Görev kümesi (ana görev dahil). */
  gorevler: Rol[];
  /** "Operasyon + Yönetici" */
  gorevAdi: string;
  izinler: Set<string>;
  /** Eylemlerden HERHANGİ biri izinliyse true. */
  izinli: (...eylemler: string[]) => boolean;
  anaEkran: AnaEkran;
  /** Ana ekranın adresi; yöneticide cihaz tercihi hesaba katılır. */
  anaYol: string;
  /** Yöneticiye "Nereden başlayalım?" sorulmalı mı (cihazda bir kez). */
  baslangicSor: boolean;
  baslangicSec: (secim: Baslangic, git?: boolean) => void;
  /** Giriş ekranının üstündeki bilgi şeridi ("Göreviniz değişti…"). */
  girisBilgisi: string | null;
  girisYapildi: (token: string, kullanici: Kullanici) => void;
  cikisYap: () => void;
  ozetiTazele: () => Promise<void>;
  /**
   * Kayıt telefona yazıldığı anda sayaçları ilerletir.
   *
   * Primi satıştan olan biri için "satışımı kaydettim ama sayı kımıldamadı"
   * sistemin güvenini bitiren şeydir. Kayıt kuyrukta bile olsa sayı doğrudur.
   */
  ozetiIlerlet: (fark: { ziyaret?: number; satis?: number; satisBina?: number }) => void;
}

const Baglam = createContext<OturumDurumu | null>(null);

export function baslangicOku(): Baslangic | null {
  const ham = yerelOku(BASLANGIC_ANAHTARI);
  return ham === 'isler' || ham === 'takip' || ham === 'bugun' ? ham : null;
}

function baslangicYolu(b: Baslangic): string {
  return b === 'takip' ? '/yonetici/takip' : b === 'bugun' ? '/bugun' : '/yonetici/isler';
}

/** Kişinin ana ekran adresi: yöneticide cihaz tercihi, diğerlerinde görevi. */
function anaYolHesapla(ozet: BenYaniti | null): string {
  if (ozet?.kullanici?.rol === 'yonetici') {
    const tercih = baslangicOku();
    if (tercih) return baslangicYolu(tercih);
  }
  return anaEkranYolu(anaEkranCoz(ozet));
}

export function OturumSaglayici({ children }: { children: ReactNode }) {
  const [asama, setAsama] = useState<Asama>('baslatiliyor');
  const [ozet, setOzet] = useState<BenYaniti | null>(null);
  const [baslangicSor, setBaslangicSor] = useState(false);
  const [girisBilgisi, setGirisBilgisi] = useState<string | null>(null);
  /** Girişten hemen sonra: sunucunun `ana_ekran`ı gelince bir kez oraya gidilir. */
  const girisSonrasi = useRef(false);
  /** Oturum düşünce nedenini sormak için son jeton (istemci onu siler). */
  const sonJeton = useRef<string | null>(jetonuAl());

  const ozetiTazele = useCallback(async () => {
    if (!jetonuAl()) return;
    try {
      const veri = await benUcu();
      setOzet(veri);
      // Sonuç/durum etiketleri sunucudan gelir: telefonda ve raporda aynı kelime.
      etiketleriYaz(veri.etiketler?.sonuc);
      void onbellegeYaz(ONBELLEK_ANAHTARI, veri);
      if (girisSonrasi.current) {
        girisSonrasi.current = false;
        // Sunucu farklı bir ana ekran söylediyse (çoklu görev) oraya geç.
        if (veri.kullanici.rol !== 'yonetici' || baslangicOku()) {
          git(anaYolHesapla(veri), { degistir: true });
        }
      }
    } catch {
      /* bağlantı yoksa önbellekteki özet ekranda kalır */
    }
  }, []);

  /* Açılış */
  useEffect(() => {
    let iptal = false;
    (async () => {
      if (!jetonuAl()) {
        if (!iptal) setAsama('kapali');
        return;
      }
      const saklanan = await onbellektenOku<BenYaniti>(ONBELLEK_ANAHTARI);
      if (iptal) return;
      if (saklanan) {
        setOzet(saklanan);
        etiketleriYaz(saklanan.etiketler?.sonuc);
        setAsama('acik');
        void ozetiTazele();
        return;
      }
      try {
        const veri = await benUcu();
        if (iptal) return;
        setOzet(veri);
        void onbellegeYaz(ONBELLEK_ANAHTARI, veri);
        setAsama('acik');
      } catch {
        // Jeton var ama sunucuya ulaşılamıyor: kullanıcıyı dışarı atmıyoruz.
        if (!iptal) setAsama(jetonuAl() ? 'acik' : 'kapali');
      }
    })();
    return () => {
      iptal = true;
    };
  }, [ozetiTazele]);

  /*
   * Sunucu 401 dediyse giriş ekranına dön. Nedeni (görev değişti, hesap
   * kapandı) giriş ekranının üstünde tek cümleyle yazılır: kişi "neden
   * atıldım?" diye yöneticisini aramasın. İstemci jetonu çoktan sildiği için
   * neden, eski jetonla bir kez daha sorulur (yalnız bu anda, tek istek).
   */
  useEffect(() => {
    const birak = oturumBitinceDinle(() => {
      const eski = sonJeton.current;
      sonJeton.current = null;
      setOzet(null);
      setAsama('kapali');
      void apiOnbelleginiTemizle();
      if (!eski) return;
      void fetch('/api/ben', { headers: { Authorization: `Bearer ${eski}` }, cache: 'no-store' })
        .then((y) => (y.status === 401 ? y.json() : null))
        .then((g: { kod?: string; hata?: string } | null) => {
          if (!g?.kod) return;
          if (g.kod === 'gorev_degisti' || g.kod === 'hesap_kapali') {
            setGirisBilgisi(
              g.hata ||
                (g.kod === 'gorev_degisti'
                  ? "Göreviniz değişti. PIN'inizle yeniden girin."
                  : 'Hesabınız kapatıldı. Yöneticinize başvurun.'),
            );
          }
        })
        .catch(() => undefined);
    });
    return () => {
      birak();
    };
  }, []);

  const girisYapildi = useCallback(
    (token: string, kullanici: Kullanici) => {
      jetonuYaz(token);
      sonJeton.current = token;
      setGirisBilgisi(null);
      // Aynı telefonda kullanıcı değişmiş olabilir: servis çalışanının
      // sakladığı kişiye özel API yanıtları (ad, bölge, gün listesi) temizlenir.
      void apiOnbelleginiTemizle();
      const baslangic: BenYaniti = {
        kullanici,
        bugun: { gorev_id: null, toplam: 0, tamam: 0, kalan: 0, satis: 0 },
      };
      setOzet(baslangic);
      setAsama('acik');
      // Herkes kendi ana ekranına: satış Bugün, teknik İşlerim, operasyon ve
      // yönetici İşler. Yönetici bu cihazda ilk kez giriyorsa önce sorulur.
      if (kullanici.rol === 'yonetici' && !baslangicOku()) {
        setBaslangicSor(true);
        git('/yonetici/isler', { degistir: true });
      } else {
        git(anaYolHesapla(baslangic), { degistir: true });
      }
      girisSonrasi.current = true;
      void ozetiTazele();
    },
    [ozetiTazele],
  );

  const baslangicSec = useCallback((secim: Baslangic, gitsin = true) => {
    yerelYaz(BASLANGIC_ANAHTARI, secim);
    setBaslangicSor(false);
    if (gitsin) git(baslangicYolu(secim), { degistir: true });
  }, []);

  const ozetiIlerlet = useCallback(
    (fark: { ziyaret?: number; satis?: number; satisBina?: number }) => {
      setOzet((onceki) => {
        if (!onceki) return onceki;
        const bugun = { ...onceki.bugun };
        bugun.tamam = (bugun.tamam ?? 0) + (fark.ziyaret ?? 0);
        bugun.kalan = Math.max(0, (bugun.kalan ?? 0) - (fark.ziyaret ?? 0));
        bugun.satis = (bugun.satis ?? 0) + (fark.satis ?? 0);
        bugun.satis_bina = (bugun.satis_bina ?? 0) + (fark.satisBina ?? 0);
        bugun.ziyaret = (bugun.ziyaret ?? 0) + (fark.ziyaret ?? 0);
        bugun.donusum = bugun.ziyaret ? (bugun.satis_bina ?? 0) / bugun.ziyaret : 0;
        const hafta = onceki.hafta
          ? {
              ...onceki.hafta,
              ziyaret: onceki.hafta.ziyaret + (fark.ziyaret ?? 0),
              satis: onceki.hafta.satis + (fark.satisBina ?? 0),
              satis_adedi: (onceki.hafta.satis_adedi ?? 0) + (fark.satis ?? 0),
            }
          : onceki.hafta;
        return { ...onceki, bugun, hafta };
      });
    },
    [],
  );

  const cikisYap = useCallback(() => {
    jetonuYaz(null);
    sonJeton.current = null;
    setOzet(null);
    setAsama('kapali');
    setBaslangicSor(false);
    void hepsiniTemizle();
  }, []);

  const deger = useMemo<OturumDurumu>(() => {
    const izinler = izinleriCoz(ozet);
    return {
      asama,
      kullanici: ozet?.kullanici ?? null,
      ozet,
      gorevler: gorevleriCoz(ozet),
      gorevAdi: gorevEtiketi(ozet),
      izinler,
      izinli: (...eylemler: string[]) => eylemler.some((e) => izinler.has(e)),
      anaEkran: anaEkranCoz(ozet),
      anaYol: anaYolHesapla(ozet),
      baslangicSor,
      baslangicSec,
      girisBilgisi,
      girisYapildi,
      cikisYap,
      ozetiTazele,
      ozetiIlerlet,
    };
  }, [
    asama,
    ozet,
    baslangicSor,
    baslangicSec,
    girisBilgisi,
    girisYapildi,
    cikisYap,
    ozetiTazele,
    ozetiIlerlet,
  ]);

  return <Baglam.Provider value={deger}>{children}</Baglam.Provider>;
}

export function useOturum() {
  const deger = useContext(Baglam);
  if (!deger) throw new Error('OturumSaglayici bulunamadı');
  return deger;
}
