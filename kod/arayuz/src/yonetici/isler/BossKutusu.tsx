/**
 * BOSS ile konuşma sınırı (EK-4, §3.4): sistem Turkcell'e YAZMAZ.
 *
 *   · "BOSS'a işlenecek" (giden kutusu): bizdeki atama/randevu/askı/SMS BOSS'a
 *     elle yazılır. Her satırda BOSS'a birebir girilecek değerler ve [Kopyala];
 *     işaretleyince "BOSS'a işlendi". (Eklenti gelirse aynı uçlarla çalışır.)
 *   · "Eşleşmemiş BOSS ekibi" (§6.3): "BOSS'ta 'EKİP ADI' yazan 23 iş var. Bu
 *     ekip kim?" + teknisyen seçici (girişsiz BOSS Mobil kişiler dahil, EK-2)
 *     → [Eşle ve ata] tek hamlede atar; toplu geri alınabilir.
 */

import { useCallback, useEffect, useState } from 'react';
import { bossEkip, bossEkipEsle, bossGiden, bossGidenIslendi, bossIslendi, hataMetni, topluGeriAl } from '../../is/api';
import type { BossEkipYanit, BossGiden } from '../../is/tipler';
import { useBildirim } from '../../ortak/Bildirim';
import { BosDurum, Iskelet } from '../../ortak/Bos';
import { useIsler } from './depo';
import { BossGidenAlanlari } from './IsCekmecesi';
import { yonelme } from './dil';
import { kisaAd, TeknikSecici } from './parcalar';

const NEDEN_METNI: Record<string, string> = {
  ekip: 'Ekip',
  randevu: 'Randevu',
  aski: 'Askı',
  sms: 'Talep Ulaşamama SMS',
};

export function BossGidenListesi({ ac }: { ac: (isNo: string) => void }) {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [liste, setListe] = useState<BossGiden[] | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [bekliyor, setBekliyor] = useState<string | null>(null);

  const yukle = useCallback(() => {
    bossGiden()
      .then((l) => {
        setListe(l);
        setHata(null);
      })
      .catch((e) => setHata(hataMetni(e)));
  }, []);

  useEffect(() => {
    yukle();
  }, [yukle, depo.meta?.sayac.boss_bekleyen]);

  const islendi = async (g: BossGiden) => {
    setBekliyor(g.is_no);
    try {
      const y = await bossGidenIslendi(g.is_no);
      depo.isYaz(y);
      setListe((l) => (l ?? []).filter((x) => x.is_no !== g.is_no));
      bildirim.geriAl(`${g.boss_task_no ?? g.is_no} BOSS’a işlendi`, async () => {
        try {
          const z = await bossIslendi(g.is_no, false);
          depo.isYaz(z);
          yukle();
        } catch (e) {
          bildirim.goster(hataMetni(e), 'uyari');
        }
      });
      void depo.simdiYokla();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(null);
    }
  };

  if (hata) return <div className="o-hata"><span className="mesaj">{hata}</span></div>;
  if (!liste) return <Iskelet satir={4} yukseklik={96} />;
  if (!liste.length) {
    return <BosDurum simge="✓" baslik="BOSS’a işlenecek bir şey yok." aciklama="Bizdeki atama ve randevular BOSS’la aynı." kucuk />;
  }
  return (
    <div className="ip-giden-liste" role="list">
      <p className="ip-not-satiri">
        Sistem BOSS’a yazmaz. Her satırdaki değerleri BOSS’ta ilgili task’a girin, sonra “BOSS’a işlendi”yi işaretleyin. Sonraki
        raporda BOSS aynıysa bayrak kendiliğinden kalkar.
      </p>
      {liste.map((g) => {
        const s = depo.harita.get(g.is_no);
        return (
          <article key={g.is_no} className="ip-giden" role="listitem">
            <header>
              <button type="button" className="o-bag" onClick={() => ac(g.is_no)}>
                {s?.task_adi ?? 'İş'}
              </button>
              <span className="ip-kaynak">
                {s?.musteri_adi ? `${s.musteri_adi} · ` : ''}
                {g.neden
                  .split(',')
                  .map((n) => NEDEN_METNI[n] ?? n)
                  .join(' + ')}
              </span>
            </header>
            <BossGidenAlanlari g={g} />
            <label className="o-onay-kutusu">
              <input type="checkbox" checked={false} disabled={bekliyor === g.is_no} onChange={() => void islendi(g)} />
              <span>BOSS’a işlendi</span>
            </label>
          </article>
        );
      })}
    </div>
  );
}

export function BossEkipEsleme() {
  const depo = useIsler();
  const bildirim = useBildirim();
  const [veri, setVeri] = useState<BossEkipYanit | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [secim, setSecim] = useState<Record<string, number | null>>({});
  const [bekliyor, setBekliyor] = useState<string | null>(null);

  const yukle = useCallback(() => {
    bossEkip()
      .then((v) => {
        setVeri(v);
        setHata(null);
      })
      .catch((e) => setHata(hataMetni(e)));
  }, []);

  useEffect(() => {
    yukle();
  }, [yukle]);

  const esle = async (ekip: string, teknikId: number) => {
    const t = depo.teknikler.find((x) => x.id === teknikId);
    setBekliyor(ekip);
    try {
      const y = await bossEkipEsle(ekip, teknikId);
      const n = Array.isArray(y.atanan) ? y.atanan.length : Number(y.atanan) || 0;
      void depo.tazele();
      depo.teknikleriTazele();
      yukle();
      bildirim.geriAl(`“${ekip}” artık ${t?.ad ?? 'bu kişi'} · ${n} iş ${yonelme(kisaAd(t?.ad))} atandı`, async () => {
        try {
          await topluGeriAl(y.toplu_id);
          void depo.tazele();
          yukle();
          bildirim.goster('Atamalar geri alındı. (Ekip eşleşmesi kişinin kartında kalır.)', 'basari');
        } catch (e) {
          bildirim.goster(hataMetni(e), 'uyari');
        }
      });
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setBekliyor(null);
    }
  };

  if (hata) return <div className="o-hata"><span className="mesaj">{hata}</span></div>;
  if (!veri) return <Iskelet satir={3} yukseklik={120} />;
  if (!veri.eslesmemis.length) {
    return (
      <BosDurum
        simge="✓"
        baslik="Bütün BOSS ekipleri tanınıyor."
        aciklama={veri.eslesmis.length ? `${veri.eslesmis.length} BOSS ekibi bir teknisyenle eşleşmiş.` : undefined}
        kucuk
      />
    );
  }
  return (
    <div className="ip-ekip-esle">
      <p className="ip-not-satiri">
        BOSS’ta ekibi yazılı ama bizde karşılığı bilinmeyen işler. Ekibin kim olduğunu bir kez seçin; o ekibin bütün atanmamış işleri
        tek hamlede atanır ve sonraki raporlarda kendiliğinden eşleşir.
      </p>
      {veri.eslesmemis.map((e) => (
        <article key={e.boss_ekip} className="ip-ekip-kart">
          <p className="cumle">
            BOSS’ta “<b>{e.boss_ekip}</b>” yazan {e.is} iş var. Bu ekip kim?
          </p>
          <TeknikSecici
            teknikler={depo.teknikler}
            deger={secim[e.boss_ekip] ?? null}
            degisti={(id) => setSecim((s) => ({ ...s, [e.boss_ekip]: id }))}
          />
          <div className="ip-satir-eylemler sag">
            <button
              type="button"
              className="o-dugme"
              disabled={!secim[e.boss_ekip] || bekliyor === e.boss_ekip}
              onClick={() => void esle(e.boss_ekip, secim[e.boss_ekip]!)}
            >
              {bekliyor === e.boss_ekip ? 'Bekleyin…' : 'Eşle ve ata'}
            </button>
          </div>
        </article>
      ))}
      {veri.eslesmis.length ? (
        <details className="ip-acilir">
          <summary>Eşleşmiş ekipler ({veri.eslesmis.length})</summary>
          <ul className="ip-cikarilan">
            {veri.eslesmis.map((e) => (
              <li key={e.boss_ekip}>
                <span>{e.boss_ekip}</span>
                <b>{e.kisi.ad}</b>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
