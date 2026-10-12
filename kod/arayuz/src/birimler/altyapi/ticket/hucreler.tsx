/**
 * Ticket tablosunun yerinde düzenlenen hücreleri (Excel'deki gibi): Durum açılır liste, Konu uygulamanın açılır
 * listesi (`Acilir`, yeni satırda da), Ticket no yazılır (Hata durumunda no istenmez: ek kapasite açılamadı). Değişiklik hemen sunucuya gider (`PATCH /api/ticket/<id>`).
 * Çağıran: `Ticketlar.tsx` (sütun tanımları). Tablo'nun hücre seçimi/klavyesi bu
 * denetimlere karışmasın diye fare ve tuş olayları burada durdurulur.
 */

import { useState, type SyntheticEvent } from 'react';
import { DahaMenusu } from '../../../cekirdek/ortak/Menu';
import type { TicketDurumu, TicketKonusu } from '../../../cekirdek/api/tipler';
import { durumBilgisi } from '../../../cekirdek/ortak/ticketBilgi';

/** Excel TICKET sayfasındaki durumlar + Bölge (bölgeye iletildi); eski kayıttaki başka bir durum (Kapatıldı…) listede
 *  kendisi de görünür. */
const HUCRE_DURUMLARI: TicketDurumu[] = ['AÇIK', 'ÇÖZÜLDÜ', 'HATA', 'BÖLGE'];

/** Kullanıcının Excel'indeki iki konu; eski kayıttaki başka konu listede kendisi de görünür. */
export const HUCRE_KONULARI: Array<{ konu: TicketKonusu; etiket: string }> = [
  { konu: 'SİNYAL', etiket: 'Sinyal' },
  { konu: 'EK SP', etiket: 'Ek kapasite' },
];

const durdur = (o: SyntheticEvent) => o.stopPropagation();

/**
 * Uygulamanın kendi açılır listesi (`DahaMenusu`): bütün seçenekler birlikte görünür, seçili olan ✓.
 * Yerli `<select>` Excel görünümlü satırda boş seçenek gösterip tek değer gösteriyordu (kullanıcı ekran görüntüsü).
 */
export function Acilir<T extends string>({
  deger,
  secenekler,
  degistir,
  etiket,
  sinif,
}: {
  deger: T;
  secenekler: Array<{ deger: T; etiket: string }>;
  degistir: (yeni: T) => void;
  etiket: string;
  sinif?: string;
}) {
  const secili = secenekler.find((s) => s.deger === deger);
  return (
    <span className={`tk-acilir${sinif ? ` ${sinif}` : ''}`} onMouseDown={durdur} onClick={durdur} onDoubleClick={durdur} onKeyDown={durdur}>
      <DahaMenusu
        etiket={etiket}
        dugme={
          <>
            <span className="tk-acilir-deger">{secili?.etiket ?? deger}</span>
            <span className="tk-acilir-ok" aria-hidden="true">
              ▾
            </span>
          </>
        }
        ogeler={secenekler.map((s) => ({
          etiket: s.etiket,
          simge: s.deger === deger ? '✓' : <span aria-hidden="true">&nbsp;</span>,
          calistir: () => {
            if (s.deger !== deger) degistir(s.deger);
          },
        }))}
      />
    </span>
  );
}

/** Konu seçenekleri: Excel'deki iki konu; eski kayıttaki başka konu listede kendisi de görünür. */
export function konuSecenekleri(konu?: TicketKonusu, etiket?: string): Array<{ deger: TicketKonusu; etiket: string }> {
  const iki = HUCRE_KONULARI.map((k) => ({ deger: k.konu, etiket: k.etiket }));
  return !konu || iki.some((k) => k.deger === konu) ? iki : [{ deger: konu, etiket: etiket ?? konu }, ...iki];
}

export function KonuHucresi({
  konu,
  etiket,
  degistir,
}: {
  konu: TicketKonusu;
  etiket: string;
  degistir: (yeni: TicketKonusu) => Promise<boolean>;
}) {
  const [bekliyor, setBekliyor] = useState(false);
  return (
    <Acilir
      deger={konu}
      secenekler={konuSecenekleri(konu, etiket)}
      etiket="Konu"
      sinif={`tk-hucre-acilir${bekliyor ? ' bekliyor' : ''}`}
      degistir={async (k) => {
        setBekliyor(true);
        await degistir(k);
        setBekliyor(false);
      }}
    />
  );
}

export function DurumHucresi({
  durum,
  degistir,
  salt = false,
}: {
  durum: TicketDurumu;
  degistir: (yeni: TicketDurumu) => Promise<boolean>;
  /** Salt okunur (ticket.oku): açılır liste yok, yalnız durum çipi. */
  salt?: boolean;
}) {
  const [bekliyor, setBekliyor] = useState(false);
  if (salt) return <span className={`tk-cip kucuk tk-d-${durumBilgisi(durum).renk}`}>{durumBilgisi(durum).etiket}</span>;
  const secenekler = HUCRE_DURUMLARI.includes(durum) ? HUCRE_DURUMLARI : [durum, ...HUCRE_DURUMLARI];
  return (
    <select
      className={`tk-cip kucuk tk-d-${durumBilgisi(durum).renk} tk-hucre-durum`}
      value={durum}
      disabled={bekliyor}
      aria-label="Durum"
      onMouseDown={durdur}
      onClick={durdur}
      onDoubleClick={durdur}
      onKeyDown={durdur}
      onChange={async (o) => {
        setBekliyor(true);
        await degistir(o.target.value as TicketDurumu);
        setBekliyor(false);
      }}
    >
      {secenekler.map((d) => (
        <option key={d} value={d}>
          {durumBilgisi(d).etiket}
        </option>
      ))}
    </select>
  );
}

export function NoHucresi({
  no,
  kaydet,
  gerekmez = false,
}: {
  no: string;
  kaydet: (yeni: string) => Promise<boolean>;
  /** Durum Hata: ek kapasite açılamadı, ticket no yok — "+ no yaz" gösterilmez. */
  gerekmez?: boolean;
}) {
  const [yazilan, setYazilan] = useState<string | null>(null);
  if (yazilan === null) {
    return no ? (
      <>{no}</>
    ) : gerekmez ? null : (
      <button
        type="button"
        className="tk-hucre-no-ekle"
        onMouseDown={durdur}
        onDoubleClick={durdur}
        onClick={(o) => {
          o.stopPropagation();
          setYazilan('');
        }}
      >
        + no yaz
      </button>
    );
  }
  const bitir = async () => {
    const deger = yazilan.trim();
    if (!deger) return setYazilan(null);
    if (await kaydet(deger)) setYazilan(null);
  };
  return (
    <input
      className="tk-hucre-no"
      autoFocus
      inputMode="numeric"
      value={yazilan}
      placeholder="Ticket no"
      onMouseDown={durdur}
      onClick={durdur}
      onDoubleClick={durdur}
      onChange={(o) => setYazilan(o.target.value.replace(/[^\dA-Za-z-]/g, ''))}
      onBlur={() => void bitir()}
      onKeyDown={(o) => {
        o.stopPropagation();
        if (o.key === 'Enter') o.currentTarget.blur(); // kayıt tek yerden: onBlur
        if (o.key === 'Escape') setYazilan(null);
      }}
    />
  );
}
