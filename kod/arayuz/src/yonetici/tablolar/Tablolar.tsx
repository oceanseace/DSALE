/**
 * Tablolar (EK-8, EK-9) — PS26'nın yerine: "Excel'deki gibi, ama herkese açık değil".
 *
 * PS26'daki gibi üstte sayfa sekmeleri (Ticketlar · Güzergah · Altyapı bekleyen · Binalar · İşler),
 * altında tek "Ara…" kutusu (bütün sütunlarda, Türkçe harf duyarsız; sekme değişince aynı arama sürer)
 * ve ortak `Tablo` (EK-9): başlıktan sırala ve süz, dondurulmuş başlık, klavyeyle hücre gezme,
 * seçip Ctrl+C → Excel'e yapıştır, "Excel'e indir". Telefonda satırlar kart olur.
 *
 * Satıra basınca: ticket → ticket çekmecesi (fotoğraflarıyla), bina → bina kartı, altyapı satırı →
 * durum (bekliyor · kuruldu · iptal) ve not, iş → İşler panosunda o iş.
 * Adres: #/yonetici/tablolar/<sekme> (yer imi ve geri tuşu çalışır).
 *
 * Kişisel veri sunucuda görevle süzülür; tablo yalnız kendisine gelen sütunları gösterir.
 */

import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { SahaHatasi } from '../../api/istemci';
import { DURUM_ETIKET, type IslerYanit } from '../../is/tipler';
import { BosDurum, HataKutusu, Iskelet } from '../../ortak/Bos';
import { useBildirim } from '../../ortak/Bildirim';
import { DurumCipi } from '../../ortak/BinaNotlari';
import { gunMetni, sayi, tarihSaat } from '../../ortak/bicim';
import { Hikaye, type HikayeTonu } from '../../ortak/Hikaye';
import { Manset } from '../../ortak/Manset';
import { Panel } from '../../ortak/Panel';
import { Hap } from '../../ortak/Rozet';
import { Segment } from '../../ortak/Segment';
import { Tablo, type TabloSutunu } from '../../ortak/Tablo';
import { useOturum } from '../../depo/oturum';
import { git, useAdres } from '../../yol/rota';
import { TicketCekmecesi } from '../ekran/ticket/TicketAyrinti';
import { BinaAyrintiPenceresi } from '../ortak/BinaAyrinti';
import { Icerik, YonUst } from '../ortak/Kabuk';
import {
  altyapiEkle,
  altyapiGuncelle,
  isListesi,
  ps26Aktar,
  ps26Durumu,
  tabloGetir,
  tablolarOzeti,
  type AltyapiKaydi,
  type HucreDegeri,
  type Ps26Durumu,
  type Ps26Sonucu,
  type SekmeAnahtari,
  type SunucuSutunu,
  type TabloVerisi,
  type TablolarOzeti,
} from './api';
import './tablolar.css';

type Satir = HucreDegeri[];

const SEKME_SIRASI: SekmeAnahtari[] = ['ticketlar', 'guzergah', 'altyapi', 'binalar', 'isler'];
const SEKME_ADI: Record<SekmeAnahtari, string> = {
  ticketlar: 'Ticketlar',
  guzergah: 'Güzergah',
  altyapi: 'Altyapı bekleyen',
  binalar: 'Binalar',
  isler: 'İşler',
};
const KISA_AD: Partial<Record<SekmeAnahtari, string>> = { altyapi: 'Altyapı' };

function hataMetni(h: unknown, yedek: string): string {
  return h instanceof SahaHatasi ? h.message : yedek;
}

/* ------------------------------ Hücre biçimi ------------------------------ */

/** "2026-08-29" → "29.08.2026"; saatliyse "29.08.2026 14:05". Sıralama ham ISO değerle yapılır. */
function tarihGoster(d: HucreDegeri): string {
  if (!d || typeof d !== 'string') return '';
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(d);
  if (!m) return d;
  return `${m[3]}.${m[2]}.${m[1]}${m[4] && d.length > 10 ? ` ${m[4]}:${m[5]}` : ''}`;
}

const ALTYAPI_RENK: Record<string, 'amber' | 'yesil' | 'gri'> = { Bekliyor: 'amber', Kuruldu: 'yesil', İptal: 'gri' };

function durumGoster(sekme: SekmeAnahtari, d: HucreDegeri): ReactNode {
  if (!d) return '';
  if (sekme === 'altyapi') return <Hap renk={ALTYAPI_RENK[String(d)] ?? 'gri'}>{String(d)}</Hap>;
  return <DurumCipi durum={String(d)} kucuk />;
}

/** Sunucunun sütun tanımı → ortak Tablo sütunu (dizi satır, sütun sırası aynı). */
function tabloSutunlari(sekme: SekmeAnahtari, sutunlar: SunucuSutunu[]): Array<TabloSutunu<Satir>> {
  return sutunlar.flatMap((s, i) => {
    if (s.gizli) return [];
    const temel: TabloSutunu<Satir> = {
      anahtar: s.anahtar,
      baslik: s.baslik,
      deger: (r) => r[i],
      genislik: s.genislik,
      kartta: s.kartta,
    };
    if (s.tur === 'sayi') return [{ ...temel, sayi: true, suzgec: s.anahtar === 'bolge' }];
    if (s.tur === 'tarih') return [{ ...temel, goster: (r: Satir) => tarihGoster(r[i]) }];
    if (s.tur === 'durum') return [{ ...temel, goster: (r: Satir) => durumGoster(sekme, r[i]) }];
    return [temel];
  });
}

/* ------------------------------ İşler sekmesi (v2 iş listesinden) ------------------------------ */

function kalanMetni(dk: number, gecikti: boolean): string {
  const m = Math.abs(Math.round(dk));
  const s = Math.floor(m / 60);
  const metin = s ? `${s} s ${m % 60} dk` : `${m} dk`;
  return gecikti ? `Gecikti · ${metin}` : metin;
}

function isTablosu(y: IslerYanit): TabloVerisi {
  const musteri = y.isler.some((i) => 'musteri_no' in i);
  const sutunlar: SunucuSutunu[] = [
    { anahtar: 'is_no', baslik: 'İş no', tur: 'metin', genislik: 120 },
    { anahtar: 'task_adi', baslik: 'Task adı', tur: 'metin', genislik: 220, kartta: 'baslik' },
    { anahtar: 'durum', baslik: 'Durum', tur: 'metin', genislik: 130, kartta: 'alt' },
    { anahtar: 'serit', baslik: 'Şerit', tur: 'metin', genislik: 84 },
    { anahtar: 'kalan', baslik: 'Kalan (24 s)', tur: 'metin', genislik: 140 },
    { anahtar: 'ilce', baslik: 'İlçe', tur: 'metin', genislik: 110 },
    { anahtar: 'mahalle', baslik: 'Mahalle', tur: 'metin', genislik: 150 },
    { anahtar: 'obek', baslik: 'Öbek', tur: 'metin', genislik: 140 },
    { anahtar: 'atanan', baslik: 'Atanan', tur: 'metin', genislik: 150 },
    { anahtar: 'randevu', baslik: 'Randevu', tur: 'tarih', genislik: 140 },
    { anahtar: 'acilis', baslik: 'Açılış', tur: 'tarih', genislik: 140 },
    ...(musteri
      ? ([
          { anahtar: 'musteri_adi', baslik: 'Müşteri', tur: 'metin', genislik: 170, kartta: 'gizli' },
          { anahtar: 'musteri_no', baslik: 'Müşteri no', tur: 'metin', genislik: 120 },
        ] as SunucuSutunu[])
      : []),
    { anahtar: 'ticket', baslik: 'Ticket', tur: 'metin', genislik: 120, kartta: 'gizli' },
  ];
  const satirlar: Satir[] = y.isler.map((i) => [
    i.is_no,
    i.task_adi,
    DURUM_ETIKET[i.durum] ?? i.durum,
    i.serit,
    i.kova === 'biten' ? '' : kalanMetni(i.kalan_dk, i.gecikti),
    i.ilce ?? '',
    i.mahalle ?? '',
    i.obek?.ad ?? '',
    i.atanan?.ad ?? '',
    i.randevu?.bas ?? '',
    i.acilis,
    ...(musteri ? [i.musteri_adi ?? '', i.musteri_no ?? ''] : []),
    i.ticket ? `${i.ticket.konu} · ${i.ticket.durum}` : '',
  ]);
  return { sekme: 'isler', ad: 'İşler', sutunlar, satirlar, kimlik: 'is_no', toplam: satirlar.length, sunucu_zamani: y.sunucu_zamani };
}

/* ------------------------------ Ekran ------------------------------ */

export function Tablolar() {
  const adres = useAdres();
  const { izinli } = useOturum();
  const { goster } = useBildirim();
  const istenen = (adres.split('/').filter(Boolean)[2] ?? '') as SekmeAnahtari;
  const [ozet, setOzet] = useState<TablolarOzeti | null>(null);
  const [ozetHata, setOzetHata] = useState<string | null>(null);
  const [veriler, setVeriler] = useState<Partial<Record<SekmeAnahtari, TabloVerisi>>>({});
  const [hatalar, setHatalar] = useState<Partial<Record<SekmeAnahtari, string>>>({});
  const [arama, setArama] = useState('');
  const [aramaSurumu, setAramaSurumu] = useState(0);
  const [altyapiGorunum, setAltyapiGorunum] = useState<'satirlar' | 'satici'>('satirlar');
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [binaSerial, setBinaSerial] = useState<string | null>(null);
  const [altyapiAcik, setAltyapiAcik] = useState<number | 'yeni' | null>(null);
  const [aktarAcik, setAktarAcik] = useState(false);

  const sekmeler = useMemo(
    () => (ozet?.sekmeler ?? []).filter((s) => SEKME_SIRASI.includes(s.anahtar)),
    [ozet],
  );
  const sekme: SekmeAnahtari = sekmeler.some((s) => s.anahtar === istenen) ? istenen : 'ticketlar';

  const ozetiGetir = useCallback(async () => {
    try {
      setOzet(await tablolarOzeti());
      setOzetHata(null);
    } catch (h) {
      setOzetHata(hataMetni(h, 'Tablolar açılamadı.'));
    }
  }, []);

  const sekmeyiGetir = useCallback(async (s: SekmeAnahtari) => {
    setHatalar((o) => ({ ...o, [s]: undefined }));
    try {
      const v = s === 'isler' ? isTablosu(await isListesi()) : await tabloGetir(s);
      setVeriler((o) => ({ ...o, [s]: v }));
    } catch (h) {
      setHatalar((o) => ({ ...o, [s]: hataMetni(h, 'Tablo alınamadı.') }));
    }
  }, []);

  useEffect(() => {
    void ozetiGetir();
  }, [ozetiGetir]);

  useEffect(() => {
    if (ozet && !veriler[sekme]) void sekmeyiGetir(sekme);
  }, [ozet, sekme, veriler, sekmeyiGetir]);

  const hepsiniYenile = useCallback(() => {
    setVeriler({});
    void ozetiGetir();
  }, [ozetiGetir]);

  const sekmeSec = (s: SekmeAnahtari) => git(`/yonetici/tablolar/${s}`, { degistir: true });

  const veri = veriler[sekme];
  const sutunlar = useMemo(() => (veri ? tabloSutunlari(sekme, veri.sutunlar) : []), [veri, sekme]);
  const kimlikSirasi = veri ? Math.max(0, veri.sutunlar.findIndex((s) => s.anahtar === veri.kimlik)) : 0;

  const satirAc = (r: Satir) => {
    const k = r[kimlikSirasi];
    if (sekme === 'ticketlar' || sekme === 'guzergah') setTicketId(Number(k));
    else if (sekme === 'binalar') setBinaSerial(String(k));
    else if (sekme === 'altyapi') setAltyapiAcik(Number(k));
    else if (sekme === 'isler') git(`/yonetici/isler/is/${encodeURIComponent(String(k))}`);
  };

  /* Hikâye cümlesi (EK-6): önce en önemli şey. */
  const hikaye = useMemo((): { cumle: string; ton: HikayeTonu; eylem?: { etiket: string; calistir: () => void } } | null => {
    if (!ozet) return null;
    const o = ozet.ozet;
    const say = (a: SekmeAnahtari) => sekmeler.find((s) => s.anahtar === a)?.satir ?? 0;
    if (!o.ps26_son_aktarim && !say('ticketlar') && !say('altyapi')) {
      return {
        cumle: 'PS26 henüz aktarılmadı. data.xlsx’i bir kez aktarın; tablolar burada, girişle ve güvenle açılır.',
        ton: 'dikkat',
        eylem: izinli('ticket.defter') ? { etiket: 'PS26’dan aktar', calistir: () => setAktarAcik(true) } : undefined,
      };
    }
    const ticketParca = `Takipte ${sayi(o.ticket_takipte ?? 0)} ticket ve ${sayi(o.guzergah_acik ?? 0)} açık güzergah var.`;
    if (!o.altyapi_bekliyor) {
      return { cumle: `Altyapı bekleyen satış kalmadı. ${ticketParca}`, ton: 'iyi' };
    }
    const eski = o.altyapi_en_eski_gun;
    return {
      cumle: `${sayi(o.altyapi_bekliyor)} satış altyapı yüzünden kurulamadı${eski ? `; en eskisi ${sayi(eski)} gündür bekliyor` : ''}. ${ticketParca}`,
      ton: (eski ?? 0) >= 30 ? 'dikkat' : 'sakin',
      eylem: sekme !== 'altyapi' ? { etiket: 'Onları göster', calistir: () => sekmeSec('altyapi') } : undefined,
    };
  }, [ozet, sekmeler, sekme, izinli]);

  const aktarildiMi = Boolean(ozet?.ozet.ps26_son_aktarim);
  const altyapiPivot = sekme === 'altyapi' && altyapiGorunum === 'satici' && veri?.pivot;
  const pivotVerisi = useMemo(
    () => (veri?.pivot ? { sutunlar: tabloSutunlari('altyapi', veri.pivot.sutunlar), satirlar: veri.pivot.satirlar } : null),
    [veri],
  );

  const aracCubugu =
    sekme === 'altyapi' ? (
      <>
        <Segment<'satirlar' | 'satici'>
          etiket="Altyapı görünümü"
          kucuk
          deger={altyapiGorunum}
          degisti={setAltyapiGorunum}
          secenekler={[
            { deger: 'satirlar', etiket: 'Satırlar' },
            { deger: 'satici', etiket: 'Satıcıya göre' },
          ]}
        />
        {izinli('ticket.defter') ? (
          <button type="button" className="o-dugme kucuk" onClick={() => setAltyapiAcik('yeni')}>
            + Yeni satır
          </button>
        ) : null}
      </>
    ) : null;

  return (
    <>
      <YonUst baslik="Tablolar">
        <button type="button" className="yd" onClick={hepsiniYenile}>
          Yenile
        </button>
        {izinli('ticket.defter') ? (
          <button type="button" className={`yd${aktarildiMi ? '' : ' birincil'}`} onClick={() => setAktarAcik(true)}>
            PS26’dan aktar
          </button>
        ) : null}
      </YonUst>

      <Icerik>
        {ozetHata ? <HataKutusu mesaj={ozetHata} tekrar={() => void ozetiGetir()} /> : null}
        {hikaye ? (
          <Hikaye
            cumle={hikaye.cumle}
            ton={hikaye.ton}
            eylem={hikaye.eylem}
            ayrinti={
              ozet?.ozet.ps26_son_aktarim ? (
                <span className="tb-ayrinti">
                  PS26’dan son aktarım: {tarihSaat(ozet.ozet.ps26_son_aktarim)} · {sayi(ozet.ozet.foto ?? 0)} ticket fotoğrafı.
                  Uygulamada değiştirdiğiniz kayda Excel bir daha dokunmaz.
                </span>
              ) : undefined
            }
          />
        ) : null}

        {!ozet ? (
          !ozetHata ? <Iskelet satir={6} yukseklik={36} /> : null
        ) : (
          <>
            <div className="tb-sekmeler">
              <Segment<SekmeAnahtari>
                etiket="Tablo sayfaları"
                deger={sekme}
                degisti={sekmeSec}
                secenekler={sekmeler.map((s) => ({
                  deger: s.anahtar,
                  etiket: (
                    <>
                      <span className="tb-uzun">{SEKME_ADI[s.anahtar] ?? s.ad}</span>
                      <span className="tb-kisa">{KISA_AD[s.anahtar] ?? SEKME_ADI[s.anahtar] ?? s.ad}</span>
                    </>
                  ),
                  sayi: s.satir ?? undefined,
                }))}
              />
            </div>

            {hatalar[sekme] ? (
              <HataKutusu mesaj={hatalar[sekme]} tekrar={() => void sekmeyiGetir(sekme)} />
            ) : !veri ? (
              <Iskelet satir={8} yukseklik={36} />
            ) : !veri.toplam && sekme !== 'isler' ? (
              <BosSekme sekme={sekme} aktar={izinli('ticket.defter') ? () => setAktarAcik(true) : undefined} yeni={() => setAltyapiAcik('yeni')} />
            ) : (
              /* Tek "Ara…" kutusu: yazılan arama sekme değişince de sürer (Tablo yeniden kurulur, aynı metinle). */
              <div
                className="tb-tablo"
                onInput={(o) => {
                  const h = o.target as HTMLInputElement;
                  if (h.getAttribute('aria-label') === 'Tabloda ara') setArama(h.value);
                }}
              >
                {altyapiPivot && pivotVerisi ? (
                  <Tablo<Satir>
                    key={`pivot-${aramaSurumu}`}
                    satirlar={pivotVerisi.satirlar}
                    sutunlar={pivotVerisi.sutunlar}
                    anahtar={(r) => String(r[0])}
                    onAc={(r) => {
                      setArama(String(r[0] ?? ''));
                      setAramaSurumu((n) => n + 1);
                      setAltyapiGorunum('satirlar');
                    }}
                    aramaYerTutucu="Ara…"
                    excelAdi="Altyapı - satıcıya göre"
                    kayitAnahtari="tablolar.altyapi.satici"
                    aramaBaslangic={arama}
                    arac={aracCubugu}
                  />
                ) : (
                  <Tablo<Satir>
                    key={`${sekme}-${aramaSurumu}`}
                    satirlar={veri.satirlar}
                    sutunlar={sutunlar}
                    anahtar={(r) => String(r[kimlikSirasi])}
                    onAc={satirAc}
                    seciliAnahtar={
                      ticketId !== null && (sekme === 'ticketlar' || sekme === 'guzergah')
                        ? String(ticketId)
                        : sekme === 'binalar'
                          ? binaSerial
                          : typeof altyapiAcik === 'number' && sekme === 'altyapi'
                            ? String(altyapiAcik)
                            : null
                    }
                    aramaYerTutucu="Ara… (bütün sütunlarda)"
                    excelAdi={SEKME_ADI[sekme]}
                    kayitAnahtari={`tablolar.${sekme}`}
                    aramaBaslangic={arama}
                    bosMetin={sekme === 'isler' && !veri.toplam ? 'Açık iş yok.' : 'Bu aramayla eşleşen satır yok.'}
                    arac={aracCubugu}
                  />
                )}
              </div>
            )}
          </>
        )}
      </Icerik>

      {ticketId !== null ? (
        <TicketCekmecesi
          id={ticketId}
          kapat={() => setTicketId(null)}
          degisti={() => {
            /* Durum değişti: bu sekme ve sayılar sonra tazelensin. */
            setVeriler((o) => ({ ...o, ticketlar: undefined, guzergah: undefined }));
            void ozetiGetir();
          }}
        />
      ) : null}
      {binaSerial ? <BinaAyrintiPenceresi serial={binaSerial} kapat={() => setBinaSerial(null)} /> : null}
      <AltyapiPaneli
        acik={altyapiAcik}
        kapat={() => setAltyapiAcik(null)}
        veri={veriler.altyapi ?? null}
        kaydedildi={(mesaj) => {
          goster(mesaj, 'basari');
          setVeriler((o) => ({ ...o, altyapi: undefined }));
          void ozetiGetir();
        }}
      />
      <Ps26Paneli
        acik={aktarAcik}
        kapat={() => setAktarAcik(false)}
        bitti={(s) => {
          hepsiniYenile();
          const e = (b: keyof Pick<Ps26Sonucu, 'ticket' | 'guzergah' | 'altyapi' | 'foto'>) => s[b].eklenen ?? 0;
          goster(
            `${sayi(e('ticket'))} ticket, ${sayi(e('guzergah'))} güzergah, ${sayi(e('altyapi'))} altyapı satırı ve ${sayi(e('foto'))} fotoğraf aktarıldı.`,
            'basari',
          );
        }}
      />
    </>
  );
}

function BosSekme({ sekme, aktar, yeni }: { sekme: SekmeAnahtari; aktar?: () => void; yeni: () => void }) {
  if (sekme === 'altyapi') {
    return (
      <BosDurum
        simge="🏗️"
        baslik="Altyapı bekleyen satış yok"
        aciklama="Altyapı yüzünden kurulamayan bir satış olunca buraya ekleyin ya da PS26’daki ALTYAPI sayfasını aktarın."
      >
        <button type="button" className="o-dugme birincil" onClick={yeni}>
          + Yeni satır
        </button>
      </BosDurum>
    );
  }
  return (
    <BosDurum
      simge="📄"
      baslik={`${SEKME_ADI[sekme]} boş`}
      aciklama="PS26’daki data.xlsx aktarılınca bu sayfa dolar. İki kez aktarmak çift kayıt üretmez."
    >
      {aktar ? (
        <button type="button" className="o-dugme birincil" onClick={aktar}>
          PS26’dan aktar
        </button>
      ) : null}
    </BosDurum>
  );
}

/* ------------------------------ Altyapı bekleyen: durum / yeni satır ------------------------------ */

const DURUMLAR: Array<{ deger: AltyapiKaydi['durum_kod']; etiket: string }> = [
  { deger: 'bekliyor', etiket: 'Bekliyor' },
  { deger: 'kuruldu', etiket: 'Kuruldu' },
  { deger: 'iptal', etiket: 'İptal' },
];
const DURUM_KODU: Record<string, AltyapiKaydi['durum_kod']> = { Bekliyor: 'bekliyor', Kuruldu: 'kuruldu', İptal: 'iptal' };
const KANALLAR = ['GLOBAL', 'DEHA', 'TOPTAN'];

function AltyapiPaneli({
  acik,
  kapat,
  veri,
  kaydedildi,
}: {
  acik: number | 'yeni' | null;
  kapat: () => void;
  veri: TabloVerisi | null;
  kaydedildi: (mesaj: string) => void;
}) {
  const [durum, setDurum] = useState<AltyapiKaydi['durum_kod']>('bekliyor');
  const [notu, setNotu] = useState('');
  const [bina, setBina] = useState('');
  const [yeni, setYeni] = useState({ musteri_no: '', kanal: '', satici_ad: '', bolge: '', baslangic: '' });
  const [bekliyor, setBekliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  const satir = useMemo(() => {
    if (typeof acik !== 'number' || !veri) return null;
    const ad = veri.sutunlar.map((s) => s.anahtar);
    const r = veri.satirlar.find((x) => Number(x[0]) === acik);
    return r ? (Object.fromEntries(ad.map((a, i) => [a, r[i]])) as Record<string, HucreDegeri>) : null;
  }, [acik, veri]);

  useEffect(() => {
    setHata(null);
    if (satir) {
      setDurum(DURUM_KODU[String(satir.durum)] ?? 'bekliyor');
      setNotu(String(satir.notu ?? ''));
      setBina(String(satir.bina_serial ?? ''));
    } else if (acik === 'yeni') {
      setYeni({ musteri_no: '', kanal: '', satici_ad: '', bolge: '', baslangic: gunMetni() });
      setNotu('');
      setBina('');
    }
  }, [satir, acik]);

  const degisti =
    satir !== null &&
    (durum !== (DURUM_KODU[String(satir.durum)] ?? 'bekliyor') ||
      notu.trim() !== String(satir.notu ?? '') ||
      bina.trim() !== String(satir.bina_serial ?? ''));
  const yeniHazir = acik === 'yeni' && Boolean(yeni.musteri_no.trim() || yeni.satici_ad.trim() || bina.trim());

  const kaydet = async (o?: FormEvent) => {
    o?.preventDefault();
    setBekliyor(true);
    setHata(null);
    try {
      if (acik === 'yeni') {
        await altyapiEkle({ ...yeni, bina_serial: bina.trim() || undefined, notu: notu.trim() || undefined });
        kaydedildi('Kayıt eklendi.');
      } else if (typeof acik === 'number') {
        await altyapiGuncelle(acik, { durum, notu: notu.trim() || null, bina_serial: bina.trim() || null });
        kaydedildi(durum === 'kuruldu' ? 'Kuruldu olarak işaretlendi.' : 'Kaydedildi.');
      }
      kapat();
    } catch (h) {
      setHata(hataMetni(h, 'Kaydedilemedi.'));
    } finally {
      setBekliyor(false);
    }
  };

  const baslik = acik === 'yeni' ? 'Altyapı bekleyen satış ekle' : 'Altyapı bekleyen satış';
  const alt =
    satir && acik !== 'yeni'
      ? [satir.satici_ad, tarihGoster(satir.baslangic), satir.bekleme_gun != null ? `${sayi(Number(satir.bekleme_gun))} gündür` : null]
          .filter(Boolean)
          .join(' · ')
      : 'Altyapı yüzünden kurulamayan satışı kaydedin; kurulunca "Kuruldu" deyin.';

  return (
    <Panel
      acik={acik !== null && (acik === 'yeni' || satir !== null)}
      kapat={kapat}
      kilitli={bekliyor}
      baslik={baslik}
      altBaslik={alt}
      alt={
        <>
          <button type="button" className="o-dugme" onClick={kapat} disabled={bekliyor}>
            Vazgeç
          </button>
          <span className="bosluk" />
          <button
            type="button"
            className="o-dugme birincil"
            onClick={() => void kaydet()}
            disabled={bekliyor || (acik === 'yeni' ? !yeniHazir : !degisti)}
          >
            {bekliyor ? 'Kaydediliyor…' : acik === 'yeni' ? 'Ekle' : 'Kaydet'}
          </button>
        </>
      }
    >
      <form className="tb-form" onSubmit={kaydet}>
        {acik === 'yeni' ? (
          <>
            <label>
              <span className="yon-etiket">Müşteri no</span>
              <input className="yon-alan" inputMode="numeric" value={yeni.musteri_no}
                onChange={(o) => setYeni({ ...yeni, musteri_no: o.target.value })} />
            </label>
            <label>
              <span className="yon-etiket">Satıcı</span>
              <input className="yon-alan" value={yeni.satici_ad} onChange={(o) => setYeni({ ...yeni, satici_ad: o.target.value })} />
            </label>
            <div className="tb-ikili">
              <label>
                <span className="yon-etiket">Kanal</span>
                <input className="yon-alan" list="tb-kanallar" value={yeni.kanal}
                  onChange={(o) => setYeni({ ...yeni, kanal: o.target.value.toLocaleUpperCase('tr-TR') })} />
                <datalist id="tb-kanallar">
                  {KANALLAR.map((k) => (
                    <option key={k} value={k} />
                  ))}
                </datalist>
              </label>
              <label>
                <span className="yon-etiket">Başlangıç</span>
                <input className="yon-alan" type="date" value={yeni.baslangic}
                  onChange={(o) => setYeni({ ...yeni, baslangic: o.target.value })} />
              </label>
            </div>
            <label>
              <span className="yon-etiket">Bölge (mahalle)</span>
              <input className="yon-alan" value={yeni.bolge} onChange={(o) => setYeni({ ...yeni, bolge: o.target.value })} />
            </label>
          </>
        ) : satir ? (
          <>
            <div>
              <span className="yon-etiket">Durum</span>
              <Segment<AltyapiKaydi['durum_kod']> etiket="Durum" tam deger={durum} degisti={setDurum} secenekler={DURUMLAR} />
            </div>
            <dl className="tb-bilgi">
              {'musteri_no' in satir ? (
                <>
                  <dt>Müşteri</dt>
                  <dd>{String(satir.musteri_no || '—')}</dd>
                </>
              ) : null}
              <dt>Kanal</dt>
              <dd>{String(satir.kanal || '—')}</dd>
              <dt>Bölge</dt>
              <dd>{String(satir.bolge || '—')}</dd>
              <dt>Kaynak</dt>
              <dd>{satir.kaynak === 'Excel' ? 'PS26’dan aktarıldı' : 'Uygulamada eklendi'}</dd>
            </dl>
          </>
        ) : null}
        <label>
          <span className="yon-etiket">Bina Serial (isteğe bağlı)</span>
          <input className="yon-alan" value={bina} placeholder="BN-…" onChange={(o) => setBina(o.target.value.trim())} />
        </label>
        <label>
          <span className="yon-etiket">Not</span>
          <textarea className="yon-alan" value={notu} maxLength={1000} onChange={(o) => setNotu(o.target.value)} />
        </label>
        {hata ? <HataKutusu mesaj={hata} /> : null}
      </form>
    </Panel>
  );
}

/* ------------------------------ PS26'dan aktar ------------------------------ */

function Ps26Paneli({ acik, kapat, bitti }: { acik: boolean; kapat: () => void; bitti: (s: Ps26Sonucu) => void }) {
  const [durum, setDurum] = useState<Ps26Durumu | null>(null);
  const [dosyalar, setDosyalar] = useState<{ xlsx: File; zipler: File[] } | null>(null);
  const [onizleme, setOnizleme] = useState<Ps26Sonucu | null>(null);
  const [bekliyor, setBekliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  useEffect(() => {
    if (!acik) {
      setDosyalar(null);
      setOnizleme(null);
      setHata(null);
      return;
    }
    let iptal = false;
    ps26Durumu()
      .then((d) => !iptal && setDurum(d))
      .catch((h) => !iptal && setHata(hataMetni(h, 'PS26 durumu alınamadı.')));
    return () => {
      iptal = true;
    };
  }, [acik]);

  const kaynak: 'klasor' | { xlsx: File; zipler: File[] } | null = dosyalar ?? (durum?.klasor.bulundu ? 'klasor' : null);

  const onizle = async (k = kaynak) => {
    if (!k) return;
    setBekliyor(true);
    setHata(null);
    setOnizleme(null);
    try {
      setOnizleme(await ps26Aktar(k, true));
    } catch (h) {
      setHata(hataMetni(h, 'Dosya okunamadı.'));
    } finally {
      setBekliyor(false);
    }
  };

  const uygula = async () => {
    if (!kaynak) return;
    setBekliyor(true);
    setHata(null);
    try {
      const s = await ps26Aktar(kaynak, false);
      bitti(s);
      kapat();
    } catch (h) {
      setHata(hataMetni(h, 'Aktarılamadı.'));
    } finally {
      setBekliyor(false);
    }
  };

  const dosyaSec = (liste: FileList | null) => {
    const hepsi = Array.from(liste ?? []);
    const xlsx = hepsi.find((f) => /\.xlsx?$|\.xlsm$/i.test(f.name));
    if (!xlsx) {
      setHata('data.xlsx seçilmedi. Fotoğraf arşivlerini (zip) data.xlsx ile birlikte seçin.');
      return;
    }
    const d = { xlsx, zipler: hepsi.filter((f) => /\.zip$/i.test(f.name)) };
    setDosyalar(d);
    void onizle(d);
  };

  const yapilacak = onizleme?.eklenecek_toplam ?? 0;
  const k = durum?.klasor;
  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik="PS26’dan aktar"
      altBaslik="Önce ne olacağını görürsünüz; hiçbir şey değişmez. İki kez aktarmak çift kayıt üretmez."
      alt={
        <>
          <label className="o-dugme">
            {dosyalar ? 'Başka dosya' : 'Dosya seç'}
            <input type="file" accept=".xlsx,.xlsm,.zip" multiple hidden onChange={(o) => dosyaSec(o.target.files)} />
          </label>
          <span className="bosluk" />
          {!onizleme ? (
            <button type="button" className="o-dugme birincil" disabled={!kaynak || bekliyor} onClick={() => void onizle()}>
              {bekliyor ? 'Okunuyor…' : 'Önizle'}
            </button>
          ) : (
            <button type="button" className="o-dugme birincil" disabled={bekliyor || !yapilacak} onClick={() => void uygula()}>
              {bekliyor ? 'Aktarılıyor…' : 'Aktar'}
            </button>
          )}
        </>
      }
    >
      {!durum && !hata ? <Iskelet satir={2} yukseklik={48} /> : null}
      {durum ? (
        dosyalar ? (
          <p className="tb-kaynak">
            <b>{dosyalar.xlsx.name}</b>
            {dosyalar.zipler.length ? ` + ${sayi(dosyalar.zipler.length)} fotoğraf arşivi` : ' · fotoğraf arşivi seçilmedi'}
          </p>
        ) : k?.bulundu ? (
          <p className="tb-kaynak">
            PS26 klasörü bu bilgisayarda bulundu: <b>{k.yer}</b> · data.xlsx {tarihGoster(k.dosya.degisme)}
            {k.zip != null ? ` · ${sayi(k.zip)} fotoğraf arşivi` : ''}
          </p>
        ) : (
          <BosDurum
            kucuk
            simge="📄"
            baslik="data.xlsx’i seçin"
            aciklama="PS26 klasöründeki data.xlsx. Fotoğraflar için imgs klasöründeki .zip dosyalarını da birlikte seçebilirsiniz."
          />
        )
      ) : null}
      {onizleme ? <OnizlemeOzeti s={onizleme} /> : null}
      {hata ? <HataKutusu mesaj={hata} /> : null}
    </Panel>
  );
}

function OnizlemeOzeti({ s }: { s: Ps26Sonucu }) {
  const e = (b: keyof Pick<Ps26Sonucu, 'ticket' | 'guzergah' | 'altyapi' | 'foto'>) => (s[b].eklenecek ?? 0) + (s[b].guncellenen ?? 0);
  if (!s.eklenecek_toplam) {
    return (
      <div className="tb-esit" role="status">
        <b>PS26 ile Saha Sistemi eşit.</b>
        <span>Aktarılacak yeni bir şey yok. PS26’yı kapatabilirsiniz; tablolar burada.</span>
      </div>
    );
  }
  return (
    <div className="tb-onizleme">
      <Manset
        etiket="Aktarılacaklar"
        ogeler={[
          { etiket: 'Ticket', deger: sayi(e('ticket')), ek: `${sayi(s.ticket.okunan ?? 0)} satır` },
          { etiket: 'Güzergah', deger: sayi(e('guzergah')), ek: `${sayi(s.guzergah.okunan ?? 0)} dolu satır` },
          { etiket: 'Altyapı bekleyen', deger: sayi(e('altyapi')), ek: `${sayi(s.altyapi.okunan ?? 0)} satır` },
          { etiket: 'Fotoğraf', deger: s.foto.klasor ? sayi(e('foto')) : '—', ek: s.foto.klasor ? `${sayi(s.foto.eslesen_zip ?? 0)} arşiv` : 'arşiv yok' },
        ]}
      />
      <ul className="tb-notlar">
        {(s.ticket.uygulamada_degismis ?? 0) > 0 ? (
          <li>{sayi(s.ticket.uygulamada_degismis)} ticket uygulamada değiştirildiği için Excel’den güncellenmeyecek.</li>
        ) : null}
        {(s.ticket.binasiz ?? 0) + (s.guzergah.binasiz ?? 0) > 0 ? (
          <li>{sayi((s.ticket.binasiz ?? 0) + (s.guzergah.binasiz ?? 0))} satırın lokasyonu bir binayla eşleşmedi; yine aktarılır.</li>
        ) : null}
        {(s.altyapi.excelde_yok ?? 0) > 0 ? (
          <li>{sayi(s.altyapi.excelde_yok)} altyapı satırı Excel’den silinmiş; burada “Bekliyor” duruyor. Kurulduysa işaretleyin.</li>
        ) : null}
        {(s.foto.eslesmeyen_zip ?? 0) > 0 ? (
          <li>{sayi(s.foto.eslesmeyen_zip)} fotoğraf arşivi hiçbir ticket satırıyla eşleşmedi; aktarılmayacak.</li>
        ) : null}
        {(s.foto.alinmayan ?? 0) > 0 ? <li>{sayi(s.foto.alinmayan)} dosya fotoğraf olmadığı için alınmayacak.</li> : null}
      </ul>
    </div>
  );
}
