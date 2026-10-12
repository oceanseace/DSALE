/**
 * Yeni ticket — yalnız iki şey sorulur: Loc ID ve konu (Sinyal / Ek kapasite).
 * Loc ID yazılınca site (bina adı), ilçe/mahalle ve binadaki açık işlerin müşteri
 * numaraları sunucudan gelir (`./api.ts` → `saha/ticket.py · lokasyon_bilgisi`);
 * kayıtta da sunucu aynısını doldurur. Durum Açık başlar; Detay isteğe bağlı;
 * ticket no (BÇO) sonradan listeden ya da ayrıntıdan yazılır.
 * Çağıranlar: Altyapı › Ticketlar, iş çekmecesi ("Ticket bağla"), bina kartı (bina hazır gelir).
 */

import { useEffect, useState } from 'react';
import { SahaHatasi } from '../api/istemci';
import type { Ticket, TicketKonusu } from '../api/tipler';
import { ticketOlustur } from '../api/yonetim';
import { Cekmece } from '../ortak/Cekmece';
import { useBildirim } from '../ortak/Bildirim';
import { DurumCipi } from '../ortak/BinaNotlari';
import { Uyari } from '../ortak/Ikon';
import { acikGunMetni } from '../ortak/ticketBilgi';
import { lokasyonBilgisi, type LokasyonBilgisi } from './api';
import '../konsol/ekran.css';
import './yeniTicket.css';

/** Kullanıcının Excel'indeki iki konu. Diğer konular (Güzergah…) yalnız eski kayıtlarda kalır. */
const KONULAR: Array<{ konu: TicketKonusu; etiket: string }> = [
  { konu: 'SİNYAL', etiket: 'Sinyal' },
  { konu: 'EK SP', etiket: 'Ek kapasite' },
];

export function YeniTicketPenceresi({
  acik,
  kapat,
  bina,
  lokasyon,
  kaydedildi,
}: {
  acik: boolean;
  kapat: () => void;
  /** Binadan açılınca dolu gelir; Loc ID binadan okunur. */
  bina?: { bina_serial: string; baslik?: string | null } | null;
  /** Binası olmayan işten açılınca işin Loc ID'si; kutu bununla dolu açılır. */
  lokasyon?: string | null;
  kaydedildi?: (t: Ticket) => void;
}) {
  const { goster } = useBildirim();
  const [loc, setLoc] = useState('');
  const [konu, setKonu] = useState<TicketKonusu | null>(null);
  const [detay, setDetay] = useState('');
  const [bilgi, setBilgi] = useState<LokasyonBilgisi | null>(null);
  const [bilgiHata, setBilgiHata] = useState<string | null>(null);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  /* Pencere her açılışta temiz başlar. */
  useEffect(() => {
    if (!acik) return;
    setLoc(lokasyon ?? '');
    setKonu(null);
    setDetay('');
    setBilgi(null);
    setHata(null);
  }, [acik, lokasyon]);

  /* Loc ID (ya da hazır bina) → site, ilçe/mahalle, müşteri no'ları. Yazarken beklenir. */
  const binadan = Boolean(bina);
  const aranan = bina ? bina.bina_serial : loc.trim();
  useEffect(() => {
    setBilgi(null);
    setBilgiHata(null);
    if (!acik || aranan.length < 4) return undefined;
    let iptal = false;
    const sayac = window.setTimeout(() => {
      lokasyonBilgisi(binadan ? { bina_serial: aranan } : { loc: aranan })
        .then((b) => {
          if (iptal) return;
          setBilgi(b);
          if (binadan) setLoc(b.location_id);
        })
        .catch((h) => !iptal && setBilgiHata(h instanceof SahaHatasi ? h.message : 'Bilgi alınamadı.'));
    }, binadan ? 0 : 350);
    return () => {
      iptal = true;
      window.clearTimeout(sayac);
    };
  }, [acik, aranan, binadan]);

  const acikTicketlar = bilgi?.acik_ticketlar ?? [];
  const ayniKonuAcik = acikTicketlar.some((t) => t.konu === konu);
  const hazir = Boolean((bina || loc.trim()) && konu);

  const kaydet = async () => {
    if (!hazir || !konu) return;
    setKaydediliyor(true);
    setHata(null);
    try {
      const y = await ticketOlustur({
        konu,
        bina_serial: bina?.bina_serial ?? bilgi?.bina_serial ?? null,
        location_id: loc.trim() || null,
        detay: detay.trim() || null,
      });
      goster('Ticket kaydedildi. Ticket no gelince listeye yazın.', 'basari');
      kaydedildi?.(y.ticket);
      kapat();
    } catch (h) {
      setHata(h instanceof SahaHatasi ? h.message : 'Ticket kaydedilemedi.');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <Cekmece acik={acik} kapat={kapat} kilitli={kaydediliyor} baslik="Yeni ticket" altBaslik="Loc ID yazın, konuyu seçin.">
      <div className="tk-yeni">
        <label className="tk-alan">
          <span className="yon-etiket">Loc ID</span>
          {bina ? (
            <div className="tk-bina">
              <div style={{ minWidth: 0 }}>
                <b>{bilgi?.site || bina.baslik || bina.bina_serial}</b>
                <span>{loc ? `Loc ID ${loc}` : 'Loc ID okunuyor…'}</span>
              </div>
            </div>
          ) : (
            <input
              className="o-girdi tk-no"
              autoFocus
              value={loc}
              placeholder="Örn. O25265408"
              onChange={(e) => setLoc(e.target.value.toLocaleUpperCase('tr-TR').replace(/\s+/g, ''))}
            />
          )}
        </label>

        {/* ---------------- Otomatik dolan bilgiler ---------------- */}
        {bilgi ? (
          bilgi.bulundu ? (
            <div className="tk-oto">
              <Satir etiket="Site" deger={bilgi.site} />
              <Satir etiket="İlçe / mahalle" deger={[bilgi.ilce, bilgi.mahalle].filter(Boolean).join(' / ')} />
              <Satir
                etiket="Müşteri"
                deger={bilgi.musteriler.join(', ')}
                bos="Binada açık iş yok"
              />
            </div>
          ) : !bina ? (
            <p className="tk-ipucu">Bu Loc ID ile bina bulunamadı; yine de kaydedebilirsiniz.</p>
          ) : null
        ) : bilgiHata ? (
          <p className="tk-ipucu">{bilgiHata} Kaydedince sunucu Loc ID’den doldurur.</p>
        ) : null}

        {acikTicketlar.length ? (
          <div className={`tk-acik-uyari${ayniKonuAcik ? ' guclu' : ''}`}>
            <Uyari boyut={17} />
            <div>
              <b>{ayniKonuAcik ? 'Bu binada aynı konuda açık ticket var — ikincisini açmayın.' : 'Bu binada açık ticket var.'}</b>
              {acikTicketlar.slice(0, 3).map((t) => (
                <div key={t.id} className="tk-acik-satir">
                  <DurumCipi durum={t.durum} kucuk /> {t.konu_etiket}
                  {t.ticket_no ? ` · No ${t.ticket_no}` : ''}
                  {acikGunMetni(t.acik_gun) ? ` · ${acikGunMetni(t.acik_gun)}` : ''}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* ---------------- Konu ---------------- */}
        <div className="tk-alan">
          <span className="yon-etiket">Konu</span>
          <div className="tk-konular" role="radiogroup" aria-label="Konu">
            {KONULAR.map((k) => (
              <button
                key={k.konu}
                type="button"
                role="radio"
                aria-checked={konu === k.konu}
                className={konu === k.konu ? 'secili' : undefined}
                onClick={() => setKonu(k.konu)}
              >
                {k.etiket}
              </button>
            ))}
          </div>
        </div>

        <label className="tk-alan">
          <span className="yon-etiket">Detay (isteğe bağlı)</span>
          <input
            className="o-girdi"
            value={detay}
            maxLength={4000}
            placeholder="Örn. 3 daire sinyal yok diyor"
            onChange={(e) => setDetay(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !kaydediliyor && void kaydet()}
          />
        </label>

        {hata ? (
          <div className="yon-uyari kirmizi">
            <Uyari boyut={18} />
            {hata}
          </div>
        ) : null}

        <div className="bp-onay-dugmeler">
          <button className="o-dugme" onClick={kapat} disabled={kaydediliyor}>
            Vazgeç
          </button>
          <button className="o-dugme buyuk birincil" onClick={() => void kaydet()} disabled={!hazir || kaydediliyor}>
            {kaydediliyor ? 'Kaydediliyor…' : ayniKonuAcik ? 'Yine de kaydet' : !konu ? 'Konuyu seçin' : 'Kaydet'}
          </button>
        </div>
      </div>
    </Cekmece>
  );
}

function Satir({ etiket, deger, bos = '—' }: { etiket: string; deger: string; bos?: string }) {
  return (
    <div className="tk-oto-satir">
      <span>{etiket}</span>
      <b>{deger || bos}</b>
    </div>
  );
}
