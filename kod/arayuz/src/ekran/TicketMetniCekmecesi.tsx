/**
 * Satışçı: "Ticket aç" — sahada sinyal yok / port yok görülünce.
 *
 * Satışçı ticket kaydı açamaz (defter yöneticide); yaptığı iş bugünküyle aynı:
 * metni kopyalar, OneDesk'e ya da operasyona (WhatsApp) yapıştırır. Metin
 * sunucudan gelir — operasyonun OneDesk'e yazdığıyla harfi harfine aynı.
 * İnternet yoksa aynı metin telefonda üretilir (`ortak/kimlik.ts`); bunu
 * yalnız "Sinyal" ve "Ek kapasite" için yapabiliriz.
 */

import { useEffect, useRef, useState } from 'react';
import { ticketSablonu } from '../api/uclar';
import type { Bina, Ticket, TicketKonusu } from '../api/tipler';
import { Cekmece } from '../ortak/Cekmece';
import { Onay } from '../ortak/Ikon';
import { ekipTelefonunuKaydet, kayitliEkipTelefonu, kopyala, ticketMetni } from '../ortak/kimlik';
import { KONU_TURU, TICKET_KONULARI, acikGunMetni } from '../ortak/ticketBilgi';

export function TicketMetniCekmecesi({
  acik,
  kapat,
  bina,
  ticketlar,
}: {
  acik: boolean;
  kapat: () => void;
  bina: Bina;
  /** Binanın ticket'ları: aynı konuda açık ticket varsa satışçı uyarılır. */
  ticketlar?: Ticket[];
}) {
  const [konu, setKonu] = useState<TicketKonusu>('SİNYAL');
  const [ekip, setEkip] = useState(kayitliEkipTelefonu);
  const [metin, setMetin] = useState<string | null>(null);
  const [yerel, setYerel] = useState(false);
  const [kopyalandi, setKopyalandi] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  // Üst ekran her çizimde yeni nesne verir; metin yalnız seri / konu / ekip değişince yenilenir.
  const binaRef = useRef(bina);
  binaRef.current = bina;

  useEffect(() => {
    if (acik) {
      setKopyalandi(false);
      setHata(null);
      setEkip(kayitliEkipTelefonu());
    }
  }, [acik]);

  useEffect(() => {
    if (!acik) return undefined;
    let iptal = false;
    setKopyalandi(false);
    const sayac = window.setTimeout(async () => {
      try {
        const s = await ticketSablonu(binaRef.current.bina_serial, konu, ekip);
        if (iptal) return;
        setMetin(s.metin);
        setYerel(false);
        setHata(null);
      } catch {
        if (iptal) return;
        // Çevrimdışı: aynı şablon telefonda üretilir (yalnız iki konu için var).
        const tur = KONU_TURU[konu];
        if (tur) {
          setMetin(ticketMetni(binaRef.current, tur, ekip));
          setYerel(true);
          setHata(null);
        } else {
          setMetin(null);
          setHata('Bu konunun metni için internet gerekiyor. "Sinyal" ya da "Ek kapasite" internetsiz de çalışır.');
        }
      }
    }, 200);
    return () => {
      iptal = true;
      window.clearTimeout(sayac);
    };
  }, [acik, bina.bina_serial, konu, ekip]);

  const kopyalaTikla = async () => {
    if (!metin) return;
    ekipTelefonunuKaydet(ekip);
    const ok = await kopyala(metin);
    setKopyalandi(ok);
    if (!ok) setHata('Kopyalanamadı. Metne uzun basıp "Kopyala" deyin.');
  };

  return (
    <Cekmece
      acik={acik}
      kapat={kapat}
      baslik="Ticket aç"
      altBaslik="Konuyu seç, metni kopyala; OneDesk'e ya da operasyona (WhatsApp) yapıştır."
    >
      <div className="cekmece-govde">
        <span className="etiket blok bn-etiket">Sorun ne?</span>
        <div className="secim-serit bn-konular" role="radiogroup" aria-label="Konu">
          {TICKET_KONULARI.map((k) => (
            <button
              key={k.konu}
              type="button"
              role="radio"
              aria-checked={konu === k.konu}
              className={`secim bn-secim${konu === k.konu ? ' secili' : ''}`}
              onClick={() => setKonu(k.konu)}
            >
              {k.etiket}
            </button>
          ))}
        </div>

        <label className="alan" style={{ marginTop: 16 }}>
          <span className="etiket">Ekip telefonu (metnin sonuna yazılır)</span>
          <input
            className="girdi"
            inputMode="tel"
            value={ekip}
            placeholder="+90 5xx xxx xx xx"
            onChange={(e) => setEkip(e.target.value)}
          />
        </label>

        {(() => {
          const ayni = (ticketlar ?? []).find((t) => t.acik && t.konu === konu);
          if (!ayni) return null;
          return (
            <p className="bn-ipucu uyari">
              Bu binada bu konuda zaten açık ticket var
              {ayni.ticket_no ? ` (No ${ayni.ticket_no}` : ' ('}
              {acikGunMetni(ayni.acik_gun) ? `${ayni.ticket_no ? ', ' : ''}${acikGunMetni(ayni.acik_gun)}` : ''}).
              Yenisini göndermeden önce operasyona sor.
            </p>
          );
        })()}

        {metin ? <pre className="bn-metin">{metin}</pre> : null}
        {yerel ? <p className="bn-ipucu">İnternet yok: metin telefonda üretildi (aynı şablon).</p> : null}
        {hata ? <p className="bn-ipucu hata">{hata}</p> : null}
      </div>

      <div className="cekmece-ayak">
        <button
          type="button"
          className={`dugme buyuk ${kopyalandi ? 'yesil' : 'birincil'}`}
          onClick={kopyalaTikla}
          disabled={!metin}
        >
          {kopyalandi ? (
            <>
              <Onay boyut={22} /> Kopyalandı — yapıştırabilirsin
            </>
          ) : (
            'Metni kopyala'
          )}
        </button>
        <button type="button" className="dugme sessiz" onClick={kapat}>
          Kapat
        </button>
      </div>
    </Cekmece>
  );
}
