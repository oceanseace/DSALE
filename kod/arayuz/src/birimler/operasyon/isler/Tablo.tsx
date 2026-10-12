/**
 * TASKS ızgarası — Turkcell.exe içinde Excel: ızgara çizgileri, sabit başlık + ilk 2 sütun donuk, satır başında
 * numara ve "i" (İş çekmecesini o açar). Hücreye tıklamak YALNIZ seçer; sürükle / Shift+tık alan seçer.
 * Tuşlar: oklar, Tab, Home/End, Ctrl+Home/End, PgUp/PgDn, Ctrl+A, Ctrl+C (TSV), Enter/Space (aç),
 * Shift+Space satır, Ctrl+Space sütun, Alt+↓ (Bizim durum listesi). Sağ tık: menü + dolgu rengi (yalnız seçili
 * hücrelere; hücre rengi `hucreRengi`, eski satır rengi bütün hücrelere).
 * Sanal kaydırma: yalnız görünen satırlar çizilir (3.000+ iş akıcı). Yakınlaştırma (Excel gibi): Ctrl+tekerlek ya da
 * durum çubuğundaki kaydırıcı (%50–200, kişi başına saklanır; Isler.tsx) — yalnız ızgara CSS `zoom` ile ölçeklenir;
 * ekran koordinatı → ızgara koordinatı dönüşümleri `z`ye bölünür. Kim: Isler.tsx.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { IsaretRengi, IsSatir } from '../../../cekirdek/is/tipler';
import { hucreRengi } from './sutunlar';
import { Baslik } from './Baslik';
import { BizimListesi } from './BizimListesi';
import { basYuksekligi, DONUK, geometri, SATIR_Y, sutunBul } from './geometri';
import { tusHedefi } from './klavye';
import { alanMetni, panoyaYaz } from './pano';
import { SagTikMenusu } from './SagTikMenusu';
import type { Secim } from './secim';
import type { SutunDuzeni } from './sutunDuzeni';
import type { Sutun } from './sutunlar';
import { SuzgecMenusu } from './SuzgecMenusu';
import type { TabloSuzgec } from './tabloSuzgec';

const TAMPON = 10;

export function IsTablosu({
  satirlar,
  sutunlar,
  duzen,
  t,
  secim,
  acikNo,
  yeniler,
  duzenleyebilir,
  harfler,
  yanan,
  gidilecek,
  ustAnahtar,
  ac,
  bizimYaz,
  boya,
  bildir,
  ata,
  aski,
  yakinlik = 100,
  yakinlikDegisti,
}: {
  satirlar: IsSatir[];
  /** Görünür sütunlar, ekrandaki sırayla. */
  sutunlar: Sutun[];
  duzen: SutunDuzeni;
  t: TabloSuzgec;
  secim: Secim;
  /** Çekmecesi açık iş. */
  acikNo: string | null;
  yeniler: Set<string>;
  duzenleyebilir: boolean;
  /** Üstte Excel sütun harfleri (A, B, C…) satırı. */
  harfler: boolean;
  /** BOSS eşitlemesiyle değişen hücreler (is_no → sütun id'leri): birkaç saniye sarı yanar. */
  yanan?: Map<string, Set<string>>;
  /** Dışarıdan "şu satıra git" (değişiklik şeridi): `k` her istekte artar. */
  gidilecek?: { r: number; k: number } | null;
  /** Tablonun üstündeki alan değişince (çip satırı) yükseklik yeniden ölçülür. */
  ustAnahtar: string;
  ac: (no: string) => void;
  bizimYaz: (satirlar: IsSatir[], deger: string | null) => void;
  /** Dolgu rengi: yalnız seçili hücreler (Excel gibi). */
  boya: (hucreler: Array<{ is_no: string; sutun: string }>, renk: IsaretRengi | null) => void;
  bildir: (metin: string) => void;
  /** Sağ tık "Ata…" (seçili satırlar); yoksa menüde görünmez. */
  ata?: () => void;
  /** Sağ tık "Askıya al…" (seçili satırlar). */
  aski?: () => void;
  /** Izgara yakınlaştırması, yüzde (50–200). */
  yakinlik?: number;
  /** Ctrl+tekerlek: yeni yüzde. */
  yakinlikDegisti?: (y: number) => void;
}) {
  const z = Math.max(0.5, Math.min(2, (yakinlik || 100) / 100));
  const kap = useRef<HTMLDivElement>(null);
  const [kaydir, setKaydir] = useState(0);
  const [yuk, setYuk] = useState(560);
  const [canli, setCanli] = useState<{ id: string; px: number } | null>(null);
  const [menu, setMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const [sagTik, setSagTik] = useState<{ x: number; y: number } | null>(null);
  const [bizimAcik, setBizimAcik] = useState<{ x: number; y: number } | null>(null);
  const [ipucu, setIpucu] = useState<{ metin: string; x: number; y: number } | null>(null);
  const surukle = useRef<{ tur: 'hucre' | 'satir'; r0: number; x: number; y: number } | null>(null);

  const g = useMemo(
    () => geometri(sutunlar.map((c) => (canli?.id === c.id ? canli.px : duzen.genislik(c)))),
    [sutunlar, duzen, canli],
  );
  const BAS_Y = basYuksekligi(harfler);
  /** Izgaranın kendi pikselleriyle görünür yükseklik (yakınlaştırmada ekrandaki yükseklik / z). */
  const yukIc = yuk / z;
  const n = satirlar.length;
  const m = sutunlar.length;
  const { alan, etkin } = secim;
  const bizimSutun = sutunlar.findIndex((c) => c.id === 'bizim');

  /* ------------------------------ yükseklik: ekranın kalanı ------------------------------ */
  useLayoutEffect(() => {
    const olc = () => {
      const el = kap.current;
      if (!el) return;
      // Altta içerik boşluğu (24 px) ve kabuğun durum çubuğu (24 px) kalsın.
      setYuk(Math.max(260, window.innerHeight - el.getBoundingClientRect().top - 48));
    };
    olc();
    window.addEventListener('resize', olc);
    return () => window.removeEventListener('resize', olc);
  }, [ustAnahtar]);

  /* ------------------------------ Ctrl+tekerlek: yakınlaştır (Excel gibi; sayfanın kendisi büyümez) ------------------------------ */
  const yakinlikRef = useRef({ y: yakinlik, f: yakinlikDegisti });
  yakinlikRef.current = { y: yakinlik, f: yakinlikDegisti };
  useEffect(() => {
    const el = kap.current;
    if (!el) return undefined;
    const teker = (o: WheelEvent) => {
      if (!(o.ctrlKey || o.metaKey) || !yakinlikRef.current.f) return;
      o.preventDefault();
      const y = yakinlikRef.current.y || 100;
      const adim = o.deltaY < 0 ? 10 : -10;
      yakinlikRef.current.f(Math.max(50, Math.min(200, Math.round((y + adim) / 10) * 10)));
    };
    el.addEventListener('wheel', teker, { passive: false });
    return () => el.removeEventListener('wheel', teker);
  }, []);

  /* ------------------------------ görünür alan ------------------------------ */
  const gorunurYap = useCallback(
    (r: number, c: number) => {
      const el = kap.current;
      if (!el) return;
      const ust = r * SATIR_Y;
      if (ust < el.scrollTop) el.scrollTop = ust;
      else if (BAS_Y + ust + SATIR_Y > el.scrollTop + el.clientHeight) el.scrollTop = BAS_Y + ust + SATIR_Y - el.clientHeight;
      if (c === 0) el.scrollLeft = 0; // Home / Ctrl+Home: Excel gibi sola döner
      else if (c >= DONUK && g.sol[c] !== undefined) {
        const sol = g.sol[c] - g.donukGen;
        const sag = g.sol[c] + g.gen[c];
        if (sol < el.scrollLeft) el.scrollLeft = sol;
        else if (sag > el.scrollLeft + el.clientWidth) el.scrollLeft = sag - el.clientWidth;
      }
    },
    [g, BAS_Y],
  );

  /* Değişiklik şeridinden gelen "satıra git": kaydır + klavye tabloda. */
  const gitK = gidilecek?.k;
  useEffect(() => {
    if (!gidilecek) return;
    gorunurYap(gidilecek.r, DONUK - 1); // yalnız dikey: yatay kaydırma yerinde kalır
    kap.current?.focus({ preventScroll: true });
    // yalnız yeni istekte
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gitK]);

  /* Yeni iş gelince (en alta) aşağıda duruluyorsa takip et. */
  const oncekiN = useRef(n);
  useEffect(() => {
    const el = kap.current;
    if (el && yeniler.size && n > oncekiN.current && el.scrollTop + el.clientHeight >= el.scrollHeight - SATIR_Y * 3) {
      el.scrollTop = el.scrollHeight;
    }
    oncekiN.current = n;
  }, [n, yeniler]);

  /* ------------------------------ fare ------------------------------ */
  const hucreBul = useCallback(
    (clientX: number, clientY: number): { r: number; c: number } => {
      const el = kap.current!;
      const k = el.getBoundingClientRect();
      const r = Math.max(0, Math.min(n - 1, Math.floor(((clientY - k.top) / z + el.scrollTop - BAS_Y) / SATIR_Y)));
      const x = (clientX - k.left) / z;
      return { r, c: sutunBul(g, x < g.donukGen ? x : x + el.scrollLeft) };
    },
    [g, n, BAS_Y, z],
  );

  const satirSec = useCallback(
    (r0: number, r: number) => secim.alanSec(r0, m - 1, r, 0),
    [secim, m],
  );

  /* Sürüklerken: hücreyi izle; kenara gelince kendiliğinden kaydır (Excel gibi). Döngü yalnız sürüklerken döner. */
  const izle = useRef<(x: number, y: number) => void>(() => undefined);
  izle.current = (x, y) => {
    const s = surukle.current;
    if (!s) return;
    const h = hucreBul(x, y);
    if (s.tur === 'satir') satirSec(s.r0, h.r);
    else secim.git(h.r, Math.max(0, h.c), true);
  };
  const donukGen = useRef(g.donukGen * z);
  donukGen.current = g.donukGen * z;
  const basEkran = useRef(BAS_Y * z);
  basEkran.current = BAS_Y * z;
  const surukleBasla = (tur: 'hucre' | 'satir', r0: number, x: number, y: number) => {
    surukle.current = { tur, r0, x, y };
    const hareket = (e: PointerEvent) => {
      if (!surukle.current) return;
      surukle.current.x = e.clientX;
      surukle.current.y = e.clientY;
      izle.current(e.clientX, e.clientY);
    };
    let kare = 0;
    const dongu = () => {
      const s = surukle.current;
      const el = kap.current;
      if (!s || !el) return;
      const k = el.getBoundingClientRect();
      const dy = s.y > k.bottom - 6 ? s.y - k.bottom + 6 : s.y < k.top + basEkran.current + 4 ? s.y - (k.top + basEkran.current + 4) : 0;
      const dx = s.x > k.right - 6 ? s.x - k.right + 6 : s.x < k.left + donukGen.current ? s.x - (k.left + donukGen.current) : 0;
      if (dy || dx) {
        el.scrollTop += Math.max(-40, Math.min(40, dy));
        el.scrollLeft += Math.max(-40, Math.min(40, dx));
        izle.current(s.x, s.y);
      }
      kare = window.requestAnimationFrame(dongu);
    };
    const bitir = () => {
      surukle.current = null;
      window.cancelAnimationFrame(kare);
      window.removeEventListener('pointermove', hareket);
      window.removeEventListener('pointerup', bitir);
    };
    window.addEventListener('pointermove', hareket);
    window.addEventListener('pointerup', bitir);
    kare = window.requestAnimationFrame(dongu);
  };

  const fareBas = (o: React.PointerEvent<HTMLDivElement>) => {
    const h = (o.target as HTMLElement).closest<HTMLElement>('[data-r]');
    if (!h || (o.target as HTMLElement).closest('button')) return;
    if (o.button !== 0) return;
    o.preventDefault();
    kap.current?.focus({ preventScroll: true });
    const r = Number(h.dataset.r);
    const c = Number(h.dataset.c);
    if (c < 0) {
      const r0 = o.shiftKey && etkin ? etkin.r : r;
      satirSec(r0, r);
      surukleBasla('satir', r0, o.clientX, o.clientY);
    } else {
      secim.git(r, c, o.shiftKey);
      surukleBasla('hucre', r, o.clientX, o.clientY);
    }
  };

  const sagTikla = (o: React.MouseEvent<HTMLDivElement>) => {
    const h = (o.target as HTMLElement).closest<HTMLElement>('[data-r]');
    if (!h) return;
    o.preventDefault();
    const r = Number(h.dataset.r);
    const c = Number(h.dataset.c);
    const icinde = alan && r >= alan.r1 && r <= alan.r2 && (c < 0 || (c >= alan.c1 && c <= alan.c2));
    if (!icinde) {
      if (c < 0) satirSec(r, r);
      else secim.git(r, c);
    }
    setSagTik({ x: o.clientX, y: o.clientY });
  };

  const ipucuIzle = (o: React.MouseEvent) => {
    const h = (o.target as HTMLElement).closest<HTMLElement>('[data-ipucu]');
    if (!h) {
      if (ipucu) setIpucu(null);
      return;
    }
    if (ipucu?.metin === h.dataset.ipucu) return;
    const k = h.getBoundingClientRect();
    setIpucu({ metin: h.dataset.ipucu ?? '', x: k.left, y: k.bottom + 4 });
  };

  /* ------------------------------ eylemler ------------------------------ */
  const kopyala = useCallback(() => {
    if (!alan) return;
    const { duz, html } = alanMetni(satirlar, sutunlar, alan);
    const r = alan.r2 - alan.r1 + 1;
    const c = alan.c2 - alan.c1 + 1;
    void panoyaYaz(duz, html).then((ok) =>
      bildir(ok ? `Kopyalandı: ${r.toLocaleString('tr-TR')} satır × ${c} sütun — Excel'e Ctrl+V` : 'Kopyalanamadı'),
    );
  }, [alan, satirlar, sutunlar, bildir]);

  const bizimAc = useCallback(() => {
    if (!etkin || etkin.c !== bizimSutun || !duzenleyebilir) return;
    const h = kap.current?.querySelector<HTMLElement>(`[data-r="${etkin.r}"][data-c="${etkin.c}"]`);
    const k = h?.getBoundingClientRect();
    if (k) setBizimAcik({ x: k.left, y: k.bottom });
  }, [etkin, bizimSutun, duzenleyebilir]);

  /** Bizim durum: seçim yalnız o sütundaysa bütün seçili satırlar, değilse etkin satır. */
  const bizimHedef = (): IsSatir[] =>
    alan && alan.c1 === bizimSutun && alan.c2 === bizimSutun ? secim.seciliSatirlar() : etkin ? [satirlar[etkin.r]] : [];

  const tus = (o: React.KeyboardEvent<HTMLDivElement>) => {
    if ((o.target as HTMLElement).closest('input, select, textarea')) return;
    const ctrl = o.ctrlKey || o.metaKey;
    const k = o.key.length === 1 ? o.key.toLocaleLowerCase('tr-TR') : o.key;
    if (!n || !m) return;
    if (ctrl && k === 'c') {
      o.preventDefault();
      kopyala();
      return;
    }
    if (ctrl && k === 'a') {
      o.preventDefault();
      secim.hepsi();
      return;
    }
    const e = etkin ?? { r: 0, c: 0 };
    if (o.key === ' ' && o.shiftKey) {
      o.preventDefault();
      satirSec(alan?.r1 ?? e.r, alan?.r2 ?? e.r);
      return;
    }
    if (o.key === ' ' && ctrl) {
      o.preventDefault();
      secim.alanSec(n - 1, alan?.c1 ?? e.c, 0, alan?.c2 ?? e.c);
      return;
    }
    if ((o.key === 'Enter' || o.key === ' ') && !o.altKey) {
      o.preventDefault();
      if (etkin) ac(satirlar[etkin.r].is_no);
      else secim.git(0, 0);
      return;
    }
    if (o.altKey && o.key === 'ArrowDown') {
      o.preventDefault();
      bizimAc();
      return;
    }
    const sayfa = Math.max(1, Math.floor((kap.current?.clientHeight ?? yukIc) / SATIR_Y) - 2);
    const y = tusHedefi(o.key, ctrl, o.shiftKey, e, n, m, sayfa);
    if (!y) return;
    o.preventDefault();
    // Seçim yokken ilk gezinme tuşu A1'e (ilk hücre) götürür, Excel gibi.
    const h = etkin ? y : { r: 0, c: 0 };
    secim.git(h.r, h.c, Boolean(etkin) && o.shiftKey && o.key !== 'Tab');
    gorunurYap(h.r, h.c);
  };

  /* ------------------------------ çizim ------------------------------ */
  const bas = Math.max(0, Math.floor(kaydir / SATIR_Y) - TAMPON);
  const son = Math.min(n, Math.ceil((kaydir + yukIc) / SATIR_Y) + TAMPON);
  const donukStil = (j: number) => (j < DONUK ? { left: g.sol[j] } : undefined);

  const hucre = (c: Sutun, s: IsSatir, r: number, j: number) => {
    const v = c.deger(s);
    const secili = alan && r >= alan.r1 && r <= alan.r2 && j >= alan.c1 && j <= alan.c2;
    const etkinHucre = etkin && etkin.r === r && etkin.c === j;
    const sayi = c.sayi?.(s) != null;
    const yandi = yanan?.get(s.is_no)?.has(c.id);
    const dolgu = hucreRengi(s, c.id);
    const sinif = `xg-h${dolgu ? ` r-${dolgu}` : ''}${secili ? ' secili' : ''}${etkinHucre ? ' etkin' : ''}${j < DONUK ? ' donuk' : ''}${j === DONUK - 1 ? ' donuk-son' : ''}${sayi ? ' sayi' : ''}${yandi ? ' degisti' : ''}`;
    let icerik: React.ReactNode = v;
    if (c.id === 'uyari' && v) {
      icerik = (
        <span
          className="xg-uyari"
          data-ipucu={(s.uyarilar ?? []).map((u) => u.metin).join('\n')}
          aria-label={(s.uyarilar ?? []).map((u) => u.metin).join('; ')}
        >
          {v}
        </span>
      );
    } else if (c.id === 'bizim' && etkinHucre && duzenleyebilir) {
      icerik = (
        <>
          <span className="xg-h-metin">{v}</span>
          <button type="button" tabIndex={-1} className="xg-hucre-ok" aria-label="Bizim durum seç" onMouseDown={(o) => o.preventDefault()} onClick={bizimAc}>
            ▾
          </button>
        </>
      );
    }
    return (
      <div
        key={c.id}
        className={sinif}
        style={donukStil(j)}
        data-r={r}
        data-c={j}
        role="gridcell"
        aria-selected={secili || undefined}
        title={c.id === 'uyari' || !v || v.length < 14 ? undefined : v}
        onDoubleClick={c.id === 'bizim' ? bizimAc : undefined}
      >
        {icerik}
      </div>
    );
  };

  const satirlarJsx = [];
  for (let r = bas; r < son; r++) {
    const s = satirlar[r];
    const satirSecili = alan && r >= alan.r1 && r <= alan.r2;
    satirlarJsx.push(
      <div
        key={s.is_no}
        className={`xg-satir${s.is_no === acikNo ? ' acik' : ''}${yeniler.has(s.is_no) ? ' yeni' : ''}`}
        style={{ top: r * SATIR_Y, gridTemplateColumns: g.sablon, width: g.toplam }}
        role="row"
        aria-rowindex={r + 2}
      >
        <div className={`xg-sb${satirSecili ? ' secili' : ''}`} data-r={r} data-c={-1} role="rowheader">
          <span className="xg-sb-no">{r + 1}</span>
          <button
            type="button"
            tabIndex={-1}
            className="xg-i"
            title="Ayrıntı (Enter)"
            aria-label={`${s.boss_task_no ?? s.is_no} ayrıntısı`}
            onMouseDown={(o) => o.preventDefault()}
            onClick={() => {
              secim.git(r, etkin?.c ?? 0);
              ac(s.is_no);
            }}
          >
            i
          </button>
        </div>
        {sutunlar.map((c, j) => hucre(c, s, r, j))}
      </div>,
    );
  }

  return (
    <div className="xg-kok">
      <div
        ref={kap}
        className="xg-kap"
        style={z === 1 ? { height: yuk } : { height: yukIc, zoom: z }}
        tabIndex={0}
        role="grid"
        aria-label="TASKS"
        aria-rowcount={n + 1}
        aria-colcount={m}
        aria-multiselectable="true"
        onKeyDown={tus}
        onPointerDown={fareBas}
        onContextMenu={sagTikla}
        onMouseOver={ipucuIzle}
        onMouseLeave={() => setIpucu(null)}
        onScroll={(o) => {
          const y = (o.target as HTMLDivElement).scrollTop;
          if (y !== kaydir) setKaydir(y);
          if (ipucu) setIpucu(null);
        }}
      >
        <Baslik
          sutunlar={sutunlar}
          g={g}
          t={t}
          alan={alan}
          kap={kap}
          duzen={duzen}
          satirlar={satirlar}
          harfler={harfler}
          canliGen={setCanli}
          sutunSec={(j, genislet) => {
            const a = genislet && etkin ? etkin.c : j;
            secim.alanSec(n - 1, a, 0, j);
          }}
          sutunAralik={(a, b) => secim.alanSec(n - 1, a, 0, b)}
          hepsiniSec={secim.hepsi}
          menuAc={(id, x, y) => setMenu((o) => (o?.id === id ? null : { id, x, y }))}
          olcek={z}
        />
        <div className="xg-govde" style={{ height: n * SATIR_Y, width: g.toplam }}>
          {satirlarJsx}
        </div>
        {!n ? <div className="xg-bos">Süzgece uyan iş yok.</div> : null}
      </div>
      {menu ? <SuzgecMenusu key={menu.id} id={menu.id} x={menu.x} y={menu.y} t={t} kapat={() => setMenu(null)} /> : null}
      {sagTik && etkin ? (
        <SagTikMenusu
          x={sagTik.x}
          y={sagTik.y}
          satirSayisi={alan ? alan.r2 - alan.r1 + 1 : 1}
          hucreSayisi={alan ? (alan.r2 - alan.r1 + 1) * (alan.c2 - alan.c1 + 1) : 1}
          boyanabilir={duzenleyebilir}
          ac={() => ac(satirlar[etkin.r].is_no)}
          kopyala={kopyala}
          boya={(r) => boya(secim.seciliHucreler(), r)}
          ata={ata}
          aski={aski}
          kapat={() => {
            setSagTik(null);
            kap.current?.focus({ preventScroll: true });
          }}
        />
      ) : null}
      {bizimAcik && etkin ? (
        <BizimListesi
          x={bizimAcik.x}
          y={bizimAcik.y}
          deger={satirlar[etkin.r]?.bizim_durum ?? null}
          satirSayisi={bizimHedef().length}
          sec={(v) => {
            bizimYaz(bizimHedef(), v);
            setBizimAcik(null);
            kap.current?.focus({ preventScroll: true });
          }}
          kapat={() => {
            setBizimAcik(null);
            kap.current?.focus({ preventScroll: true });
          }}
        />
      ) : null}
      {ipucu
        ? createPortal(
            <div className="xg-ipucu" role="tooltip" style={{ left: Math.min(ipucu.x, window.innerWidth - 340), top: ipucu.y }}>
              {ipucu.metin}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
