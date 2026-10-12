/**
 * Komut paleti — her yerden arama (Spotlight gibi).
 *
 * Açılış: Ctrl+F (tarayıcının "Bul" penceresinin yerine), Ctrl+K, ⌘F/⌘K ve —
 * bir yazı alanında değilken — "/". Konsolda kenar menüdeki arama alanı ve
 * telefondaki büyüteç de `paletiAc()` çağırır.
 *
 * Yazdıkça arar (≈120 ms bekler, eski isteği iptal eder); sonuçlar gruplu:
 * Binalar (Location ID, BN, site, adres) · Aboneler/işler (task no, müşteri no,
 * müşteri adı — izin varsa) · Kişiler · Mahalleler · Öbekler. Ne görüneceğine
 * SUNUCU karar verir (izin süzgeci); palet yalnız çizer.
 *
 * ↑↓ gezin · ↵ aç · ⌥↵ / ⇧↵ bina kartı · Tab tür süzgeci · Esc kapat.
 * Seçim yalnız ROTA ile gider (birim içe aktarılmaz):
 *   bina     → harita (satış: #/harita, konsol: Kapsama) uçar + vurgular;
 *              haritası olmayan görevde #/bina/<serial>
 *   iş       → #/yonetici/isler/is/<no> (teknikte #/islerim/<no>)
 *   kişi     → #/yonetici/ekip (yoksa iş.ata ile teknisyen süzgeçli işler)
 *   öbek     → #/yonetici/obekler/<id>
 * Telefonda tam ekran sayfa olarak açılır.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { git } from '../yol/rota';
import { TASKS_SUZ, tasksSuzYolu } from '../yol/tasks';
import { useOturum } from '../yerel/oturum';
import { useBildirim } from '../ortak/Bildirim';
import { katla } from '../ortak/ara';
import { haritaHedefiBirak } from '../harita/hedef';
import { Dugme, KapatDugmesi, Sekmeler } from '../ortak/Ilkel';
import { Buyutec } from '../ortak/Ikon';
import { Hap } from '../ortak/Rozet';
import { ara, type AramaGrubu, type AramaSonucu, type AramaTuru, type AramaYaniti } from './api';
import { sonAramaEkle, sonAramalar, sonAramalariSil, type SonArama } from './son';
import './arama.css';

const OLAY = 'turkcell:palet-ac';
const GECIKME_MS = 120;

/** Paleti aç (düğmeler, menüler). `ilk` verilirse kutu o metinle açılır. */
export function paletiAc(ilk?: string) {
  window.dispatchEvent(new CustomEvent(OLAY, { detail: ilk ?? '' }));
}

const TUR_ADI: Record<AramaTuru, string> = {
  bina: 'Binalar',
  is: 'Aboneler',
  kisi: 'Kişiler',
  mahalle: 'Mahalleler',
  obek: 'Öbekler',
};

function yaziAlaniMi(h: EventTarget | null): boolean {
  const e = h as HTMLElement | null;
  if (!e) return false;
  const ad = e.tagName;
  return ad === 'INPUT' || ad === 'TEXTAREA' || ad === 'SELECT' || e.isContentEditable;
}

export function AramaPaleti() {
  const { izinli, gorevler } = useOturum();
  const { goster } = useBildirim();
  const [acik, setAcik] = useState(false);
  const [metin, setMetin] = useState('');
  const [tur, setTur] = useState<AramaTuru | null>(null);
  const [yanit, setYanit] = useState<AramaYaniti | null>(null);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const [imlec, setImlec] = useState(0);
  const [son, setSon] = useState<SonArama[]>([]);
  const girdi = useRef<HTMLInputElement | null>(null);
  const liste = useRef<HTMLDivElement | null>(null);
  const oncekiOdak = useRef<HTMLElement | null>(null);

  /* Görevin görebileceği türler (çipler); asıl süzgeç sunucuda. */
  const turler = useMemo<AramaTuru[]>(() => {
    const t: AramaTuru[] = [];
    if (izinli('bina.oku')) t.push('bina');
    if (izinli('is.liste')) t.push('is');
    if (izinli('ekip.yonet', 'yetkinlik.yonet') || (izinli('ekip.teknikler') && izinli('is.ata'))) t.push('kisi');
    if (izinli('geometri.oku') && izinli('satis.kendi', 'satis.izle')) t.push('mahalle');
    if (izinli('obek.oku')) t.push('obek');
    return t;
  }, [izinli]);

  const ac = useCallback((ilk = '') => {
    oncekiOdak.current = document.activeElement as HTMLElement | null;
    setSon(sonAramalar());
    setAcik(true);
    if (ilk) setMetin(ilk);
    requestAnimationFrame(() => {
      girdi.current?.focus();
      girdi.current?.select();
    });
  }, []);

  const kapat = useCallback(() => {
    setAcik(false);
    setHata(null);
    // Odak, paleti açan yere döner (klavyeyle çalışan kaybolmasın).
    requestAnimationFrame(() => oncekiOdak.current?.focus?.());
  }, []);

  /* Kısayollar: her yerde (konsol ve telefon uygulaması). */
  useEffect(() => {
    const tus = (o: KeyboardEvent) => {
      const k = o.key.toLowerCase();
      const komut = (o.ctrlKey || o.metaKey) && !o.altKey && !o.shiftKey;
      if (komut && (k === 'f' || k === 'k')) {
        o.preventDefault(); // tarayıcının "Bul" penceresi açılmasın
        if (acik) {
          girdi.current?.focus();
          girdi.current?.select();
        } else ac();
        return;
      }
      if (!acik && o.key === '/' && !o.ctrlKey && !o.metaKey && !o.altKey && !yaziAlaniMi(o.target)) {
        o.preventDefault();
        ac();
      }
    };
    const dis = (o: Event) => ac(String((o as CustomEvent).detail ?? ''));
    window.addEventListener('keydown', tus, true);
    window.addEventListener(OLAY, dis);
    return () => {
      window.removeEventListener('keydown', tus, true);
      window.removeEventListener(OLAY, dis);
    };
  }, [acik, ac]);

  /* Adres değişince (seçim yapıldı ya da geri gidildi) palet kapanır. */
  useEffect(() => {
    if (!acik) return undefined;
    const kapa = () => setAcik(false);
    window.addEventListener('hashchange', kapa);
    return () => window.removeEventListener('hashchange', kapa);
  }, [acik]);

  /* Telefonda arka sayfa kaymasın. */
  useEffect(() => {
    if (!acik) return undefined;
    const eski = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = eski;
    };
  }, [acik]);

  /* Yazdıkça ara: 120 ms bekle, eski isteği iptal et. */
  useEffect(() => {
    if (!acik) return undefined;
    const q = metin.trim();
    if (katla(q).replace(/[^a-z0-9]/g, '').length < 2) {
      setYanit(null);
      setYukleniyor(false);
      setHata(null);
      return undefined;
    }
    const denetleyici = new AbortController();
    setYukleniyor(true);
    const zaman = setTimeout(() => {
      ara(q, tur, denetleyici.signal)
        .then((y) => {
          if (denetleyici.signal.aborted) return;
          setYanit(y);
          setHata(null);
          setImlec(0);
        })
        .catch((e: { kod?: string; message?: string }) => {
          if (denetleyici.signal.aborted) return;
          setHata(e?.kod === 'ag_yok' ? 'Bağlantı yok — arama sunucuda yapılır.' : e?.message || 'Arama yapılamadı.');
        })
        .finally(() => {
          if (!denetleyici.signal.aborted) setYukleniyor(false);
        });
    }, GECIKME_MS);
    return () => {
      clearTimeout(zaman);
      denetleyici.abort();
    };
  }, [metin, tur, acik]);

  /* Düz liste (klavye gezintisi için). */
  /* Sunucu süzer; yine de yalnız açılabilen türler gösterilir (Administrator
     önizlemesinde sunucu gerçek izinle döner — önizlenen izinle süz). */
  const gruplar = useMemo<AramaGrubu[]>(
    () => (yanit ? yanit.gruplar.filter((g) => turler.includes(g.tur) && g.sonuclar.length) : []),
    [yanit, turler],
  );
  const duz = useMemo<AramaSonucu[]>(() => gruplar.flatMap((g) => g.sonuclar), [gruplar]);
  const sonListe = !metin.trim() ? son : [];
  const satirSayisi = duz.length || sonListe.length;

  /* Etkin satır görünür kalsın. */
  useEffect(() => {
    liste.current?.querySelector<HTMLElement>(`[data-sira="${imlec}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [imlec]);

  /* ---------------- Seçim → rota ---------------- */

  const konsolda = () => window.location.hash.startsWith('#/yonetici');

  const haritayaGit = useCallback(
    (h: { serial?: string; loc?: string | null; lat?: number | null; lon?: number | null; etiket?: string; sorgu?: string }) => {
      const k = konsolda();
      const hedef = { ...h, loc: h.loc ?? undefined };
      if (k && izinli('satis.izle')) {
        haritaHedefiBirak(hedef);
        git('/yonetici/kapsama');
        return true;
      }
      if (izinli('satis.kendi')) {
        haritaHedefiBirak(hedef);
        git('/harita');
        return true;
      }
      if (izinli('satis.izle')) {
        haritaHedefiBirak(hedef);
        git('/yonetici/kapsama');
        return true;
      }
      return false;
    },
    [izinli],
  );

  const sec = useCallback(
    (s: AramaSonucu, kart = false) => {
      let acilmadi = false;
      switch (s.tur) {
        case 'bina': {
          const serial = String(s.serial ?? s.id);
          sonAramaEkle({ serial, baslik: s.baslik, loc: s.location_id, alt: s.alt, lat: s.lat, lon: s.lon });
          if (kart || !haritayaGit({ serial, loc: s.location_id, lat: s.lat, lon: s.lon, etiket: s.baslik })) {
            if (izinli('bina.oku')) git(`/bina/${encodeURIComponent(serial)}`);
            else acilmadi = true;
          }
          break;
        }
        case 'mahalle':
          if (!haritayaGit({ lat: s.lat, lon: s.lon, etiket: s.baslik })) acilmadi = true;
          break;
        case 'is': {
          const no = encodeURIComponent(String(s.is_no ?? s.id));
          if (izinli('is.ata', 'is.randevu')) git(`/yonetici/isler/is/${no}`);
          else if (gorevler.includes('teknik')) git(`/islerim/${no}`);
          else acilmadi = true;
          break;
        }
        case 'kisi':
          if (izinli('ekip.yonet', 'yetkinlik.yonet')) git('/yonetici/ekip');
          else if (izinli('is.ata')) git(tasksSuzYolu(TASKS_SUZ.teknik(String(s.id))));
          else acilmadi = true;
          break;
        case 'obek':
          if (izinli('obek.oku')) git(`/yonetici/obekler/${encodeURIComponent(String(s.id))}`);
          else acilmadi = true;
          break;
      }
      if (acilmadi) {
        goster('Bu sonuç bu görevle açılamıyor.', 'uyari');
        return;
      }
      setAcik(false);
      setMetin('');
      setYanit(null);
    },
    [haritayaGit, izinli, gorevler, goster],
  );

  const sonSec = (x: SonArama, kart = false) =>
    sec({ tur: 'bina', id: x.serial, serial: x.serial, baslik: x.baslik, alt: x.alt, location_id: x.loc, lat: x.lat, lon: x.lon }, kart);

  const tusBasildi = (o: React.KeyboardEvent) => {
    if (o.key === 'Escape') {
      o.preventDefault();
      if (metin) setMetin('');
      else kapat();
    } else if (o.key === 'ArrowDown' && satirSayisi) {
      o.preventDefault();
      setImlec((i) => (i + 1) % satirSayisi);
    } else if (o.key === 'ArrowUp' && satirSayisi) {
      o.preventDefault();
      setImlec((i) => (i - 1 + satirSayisi) % satirSayisi);
    } else if (o.key === 'Enter') {
      o.preventDefault();
      const kart = o.altKey || o.shiftKey;
      if (duz[imlec]) sec(duz[imlec], kart);
      else if (sonListe[imlec]) sonSec(sonListe[imlec], kart);
    } else if (o.key === 'Tab' && turler.length > 1) {
      o.preventDefault();
      const sira: Array<AramaTuru | null> = [null, ...turler];
      const i = sira.indexOf(tur);
      setTur(sira[(i + (o.shiftKey ? sira.length - 1 : 1)) % sira.length]);
    }
  };

  if (!acik) return null;

  let sira = -1;
  const satir = (s: AramaSonucu) => {
    sira += 1;
    const benim = sira;
    return (
      <SonucSatiri
        key={`${s.tur}-${s.id}`}
        s={s}
        sorgu={metin}
        etkin={benim === imlec}
        sira={benim}
        uzerinde={() => setImlec(benim)}
        sec={(kart) => sec(s, kart)}
        kartVar={s.tur === 'bina' && izinli('bina.oku')}
      />
    );
  };

  const yazildi = metin.trim().length > 0;

  return createPortal(
    <div className="ara-kap" role="presentation" onMouseDown={(o) => o.target === o.currentTarget && kapat()}>
      <div className="ara-panel" role="dialog" aria-modal="true" aria-label="Ara">
        <div className="ara-ust">
          <span className="ara-buyutec" aria-hidden="true">
            <Buyutec boyut={16} />
          </span>
          <input
            ref={girdi}
            className="ara-girdi"
            value={metin}
            onChange={(o) => setMetin(o.target.value)}
            onKeyDown={tusBasildi}
            placeholder={turler.includes('is') ? 'Location ID, bina, abone, task no, kişi…' : 'Location ID, BN, site ya da adres…'}
            aria-label="Ara"
            aria-controls="ara-sonuclar"
            aria-activedescendant={satirSayisi ? `ara-satir-${imlec}` : undefined}
            role="combobox"
            aria-expanded={satirSayisi > 0}
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            inputMode="search"
          />
          {yazildi ? (
            <KapatDugmesi
              kucuk
              etiket="Temizle"
              kapat={() => {
                setMetin('');
                girdi.current?.focus();
              }}
            />
          ) : null}
          <Dugme tur="metin" className="ara-vazgec" onClick={kapat}>
            Vazgeç
          </Dugme>
        </div>

        {turler.length > 1 ? (
          <Sekmeler
            className="ara-sekmeler"
            etiket="Ne aranıyor"
            sekmeler={[{ deger: 'hepsi' as const, etiket: 'Tümü' }, ...turler.map((t) => ({ deger: t, etiket: TUR_ADI[t] }))]}
            deger={tur ?? 'hepsi'}
            degisti={(t) => {
              setTur(t === 'hepsi' ? null : t);
              girdi.current?.focus();
            }}
          />
        ) : null}

        <div className="ara-govde" id="ara-sonuclar" ref={liste} role="listbox" aria-label="Sonuçlar">
          {!yazildi ? (
            sonListe.length ? (
              <section className="ara-grup">
                <header>
                  <span>Son bakılan binalar</span>
                  <button
                    type="button"
                    className="ara-grup-eylem"
                    onClick={() => {
                      sonAramalariSil();
                      setSon([]);
                    }}
                  >
                    Temizle
                  </button>
                </header>
                {sonListe.map((x, i) => (
                  <SonucSatiri
                    key={x.serial}
                    s={{ tur: 'bina', id: x.serial, serial: x.serial, baslik: x.baslik, alt: x.alt, location_id: x.loc }}
                    sorgu=""
                    etkin={i === imlec}
                    sira={i}
                    uzerinde={() => setImlec(i)}
                    sec={(kart) => sonSec(x, kart)}
                    kartVar={izinli('bina.oku')}
                    gecmis
                  />
                ))}
              </section>
            ) : (
              <Ipucu turler={turler} />
            )
          ) : hata ? (
            <div className="ara-bos hata">{hata}</div>
          ) : yanit && gruplar.length ? (
            gruplar.map((g) => (
              <Grup key={g.tur} g={g} tumunuGor={!tur && g.toplam > g.sonuclar.length ? () => setTur(g.tur) : undefined}>
                {g.sonuclar.map(satir)}
              </Grup>
            ))
          ) : yanit && !yukleniyor ? (
            <div className="ara-bos">“{metin.trim()}” için sonuç yok</div>
          ) : metin.trim().length < 2 ? (
            <div className="ara-bos">En az iki harf ya da rakam yazın.</div>
          ) : (
            <div className="ara-iskelet" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          )}
        </div>

        <footer className="ara-alt" aria-hidden="true">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> gezin
          </span>
          <span>
            <kbd>↵</kbd> aç
          </span>
          {izinli('bina.oku') ? (
            <span>
              <kbd>⇧</kbd>
              <kbd>↵</kbd> bina kartı
            </span>
          ) : null}
          {turler.length > 1 ? (
            <span>
              <kbd>Tab</kbd> tür
            </span>
          ) : null}
          <span className="sag">
            {yanit && yazildi
              ? `${yanit.toplam.toLocaleString('tr-TR')} sonuç · ${Math.max(1, Math.round(yanit.sure_ms))} ms`
              : 'Ctrl F · Ctrl K · /'}
          </span>
        </footer>
      </div>
    </div>,
    document.body,
  );
}

/* ------------------------------ Parçalar ------------------------------ */

function Grup({ g, tumunuGor, children }: { g: AramaGrubu; tumunuGor?: () => void; children: ReactNode }) {
  return (
    <section className="ara-grup">
      <header>
        <span>{g.baslik}</span>
        <span className="sayi">{g.toplam.toLocaleString('tr-TR')}</span>
        {tumunuGor ? (
          <button type="button" className="ara-grup-eylem" onClick={tumunuGor}>
            Tümünü gör
          </button>
        ) : null}
      </header>
      {children}
    </section>
  );
}

function SonucSatiri({
  s,
  sorgu,
  etkin,
  sira,
  uzerinde,
  sec,
  kartVar,
  gecmis = false,
}: {
  s: AramaSonucu;
  sorgu: string;
  etkin: boolean;
  sira: number;
  uzerinde: () => void;
  sec: (kart: boolean) => void;
  kartVar: boolean;
  gecmis?: boolean;
}) {
  const kimlik =
    s.tur === 'bina'
      ? s.location_id
        ? `LOC ${s.location_id}`
        : s.serial
      : s.tur === 'is'
        ? s.task_no || s.is_no
        : null;
  return (
    <div
      id={`ara-satir-${sira}`}
      data-sira={sira}
      role="option"
      aria-selected={etkin}
      className={`ara-satir${etkin ? ' etkin' : ''}${s.pasif || s.aktif === false || s.acik === false ? ' soluk' : ''}`}
      onMouseMove={etkin ? undefined : uzerinde}
      onClick={(o) => sec(o.altKey || o.shiftKey)}
    >
      <span className="ara-simge" aria-hidden="true">
        <TurSimgesi tur={s.tur} gecmis={gecmis} />
      </span>
      <span className="ara-metin">
        <span className="baslik">
          <Vurgu metin={s.baslik} sorgu={sorgu} />
        </span>
        {s.tur === 'is' && s.durum ? <Hap renk={s.acik ? 'yesil' : 'gri'}>{s.acik ? 'açık' : 'kapalı'}</Hap> : null}
        {s.pasif ? <Hap>pasif</Hap> : null}
        {s.alt ? (
          <span className="alt">
            <Vurgu metin={s.alt} sorgu={sorgu} />
          </span>
        ) : null}
      </span>
      {kimlik ? (
        <span className="ara-kimlik">
          <Vurgu metin={String(kimlik)} sorgu={sorgu} />
        </span>
      ) : null}
      {kartVar ? (
        <Dugme
          tur="metin"
          boy="kucuk"
          className="ara-kart"
          tabIndex={-1}
          onClick={(o) => {
            o.stopPropagation();
            sec(true);
          }}
        >
          Kart
        </Dugme>
      ) : null}
      <span className="ara-enter" aria-hidden="true">
        ↵
      </span>
    </div>
  );
}

/** Eşleşen parçayı kalın yazar (Türkçe harf duyarsız; uzunluk değişirse vurgusuz). */
function Vurgu({ metin, sorgu }: { metin: string; sorgu: string }) {
  const q = katla(sorgu).trim();
  if (!q || q.length < 2) return <>{metin}</>;
  const k = katla(metin);
  if (k.length !== metin.length) return <>{metin}</>;
  const i = k.indexOf(q);
  if (i < 0) return <>{metin}</>;
  return (
    <>
      {metin.slice(0, i)}
      <mark>{metin.slice(i, i + q.length)}</mark>
      {metin.slice(i + q.length)}
    </>
  );
}

function Ipucu({ turler }: { turler: AramaTuru[] }) {
  const neler = ['Location ID', 'bina adı'];
  if (turler.includes('is')) neler.push('task no');
  if (turler.includes('kisi')) neler.push('kişi adı');
  return <div className="ara-bos">{neler.join(', ')} yazın.</div>;
}

function TurSimgesi({ tur, gecmis }: { tur: AramaTuru; gecmis?: boolean }) {
  const ortak = { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  if (gecmis)
    return (
      <svg {...ortak}>
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v4l2.5 2" />
      </svg>
    );
  switch (tur) {
    case 'bina':
      return (
        <svg {...ortak}>
          <path d="M5 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M15 10h3a1 1 0 0 1 1 1v10M3 21h18M8.5 8h3M8.5 12h3M8.5 16h3" />
        </svg>
      );
    case 'is':
      return (
        <svg {...ortak}>
          <circle cx="12" cy="8" r="3.5" />
          <path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" />
        </svg>
      );
    case 'kisi':
      return (
        <svg {...ortak}>
          <circle cx="9" cy="8.5" r="3" />
          <path d="M3.5 19c.6-3 2.8-4.6 5.5-4.6s4.9 1.6 5.5 4.6M16 5.5a3 3 0 0 1 0 6M18 14.6c1.5.6 2.5 2 2.8 4.4" />
        </svg>
      );
    case 'mahalle':
      return (
        <svg {...ortak}>
          <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z" />
          <circle cx="12" cy="10" r="2.3" />
        </svg>
      );
    default:
      return (
        <svg {...ortak}>
          <circle cx="8" cy="9" r="3.2" />
          <circle cx="16" cy="9" r="3.2" />
          <circle cx="12" cy="16" r="3.2" />
        </svg>
      );
  }
}
