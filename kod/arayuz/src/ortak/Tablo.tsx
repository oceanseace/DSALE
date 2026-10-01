/**
 * Tablo (EK-9) — "insanlar Excel dışında bir şey kullanmak istemiyor".
 *
 * Bildik Excel alışkanlıkları, tek bileşende:
 *   · tek "Ara…" kutusu (bütün sütunlarda, Türkçe harf duyarsız: "gursu" → Gürsu)
 *   · başlığa tıkla → sırala (artan → azalan → kapalı); ▾ → sütun süzgeci (değer listesi)
 *   · dondurulmuş başlık, ince ızgara çizgileri, sağa yaslı sayılar, Türkçe biçim
 *   · klavye: ok tuşları hücre gezer, Shift+ok seçimi büyütür, Ctrl+A hepsi,
 *     Enter = aç, Esc = seçimi bırak; fareyle sürükleyerek seçim
 *   · Ctrl+C → sekme ayrımlı kopya: Excel'e yapıştırınca sütunlar yerine oturur
 *   · altta Excel'in durum çubuğu gibi: satır sayısı, seçili hücre, sayıların TOPLAMI
 *   · "Excel'e indir": süzülmüş ve sıralı hâliyle gerçek .xlsx
 *   · sanal kaydırma: yalnız görünen satırlar çizilir (20.000 satır akıcı)
 *   · telefonda (< 768 px) satırlar kart olur; arama aynı kalır
 *
 * Kişisel veri süzmesi SUNUCUDADIR; tablo yalnız kendisine verileni gösterir.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as TusOlayi,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import { katla, eslesir } from './ara';
import { dosyaIndir, tarihliAd, xlsxOlustur, type Hucre } from './xlsx';
import { yerelJsonOku, yerelJsonYaz } from './yerel';
import './bilesen.css';

export interface TabloSutunu<T> {
  anahtar: string;
  baslik: string;
  /** Ham değer: sıralama, süzgeç, arama, kopya ve Excel bunu kullanır. */
  deger: (satir: T) => Hucre;
  /** Hücrede gösterilecek (rozet, renkli hap…). Verilmezse ham değer biçimlenir. */
  goster?: (satir: T) => ReactNode;
  /** Sayı sütunu: sağa yaslı, tabular rakam, toplamlanır. */
  sayi?: boolean;
  /** px; verilmezse 160 (sayıda 96). */
  genislik?: number;
  /** Sütun süzgeci (değer listesi) açık mı. Varsayılan: sayı değilse açık. */
  suzgec?: boolean;
  /** Telefondaki kartta: 'baslik' (kalın ilk satır), 'alt' (ikinci satır), 'gizli'. Varsayılan: etiket: değer satırı. */
  kartta?: 'baslik' | 'alt' | 'gizli';
}

type Siralama = { anahtar: string; yon: 1 | -1 } | null;
interface Nokta {
  r: number;
  c: number;
}

const SATIR_Y = 36;
const TAMPON = 12;

function hucreMetni(d: Hucre): string {
  if (d === null || d === undefined) return '';
  if (typeof d === 'number') return Number.isFinite(d) ? d.toLocaleString('tr-TR', { maximumFractionDigits: 2 }) : '';
  if (typeof d === 'boolean') return d ? 'Evet' : 'Hayır';
  if (d instanceof Date) return d.toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' });
  return String(d);
}

/** Kopyada sayı: binlik ayraçsız, virgüllü ondalık (Türkçe Excel doğru okusun). */
function kopyaMetni(d: Hucre): string {
  if (typeof d === 'number') return Number.isFinite(d) ? String(d).replace('.', ',') : '';
  return hucreMetni(d).replace(/[\t\r\n]+/g, ' ');
}

function karsilastir(a: Hucre, b: Hucre): number {
  const bosA = a === null || a === undefined || a === '';
  const bosB = b === null || b === undefined || b === '';
  if (bosA || bosB) return bosA === bosB ? 0 : bosA ? 1 : -1; // boşlar hep sonda
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (a instanceof Date && b instanceof Date) return a.getTime() - b.getTime();
  return String(a).localeCompare(String(b), 'tr', { numeric: true, sensitivity: 'base' });
}

function useDarEkran(): boolean {
  const sorgu = '(max-width: 767px)';
  const [dar, setDar] = useState(() => {
    try {
      return window.matchMedia(sorgu).matches;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    let mq: MediaQueryList;
    try {
      mq = window.matchMedia(sorgu);
    } catch {
      return;
    }
    const d = () => setDar(mq.matches);
    mq.addEventListener('change', d);
    return () => mq.removeEventListener('change', d);
  }, []);
  return dar;
}

export function Tablo<T>({
  satirlar,
  sutunlar,
  anahtar,
  onAc,
  seciliAnahtar,
  aramaYerTutucu = 'Ara…',
  excelAdi,
  bosMetin = 'Bu aramayla eşleşen satır yok.',
  yukseklik,
  arac,
  kayitAnahtari,
  aramaBaslangic = '',
}: {
  satirlar: T[];
  sutunlar: Array<TabloSutunu<T>>;
  anahtar: (satir: T) => string | number;
  /** Enter ya da çift tıklama / telefonda karta dokunma. */
  onAc?: (satir: T) => void;
  /** Dışarıda açık olan satır (çekmecede gösterilen) vurgulanır. */
  seciliAnahtar?: string | number | null;
  aramaYerTutucu?: string;
  /** Verilirse "Excel'e indir" düğmesi çıkar ("Ticketlar" → Ticketlar-2026-09-30.xlsx). */
  excelAdi?: string;
  bosMetin?: string;
  /** Kaydırma alanının yüksekliği (CSS). Varsayılan: ekranın kalanı. */
  yukseklik?: string;
  /** Araç çubuğunun sağına ek (segment, düğme…). */
  arac?: ReactNode;
  /** Sıralama cihazda hatırlansın diye tablo adı. */
  kayitAnahtari?: string;
  aramaBaslangic?: string;
}) {
  const dar = useDarEkran();
  const [arama, setArama] = useState(aramaBaslangic);
  const [siralama, setSiralama] = useState<Siralama>(() =>
    kayitAnahtari ? yerelJsonOku<Siralama>(`saha.tablo.${kayitAnahtari}.sira`, null) : null,
  );
  const [suzgecler, setSuzgecler] = useState<Record<string, Set<string>>>({});
  const [suzgecAcik, setSuzgecAcik] = useState<string | null>(null);
  const [suzgecYeri, setSuzgecYeri] = useState<{ x: number; y: number; sag: number }>({ x: 0, y: 0, sag: 0 });
  const [capa, setCapa] = useState<Nokta | null>(null);
  const [odak, setOdak] = useState<Nokta | null>(null);
  const [kaydirma, setKaydirma] = useState(0);
  const [gorunur, setGorunur] = useState(600);
  const [kartSiniri, setKartSiniri] = useState(100);
  const [kopyalandi, setKopyalandi] = useState(false);
  const kutu = useRef<HTMLDivElement>(null);
  const suruklenen = useRef(false);

  useEffect(() => {
    if (kayitAnahtari) yerelJsonYaz(`saha.tablo.${kayitAnahtari}.sira`, siralama);
  }, [siralama, kayitAnahtari]);

  /*
   * Sütunlar çağıranda çoğu zaman her çizimde yeniden kurulur; hesaplar sütun
   * ANAHTARLARINA bağlanır, böylece 20.000 satırlık arama metni her çizimde
   * yeniden katlanmaz.
   */
  const sutunImza = sutunlar.map((c) => c.anahtar).join('|');
  const sutunRef = useRef(sutunlar);
  sutunRef.current = sutunlar;

  /* Her satırın arama metni bir kez hazırlanır (her tuşta 20.000 satır katlanmasın). */
  const aramaMetni = useMemo(
    () => satirlar.map((s) => katla(sutunRef.current.map((c) => hucreMetni(c.deger(s))).join(' '))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [satirlar, sutunImza],
  );

  const gorunen = useMemo(() => {
    const sorgu = katla(arama).trim().split(/\s+/).filter(Boolean);
    const etkin = Object.entries(suzgecler).filter(([, k]) => k.size);
    const sutunHaritasi = new Map(sutunRef.current.map((c) => [c.anahtar, c]));
    const idx: number[] = [];
    for (let i = 0; i < satirlar.length; i++) {
      if (sorgu.length && !sorgu.every((p) => aramaMetni[i].includes(p))) continue;
      let gec = true;
      for (const [a, kume] of etkin) {
        const c = sutunHaritasi.get(a);
        if (c && !kume.has(hucreMetni(c.deger(satirlar[i])) || '(Boş)')) {
          gec = false;
          break;
        }
      }
      if (gec) idx.push(i);
    }
    if (siralama) {
      const c = sutunHaritasi.get(siralama.anahtar);
      if (c) {
        // Excel gibi: boş hücreler iki yönde de EN SONDA kalır.
        const bos = (d: Hucre) => d === null || d === undefined || d === '';
        idx.sort((x, y) => {
          const a = c.deger(satirlar[x]);
          const b = c.deger(satirlar[y]);
          if (bos(a) || bos(b)) return bos(a) === bos(b) ? x - y : bos(a) ? 1 : -1;
          return karsilastir(a, b) * siralama.yon || x - y;
        });
      }
    }
    return idx;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [satirlar, sutunImza, arama, suzgecler, siralama, aramaMetni]);

  /* Veri ya da süzgeç değişince seçim sıfırlanır (başka satırı kopyalamasın). */
  useEffect(() => {
    setCapa(null);
    setOdak(null);
    setKartSiniri(100);
  }, [gorunen]);

  /* Görünür yükseklik */
  useEffect(() => {
    const el = kutu.current;
    if (!el) return;
    const olc = () => setGorunur(el.clientHeight || 600);
    olc();
    const g = new ResizeObserver(olc);
    g.observe(el);
    return () => g.disconnect();
  }, [dar]);

  const secim = useMemo(() => {
    if (!capa || !odak) return null;
    return {
      r1: Math.min(capa.r, odak.r),
      r2: Math.max(capa.r, odak.r),
      c1: Math.min(capa.c, odak.c),
      c2: Math.max(capa.c, odak.c),
    };
  }, [capa, odak]);

  const secimOzeti = useMemo(() => {
    if (!secim) return null;
    let hucre = 0;
    let toplam = 0;
    let sayiVar = false;
    const satirSayisi = secim.r2 - secim.r1 + 1;
    // Çok büyük seçimde (hepsini seç) yalnız sayı sütunları toplanır; yine de hızlı.
    for (let r = secim.r1; r <= secim.r2; r++) {
      const s = satirlar[gorunen[r]];
      for (let c = secim.c1; c <= secim.c2; c++) {
        hucre++;
        const d = sutunlar[c].deger(s);
        if (typeof d === 'number' && Number.isFinite(d)) {
          toplam += d;
          sayiVar = true;
        }
      }
    }
    return { hucre, satir: satirSayisi, toplam: sayiVar ? toplam : null };
  }, [secim, satirlar, gorunen, sutunlar]);

  const kopyala = useCallback(async () => {
    if (!secim) return;
    const satirMetni: string[] = [];
    for (let r = secim.r1; r <= secim.r2; r++) {
      const s = satirlar[gorunen[r]];
      const hucreler: string[] = [];
      for (let c = secim.c1; c <= secim.c2; c++) hucreler.push(kopyaMetni(sutunlar[c].deger(s)));
      satirMetni.push(hucreler.join('\t'));
    }
    const metin = satirMetni.join('\r\n');
    try {
      await navigator.clipboard.writeText(metin);
    } catch {
      // Pano izni yoksa eski yol: gizli metin alanı.
      const alan = document.createElement('textarea');
      alan.value = metin;
      alan.style.position = 'fixed';
      alan.style.opacity = '0';
      document.body.appendChild(alan);
      alan.select();
      document.execCommand('copy');
      alan.remove();
      kutu.current?.focus();
    }
    setKopyalandi(true);
    window.setTimeout(() => setKopyalandi(false), 1600);
  }, [secim, satirlar, gorunen, sutunlar]);

  const gorunureGetir = useCallback((r: number) => {
    const el = kutu.current;
    if (!el) return;
    const ust = r * SATIR_Y;
    const baslikY = SATIR_Y;
    if (ust < el.scrollTop) el.scrollTop = ust;
    else if (ust + SATIR_Y + baslikY > el.scrollTop + el.clientHeight) {
      el.scrollTop = ust + SATIR_Y + baslikY - el.clientHeight;
    }
  }, []);

  const tus = (o: TusOlayi<HTMLDivElement>) => {
    if ((o.target as HTMLElement).tagName === 'INPUT') return;
    const n = gorunen.length;
    if (!n) return;
    const ctrl = o.ctrlKey || o.metaKey;
    if (ctrl && (o.key === 'c' || o.key === 'C')) {
      o.preventDefault();
      void kopyala();
      return;
    }
    if (ctrl && (o.key === 'a' || o.key === 'A')) {
      o.preventDefault();
      setCapa({ r: 0, c: 0 });
      setOdak({ r: n - 1, c: sutunlar.length - 1 });
      return;
    }
    if (o.key === 'Escape') {
      if (suzgecAcik) setSuzgecAcik(null);
      else {
        setCapa(null);
        setOdak(null);
      }
      return;
    }
    const simdi = odak ?? { r: 0, c: 0 };
    let yeni: Nokta | null = null;
    const sayfa = Math.max(1, Math.floor(gorunur / SATIR_Y) - 2);
    switch (o.key) {
      case 'ArrowDown':
        yeni = { r: Math.min(n - 1, odak ? simdi.r + (ctrl ? n : 1) : 0), c: simdi.c };
        break;
      case 'ArrowUp':
        yeni = { r: Math.max(0, simdi.r - (ctrl ? n : 1)), c: simdi.c };
        break;
      case 'ArrowRight':
        yeni = { r: simdi.r, c: Math.min(sutunlar.length - 1, simdi.c + (ctrl ? sutunlar.length : 1)) };
        break;
      case 'ArrowLeft':
        yeni = { r: simdi.r, c: Math.max(0, simdi.c - (ctrl ? sutunlar.length : 1)) };
        break;
      case 'PageDown':
        yeni = { r: Math.min(n - 1, simdi.r + sayfa), c: simdi.c };
        break;
      case 'PageUp':
        yeni = { r: Math.max(0, simdi.r - sayfa), c: simdi.c };
        break;
      case 'Home':
        yeni = ctrl ? { r: 0, c: 0 } : { r: simdi.r, c: 0 };
        break;
      case 'End':
        yeni = ctrl ? { r: n - 1, c: sutunlar.length - 1 } : { r: simdi.r, c: sutunlar.length - 1 };
        break;
      case 'Enter':
        if (odak && onAc) {
          o.preventDefault();
          onAc(satirlar[gorunen[odak.r]]);
        }
        return;
      default:
        return;
    }
    o.preventDefault();
    if (o.shiftKey) {
      if (!capa) setCapa(simdi);
    } else {
      setCapa(yeni);
    }
    setOdak(yeni);
    gorunureGetir(yeni.r);
  };

  const siralaTikla = (a: string) => {
    setSiralama((s) => (!s || s.anahtar !== a ? { anahtar: a, yon: 1 } : s.yon === 1 ? { anahtar: a, yon: -1 } : null));
  };

  const excel = () => {
    if (!excelAdi) return;
    const blob = xlsxOlustur([
      {
        ad: excelAdi,
        basliklar: sutunlar.map((c) => c.baslik),
        satirlar: gorunen.map((i) => sutunlar.map((c) => c.deger(satirlar[i]))),
      },
    ]);
    dosyaIndir(blob, tarihliAd(excelAdi));
  };

  const etkinSuzgec = Object.values(suzgecler).filter((k) => k.size).length;

  /* ------------------------------ Araç çubuğu ------------------------------ */
  const aracCubugu = (
    <div className="o-tablo-arac">
      <label className="o-arama">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" />
          <path d="m16 16 4 4" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          value={arama}
          onChange={(o) => setArama(o.target.value)}
          placeholder={aramaYerTutucu}
          aria-label="Tabloda ara"
        />
      </label>
      {etkinSuzgec ? (
        <button type="button" className="o-dugme kucuk" onClick={() => setSuzgecler({})}>
          Süzgeçleri kaldır ({etkinSuzgec})
        </button>
      ) : null}
      <span className="bosluk" />
      {arac}
      {excelAdi ? (
        <button type="button" className="o-dugme kucuk" onClick={excel} disabled={!gorunen.length}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <path d="M12 4v11m0 0-4-4m4 4 4-4M5 19h14" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Excel’e indir
        </button>
      ) : null}
    </div>
  );

  /* ------------------------------ Telefon: kartlar ------------------------------ */
  if (dar) {
    const baslikSutunu = sutunlar.find((c) => c.kartta === 'baslik') ?? sutunlar[0];
    const altSutun = sutunlar.find((c) => c.kartta === 'alt');
    const digerleri = sutunlar.filter((c) => c !== baslikSutunu && c !== altSutun && c.kartta !== 'gizli');
    return (
      <div className="o-tablo dar">
        {aracCubugu}
        <div className="o-tablo-kartlar">
          {gorunen.slice(0, kartSiniri).map((i) => {
            const s = satirlar[i];
            const k = anahtar(s);
            return (
              <button
                type="button"
                key={k}
                className={`o-tablo-kart${seciliAnahtar === k ? ' secili' : ''}`}
                onClick={onAc ? () => onAc(s) : undefined}
                disabled={!onAc}
              >
                <span className="baslik">{baslikSutunu.goster ? baslikSutunu.goster(s) : hucreMetni(baslikSutunu.deger(s))}</span>
                {altSutun ? (
                  <span className="alt">{altSutun.goster ? altSutun.goster(s) : hucreMetni(altSutun.deger(s))}</span>
                ) : null}
                <span className="alanlar">
                  {digerleri.map((c) => {
                    const d = c.deger(s);
                    if (d === null || d === undefined || d === '') return null;
                    return (
                      <span key={c.anahtar} className="o-tk-alan">
                        <span className="o-tk-etiket">{c.baslik}</span>
                        <span className={`o-tk-deger${c.sayi ? ' sayi' : ''}`}>{c.goster ? c.goster(s) : hucreMetni(d)}</span>
                      </span>
                    );
                  })}
                </span>
              </button>
            );
          })}
          {!gorunen.length ? <p className="o-tablo-bos">{bosMetin}</p> : null}
          {gorunen.length > kartSiniri ? (
            <button type="button" className="o-dugme" onClick={() => setKartSiniri((s) => s + 200)}>
              {`${(gorunen.length - kartSiniri).toLocaleString('tr-TR')} satır daha göster`}
            </button>
          ) : null}
        </div>
        <div className="o-tablo-durum">{gorunen.length.toLocaleString('tr-TR')} satır</div>
      </div>
    );
  }

  /* ------------------------------ Masaüstü: ızgara ------------------------------ */
  const ilk = Math.max(0, Math.floor(kaydirma / SATIR_Y) - TAMPON);
  const son = Math.min(gorunen.length, Math.ceil((kaydirma + gorunur) / SATIR_Y) + TAMPON);
  const genislikler = sutunlar.map((c) => c.genislik ?? (c.sayi ? 96 : 160));
  const toplamGenislik = genislikler.reduce((t, g) => t + g, 0);

  const hucreBas = (r: number, c: number, shift: boolean) => {
    kutu.current?.focus({ preventScroll: true });
    if (shift && capa) setOdak({ r, c });
    else {
      setCapa({ r, c });
      setOdak({ r, c });
    }
    suruklenen.current = true;
  };

  return (
    <div className="o-tablo">
      {aracCubugu}
      <div
        ref={kutu}
        className="o-tablo-kaydir"
        style={yukseklik ? { height: yukseklik } : undefined}
        tabIndex={0}
        role="grid"
        aria-rowcount={gorunen.length + 1}
        aria-colcount={sutunlar.length}
        aria-multiselectable="true"
        onKeyDown={tus}
        onScroll={(o) => setKaydirma((o.target as HTMLDivElement).scrollTop)}
        onMouseUp={() => {
          suruklenen.current = false;
        }}
        onMouseLeave={() => {
          suruklenen.current = false;
        }}
      >
        <table style={{ width: toplamGenislik }}>
          <colgroup>
            {genislikler.map((g, i) => (
              <col key={i} style={{ width: g }} />
            ))}
          </colgroup>
          <thead>
            <tr role="row">
              {sutunlar.map((c) => {
                const sira = siralama?.anahtar === c.anahtar ? siralama.yon : 0;
                const suzgecVar = (c.suzgec ?? !c.sayi) !== false;
                const suzuk = (suzgecler[c.anahtar]?.size ?? 0) > 0;
                return (
                  <th
                    key={c.anahtar}
                    role="columnheader"
                    className={c.sayi ? 'sayi' : undefined}
                    aria-sort={sira === 1 ? 'ascending' : sira === -1 ? 'descending' : 'none'}
                  >
                    <div className="th-ic">
                      <button type="button" className="sirala" onClick={() => siralaTikla(c.anahtar)} title="Sırala">
                        <span className="ad">{c.baslik}</span>
                        <span className={`ok${sira ? ' etkin' : ''}`} aria-hidden="true">
                          {sira === -1 ? '↓' : sira === 1 ? '↑' : '↕'}
                        </span>
                      </button>
                      {suzgecVar ? (
                        <button
                          type="button"
                          className={`suz${suzuk ? ' etkin' : ''}`}
                          aria-label={`${c.baslik} süzgeci`}
                          aria-expanded={suzgecAcik === c.anahtar}
                          onClick={(o) => {
                            const r = (o.currentTarget as HTMLElement).getBoundingClientRect();
                            setSuzgecYeri({ x: r.left, y: r.bottom + 4, sag: window.innerWidth - r.right });
                            setSuzgecAcik((a) => (a === c.anahtar ? null : c.anahtar));
                          }}
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                            <path d="M3 5h18l-7 8v6l-4 2v-8z" />
                          </svg>
                        </button>
                      ) : null}
                    </div>
                    {suzgecAcik === c.anahtar ? (
                      <SutunSuzgeci
                        degerler={satirlar.map((s) => hucreMetni(c.deger(s)) || '(Boş)')}
                        secili={suzgecler[c.anahtar] ?? new Set()}
                        degisti={(k) => setSuzgecler((o) => ({ ...o, [c.anahtar]: k }))}
                        kapat={() => {
                          setSuzgecAcik(null);
                          kutu.current?.focus({ preventScroll: true });
                        }}
                        sagda={c.sayi}
                        yer={suzgecYeri}
                      />
                    ) : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {ilk > 0 ? (
              <tr aria-hidden="true" style={{ height: ilk * SATIR_Y }}>
                <td colSpan={sutunlar.length} />
              </tr>
            ) : null}
            {gorunen.slice(ilk, son).map((i, j) => {
              const r = ilk + j;
              const s = satirlar[i];
              const k = anahtar(s);
              const satirSecili = secim && r >= secim.r1 && r <= secim.r2;
              return (
                <tr
                  key={k}
                  role="row"
                  aria-rowindex={r + 2}
                  className={`${seciliAnahtar === k ? 'acik' : ''}${satirSecili ? ' secimde' : ''}`}
                  onDoubleClick={onAc ? () => onAc(s) : undefined}
                >
                  {sutunlar.map((c, ci) => {
                    const sec = satirSecili && ci >= secim!.c1 && ci <= secim!.c2;
                    const odakta = odak && odak.r === r && odak.c === ci;
                    const metin = c.goster ? null : hucreMetni(c.deger(s));
                    return (
                      <td
                        key={c.anahtar}
                        role="gridcell"
                        aria-selected={sec || undefined}
                        className={`${c.sayi ? 'sayi' : ''}${sec ? ' sec' : ''}${odakta ? ' odak' : ''}`}
                        title={metin && metin.length > 18 ? metin : undefined}
                        onMouseDown={(o) => {
                          if (o.button !== 0) return;
                          o.preventDefault();
                          hucreBas(r, ci, o.shiftKey);
                        }}
                        onMouseEnter={() => {
                          if (suruklenen.current) setOdak({ r, c: ci });
                        }}
                      >
                        {c.goster ? c.goster(s) : metin}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
            {son < gorunen.length ? (
              <tr aria-hidden="true" style={{ height: (gorunen.length - son) * SATIR_Y }}>
                <td colSpan={sutunlar.length} />
              </tr>
            ) : null}
          </tbody>
        </table>
        {!gorunen.length ? <p className="o-tablo-bos">{bosMetin}</p> : null}
      </div>
      <div className="o-tablo-durum" aria-live="polite">
        <span>
          {gorunen.length.toLocaleString('tr-TR')} satır
          {gorunen.length !== satirlar.length ? ` · ${satirlar.length.toLocaleString('tr-TR')} içinden` : ''}
        </span>
        {secimOzeti && secimOzeti.hucre > 1 ? (
          <span>
            {secimOzeti.hucre.toLocaleString('tr-TR')} hücre seçili
            {secimOzeti.toplam !== null ? ` · Toplam ${secimOzeti.toplam.toLocaleString('tr-TR', { maximumFractionDigits: 2 })}` : ''}
          </span>
        ) : null}
        <span className="ipucu">
          {kopyalandi ? 'Kopyalandı — Excel’e yapıştırabilirsiniz' : 'Hücre seçip Ctrl+C ile Excel’e kopyalayın'}
        </span>
      </div>
    </div>
  );
}

/** Excel'deki gibi: değer listesi, arama, "Tümünü seç". Boş seçim = süzgeç yok. */
function SutunSuzgeci({
  degerler,
  secili,
  degisti,
  kapat,
  sagda,
  yer,
}: {
  degerler: string[];
  secili: Set<string>;
  degisti: (k: Set<string>) => void;
  kapat: () => void;
  sagda?: boolean;
  yer: { x: number; y: number; sag: number };
}) {
  const [ara, setAra] = useState('');
  const kutu = useRef<HTMLDivElement>(null);
  const sayilar = useMemo(() => {
    const m = new Map<string, number>();
    for (const d of degerler) m.set(d, (m.get(d) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], 'tr', { numeric: true }));
  }, [degerler]);
  const liste = sayilar.filter(([d]) => eslesir(d, ara)).slice(0, 500);

  useEffect(() => {
    const disari = (o: MouseEvent) => {
      if (kutu.current && !kutu.current.contains(o.target as Node)) kapat();
    };
    const t = window.setTimeout(() => document.addEventListener('mousedown', disari), 0);
    return () => {
      window.clearTimeout(t);
      document.removeEventListener('mousedown', disari);
    };
  }, [kapat]);

  const tumu = secili.size === 0;
  const degistir = (d: string) => {
    const yeni = new Set(tumu ? sayilar.map(([x]) => x) : secili);
    if (yeni.has(d)) yeni.delete(d);
    else yeni.add(d);
    degisti(yeni.size === sayilar.length ? new Set() : yeni);
  };

  // Kaydırma alanı süzgeci kesmesin diye sayfanın üstüne (portal) çizilir.
  const konum = sagda
    ? { top: yer.y, right: Math.max(8, yer.sag - 8) }
    : { top: yer.y, left: Math.max(8, Math.min(yer.x - 8, window.innerWidth - 288)) };
  return createPortal(
    <div
      ref={kutu}
      style={{ position: 'fixed', ...konum }}
      className={`o-sutun-suzgeci${sagda ? ' sagda' : ''}`}
      onKeyDown={(o) => {
        if (o.key === 'Escape') {
          o.stopPropagation();
          kapat();
        }
      }}
    >
      <input type="search" autoFocus value={ara} onChange={(o) => setAra(o.target.value)} placeholder="Değer ara…" />
      <label className="tumu">
        <input type="checkbox" checked={tumu} onChange={() => degisti(new Set())} />
        <span>(Tümü)</span>
      </label>
      <div className="degerler">
        {liste.map(([d, n]) => (
          <label key={d}>
            <input type="checkbox" checked={tumu || secili.has(d)} onChange={() => degistir(d)} />
            <span className="d">{d}</span>
            <span className="n">{n.toLocaleString('tr-TR')}</span>
          </label>
        ))}
      </div>
      <div className="alt">
        <button type="button" className="o-dugme kucuk birincil" onClick={kapat}>
          Tamam
        </button>
      </div>
    </div>,
    document.body,
  );
}
