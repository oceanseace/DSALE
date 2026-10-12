/**
 * Yönetim kabuğu (OPERASYON_V2_SPEC §6.0): solda bölüm menüsü, sağda başlık +
 * içerik; telefonda alt sekmeler.
 *
 *   ≥ 1024 px  232 px sol menü: birimler (Operasyon · Saha · Altyapı · Depo ·
 *              Yönetim…), en çok bir birim açık (başlığa yeniden basınca kapanır).
 *              Altta: kişi + unvan, (Administrator dışında, izni olana) Satış
 *              uygulaması / İşlerim, Görünüm (+ Administrator önizleme), Çıkış. Markanın altında arama alanı
 *              (Ctrl+F · Ctrl+K · "/" ile de açılır).
 *   < 1024 px  menü yok; altta en çok 4 sekme (3 bölüm + "Daha"), kalanı
 *              "Daha" çekmecesinde. Her ekranın başlığı 44 px'lik çubuk olur;
 *              başlıkta büyüteç arama paletini açar.
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
import { git } from '../yol/rota';
import { useOturum } from '../yerel/oturum';
import { Cikis, Liste } from '../ortak/Ikon';
import { Marka } from '../ortak/Marka';
import { Segment } from '../ortak/Segment';
import { Panel } from '../ortak/Panel';
import { OnizlemeSecici } from '../ortak/OnizlemeSecici';
import { Hap } from '../ortak/Rozet';
import { useGorunum, GORUNUM_ETIKET, type Gorunum as GorunumTuru } from '../ortak/tema';
import { useKutlama } from '../ortak/Kutlama';
import { Alet, AsagiOk, Ayar, Daha, Gorunum } from './simgeler';
import { AyarlarPaneli } from './AyarlarPaneli';
import { basHarfler } from './parcalar';
import {
  BIRIMLER,
  BIRIM_ADI,
  BASLIKSIZ_BIRIMLER,
  MENU,
  bolumYolu,
  menuSuz,
  telefonSekmeleri,
  type Birim,
  type Bolum,
  type MenuTanimi,
} from './menu';
import { AltSekme, type AltSekmeOgesi } from '../ortak/AltBar';
import { BaglantiDurumu, BaglantiSeridi } from '../ortak/BaglantiSeridi';
import { DurumCubugu, DurumIcerigi, SimgeDugme } from '../ortak/Ilkel';
import { AramaDugmesi } from '../arama';
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

export function Kabuk({
  bolum,
  sayaclar = {},
  children,
}: {
  bolum: Bolum;
  sayaclar?: Partial<Record<Bolum, Sayac>>;
  children: ReactNode;
}) {
  const { kullanici, cikisYap, izinli, gorevler, gorevAdi, gercekAdministrator, onizleme } = useOturum();
  const gorunen = useMemo(() => menuSuz(izinli), [izinli]);
  const [dahaAcik, setDahaAcik] = useState(false);
  const [hesapAcik, setHesapAcik] = useState(false);
  const [ayarAcik, setAyarAcik] = useState(false);
  /* Tek birim açık: içinde bulunulan. Başka birimin başlığına basınca o açılır. */
  const etkinBirim = MENU.find((m) => m.bolum === bolum)?.birim ?? 'operasyon';
  const [acikBirim, setAcikBirim] = useState<Birim | null>(etkinBirim);
  useEffect(() => setAcikBirim(etkinBirim), [etkinBirim]);

  /* Sekme değişince "Daha" kapanır. */
  useEffect(() => setDahaAcik(false), [bolum]);

  /* Administrator (önizlemesizken) kısayola ihtiyaç duymaz: her şey menüde. */
  const kisayolGoster = !(gercekAdministrator && !onizleme);
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
        <m.Ikon boyut={telefonda ? 20 : 16} />
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
    const birimler = BIRIMLER.map((b) => ({ b, ogeler: liste.filter((m) => m.birim === b) })).filter(
      (x) => x.ogeler.length,
    );
    return (
      <>
        {birimler.map(({ b, ogeler }) => {
          if (BASLIKSIZ_BIRIMLER.has(b)) {
            return (
              <div key={b} className="kabuk-grup basliksiz">
                {ogeler.map((m) => menuOgesi(m, telefonda))}
              </div>
            );
          }
          const acik = telefonda || acikBirim === b;
          return (
            <div key={b} className={`kabuk-grup${b === etkinBirim ? ' etkin' : ''}`}>
              {telefonda ? (
                <div className="kabuk-grup-adi">{BIRIM_ADI[b]}</div>
              ) : (
                <button type="button" className="kabuk-grup-bas" aria-expanded={acik} onClick={() => setAcikBirim((o) => (o === b ? null : b))}>
                  <span>{BIRIM_ADI[b]}</span>
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
      {kisayolGoster && izinli('satis.kendi') ? (
        <button type="button" className="kabuk-oge" onClick={() => git('/bugun')}>
          <Liste boyut={16} />
          <span className="ad">Satış uygulaması</span>
        </button>
      ) : null}
      {kisayolGoster && gorevler.includes('teknik') ? (
        <button type="button" className="kabuk-oge" onClick={() => git('/islerim')}>
          <Alet boyut={16} />
          <span className="ad">İşlerim</span>
        </button>
      ) : null}
      <GorunumSatiri kutlamaGoster={telefonda} />
      <button type="button" className="kabuk-oge" onClick={() => setAyarAcik(true)}>
        <Ayar boyut={16} />
        <span className="ad">Ayarlar</span>
      </button>
      <OnizlemeSecici kucuk />
      <button type="button" className="kabuk-oge" onClick={cikisYap}>
        <Cikis boyut={16} />
        <span className="ad">Çıkış</span>
      </button>
    </div>
  );

  return (
    <BolumBaglami.Provider value={bolum}>
      <div className="yon">
        <aside className="kabuk-kenar" aria-label="Yönetim menüsü">
          <div className={`kabuk-marka${gercekAdministrator && !onizleme ? ' admin' : ''}`}>
            <Marka boyut={24} />
            <div className="metin">
              <div className="ad">Turkcell</div>
              <div className="alt">Bursa · Yalova</div>
            </div>
          </div>
          <div className="kabuk-ara">
            <AramaDugmesi />
          </div>
          <nav className="kabuk-menu" aria-label="Bölümler">
            {menuListesi(gorunen)}
          </nav>
          {hesapBolumu(false)}
        </aside>

        <div className="yon-govde">
          <BaglantiSeridi className="yalniz-telefon" />
          {children}
          <DurumCubugu>
            <BaglantiDurumu />
          </DurumCubugu>
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

        <AyarlarPaneli acik={ayarAcik} kapat={() => setAyarAcik(false)} />
        <Panel acik={hesapAcik} kapat={() => setHesapAcik(false)} baslik={kullanici?.ad ?? 'Hesabım'} altBaslik={gorevAdi} genislik={380}>
          {hesapBolumu(true)}
        </Panel>
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
        <Gorunum boyut={16} />
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
 * (Canlı, Kapsama, Görev atama, Rapor) başlığın yanında. TASKS, MAP,
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
 * Ekranın üst çubuğu — her ekranda aynı: başlık solda, eylemler sağda (TEK
 * birincil). Başlığın altına açıklama yazılmaz; `altYazi` (ör. "2.903 açık iş")
 * alttaki durum çubuğuna gider. Telefonda 44 px'lik
 * çubuk olur: yalnız BİRİNCİL eylem görünür, diğerleri "…" içinde.
 */
/** Başlıktaki eylem birincil mi: `className="o-dugme birincil"` ya da `<Dugme tur="birincil">`. */
function birincilMi(p: { className?: string; tur?: string }): boolean {
  return p.tur === 'birincil' || String(p.className ?? '').split(' ').includes('birincil');
}

export function YonUst({
  baslik,
  altYazi,
  children,
}: {
  baslik: string;
  altYazi?: ReactNode;
  children?: ReactNode;
}) {
  const cocuklar = Children.toArray(children);
  const ikincilVar = cocuklar.some(
    (c) => isValidElement<{ className?: string; tur?: string }>(c) && !birincilMi(c.props),
  );
  return (
    <header className="yon-ust">
      <div className="yon-ust-satir">
        <div className="yon-ust-baslik">
          <h1>{baslik}</h1>
          <DemoUyarisi />
        </div>
        <div className="yon-ust-sag">
          {children}
          {ikincilVar ? <UstTasma>{children}</UstTasma> : null}
          <AramaDugmesi bicim="simge" className="ara-yalniz-telefon" />
        </div>
      </div>
      {altYazi ? <DurumIcerigi>{altYazi}</DurumIcerigi> : null}
    </header>
  );
}

/** Telefonda başlığın ikincil eylemleri: "…" → alttan liste. */
function UstTasma({ children }: { children: ReactNode }) {
  const [acik, setAcik] = useState(false);
  return (
    <>
      <SimgeDugme etiket="Diğer eylemler" className="yon-ust-tasma-dugme" aria-expanded={acik} onClick={() => setAcik(true)}>
        <Daha boyut={20} />
      </SimgeDugme>
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
