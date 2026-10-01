/**
 * Kuyruk ve senkron.
 *
 * Kural: kullanıcı "Kaydet"e bastığında kayıt ÖNCE telefona yazılır, SONRA
 * sunucuya gönderilir. Böylece sinyal gitse, uygulama kapansa, pil bitse bile
 * hiçbir ziyaret kaybolmaz. Ekranda "3 kayıt bekliyor" yazar ve bağlantı
 * gelince kendiliğinden gönderilir.
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
import { ziyaretGonder, ziyaretToplu } from '../api/uclar';
import { SahaHatasi } from '../api/istemci';
import {
  eskiIsKayitlariniTemizle,
  kuyrugaReddiYaz,
  kuyrugaYaz,
  kuyrukDenemeArtir,
  kuyruguOku,
  kuyruktanSil,
  kuyrukSayisi,
  type KuyrukKaydi,
} from './db';
import type { ZiyaretKaydi } from '../api/tipler';
import { useCevrimici } from './cevrimici';
import { isKuyrugunuBaslat, isKuyrugunuGonder } from '../teknik/kuyruk';

/** İş kayıtlarının 24 saat kuralı açıkken de işler (§6.9). */
const TEMIZLIK_ARALIGI = 30 * 60 * 1000;

/** Bu kadar denemeden sonra kayıt otomatik denenmez; kullanıcı elle tetikler. */
const TAKILMA_SINIRI = 8;
const EN_KISA_BEKLEME = 15000;
const EN_UZUN_BEKLEME = 5 * 60 * 1000;

export interface SenkronDurumu {
  bekleyen: number;
  takilan: number;
  /** Sunucunun REDDETTİĞİ kayıtlar. Kullanıcı bunları görmeli, sessizce silinmemeli. */
  reddedilen: ReddedilenKayit[];
  gonderiliyor: boolean;
  cevrimici: boolean;
  /** Kaydı kuyruğa yazar ve (bağlantı varsa) hemen göndermeyi dener. */
  kaydet: (kayit: ZiyaretKaydi) => Promise<void>;
  /** Kullanıcının "Tekrar dene" düğmesi. */
  simdiGonder: () => void;
  /** Reddedilen bir kaydı kullanıcı onayıyla kuyruktan siler. */
  kayitAt: (offlineId: string) => Promise<void>;
  tazele: () => void;
}

export interface ReddedilenKayit {
  offline_id: string;
  bina_serial: string;
  hata: string;
}

const Baglam = createContext<SenkronDurumu | null>(null);

function yeniKimlik(): string {
  try {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  } catch {
    /* eski tarayıcı — aşağıdaki yedeğe düşer */
  }
  return `o-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function offlineKimlikUret() {
  return yeniKimlik();
}

/** Kuyruk alanlarını ayıklayıp sunucunun beklediği gövdeyi üretir. */
function govdeyeCevir(kayit: KuyrukKaydi): ZiyaretKaydi {
  const {
    deneme: _deneme,
    son_hata: _sonHata,
    olusturma: _olusturma,
    reddedildi: _reddedildi,
    ...kalan
  } = kayit;
  return kalan;
}

export function SenkronSaglayici({ children }: { children: ReactNode }) {
  const cevrimici = useCevrimici();
  const [bekleyen, setBekleyen] = useState(0);
  const [takilan, setTakilan] = useState(0);
  const [reddedilen, setReddedilen] = useState<ReddedilenKayit[]>([]);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  const calisiyorRef = useRef(false);
  const hataSayisiRef = useRef(0);
  const zamanlayiciRef = useRef<number | null>(null);

  const tazele = useCallback(async () => {
    const kayitlar = await kuyruguOku();
    setBekleyen(kayitlar.length);
    setTakilan(kayitlar.filter((k) => k.deneme >= TAKILMA_SINIRI).length);
    setReddedilen(
      kayitlar
        .filter((k) => k.reddedildi)
        .map((k) => ({
          offline_id: k.offline_id,
          bina_serial: k.bina_serial,
          hata: k.son_hata ?? 'Sunucu kaydı kabul etmedi.',
        })),
    );
  }, []);

  const gonder = useCallback(
    async (zorla = false) => {
      if (calisiyorRef.current) return;
      if (!navigator.onLine) {
        await tazele();
        return;
      }

      const hepsi = await kuyruguOku();
      const gonderilecek = zorla
        ? hepsi
        : hepsi.filter((k) => k.deneme < TAKILMA_SINIRI && !k.reddedildi);
      if (!gonderilecek.length) {
        await tazele();
        return;
      }

      calisiyorRef.current = true;
      setGonderiliyor(true);
      try {
        if (gonderilecek.length === 1) {
          await ziyaretGonder(govdeyeCevir(gonderilecek[0]));
          await kuyruktanSil(gonderilecek[0].offline_id);
        } else {
          const yanit = await ziyaretToplu(gonderilecek.map(govdeyeCevir));
          // Sunucu kısmi hatada HTTP 200 + `hatali` listesi döner. Eskiden bu
          // liste hiç okunmuyor, kuyruğun TAMAMI siliniyordu: sunucunun kabul
          // etmediği gerçek ziyaretler sessizce kayboluyordu. Artık yalnız
          // KABUL EDİLENLER silinir; reddedilenler kuyrukta işaretli kalır ve
          // ekranda "N kayıt gönderilemedi" olarak görünür.
          const reddedilenler = new Map(
            (yanit?.hatali ?? []).map((h) => [h.offline_id, h.hata]),
          );
          // Silme kararı OLUMLU listeye dayanır: sunucu `kabul` diyorsa kayıt
          // yazıldı demektir. "Hata listesinde yoksa silinebilir" demek, yanıtta
          // hiç geçmeyen bir kaydı da sildirir. Kaydın kaybolmaması bu
          // uygulamanın tek sözü; kuyrukta fazladan bekleyen kayıt zararsız,
          // silinen kayıt geri gelmez.
          const kabul = yanit?.kabul ? new Set(yanit.kabul) : null;
          for (const kayit of gonderilecek) {
            const hataMesaji = reddedilenler.get(kayit.offline_id);
            if (hataMesaji !== undefined) {
              await kuyrugaReddiYaz(kayit.offline_id, hataMesaji);
            } else if (kabul ? kabul.has(kayit.offline_id) : true) {
              await kuyruktanSil(kayit.offline_id);
            } else {
              // Ne kabul ne ret: sunucu bu kayıt hakkında bir şey söylemedi.
              // Tekrar denenir (idempotans çift kayıt oluşturmaz).
              await kuyrukDenemeArtir(kayit.offline_id, 'Sunucu bu kayıt için cevap vermedi.');
            }
          }
        }
        hataSayisiRef.current = 0;
      } catch (h) {
        hataSayisiRef.current += 1;
        const mesaj = h instanceof Error ? h.message : 'bilinmeyen';

        if (h instanceof SahaHatasi && h.durum === 401) {
          // Oturum kapandı: kayıtlar kuyrukta bekler, tekrar girişten sonra gider.
        } else if (h instanceof SahaHatasi && !h.agHatasi && gonderilecek.length > 1) {
          // Toplu istek sunucu tarafından reddedildi. Bozuk olabilecek tek bir
          // kaydın diğerlerini kilitlememesi için teker teker denenir.
          for (const kayit of gonderilecek) {
            try {
              await ziyaretGonder(govdeyeCevir(kayit));
              await kuyruktanSil(kayit.offline_id);
            } catch (tekHata) {
              const mesajTek = tekHata instanceof Error ? tekHata.message : 'bilinmeyen';
              // Ağ hatasıysa tekrar denenir; sunucu KAYDI REDDETTİYSE tekrar
              // denemenin anlamı yok — işaretlenir ve kullanıcıya gösterilir.
              if (tekHata instanceof SahaHatasi && !tekHata.agHatasi) {
                await kuyrugaReddiYaz(kayit.offline_id, mesajTek);
              } else {
                await kuyrukDenemeArtir(kayit.offline_id, mesajTek);
              }
            }
          }
        } else {
          await Promise.all(gonderilecek.map((k) => kuyrukDenemeArtir(k.offline_id, mesaj)));
        }
      } finally {
        calisiyorRef.current = false;
        setGonderiliyor(false);
        await tazele();
      }
    },
    [tazele],
  );

  const kaydet = useCallback(
    async (kayit: ZiyaretKaydi) => {
      await kuyrugaYaz(kayit);
      setBekleyen((s) => s + 1);
      // Gönderim arka planda; kullanıcı beklemez.
      void gonder();
    },
    [gonder],
  );

  const simdiGonder = useCallback(() => {
    hataSayisiRef.current = 0;
    void gonder(true);
  }, [gonder]);

  /** Reddedilen bir kaydı kullanıcı bilerek siler (onaydan sonra). */
  const kayitAt = useCallback(
    async (offlineId: string) => {
      await kuyruktanSil(offlineId);
      await tazele();
    },
    [tazele],
  );

  /* İlk açılış + bağlantı geri geldiğinde + uygulamaya dönüldüğünde dene. */
  useEffect(() => {
    void tazele();
    const cevrimiciOlunca = () => void gonder();
    const gorunurOlunca = () => {
      if (document.visibilityState === 'visible') void gonder();
    };
    window.addEventListener('online', cevrimiciOlunca);
    document.addEventListener('visibilitychange', gorunurOlunca);
    return () => {
      window.removeEventListener('online', cevrimiciOlunca);
      document.removeEventListener('visibilitychange', gorunurOlunca);
    };
  }, [gonder, tazele]);

  /*
   * Teknisyen iş kuyruğu (`teknik/kuyruk.ts`): düğme basışları bağlantı gelince,
   * uygulamaya dönülünce kendiliğinden gider — teknisyen İşlerim dışında dursa da.
   * Müşteri bilgisi taşıyan iş kayıtları 24 saatten eskiyse silinir (açılışta ve
   * yarım saatte bir).
   */
  useEffect(() => {
    const birak = isKuyrugunuBaslat();
    void eskiIsKayitlariniTemizle();
    const sayac = window.setInterval(() => void eskiIsKayitlariniTemizle(), TEMIZLIK_ARALIGI);
    return () => {
      birak();
      window.clearInterval(sayac);
    };
  }, []);

  /* Servis çalışanı arka plan senkronu tetiklerse. */
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return;
    const dinle = (olay: MessageEvent) => {
      if (olay.data && olay.data.tip === 'KUYRUGU_GONDER') {
        void gonder();
        void isKuyrugunuGonder();
      }
    };
    navigator.serviceWorker.addEventListener('message', dinle);
    return () => navigator.serviceWorker.removeEventListener('message', dinle);
  }, [gonder]);

  /* Bekleyen varken artan aralıklarla tekrar dene. */
  useEffect(() => {
    if (zamanlayiciRef.current) {
      window.clearTimeout(zamanlayiciRef.current);
      zamanlayiciRef.current = null;
    }
    if (bekleyen === 0 || !cevrimici) return;

    const bekleme = Math.min(EN_UZUN_BEKLEME, EN_KISA_BEKLEME * 2 ** hataSayisiRef.current);
    zamanlayiciRef.current = window.setTimeout(() => void gonder(), bekleme);
    return () => {
      if (zamanlayiciRef.current) window.clearTimeout(zamanlayiciRef.current);
    };
  }, [bekleyen, cevrimici, gonder, gonderiliyor]);

  const deger = useMemo<SenkronDurumu>(
    () => ({
      bekleyen,
      takilan,
      reddedilen,
      gonderiliyor,
      cevrimici,
      kaydet,
      simdiGonder,
      kayitAt,
      tazele,
    }),
    [bekleyen, takilan, reddedilen, gonderiliyor, cevrimici, kaydet, simdiGonder, kayitAt, tazele],
  );

  return <Baglam.Provider value={deger}>{children}</Baglam.Provider>;
}

export function useSenkron() {
  const deger = useContext(Baglam);
  if (!deger) throw new Error('SenkronSaglayici bulunamadı');
  return deger;
}

export { kuyrukSayisi };
