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
 *
 * Arama paleti (Ctrl+F · Ctrl+K · "/") oturum açıkken her ekranda bağlıdır.
 * Adresin `?…` kısmı (ör. `#/harita?loc=…`) ekran seçiminde yok sayılır; onu
 * ekranın kendisi okur.
 */

import { lazy, Suspense, useEffect, useState } from 'react';
import { BildirimSaglayici } from './cekirdek/ortak/Bildirim';
import { SenkronSaglayici, type EkKuyruk } from './cekirdek/yerel/senkron';
import { isKuyrugunuBaslat, isKuyrugunuGonder } from './birimler/teknik/kuyruk';
import { OturumSaglayici, useOturum } from './cekirdek/yerel/oturum';
import { BugunSaglayici } from './cekirdek/yerel/bugun';
import { AltBar } from './cekirdek/ortak/AltBar';
import { Giris } from './cekirdek/giris/Giris';
import { Bugun } from './birimler/saha/ekran/Bugun';
import { Bina } from './birimler/saha/ekran/Bina';
import { Ben } from './birimler/saha/ekran/Ben';
import { bosAdresMi, git, useAdres, yoluCoz } from './cekirdek/yol/rota';
import { Sayfa, SayfaGovde, Ust, BosDurum } from './cekirdek/ortak/Sayfa';
import { HataSiniri } from './cekirdek/ortak/HataSiniri';
import { KapaliBolum } from './cekirdek/ortak/Bos';
import { KutlamaSaglayici } from './cekirdek/ortak/Kutlama';
import { OnizlemeSeridi } from './cekirdek/ortak/OnizlemeSecici';
import { menuSuz } from './cekirdek/konsol/menu';
import { Profil } from './cekirdek/ortak/Profil';
import { AramaPaleti } from './cekirdek/arama';
import { acilisSerbest, useAcilisTut } from './cekirdek/ortak/acilis';

/** Harita ağır (deck.gl); yalnız sekmeye girilince indirilir. */
const Harita = lazy(() => import('./birimler/saha/ekran/Harita').then((m) => ({ default: m.Harita })));
/** Yönetim konsolu ayrı parça olarak yüklenir. */
const Yonetim = lazy(() => import('./Konsol').then((m) => ({ default: m.Yonetim })));
/** Teknik birimi: teknisyenin "İşlerim" ekranı. */
const Islerim = lazy(() => import('./birimler/teknik').then((m) => ({ default: m.Islerim })));

/** Birimlerin çevrimdışı kuyrukları: teknisyenin düğme basışları. */
const EK_KUYRUKLAR: EkKuyruk[] = [{ baslat: isKuyrugunuBaslat, gonder: isKuyrugunuGonder }];

export function App() {
  return (
    <BildirimSaglayici>
      <SenkronSaglayici ekKuyruklar={EK_KUYRUKLAR}>
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
  const { asama, anaYol } = useOturum();

  useEffect(() => {
    // Açılış perdesi: giriş ekranında hemen kalkar; oturum açıksa ilk veriyi bekleyenler bırakınca (acilis.ts).
    if (asama === 'baslatiliyor') return;
    acilisSerbest(asama === 'kapali');
  }, [asama]);

  /* Adres boşsa (uygulama simgesinden açılış) kişinin ana ekranına. */
  useEffect(() => {
    if (asama === 'acik' && bosAdresMi()) git(anaYol, { degistir: true });
  }, [asama, anaYol]);

  if (asama === 'baslatiliyor') return null;
  if (asama === 'kapali') return <Giris />;

  return (
    <>
      <OnizlemeSeridi />
      <Yonlendirici />
      <AramaPaleti />
    </>
  );
}

/**
 * Sekme çubuğu yalnız satış ve teknik ana bölümlerinde durur. Yönetim konsolu
 * kendi menüsünü (masaüstünde sol, telefonda alt sekmeler) çizer.
 */
const SEKMELI_EKRANLAR = new Set(['bugun', 'harita', 'ben', 'islerim']);

function Yonlendirici() {
  const adres = useAdres().split('?')[0];
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
  const { izinli, gorevler, ozet, anaYol, onizleme } = useOturum();
  const kapali = (baslik: string) => <Kapali baslik={baslik} anaYol={anaYol} />;

  switch (ekran) {
    case 'bugun':
      if (!izinli('satis.kendi')) return kapali('Bugün');
      // Önizlemede sunucu gerçek kişinin verisini döner: örnek veri yok.
      if (onizleme) return <OnizlemeBos baslik="Bugün" />;
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
      if (onizleme && !deger) return <OnizlemeBos baslik="İşlerim" />;
      return (
        <HataSiniri baslik="İşlerim">
          <Suspense fallback={<Bekleyen baslik="İşlerim" />}><Islerim /></Suspense>
        </HataSiniri>
      );
    case 'yonetici':
      if (!menuSuz(izinli).length) return kapali('Yönetim');
      return (
        <HataSiniri baslik="Yönetim">
          <Suspense fallback={<Bekleyen baslik="Yönetim" />}>
            <Yonetim />
          </Suspense>
        </HataSiniri>
      );
    case 'bos':
      return <BosUnvan />;
    default:
      return <Bulunamadi anaYol={anaYol} />;
  }
}

/** Hiç ekranı açılmayan unvanlar (Finans, İK, İdari İşler…): sakin boş sayfa. */
function BosUnvan() {
  const { gorevAdi, cikisYap } = useOturum();
  return (
    <Sayfa>
      <Ust baslik={gorevAdi || 'Turkcell'} />
      <SayfaGovde sekmesiz>
        <div className="bos-unvan">
          <div>
            <p>Bu unvanın ekranları henüz tanımlanmadı.</p>
            <TazeleProfil />
            <button type="button" className="dugme sessiz" onClick={cikisYap}>
              Çıkış
            </button>
          </div>
        </div>
      </SayfaGovde>
    </Sayfa>
  );
}

function Bekleyen({ baslik }: { baslik: string }) {
  useAcilisTut();
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
        <BosDurum simge="🗺️" baslik="Size henüz bölge atanmadı." aciklama="Yöneticinize başvurun; atandıktan sonra Yenile'ye basın.">
          <TazeleProfil />
        </BosDurum>
      </SayfaGovde>
    </Sayfa>
  );
}

/** Yönetici bölge/unvan atadıktan sonra çıkmadan yenileme + profil (görünüm). */
function TazeleProfil() {
  const { ozetiTazele } = useOturum();
  const [bekle, setBekle] = useState(false);
  return (
    <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', margin: '12px 0' }}>
      <button
        type="button"
        className="dugme birincil"
        disabled={bekle}
        onClick={() => {
          setBekle(true);
          void ozetiTazele().finally(() => setBekle(false));
        }}
      >
        {bekle ? 'Yenileniyor…' : 'Yenile'}
      </button>
      <button type="button" className="dugme sessiz" onClick={() => git('/ben')}>
        Profil ve görünüm
      </button>
    </div>
  );
}

/** Administrator önizlemesi: kişisel ekranlar için örnek veri yok. */
function OnizlemeBos({ baslik }: { baslik: string }) {
  return (
    <Sayfa>
      <Ust baslik={baslik} />
      <SayfaGovde>
        <BosDurum
          simge="👁️"
          baslik="Önizleme — örnek veri yok"
          aciklama="Bu ekran görevlinin kendi kayıtlarını gösterir; önizlemede örnek veri bulunmuyor."
        />
      </SayfaGovde>
    </Sayfa>
  );
}

function Bulunamadi({ anaYol }: { anaYol: string }) {
  return (
    <Sayfa>
      <Ust baslik="Turkcell" />
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
