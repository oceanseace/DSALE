/**
 * Toplu atama kartı (§6.3) — 15 dakikanın ana yolu.
 *
 *   "4 atanmamış iş → Ali K.'ya ata (bugün 3, yarın 1)  [Ata]   Başkasına…"
 *
 * Kapsam: seçili öbeğin (ya da Tümü'nün) önerisi olan atanmamış işleri. Atlanır:
 * binasında açık ticket olan, ulaşılamayan, kontrol gereken iş (cümlede söylenir).
 * Sonuç: "4 iş Ali K.'ya atandı · Geri al" (10 sn; toplu geri al). Shift+O aynı yol.
 * Öbeğin teknisyeni yoksa: "Bu öbeğin teknisyeni yok. [Teknisyen seç]".
 */

import { useMemo, useState } from 'react';
import { hataMetni, oneriOnayla, topluAta, topluGeriAl } from '../../is/api';
import type { IsSatir, Obek, TopluSonuc } from '../../is/tipler';
import { useBildirim } from '../../ortak/Bildirim';
import { Panel } from '../../ortak/Panel';
import { Kbd } from '../../ortak/Kbd';
import { useIsler } from './depo';
import { yonelme } from './dil';
import { gunAnahtari, kisaAd, TeknikSecici } from './parcalar';

/** Kartın kapsamı: önerisi olan, atanabilir atanmamış işler. */
export function onerililer(isler: IsSatir[]): IsSatir[] {
  return isler.filter(
    (x) =>
      x.kova === 'atanmadi' &&
      x.durum !== 'triyaj' &&
      x.oneri &&
      !x.ticket &&
      !x.binada_acik_ticket,
  );
}

export function useTopluOnay() {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [bekliyor, setBekliyor] = useState(false);

  const sonuc = (y: TopluSonuc, kime: string) => {
    void depo.tazele();
    depo.teknikleriTazele();
    const n = y.atanan.length;
    const atlanan = y.atlanan.length ? ` · ${y.atlanan.length} iş atlandı (${y.atlanan[0].hata})` : '';
    if (!n) {
      bildirim.goster(y.atlanan[0]?.hata ?? 'Hiçbir iş atanmadı.', 'uyari', { sureMs: 6000 });
      return;
    }
    bildirim.geriAl(`${n} iş ${kime} atandı${atlanan}`, async () => {
      try {
        const g = await topluGeriAl(y.toplu_id);
        void depo.tazele();
        depo.teknikleriTazele();
        bildirim.goster(
          `${g.geri_alinan.length} atama geri alındı${g.atlanan.length ? ` · ${g.atlanan.length} iş o arada değiştiği için atlandı` : ''}`,
          'basari',
        );
      } catch (e) {
        bildirim.goster(hataMetni(e), 'uyari');
      }
    });
  };

  /** Önerileri onayla (O / Shift+O / kart). */
  const onayla = async (isler: IsSatir[]) => {
    if (!isler.length) return;
    setBekliyor(true);
    try {
      const y = await oneriOnayla(Object.fromEntries(isler.map((x) => [x.is_no, x.surum])));
      const kisiler = [...new Set(isler.map((x) => x.oneri?.teknik.id))];
      const kime =
        kisiler.length === 1 && isler[0].oneri ? yonelme(kisaAd(isler[0].oneri.teknik.ad)) : `${kisiler.length} teknisyene`;
      sonuc(y, kime);
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  /** Hepsini tek bir teknisyene ("Başkasına…"). */
  const birineAta = async (isler: IsSatir[], teknikId: number, ad: string) => {
    if (!isler.length) return;
    setBekliyor(true);
    try {
      const y = await topluAta(isler.map((x) => ({ is_no: x.is_no, teknik_id: teknikId, surum: x.surum })));
      sonuc(y, yonelme(kisaAd(ad)));
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(false);
    }
  };

  return { onayla, birineAta, bekliyor };
}

export function TopluAtaKarti({
  isler,
  obek,
  birincil,
  teknisyenSec,
}: {
  /** Kartın baktığı liste (öbek ya da Tümü; süzgeçsiz). */
  isler: IsSatir[];
  obek: Obek | null;
  /** Çekmece açıkken kartın düğmesi ikincil olur (ekranda tek birincil). */
  birincil: boolean;
  teknisyenSec: () => void;
}) {
  const depo = useIsler();
  const { onayla, birineAta, bekliyor } = useTopluOnay();
  const [baskasi, setBaskasi] = useState(false);

  const kapsam = useMemo(() => onerililer(isler), [isler]);
  const atanmamis = useMemo(() => isler.filter((x) => x.kova === 'atanmadi'), [isler]);
  const ticketli = atanmamis.filter((x) => x.durum !== 'triyaj' && (x.ticket || x.binada_acik_ticket)).length;
  const kontrol = atanmamis.filter((x) => x.durum === 'triyaj').length;
  const onerisiz = atanmamis.filter((x) => x.durum !== 'triyaj' && !x.oneri && !x.ticket && !x.binada_acik_ticket).length;

  const simdi = new Date(Date.now() + depo.sunucuFarkMs);
  const bugun = gunAnahtari(simdi);
  const bugunSay = kapsam.filter((x) => !x.oneri?.bas || x.oneri.bas.slice(0, 10) <= bugun).length;
  const sonraSay = kapsam.length - bugunSay;

  const kisiler = useMemo(() => {
    const m = new Map<number, { ad: string; n: number }>();
    kapsam.forEach((x) => {
      const t = x.oneri!.teknik;
      m.set(t.id, { ad: t.ad, n: (m.get(t.id)?.n ?? 0) + 1 });
    });
    return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
  }, [kapsam]);

  const notlar = [
    ticketli ? `${ticketli} iş ticket bekliyor, atanmadı` : null,
    kontrol ? `${kontrol} iş kontrol gerekli` : null,
  ].filter(Boolean);

  if (!atanmamis.length) return null;

  /* Öbeğin teknisyeni yok ve öneri de yok */
  if (!kapsam.length) {
    if (obek && !obek.sahip && onerisiz) {
      return (
        <div className="ip-toplu uyari">
          <p className="cumle">
            {onerisiz} atanmamış iş var. Bu öbeğin teknisyeni yok; ev teknisyeni seçilince işler ona önerilir.
          </p>
          <button type="button" className={`o-dugme ${birincil ? 'birincil' : ''}`} onClick={teknisyenSec}>
            Teknisyen seç
          </button>
        </div>
      );
    }
    if (!onerisiz && !notlar.length) return null;
    return (
      <div className="ip-toplu sade">
        <p className="cumle">
          {onerisiz ? `${onerisiz} atanmamış işin önerisi yok; satırdaki [Ata] ile teknisyen seçin.` : ''}
          {notlar.length ? `${onerisiz ? ' ' : ''}${notlar.join(' · ')}.` : ''}
        </p>
      </div>
    );
  }

  const tekKisi = kisiler.length === 1 ? kisiler[0][1].ad : null;
  const gunMetni = sonraSay ? ` (bugün ${bugunSay}, sonra ${sonraSay})` : bugunSay === kapsam.length ? ' (bugün)' : '';

  return (
    <div className="ip-toplu">
      <div className="ip-toplu-metin">
        <p className="cumle">
          <b>{kapsam.length} atanmamış iş</b> → {tekKisi ? `${yonelme(kisaAd(tekKisi))} ata` : `${kisiler.length} teknisyene ata`}
          {gunMetni}
        </p>
        {!tekKisi ? (
          <p className="alt">{kisiler.map(([, k]) => `${kisaAd(k.ad)} ${k.n}`).join(' · ')}</p>
        ) : null}
        {notlar.length || onerisiz ? (
          <p className="alt">
            {[...notlar, onerisiz ? `${onerisiz} işin önerisi yok` : null].filter(Boolean).join(' · ')}
          </p>
        ) : null}
      </div>
      <div className="ip-toplu-eylem">
        <button type="button" className="o-dugme metin" onClick={() => setBaskasi(true)} disabled={bekliyor}>
          Başkasına…
        </button>
        <button
          type="button"
          className={`o-dugme ${birincil ? 'birincil' : ''} ip-toplu-ata`}
          onClick={() => void onayla(kapsam)}
          disabled={bekliyor}
        >
          {bekliyor ? 'Atanıyor…' : 'Ata'}
          <Kbd>Shift+O</Kbd>
        </button>
      </div>
      <BaskasinaPaneli
        acik={baskasi}
        kapat={() => setBaskasi(false)}
        sayi={kapsam.length}
        obekId={obek?.id ?? null}
        sec={(id, ad) => {
          setBaskasi(false);
          void birineAta(kapsam, id, ad);
        }}
      />
    </div>
  );
}

function BaskasinaPaneli({
  acik,
  kapat,
  sayi,
  obekId,
  sec,
}: {
  acik: boolean;
  kapat: () => void;
  sayi: number;
  obekId: number | null;
  sec: (id: number, ad: string) => void;
}) {
  const depo = useIsler();
  const [secili, setSecili] = useState<number | null>(null);
  const t = depo.teknikler.find((x) => x.id === secili);
  return (
    <Panel
      acik={acik}
      kapat={kapat}
      baslik={`${sayi} işi kime verelim?`}
      altBaslik="Saatler teknisyenin sıradaki boş dilimlerinden yazılır."
      alt={
        <>
          <button type="button" className="o-dugme" onClick={kapat}>
            Vazgeç
          </button>
          <button type="button" className="o-dugme birincil" disabled={!t} onClick={() => t && sec(t.id, t.ad)}>
            {t ? `${yonelme(kisaAd(t.ad))} ata` : 'Ata'}
          </button>
        </>
      }
    >
      <TeknikSecici teknikler={depo.teknikler} deger={secili} degisti={setSecili} obekId={obekId} />
    </Panel>
  );
}
