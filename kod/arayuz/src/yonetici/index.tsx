/**
 * Yönetim konsolu (OPERASYON_V2_SPEC §6.0) — operasyon ve yönetici.
 *
 * Adresler:
 *   #/yonetici                                → kişinin başlangıç ekranı (İşler)
 *   #/yonetici/isler[/obek/<id>][/is/<no>]    → İşler panosu           (WP-C)
 *   #/yonetici/aranacak                       → Aranacaklar            (WP-C)
 *   #/yonetici/obekler[/<id>]                 → Öbekler                (WP-C)
 *   #/yonetici/takip                          → Takip                  (WP-D)
 *   #/yonetici/tablolar                       → Tablolar (PS26 yerine) (WP-G)
 *   #/yonetici/rapor-gecmisi                  → Veri ▸ Rapor geçmişi   (WP-C)
 *   #/yonetici/ticketlar[/<id|BN>]            → Ticket defteri
 *   #/yonetici/ekip                           → Ekip (yalnız yönetici)
 *   #/yonetici/{canli,kapsama,atama[/<id>],rapor}          → Satış ▸
 *   #/yonetici/{bolge-planlayici,tur-raporu,veri-kalitesi} → Veri ▸
 *   #/yonetici/is-emirleri                    → #/yonetici/isler (eski yer imi)
 *
 * Başka paketlerin ekranları (İşler, Öbekler, Takip, Tablolar…) dosyaları
 * geldiği anda kendiliğinden bağlanır: `import.meta.glob` dosya yoksa boş döner,
 * o zamana kadar yerinde sakin bir "hazırlanıyor" kartı durur. İzinsiz bölümde
 * "Bu bölüm görevinize kapalı." görünür (asıl kapı sunucudadır).
 */

import { lazy, Suspense, useEffect, useMemo, useState, type ComponentType } from 'react';
import { git, useAdres } from '../yol/rota';
import { useOturum } from '../depo/oturum';
import { YonetimSaglayici, useYonetim } from './depo';
import { Kabuk, Icerik, YonUst, type Sayac } from './ortak/Kabuk';
import { BOLUMLER, MENU, type Bolum } from './ortak/menu';
import { hesaplaHal, Canli } from './ekran/Canli';
import { Kapsama } from './ekran/Kapsama';
import { Atama } from './ekran/Atama';
import { Ekip } from './ekran/Ekip';
import { Rapor } from './ekran/Rapor';
import { Ticketlar } from './ekran/Ticketlar';
import { BolgePlanlayici } from './ekran/BolgePlanlayici';
import { TurRaporu } from './ekran/TurRaporu';
import { VeriKalitesi } from './ekran/VeriKalitesi';
import { ticketListesi } from './api';
import { HataSiniri } from '../ortak/HataSiniri';
import { BosDurum, Iskelet, KapaliBolum } from '../ortak/Bos';
import './yonetim.css';

/* ------------------------------ Başka paketlerin ekranları ------------------------------ */

type Yukleyici = () => Promise<Record<string, unknown>>;

/**
 * `klasor/index.ts(x)` varsa içinden `ad` adlı bileşeni tembel yükler; yoksa null.
 * (Dosya eklenince bir sonraki derlemede kendiliğinden bağlanır.)
 */
function paketEkrani(moduller: Record<string, unknown>, ad: string): ComponentType | null {
  const yukle = Object.values(moduller)[0] as Yukleyici | undefined;
  if (!yukle) return null;
  return lazy(async () => {
    const m = await yukle();
    const B = m[ad] as ComponentType | undefined;
    return { default: B ?? (() => <Hazirlaniyor bolum={null} />) };
  });
}

const ISLER = import.meta.glob('./isler/index.{ts,tsx}');
const OBEKLER = import.meta.glob('./obekler/index.{ts,tsx}');
const TAKIP = import.meta.glob('./takip/index.{ts,tsx}');
const TABLOLAR = import.meta.glob('./tablolar/index.{ts,tsx}');
/*
 * Geçiş dönemi: yeni İşler ekranı (WP-C) gelene kadar eski "İş emirleri" ekranı
 * aynı yerde çalışır. Sunucu da bu dosya yerindeyken eski /api/is-emri/* uçlarını
 * açık tutar (operasyon/v2/api.py → eski_yonlendirici); WP-C dosyayı kaldırınca
 * ikisi birlikte kalkar (uçlar 410 `yenilendi`). Dosya yoksa glob boş döner.
 */
const ESKI_IS_EMIRLERI = import.meta.glob('./ekran/IsEmirleri.tsx');

const PAKET: Partial<Record<Bolum, ComponentType | null>> = {
  isler: paketEkrani(ISLER, 'Isler') ?? paketEkrani(ESKI_IS_EMIRLERI, 'IsEmirleri'),
  aranacak: paketEkrani(ISLER, 'Aranacaklar'),
  'rapor-gecmisi': paketEkrani(ISLER, 'RaporGecmisi'),
  obekler: paketEkrani(OBEKLER, 'Obekler'),
  takip: paketEkrani(TAKIP, 'Takip'),
  tablolar: paketEkrani(TABLOLAR, 'Tablolar'),
};

/* ------------------------------ Adres ------------------------------ */

function adresiCoz(adres: string): { bolum: Bolum | null; deger: string | null } {
  const parcalar = adres.split('/').filter(Boolean); // ["yonetici", "atama", "5"]
  const ikinci = parcalar[1] ?? '';
  if (ikinci === 'is-emirleri') return { bolum: 'isler', deger: null };
  const bolum = (BOLUMLER as string[]).includes(ikinci) ? (ikinci as Bolum) : null;
  return { bolum, deger: parcalar[2] ? decodeURIComponent(parcalar[2]) : null };
}

export function Yonetim() {
  const adres = useAdres();
  const { anaYol, izinli } = useOturum();
  const { bolum, deger } = useMemo(() => adresiCoz(adres), [adres]);

  /* Eski yer imi ve çıplak #/yonetici: kişinin başlangıç ekranına. */
  useEffect(() => {
    if (adres.startsWith('/yonetici/is-emirleri')) {
      git('/yonetici/isler', { degistir: true });
      return;
    }
    if (!bolum) {
      const hedef = anaYol.startsWith('/yonetici/') ? anaYol : null;
      const ilk = MENU.find((m) => izinli(...m.izin));
      git(hedef ?? (ilk ? `/yonetici/${ilk.bolum}` : '/ben'), { degistir: true });
    }
  }, [adres, bolum, anaYol, izinli]);

  if (!bolum) return null;
  return (
    <YonetimSaglayici>
      <Govde bolum={bolum} deger={deger} />
    </YonetimSaglayici>
  );
}

/**
 * Menüdeki gri ticket sayacı: takipteki (açık · hata · transfer) ticket'lar.
 * Adres her değiştiğinde tazelenir (ticket çekmecesi açılıp kapanınca da).
 */
function useTakiptekiTicket(anahtar: string, acik: boolean): number {
  const [sayi, setSayi] = useState(0);
  useEffect(() => {
    if (!acik) return;
    let iptal = false;
    ticketListesi({ limit: 1 })
      .then((y) => !iptal && setSayi(y.acik_toplam))
      .catch(() => {
        /* sayaç yalnız bilgi; alınamazsa gösterilmez */
      });
    return () => {
      iptal = true;
    };
  }, [anahtar, acik]);
  return sayi;
}

function Govde({ bolum, deger }: { bolum: Bolum; deger: string | null }) {
  const { izinli } = useOturum();
  const { gun, ekip } = useYonetim();
  const ticketSayisi = useTakiptekiTicket(`${bolum}/${deger ?? ''}`, izinli('ticket.defter'));

  /* Canlı durum sayacı: bugün hâlâ sahaya çıkmamış (aktif) satışçılar. */
  const pasifler = new Set((ekip ?? []).filter((k) => !k.aktif).map((k) => k.id));
  const uyariSayisi = izinli('satis.izle')
    ? (gun?.satiscilar ?? []).filter((s) => {
        if (pasifler.has(s.kullanici_id)) return false;
        const hal = hesaplaHal(s);
        return hal === 'baslamadi' || hal === 'listesiz';
      }).length
    : 0;

  const sayaclar: Partial<Record<Bolum, Sayac>> = {
    canli: { sayi: uyariSayisi, tur: 'uyari', etiket: `${uyariSayisi} satışçı başlamadı` },
    ticketlar: { sayi: ticketSayisi, tur: 'bilgi', etiket: `${ticketSayisi} ticket takipte` },
  };

  const tanim = MENU.find((m) => m.bolum === bolum);
  const acik = tanim ? izinli(...tanim.izin) : false;

  return (
    <Kabuk bolum={bolum} sayaclar={sayaclar}>
      {!acik ? (
        <>
          <YonUst baslik={tanim?.etiket ?? 'Yönetim'} />
          <Icerik>
            <KapaliBolum anaEkranaDon={() => git('/', { degistir: true })} />
          </Icerik>
        </>
      ) : (
        <HataSiniri baslik={tanim?.etiket ?? 'Yönetim'}>
          <Suspense fallback={<Bekleyen baslik={tanim?.etiket ?? ''} />}>
            <Bolumu bolum={bolum} deger={deger} />
          </Suspense>
        </HataSiniri>
      )}
    </Kabuk>
  );
}

function Bolumu({ bolum, deger }: { bolum: Bolum; deger: string | null }) {
  if (bolum in PAKET) {
    const B = PAKET[bolum];
    return B ? <B /> : <Hazirlaniyor bolum={bolum} />;
  }
  switch (bolum) {
    case 'kapsama':
      return <Kapsama />;
    case 'atama':
      return <Atama baslangicKullanici={deger ? Number(deger) || null : null} />;
    case 'ekip':
      return <Ekip />;
    case 'rapor':
      return <Rapor />;
    case 'ticketlar':
      return <Ticketlar deger={deger} />;
    case 'bolge-planlayici':
      return <BolgePlanlayici />;
    case 'tur-raporu':
      return <TurRaporu />;
    case 'veri-kalitesi':
      return <VeriKalitesi baslangicKural={deger} />;
    case 'canli':
    default:
      return <Canli />;
  }
}

function Bekleyen({ baslik }: { baslik: string }) {
  return (
    <>
      <YonUst baslik={baslik} />
      <Icerik>
        <Iskelet satir={6} />
      </Icerik>
    </>
  );
}

/** Ekranı başka pakette yapılan bölüm henüz gelmediyse sakin bir yer tutucu. */
function Hazirlaniyor({ bolum }: { bolum: Bolum | null }) {
  const tanim = MENU.find((m) => m.bolum === bolum);
  return (
    <>
      <YonUst baslik={tanim?.etiket ?? 'Hazırlanıyor'} />
      <Icerik>
        <BosDurum
          simge="🛠️"
          baslik={`${tanim?.etiket ?? 'Bu bölüm'} hazırlanıyor`}
          aciklama="Bu ekran yeni sürümle birlikte gelecek. Şimdilik menüdeki diğer bölümleri kullanabilirsiniz."
        />
      </Icerik>
    </>
  );
}
