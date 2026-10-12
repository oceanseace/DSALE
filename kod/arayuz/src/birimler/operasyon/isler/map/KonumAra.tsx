/**
 * MAP arama kutusu: Task No, müşteri no, ad, Location ID, BN/bina/site adı. Yazarken sonuçlar listelenir
 * (İşler · Binalar); Enter ya da tıklama sonucu seçer, çağıran kamerayı uçurur ve vurgular. Birden çok
 * sonuç varsa liste açık kalır; seçilenin kartı kutunun altında durur, yeni yazınca kalkar.
 * Esc önce listeyi, sonra aramayı kapatır.
 * Giriş: <KonumAra>. Çağıran: IsHaritasiEkrani. Arama motoru map/konumArama.ts, kart map/SecimKarti.tsx.
 */

import { useEffect, useRef, useState } from 'react';
import type { IsSatir } from '../../../../cekirdek/is/tipler';
import { Kapat } from '../../../../cekirdek/ortak/Ikon';
import { useKonumArama, type Bulunan, type BulunanIs } from './konumArama';
import { SecimKarti } from './SecimKarti';

export function KonumAra({
  isler,
  harita,
  secim,
  sec,
  temizle,
  isiAc,
  gizliMi,
}: {
  /** Yüklü açık işler (anında arama ve bina kartı). */
  isler: readonly IsSatir[];
  harita: ReadonlyMap<string, IsSatir>;
  secim: Bulunan | null;
  sec: (b: Bulunan) => void;
  temizle: () => void;
  isiAc: (isNo: string) => void;
  /** Yüklü iş şu an haritada görünmüyor mu (tarih/tür süzgeci ya da lejantta kapalı renk). */
  gizliMi: (isNo: string) => boolean;
}) {
  const [metin, setMetin] = useState('');
  const [listeAcik, setListeAcik] = useState(false);
  const [imlec, setImlec] = useState(0);
  const [enterBekliyor, setEnterBekliyor] = useState(false);
  const [uyari, setUyari] = useState<string | null>(null);
  const girdi = useRef<HTMLInputElement | null>(null);
  const sonuc = useKonumArama(metin, isler, harita);
  const sirali: Bulunan[] = sonuc.binaOnce ? [...sonuc.binalar, ...sonuc.isler] : [...sonuc.isler, ...sonuc.binalar];
  const yeterli = metin.trim().length >= 2;

  useEffect(() => {
    setImlec(0);
    setUyari(null);
  }, [metin]);

  const sec_ = (b: Bulunan) => {
    sec(b);
    setUyari(null);
    if (sirali.length <= 1) setListeAcik(false);
  };

  const bulunamadi = () => setUyari(`“${metin.trim()}” bulunamadı. Task No, müşteri no, Location ID ya da bina adını kontrol edin.`);

  /* Enter sunucu yanıtından önce basıldıysa: yanıt gelince ilk sonuca git. */
  useEffect(() => {
    if (!enterBekliyor || sonuc.bekliyor) return;
    setEnterBekliyor(false);
    if (sirali[0]) sec_(sirali[0]);
    else bulunamadi();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enterBekliyor, sonuc.bekliyor]);

  const gonder = () => {
    if (!yeterli) return;
    setListeAcik(true);
    const elle = imlec > 0 ? sirali[imlec] : undefined;
    if (elle) sec_(elle);
    else if (sonuc.bekliyor && !sonuc.kesin) setEnterBekliyor(true);
    else if (sirali[0]) sec_(sirali[0]);
    else bulunamadi();
  };

  const hepsiniTemizle = () => {
    setMetin('');
    setListeAcik(false);
    setEnterBekliyor(false);
    temizle();
  };

  const rozet = (b: BulunanIs): string | null => {
    if (!b.konum) return 'Konumu yok';
    if (!b.acik) return 'Kapalı';
    if (!b.yuklu) return null;
    return gizliMi(b.isNo) ? 'Süzgeçte gizli' : 'Haritada';
  };

  /* Bölümler `sirali` ile aynı sırada; `bas` bölümün ilk öğesinin `sirali` içindeki yeri (klavye imleci). */
  const isBolumu = { baslik: 'İşler', ogeler: sonuc.isler as Bulunan[] };
  const binaBolumu = { baslik: 'Binalar', ogeler: sonuc.binalar as Bulunan[] };
  const bolumler = (sonuc.binaOnce ? [binaBolumu, isBolumu] : [isBolumu, binaBolumu]).map((b, i, l) => ({
    ...b,
    bas: i === 0 ? 0 : l[0].ogeler.length,
  }));

  const listeGorunur = listeAcik && yeterli;

  return (
    <div className={`mp-ara${uyari ? ' uyarili' : ''}`}>
      <form
        className="hr-locgit-kutu mp-ara-kutu"
        role="search"
        onSubmit={(o) => {
          o.preventDefault();
          gonder();
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="hr-locgit-simge">
          <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2.2" />
          <path d="M20 20l-3.6-3.6" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
        <input
          ref={girdi}
          value={metin}
          onChange={(o) => {
            setMetin(o.target.value);
            setListeAcik(true);
            if (secim) temizle(); // yeni arama: eski iğne ve kart kalkar
          }}
          onFocus={() => yeterli && setListeAcik(true)}
          onKeyDown={(o) => {
            if (o.key === 'ArrowDown' && sirali.length) {
              o.preventDefault();
              setListeAcik(true);
              setImlec((i) => (i + 1) % sirali.length);
            } else if (o.key === 'ArrowUp' && sirali.length) {
              o.preventDefault();
              setListeAcik(true);
              setImlec((i) => (i - 1 + sirali.length) % sirali.length);
            } else if (o.key === 'Escape') {
              o.preventDefault();
              if (listeGorunur) setListeAcik(false);
              else hepsiniTemizle();
            }
          }}
          placeholder="Task No, müşteri no, ad, Location ID, bina…"
          aria-label="Haritada ara: Task No, müşteri no, müşteri adı, Location ID, BN ya da bina/site adı"
          inputMode="search"
          enterKeyHint="search"
          autoComplete="off"
          spellCheck={false}
          data-palet-disi="1"
        />
        {enterBekliyor ? <span className="hr-donen" aria-label="Aranıyor" /> : null}
        {metin ? (
          <button
            type="button"
            className="hr-locgit-sil"
            aria-label="Aramayı temizle"
            onMouseDown={(o) => o.preventDefault()}
            onClick={() => {
              hepsiniTemizle();
              girdi.current?.focus();
            }}
          >
            <Kapat boyut={14} kalinlik={2} />
          </button>
        ) : null}
      </form>

      {uyari ? (
        <div className="hr-locgit-uyari" role="status">
          {uyari}
        </div>
      ) : null}

      {secim ? <SecimKarti secim={secim} isler={isler} isiAc={isiAc} gizliMi={gizliMi} kapat={temizle} /> : null}

      {listeGorunur ? (
        <div className="mp-sonuc">
          <div className="mp-sonuc-ust">
            <span>
              {sirali.length
                ? `${sirali.length.toLocaleString('tr-TR')} sonuç`
                : sonuc.bekliyor
                  ? 'Aranıyor…'
                  : 'Sonuç yok'}
              {sirali.length && sonuc.bekliyor ? ' · sunucuda aranıyor…' : ''}
            </span>
            <button type="button" className="mp-gizle" onClick={() => setListeAcik(false)}>
              Listeyi gizle
            </button>
          </div>
          {sonuc.uyari ? <div className="mp-sonuc-not">{sonuc.uyari}</div> : null}
          {bolumler.filter((b) => b.ogeler.length).map((b) => (
            <section key={b.baslik} aria-label={b.baslik}>
              <h3>
                {b.baslik} <b>{b.ogeler.length.toLocaleString('tr-TR')}</b>
              </h3>
              <ul role="listbox" aria-label={b.baslik}>
                {b.ogeler.map((o, i) => {
                  const benim = b.bas + i;
                  const etkin = benim === imlec;
                  const secili = secim?.anahtar === o.anahtar;
                  const r = o.tur === 'is' ? rozet(o) : null;
                  return (
                    <li key={o.anahtar} role="option" aria-selected={secili}>
                      <button
                        type="button"
                        className={`${etkin ? 'etkin' : ''}${secili ? ' secili' : ''}`}
                        onMouseEnter={() => setImlec(benim)}
                        onClick={() => sec_(o)}
                      >
                        <span className="mp-oge-ust">
                          <span className="mp-oge-ad">{o.tur === 'is' ? o.baslik : o.ad}</span>
                          {o.tur === 'bina' ? (
                            <span className="mp-oge-loc">{o.loc ? `LOC ${o.loc}` : `BN ${o.serial}`}</span>
                          ) : r ? (
                            <span className={`mp-oge-rozet${r === 'Haritada' ? ' var' : ''}`}>{r}</span>
                          ) : null}
                        </span>
                        {o.alt ? <span className="mp-oge-alt">{o.alt}</span> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      ) : secim && sirali.length > 1 ? (
        <button type="button" className="mp-diger" onClick={() => setListeAcik(true)}>
          Diğer sonuçlar ({(sirali.length - 1).toLocaleString('tr-TR')})
        </button>
      ) : null}
    </div>
  );
}
