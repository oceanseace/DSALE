/**
 * Bina kimlik kartı — satışçı bina ekranında ve yönetici "Ayrıntılar" penceresinde.
 *
 * Her satır tek dokunuşla kopyalanır (Location Id, Bina Serial, Tellcordia ID,
 * öbek, site adı, koordinat). Altta: konumu KOORDİNATLA aç ve ticket metnini
 * kopyala (sinyal / ek kapasite).
 */

import { useState } from 'react';
import type { Bina } from '../api/tipler';
import {
  TICKET_ADLARI,
  ekipTelefonunuKaydet,
  kayitliEkipTelefonu,
  konumBaglantisi,
  koordinatMetni,
  kopyala,
  ticketMetni,
  type TicketTuru,
} from './kimlik';
import './kimlik.css';

function Satir({ etiket, deger }: { etiket: string; deger?: string | null }) {
  const [durum, setDurum] = useState<'hazir' | 'tamam' | 'hata'>('hazir');
  if (!deger) return null;
  const tikla = async () => {
    const ok = await kopyala(deger);
    setDurum(ok ? 'tamam' : 'hata');
    window.setTimeout(() => setDurum('hazir'), 1500);
  };
  return (
    <button type="button" className="bk-satir" onClick={tikla} title="Kopyalamak için dokun">
      <span className="bk-etiket">{etiket}</span>
      <span className="bk-deger">{deger}</span>
      <span className={`bk-durum bk-${durum}`}>
        {durum === 'tamam' ? 'Kopyalandı' : durum === 'hata' ? 'Kopyalanamadı' : 'Kopyala'}
      </span>
    </button>
  );
}

export function BinaKimlik({ bina, ticket = true }: { bina: Bina; ticket?: boolean }) {
  const [ekip, setEkip] = useState(kayitliEkipTelefonu);
  const [bildiri, setBildiri] = useState<string | null>(null);
  const k = bina.kimlik;
  const koordinat = bina.lat != null && bina.lon != null ? koordinatMetni(bina.lat, bina.lon) : '';

  const ticketKopyala = async (tur: TicketTuru) => {
    ekipTelefonunuKaydet(ekip);
    const ok = await kopyala(ticketMetni(bina, tur, ekip));
    setBildiri(ok ? `${TICKET_ADLARI[tur]} metni kopyalandı — ticket'a yapıştırın.` : 'Kopyalanamadı.');
    window.setTimeout(() => setBildiri(null), 2600);
  };

  return (
    <div className="bk-kart">
      <div className="bk-baslik">Bina kimliği</div>
      <Satir etiket="Location Id" deger={k?.location_id} />
      <Satir etiket="Bina Serial" deger={k?.bina_serial || bina.bina_serial} />
      <Satir etiket="Tellcordia ID" deger={k?.tellcordia_id} />
      <Satir etiket="Satış öbeği" deger={bina.obek} />
      <Satir etiket="Site adı" deger={bina.crm_site_adi || bina.site_adi} />
      <Satir etiket="Koordinat" deger={koordinat} />

      {koordinat ? (
        <a
          className="bk-dugme"
          href={konumBaglantisi(bina.lat, bina.lon)}
          target="_blank"
          rel="noreferrer"
        >
          Konumu koordinatla aç
        </a>
      ) : null}

      {ticket ? (
        <div className="bk-ticket">
          <label className="bk-ekip">
            <span>Ekip telefonu</span>
            <input
              value={ekip}
              onChange={(e) => setEkip(e.target.value)}
              inputMode="tel"
              placeholder="+90 5xx xxx xx xx"
            />
          </label>
          <div className="bk-ticket-dugmeler">
            <button type="button" className="bk-dugme" onClick={() => ticketKopyala('sinyal')}>
              Ticket metni: {TICKET_ADLARI.sinyal}
            </button>
            <button type="button" className="bk-dugme ikincil" onClick={() => ticketKopyala('ek_kapasite')}>
              Ticket metni: {TICKET_ADLARI.ek_kapasite}
            </button>
          </div>
          {bildiri ? <div className="bk-bildiri">{bildiri}</div> : null}
        </div>
      ) : null}
    </div>
  );
}
