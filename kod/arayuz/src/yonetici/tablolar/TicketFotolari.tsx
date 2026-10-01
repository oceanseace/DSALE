/**
 * Ticket fotoğrafları (EK-8) — ticket çekmecesindeki "Fotoğraflar" yeri.
 *
 * `ekran/ticket/TicketAyrinti.tsx` bu dosyayı `import.meta.glob` ile kendiliğinden bağlar:
 * `TicketFotolari({ ticketId })`. PS26 `imgs/<no>.zip` arşivlerinden gelenler ve sonradan
 * eklenenler burada küçük resim ızgarası olarak görünür; dokununca tam ekran açılır.
 *
 * Ekleme: "Fotoğraf ekle" (telefonda kamera ya da galeri — tarayıcı kendisi sorar), masaüstünde
 * sürükle-bırak. Yalnız JPEG/PNG, dosya başına 10 MB; sınırı aşan dosya gönderilmeden söylenir.
 * Aynı fotoğraf ikinci kez eklenmez (sunucu içerikten tanır). Görme yetkisi sunucudadır: ticket'ı
 * görebilen görür; ekleme düğmesi yalnız yükleyebilene çıkar.
 */

import { useCallback, useEffect, useRef, useState, type DragEvent } from 'react';
import { createPortal } from 'react-dom';
import { SahaHatasi } from '../../api/istemci';
import { useBildirim } from '../../ortak/Bildirim';
import { tarihSaat } from '../../ortak/bicim';
import { ekListesi, ekYukle, resimAdresi, type EkListesi, type TicketEki } from './api';
import './tablolar.css';

const KABUL = ['image/jpeg', 'image/png'];

function boyutMetni(bayt: number): string {
  if (bayt < 1024 * 1024) return `${Math.max(1, Math.round(bayt / 1024)).toLocaleString('tr-TR')} KB`;
  return `${(bayt / 1024 / 1024).toLocaleString('tr-TR', { maximumFractionDigits: 1 })} MB`;
}

/** Jetonla alınan resmin geçici adresi; bileşen kalkınca bırakılır. */
function useResim(yol: string | null): { adres: string | null; hata: boolean } {
  const [adres, setAdres] = useState<string | null>(null);
  const [hata, setHata] = useState(false);
  useEffect(() => {
    if (!yol) return;
    const denetleyici = new AbortController();
    let olusan: string | null = null;
    setAdres(null);
    setHata(false);
    resimAdresi(yol, denetleyici.signal)
      .then((a) => {
        olusan = a;
        setAdres(a);
      })
      .catch(() => {
        if (!denetleyici.signal.aborted) setHata(true);
      });
    return () => {
      denetleyici.abort();
      if (olusan) URL.revokeObjectURL(olusan);
    };
  }, [yol]);
  return { adres, hata };
}

export function TicketFotolari({ ticketId }: { ticketId: number }) {
  const { goster } = useBildirim();
  const [veri, setVeri] = useState<EkListesi | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [gonderilen, setGonderilen] = useState(0);
  const [surukleniyor, setSurukleniyor] = useState(false);
  const [acik, setAcik] = useState<number | null>(null);
  const girdi = useRef<HTMLInputElement>(null);

  const getir = useCallback(async () => {
    try {
      setVeri(await ekListesi(ticketId));
      setHata(null);
    } catch (h) {
      setHata(h instanceof SahaHatasi ? h.message : 'Fotoğraflar alınamadı.');
    }
  }, [ticketId]);

  useEffect(() => {
    setVeri(null);
    setAcik(null);
    void getir();
  }, [getir]);

  const yukle = async (dosyalar: File[]) => {
    if (!veri?.yukleyebilir || !dosyalar.length) return;
    const sinir = veri.en_buyuk_bayt;
    const uygun: File[] = [];
    for (const d of dosyalar) {
      if (d.type && !KABUL.includes(d.type)) {
        goster(`${d.name}: yalnız fotoğraf eklenebilir (JPEG ya da PNG).`, 'uyari');
      } else if (d.size > sinir) {
        goster(`${d.name}: ${boyutMetni(d.size)} — en çok ${boyutMetni(sinir)} olabilir.`, 'uyari');
      } else {
        uygun.push(d);
      }
    }
    if (!uygun.length) return;
    setGonderilen(uygun.length);
    let eklenen = 0;
    let zatenVar = 0;
    for (const d of uygun) {
      try {
        const y = await ekYukle(ticketId, d);
        if (y.zaten_vardi) zatenVar += 1;
        else eklenen += 1;
      } catch (h) {
        goster(`${d.name}: ${h instanceof SahaHatasi ? h.message : 'eklenemedi.'}`, 'uyari');
      }
      setGonderilen((n) => n - 1);
    }
    await getir();
    if (eklenen) goster(eklenen === 1 ? 'Fotoğraf eklendi.' : `${eklenen} fotoğraf eklendi.`, 'basari');
    else if (zatenVar) goster('Bu fotoğraf zaten ekliydi.', 'bilgi');
  };

  const birak = (o: DragEvent<HTMLDivElement>) => {
    o.preventDefault();
    setSurukleniyor(false);
    void yukle(Array.from(o.dataTransfer.files ?? []));
  };

  const ekler = veri?.ekler ?? [];
  return (
    <div
      className={`tf${surukleniyor ? ' surukleniyor' : ''}`}
      onDragOver={(o) => {
        if (!veri?.yukleyebilir) return;
        o.preventDefault();
        setSurukleniyor(true);
      }}
      onDragLeave={() => setSurukleniyor(false)}
      onDrop={veri?.yukleyebilir ? birak : undefined}
    >
      {hata ? (
        <div className="tf-bos">
          <span>{hata}</span>
          <button type="button" className="yd" onClick={() => void getir()}>
            Tekrar dene
          </button>
        </div>
      ) : !veri ? (
        <div className="tf-izgara" aria-hidden="true">
          <span className="tf-iskelet" />
          <span className="tf-iskelet" />
          <span className="tf-iskelet" />
        </div>
      ) : (
        <>
          {ekler.length ? (
            <div className="tf-izgara" role="list" aria-label="Ticket fotoğrafları">
              {ekler.map((e, i) => (
                <KucukResim key={e.id} ek={e} ac={() => setAcik(i)} />
              ))}
            </div>
          ) : (
            <p className="tf-bos-metin">
              {veri.yukleyebilir ? 'Henüz fotoğraf yok. Sürükleyip bırakın ya da ekleyin.' : 'Fotoğraf yok.'}
            </p>
          )}
          {veri.yukleyebilir ? (
            <div className="tf-alt">
              <button
                type="button"
                className="yd"
                onClick={() => girdi.current?.click()}
                disabled={gonderilen > 0}
              >
                {gonderilen > 0 ? `Gönderiliyor… (${gonderilen})` : 'Fotoğraf ekle'}
              </button>
              <span className="tf-ipucu">JPEG ya da PNG · en çok {boyutMetni(veri.en_buyuk_bayt)}</span>
              <input
                ref={girdi}
                type="file"
                accept={KABUL.join(',')}
                multiple
                hidden
                onChange={(o) => {
                  void yukle(Array.from(o.target.files ?? []));
                  o.target.value = '';
                }}
              />
            </div>
          ) : null}
        </>
      )}
      {acik !== null && ekler[acik] ? (
        <ResimGosterici ekler={ekler} sira={acik} degistir={setAcik} kapat={() => setAcik(null)} />
      ) : null}
    </div>
  );
}

function KucukResim({ ek, ac }: { ek: TicketEki; ac: () => void }) {
  const { adres, hata } = useResim(ek.kucuk);
  return (
    <button type="button" role="listitem" className="tf-kucuk" onClick={ac} title={`${ek.dosya_adi} · ${boyutMetni(ek.boyut)}`}>
      {adres ? <img src={adres} alt={ek.dosya_adi} /> : <span className={hata ? 'tf-kirik' : 'tf-iskelet'}>{hata ? '!' : ''}</span>}
    </button>
  );
}

/** Tam ekran gösterici: ok tuşları / ‹ › ile gezinir, Esc kapatır, "İndir" asıl dosyayı verir. */
function ResimGosterici({
  ekler,
  sira,
  degistir,
  kapat,
}: {
  ekler: TicketEki[];
  sira: number;
  degistir: (n: number) => void;
  kapat: () => void;
}) {
  const ek = ekler[sira];
  const { adres, hata } = useResim(ek.tam);
  const kutu = useRef<HTMLDivElement>(null);
  const oncekiVar = sira > 0;
  const sonrakiVar = sira < ekler.length - 1;

  useEffect(() => {
    const tus = (o: KeyboardEvent) => {
      if (o.key === 'Escape') {
        o.stopPropagation();
        kapat();
      } else if (o.key === 'ArrowLeft' && oncekiVar) degistir(sira - 1);
      else if (o.key === 'ArrowRight' && sonrakiVar) degistir(sira + 1);
    };
    // Yakalama evresinde: çekmecenin kendi Esc dinleyicisi çekmeceyi kapatmasın, yalnız gösterici kapansın.
    window.addEventListener('keydown', tus, true);
    return () => window.removeEventListener('keydown', tus, true);
  }, [sira, oncekiVar, sonrakiVar, degistir, kapat]);

  useEffect(() => {
    const onceki = document.activeElement as HTMLElement | null;
    kutu.current?.focus({ preventScroll: true });
    return () => onceki?.focus?.({ preventScroll: true });
  }, []);

  return createPortal(
    <div ref={kutu} className="tf-gosterici" role="dialog" aria-modal="true" aria-label="Fotoğraf" tabIndex={-1} onClick={kapat}>
      <div className="tf-g-ust" onClick={(o) => o.stopPropagation()}>
        <span className="tf-g-ad">
          {ek.dosya_adi}
          <small>
            {sira + 1} / {ekler.length} · {tarihSaat(ek.olusturma)} · {boyutMetni(ek.boyut)}
          </small>
        </span>
        {adres ? (
          <a className="tf-g-dugme" href={adres} download={ek.dosya_adi}>
            İndir
          </a>
        ) : null}
        <button type="button" className="tf-g-dugme kapat" onClick={kapat} aria-label="Kapat">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
          </svg>
        </button>
      </div>
      <div className="tf-g-resim">
        {adres ? (
          <img src={adres} alt={ek.dosya_adi} onClick={(o) => o.stopPropagation()} />
        ) : (
          <span className="tf-g-bekle">{hata ? 'Fotoğraf açılamadı.' : 'Yükleniyor…'}</span>
        )}
      </div>
      {oncekiVar ? (
        <button
          type="button"
          className="tf-g-ok sol"
          aria-label="Önceki fotoğraf"
          onClick={(o) => {
            o.stopPropagation();
            degistir(sira - 1);
          }}
        >
          ‹
        </button>
      ) : null}
      {sonrakiVar ? (
        <button
          type="button"
          className="tf-g-ok sag"
          aria-label="Sonraki fotoğraf"
          onClick={(o) => {
            o.stopPropagation();
            degistir(sira + 1);
          }}
        >
          ›
        </button>
      ) : null}
    </div>,
    document.body,
  );
}
