/**
 * Ticketlar › yeni satır — Excel'de alta satır yazar gibi: Müşteri No yapıştır/yaz → Loc ID, Site/Bina kendiliğinden
 * dolar (`GET /api/ticket/musteri`) ve altta İŞ SEÇİCİSİ açılır (`GET /api/ticket/isler`, IsSecici.tsx): müşterinin
 * (virgülle birden çok müşteri) ya da Loc ID'nin AÇIK işleri; ticket'ın hangi iş(ler) için açıldığı seçilir (toptan
 * müşteride tek müşteri no'nun yüzlerce işi olur; bir lokasyonda birden çok abone etkilenebilir — "Hepsini seç").
 * Kurulum işi varsa o (kanal şikâyeti asla) önceden seçilidir. Seçilen Task No'lar ticket'a yazılır (Task No ·
 * Task adı · Satış kanalı sütunları). Loc ID doğrudan da yazılır: o lokasyonun bütün açık işleri listelenir.
 * Aynı lokasyonda açık ya da son 180 günde kapanmış ticket varsa Ekle'den önce uyarı (engellemez).
 * Konu: Sinyal / Ek kapasite · Durum: Açık / Çözüldü / Hata (uygulamanın açılır listesi; `hucreler.tsx Acilir`).
 * Enter kaydeder (Müşteri No'da Enter yeni aramaysa ve birden çok iş geldiyse önce seçici açılır); Esc temizler.
 * Elle değiştirilen hücre (Loc ID, Site) sonraki aramayla ezilmez. Çağıran: Ticketlar.tsx.
 */

import { useRef, useState, type KeyboardEvent } from 'react';
import { SahaHatasi } from '../../../cekirdek/api/istemci';
import type { TicketDurumu, TicketKonusu } from '../../../cekirdek/api/tipler';
import { durumBilgisi } from '../../../cekirdek/ortak/ticketBilgi';
import {
  isSecenekleri,
  lokasyonBilgisi,
  musteriBilgisi,
  ticketOlusturIsli,
  type IsSecenekleri,
  type TicketSatiri,
} from '../../../cekirdek/ticket/api';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { benzerMetni } from './bildirim';
import { Acilir, konuSecenekleri } from './hucreler';
import { IsSecici } from './IsSecici';

const DURUMLAR: Array<{ deger: TicketDurumu; etiket: string }> = (['AÇIK', 'ÇÖZÜLDÜ', 'HATA', 'BÖLGE'] as TicketDurumu[]).map(
  (d) => ({ deger: d, etiket: durumBilgisi(d).etiket }),
);

interface Satir {
  musteri: string;
  loc: string;
  site: string;
  konu: TicketKonusu;
  durum: TicketDurumu;
  ticketNo: string;
  detay: string;
}

const BOS: Satir = { musteri: '', loc: '', site: '', konu: 'SİNYAL', durum: 'AÇIK', ticketNo: '', detay: '' };

export function YeniSatir({
  musteriArar,
  kaydedildi,
  odakRef,
}: {
  /** `is.musteri` izni: yoksa Müşteri No'dan arama yapılmaz (Loc ID yazılır). */
  musteriArar: boolean;
  kaydedildi: (t: TicketSatiri) => void;
  odakRef?: React.RefObject<HTMLInputElement>;
}) {
  const { goster } = useBildirim();
  const [s, setSDurum] = useState<Satir>(BOS);
  /* Son değer ref'te de tutulur: Enter → arama → kayıt zincirinde kayıt, aramanın doldurduğunu görsün. */
  const guncel = useRef<Satir>(BOS);
  const setS = (f: Satir | ((o: Satir) => Satir)) => {
    guncel.current = typeof f === 'function' ? f(guncel.current) : f;
    setSDurum(guncel.current);
  };
  const [not, setNot] = useState<{ metin: string; tur: 'bilgi' | 'uyari' } | null>(null);
  const [aranan, setAranan] = useState(false);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [secenek, setSecenek] = useState<IsSecenekleri | null>(null);
  const [secili, setSeciliDurum] = useState<Set<string>>(new Set());
  const seciliRef = useRef<Set<string>>(new Set());
  const setSecili = (y: Set<string>) => {
    seciliRef.current = y;
    setSeciliDurum(y);
  };
  /** Kullanıcının elle yazdığı hücreler: aramayla ezilmez. */
  const elle = useRef<Set<'loc' | 'site'>>(new Set());
  const sonAranan = useRef({ musteri: '', loc: '', isler: '' });
  const icRef = useRef<HTMLInputElement>(null);
  const musteriRef = odakRef ?? icRef;

  const yaz = <K extends keyof Satir>(alan: K, deger: Satir[K]) => setS((o) => ({ ...o, [alan]: deger }));

  /** Seçici: müşteri no varsa müşterinin işleri, yoksa Loc ID'nin işleri. Dönüş: yeni arama yapıldı mı + iş sayısı. */
  const isleriGetir = async (): Promise<number | null> => {
    const m = musteriArar ? guncel.current.musteri.trim() : '';
    const loc = m ? '' : guncel.current.loc.trim();
    const anahtar = `${m}|${loc}`;
    if ((!m && !loc) || anahtar === sonAranan.current.isler) return null;
    sonAranan.current.isler = anahtar;
    try {
      const v = await isSecenekleri(m ? { musteri: m } : { loc });
      setSecenek(v);
      setSecili(new Set(v.varsayilan));
      if (!m && v.site && !(elle.current.has('site') && guncel.current.site)) setS((o) => ({ ...o, site: v.site }));
      return v.isler.length;
    } catch (h) {
      sonAranan.current.isler = '';
      setNot({ metin: h instanceof SahaHatasi ? h.message : 'İşler getirilemedi.', tur: 'uyari' });
      return null;
    }
  };

  const musteriAra = async (metin = guncel.current.musteri): Promise<number | null> => {
    const no = metin.trim();
    if (!no || !musteriArar || no === sonAranan.current.musteri) return null;
    sonAranan.current.musteri = no;
    setAranan(true);
    try {
      const b = await musteriBilgisi(no);
      setS((o) => ({
        ...o,
        loc: elle.current.has('loc') && o.loc ? o.loc : b.lokasyon || o.loc,
        site: elle.current.has('site') && o.site ? o.site : b.bina_adi || o.site,
      }));
      const bulunmayan = b.sonuclar.filter((x) => !x.bulundu).length;
      setNot(
        !b.bulundu
          ? { metin: 'Bu müşteri no ile iş bulunamadı — Loc ID’yi elle yazın.', tur: 'uyari' }
          : !b.acik
            ? { metin: 'Müşterinin açık işi yok; son işinden dolduruldu.', tur: 'bilgi' }
            : bulunmayan
              ? { metin: `${bulunmayan} müşteri no için iş bulunamadı.`, tur: 'bilgi' }
              : null,
      );
      return await isleriGetir();
    } catch (h) {
      sonAranan.current.musteri = '';
      setNot({ metin: h instanceof SahaHatasi ? h.message : 'Müşteri aranamadı.', tur: 'uyari' });
      return null;
    } finally {
      setAranan(false);
    }
  };

  /** Loc ID elle yazıldıysa: site ve (müşteri boşsa) o lokasyonun açık işleri seçicide. */
  const locAra = async () => {
    const loc = guncel.current.loc.trim();
    if (!loc || !elle.current.has('loc') || loc === sonAranan.current.loc) return;
    sonAranan.current.loc = loc;
    try {
      const b = await lokasyonBilgisi({ loc });
      setS((o) => ({
        ...o,
        loc: b.location_id || o.loc,
        site: elle.current.has('site') && o.site ? o.site : b.site || o.site,
      }));
      setNot(b.bulundu ? null : { metin: 'Bu Loc ID bulunamadı; yine de kaydedilebilir.', tur: 'bilgi' });
      if (!guncel.current.musteri.trim()) await isleriGetir();
    } catch {
      sonAranan.current.loc = '';
    }
  };

  const temizle = () => {
    setS(BOS);
    setNot(null);
    setSecenek(null);
    setSecili(new Set());
    elle.current.clear();
    sonAranan.current = { musteri: '', loc: '', isler: '' };
    musteriRef.current?.focus();
  };

  const kaydet = async () => {
    if (kaydediliyor) return;
    const s = guncel.current;
    if (!s.loc.trim() && !s.musteri.trim()) {
      setNot({ metin: 'Müşteri No ya da Loc ID yazın.', tur: 'uyari' });
      musteriRef.current?.focus();
      return;
    }
    setKaydediliyor(true);
    try {
      const y = await ticketOlusturIsli({
        konu: s.konu,
        durum: s.durum,
        location_id: s.loc.trim() || null,
        musteri: s.musteri.trim() || null,
        site: s.site.trim() || null,
        ticket_no: s.ticketNo.trim() || null,
        detay: s.detay.trim() || null,
        isler: [...seciliRef.current],
      });
      kaydedildi(y.ticket);
      goster(y.bulunmayan_is?.length ? `Ticket kaydedildi; ${y.bulunmayan_is.length} iş bulunamadı.` : 'Ticket kaydedildi.', 'basari');
      temizle();
    } catch (h) {
      setNot({ metin: h instanceof SahaHatasi ? h.message : 'Kaydedilemedi.', tur: 'uyari' });
    } finally {
      setKaydediliyor(false);
    }
  };

  const tus = (o: KeyboardEvent) => {
    if (o.key === 'Enter') {
      o.preventDefault();
      void (async () => {
        if (document.activeElement === musteriRef.current) {
          const yeni = await musteriAra();
          if (yeni !== null && yeni > 1) return; // önce hangi iş(ler) olduğu seçilsin
        }
        await kaydet();
      })();
    } else if (o.key === 'Escape') {
      o.preventDefault();
      temizle();
    }
  };

  const seciliIsler = secenek?.isler.filter((x) => secili.has(x.task_no)) ?? [];
  const ilkIs = seciliIsler[0];
  const benzer = secenek ? benzerMetni(secenek.benzer) : '';

  return (
    <div className="tk-yeni" role="group" aria-label="Yeni ticket satırı" onKeyDown={tus}>
      <div className="tk-yeni-izgara">
        <label className="tk-yh genis">
          <span>Müşteri No</span>
          <input
            ref={musteriRef}
            value={s.musteri}
            placeholder={musteriArar ? 'Yapıştır / yaz (virgülle çok)' : 'Müşteri no'}
            inputMode="numeric"
            autoComplete="off"
            onChange={(o) => yaz('musteri', o.target.value)}
            onPaste={(o) => {
              const metin = o.clipboardData.getData('text').replace(/\s*[\r\n\t]+\s*/g, ', ').replace(/,\s*$/, '');
              o.preventDefault();
              const yeni = s.musteri.trim() ? `${s.musteri.replace(/,\s*$/, '')}, ${metin}` : metin;
              yaz('musteri', yeni);
              void musteriAra(yeni);
            }}
            onBlur={() => void musteriAra()}
          />
        </label>
        <label className="tk-yh">
          <span>Loc ID</span>
          <input
            value={s.loc}
            placeholder={aranan ? 'aranıyor…' : 'Loc ID'}
            autoComplete="off"
            onChange={(o) => {
              elle.current.add('loc');
              yaz('loc', o.target.value.toLocaleUpperCase('tr-TR'));
            }}
            onBlur={() => void locAra()}
          />
        </label>
        <label className="tk-yh genis">
          <span>Site / Bina</span>
          <input
            value={s.site}
            placeholder="kendiliğinden dolar"
            autoComplete="off"
            onChange={(o) => {
              elle.current.add('site');
              yaz('site', o.target.value);
            }}
          />
        </label>
        <div className="tk-yh genis salt" title={seciliIsler.map((x) => `${x.task_no} ${x.task_adi}`).join('\n') || undefined}>
          <span>Task</span>
          <output>
            {ilkIs ? (
              <>
                {ilkIs.uyari ? <span className="tk-uyari">⚠&nbsp;</span> : null}
                {ilkIs.task_no} · {ilkIs.task_adi}
                {seciliIsler.length > 1 ? ` +${seciliIsler.length - 1}` : ''}
              </>
            ) : (
              <i>{secenek?.isler.length ? 'aşağıdan seçin' : '—'}</i>
            )}
          </output>
        </div>
        <div className="tk-yh">
          <span>Konu</span>
          <Acilir deger={s.konu} secenekler={konuSecenekleri()} etiket="Konu" degistir={(k) => yaz('konu', k)} />
        </div>
        <div className="tk-yh">
          <span>Durum</span>
          <Acilir deger={s.durum} secenekler={DURUMLAR} etiket="Durum" degistir={(d) => yaz('durum', d)} />
        </div>
        <label className="tk-yh">
          <span>Ticket no</span>
          <input
            value={s.ticketNo}
            placeholder={s.durum === 'HATA' ? 'gerekmez' : 'sonra da yazılır'}
            inputMode="numeric"
            autoComplete="off"
            onChange={(o) => yaz('ticketNo', o.target.value.replace(/[^\dA-Za-z-]/g, ''))}
          />
        </label>
        <label className="tk-yh genis">
          <span>Detay</span>
          <input value={s.detay} placeholder="isteğe bağlı" autoComplete="off" onChange={(o) => yaz('detay', o.target.value)} />
        </label>
        <div className="tk-yh eylem">
          <span aria-hidden="true">&nbsp;</span>
          <button type="button" className="o-dugme birincil kucuk" disabled={kaydediliyor} onClick={() => void kaydet()}>
            {kaydediliyor ? 'Kaydediliyor…' : 'Ekle ↵'}
          </button>
        </div>
      </div>
      {not ? <p className={`tk-yeni-not ${not.tur}`}>{not.metin}</p> : null}
      {benzer ? (
        <p className="tk-yeni-not uyari" role="status">
          ⚠ {benzer}
        </p>
      ) : null}
      {secenek?.toptan ? (
        <p className="tk-yeni-not uyari" role="status">
          Toptan müşteri: bu no birçok aboneyi taşır — aboneyi Loc ID ile daraltın ya da elle seçin.
        </p>
      ) : null}
      {secenek && secenek.isler.length ? (
        <IsSecici isler={secenek.isler} secili={secili} degistir={setSecili} fazla={secenek.fazla} />
      ) : null}
    </div>
  );
}
