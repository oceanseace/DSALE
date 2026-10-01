/**
 * Ticketlar — OneDesk ticket defteri (Excel'deki TICKET sayfasının yerine).
 *
 * En üstte tek hikâye cümlesi (EK-6): kaç ticket takipte, hangileri önce.
 * Altında sakin manşet (her sayı tıklanınca süzer), durum çipleri, tarih
 * süzgeci ve Excel alışkanlığıyla bir tablo (EK-9): sütun başlığından sırala
 * ve süz, "Ara…", Ctrl+C ile Excel'e kopyala, "Excel'e indir". Satıra basınca
 * sağdan ayrıntı açılır: durum güncelle (notuyla), OneDesk numarası, ekip ve
 * başlık (EK-5), fotoğraflar (EK-8), geçmiş.
 *
 * Defter birkaç yüz satır olduğu için bir kez indirilir; süzgeçler ekranda
 * anında çalışır. Excel'den aktarılan kayıtlar da burada (kaynak: Excel).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Ticket, TicketDurumu } from '../../api/tipler';
import { useBildirim } from '../../ortak/Bildirim';
import { DurumCipi } from '../../ortak/BinaNotlari';
import { gunMetni, sayi } from '../../ortak/bicim';
import { TICKET_DURUMLARI, TICKET_KONULARI, tarihKisa } from '../../ortak/ticketBilgi';
import { git } from '../../yol/rota';
import { tumTicketlar, ticketExcelAktar, ticketKategorileri, type TicketAktarimSonucu } from '../api';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { HataKutusu, useVeri } from '../ortak/parcalar';
import { Tablo, type TabloSutunu } from '../../ortak/Tablo';
import { Hikaye, type HikayeTonu } from '../../ortak/Hikaye';
import { Manset } from '../../ortak/Manset';
import { Cip, CipSirasi } from '../../ortak/Suz';
import { BosDurum, Iskelet } from '../../ortak/Bos';
import { Panel } from '../../ortak/Panel';
import { Hap } from '../../ortak/Rozet';
import { TicketCekmecesi } from './ticket/TicketAyrinti';
import { BILINEN_KANALLAR, YeniTicketPenceresi } from './ticket/YeniTicket';
import './faz2.css';

type DurumSuzgeci = 'hepsi' | 'takipte' | 'numarasiz' | 'gec24' | TicketDurumu;
type TarihSuzgeci = 'hepsi' | 'bugun' | '7' | '30' | 'ay';

const TARIHLER: Array<{ deger: TarihSuzgeci; etiket: string }> = [
  { deger: 'hepsi', etiket: 'Bütün tarihler' },
  { deger: 'bugun', etiket: 'Bugün' },
  { deger: '7', etiket: 'Son 7 gün' },
  { deger: '30', etiket: 'Son 30 gün' },
  { deger: 'ay', etiket: 'Bu ay' },
];

function gunOnce(gun: number): string {
  const t = new Date();
  t.setDate(t.getDate() - gun);
  return gunMetni(t);
}

function tarihAraligi(s: TarihSuzgeci): [string | null, string | null] {
  const bugun = gunMetni();
  switch (s) {
    case 'bugun':
      return [bugun, bugun];
    case '7':
      return [gunOnce(6), bugun];
    case '30':
      return [gunOnce(29), bugun];
    case 'ay':
      return [`${bugun.slice(0, 8)}01`, bugun];
    default:
      return [null, null];
  }
}

/**
 * BÇO'da hatırlatma süresini (ayar `ticket_bco_hatirlatma_saat`, varsayılan 24)
 * geçen açık ticket (EK-12.7): TL'ye "OneDesk ID + müşteri no" maili
 * hatırlatılır. Açılış saati bilinmediği için gün sayısından hesaplanır.
 */
export const VARSAYILAN_HATIRLATMA_SAAT = 24;
export function gecikti(t: Ticket, saat = VARSAYILAN_HATIRLATMA_SAAT): boolean {
  return t.acik && (t.acik_gun ?? 0) * 24 >= Math.max(1, saat);
}

/* Sütunlar: ham değer (sıralama/süzgeç/kopya/Excel) + ekrandaki görünüş. */
const SUTUNLAR: Array<TabloSutunu<Ticket>> = [
  { anahtar: 'acilis', baslik: 'Açılış', deger: (t) => t.acilis ?? '', goster: (t) => tarihKisa(t.acilis), genislik: 104, kartta: 'gizli' },
  {
    anahtar: 'no',
    baslik: 'OneDesk no',
    deger: (t) => t.ticket_no || '',
    goster: (t) => (t.ticket_no ? t.ticket_no : <Hap renk="amber">numara yok</Hap>),
    genislik: 132,
  },
  {
    anahtar: 'bina',
    baslik: 'Bina',
    deger: (t) => t.bina?.ad || t.site || '',
    genislik: 220,
    kartta: 'baslik',
  },
  {
    anahtar: 'durum',
    baslik: 'Durum',
    deger: (t) => TICKET_DURUMLARI.find((d) => d.durum === t.durum)?.etiket ?? t.durum,
    goster: (t) => <DurumCipi durum={t.durum} kucuk />,
    genislik: 112,
    kartta: 'alt',
  },
  { anahtar: 'konu', baslik: 'Konu', deger: (t) => TICKET_KONULARI.find((k) => k.konu === t.konu)?.kisa ?? t.konu, genislik: 112 },
  { anahtar: 'kategori', baslik: 'Başlık', deger: (t) => t.kategori || '', genislik: 220 },
  { anahtar: 'ekip', baslik: 'OneDesk ekibi', deger: (t) => t.onedesk_ekip || '', genislik: 130 },
  {
    anahtar: 'gun',
    baslik: 'Açık gün',
    deger: (t) => (t.acik ? t.acik_gun ?? 0 : null),
    goster: (t) =>
      t.acik ? (
        <span className={gecikti(t) ? 'tk-gun-gec' : undefined}>{(t.acik_gun ?? 0).toLocaleString('tr-TR')}</span>
      ) : (
        ''
      ),
    sayi: true,
    genislik: 88,
  },
  { anahtar: 'loc', baslik: 'Location Id', deger: (t) => t.location_id || '', genislik: 120 },
  { anahtar: 'serial', baslik: 'Bina Serial', deger: (t) => t.bina_serial || '', genislik: 150 },
  { anahtar: 'bolge', baslik: 'Bölge', deger: (t) => t.bina?.bolge ?? null, sayi: true, suzgec: true, genislik: 76 },
  { anahtar: 'kanal', baslik: 'Kanal', deger: (t) => t.kanal || '', genislik: 100 },
  { anahtar: 'musteri', baslik: 'Müşteri', deger: (t) => t.musteri || '', genislik: 150 },
  { anahtar: 'foto', baslik: 'Foto', deger: (t) => t.ek_sayisi ?? null, sayi: true, genislik: 64, kartta: 'gizli' },
  { anahtar: 'detay', baslik: 'Detay', deger: (t) => (t.detay || '').replace(/\s+/g, ' '), genislik: 260, kartta: 'gizli' },
];

export function Ticketlar({ deger }: { deger?: string | null }) {
  const [surum, setSurum] = useState(0);
  const defter = useVeri(tumTicketlar, [surum]);
  /* Hatırlatma süresi ayardan (EK-12: süreç kuralları koda gömülmez). */
  const [hatirlatmaSaat, setHatirlatmaSaat] = useState(VARSAYILAN_HATIRLATMA_SAAT);
  useEffect(() => {
    let iptal = false;
    ticketKategorileri()
      .then((k) => {
        if (!iptal && k.bco_hatirlatma_saat) setHatirlatmaSaat(k.bco_hatirlatma_saat);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);
  const gec = useCallback((t: Ticket) => gecikti(t, hatirlatmaSaat), [hatirlatmaSaat]);
  const gecEtiketi = `${hatirlatmaSaat.toLocaleString('tr-TR')} saati geçen`;
  const [liste, setListe] = useState<Ticket[]>([]);

  const [durumS, setDurumS] = useState<DurumSuzgeci>('hepsi');
  const [tarih, setTarih] = useState<TarihSuzgeci>('hepsi');
  const [yeniAcik, setYeniAcik] = useState(false);
  const [aktarAcik, setAktarAcik] = useState(false);

  /* Adres: #/yonetici/ticketlar/<id> → o ticket açık; /<Bina Serial> → o binanın ticket'ları. */
  const seciliId = deger && /^\d+$/.test(deger) ? Number(deger) : null;
  const binaSerial = deger && !/^\d+$/.test(deger) ? deger : null;

  useEffect(() => {
    if (defter.veri) setListe(defter.veri.ticketlar);
  }, [defter.veri]);

  const ticketAc = useCallback((id: number | null) => {
    git(id ? `/yonetici/ticketlar/${id}` : '/yonetici/ticketlar');
  }, []);

  const guncellendi = useCallback((t: Ticket) => {
    setListe((eski) => eski.map((x) => (x.id === t.id ? t : x)));
  }, []);

  const kanallar = useMemo(() => {
    const k = new Set(BILINEN_KANALLAR);
    liste.forEach((t) => t.kanal && k.add(t.kanal));
    return [...k].sort((a, b) => a.localeCompare(b, 'tr'));
  }, [liste]);

  /* Durum dışındaki süzgeçler — çiplerdeki sayılar buna göre. */
  const [tarihBasi, tarihSonu] = tarihAraligi(tarih);
  const onSuzulen = useMemo(
    () =>
      liste.filter((t) => {
        if (binaSerial && t.bina_serial !== binaSerial) return false;
        const gun = (t.acilis || t.olusturma || '').slice(0, 10);
        if (tarihBasi && (!gun || gun < tarihBasi)) return false;
        if (tarihSonu && (!gun || gun > tarihSonu)) return false;
        return true;
      }),
    [liste, binaSerial, tarihBasi, tarihSonu],
  );

  const suzulen = useMemo(
    () =>
      onSuzulen.filter((t) => {
        switch (durumS) {
          case 'hepsi':
            return true;
          case 'takipte':
            return t.acik;
          case 'numarasiz':
            return t.acik && !t.ticket_no;
          case 'gec24':
            return gec(t);
          default:
            return t.durum === durumS;
        }
      }),
    [onSuzulen, durumS, gec],
  );

  const sayilar = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of onSuzulen) m.set(t.durum, (m.get(t.durum) ?? 0) + 1);
    return m;
  }, [onSuzulen]);

  /* Hikâye ve manşet: süzgeçten bağımsız, bütün defter. */
  const ozet = useMemo(() => {
    const acik = liste.filter((t) => t.acik);
    const hata = acik.filter((t) => t.durum === 'HATA').length;
    const numarasiz = acik.filter((t) => !t.ticket_no).length;
    const gecen = acik.filter(gec).length;
    const enEski = acik.reduce((m, t) => Math.max(m, t.acik_gun ?? 0), 0);
    return { acik: acik.length, hata, numarasiz, gec: gecen, enEski };
  }, [liste, gec]);

  const hikaye = useMemo((): { cumle: string; ton: HikayeTonu; eylem?: { etiket: string; calistir: () => void } } => {
    if (!liste.length) return { cumle: 'Defter boş.', ton: 'sakin' };
    if (!ozet.acik) return { cumle: `Takipte ticket yok; defterde ${sayi(liste.length)} kayıt var.`, ton: 'iyi' };
    const bas = `Takipte ${sayi(ozet.acik)} ticket var.`;
    if (ozet.hata) {
      return {
        cumle: `${bas} ${sayi(ozet.hata)} ticket OneDesk’te hata verdi — düzeltip yeniden açın.`,
        ton: 'acil',
        eylem: { etiket: 'Onları göster', calistir: () => setDurumS('HATA') },
      };
    }
    if (ozet.numarasiz) {
      return {
        cumle: `${bas} ${sayi(ozet.numarasiz)} ticket’ın OneDesk numarası yazılmamış.`,
        ton: 'dikkat',
        eylem: { etiket: 'Onları göster', calistir: () => setDurumS('numarasiz') },
      };
    }
    if (ozet.gec) {
      return {
        cumle: `${bas} ${sayi(ozet.gec)} ticket ${sayi(hatirlatmaSaat)} saati geçti — takım liderine OneDesk no ve müşteri no ile yazın.`,
        ton: 'dikkat',
        eylem: { etiket: 'Onları göster', calistir: () => setDurumS('gec24') },
      };
    }
    return { cumle: `${bas} En eskisi ${sayi(ozet.enEski)} gündür açık.`, ton: 'sakin' };
  }, [liste.length, ozet, hatirlatmaSaat]);

  const binaAdi = binaSerial ? liste.find((t) => t.bina_serial === binaSerial)?.bina?.ad ?? binaSerial : null;
  const suzgecVar = Boolean(tarih !== 'hepsi' || binaSerial || durumS !== 'hepsi');
  const temizle = () => {
    setDurumS('hepsi');
    setTarih('hepsi');
    if (binaSerial) git('/yonetici/ticketlar');
  };

  return (
    <>
      <YonUst baslik="Ticketlar">
        <button className="yd" onClick={() => setAktarAcik(true)}>
          Excel’den aktar
        </button>
        <button className="yd" onClick={() => setSurum((s) => s + 1)} disabled={defter.yukleniyor}>
          Yenile
        </button>
        <button className="yd birincil" onClick={() => setYeniAcik(true)}>
          + Yeni ticket
        </button>
      </YonUst>

      <Icerik>
        {defter.hata ? <HataKutusu mesaj={defter.hata} yenile={defter.yenile} /> : null}

        {!defter.veri ? (
          <Iskelet yukseklik={60} />
        ) : !liste.length ? null : (
          <>
            <Hikaye cumle={hikaye.cumle} ton={hikaye.ton} eylem={hikaye.eylem} />
            <Manset
              etiket="Ticket özeti"
              ogeler={[
                { etiket: 'Takipte', deger: sayi(ozet.acik), onClick: () => setDurumS('takipte') },
                { etiket: 'Hata', deger: sayi(ozet.hata), renk: ozet.hata ? 'kirmizi' : undefined, onClick: () => setDurumS('HATA') },
                {
                  etiket: 'OneDesk no yok',
                  deger: sayi(ozet.numarasiz),
                  renk: ozet.numarasiz ? 'amber' : undefined,
                  onClick: () => setDurumS('numarasiz'),
                },
                {
                  etiket: gecEtiketi,
                  deger: sayi(ozet.gec),
                  renk: ozet.gec ? 'amber' : undefined,
                  onClick: () => setDurumS('gec24'),
                  baslik: `BÇO’da ${gecEtiketi} ticket: takım liderine OneDesk ID + müşteri no ile mail`,
                },
                { etiket: 'En eski', deger: `${sayi(ozet.enEski)} gün` },
              ]}
            />
          </>
        )}

        {binaSerial ? (
          <div className="yon-uyari" style={{ background: 'var(--birincil-yumusak)', borderColor: 'transparent', color: 'var(--metin)' }}>
            <span>
              Yalnız bir bina gösteriliyor: <b>{binaAdi}</b> ({binaSerial})
            </span>
            <span className="sag">
              <button className="yd" onClick={() => git('/yonetici/ticketlar')}>
                Bütün defter
              </button>
            </span>
          </div>
        ) : null}

        {/* ---------------- Durum çipleri ---------------- */}
        {liste.length ? (
          <CipSirasi etiket="Durum süzgeci">
            <Cip secili={durumS === 'hepsi'} sayi={onSuzulen.length} onClick={() => setDurumS('hepsi')}>
              Hepsi
            </Cip>
            <Cip
              secili={durumS === 'takipte'}
              sayi={onSuzulen.filter((t) => t.acik).length}
              onClick={() => setDurumS('takipte')}
              baslik="Açık + hata + transfer"
            >
              Takipte
            </Cip>
            {TICKET_DURUMLARI.map((d) => (
              <Cip
                key={d.durum}
                secili={durumS === d.durum}
                sayi={sayilar.get(d.durum) ?? 0}
                onClick={() => setDurumS(durumS === d.durum ? 'hepsi' : d.durum)}
                baslik={d.anlam}
              >
                {d.etiket}
              </Cip>
            ))}
          </CipSirasi>
        ) : null}

        {defter.yukleniyor && !defter.veri ? (
          <Iskelet satir={8} yukseklik={36} />
        ) : liste.length ? (
          <Tablo
            satirlar={suzulen}
            sutunlar={SUTUNLAR}
            anahtar={(t) => t.id}
            onAc={(t) => ticketAc(t.id)}
            seciliAnahtar={seciliId}
            aramaYerTutucu="Ara: ticket no, Location Id, site, müşteri, BN…"
            excelAdi="Ticketlar"
            kayitAnahtari="ticketlar"
            bosMetin={suzgecVar ? 'Bu süzgeçle ticket yok. Süzgeci değiştirin ya da temizleyin.' : 'Bu aramayla ticket yok.'}
            arac={
              <>
                <select
                  className="yon-alan tk-tarih-sec"
                  value={tarih}
                  onChange={(e) => setTarih(e.target.value as TarihSuzgeci)}
                  aria-label="Açılış tarihi"
                >
                  {TARIHLER.map((t) => (
                    <option key={t.deger} value={t.deger}>
                      {t.etiket}
                    </option>
                  ))}
                </select>
                {suzgecVar ? (
                  <button type="button" className="o-dugme kucuk metin" onClick={temizle}>
                    Temizle
                  </button>
                ) : null}
              </>
            }
          />
        ) : (
          <div className="o-liste">
            <BosDurum
              simge="🎫"
              baslik="Takipte ticket yok"
              aciklama="Bir işte “Ticket bağla” deyin ya da Excel’deki TICKET sayfasını aktarın."
            >
              <button type="button" className="o-dugme" onClick={() => setAktarAcik(true)}>
                Excel’den aktar
              </button>
            </BosDurum>
          </div>
        )}
      </Icerik>

      {seciliId ? (
        <TicketCekmecesi id={seciliId} kapat={() => ticketAc(null)} degisti={guncellendi} hatirlatmaSaat={hatirlatmaSaat} />
      ) : null}

      <YeniTicketPenceresi
        acik={yeniAcik}
        kapat={() => setYeniAcik(false)}
        kanallar={kanallar}
        kaydedildi={(t) => {
          setListe((eski) => [t, ...eski]);
          setSurum((s) => s + 1);
          ticketAc(t.id);
        }}
      />

      <ExcelAktarPaneli acik={aktarAcik} kapat={() => setAktarAcik(false)} bitti={() => setSurum((s) => s + 1)} />
    </>
  );
}

/* ------------------------------ Excel'den aktar (§5.3.8) ------------------------------ */

function ExcelAktarPaneli({ acik, kapat, bitti }: { acik: boolean; kapat: () => void; bitti: () => void }) {
  const { goster } = useBildirim();
  const [dosya, setDosya] = useState<File | null>(null);
  const [onizleme, setOnizleme] = useState<TicketAktarimSonucu | null>(null);
  const [bekliyor, setBekliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const girdi = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!acik) {
      setDosya(null);
      setOnizleme(null);
      setHata(null);
    }
  }, [acik]);

  const sec = async (f: File | null) => {
    setDosya(f);
    setOnizleme(null);
    setHata(null);
    if (!f) return;
    setBekliyor(true);
    try {
      setOnizleme(await ticketExcelAktar(f, true));
    } catch (h) {
      setHata(h instanceof Error ? h.message : 'Dosya okunamadı.');
    } finally {
      setBekliyor(false);
    }
  };

  const uygula = async () => {
    if (!dosya) return;
    setBekliyor(true);
    try {
      const y = await ticketExcelAktar(dosya, false);
      bitti();
      kapat();
      goster(`${sayi(y.eklenen)} ticket eklendi, ${sayi(y.guncellenen)} güncellendi.`, 'basari');
    } catch (h) {
      setHata(h instanceof Error ? h.message : 'Aktarılamadı.');
    } finally {
      setBekliyor(false);
    }
  };

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      kilitli={bekliyor}
      baslik="Excel’den aktar"
      altBaslik="data.xlsx içindeki TICKET sayfası. Önce ne olacağını görürsünüz; iki kez aktarmak çift kayıt üretmez."
      alt={
        <>
          <button type="button" className="o-dugme" onClick={() => girdi.current?.click()} disabled={bekliyor}>
            {dosya ? 'Başka dosya' : 'Dosya seç'}
          </button>
          <span className="bosluk" />
          <button
            type="button"
            className="o-dugme birincil"
            onClick={() => void uygula()}
            disabled={!onizleme || bekliyor || !(onizleme.eklenen + onizleme.guncellenen)}
          >
            {bekliyor ? 'Bekleyin…' : 'Aktar'}
          </button>
        </>
      }
    >
      <input
        ref={girdi}
        type="file"
        accept=".xlsx,.xlsm"
        hidden
        onChange={(o) => void sec(o.target.files?.[0] ?? null)}
      />
      {!dosya ? (
        <BosDurum kucuk simge="📄" baslik="Excel dosyasını seçin" aciklama="PS26 klasöründeki data.xlsx ya da TICKET sayfası olan herhangi bir dosya.">
          <button type="button" className="o-dugme birincil" onClick={() => girdi.current?.click()}>
            Dosya seç
          </button>
        </BosDurum>
      ) : bekliyor && !onizleme ? (
        <Iskelet satir={4} yukseklik={40} />
      ) : onizleme ? (
        <div className="tk-aktar-ozet">
          <p>
            <b>{dosya.name}</b> — {sayi(onizleme.okunan)} satır okundu.
          </p>
          <Manset
            ogeler={[
              { etiket: 'Eklenecek', deger: sayi(onizleme.eklenen) },
              { etiket: 'Güncellenecek', deger: sayi(onizleme.guncellenen) },
              { etiket: 'Zaten var', deger: sayi(onizleme.zaten_var) },
              { etiket: 'Binaya bağlanamayan', deger: sayi(onizleme.baglanamayan.length), renk: onizleme.baglanamayan.length ? 'amber' : undefined },
            ]}
          />
          {onizleme.baglanamayan.length ? (
            <p className="tk-ipucu">
              Binaya bağlanamayan satırlar da aktarılır; ayrıntıdan sonra binaya bağlayabilirsiniz.
            </p>
          ) : null}
        </div>
      ) : null}
      {hata ? <HataKutusu mesaj={hata} /> : null}
    </Panel>
  );
}
