/**
 * Uygulama kabuğu: sağlayıcılar + adres yönlendirmesi + görev kapıları.
 *
 * Sıra önemli: Bildirim → Senkron (kuyruk) → Oturum → Kutlama → Bugün.
 * Kuyruk oturumdan bağımsızdır; kullanıcı çıksa bile bekleyen kayıt kaybolmaz.
 *
 * Kapılar (OPERASYON_V2_SPEC §6.0) izinlerden çizilir; asıl kapı sunucudadır:
 *   #/bugun, #/harita           satış (satis.kendi)
 *   #/bina/<serial>             bina kartı (bina.oku)
 *   #/islerim[/<is_no>]         teknik (WP-D ekranı)
 *   #/yonetici/…                operasyon + yönetici (menüdeki bölümün izni)
 *   #/ben                       herkes (satışta Ben, diğerlerinde Profil)
 * İzinsiz adreste "Bu bölüm görevinize kapalı." + [Ana ekrana dön].
 */

import { lazy, Suspense, useEffect, type ComponentType } from 'react';
import { BildirimSaglayici } from './ortak/Bildirim';
import { SenkronSaglayici } from './depo/senkron';
import { OturumSaglayici, useOturum } from './depo/oturum';
import { BugunSaglayici } from './depo/bugun';
import { AltBar } from './ortak/AltBar';
import { Giris } from './ekran/Giris';
import { Bugun } from './ekran/Bugun';
import { Bina } from './ekran/Bina';
import { Ben } from './ekran/Ben';
import { bosAdresMi, git, useAdres, yoluCoz } from './yol/rota';
import { Sayfa, SayfaGovde, Ust, BosDurum } from './ortak/Sayfa';
import { HataSiniri } from './ortak/HataSiniri';
import { KapaliBolum } from './ortak/Bos';
import { KutlamaSaglayici } from './ortak/Kutlama';
import { BaslangicSecimi } from './ortak/BaslangicSecimi';
import { Profil } from './ortak/Profil';

/** Harita ağır (deck.gl); yalnız sekmeye girilince indirilir. */
const Harita = lazy(() => import('./ekran/Harita').then((m) => ({ default: m.Harita })));
/** Yönetim konsolu ayrı parça olarak yüklenir. */
const Yonetim = lazy(() => import('./yonetici').then((m) => ({ default: m.Yonetim })));

/**
 * Teknik "İşlerim" (WP-D, `src/teknik/index.ts` → `Islerim`). Dosya gelince
 * kendiliğinden bağlanır; o zamana kadar sakin bir yer tutucu durur.
 */
const TEKNIK = import.meta.glob('./teknik/index.{ts,tsx}');
const Islerim: ComponentType | null = (() => {
  const yukle = Object.values(TEKNIK)[0] as (() => Promise<Record<string, unknown>>) | undefined;
  if (!yukle) return null;
  return lazy(async () => {
    const m = await yukle();
    return { default: (m.Islerim as ComponentType | undefined) ?? IslerimHazirlaniyor };
  });
})();

export function App() {
  return (
    <BildirimSaglayici>
      <SenkronSaglayici>
        <OturumSaglayici>
          <KutlamaKapisi>
            <Kapi />
          </KutlamaKapisi>
        </OturumSaglayici>
      </SenkronSaglayici>
    </BildirimSaglayici>
  );
}

/** Küçük sevinçler: sunucu ayarı `kutlamalar` (varsayılan açık). */
function KutlamaKapisi({ children }: { children: React.ReactNode }) {
  const { ozet } = useOturum();
  return <KutlamaSaglayici sunucuIzni={ozet?.kutlamalar !== false}>{children}</KutlamaSaglayici>;
}

/** Oturum açık mı kapalı mı: buna göre giriş ekranı ya da uygulama. */
function Kapi() {
  const { asama, anaYol, baslangicSor, baslangicSec } = useOturum();

  useEffect(() => {
    // Açılış perdesini ilk gerçek ekran boyandığında kaldır.
    if (asama === 'baslatiliyor') return;
    document.getElementById('acilis')?.remove();
  }, [asama]);

  /* Adres boşsa (uygulama simgesinden açılış) kişinin ana ekranına. */
  useEffect(() => {
    if (asama === 'acik' && bosAdresMi()) git(anaYol, { degistir: true });
  }, [asama, anaYol]);

  if (asama === 'baslatiliyor') return null;
  if (asama === 'kapali') return <Giris />;

  return (
    <>
      <Yonlendirici />
      <BaslangicSecimi acik={baslangicSor} sec={(b) => baslangicSec(b)} />
    </>
  );
}

/**
 * Sekme çubuğu yalnız satış ve teknik ana bölümlerinde durur. Yönetim konsolu
 * kendi menüsünü (masaüstünde sol, telefonda alt sekmeler) çizer.
 */
const SEKMELI_EKRANLAR = new Set(['bugun', 'harita', 'ben', 'islerim']);

function Yonlendirici() {
  const adres = useAdres();
  const { izinli } = useOturum();
  const { ekran, deger } = yoluCoz(adres);
  // İş ekranının içinde (İşlerim/<no>) sekme çubuğu yok: alttaki büyük düğme tek başına.
  const sekmeli = SEKMELI_EKRANLAR.has(ekran) && !(ekran === 'islerim' && deger);

  const icerik = (
    <>
      <Ekran ekran={ekran} deger={deger} />
      {sekmeli ? <AltBar /> : null}
    </>
  );
  /*
   * Bugünün satış listesi yalnız satış yapabilen kişide (satış, yönetici) hep
   * yüklüdür. Operasyon ve teknik bina kartında sağlayıcıyı yalnız kabuk olarak
   * alır (`etkin=false`: sunucuya gitmez); böylece izinsiz /api/gorev/bugun'a
   * boşuna 403 dönen bir istek atılmaz.
   */
  const satis = izinli('satis.kendi');
  return satis || ekran === 'bina' ? <BugunSaglayici etkin={satis}>{icerik}</BugunSaglayici> : icerik;
}

/**
 * Bina ekranı gibi "içeri girilen" sayfalarda sekme çubuğu gizlenir; alttaki
 * iki büyük düğme (Yol tarifi · Sonucu işle) ekranın en altını tek başına
 * kullanır. iOS'taki alışılmış davranış budur ve düğmelerin üstü kapanmaz.
 */
function Ekran({ ekran, deger }: { ekran: string; deger: string | null }) {
  const { izinli, gorevler, ozet, anaYol } = useOturum();
  const kapali = (baslik: string) => <Kapali baslik={baslik} anaYol={anaYol} />;

  switch (ekran) {
    case 'bugun':
      if (!izinli('satis.kendi')) return kapali('Bugün');
      return ozet?.bolge_yok ? <BolgeYok /> : <Bugun />;
    case 'bina':
      if (!izinli('bina.oku')) return kapali('Bina');
      return deger ? <Bina serial={deger} /> : <Bulunamadi anaYol={anaYol} />;
    case 'harita':
      if (!izinli('satis.kendi')) return kapali('Harita');
      // Harita ayrı bir dosyadır: sinyalsizken hiç inmemiş olabilir.
      // Sınır olmasa React bütün uygulamayı söker, satışçı listesini kaybeder.
      return (
        <HataSiniri baslik="Harita">
          <Suspense fallback={<Bekleyen baslik="Harita" />}>
            <Harita />
          </Suspense>
        </HataSiniri>
      );
    case 'ben':
      return izinli('satis.kendi') && !izinli('is.ata') ? <Ben /> : <Profil />;
    case 'islerim':
      if (!gorevler.includes('teknik')) return kapali('İşlerim');
      return (
        <HataSiniri baslik="İşlerim">
          <Suspense fallback={<Bekleyen baslik="İşlerim" />}>{Islerim ? <Islerim /> : <IslerimHazirlaniyor />}</Suspense>
        </HataSiniri>
      );
    case 'yonetici':
      if (!izinli('is.ata', 'satis.izle', 'ekip.yonet', 'ticket.defter', 'takip.oku', 'veri.yonet')) {
        return kapali('Yönetim');
      }
      return (
        <HataSiniri baslik="Yönetim">
          <Suspense fallback={<Bekleyen baslik="Yönetim" />}>
            <Yonetim />
          </Suspense>
        </HataSiniri>
      );
    default:
      return <Bulunamadi anaYol={anaYol} />;
  }
}

function Bekleyen({ baslik }: { baslik: string }) {
  return (
    <Sayfa>
      <Ust baslik={baslik} />
      <SayfaGovde>
        <div style={{ paddingTop: 24 }} aria-hidden="true">
          <div className="iskelet" style={{ height: 320 }} />
        </div>
      </SayfaGovde>
    </Sayfa>
  );
}

function Kapali({ baslik, anaYol }: { baslik: string; anaYol: string }) {
  return (
    <Sayfa>
      <Ust baslik={baslik} />
      <SayfaGovde sekmesiz>
        <KapaliBolum anaEkranaDon={() => git(anaYol, { degistir: true })} />
      </SayfaGovde>
    </Sayfa>
  );
}

/** §2.4: bölgesi olmayan satışçı şehri görmez; ne yapacağını bilir. */
function BolgeYok() {
  return (
    <Sayfa>
      <Ust baslik="Bugün" />
      <SayfaGovde>
        <BosDurum simge="🗺️" baslik="Size henüz bölge atanmadı." aciklama="Yöneticinize başvurun." />
      </SayfaGovde>
    </Sayfa>
  );
}

function IslerimHazirlaniyor() {
  return (
    <Sayfa>
      <Ust baslik="İşlerim" />
      <SayfaGovde>
        <BosDurum
          simge="🛠️"
          baslik="İşlerim hazırlanıyor"
          aciklama="Size atanan işler yeni sürümle burada sırayla görünecek."
        />
      </SayfaGovde>
    </Sayfa>
  );
}

function Bulunamadi({ anaYol }: { anaYol: string }) {
  return (
    <Sayfa>
      <Ust baslik="Saha Sistemi" />
      <SayfaGovde>
        <BosDurum simge="🧭" baslik="Bu sayfa yok" aciklama="Ana ekranınıza dönelim.">
          <button className="dugme birincil buyuk" onClick={() => git(anaYol, { degistir: true })}>
            Ana ekrana dön
          </button>
        </BosDurum>
      </SayfaGovde>
    </Sayfa>
  );
}
