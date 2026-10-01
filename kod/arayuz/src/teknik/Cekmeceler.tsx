/**
 * İş ekranının alttan çekmeceleri (§6.9):
 *
 *   Bitti      önce ZORUNLU "Müşteri evde miydi?" [Evet] [Hayır]; sonra sonuç:
 *              Çözüldü · Cihaz değişti · Malzeme gerekiyor · Altyapı sorunu ·
 *              Müşteri başka gün istedi (gün + dilim). Seçilmeden "Kaydet" açılmaz.
 *   Evde yok   "10 dk bekledim, BOSS'tan 2 kez aradım, not bıraktım" onayı +
 *              isteğe bağlı not → iş anında operasyonun Aranacaklar listesine düşer.
 *   Not ekle   serbest not (operasyon görür).
 *   Önce bu    sırayı değiştirir; neden tek dokunuşla (Yakındaydım · Müşteri aradı · Diğer).
 *
 * Kaydet'e basıldığı anda eylem telefona yazılır, çekmece kapanır; gönderim
 * arka planda olur (sahada bekleyecek vakit yok). Yazılanı yanlış bir dokunuş
 * sessizce silmez: dolu çekmece dışarı dokununca "çıkılsın mı?" diye sorar.
 */

import { useCallback, useEffect, useState } from 'react';
import { Cekmece } from '../ortak/Cekmece';
import { DilimSecici, type Dilim } from '../ortak/DilimSecici';
import { useBildirim } from '../ortak/Bildirim';
import { Ev, Kalem, Onay, Saat, Takvim, Uyari, Yenile } from '../ortak/Ikon';
import type { Durum, IsAyrinti } from '../is/tipler';
import { durumDegistir, notEkle, onceBunu } from './depo';

type Sonuc = 'cozuldu' | 'cihaz_degisti' | 'malzeme' | 'altyapi_sorunu' | 'baska_gun';

/** Sonuç → sunucu geçişi (§5.3.2 "Teknik Bitti eşlemesi"). */
const SONUCLAR: Array<{
  sonuc: Sonuc;
  etiket: string;
  aciklama: string;
  yeni: Durum;
  renk: 'yesil' | 'mavi' | 'amber' | 'mor';
  Ikon: (p: { boyut?: number }) => JSX.Element;
}> = [
  { sonuc: 'cozuldu', etiket: 'Çözüldü', aciklama: 'Arıza giderildi', yeni: 'cozuldu', renk: 'yesil', Ikon: Onay },
  { sonuc: 'cihaz_degisti', etiket: 'Cihaz değişti', aciklama: 'Modem / cihaz yenilendi', yeni: 'cozuldu', renk: 'yesil', Ikon: Yenile },
  { sonuc: 'malzeme', etiket: 'Malzeme gerekiyor', aciklama: 'Operasyon tekrar planlar', yeni: 'askida', renk: 'amber', Ikon: Saat },
  { sonuc: 'altyapi_sorunu', etiket: 'Altyapı sorunu', aciklama: 'Ticket açılması gerekir', yeni: 'triyaj', renk: 'amber', Ikon: Uyari },
  { sonuc: 'baska_gun', etiket: 'Müşteri başka gün istedi', aciklama: 'Gün ve saat seçin', yeni: 'atandi', renk: 'mor', Ikon: Takvim },
];

function titret(ms = 30) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* titreşim yoksa sorun değil */
  }
}

/* ------------------------------ Bitti ------------------------------ */

export function BittiCekmecesi({
  acik,
  kapat,
  is,
  kaydedildi,
}: {
  acik: boolean;
  kapat: () => void;
  is: IsAyrinti;
  kaydedildi: () => void;
}) {
  const { goster } = useBildirim();
  const [evde, setEvde] = useState<boolean | null>(null);
  const [sonuc, setSonuc] = useState<Sonuc | null>(null);
  const [dilim, setDilim] = useState<Dilim | null>(null);
  const [not, setNot] = useState('');
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [cikisSor, setCikisSor] = useState(false);

  useEffect(() => {
    if (acik) return undefined;
    const t = window.setTimeout(() => {
      setEvde(null);
      setSonuc(null);
      setDilim(null);
      setNot('');
      setCikisSor(false);
    }, 220);
    return () => window.clearTimeout(t);
  }, [acik]);

  const dolu = evde !== null || sonuc !== null || Boolean(not.trim());
  const kapatmaIstegi = useCallback(() => {
    if (kaydediliyor) return;
    if (dolu) setCikisSor(true);
    else kapat();
  }, [kaydediliyor, dolu, kapat]);

  /*
   * Seçenekler sunucunun izin verdiği geçişlerden süzülür (`izinler.durumlar`):
   * ör. "Müşteri başka gün istedi" (→ atandi) sunucu o durumdan izin veriyorsa görünür.
   */
  const izinli = new Set<Durum>(is.izinler?.durumlar ?? SONUCLAR.map((s) => s.yeni));
  const secenekler = SONUCLAR.filter((s) => izinli.has(s.yeni));
  const secili = secenekler.find((s) => s.sonuc === sonuc) ?? null;
  const eksik =
    evde === null
      ? 'Önce “Müşteri evde miydi?” sorusunu yanıtlayın'
      : !sonuc
        ? 'Ne oldu? Bir sonuç seçin'
        : sonuc === 'baska_gun' && !dilim
          ? 'Müşterinin istediği günü ve saati seçin'
          : null;

  const kaydet = async () => {
    if (eksik || !secili || kaydediliyor) return;
    setKaydediliyor(true);
    try {
      const ek: Record<string, unknown> = { evde_miydi: evde, sonuc_kodu: secili.sonuc };
      if (not.trim()) ek.notu = not.trim();
      if (secili.sonuc === 'baska_gun' && dilim) ek.randevu = { bas: dilim.bas, bit: dilim.bit };
      const ofiseDoner = secili.yeni === 'askida' || secili.yeni === 'triyaj' ? secili.etiket : undefined;
      await durumDegistir(is, secili.yeni, `Bitti · ${secili.etiket}`, ek, ofiseDoner);
      titret();
      goster(
        secili.yeni === 'cozuldu'
          ? `${secili.etiket} olarak kaydedildi`
          : secili.yeni === 'atandi'
            ? 'Yeni gün kaydedildi; iş listenizde kalır'
            : `${secili.etiket}: iş operasyona döndü`,
        'basari',
      );
      kapat();
      if (secili.yeni !== 'atandi') kaydedildi();
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Kaydedilemedi.', 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <>
      <Cekmece acik={acik} kapat={kapatmaIstegi} baslik="İş bitti" altBaslik={is.task_adi} kilitli={kaydediliyor}>
        <div className="cekmece-govde tk-cekmece">
          <fieldset className="tk-soru">
            <legend>Müşteri evde miydi?</legend>
            <div className="tk-evet-hayir" role="radiogroup" aria-label="Müşteri evde miydi?">
              {[
                { d: true, e: 'Evet' },
                { d: false, e: 'Hayır' },
              ].map((x) => (
                <button
                  key={x.e}
                  type="button"
                  role="radio"
                  aria-checked={evde === x.d}
                  className={evde === x.d ? 'secili' : undefined}
                  onClick={() => setEvde(x.d)}
                >
                  {x.e}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset className={`tk-soru${evde === null ? ' soluk' : ''}`} disabled={evde === null}>
            <legend>Ne oldu?</legend>
            <div className="tk-sonuclar">
              {secenekler.map((s, i) => (
                <button
                  key={s.sonuc}
                  type="button"
                  className={`tk-sonuc ${s.renk}${sonuc === s.sonuc ? ' secili' : ''}${
                    i === secenekler.length - 1 && secenekler.length % 2 ? ' genis' : ''
                  }`}
                  aria-pressed={sonuc === s.sonuc}
                  onClick={() => setSonuc(s.sonuc)}
                >
                  <span className="yuvarlak" aria-hidden="true">
                    <s.Ikon boyut={20} />
                  </span>
                  <span className="metin">
                    <span className="ad">{s.etiket}</span>
                    <span className="aciklama">{s.aciklama}</span>
                  </span>
                </button>
              ))}
            </div>
          </fieldset>

          {sonuc === 'baska_gun' ? (
            <div className="tk-dilim-sec">
              <span className="etiket blok">Müşteri ne zaman istiyor?</span>
              <DilimSecici deger={dilim} degisti={(d) => setDilim(d ? { ...d, teyitli: true } : null)} teyitGoster={false} />
            </div>
          ) : null}

          {sonuc && sonuc !== 'cozuldu' ? (
            <label className="alan" style={{ marginTop: 14 }}>
              <span className="etiket">
                {sonuc === 'altyapi_sorunu' ? 'Ne gördünüz? (isteğe bağlı)' : 'Not (isteğe bağlı)'}
              </span>
              <textarea
                className="girdi"
                value={not}
                onChange={(o) => setNot(o.target.value)}
                maxLength={1000}
                placeholder={
                  sonuc === 'altyapi_sorunu' ? 'Sinyal yok, kutu arızalı…' : sonuc === 'malzeme' ? 'Hangi malzeme…' : ''
                }
              />
            </label>
          ) : null}
        </div>
        <div className="cekmece-ayak">
          {eksik ? (
            <p className="cekmece-ipucu orta" role="status">
              {eksik}
            </p>
          ) : null}
          <button className="dugme birincil" onClick={() => void kaydet()} disabled={Boolean(eksik) || kaydediliyor}>
            {kaydediliyor ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
          <button className="dugme sessiz" onClick={kapatmaIstegi} disabled={kaydediliyor}>
            Vazgeç
          </button>
        </div>
      </Cekmece>
      <CikisSorusu acik={cikisSor} kal={() => setCikisSor(false)} cik={() => { setCikisSor(false); kapat(); }} />
    </>
  );
}

function CikisSorusu({ acik, kal, cik }: { acik: boolean; kal: () => void; cik: () => void }) {
  return (
    <Cekmece acik={acik} kapat={kal} baslik="Kaydetmeden çıkılsın mı?" altBaslik="Seçtikleriniz silinecek.">
      <div style={{ display: 'grid', gap: 10 }}>
        <button className="dugme ikincil" onClick={kal}>
          Vazgeç, geri dön
        </button>
        <button className="dugme tehlike" onClick={cik}>
          Evet, çık
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ Evde yok ------------------------------ */

export function EvdeYokCekmecesi({
  acik,
  kapat,
  is,
  kaydedildi,
}: {
  acik: boolean;
  kapat: () => void;
  is: IsAyrinti;
  kaydedildi: () => void;
}) {
  const { goster } = useBildirim();
  const [onay, setOnay] = useState(false);
  const [not, setNot] = useState('');
  const [kaydediliyor, setKaydediliyor] = useState(false);

  useEffect(() => {
    if (!acik) {
      setOnay(false);
      setNot('');
    }
  }, [acik]);

  const kaydet = async () => {
    if (!onay || kaydediliyor) return;
    setKaydediliyor(true);
    try {
      const ek: Record<string, unknown> = { evde_miydi: false };
      if (not.trim()) ek.notu = not.trim();
      await durumDegistir(is, 'ulasilamadi', 'Evde yok', ek, 'Evde yok');
      titret();
      goster('Evde yok kaydedildi; operasyon müşteriyi arayacak', 'basari');
      kapat();
      kaydedildi();
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Kaydedilemedi.', 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <Cekmece
      acik={acik}
      kapat={() => !kaydediliyor && kapat()}
      baslik="Müşteri evde yok"
      altBaslik="İş operasyonun aranacaklar listesine düşer."
      kilitli={kaydediliyor}
    >
      <div className="cekmece-govde tk-cekmece">
        <label className="tk-onay-kutusu">
          <input type="checkbox" checked={onay} onChange={(o) => setOnay(o.target.checked)} />
          <span>10 dk bekledim, BOSS’tan 2 kez aradım, not bıraktım</span>
        </label>
        <label className="alan" style={{ marginTop: 14 }}>
          <span className="etiket">Not (isteğe bağlı)</span>
          <textarea
            className="girdi"
            value={not}
            onChange={(o) => setNot(o.target.value)}
            maxLength={1000}
            placeholder="Komşu akşam 18’de geleceğini söyledi…"
          />
        </label>
      </div>
      <div className="cekmece-ayak">
        {!onay ? (
          <p className="cekmece-ipucu orta" role="status">
            Göndermeden önce kutuyu işaretleyin
          </p>
        ) : null}
        <button className="dugme birincil" onClick={() => void kaydet()} disabled={!onay || kaydediliyor}>
          <Ev boyut={20} />
          {kaydediliyor ? 'Kaydediliyor…' : 'Evde yok olarak kaydet'}
        </button>
        <button className="dugme sessiz" onClick={kapat} disabled={kaydediliyor}>
          Vazgeç
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ Not ------------------------------ */

export function NotCekmecesi({ acik, kapat, is }: { acik: boolean; kapat: () => void; is: IsAyrinti }) {
  const { goster } = useBildirim();
  const [metin, setMetin] = useState('');
  const [kaydediliyor, setKaydediliyor] = useState(false);

  useEffect(() => {
    if (!acik) setMetin('');
  }, [acik]);

  const kaydet = async () => {
    if (!metin.trim() || kaydediliyor) return;
    setKaydediliyor(true);
    try {
      await notEkle(is, metin.trim());
      goster('Not eklendi', 'basari');
      kapat();
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Kaydedilemedi.', 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <Cekmece acik={acik} kapat={() => !kaydediliyor && kapat()} baslik="Not ekle" altBaslik="Operasyon bu notu işin geçmişinde görür.">
      <div className="cekmece-govde tk-cekmece">
        <label className="alan">
          <span className="etiket">Not</span>
          <textarea
            className="girdi"
            value={metin}
            onChange={(o) => setMetin(o.target.value)}
            maxLength={1000}
            autoFocus
            placeholder="Kapı kodu 1234, bahçe kapısından girilir…"
          />
        </label>
      </div>
      <div className="cekmece-ayak">
        <button className="dugme birincil" onClick={() => void kaydet()} disabled={!metin.trim() || kaydediliyor}>
          <Kalem boyut={20} />
          {kaydediliyor ? 'Kaydediliyor…' : 'Notu kaydet'}
        </button>
        <button className="dugme sessiz" onClick={kapat} disabled={kaydediliyor}>
          Vazgeç
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ Önce bu ------------------------------ */

const ONCE_NEDENLERI: Array<{ neden: 'yakindaydim' | 'musteri_aradi' | 'diger'; etiket: string }> = [
  { neden: 'yakindaydim', etiket: 'Yakındaydım' },
  { neden: 'musteri_aradi', etiket: 'Müşteri aradı' },
  { neden: 'diger', etiket: 'Diğer' },
];

export function OnceCekmecesi({ acik, kapat, is }: { acik: boolean; kapat: () => void; is: IsAyrinti }) {
  const { goster } = useBildirim();
  const sec = async (neden: 'yakindaydim' | 'musteri_aradi' | 'diger') => {
    try {
      await onceBunu(is, neden);
      goster('Sıra değişti: bu iş en başta', 'basari');
      kapat();
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Kaydedilemedi.', 'uyari');
    }
  };
  return (
    <Cekmece acik={acik} kapat={kapat} baslik="Önce bu işe mi gidiyorsunuz?" altBaslik="Nedenini seçin; sıra hemen değişir.">
      <div className="tk-cekmece" style={{ display: 'grid', gap: 10 }}>
        {ONCE_NEDENLERI.map((n) => (
          <button key={n.neden} className="dugme ikincil" onClick={() => void sec(n.neden)}>
            {n.etiket}
          </button>
        ))}
        <button className="dugme sessiz" onClick={kapat}>
          Vazgeç
        </button>
      </div>
    </Cekmece>
  );
}

/* ------------------------------ Başka gün (yola çıkmadan) ------------------------------ */

/** Müşteri aradı, başka gün istedi: iş listede kalır, yeni dilim teyitli yazılır (§3.3 geçiş 7). */
export function BaskaGunCekmecesi({ acik, kapat, is }: { acik: boolean; kapat: () => void; is: IsAyrinti }) {
  const { goster } = useBildirim();
  const [dilim, setDilim] = useState<Dilim | null>(null);
  const [kaydediliyor, setKaydediliyor] = useState(false);

  useEffect(() => {
    if (!acik) setDilim(null);
  }, [acik]);

  const kaydet = async () => {
    if (!dilim || kaydediliyor) return;
    setKaydediliyor(true);
    try {
      await durumDegistir(is, 'atandi', 'Başka gün', { randevu: { bas: dilim.bas, bit: dilim.bit } });
      goster('Yeni gün kaydedildi', 'basari');
      kapat();
    } catch (h) {
      goster(h instanceof Error ? h.message : 'Kaydedilemedi.', 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  return (
    <Cekmece acik={acik} kapat={() => !kaydediliyor && kapat()} baslik="Müşteri başka gün istedi" altBaslik="Müşteriyle konuştuğunuz günü ve saati seçin.">
      <div className="cekmece-govde tk-cekmece">
        <DilimSecici deger={dilim} degisti={(d) => setDilim(d ? { ...d, teyitli: true } : null)} teyitGoster={false} />
      </div>
      <div className="cekmece-ayak">
        {!dilim ? (
          <p className="cekmece-ipucu orta" role="status">
            Gün ve saat aralığı seçin
          </p>
        ) : null}
        <button className="dugme birincil" onClick={() => void kaydet()} disabled={!dilim || kaydediliyor}>
          <Takvim boyut={20} />
          {kaydediliyor ? 'Kaydediliyor…' : 'Yeni günü kaydet'}
        </button>
        <button className="dugme sessiz" onClick={kapat} disabled={kaydediliyor}>
          Vazgeç
        </button>
      </div>
    </Cekmece>
  );
}
