/**
 * Konsol: birimleri tek kabukta toplar. Birimler birbirini tanımaz; onları
 * yalnız burası (ve App.tsx) bağlar. Menü: cekirdek/konsol/menu.ts.
 *
 * Adresler (#/yonetici/<bölüm>[/<değer>]):
 *   Operasyon  isler (TASKS)[/obek/<id>][/is/<no>] · is-haritasi (MAP) · rut (RUT) · obekler[/<id>] · boss (eski: rapor-gecmisi)
 *   Saha       canli · kapsama · atama[/<kişi>] · rapor · bolge-planlayici · tur-raporu
 *   Altyapı    ticketlar[/<id|BN>]
 *   Pano       takip (birimlerden bağımsız, menünün en üstünde)
 *   Depo       depo
 *   Administrator  ekip (Kişiler) · unvanlar · veri-kalitesi[/<kural>]
 *   is-emirleri, yeni-musteri, aranacak → isler (eski yer imleri)
 *
 * İzinsiz bölümde "Bu bölüm görevinize kapalı." görünür (asıl kapı sunucudadır).
 */

import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { git, useAdres } from './cekirdek/yol/rota';
import { useOturum } from './cekirdek/yerel/oturum';
import { YonetimSaglayici, useYonetim } from './cekirdek/konsol/saglayici';
import { Kabuk, Icerik, YonUst, type Sayac } from './cekirdek/konsol/Kabuk';
import { BOLUMLER, MENU, type Bolum } from './cekirdek/konsol/menu';
import { hesaplaHal, Canli } from './birimler/saha/yonetim/Canli';
import { Kapsama } from './birimler/saha/yonetim/Kapsama';
import { Atama } from './birimler/saha/yonetim/Atama';
import { Ekip } from './birimler/administrator/ekip/Ekip';
import { Rapor } from './birimler/saha/yonetim/Rapor';
import { Ticketlar } from './birimler/altyapi/ticket/Ticketlar';
import { BolgePlanlayici } from './birimler/saha/bolge/BolgePlanlayici';
import { TurRaporu } from './birimler/saha/yonetim/TurRaporu';
import { VeriKalitesi } from './birimler/administrator/VeriKalitesi';
import { ticketListesi } from './cekirdek/api/yonetim';
import { HataSiniri } from './cekirdek/ortak/HataSiniri';
import { Iskelet, KapaliBolum } from './cekirdek/ortak/Bos';
import { useAcilisTut } from './cekirdek/ortak/acilis';
import './cekirdek/konsol/konsol.css';

/* Büyük ekranlar ayrı parça olarak, menüden girilince yüklenir. */
const Isler = lazy(() => import('./birimler/operasyon/isler').then((m) => ({ default: m.Isler })));
const BossBaglantisi = lazy(() => import('./birimler/operasyon/isler').then((m) => ({ default: m.BossBaglantisi })));
const IsHaritasiEkrani = lazy(() => import('./birimler/operasyon/isler').then((m) => ({ default: m.IsHaritasiEkrani })));
const Rut = lazy(() => import('./birimler/operasyon/rut').then((m) => ({ default: m.Rut })));
const Obekler = lazy(() => import('./birimler/operasyon/obekler').then((m) => ({ default: m.Obekler })));
const Takip = lazy(() => import('./birimler/administrator/takip').then((m) => ({ default: m.Takip })));
const Unvanlar = lazy(() => import('./birimler/administrator/unvan/Unvanlar').then((m) => ({ default: m.Unvanlar })));
const Depo = lazy(() => import('./birimler/depo/Depo').then((m) => ({ default: m.Depo })));

/* ------------------------------ Adres ------------------------------ */

/** Kalkan ekranların eski yer imleri: TASKS'a döner. */
const ESKI_IS_ADRESLERI = ['is-emirleri', 'yeni-musteri', 'aranacak'];

function adresiCoz(adres: string): { bolum: Bolum | null; deger: string | null } {
  const parcalar = adres.split('?')[0].split('/').filter(Boolean); // ["yonetici", "atama", "5"]
  const ikinci = parcalar[1] ?? '';
  if (ESKI_IS_ADRESLERI.includes(ikinci)) return { bolum: 'isler', deger: null };
  if (ikinci === 'rapor-gecmisi') return { bolum: 'boss', deger: null };
  const bolum = (BOLUMLER as string[]).includes(ikinci) ? (ikinci as Bolum) : null;
  return { bolum, deger: parcalar[2] ? decodeURIComponent(parcalar[2]) : null };
}

export function Yonetim() {
  const adres = useAdres();
  const { anaYol, izinli } = useOturum();
  const { bolum, deger } = useMemo(() => adresiCoz(adres), [adres]);

  /* Eski yer imi ve çıplak #/yonetici: kişinin başlangıç ekranına. */
  useEffect(() => {
    if (ESKI_IS_ADRESLERI.some((a) => adres.startsWith(`/yonetici/${a}`))) {
      git('/yonetici/isler', { degistir: true });
      return;
    }
    if (!bolum) {
      const hedef = anaYol.startsWith('/yonetici/') ? anaYol : null;
      const ilk = MENU.find((m) => izinli(...m.izin));
      git(hedef ?? (ilk ? `/yonetici/${ilk.bolum}` : anaYol), { degistir: true });
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
  const { izinli, anaYol } = useOturum();
  const { gun, ekip } = useYonetim();
  const ticketSayisi = useTakiptekiTicket(`${bolum}/${deger ?? ''}`, izinli('ticket.oku') || izinli('ticket.defter'));

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
          <YonUst baslik={tanim?.etiket ?? 'Administrator'} />
          <Icerik>
            <KapaliBolum anaEkranaDon={() => git(anaYol, { degistir: true })} />
          </Icerik>
        </>
      ) : (
        <HataSiniri baslik={tanim?.etiket ?? 'Administrator'}>
          <Suspense fallback={<Bekleyen baslik={tanim?.etiket ?? ''} />}>
            <Bolumu bolum={bolum} deger={deger} />
          </Suspense>
        </HataSiniri>
      )}
    </Kabuk>
  );
}

function Bolumu({ bolum, deger }: { bolum: Bolum; deger: string | null }) {
  switch (bolum) {
    case 'depo':
      return <Depo />;
    case 'isler':
      return <Isler />;
    case 'boss':
      return <BossBaglantisi deger={deger} />;
    case 'is-haritasi':
      return <IsHaritasiEkrani />;
    case 'rut':
      return <Rut />;
    case 'obekler':
      return <Obekler />;
    case 'takip':
      return <Takip />;
    case 'kapsama':
      return <Kapsama />;
    case 'atama':
      return <Atama baslangicKullanici={deger ? Number(deger) || null : null} />;
    case 'ekip':
      return <Ekip />;
    case 'unvanlar':
      return <Unvanlar />;
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
  useAcilisTut();
  return (
    <>
      <YonUst baslik={baslik} />
      <Icerik>
        <Iskelet satir={6} />
      </Icerik>
    </>
  );
}
