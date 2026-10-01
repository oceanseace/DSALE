/**
 * Ekip (OPERASYON_V2_SPEC §6.10, EK-1, EK-2) — kişi ekle, görevini seç,
 * ayrılanı pasife al.
 *
 *   · Dört görev, bir kişide birden çok (EK-1): Satış · Operasyon · Teknik ·
 *     Yönetici + "Girişte açılacak ekran" (kümeden biri).
 *   · Girişsiz kişiler (EK-2): telefonu olmayan teknisyen BOSS Mobil ile çalışır;
 *     "Girişsiz · BOSS Mobil" rozeti. Telefon eklenince davet akışı çalışır.
 *   · "Rehberden içe al": Atmosfer/Pusula "Çalışanlar" listesi yapıştır →
 *     önizle → uygula. Unvan → görev eşlemesi buradan düzenlenir.
 *   · Silme korumalı (F13): kaydı olan silinmez, "Pasife al" önerilir; açık işi
 *     varsa önce işler aktarılır. `window.confirm` yok.
 *   · Davet kodu YALNIZ bir kez, "Davet kodu hazır" çekmecesinde görünür.
 *
 * Giriş telefon + 4 haneli PIN'dir. PIN'i kimse kimseye söylemez: yönetici
 * 6 haneli davet kodu verir, kişi ilk girişte kendi PIN'ini belirler.
 */

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useBildirim } from '../../ortak/Bildirim';
import { Uyari } from '../../ortak/Ikon';
import { Panel } from '../../ortak/Panel';
import { useOnay } from '../../ortak/Onay';
import { Liste, ListeSatiri } from '../../ortak/Liste';
import { Cip, CipSirasi } from '../../ortak/Suz';
import { Segment } from '../../ortak/Segment';
import { Hap, Rozet } from '../../ortak/Rozet';
import { Hikaye, type HikayeTonu } from '../../ortak/Hikaye';
import { BosDurum, HataKutusu, Iskelet } from '../../ortak/Bos';
import { KisiSecici } from '../../ortak/KisiSecici';
import { DahaMenusu } from '../../ortak/Menu';
import { eslesir } from '../../ortak/ara';
import { GOREV_ACIKLAMA, GOREV_ETIKET, ROLLER } from '../../ortak/yetki';
import { useOturum } from '../../depo/oturum';
import { SahaHatasi } from '../../api/istemci';
import type { Rol } from '../../api/tipler';
import {
  bugunCalismayanlar,
  bugunCalismiyorYaz,
  cihazCikis,
  davetKoduVer,
  gorevleriKaydet,
  isAktar,
  kullaniciGetir,
  kullaniciIliskileri,
  kullaniciKaydet,
  kullaniciSil,
  pinSifirla,
  rehberAktar,
  unvanEslemeOku,
  unvanEslemeYaz,
  yardimOku,
  yardimYaz,
  type KullaniciGirdisi,
} from '../api';
import { useYonetim } from '../depo';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { bolgeNumaralari, useBolgeSayisi } from './bolge/bolgeSayisi';
import { BasHarf, Kart } from '../ortak/parcalar';
import type { KullaniciIliskileri, RehberSonucu, UnvanKurali, YoneticiKullanici } from '../tipler';
import './ekip.css';

type Suzgec = 'hepsi' | Rol;

interface Taslak {
  id?: number;
  ad: string;
  telefon: string;
  gorevler: Rol[];
  rol: Rol;
  bolge: number | null;
  aktif: boolean;
  unvan: string;
  boss_ekip: string;
  kapasite: string;
  lider: boolean;
  masa: string;
  /** Kaydedilmiş hâli (görev değişti mi, uyarı için). */
  ilkGorevler?: Rol[];
  ilkRol?: Rol;
  obekler?: Array<{ id: number; ad: string }>;
  pin_var?: boolean;
  giris_var?: boolean;
}

const BOS: Taslak = {
  ad: '',
  telefon: '',
  gorevler: ['teknik'],
  rol: 'teknik',
  bolge: null,
  aktif: true,
  unvan: '',
  boss_ekip: '',
  kapasite: '15',
  lider: false,
  masa: '',
};

function gorevleri(k: YoneticiKullanici): Rol[] {
  const kume = new Set<Rol>(k.gorevler ?? []);
  kume.add(k.rol);
  return ROLLER.filter((r) => kume.has(r));
}

function hata(h: unknown, yedek: string): string {
  return h instanceof Error ? h.message : yedek;
}

/** "Teknik · Görükle, Özlüce" / "Satış · Bölge 3" / "Operasyon + Yönetici" */
function gorevBilgisi(k: YoneticiKullanici): string {
  const g = gorevleri(k);
  const parcalar: string[] = [g.map((r) => GOREV_ETIKET[r]).join(' + ')];
  if (g.includes('satisci')) parcalar.push(k.bolge ? `Bölge ${k.bolge}` : 'Bölgesiz');
  if (g.includes('teknik') && k.obekler?.length) parcalar.push(k.obekler.map((o) => o.ad).join(', '));
  return parcalar.join(' · ');
}

function durumRozeti(k: YoneticiKullanici): ReactNode {
  if (!k.aktif) return <Hap>Pasif</Hap>;
  if (k.giris_var === false) return <Rozet tur="girissiz" />;
  if (k.davet_suresi_doldu) return <Hap renk="amber">Davetin süresi doldu</Hap>;
  if (k.davet_bekliyor || !k.pin_var) return <Hap renk="mavi">Davet bekliyor</Hap>;
  return <Hap renk="yesil">Aktif</Hap>;
}

export function Ekip() {
  const { ekip, ekipYukleniyor, ekipTazele } = useYonetim();
  const { kullanici: ben, ozet, ozetiTazele } = useOturum();
  const { goster } = useBildirim();
  const [onayPenceresi, sor] = useOnay();
  const bolgeSayisi = useBolgeSayisi();

  const [suzgec, setSuzgec] = useState<Suzgec>('hepsi');
  const [arama, setArama] = useState('');
  const [taslak, setTaslak] = useState<Taslak | null>(null);
  const [taslakYukleniyor, setTaslakYukleniyor] = useState(false);
  const [kod, setKod] = useState<{ ad: string; kod: string; gecerlilik: string } | null>(null);
  const [rehberAcik, setRehberAcik] = useState(false);
  const [eslemeAcik, setEslemeAcik] = useState(false);
  const [gozdenAcik, setGozdenAcik] = useState(false);
  const [sil, setSil] = useState<{ kisi: YoneticiKullanici; il: KullaniciIliskileri } | null>(null);

  const kisiler = useMemo(
    () =>
      (ekip ?? [])
        .slice()
        // Aktifler önce; görev sırası (Yönetici · Operasyon · Teknik · Satış), sonra ad.
        .sort(
          (a, b) =>
            Number(!a.aktif) - Number(!b.aktif) ||
            ROLLER.indexOf(b.rol) - ROLLER.indexOf(a.rol) ||
            (a.bolge ?? 99) - (b.bolge ?? 99) ||
            a.ad.localeCompare(b.ad, 'tr'),
        ),
    [ekip],
  );

  const sayilar = useMemo(() => {
    const s: Record<Suzgec, number> = { hepsi: kisiler.length, satisci: 0, operasyon: 0, teknik: 0, yonetici: 0 };
    for (const k of kisiler) for (const g of gorevleri(k)) s[g] += 1;
    return s;
  }, [kisiler]);

  const gorunen = useMemo(
    () =>
      kisiler.filter(
        (k) =>
          (suzgec === 'hepsi' || gorevleri(k).includes(suzgec)) &&
          eslesir(`${k.ad} ${k.unvan ?? ''} ${k.boss_ekip ?? ''} ${gorevBilgisi(k)}`, arama),
      ),
    [kisiler, suzgec, arama],
  );

  const hikaye = useMemo((): { cumle: string; ton: HikayeTonu } | null => {
    if (!kisiler.length) return null;
    const aktif = kisiler.filter((k) => k.aktif);
    const girissiz = aktif.filter((k) => k.giris_var === false).length;
    const doldu = aktif.filter((k) => k.davet_suresi_doldu).length;
    // Görev sayıları AKTİF kişilerden; birden çok görevi olan her görevde sayılır,
    // bu yüzden toplam kişi sayısını aşabilir — cümle bunu açıkça söyler.
    const aktifSayi: Record<Rol, number> = { satisci: 0, operasyon: 0, teknik: 0, yonetici: 0 };
    for (const k of aktif) for (const g of gorevleri(k)) aktifSayi[g] += 1;
    const cokGorevli = aktif.filter((k) => gorevleri(k).length > 1).length;
    const parca = (ROLLER.slice().reverse() as Rol[])
      .filter((r) => aktifSayi[r])
      .map((r) => `${aktifSayi[r]} ${GOREV_ETIKET[r].toLocaleLowerCase('tr-TR')}`);
    let cumle = `Ekipte ${aktif.length} aktif kişi var: ${parca.join(', ')}.`;
    if (cokGorevli) cumle += ` ${cokGorevli} kişinin birden çok görevi var.`;
    if (girissiz) cumle += ` ${girissiz} kişi girişsiz, işini BOSS Mobil ile yapıyor.`;
    if (doldu) return { cumle: `${cumle} ${doldu} kişinin davet kodunun süresi doldu — yeni kod verin.`, ton: 'dikkat' };
    return { cumle, ton: 'sakin' };
  }, [kisiler]);

  const kullanilanBolgeler = useMemo(
    () =>
      new Set(
        kisiler
          .filter((k) => gorevleri(k).includes('satisci') && k.aktif)
          .map((k) => k.bolge)
          .filter((b): b is number => Boolean(b)),
      ),
    [kisiler],
  );

  /* ------------------------------ Kişi aç / kaydet ------------------------------ */

  const kisiAc = async (k: YoneticiKullanici) => {
    setTaslakYukleniyor(true);
    try {
      // Tam telefon yalnız tek kişi yanıtında gelir; kaydetmede kaybolmasın.
      const tam = await kullaniciGetir(k.id).catch(() => k);
      const g = gorevleri(tam);
      setTaslak({
        id: tam.id,
        ad: tam.ad,
        telefon: tam.telefon ?? '',
        gorevler: g,
        rol: tam.rol,
        bolge: tam.bolge,
        aktif: tam.aktif,
        unvan: tam.unvan ?? '',
        boss_ekip: tam.boss_ekip ?? '',
        kapasite: tam.kapasite ? String(tam.kapasite) : '',
        lider: (tam.etiket ?? []).includes('lider'),
        masa: (tam.etiket ?? []).filter((e) => e !== 'lider').join(', '),
        ilkGorevler: g,
        ilkRol: tam.rol,
        obekler: tam.obekler ?? k.obekler,
        pin_var: tam.pin_var,
        giris_var: tam.giris_var ?? Boolean(tam.telefon),
      });
    } finally {
      setTaslakYukleniyor(false);
    }
  };

  const girdiYap = (t: Taslak): KullaniciGirdisi => {
    const etiket = [
      ...(t.lider && t.gorevler.includes('teknik') ? ['lider'] : []),
      ...(t.gorevler.includes('operasyon')
        ? t.masa
            .split(',')
            .map((s) => s.trim().toLocaleLowerCase('tr-TR'))
            .filter(Boolean)
        : []),
    ];
    return {
      id: t.id,
      ad: t.ad.trim(),
      telefon: t.telefon.replace(/\D/g, '') || null,
      rol: t.gorevler.includes(t.rol) ? t.rol : t.gorevler[0],
      gorevler: t.gorevler,
      bolge: t.gorevler.includes('satisci') ? t.bolge : null,
      etiket,
      boss_ekip: t.gorevler.includes('teknik') ? t.boss_ekip.trim() || null : null,
      kapasite: t.gorevler.includes('teknik') && t.kapasite ? Number(t.kapasite) : null,
      unvan: t.unvan.trim() || null,
      aktif: t.aktif,
    };
  };

  /* ------------------------------ Pasife al / aktif et ------------------------------ */

  const aktiflikDegistir = async (k: YoneticiKullanici, aktif: boolean) => {
    const tam = await kullaniciGetir(k.id).catch(() => null);
    if (!tam) {
      goster('Kişi okunamadı; tekrar deneyin.', 'uyari');
      return false;
    }
    try {
      await kullaniciKaydet({
        id: tam.id,
        ad: tam.ad,
        telefon: tam.telefon ?? null,
        rol: tam.rol,
        gorevler: gorevleri(tam),
        bolge: tam.bolge,
        aktif,
      });
      ekipTazele();
      goster(aktif ? `${tam.ad} yeniden aktif.` : `${tam.ad} pasife alındı. Giriş yapamaz; geçmişi olduğu gibi kaldı.`, 'basari');
      return true;
    } catch (h) {
      goster(hata(h, 'Değiştirilemedi.'), 'uyari');
      return false;
    }
  };

  /* ------------------------------ Sil (F13) ------------------------------ */

  const silBaslat = async (k: YoneticiKullanici) => {
    let il: KullaniciIliskileri;
    try {
      il = await kullaniciIliskileri(k.id);
    } catch (h) {
      goster(hata(h, 'Kayıtlar sayılamadı.'), 'uyari');
      return;
    }
    if (il.engeller.includes('kendini_silemez') || il.engeller.includes('son_yonetici')) {
      goster(
        il.engeller.includes('son_yonetici')
          ? 'Son aktif yönetici silinemez.'
          : 'Kendinizi silemezsiniz.',
        'uyari',
      );
      return;
    }
    if (il.engeller.includes('iliskili_kayit')) {
      setTaslak(null);
      setSil({ kisi: k, il });
      return;
    }
    const obekli = il.obek_sahipligi > 0;
    const evet = await sor({
      baslik: obekli ? `${k.ad} silinsin mi?` : `${k.ad} kalıcı olarak silinsin mi?`,
      metin: obekli
        ? `${k.ad} ${il.obek_sahipligi} öbeğin ev teknisyeni; silinirse öbekler teknisyensiz kalır.`
        : 'Bu işlem geri alınamaz.',
      onay: 'Sil',
      yikici: true,
    });
    if (!evet) return;
    try {
      await kullaniciSil(k.id, obekli);
      setTaslak(null);
      ekipTazele();
      goster(`${k.ad} silindi.`, 'basari');
    } catch (h) {
      goster(hata(h, 'Silinemedi.'), 'uyari');
    }
  };

  const yonetici = kisiler.length > 0;

  return (
    <>
      <YonUst baslik="Ekip">
        <button type="button" className="yd" onClick={() => setRehberAcik(true)}>
          Rehberden içe al
        </button>
        <button type="button" className="yd" onClick={() => setEslemeAcik(true)}>
          Unvan eşlemesi
        </button>
        <button type="button" className="yd birincil" onClick={() => setTaslak({ ...BOS, gorevler: ['teknik'], rol: 'teknik' })}>
          + Kişi ekle
        </button>
      </YonUst>

      <Icerik>
        {hikaye ? <Hikaye cumle={hikaye.cumle} ton={hikaye.ton} /> : null}

        {ozet?.gorev_gozden_gecir ? (
          <div className="ekip-gozden">
            <div className="metin">
              <strong>Görevler artık dört çeşit</strong>
              <span>
                {sayilar.yonetici} kişi “Yönetici” görünüyor. Gerçek görevlerini seçin; kimse erişim kaybetmez.
              </span>
            </div>
            <button type="button" className="o-dugme" onClick={() => setGozdenAcik(true)}>
              Gözden geçir
            </button>
          </div>
        ) : null}

        <div className="ekip-arac">
          <Segment<Suzgec>
            etiket="Göreve göre süz"
            deger={suzgec}
            degisti={setSuzgec}
            secenekler={[
              { deger: 'hepsi', etiket: 'Hepsi', sayi: sayilar.hepsi },
              ...ROLLER.map((r) => ({ deger: r, etiket: GOREV_ETIKET[r], sayi: sayilar[r] })),
            ]}
          />
          <label className="o-arama ekip-ara">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
              <circle cx="11" cy="11" r="6.5" />
              <path d="m16 16 4 4" strokeLinecap="round" />
            </svg>
            <input type="search" value={arama} onChange={(o) => setArama(o.target.value)} placeholder="Ad, unvan, öbek…" aria-label="Ekipte ara" />
          </label>
        </div>

        {ekipYukleniyor && !kisiler.length ? (
          <Iskelet satir={6} yukseklik={60} />
        ) : !yonetici || kisiler.length <= 1 ? (
          <div className="o-liste">
            {kisiler.map((k) => (
              <KisiSatiri key={k.id} k={k} ac={() => void kisiAc(k)} ben={ben?.id === k.id} />
            ))}
            <BosDurum
              simge="👥"
              baslik="Ekibinizi ekleyin"
              aciklama="Telefon numarası yeter; kişi ilk girişte kendi PIN'ini belirler. BOSS Mobil ile çalışan teknisyenleri telefonsuz ekleyebilir ya da rehberden içe alabilirsiniz."
            >
              <button type="button" className="o-dugme birincil" onClick={() => setTaslak({ ...BOS })}>
                + Kişi ekle
              </button>
            </BosDurum>
          </div>
        ) : gorunen.length ? (
          <Liste etiket="Ekip">
            {gorunen.map((k) => (
              <KisiSatiri key={k.id} k={k} ac={() => void kisiAc(k)} ben={ben?.id === k.id} />
            ))}
          </Liste>
        ) : (
          <div className="o-liste">
            <BosDurum kucuk baslik="Bu süzgeçte kimse yok." aciklama="Süzgeci “Hepsi” yapın ya da aramayı temizleyin." />
          </div>
        )}

        {kullanilanBolgeler.size < bolgeSayisi && sayilar.satisci > 0 ? (
          <div className="yon-uyari">
            <Uyari boyut={18} />
            Satışçısı olmayan bölgeler:{' '}
            <b>
              {bolgeNumaralari(bolgeSayisi)
                .filter((b) => !kullanilanBolgeler.has(b))
                .join(', ')}
            </b>
          </div>
        ) : null}

        <YardimKarti />
      </Icerik>

      {/* ---------------- Kişi çekmecesi ---------------- */}
      <KisiCekmecesi
        taslak={taslak}
        setTaslak={setTaslak}
        yukleniyor={taslakYukleniyor}
        benId={ben?.id ?? null}
        bolgeSayisi={bolgeSayisi}
        girdiYap={girdiYap}
        kaydedildi={(ad, davet, gorevDegisti) => {
          ekipTazele();
          setTaslak(null);
          if (davet) setKod({ ad, kod: davet, gecerlilik: '48 saat' });
          else goster(gorevDegisti ? `${ad} kaydedildi. Bir kez yeniden giriş yapacak.` : `${ad} kaydedildi.`, 'basari');
        }}
        davet={(ad, k, gecerlilik) => setKod({ ad, kod: k, gecerlilik })}
        sil={(k) => void silBaslat(k)}
        aktiflik={aktiflikDegistir}
        kisiler={kisiler}
      />

      {/* ---------------- Davet kodu (yalnız bir kez) ---------------- */}
      <Panel
        acik={Boolean(kod)}
        kapat={() => setKod(null)}
        baslik="Davet kodu hazır"
        genislik={420}
        alt={
          <>
            <button
              type="button"
              className="o-dugme"
              onClick={() => {
                if (!kod) return;
                void navigator.clipboard?.writeText(kod.kod).then(
                  () => goster('Kod kopyalandı.', 'basari'),
                  () => goster('Kopyalanamadı; kodu okuyun.', 'uyari'),
                );
              }}
            >
              Kodu kopyala
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => setKod(null)}>
              Tamam
            </button>
          </>
        }
      >
        {kod ? (
          <div className="ekip-kod">
            <p>
              <strong>{kod.ad}</strong> ilk girişte bu kodu yazıp kendi PIN’ini belirleyecek.
            </p>
            <span className="kod" aria-label={`Kod ${kod.kod.split('').join(' ')}`}>
              {kod.kod.slice(0, 3)} {kod.kod.slice(3)}
            </span>
            <p className="alt">
              {kod.gecerlilik} geçerli. Kişiye telefonla söyleyin; bu kod bir daha gösterilmez.
            </p>
          </div>
        ) : null}
      </Panel>

      {/* ---------------- Silinemez: pasife al / işleri aktar ---------------- */}
      <SilinemezPaneli
        durum={sil}
        kapat={() => setSil(null)}
        kisiler={kisiler}
        pasifeAl={async (k) => {
          if (await aktiflikDegistir(k, false)) setSil(null);
        }}
        aktarildi={async (k) => {
          const il = await kullaniciIliskileri(k.id).catch(() => null);
          if (il) setSil({ kisi: k, il });
        }}
      />

      <RehberPaneli acik={rehberAcik} kapat={() => setRehberAcik(false)} bitti={() => ekipTazele()} esleme={() => setEslemeAcik(true)} />
      <EslemePaneli acik={eslemeAcik} kapat={() => setEslemeAcik(false)} />
      <GozdenGecirPaneli
        acik={gozdenAcik}
        kapat={() => setGozdenAcik(false)}
        kisiler={kisiler.filter((k) => k.aktif)}
        benId={ben?.id ?? null}
        bolgeSayisi={bolgeSayisi}
        bitti={() => {
          ekipTazele();
          void ozetiTazele();
        }}
      />
      {onayPenceresi}
    </>
  );
}

/* ------------------------------ Liste satırı ------------------------------ */

function KisiSatiri({ k, ac, ben }: { k: YoneticiKullanici; ac: () => void; ben: boolean }) {
  return (
    <ListeSatiri
      soluk={!k.aktif}
      onClick={ac}
      sol={<BasHarf ad={k.ad} anahtar={k.id} boyut={36} />}
      baslik={
        <>
          {k.ad}
          {ben ? <span className="ekip-sen"> (siz)</span> : null}
        </>
      }
      alt={gorevBilgisi(k)}
      ucuncu={k.unvan || (k.giris_var !== false ? k.telefon_goster : undefined)}
      sag={durumRozeti(k)}
    />
  );
}

/* ------------------------------ Kişi çekmecesi ------------------------------ */

function KisiCekmecesi({
  taslak,
  setTaslak,
  yukleniyor,
  benId,
  bolgeSayisi,
  girdiYap,
  kaydedildi,
  davet,
  sil,
  aktiflik,
  kisiler,
}: {
  taslak: Taslak | null;
  setTaslak: (t: Taslak | null) => void;
  yukleniyor: boolean;
  benId: number | null;
  bolgeSayisi: number;
  girdiYap: (t: Taslak) => KullaniciGirdisi;
  kaydedildi: (ad: string, davet: string | null, gorevDegisti: boolean) => void;
  davet: (ad: string, kod: string, gecerlilik: string) => void;
  sil: (k: YoneticiKullanici) => void;
  aktiflik: (k: YoneticiKullanici, aktif: boolean) => Promise<boolean>;
  kisiler: YoneticiKullanici[];
}) {
  const { goster } = useBildirim();
  const [onayPenceresi, sor] = useOnay();
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [hataMetni, setHataMetni] = useState<string | null>(null);
  /* §6.10 "Bugün çalışmıyor": yalnız kayıtlı, aktif teknikte; anında yazılır (Kaydet beklemez). */
  const [bugunYok, setBugunYok] = useState<boolean | null>(null);
  const [bugunYokYaziliyor, setBugunYokYaziliyor] = useState(false);
  const teknikKayitli = Boolean(
    taslak?.id !== undefined && kisiler.find((k) => k.id === taslak?.id)?.aktif && taslak?.ilkGorevler?.includes('teknik'),
  );

  useEffect(() => setHataMetni(null), [taslak?.id]);
  useEffect(() => {
    setBugunYok(null);
    if (!teknikKayitli || taslak?.id === undefined) return undefined;
    let iptal = false;
    const id = taslak.id;
    bugunCalismayanlar()
      .then((s) => !iptal && setBugunYok(s.has(id)))
      .catch(() => {
        /* anahtar yalnız bilgi; okunamazsa gösterilmez */
      });
    return () => {
      iptal = true;
    };
  }, [taslak?.id, teknikKayitli]);

  if (!taslak) return <>{onayPenceresi}</>;
  const t = taslak;
  const kendisi = t.id !== undefined && t.id === benId;
  const kayitli = kisiler.find((k) => k.id === t.id) ?? null;
  const gorevDegisti =
    t.id !== undefined &&
    (t.rol !== t.ilkRol || t.gorevler.join() !== (t.ilkGorevler ?? []).join());
  const telefonVar = t.telefon.replace(/\D/g, '').length > 0;

  const gorevDegistir = (r: Rol) => {
    if (kendisi) return;
    const var_ = t.gorevler.includes(r);
    if (var_ && t.gorevler.length === 1) return; // en az bir görev
    const yeni = var_ ? t.gorevler.filter((x) => x !== r) : ROLLER.filter((x) => x === r || t.gorevler.includes(x));
    setTaslak({ ...t, gorevler: yeni, rol: yeni.includes(t.rol) ? t.rol : yeni[0] });
  };

  const kaydet = async () => {
    setHataMetni(null);
    const tel = t.telefon.replace(/\D/g, '');
    if (t.ad.trim().length < 2) return setHataMetni('Ad soyad yazın.');
    if (tel && tel.replace(/^0+/, '').length !== 10) return setHataMetni('Telefonu 10 hane olarak yazın (5XX…) ya da boş bırakın.');
    if (t.gorevler.includes('satisci') && !t.bolge) return setHataMetni('Satış görevi için bölge seçin.');
    if (t.kapasite && (Number(t.kapasite) < 1 || Number(t.kapasite) > 60)) return setHataMetni('Günlük kapasite 1–60 arası olmalı.');
    setKaydediliyor(true);
    try {
      const y = await kullaniciKaydet(girdiYap(t));
      kaydedildi(y.kullanici.ad, y.davet_kodu ?? null, Boolean(y.oturum_dustu && gorevDegisti));
    } catch (h) {
      setHataMetni(hata(h, 'Kaydedilemedi.'));
    } finally {
      setKaydediliyor(false);
    }
  };

  const ikincil = kayitli
    ? [
        ...(kayitli.giris_var !== false && kayitli.pin_var
          ? [
              {
                etiket: 'PIN’i sıfırla',
                calistir: async () => {
                  const evet = await sor({
                    baslik: `${kayitli.ad} için PIN sıfırlansın mı?`,
                    metin: 'Eski PIN silinir, açık oturumu kapanır. Yeni davet kodu verilir.',
                    onay: 'PIN’i sıfırla',
                  });
                  if (!evet) return;
                  try {
                    const y = await pinSifirla(kayitli.id);
                    setTaslak(null);
                    davet(kayitli.ad, y.davet_kodu, '48 saat');
                  } catch (h) {
                    goster(hata(h, 'PIN sıfırlanamadı.'), 'uyari');
                  }
                },
              },
              {
                etiket: 'Cihazlardan çıkış yaptır',
                calistir: async () => {
                  const evet = await sor({
                    baslik: `${kayitli.ad} bütün cihazlardan çıksın mı?`,
                    metin: 'Telefon kaybolduysa ilk yapılacak budur. PIN aynı kalır; kişi yeni telefonundan girebilir.',
                    onay: 'Çıkış yaptır',
                  });
                  if (!evet) return;
                  try {
                    const y = await cihazCikis(kayitli.id);
                    goster(y.mesaj, 'basari');
                  } catch (h) {
                    goster(hata(h, 'Çıkış yaptırılamadı.'), 'uyari');
                  }
                },
              },
            ]
          : []),
        ...(kayitli.giris_var !== false && !kayitli.pin_var
          ? [
              {
                etiket: 'Yeni davet kodu',
                calistir: async () => {
                  try {
                    const y = await davetKoduVer(kayitli.id);
                    setTaslak(null);
                    davet(kayitli.ad, y.davet_kodu, y.gecerlilik);
                  } catch (h) {
                    goster(hata(h, 'Kod verilemedi.'), 'uyari');
                  }
                },
              },
            ]
          : []),
        ...(!kendisi
          ? [
              kayitli.aktif
                ? {
                    etiket: 'Pasife al',
                    calistir: async () => {
                      const evet = await sor({
                        baslik: `${kayitli.ad} pasife alınsın mı?`,
                        metin: 'Giriş yapamaz; geçmiş kayıtları olduğu gibi kalır. İstediğinizde yeniden aktif edebilirsiniz.',
                        onay: 'Pasife al',
                      });
                      if (evet && (await aktiflik(kayitli, false))) setTaslak(null);
                    },
                  }
                : {
                    etiket: 'Yeniden aktif et',
                    calistir: async () => {
                      if (await aktiflik(kayitli, true)) setTaslak(null);
                    },
                  },
              { etiket: 'Kişiyi sil', yikici: true, calistir: () => sil(kayitli) },
            ]
          : []),
      ]
    : [];

  return (
    <>
      <Panel
        acik
        kapat={() => setTaslak(null)}
        kilitli={kaydediliyor}
        baslik={t.id ? t.ad || 'Kişi' : 'Yeni kişi'}
        altBaslik={
          t.id
            ? kayitli
              ? gorevBilgisi(kayitli)
              : undefined
            : 'Telefonu olan kişiye kaydedince 6 haneli davet kodu verilir.'
        }
        basSag={ikincil.length ? <DahaMenusu ogeler={ikincil} etiket="Kişi eylemleri" /> : null}
        alt={
          <>
            <button type="button" className="o-dugme" onClick={() => setTaslak(null)} disabled={kaydediliyor}>
              Vazgeç
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => void kaydet()} disabled={kaydediliyor || yukleniyor}>
              {kaydediliyor ? 'Kaydediliyor…' : 'Kaydet'}
            </button>
          </>
        }
      >
        <div className="ekip-form">
          <label className="o-alan">
            <span className="etiket">Ad soyad</span>
            <input value={t.ad} autoFocus={!t.id} onChange={(o) => setTaslak({ ...t, ad: o.target.value })} />
          </label>

          <label className="o-alan">
            <span className="etiket">Telefon</span>
            <input
              inputMode="numeric"
              value={t.telefon}
              placeholder="5XX XXX XX XX"
              onChange={(o) => setTaslak({ ...t, telefon: o.target.value.replace(/[^\d+ ]/g, '') })}
            />
            <span className="aciklama">
              {telefonVar
                ? 'Bu telefonla giriş yapar.'
                : 'Boş bırakılırsa girişsiz kişi olur: işini BOSS Mobil ile yapar, iş yine ona atanabilir.'}
            </span>
          </label>

          <fieldset className="ekip-gorevler">
            <legend className="etiket">Görevler</legend>
            {kendisi ? <p className="aciklama">Kendi görevinizi değiştiremezsiniz.</p> : null}
            {ROLLER.map((r) => {
              const secili = t.gorevler.includes(r);
              return (
                <label key={r} className={`ekip-gorev${secili ? ' secili' : ''}${kendisi ? ' kilitli' : ''}`}>
                  <input type="checkbox" checked={secili} disabled={kendisi} onChange={() => gorevDegistir(r)} />
                  <span className="metin">
                    <strong>{GOREV_ETIKET[r]}</strong>
                    <span>{GOREV_ACIKLAMA[r]}</span>
                  </span>
                </label>
              );
            })}
          </fieldset>

          {t.gorevler.length > 1 ? (
            <div className="o-alan">
              <span className="etiket">Girişte açılacak ekran</span>
              <Segment<Rol>
                etiket="Girişte açılacak ekran"
                tam
                deger={t.rol}
                degisti={(r) => !kendisi && setTaslak({ ...t, rol: r })}
                secenekler={t.gorevler.map((r) => ({ deger: r, etiket: GOREV_ETIKET[r], kapali: kendisi }))}
              />
            </div>
          ) : null}

          {gorevDegisti ? (
            <p className="ekip-not">Bu kişi bir kez yeniden giriş yapacak. PIN’i aynı kalır.</p>
          ) : null}

          {t.gorevler.includes('satisci') ? (
            <label className="o-alan">
              <span className="etiket">Bölge (satış için zorunlu)</span>
              <select value={t.bolge ?? ''} onChange={(o) => setTaslak({ ...t, bolge: o.target.value ? Number(o.target.value) : null })}>
                <option value="">Seçin…</option>
                {bolgeNumaralari(bolgeSayisi).map((b) => (
                  <option key={b} value={b}>
                    {b}. bölge
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {t.gorevler.includes('teknik') ? (
            <div className="ekip-teknik">
              <div className="o-alan">
                <span className="etiket">Ev öbekleri</span>
                <span className="deger">
                  {t.obekler?.length ? t.obekler.map((o) => o.ad).join(', ') : 'Henüz yok — Öbekler ekranından ev teknisyeni seçilir.'}
                </span>
              </div>
              <div className="ekip-ikili">
                <label className="o-alan">
                  <span className="etiket">BOSS’taki ekip adı</span>
                  <input value={t.boss_ekip} onChange={(o) => setTaslak({ ...t, boss_ekip: o.target.value })} placeholder="BOSS raporundaki “Ekip”" />
                </label>
                <label className="o-alan">
                  <span className="etiket">Günlük kapasite</span>
                  <input
                    inputMode="numeric"
                    value={t.kapasite}
                    placeholder="15"
                    onChange={(o) => setTaslak({ ...t, kapasite: o.target.value.replace(/\D/g, '').slice(0, 2) })}
                  />
                </label>
              </div>
              <label className="o-onay-kutusu">
                <input type="checkbox" checked={t.lider} onChange={(o) => setTaslak({ ...t, lider: o.target.checked })} />
                <span>Teknik lider (yetki vermez; listede işaretlenir)</span>
              </label>
              {bugunYok !== null && t.id !== undefined ? (
                <label className="o-onay-kutusu">
                  <input
                    type="checkbox"
                    checked={bugunYok}
                    disabled={bugunYokYaziliyor}
                    onChange={async (o) => {
                      const yok = o.target.checked;
                      setBugunYokYaziliyor(true);
                      try {
                        await bugunCalismiyorYaz(t.id as number, yok);
                        setBugunYok(yok);
                        goster(yok ? `${t.ad} bugün çalışmıyor olarak işaretlendi.` : `${t.ad} bugün çalışıyor.`, 'basari');
                      } catch (h) {
                        goster(hata(h, 'Kaydedilemedi.'), 'uyari');
                      } finally {
                        setBugunYokYaziliyor(false);
                      }
                    }}
                  />
                  <span>Bugün çalışmıyor (yalnız bugün; atama listesinde işaretlenir)</span>
                </label>
              ) : null}
            </div>
          ) : null}

          {t.gorevler.includes('operasyon') ? (
            <label className="o-alan">
              <span className="etiket">Masa etiketi (isteğe bağlı)</span>
              <input value={t.masa} onChange={(o) => setTaslak({ ...t, masa: o.target.value })} placeholder="btk, arama" />
            </label>
          ) : null}

          <label className="o-alan">
            <span className="etiket">Unvan (isteğe bağlı)</span>
            <input value={t.unvan} onChange={(o) => setTaslak({ ...t, unvan: o.target.value })} placeholder="Teknik - Sorumlu" />
          </label>

          {t.id && !t.aktif ? <p className="ekip-not">Bu kişi pasif: giriş yapamaz. “…” menüsünden yeniden aktif edebilirsiniz.</p> : null}

          {hataMetni ? <HataKutusu mesaj={hataMetni} /> : null}
        </div>
      </Panel>
      {onayPenceresi}
    </>
  );
}

/* ------------------------------ Silinemez paneli ------------------------------ */

function SilinemezPaneli({
  durum,
  kapat,
  kisiler,
  pasifeAl,
  aktarildi,
}: {
  durum: { kisi: YoneticiKullanici; il: KullaniciIliskileri } | null;
  kapat: () => void;
  kisiler: YoneticiKullanici[];
  pasifeAl: (k: YoneticiKullanici) => Promise<void>;
  aktarildi: (k: YoneticiKullanici) => Promise<void>;
}) {
  const { goster } = useBildirim();
  const [aktarim, setAktarim] = useState(false);
  const [hedef, setHedef] = useState<number | null>(null);
  const [bekliyor, setBekliyor] = useState(false);

  useEffect(() => {
    setAktarim(false);
    setHedef(null);
  }, [durum?.kisi.id]);

  if (!durum) return null;
  const { kisi, il } = durum;
  const kayitlar = il.etiketler
    .filter((e) => !e.metin.startsWith('öbeğin'))
    .map((e) => `${e.sayi.toLocaleString('tr-TR')} ${e.metin}`);
  const teknikler = kisiler
    .filter((k) => k.aktif && k.id !== kisi.id && gorevleri(k).includes('teknik'))
    .map((k) => ({ id: k.id, ad: k.ad, bilgi: k.obekler?.map((o) => o.ad).join(', ') || undefined }));

  const aktar = async () => {
    if (!hedef) return;
    setBekliyor(true);
    try {
      const y = await isAktar(kisi.id, hedef);
      goster(`${y.aktarilan} iş aktarıldı.`, 'basari');
      setAktarim(false);
      await aktarildi(kisi);
    } catch (h) {
      goster(hata(h, 'İşler aktarılamadı.'), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <Panel
      acik
      kapat={kapat}
      kilitli={bekliyor}
      baslik={`${kisi.ad} silinemez`}
      genislik={460}
      alt={
        aktarim ? (
          <>
            <button type="button" className="o-dugme" onClick={() => setAktarim(false)} disabled={bekliyor}>
              Geri
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => void aktar()} disabled={!hedef || bekliyor}>
              {bekliyor ? 'Aktarılıyor…' : 'İşleri aktar'}
            </button>
          </>
        ) : il.acik_is > 0 ? (
          <>
            <button type="button" className="o-dugme" onClick={kapat}>
              Vazgeç
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => setAktarim(true)}>
              İşleri aktar
            </button>
          </>
        ) : (
          <>
            <button type="button" className="o-dugme" onClick={kapat}>
              Vazgeç
            </button>
            <button type="button" className="o-dugme birincil" onClick={() => void pasifeAl(kisi)} disabled={!kisi.aktif}>
              {kisi.aktif ? 'Pasife al' : 'Zaten pasif'}
            </button>
          </>
        )
      }
    >
      {aktarim ? (
        <div className="ekip-form">
          <p className="ekip-paragraf">
            {kisi.ad} adlı kişinin {il.acik_is} açık işi kime geçsin? Her iş kendi kaydıyla aktarılır.
          </p>
          <KisiSecici kisiler={teknikler} deger={hedef} degisti={setHedef} yerTutucu="Teknisyen adı yazın…" bosMetin="Aktif teknik görevli yok." />
        </div>
      ) : (
        <div className="ekip-form">
          <p className="ekip-paragraf">
            {kayitlar.length ? `${kayitlar.join(', ')} var. ` : ''}Kayıtlar korunmalı. Pasife alırsanız giriş yapamaz, geçmişi olduğu gibi kalır.
          </p>
          {il.acik_is > 0 ? (
            <p className="ekip-not">Önce {il.acik_is} açık işi başka teknisyene aktarın.</p>
          ) : null}
          {il.hepsi_demo ? (
            <p className="ekip-paragraf soluk">Bu kayıtların hepsi gösterim verisi; gösterim verisi temizlenince silinebilir.</p>
          ) : null}
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------ Rehberden içe al (EK-2) ------------------------------ */

function RehberPaneli({
  acik,
  kapat,
  bitti,
  esleme,
}: {
  acik: boolean;
  kapat: () => void;
  bitti: () => void;
  esleme: () => void;
}) {
  const { goster } = useBildirim();
  const [metin, setMetin] = useState('');
  const [onizleme, setOnizleme] = useState<RehberSonucu | null>(null);
  const [bekliyor, setBekliyor] = useState(false);
  const [hataMetni, setHataMetni] = useState<string | null>(null);
  const [acikListe, setAcikListe] = useState<'eklenecek' | 'guncellenecek' | 'atlanacak' | null>('eklenecek');

  useEffect(() => {
    if (!acik) {
      setOnizleme(null);
      setHataMetni(null);
    }
  }, [acik]);

  const onizle = async () => {
    setBekliyor(true);
    setHataMetni(null);
    try {
      const y = await rehberAktar(metin, false);
      if (!y.okunan) {
        setHataMetni('Metinde kişi bulunamadı. Listede her kişinin adı bir satırda, unvanı alt satırda olmalı.');
        return;
      }
      setOnizleme(y);
      setAcikListe(y.eklenecek.length ? 'eklenecek' : y.guncellenecek.length ? 'guncellenecek' : 'atlanacak');
    } catch (h) {
      setHataMetni(hata(h, 'Önizleme yapılamadı.'));
    } finally {
      setBekliyor(false);
    }
  };

  const uygula = async () => {
    setBekliyor(true);
    try {
      const y = await rehberAktar(metin, true);
      bitti();
      kapat();
      setMetin('');
      goster(
        `${y.sayilar.eklenecek} kişi eklendi (girişsiz), ${y.sayilar.guncellenecek} unvan güncellendi.`,
        'basari',
      );
    } catch (h) {
      setHataMetni(hata(h, 'Uygulanamadı.'));
    } finally {
      setBekliyor(false);
    }
  };

  const bolum = (
    anahtar: 'eklenecek' | 'guncellenecek' | 'atlanacak',
    baslik: string,
    satirlar: Array<{ ad: string; ek: string }>,
  ) => (
    <section className="rehber-bolum" key={anahtar}>
      <button
        type="button"
        className="rehber-bas"
        aria-expanded={acikListe === anahtar}
        onClick={() => setAcikListe((a) => (a === anahtar ? null : anahtar))}
        disabled={!satirlar.length}
      >
        <span>{baslik}</span>
        <span className="sayi">{satirlar.length.toLocaleString('tr-TR')}</span>
      </button>
      {acikListe === anahtar && satirlar.length ? (
        <ul>
          {satirlar.map((s, i) => (
            <li key={i}>
              <span className="ad">{s.ad}</span>
              <span className="ek">{s.ek}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik="Rehberden içe al"
      altBaslik="Atmosfer ya da Pusula’daki “Çalışanlar” listesi"
      genislik={520}
      alt={
        onizleme ? (
          <>
            <button type="button" className="o-dugme" onClick={() => setOnizleme(null)} disabled={bekliyor}>
              Geri
            </button>
            <button
              type="button"
              className="o-dugme birincil"
              onClick={() => void uygula()}
              disabled={bekliyor || !(onizleme.sayilar.eklenecek + onizleme.sayilar.guncellenecek)}
            >
              {bekliyor ? 'Uygulanıyor…' : 'Uygula'}
            </button>
          </>
        ) : (
          <>
            <button type="button" className="o-dugme metin" onClick={esleme}>
              Unvan eşlemesi
            </button>
            <span className="bosluk" />
            <button type="button" className="o-dugme birincil" onClick={() => void onizle()} disabled={bekliyor || metin.trim().length < 5}>
              {bekliyor ? 'Okunuyor…' : 'Önizle'}
            </button>
          </>
        )
      }
    >
      {!onizleme ? (
        <div className="ekip-form">
          <ol className="rehber-adimlar">
            <li>Atmosfer ya da Pusula’da “Çalışanlar” listesini açın.</li>
            <li>Listeyi seçip kopyalayın (Ctrl+A, Ctrl+C).</li>
            <li>Aşağıya yapıştırın. Önce ne olacağını görürsünüz; hiçbir şey hemen değişmez.</li>
          </ol>
          <label className="o-alan">
            <span className="etiket">Yapıştırılan liste</span>
            <textarea
              value={metin}
              onChange={(o) => setMetin(o.target.value)}
              rows={10}
              placeholder={'Ad Soyad\nTeknik - Sorumlu\nAd Soyad\nSatış Destek - Uzman\n…'}
            />
          </label>
          <p className="ekip-paragraf soluk">
            Eşleşen kişinin yalnız unvanı güncellenir, görevine dokunulmaz. Yeni kişiler telefonsuz (girişsiz) eklenir;
            göreve eşlenmeyen unvanlar (Stok, Finans, İK…) alınmaz. İki kez uygulamak çift kayıt üretmez.
          </p>
          {hataMetni ? <HataKutusu mesaj={hataMetni} /> : null}
        </div>
      ) : (
        <div className="ekip-form">
          <p className="ekip-paragraf">
            {onizleme.okunan.toLocaleString('tr-TR')} kişi okundu
            {onizleme.ayni ? `; ${onizleme.ayni} kişi zaten aynı` : ''}
            {onizleme.okunamayan_satir ? `; ${onizleme.okunamayan_satir} satır okunamadı` : ''}.
          </p>
          {bolum(
            'eklenecek',
            'Eklenecek (girişsiz)',
            onizleme.eklenecek.map((e) => ({ ad: e.ad, ek: `${e.unvan ?? ''} → ${e.gorevler.map((g) => GOREV_ETIKET[g]).join(' + ')}` })),
          )}
          {bolum(
            'guncellenecek',
            'Unvanı güncellenecek',
            onizleme.guncellenecek.map((g) => ({ ad: g.ad, ek: `${g.unvan_eski ?? '—'} → ${g.unvan}` })),
          )}
          {bolum(
            'atlanacak',
            'Alınmayacak',
            onizleme.atlanacak.map((a) => ({
              ad: a.ad,
              ek: a.neden === 'unvan_yok' ? 'Unvanı okunamadı' : `${a.unvan ?? ''} · göreve eşlenmiyor`,
            })),
          )}
          {hataMetni ? <HataKutusu mesaj={hataMetni} /> : null}
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------ Unvan → görev eşlemesi ------------------------------ */

function EslemePaneli({ acik, kapat }: { acik: boolean; kapat: () => void }) {
  const { goster } = useBildirim();
  const [kurallar, setKurallar] = useState<UnvanKurali[] | null>(null);
  const [hataMetni, setHataMetni] = useState<string | null>(null);
  const [bekliyor, setBekliyor] = useState(false);

  useEffect(() => {
    if (!acik) return;
    setKurallar(null);
    setHataMetni(null);
    unvanEslemeOku()
      .then(setKurallar)
      .catch((h) => setHataMetni(hata(h, 'Eşleme okunamadı.')));
  }, [acik]);

  const degistir = (i: number, yeni: Partial<UnvanKurali>) =>
    setKurallar((k) => (k ? k.map((x, j) => (j === i ? { ...x, ...yeni } : x)) : k));

  const tasi = (i: number, yon: -1 | 1) =>
    setKurallar((k) => {
      if (!k) return k;
      const j = i + yon;
      if (j < 0 || j >= k.length) return k;
      const y = k.slice();
      [y[i], y[j]] = [y[j], y[i]];
      return y;
    });

  const kaydet = async () => {
    if (!kurallar) return;
    const temiz = kurallar.filter((k) => k.desen.trim().length >= 2 && k.gorevler.length);
    setBekliyor(true);
    setHataMetni(null);
    try {
      await unvanEslemeYaz(temiz.map((k) => ({ desen: k.desen.trim(), gorevler: k.gorevler })));
      goster('Unvan eşlemesi kaydedildi.', 'basari');
      kapat();
    } catch (h) {
      setHataMetni(hata(h, 'Kaydedilemedi.'));
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik="Unvan → görev eşlemesi"
      altBaslik="Rehberden gelen kişinin görevi unvanından seçilir. Üstteki kural önce denenir; kümenin ilki girişte açılan ekrandır."
      genislik={560}
      alt={
        <>
          <button
            type="button"
            className="o-dugme metin"
            onClick={() => setKurallar((k) => [...(k ?? []), { desen: '', gorevler: ['teknik'] }])}
            disabled={!kurallar}
          >
            + Kural ekle
          </button>
          <span className="bosluk" />
          <button type="button" className="o-dugme birincil" onClick={() => void kaydet()} disabled={!kurallar || bekliyor}>
            {bekliyor ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </>
      }
    >
      {!kurallar ? (
        hataMetni ? <HataKutusu mesaj={hataMetni} /> : <Iskelet satir={5} yukseklik={64} />
      ) : (
        <div className="esleme-liste">
          {kurallar.map((k, i) => (
            <div key={i} className="esleme-kural">
              <div className="ust">
                <input
                  className="o-girdi"
                  value={k.desen}
                  onChange={(o) => degistir(i, { desen: o.target.value })}
                  placeholder="Unvan içinde geçen (ör. Teknik - Sorumlu)"
                  aria-label="Unvan deseni"
                />
                <button type="button" className="o-daha" onClick={() => tasi(i, -1)} disabled={i === 0} aria-label="Yukarı taşı">
                  ↑
                </button>
                <button type="button" className="o-daha" onClick={() => tasi(i, 1)} disabled={i === kurallar.length - 1} aria-label="Aşağı taşı">
                  ↓
                </button>
                <button
                  type="button"
                  className="o-daha"
                  onClick={() => setKurallar(kurallar.filter((_, j) => j !== i))}
                  aria-label="Kuralı sil"
                >
                  ✕
                </button>
              </div>
              <CipSirasi etiket="Görevler">
                {ROLLER.map((r) => {
                  const secili = k.gorevler.includes(r);
                  return (
                    <Cip
                      key={r}
                      secili={secili}
                      onClick={() => {
                        const yeni = secili ? k.gorevler.filter((x) => x !== r) : [...k.gorevler, r];
                        if (yeni.length) degistir(i, { gorevler: yeni });
                      }}
                    >
                      {GOREV_ETIKET[r]}
                    </Cip>
                  );
                })}
              </CipSirasi>
            </div>
          ))}
          {hataMetni ? <HataKutusu mesaj={hataMetni} /> : null}
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------ Görevleri gözden geçir (§1.11) ------------------------------ */

function GozdenGecirPaneli({
  acik,
  kapat,
  kisiler,
  benId,
  bolgeSayisi,
  bitti,
}: {
  acik: boolean;
  kapat: () => void;
  kisiler: YoneticiKullanici[];
  benId: number | null;
  bolgeSayisi: number;
  bitti: () => void;
}) {
  const { goster } = useBildirim();
  const [secim, setSecim] = useState<Record<number, { gorevler: Rol[]; rol: Rol; bolge: number | null }>>({});
  const [bekliyor, setBekliyor] = useState(false);
  const [hataMetni, setHataMetni] = useState<string | null>(null);

  useEffect(() => {
    if (!acik) return;
    const ilk: typeof secim = {};
    for (const k of kisiler) ilk[k.id] = { gorevler: gorevleri(k), rol: k.rol, bolge: k.bolge };
    setSecim(ilk);
    setHataMetni(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acik]);

  const kaydet = async () => {
    const degisiklikler = kisiler
      .filter((k) => {
        const s = secim[k.id];
        return s && (s.rol !== k.rol || s.gorevler.join() !== gorevleri(k).join() || (s.bolge ?? 0) !== (k.bolge ?? 0));
      })
      .map((k) => ({ id: k.id, rol: secim[k.id].rol, gorevler: secim[k.id].gorevler, bolge: secim[k.id].bolge }));
    const bolgesiz = degisiklikler.find((d) => d.gorevler.includes('satisci') && !d.bolge);
    if (bolgesiz) {
      setHataMetni(`${kisiler.find((k) => k.id === bolgesiz.id)?.ad ?? 'Bir kişi'} için bölge seçin.`);
      return;
    }
    setBekliyor(true);
    setHataMetni(null);
    try {
      const y = await gorevleriKaydet({ degisiklikler, tamam: true });
      bitti();
      kapat();
      goster(y.degisen ? `${y.degisen} kişinin görevi değişti. Bir kez yeniden giriş yapacaklar.` : 'Görevler olduğu gibi kaldı.', 'basari');
    } catch (h) {
      setHataMetni(h instanceof SahaHatasi ? h.message : 'Kaydedilemedi.');
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik="Görevleri gözden geçirin"
      altBaslik="Her kişinin gerçek görevini seçin. Görevi değişen kişi bir kez yeniden giriş yapar; PIN’i aynı kalır."
      genislik={620}
      alt={
        <>
          <button type="button" className="o-dugme" onClick={kapat} disabled={bekliyor}>
            Sonra
          </button>
          <button type="button" className="o-dugme birincil" onClick={() => void kaydet()} disabled={bekliyor}>
            {bekliyor ? 'Kaydediliyor…' : 'Kaydet ve bitir'}
          </button>
        </>
      }
    >
      <div className="gozden-liste">
        {kisiler.map((k) => {
          const s = secim[k.id];
          if (!s) return null;
          const kendisi = k.id === benId;
          return (
            <div key={k.id} className="gozden-kisi">
              <div className="ad">
                <BasHarf ad={k.ad} anahtar={k.id} boyut={28} />
                <span>{k.ad}</span>
                {kendisi ? <span className="ekip-sen">(siz — değiştirilemez)</span> : null}
              </div>
              <CipSirasi etiket={`${k.ad} görevleri`}>
                {ROLLER.map((r) => {
                  const secili = s.gorevler.includes(r);
                  return (
                    <Cip
                      key={r}
                      secili={secili}
                      onClick={
                        kendisi
                          ? undefined
                          : () => {
                              const yeni = secili ? s.gorevler.filter((x) => x !== r) : ROLLER.filter((x) => x === r || s.gorevler.includes(x));
                              if (!yeni.length) return;
                              setSecim({ ...secim, [k.id]: { ...s, gorevler: yeni, rol: yeni.includes(s.rol) ? s.rol : yeni[0] } });
                            }
                      }
                    >
                      {GOREV_ETIKET[r]}
                    </Cip>
                  );
                })}
              </CipSirasi>
              {s.gorevler.includes('satisci') ? (
                <select
                  className="o-girdi"
                  value={s.bolge ?? ''}
                  onChange={(o) => setSecim({ ...secim, [k.id]: { ...s, bolge: o.target.value ? Number(o.target.value) : null } })}
                  aria-label={`${k.ad} bölgesi`}
                >
                  <option value="">Bölge seçin…</option>
                  {bolgeNumaralari(bolgeSayisi).map((b) => (
                    <option key={b} value={b}>
                      {b}. bölge
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          );
        })}
        {hataMetni ? <HataKutusu mesaj={hataMetni} /> : null}
      </div>
    </Panel>
  );
}

/* ------------------------------ Yardım numarası ------------------------------ */

/**
 * Giriş ekranındaki "Yöneticini ara" satırı.
 *
 * Takılan satışçının tek çaresi WhatsApp'a dönmek olmamalı — sistemin yerine
 * geçmeye çalıştığı şey tam da o. Numara burada bir kez girilir, giriş ekranının
 * altında `tel:` bağlantısı olarak görünür.
 */
function YardimKarti() {
  const [ad, setAd] = useState('');
  const [telefon, setTelefon] = useState('');
  const [yukleniyor, setYukleniyor] = useState(true);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const { goster } = useBildirim();

  useEffect(() => {
    let iptal = false;
    void yardimOku()
      .then((veri) => {
        if (iptal) return;
        setAd(veri.yardim_ad ?? '');
        setTelefon(veri.yardim_telefon ?? '');
      })
      .catch(() => undefined)
      .finally(() => {
        if (!iptal) setYukleniyor(false);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const kaydet = async () => {
    setKaydediliyor(true);
    try {
      await yardimYaz({ yardim_ad: ad, yardim_telefon: telefon });
      goster('Yardım numarası kaydedildi', 'basari');
    } catch (h) {
      goster(hata(h, 'Kaydedilemedi'), 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <Kart baslik="Giriş ekranındaki yardım numarası" altYazi="Giriş yapamayan kişi burayı arar. Boş bırakılırsa satır gösterilmez.">
      {yukleniyor ? (
        <Iskelet satir={1} yukseklik={44} />
      ) : (
        <div className="ekip-yardim">
          <label className="o-alan">
            <span className="etiket">Kimi arasın?</span>
            <input value={ad} onChange={(o) => setAd(o.target.value)} placeholder="Örn. Hasan Bey" maxLength={60} />
          </label>
          <label className="o-alan">
            <span className="etiket">Telefon</span>
            <input value={telefon} onChange={(o) => setTelefon(o.target.value)} placeholder="0532 111 22 33" inputMode="tel" />
          </label>
          <button type="button" className="o-dugme" onClick={() => void kaydet()} disabled={kaydediliyor}>
            {kaydediliyor ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      )}
    </Kart>
  );
}
