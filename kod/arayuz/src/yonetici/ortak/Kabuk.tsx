/**
 * Yönetim kabuğu (OPERASYON_V2_SPEC §6.0): solda bölüm menüsü, sağda başlık +
 * içerik; telefonda alt sekmeler.
 *
 *   ≥ 1024 px  232 px sol menü. Gruplar (Satış ▸, Veri ▸) açılır/kapanır,
 *              hâli cihazda hatırlanır. Altta: kişi + görev, Başlangıç ekranı
 *              (yönetici), Satış uygulaması, Görünüm, Çıkış.
 *   < 1024 px  menü yok; altta en çok 4 sekme (3 bölüm + "Daha"), kalanı
 *              "Daha" çekmecesinde. Her ekranın başlığı 44 px'lik çubuk olur.
 *
 * Menü izinlerden çizilir (EK-1: görev kümesinin birleşimi); kişi yalnız
 * görevlerinin açtığı bölümleri görür.
 */

import {
  Children,
  createContext,
  isValidElement,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { git } from '../../yol/rota';
import { useOturum, baslangicOku, type Baslangic } from '../../depo/oturum';
import { Cikis, Liste } from '../../ortak/Ikon';
import { Marka } from '../../ortak/Marka';
import { Segment } from '../../ortak/Segment';
import { Panel } from '../../ortak/Panel';
import { EkranCumlesi } from '../../ortak/IlkIpucu';
import { BaslangicSecimi } from '../../ortak/BaslangicSecimi';
import { Hap } from '../../ortak/Rozet';
import { useGorunum, GORUNUM_ETIKET, type Gorunum as GorunumTuru } from '../../ortak/tema';
import { useKutlama } from '../../ortak/Kutlama';
import { yerelJsonOku, yerelJsonYaz } from '../../ortak/yerel';
import { Alet, AsagiOk, Bayrak, Daha, Gorunum } from './simgeler';
import { basHarfler } from './parcalar';
import {
  EKRAN_CUMLESI,
  GRUP_ADI,
  MENU,
  bolumYolu,
  menuSuz,
  telefonSekmeleri,
  type Bolum,
  type Grup,
  type MenuTanimi,
} from './menu';
import { AltSekme, type AltSekmeOgesi } from '../../ortak/AltBar';
import { BaglantiSeridi } from '../../ortak/BaglantiSeridi';
import './kabuk.css';

export type { Bolum } from './menu';
export { MENU } from './menu';

export function bolumeGit(bolum: Bolum) {
  git(bolumYolu(bolum));
}

/** Menüdeki sayaç: kırmızı (uyarı) ya da gri (bilgi). */
export interface Sayac {
  sayi: number;
  tur: 'uyari' | 'bilgi';
  etiket: string;
}

const BolumBaglami = createContext<Bolum | null>(null);

const BASLANGIC_ADI: Record<Baslangic, string> = { isler: 'İşler', takip: 'Takip', bugun: 'Satış uygulaması' };
const GRUP_ANAHTARI = 'saha.menu.gruplar';

export function Kabuk({
  bolum,
  sayaclar = {},
  children,
}: {
  bolum: Bolum;
  sayaclar?: Partial<Record<Bolum, Sayac>>;
  children: ReactNode;
}) {
  const { kullanici, cikisYap, izinli, gorevler, gorevAdi } = useOturum();
  const gorunen = useMemo(() => menuSuz(izinli), [izinli]);
  const [dahaAcik, setDahaAcik] = useState(false);
  const [baslangicAcik, setBaslangicAcik] = useState(false);
  // Gruplar varsayılan KAPALI: menü 768 px yüksekliğe kaydırmasız sığar.
  const [gruplar, setGruplar] = useState<Record<Grup, boolean>>(() =>
    yerelJsonOku(GRUP_ANAHTARI, { satis: false, veri: false }),
  );
  const [hesapAcik, setHesapAcik] = useState(false);
  const { baslangicSec } = useOturum();
  /* Etkin bölüm kapalı bir gruptaysa o grup görünür (kişi nerede olduğunu görsün). */
  const etkinGrup = MENU.find((m) => m.bolum === bolum)?.grup;

  useEffect(() => {
    yerelJsonYaz(GRUP_ANAHTARI, gruplar);
  }, [gruplar]);

  /* Sekme değişince "Daha" kapanır. */
  useEffect(() => setDahaAcik(false), [bolum]);

  const yonetici = kullanici?.rol === 'yonetici' || gorevler.includes('yonetici');
  const sekmeler = telefonSekmeleri(kullanici?.rol, gorunen);
  const dahadakiler = gorunen.filter((m) => !sekmeler.includes(m.bolum));
  const dahaEtkin = dahadakiler.some((m) => m.bolum === bolum);

  const altOgeler: AltSekmeOgesi[] = [
    ...sekmeler.map((b) => {
      const m = MENU.find((x) => x.bolum === b)!;
      const s = sayaclar[b];
      return {
        anahtar: b,
        etiket: m.kisa ?? m.etiket,
        Ikon: m.Ikon,
        etkin: b === bolum,
        tikla: () => bolumeGit(b),
        sayac: s?.tur === 'uyari' ? s.sayi : undefined,
        sayacEtiketi: s?.etiket,
      };
    }),
    { anahtar: 'daha', etiket: 'Daha', Ikon: Daha, etkin: dahaEtkin || dahaAcik, tikla: () => setDahaAcik(true) },
  ];

  const menuOgesi = (m: MenuTanimi, telefonda = false) => {
    const etkin = m.bolum === bolum;
    const s = sayaclar[m.bolum];
    return (
      <button
        key={m.bolum}
        type="button"
        className={`kabuk-oge${etkin ? ' etkin' : ''}`}
        aria-current={etkin ? 'page' : undefined}
        onClick={() => {
          bolumeGit(m.bolum);
          if (telefonda) setDahaAcik(false);
        }}
      >
        <m.Ikon boyut={telefonda ? 22 : 19} />
        <span className="ad">{m.etiket}</span>
        {s && s.sayi > 0 ? (
          <span className={`kabuk-sayac ${s.tur}`} aria-label={s.etiket}>
            {s.sayi > 99 ? '99+' : s.sayi}
          </span>
        ) : null}
      </button>
    );
  };

  const menuListesi = (liste: MenuTanimi[], telefonda = false) => {
    const grupsuz = liste.filter((m) => !m.grup);
    const grupluler = (['satis', 'veri'] as Grup[])
      .map((g) => ({ g, ogeler: liste.filter((m) => m.grup === g) }))
      .filter((x) => x.ogeler.length);
    return (
      <>
        {grupsuz.map((m) => menuOgesi(m, telefonda))}
        {grupluler.map(({ g, ogeler }) => {
          const acik = telefonda || gruplar[g] || etkinGrup === g;
          return (
            <div key={g} className="kabuk-grup">
              {telefonda ? (
                <div className="kabuk-grup-adi">{GRUP_ADI[g]}</div>
              ) : (
                <button
                  type="button"
                  className="kabuk-grup-bas"
                  aria-expanded={acik}
                  onClick={() => setGruplar((o) => ({ ...o, [g]: !acik }))}
                >
                  <span>{GRUP_ADI[g]}</span>
                  <span className={`ok${acik ? ' acik' : ''}`}>
                    <AsagiOk boyut={16} />
                  </span>
                </button>
              )}
              {acik ? ogeler.map((m) => menuOgesi(m, telefonda)) : null}
            </div>
          );
        })}
      </>
    );
  };

  const hesapBolumu = (telefonda: boolean) => (
    <div className={`kabuk-hesap${telefonda ? ' telefonda' : ''}`}>
      <button
        type="button"
        className="kabuk-kisi"
        onClick={() => setHesapAcik(true)}
        title="Hesabım"
        disabled={telefonda}
      >
        <span className="bas-harf" aria-hidden="true">
          {basHarfler(kullanici?.ad ?? '?')}
        </span>
        <span className="metin">
          <span className="ad">{kullanici?.ad ?? '—'}</span>
          <span className="gorev">{gorevAdi}</span>
        </span>
      </button>
      {yonetici ? (
        <button type="button" className="kabuk-oge" onClick={() => setBaslangicAcik(true)}>
          <Bayrak boyut={19} />
          <span className="ad">Başlangıç ekranı</span>
          <span className="deger">{BASLANGIC_ADI[baslangicOku() ?? 'isler']}</span>
        </button>
      ) : null}
      {izinli('satis.kendi') ? (
        <button type="button" className="kabuk-oge" onClick={() => git('/bugun')}>
          <Liste boyut={19} />
          <span className="ad">Satış uygulaması</span>
        </button>
      ) : null}
      {gorevler.includes('teknik') ? (
        <button type="button" className="kabuk-oge" onClick={() => git('/islerim')}>
          <Alet boyut={19} />
          <span className="ad">İşlerim</span>
        </button>
      ) : null}
      <GorunumSatiri kutlamaGoster={telefonda} />
      <button type="button" className="kabuk-oge" onClick={cikisYap}>
        <Cikis boyut={19} />
        <span className="ad">Çıkış</span>
      </button>
    </div>
  );

  return (
    <BolumBaglami.Provider value={bolum}>
      <div className="yon">
        <aside className="kabuk-kenar" aria-label="Yönetim menüsü">
          <div className="kabuk-marka">
            <Marka boyut={34} />
            <div className="metin">
              <div className="ad">Saha Sistemi</div>
              <div className="alt">Dehanet EÇM · Bursa</div>
            </div>
          </div>
          <nav className="kabuk-menu" aria-label="Bölümler">
            {menuListesi(gorunen)}
          </nav>
          {hesapBolumu(false)}
        </aside>

        <div className="yon-govde">
          <BaglantiSeridi />
          {children}
        </div>

        <div className="kabuk-alt-sekme">
          <AltSekme ogeler={altOgeler} etiket="Yönetim bölümleri" />
        </div>

        <Panel acik={dahaAcik} kapat={() => setDahaAcik(false)} baslik="Daha">
          <nav className="kabuk-daha" aria-label="Diğer bölümler">
            {menuListesi(dahadakiler, true)}
          </nav>
          {hesapBolumu(true)}
        </Panel>

        <Panel acik={hesapAcik} kapat={() => setHesapAcik(false)} baslik={kullanici?.ad ?? 'Hesabım'} altBaslik={gorevAdi} genislik={380}>
          {hesapBolumu(true)}
        </Panel>

        <BaslangicSecimi
          acik={baslangicAcik}
          ilkKez={false}
          sec={(b) => {
            setBaslangicAcik(false);
            baslangicSec(b, false);
          }}
        />
      </div>
    </BolumBaglami.Provider>
  );
}

/** Görünüm: Sistem · Açık · Koyu (+ küçük kutlamalar anahtarı). */
function GorunumSatiri({ kutlamaGoster = true }: { kutlamaGoster?: boolean }) {
  const { gorunum, degistir } = useGorunum();
  const kutlama = useKutlama();
  return (
    <div className="kabuk-gorunum">
      <div className="bas">
        <Gorunum boyut={19} />
        <span>Görünüm</span>
      </div>
      <Segment<GorunumTuru>
        etiket="Görünüm"
        kucuk
        tam
        deger={gorunum}
        degisti={degistir}
        secenekler={(['sistem', 'acik', 'koyu'] as GorunumTuru[]).map((g) => ({ deger: g, etiket: GORUNUM_ETIKET[g] }))}
      />
      {kutlamaGoster ? (
        <label className="kabuk-kutlama">
          <input type="checkbox" checked={kutlama.acik} onChange={(o) => kutlama.degistir(o.target.checked)} />
          <span>Küçük kutlamalar (iş bitince kısa bir işaret)</span>
        </label>
      ) : null}
    </div>
  );
}

/**
 * Gösterim verisi hapı (§6.0): yalnız demo ziyaret kullanan SATIŞ ekranlarında
 * (Canlı, Kapsama, Görev atama, Rapor) başlığın yanında. İşler, Aranacaklar,
 * Öbekler, Ticketlar, Ekip'te yoktur.
 */
const DEMO_EKRANLARI = new Set<Bolum>(['canli', 'kapsama', 'atama', 'rapor']);

export function DemoUyarisi() {
  const { ozet } = useOturum();
  const bolum = useContext(BolumBaglami);
  if (!ozet?.demo || (bolum && !DEMO_EKRANLARI.has(bolum))) return null;
  return (
    <Hap renk="amber" baslik="Ekrandaki ziyaret, satış ve kapsama sayıları gerçek saha kaydı değildir.">
      Gösterim verisi
    </Hap>
  );
}

/**
 * Ekran başlığı — sayfanın üstüne yapışır. Altında "Bu ekranda ne yaparım?"
 * cümlesi (menüdeki bölümden; kapatılır, cihaz hatırlar). Telefonda 44 px'lik
 * çubuk olur: yalnız BİRİNCİL eylem görünür, diğerleri "…" içinde.
 */
export function YonUst({
  baslik,
  altYazi,
  children,
}: {
  baslik: string;
  altYazi?: ReactNode;
  children?: ReactNode;
}) {
  const bolum = useContext(BolumBaglami);
  const cumle = bolum ? EKRAN_CUMLESI[bolum] : undefined;
  const cocuklar = Children.toArray(children);
  const ikincilVar = cocuklar.some(
    (c) => isValidElement<{ className?: string }>(c) && !String(c.props.className ?? '').includes('birincil'),
  );
  return (
    <header className="yon-ust">
      <div className="yon-ust-satir">
        <div className="yon-ust-baslik">
          <h1>{baslik}</h1>
          <DemoUyarisi />
        </div>
        {cocuklar.length ? (
          <div className="yon-ust-sag">
            {children}
            {ikincilVar ? <UstTasma>{children}</UstTasma> : null}
          </div>
        ) : null}
      </div>
      {altYazi ? <div className="alt">{altYazi}</div> : null}
      {!altYazi && cumle && bolum ? <EkranCumlesi anahtar={bolum}>{cumle}</EkranCumlesi> : null}
    </header>
  );
}

/** Telefonda başlığın ikincil eylemleri: "…" → alttan liste. */
function UstTasma({ children }: { children: ReactNode }) {
  const [acik, setAcik] = useState(false);
  return (
    <>
      <button
        type="button"
        className="o-daha yon-ust-tasma-dugme"
        aria-label="Diğer eylemler"
        aria-expanded={acik}
        onClick={() => setAcik(true)}
      >
        <Daha boyut={20} />
      </button>
      {acik
        ? createPortal(
            <>
              <div className="o-menu-perde yon-ust-tasma-perde" onClick={() => setAcik(false)} aria-hidden="true" />
              <div className="yon-ust-tasma" role="menu" onClick={() => setAcik(false)}>
                {children}
                <button type="button" className="o-dugme genis" onClick={() => setAcik(false)}>
                  Vazgeç
                </button>
              </div>
            </>,
            document.body,
          )
        : null}
    </>
  );
}

export function Icerik({ children }: { children: ReactNode }) {
  return <div className="yon-icerik">{children}</div>;
}
