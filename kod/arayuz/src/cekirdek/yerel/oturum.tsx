/**
 * Oturum: kim girdi, jetonu ne, bugünkü özeti ne, hangi bölümler açık.
 *
 * Çevrimdışı açılışta sunucuya hiç gidilmez; en son bilinen kullanıcı ve özet
 * telefondan okunur. Böylece uygulama sinyal olmadan da aynı şekilde açılır.
 *
 * v2 (OPERASYON_V2_SPEC §2, EK-1): menü ve adres kapıları `izinler`den çizilir.
 * Sunucu `/api/ben.izinler` gönderir; eski sunucuda liste rolden türetilir
 * (`ortak/yetki.ts`). Girişten sonra kişi kendi ANA EKRANINA gider: yetkinliklerinin
 * açtığı İLK menü bölümü (yoksa satışta Bugün, teknikte İşlerim, hiçbiri yoksa
 * "Bu unvanın ekranları henüz tanımlanmadı." sayfası).
 *
 * Administrator ÖNİZLEMESİ: Administrator bir unvan seçince arayüz o unvandaki
 * biri gibi çizilir (menü + açılış). Yalnız istemci tarafıdır; sunucu yetkisi
 * değişmez. Seçim cihazda hatırlanır (`saha.onizleme`).
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
import { ben as benUcu, bossOturumYokla } from '../api/uclar';
import { onbellegeYaz, onbellektenOku, hepsiniTemizle, apiOnbelleginiTemizle } from './db';
import { etiketleriYaz } from '../ortak/bicim';
import { git } from '../yol/rota';
import { yerelJsonOku, yerelJsonYaz, yerelYaz } from '../ortak/yerel';
import { administratorMu, anaEkranCoz, gorevEtiketi, gorevleriCoz, izinleriCoz } from '../ortak/yetki';
import { MENU, bolumYolu } from '../konsol/menu';
import type { AnaEkran, BenYaniti, Kullanici, Rol } from '../api/tipler';

const ONBELLEK_ANAHTARI = 'ben';
/** Administrator önizlemesi (cihazda hatırlanır). */
export const ONIZLEME_ANAHTARI = 'saha.onizleme';

/** Önizlenen unvan: adı ve yetkinliklerinden türetilen izin + görev kümesi. */
export interface Onizleme {
  id: number;
  ad: string;
  izinler: string[];
  gorevler: Rol[];
}

/** Hiç ekranı olmayan unvanların sakin boş sayfası. */
export const BOS_YOL = '/bos';

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
  /** Uygulamanın tek Administrator'ı (rozet; yetkisi zaten izinlerde). Önizlemede false. */
  administrator: boolean;
  /** Gerçek Administrator mı (önizlemeden bağımsız; Görünüm seçicisi bunu kullanır). */
  gercekAdministrator: boolean;
  /** Etkin önizleme (yalnız Administrator'da). */
  onizleme: Onizleme | null;
  onizlemeSec: (o: Onizleme | null) => void;
  /** Etkin yetkinlik kodları (unvan + ek). */
  yetkinlikler: string[];
  anaEkran: AnaEkran;
  /** Ana ekranın adresi: izinlerin açtığı ilk menü bölümü. */
  anaYol: string;
  /** Giriş ekranının üstündeki bilgi şeridi ("Göreviniz değişti…"). */
  girisBilgisi: string | null;
  /** `bossla`: BOSS ile giriş (BOSS'tan çıkılınca oturum biter; yoklanır). */
  girisYapildi: (token: string, kullanici: Kullanici, bossla?: boolean) => void;
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

/**
 * Açılış adresi: izinlerin açtığı İLK menü bölümü; menüsü olmayanda satış
 * (Bugün) ya da teknik (İşlerim); hiçbiri yoksa boş sayfa.
 */
export function inisYolu(izinler: Set<string>, gorevler: Rol[]): string {
  const ilk = MENU.find((m) => m.izin.some((e) => izinler.has(e)));
  if (ilk) return bolumYolu(ilk.bolum);
  if (izinler.has('satis.kendi')) return '/bugun';
  if (gorevler.includes('teknik')) return '/islerim';
  return BOS_YOL;
}

function onizlemeOku(): Onizleme | null {
  const o = yerelJsonOku<Onizleme | null>(ONIZLEME_ANAHTARI, null);
  return o && typeof o.ad === 'string' && Array.isArray(o.izinler) && Array.isArray(o.gorevler) ? o : null;
}

/** Önizlemede ana görev (telefon sekmeleri vb. için): ilk eşleşen. */
function onizlemeRolu(gorevler: Rol[], yedek: Rol): Rol {
  for (const r of ['operasyon', 'teknik', 'satisci', 'yonetici'] as Rol[]) if (gorevler.includes(r)) return r;
  return yedek;
}

export function OturumSaglayici({ children }: { children: ReactNode }) {
  const [asama, setAsama] = useState<Asama>('baslatiliyor');
  const [ozet, setOzet] = useState<BenYaniti | null>(null);
  const [onizlemeHam, setOnizlemeHam] = useState<Onizleme | null>(onizlemeOku);
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
        // Gerçek izinler gelince kişinin açılış ekranına geç.
        const o = administratorMu(veri) ? onizlemeOku() : null;
        git(
          o ? inisYolu(new Set(o.izinler), o.gorevler) : inisYolu(izinleriCoz(veri), gorevleriCoz(veri)),
          { degistir: true },
        );
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
          if (g.kod === 'boss_oturumu_bitti') {
            setGirisBilgisi(g.hata || 'BOSS oturumunuz kapandı. Yeniden “BOSS ile giriş yap”a basın.');
            return;
          }
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

  /* BOSS ile açılan oturum: BOSS'tan çıkılınca ekran beklemeden giriş ekranına dönsün (15 sn'de bir hafif yoklama;
     401 merkezi istemciden oturumu kapatır). Telefon + PIN oturumunda yoklama yok. */
  useEffect(() => {
    if (asama !== 'acik') return undefined;
    let bossla = false;
    try {
      bossla = window.localStorage.getItem('saha.boss_giris') === '1';
    } catch {
      bossla = false;
    }
    if (!bossla) return undefined;
    const t = window.setInterval(() => {
      if (document.visibilityState === 'visible') void bossOturumYokla().catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(t);
  }, [asama]);

  const girisYapildi = useCallback(
    (token: string, kullanici: Kullanici, bossla = false) => {
      try {
        if (bossla) window.localStorage.setItem('saha.boss_giris', '1');
        else window.localStorage.removeItem('saha.boss_giris');
      } catch {
        /* depo yoksa BOSS çıkışı ilk istekte anlaşılır */
      }
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
      // Herkes kendi açılış ekranına (izinlerin açtığı ilk bölüm).
      git(inisYolu(izinleriCoz(baslangic), gorevleriCoz(baslangic)), { degistir: true });
      girisSonrasi.current = true;
      void ozetiTazele();
    },
    [ozetiTazele],
  );

  const onizlemeSec = useCallback(
    (o: Onizleme | null) => {
      setOnizlemeHam(o);
      if (o) yerelJsonYaz(ONIZLEME_ANAHTARI, o);
      else yerelYaz(ONIZLEME_ANAHTARI, null);
      git(o ? inisYolu(new Set(o.izinler), o.gorevler) : inisYolu(izinleriCoz(ozet), gorevleriCoz(ozet)), {
        degistir: true,
      });
    },
    [ozet],
  );

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
    try {
      window.localStorage.removeItem('saha.boss_giris');
    } catch {
      /* depo yok */
    }
    jetonuYaz(null);
    sonJeton.current = null;
    setOzet(null);
    setAsama('kapali');
    void hepsiniTemizle();
  }, []);

  const deger = useMemo<OturumDurumu>(() => {
    const gercekAdministrator = administratorMu(ozet);
    const onizleme = gercekAdministrator ? onizlemeHam : null;
    const izinler = onizleme ? new Set(onizleme.izinler) : izinleriCoz(ozet);
    const gorevler = onizleme ? onizleme.gorevler : gorevleriCoz(ozet);
    const k = ozet?.kullanici ?? null;
    return {
      asama,
      kullanici: k && onizleme ? { ...k, rol: onizlemeRolu(onizleme.gorevler, k.rol), administrator: false } : k,
      ozet,
      gorevler,
      gorevAdi: onizleme ? onizleme.ad : gorevEtiketi(ozet),
      izinler,
      izinli: (...eylemler: string[]) => eylemler.some((e) => izinler.has(e)),
      administrator: gercekAdministrator && !onizleme,
      gercekAdministrator,
      onizleme,
      onizlemeSec,
      yetkinlikler: (ozet?.yetkinlikler ?? []).map((y) => y.kod),
      anaEkran: anaEkranCoz(ozet),
      anaYol: inisYolu(izinler, gorevler),
      girisBilgisi,
      girisYapildi,
      cikisYap,
      ozetiTazele,
      ozetiIlerlet,
    };
  }, [
    asama,
    ozet,
    onizlemeHam,
    onizlemeSec,
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
