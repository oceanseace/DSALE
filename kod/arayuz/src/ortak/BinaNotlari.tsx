/**
 * Bina kartının iki küçük bölümü — satışçı bina ekranında ve yönetici
 * "Ayrıntılar" penceresinde aynı görünür:
 *
 *   · Veri notları: sistemin bu binanın kaydında bulduğu tutarsızlıklar
 *     (dsale/kalite.py). Uyarılar önce; düzeltilen değer "eski → yeni" yazılır.
 *   · Ticket'lar: bu binaya açılmış OneDesk ticket'larının sayısı ve son durumu,
 *     altında "Ticket aç". Açık ticket varken ikinci ticket açılmasın diye açık
 *     olan en üstte ve renkli durur.
 */

import { useState } from 'react';
import type { KaliteBayragi, Ticket } from '../api/tipler';
import { acikGunMetni, durumBilgisi, tarihKisa } from './ticketBilgi';
import './binaNotlari.css';

/* ------------------------------ Veri notları ------------------------------ */

const ALAN_ADI: Record<string, string> = {
  location_id: 'Location Id',
  tellcordia_id: 'Tellcordia ID',
  kat: 'Kat',
  ad: 'Ad',
  site_adi: 'Site adı',
};

export function KaliteNotlari({
  notlar,
  enFazla = 4,
}: {
  notlar: KaliteBayragi[] | undefined | null;
  /** Bu kadarı görünür, kalanı "+N not daha" ile açılır. */
  enFazla?: number;
}) {
  const [hepsi, setHepsi] = useState(false);
  if (!notlar?.length) return null;
  // Uyarılar önce: satışçıyı ya da yöneticiyi yanıltabilecek olanlar üstte.
  const sirali = [...notlar].sort(
    (a, b) => (a.seviye === 'uyari' ? 0 : 1) - (b.seviye === 'uyari' ? 0 : 1),
  );
  const gorunen = hepsi ? sirali : sirali.slice(0, enFazla);
  const kalan = sirali.length - gorunen.length;

  return (
    <section className="bn-kart" aria-label="Veri notları">
      <div className="bn-baslik">
        <span>Veri notları</span>
        <span className="bn-sayi">{sirali.length}</span>
      </div>
      <ul className="bn-notlar">
        {gorunen.map((n, i) => (
          <li key={`${n.kural}-${i}`} className={`bn-not s-${n.seviye}`}>
            <span className="bn-nokta" aria-hidden="true" />
            <span className="bn-not-metin">
              {n.mesaj}
              {n.duzeltme ? (
                <span className="bn-duzeltme">
                  Düzeltildi · {ALAN_ADI[n.duzeltme.alan] ?? n.duzeltme.alan}:{' '}
                  <s>{String(n.duzeltme.eski ?? '—')}</s> → <b>{String(n.duzeltme.yeni ?? '—')}</b>
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
      {kalan > 0 ? (
        <button type="button" className="bn-daha" onClick={() => setHepsi(true)}>
          +{kalan} not daha
        </button>
      ) : null}
    </section>
  );
}

/* ------------------------------ Ticket'lar ------------------------------ */

export function DurumCipi({ durum, kucuk = false }: { durum: string; kucuk?: boolean }) {
  const b = durumBilgisi(durum);
  return (
    <span className={`tk-cip tk-d-${b.renk}${kucuk ? ' kucuk' : ''}`} title={b.anlam}>
      {b.etiket}
    </span>
  );
}

export function TicketOzeti({
  ticketlar,
  ticketAc,
  ticketSecildi,
  tumunuGor,
  enFazla = 3,
  dugmeEtiketi = 'Ticket aç',
}: {
  /** `undefined`: henüz bilinmiyor (çevrimdışı / yükleniyor). */
  ticketlar: Ticket[] | undefined;
  ticketAc?: () => void;
  /** Satıra tıklanınca (yönetici: ticket ayrıntısı). Verilmezse satırlar düz yazıdır. */
  ticketSecildi?: (t: Ticket) => void;
  tumunuGor?: () => void;
  enFazla?: number;
  dugmeEtiketi?: string;
}) {
  const liste = ticketlar ?? [];
  const acik = liste.filter((t) => t.acik).length;

  return (
    <section className="bn-kart" aria-label="Ticket'lar">
      <div className="bn-baslik">
        <span>Ticket'lar</span>
        {liste.length ? <span className="bn-sayi">{liste.length}</span> : null}
        {ticketAc ? (
          <button type="button" className="bn-ticket-ac" onClick={ticketAc}>
            <span aria-hidden="true">+</span> {dugmeEtiketi}
          </button>
        ) : null}
      </div>

      {ticketlar === undefined ? (
        <p className="bn-bos">Ticket bilgisi için internet gerekiyor.</p>
      ) : !liste.length ? (
        <p className="bn-bos">Bu binaya hiç ticket açılmadı.</p>
      ) : (
        <>
          <p className={`bn-ozet${acik ? ' acik' : ''}`}>
            {acik
              ? `${acik.toLocaleString('tr-TR')} açık ticket var — aynı sorun için ikincisini açmayın.`
              : 'Açık ticket yok.'}
          </p>
          <ul className="bn-ticketlar">
            {liste.slice(0, enFazla).map((t) => {
              const yas = t.acik ? acikGunMetni(t.acik_gun) : null;
              const icerik = (
                <>
                  <DurumCipi durum={t.durum} kucuk />
                  <span className="bn-ticket-metin">
                    <b>{t.konu_etiket}</b>
                    <span className="bn-ticket-alt">
                      {[
                        t.ticket_no ? `No ${t.ticket_no}` : 'OneDesk no yok',
                        tarihKisa(t.acilis),
                        yas,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  </span>
                </>
              );
              return (
                <li key={t.id}>
                  {ticketSecildi ? (
                    <button type="button" className="bn-ticket" onClick={() => ticketSecildi(t)}>
                      {icerik}
                      <span className="bn-ok" aria-hidden="true">
                        ›
                      </span>
                    </button>
                  ) : (
                    <div className="bn-ticket">{icerik}</div>
                  )}
                </li>
              );
            })}
          </ul>
          {tumunuGor && liste.length > 0 ? (
            <button type="button" className="bn-daha" onClick={tumunuGor}>
              {liste.length > enFazla
                ? `Hepsini ticket defterinde gör (${liste.length.toLocaleString('tr-TR')})`
                : 'Ticket defterinde gör'}
            </button>
          ) : null}
        </>
      )}
    </section>
  );
}
