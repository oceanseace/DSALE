/**
 * Altyapı › Ticketlar — Excel'deki TICKET sayfası gibi: Müşteri No ("73874320 +3", üzerine gelince hepsi) · Loc ID ·
 * Site · Task No · Task adı (⚠ kanal şikâyeti, TASKS'taki gibi) · Konu · Durum · Satış kanalı · Ticket · Başlangıç ·
 * Detay. Task No / Task adı / Satış kanalı ticket'ın işlerinden (seçilenler + kurulum engeliyle bağlananlar; sunucu
 * `saha/ticket.py _task_bilgileri`). Konu ve Durum hücreden seçilir, ticket no hücreye yazılır (Hata'da no istenmez);
 * sütun başlığından sırala/süz, "Ara…", Ctrl+C, Excel'e indir (ortak `Tablo`). Satıra çift tıklayınca ayrıntı
 * çekmecesi (TicketAyrinti.tsx: işler, "+ abone ekle", Sil). Yeni ticket tablonun üstündeki satıra yazılır
 * (YeniSatir.tsx + IsSecici.tsx: Müşteri No / Loc ID → açık işlerden seçim). ⋯ menü: "Çözüldü, 3 aydan eski" toplu
 * temizlik (kalıcı silme, onaylı). Eski "Tablolar" ekranı kaldırıldı (bu tablo onun yerini tutar).
 *
 * Yetki: `ticket.oku` salt okunur (liste, ayrıntı, fotoğraf, Excel); düzenleme denetimleri (yeni satır, durum/konu
 * listeleri, no yazma, Sil, "+ abone ekle") yalnız `ticket.defter` ile görünür — sunucu da aynı ayrımı uygular.
 * Durumlar: Açık · Hata · Bölge (bölgeye iletildi) · Çözüldü. "Açık engeller" YALNIZ Açık'ı izler; Hata ve Bölge kendi
 * çiplerinde (ikisi de çözülmemiş sayılır: bağlı işler askıda kalır). Bağlı işlerin hepsi BOSS'ta kapandıysa
 * (Tamamlandı / İptal / FOX iptal) satırda "Bağlı iş kapandı — takip gerekmiyor" + hızlı Sil; çip "İşi kapanan (N)".
 *
 * Varsayılan görünüm "Açık engeller": açık ticket'lar ve her birini bekleyen iş sayısı (sunucu `bekleyen_is`:
 * bağlı, kapanmamış, Bizim durumu "İptal" olmayan işler). TASKS'ta Bizim durum Port yok · Kıl yok · Sinyal yok ·
 * Güzergah yok seçilince iş ertelenir ve buradaki ticket'a bağlanır (yoksa açılır); ticket "Çözüldü" olunca
 * bekleyen işler TASKS'ta "Aranacak"a döner (operasyon/v2/akis.py → `_engel_bagla`, `ticket_degisti`).
 * Adres (Konsol.tsx): #/yonetici/ticketlar[/<id> | /<Bina Serial>].
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { SahaHatasi } from '../../../cekirdek/api/istemci';
import type { Ticket, TicketDurumu, TicketKonusu } from '../../../cekirdek/api/tipler';
import { ticketGuncelle, ticketKategorileri, tumTicketlar } from '../../../cekirdek/api/yonetim';
import { Icerik, YonUst } from '../../../cekirdek/konsol/Kabuk';
import { HataKutusu, useVeri } from '../../../cekirdek/konsol/parcalar';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { Iskelet } from '../../../cekirdek/ortak/Bos';
import { Cip, CipSirasi } from '../../../cekirdek/ortak/Suz';
import { Tablo, type TabloSutunu } from '../../../cekirdek/ortak/Tablo';
import { TICKET_KONULARI, durumBilgisi, tarihKisa } from '../../../cekirdek/ortak/ticketBilgi';
import { useOturum } from '../../../cekirdek/yerel/oturum';
import { git } from '../../../cekirdek/yol/rota';
import { DahaMenusu } from '../../../cekirdek/ortak/Menu';
import { useOnay } from '../../../cekirdek/ortak/Onay';
import { temizlikOnizle, temizlikYap, ticketSil, type TicketSatiri } from '../../../cekirdek/ticket/api';
import { cozulduMetni } from './bildirim';
import { DurumHucresi, KonuHucresi, NoHucresi } from './hucreler';
import { YeniSatir } from './YeniSatir';
import { TicketCekmecesi } from './TicketAyrinti';
import './ticket.css';

type Suzgec = 'hepsi' | 'engeller' | 'numarasiz' | 'gec' | 'kapanan' | TicketDurumu;

/** Sunucu her ticket'a bekleyen iş sayısını ekler (`saha/ticket.py` → `bekleyen_isler`). */
const bekleyen = (t: Ticket) => (t as TicketSatiri).bekleyen_is ?? 0;
const ts = (t: Ticket) => t as TicketSatiri;
/** Müşteri No hücresi: ticket'ın ve işlerinin müşteri no'ları, tekrarsız. */
const musteriler = (t: Ticket) => ts(t).musteriler ?? (t.musteri ? t.musteri.split(/[\s,;/|]+/).filter(Boolean) : []);
/** Ticket no gerekmeyen durum: Hata (ek kapasite açılamadı). "Ticket no yok" yalnız Açık/Çözüldü'yü sayar. */
const noGerekmez = (t: Ticket) => t.durum === 'HATA';
/** Bağlı işlerin hepsi BOSS'ta kapandı (sunucu `isi_kapandi`): takip gerekmiyor. */
const isiKapandi = (t: Ticket) => Boolean(ts(t).isi_kapandi);

/** BÇO'da hatırlatma süresi (ayar `ticket_bco_hatirlatma_saat`; EK-12.7): geçen açık ticket için TL'ye mail. */
const VARSAYILAN_HATIRLATMA_SAAT = 24;
const gecti = (t: Ticket, saat: number) => t.acik && (t.acik_gun ?? 0) * 24 >= Math.max(1, saat);

const konuKisa = (konu: string) => TICKET_KONULARI.find((k) => k.konu === konu)?.kisa ?? konu;

export function Ticketlar({ deger }: { deger?: string | null }) {
  const { goster } = useBildirim();
  const [surum, setSurum] = useState(0);
  const defter = useVeri(tumTicketlar, [surum]);
  const [liste, setListe] = useState<Ticket[]>([]);
  const [suzgec, setSuzgec] = useState<Suzgec>('engeller');
  const { izinli } = useOturum();
  /** Yazma (aç, düzenle, durum, sil, iş bağla) yalnız ticket.defter; ticket.oku salt okunur. */
  const yazabilir = izinli('ticket.defter');
  const yeniRef = useRef<HTMLInputElement>(null);
  const [hatirlatmaSaat, setHatirlatmaSaat] = useState(VARSAYILAN_HATIRLATMA_SAAT);
  const [onayPenceresi, sor] = useOnay();

  /* Adres: /<id> → o ticket açık; /<Bina Serial> → yalnız o binanın ticket'ları. */
  const seciliId = deger && /^\d+$/.test(deger) ? Number(deger) : null;
  const binaSerial = deger && !/^\d+$/.test(deger) ? deger : null;

  useEffect(() => {
    if (defter.veri) setListe(defter.veri.ticketlar);
  }, [defter.veri]);

  useEffect(() => {
    let iptal = false;
    ticketKategorileri()
      .then((k) => !iptal && k.bco_hatirlatma_saat && setHatirlatmaSaat(k.bco_hatirlatma_saat))
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  const ticketAc = useCallback((id: number | null) => git(id ? `/yonetici/ticketlar/${id}` : '/yonetici/ticketlar'), []);
  const yerlestir = useCallback((t: Ticket) => setListe((eski) => eski.map((x) => (x.id === t.id ? t : x))), []);
  const cikar = useCallback((id: number) => setListe((eski) => eski.filter((x) => x.id !== id)), []);

  /** "Çözüldü, 3 aydan eski" toplu temizlik: önce sayı, onay, sonra kalıcı silme. */
  const temizle = useCallback(async () => {
    try {
      const { sayi } = await temizlikOnizle(90);
      if (!sayi) {
        goster('3 aydan eski çözülmüş ticket yok.', 'bilgi');
        return;
      }
      const evet = await sor({
        baslik: `${sayi.toLocaleString('tr-TR')} ticket temizlensin mi?`,
        metin: "Çözüldü durumunda ve 3 aydan (90 gün) eski ticket'lar kalıcı olarak silinir.",
        onay: 'Temizle',
        yikici: true,
      });
      if (!evet) return;
      const y = await temizlikYap(90);
      goster(y.mesaj, 'basari');
      setSurum((s) => s + 1);
    } catch (h) {
      goster(h instanceof SahaHatasi ? h.message : 'Temizlenemedi.', 'uyari');
    }
  }, [goster, sor]);

  /** Hızlı Sil (bağlı işi kapanmış ticket): onay, sonra KALICI silme (ayrıntıdaki Sil ile aynı uç). */
  const hizliSil = useCallback(
    async (t: Ticket) => {
      const evet = await sor({
        baslik: `Ticket ${t.ticket_no || `#${t.id}`} silinsin mi?`,
        metin: "Bağlı işlerin hepsi BOSS'ta kapandı. Ticket, geçmişi ve fotoğrafları kalıcı olarak silinir.",
        onay: 'Sil',
        yikici: true,
      });
      if (!evet) return;
      try {
        const y = await ticketSil(t.id);
        cikar(t.id);
        goster(y.mesaj || 'Ticket silindi.', 'basari');
      } catch (h) {
        goster(h instanceof SahaHatasi ? h.message : 'Silinemedi.', 'uyari');
      }
    },
    [sor, cikar, goster],
  );

  /** Hücreden değişiklik: hemen kaydedilir; hata olursa hücre eski değerinde kalır. */
  const guncelle = useCallback(
    async (id: number, govde: { durum?: TicketDurumu; ticket_no?: string; konu?: TicketKonusu }, basari: string) => {
      try {
        const y = await ticketGuncelle(id, govde);
        yerlestir(y.ticket);
        const d = y as { bekliyora_donen_is?: number; donen_tasklar?: string[] };
        const cozuldu = cozulduMetni(d.donen_tasklar, d.bekliyora_donen_is ?? 0);
        goster(cozuldu ? `${basari} ${cozuldu}` : basari, 'basari');
        return true;
      } catch (h) {
        goster(h instanceof SahaHatasi ? h.message : 'Kaydedilemedi.', 'uyari');
        return false;
      }
    },
    [yerlestir, goster],
  );

  const sutunlar = useMemo<Array<TabloSutunu<Ticket>>>(
    () => [
      {
        anahtar: 'musteri',
        baslik: 'Müşteri No',
        deger: (t) => musteriler(t).join(', '),
        goster: (t) => {
          const m = musteriler(t);
          if (!m.length) return '';
          return (
            <span className="tk-musteri" title={m.length > 1 ? m.join('\n') : undefined}>
              {m[0]}
              {m.length > 1 ? <span className="tk-musteri-ek">+{m.length - 1}</span> : null}
            </span>
          );
        },
        genislik: 130,
      },
      { anahtar: 'loc', baslik: 'Loc ID', deger: (t) => t.location_id || '', genislik: 116 },
      { anahtar: 'site', baslik: 'Site / Bina', deger: (t) => t.site || t.bina?.ad || '', genislik: 200, kartta: 'baslik' },
      {
        anahtar: 'taskno',
        baslik: 'Task No',
        deger: (t) => t.task_no || '',
        goster: (t) => {
          const l = (t.task_no || '').split(', ').filter(Boolean);
          if (!l.length) return '';
          return (
            <span title={l.length > 1 ? l.join('\n') : undefined}>
              {l[0]}
              {l.length > 1 ? <span className="tk-musteri-ek">+{l.length - 1}</span> : null}
            </span>
          );
        },
        genislik: 120,
      },
      {
        anahtar: 'task',
        baslik: 'Task adı',
        deger: (t) => t.task_adi || '',
        goster: (t) =>
          isiKapandi(t) ? (
            <span className="tk-kapandi-satir">
              <span className="tk-kapandi" title={`Bağlı iş kapandı — takip gerekmiyor (${t.task_adi || ''})`}>
                Bağlı iş kapandı — takip gerekmiyor
              </span>
              {yazabilir ? (
                <button
                  type="button"
                  className="tk-kapandi-sil"
                  onMouseDown={(o) => o.stopPropagation()}
                  onDoubleClick={(o) => o.stopPropagation()}
                  onClick={(o) => {
                    o.stopPropagation();
                    void hizliSil(t);
                  }}
                >
                  Sil
                </button>
              ) : null}
            </span>
          ) : ts(t).uyari ? (
            <span title={ts(t).uyari}>
              <span className="tk-uyari" aria-label={ts(t).uyari}>
                ⚠{' '}
              </span>
              {t.task_adi}
            </span>
          ) : (
            t.task_adi || ''
          ),
        genislik: 190,
      },
      {
        anahtar: 'konu',
        baslik: 'Konu',
        deger: (t) => konuKisa(t.konu),
        goster: (t) =>
          yazabilir ? (
            <KonuHucresi
              konu={t.konu}
              etiket={konuKisa(t.konu)}
              degistir={(k) => guncelle(t.id, { konu: k }, `Konu: ${konuKisa(k)}.`)}
            />
          ) : (
            konuKisa(t.konu)
          ),
        genislik: 120,
      },
      {
        anahtar: 'durum',
        baslik: 'Durum',
        deger: (t) => durumBilgisi(t.durum).etiket,
        goster: (t) => (
          <DurumHucresi
            durum={t.durum}
            salt={!yazabilir}
            degistir={(d) => guncelle(t.id, { durum: d }, `Durum: ${durumBilgisi(d).etiket}.`)}
          />
        ),
        genislik: 120,
        kartta: 'alt',
      },
      { anahtar: 'kanal', baslik: 'Satış kanalı', deger: (t) => ts(t).satis_kanali || t.kanal || '', genislik: 170 },
      {
        anahtar: 'no',
        baslik: 'Ticket',
        deger: (t) => t.ticket_no || '',
        goster: (t) =>
          yazabilir ? (
            <NoHucresi
              no={t.ticket_no}
              gerekmez={noGerekmez(t)}
              kaydet={(no) => guncelle(t.id, { ticket_no: no }, `Ticket no ${no} yazıldı.`)}
            />
          ) : (
            t.ticket_no || ''
          ),
        genislik: 132,
      },
      { anahtar: 'acilis', baslik: 'Başlangıç', deger: (t) => t.acilis ?? '', goster: (t) => tarihKisa(t.acilis), genislik: 104 },
      { anahtar: 'detay', baslik: 'Detay', deger: (t) => (t.detay || '').replace(/\s+/g, ' '), genislik: 260 },
    ],
    [guncelle, yazabilir, hizliSil],
  );

  const binada = useMemo(() => (binaSerial ? liste.filter((t) => t.bina_serial === binaSerial) : liste), [liste, binaSerial]);
  const say = useCallback((s: Suzgec) => binada.filter((t) => uyar(t, s, hatirlatmaSaat)).length, [binada, hatirlatmaSaat]);
  const suzulen = useMemo(() => {
    const l = binada.filter((t) => uyar(t, suzgec, hatirlatmaSaat));
    /* Açık engeller: en çok işi bekleten önce, sonra en eski. */
    return suzgec === 'engeller' ? [...l].sort((a, b) => bekleyen(b) - bekleyen(a) || (b.acik_gun ?? 0) - (a.acik_gun ?? 0)) : l;
  }, [binada, suzgec, hatirlatmaSaat]);
  const bekleyenToplam = useMemo(() => binada.reduce((n, t) => n + (t.durum === 'AÇIK' ? bekleyen(t) : 0), 0), [binada]);
  const kapananSayisi = say('kapanan');
  const gecenSayisi = say('gec');
  const numarasizSayisi = say('numarasiz');

  return (
    <>
      <YonUst baslik="Ticketlar">
        <button className="yd" onClick={() => setSurum((s) => s + 1)} disabled={defter.yukleniyor}>
          Yenile
        </button>
        {yazabilir ? (
          <button className="yd birincil" onClick={() => yeniRef.current?.focus()}>
            + Yeni ticket
          </button>
        ) : null}
        {izinli('ticket.defter') ? (
          <DahaMenusu
            etiket="Ticket defteri eylemleri"
            ogeler={[{ etiket: 'Çözüldü, 3 aydan eski — temizle…', yikici: true, calistir: () => void temizle() }]}
          />
        ) : null}
      </YonUst>

      <Icerik>
        {defter.hata ? <HataKutusu mesaj={defter.hata} yenile={defter.yenile} /> : null}

        {binaSerial ? (
          <div className="yon-uyari tk-bina-suzgeci">
            <span>
              Yalnız bir bina: <b>{binada[0]?.site || binada[0]?.bina?.ad || binaSerial}</b>
            </span>
            <span className="sag">
              <button className="yd" onClick={() => git('/yonetici/ticketlar')}>
                Bütün defter
              </button>
            </span>
          </div>
        ) : null}

        {yazabilir ? (
          <YeniSatir
            odakRef={yeniRef}
            musteriArar={izinli('is.musteri')}
            kaydedildi={(t) => {
              setListe((eski) => [t, ...eski]);
              setSuzgec(t.durum === 'AÇIK' ? 'engeller' : 'hepsi');
            }}
          />
        ) : null}

        {!defter.veri ? (
          defter.hata ? null : <Iskelet satir={8} yukseklik={36} />
        ) : !liste.length ? (
          <p className="tk-bos">Henüz ticket yok. Yukarıdaki satıra Müşteri No yapıştırın (ya da Loc ID yazın), Enter.</p>
        ) : (
          <>
            <CipSirasi etiket="Durum süzgeci">
              <Cip
                secili={suzgec === 'engeller'}
                sayi={say('engeller')}
                onClick={() => setSuzgec('engeller')}
                baslik={`Takipteki (Açık) ticket'lar · onları bekleyen ${bekleyenToplam.toLocaleString('tr-TR')} iş. Hata ve Bölge kendi çiplerinde.`}
              >
                Açık engeller
              </Cip>
              <Cip secili={suzgec === 'hepsi'} sayi={binada.length} onClick={() => setSuzgec('hepsi')}>
                Hepsi
              </Cip>
              {(['AÇIK', 'HATA', 'BÖLGE', 'ÇÖZÜLDÜ'] as TicketDurumu[]).map((d) => (
                <Cip key={d} secili={suzgec === d} sayi={say(d)} onClick={() => setSuzgec(suzgec === d ? 'engeller' : d)}>
                  {durumBilgisi(d).etiket}
                </Cip>
              ))}
              {kapananSayisi ? (
                <Cip
                  secili={suzgec === 'kapanan'}
                  sayi={kapananSayisi}
                  onClick={() => setSuzgec(suzgec === 'kapanan' ? 'engeller' : 'kapanan')}
                  baslik="Bağlı işlerin hepsi BOSS'ta kapandı (Tamamlandı / İptal / FOX iptal): takip gerekmiyor"
                >
                  İşi kapanan
                </Cip>
              ) : null}
              {numarasizSayisi ? (
                <Cip secili={suzgec === 'numarasiz'} sayi={numarasizSayisi} onClick={() => setSuzgec('numarasiz')}>
                  Ticket no yok
                </Cip>
              ) : null}
              {gecenSayisi ? (
                <Cip
                  secili={suzgec === 'gec'}
                  sayi={gecenSayisi}
                  onClick={() => setSuzgec('gec')}
                  baslik="Takım liderine ticket no + müşteri no ile mail atın"
                >
                  {hatirlatmaSaat.toLocaleString('tr-TR')} saati geçen
                </Cip>
              ) : null}
            </CipSirasi>
            <Tablo
              satirlar={suzulen}
              sutunlar={sutunlar}
              anahtar={(t) => t.id}
              onAc={(t) => ticketAc(t.id)}
              seciliAnahtar={seciliId}
              aramaYerTutucu="Ara: ticket no, Loc ID, site, müşteri…"
              excelAdi="Ticketlar"
              kayitAnahtari="ticketlar"
              bosMetin={suzgec === 'engeller' ? 'Açık engel yok: bekleyen ticket kalmadı.' : 'Bu süzgeçle ticket yok.'}
            />
          </>
        )}
      </Icerik>

      {seciliId ? (
        <TicketCekmecesi
          id={seciliId}
          kapat={() => ticketAc(null)}
          degisti={yerlestir}
          silindi={cikar}
          yazabilir={yazabilir}
          hatirlatmaSaat={hatirlatmaSaat}
        />
      ) : null}
      {onayPenceresi}

    </>
  );
}

function uyar(t: Ticket, s: Suzgec, hatirlatmaSaat: number): boolean {
  switch (s) {
    case 'hepsi':
      return true;
    case 'engeller':
      return t.durum === 'AÇIK';
    case 'kapanan':
      return isiKapandi(t);
    case 'numarasiz':
      return (t.durum === 'AÇIK' || t.durum === 'ÇÖZÜLDÜ') && !t.ticket_no;
    case 'gec':
      return gecti(t, hatirlatmaSaat);
    default:
      return t.durum === s;
  }
}
