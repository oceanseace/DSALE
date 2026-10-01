/**
 * İş emirleri — BOSS "Teknik Task Detay Raporu"nu makro gibi hazırlar, öbekleri kurar.
 *
 *   1. Rapor bırakılır → kurulum / 2. donanım satırları çıkar, adresten mahalle bulunur
 *      (ilçe ile: Nilüfer/Dumlupınar ≠ Osmangazi/Dumlupınar).
 *   2. Süzülür (ilçe · öbek · task · durum · arama).
 *   3. Soldaki mahalle listesinden seçilenler tek tuşla öbek olur (ya da var olana eklenir).
 *   4. Yoğun öbek (ya da süzülen işlerin tamamı) yakınlığa göre k eşit parçaya bölünür:
 *      "mahalleye göre" kalıcı öbek olur, "binaya göre" bugünkü dağıtım listesi olur.
 *   5. Excel: İşler · Öbekler · Mahalleler · Kontrol · Çıkarılanlar · Özet.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import { sayi } from '../../ortak/bicim';
import { SahaHatasi } from '../../api/istemci';
import { Icerik, YonUst } from '../ortak/Kabuk';
import { HataKutusu, Iskelet, Kart, Segment } from '../ortak/parcalar';
import {
  bol,
  durumOku,
  excelIndir,
  mahalleRef,
  obekIslemi,
  parcaKaydet,
  raporYukle,
  type BolmeSonucu,
  type Is,
  type IsEmriDurumu,
} from '../is_emri/api';
import { IsHaritasi, type HaritaEtiketi, type IsNoktasi, type Renk } from '../is_emri/IsHaritasi';
import '../is_emri/is_emri.css';

const OBEKSIZ = '(öbeksiz)';
const GRI: Renk = [140, 150, 165];
const PALET: Renk[] = [
  [11, 99, 229], [15, 138, 74], [224, 138, 30], [96, 51, 201], [192, 42, 42], [0, 150, 160],
  [200, 60, 150], [120, 110, 20], [30, 60, 140], [230, 90, 70], [80, 160, 60], [150, 90, 40],
  [20, 120, 200], [170, 40, 90],
];
const rgb = (r: Renk) => `rgb(${r.join(',')})`;

type Birim = 'mahalle' | 'bina';
interface BolmeHedefi {
  /** Öbek adı; null = süzülen işlerin tamamı */
  obek: string | null;
  ids: number[];
  k: number;
  birim: Birim;
  sonuc: BolmeSonucu | null;
  adlar: string[];
  calisiyor: boolean;
}

function mesafeKm(a: [number, number], b: [number, number]) {
  const r = Math.PI / 180;
  const dLat = (b[0] - a[0]) * r;
  const dLon = (b[1] - a[1]) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * r) * Math.cos(b[0] * r) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

/** İşlerin kapladığı alanın yarıçapı (merkezden en uzak kesin konumlu iş, km). */
function yaricap(isler: Is[]): number | null {
  const k = isler.filter((i) => i.lat != null && i.lon != null && !i.konum.startsWith('ilçe'));
  if (k.length < 2) return null;
  const m: [number, number] = [
    k.reduce((t, i) => t + (i.lat as number), 0) / k.length,
    k.reduce((t, i) => t + (i.lon as number), 0) / k.length,
  ];
  return Math.max(...k.map((i) => mesafeKm(m, [i.lat as number, i.lon as number])));
}

function hataMetni(h: unknown) {
  return h instanceof SahaHatasi ? h.message : 'İşlem yapılamadı.';
}

export function IsEmirleri() {
  const [veri, setVeri] = useState<IsEmriDurumu | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState<string | null>(null);
  const [bildiri, setBildiri] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [surukle, setSurukle] = useState(false);
  const dosyaGirdi = useRef<HTMLInputElement | null>(null);

  /* Süzgeçler */
  const [ilceler, setIlceler] = useState<Set<string>>(new Set());
  const [obekFiltre, setObekFiltre] = useState<string>('');
  const [tasklar, setTasklar] = useState<Set<string>>(new Set());
  const [durumlar, setDurumlar] = useState<Set<string>>(new Set());
  const [arama, setArama] = useState('');

  /* Öbek kurma */
  const [secili, setSecili] = useState<Set<string>>(new Set());
  const [obekAdi, setObekAdi] = useState('');
  const [adDegisen, setAdDegisen] = useState<{ eski: string; yeni: string } | null>(null);

  /* Bölme */
  const [bolme, setBolme] = useState<BolmeHedefi | null>(null);
  const [kontrolAcik, setKontrolAcik] = useState(false);

  const yenile = useCallback(async () => {
    try {
      setVeri(await durumOku());
      setHata(null);
    } catch (h) {
      setHata(hataMetni(h));
    } finally {
      setYukleniyor(false);
    }
  }, []);

  useEffect(() => {
    void yenile();
  }, [yenile]);

  const bildir = (m: string) => {
    setBildiri(m);
    window.setTimeout(() => setBildiri((b) => (b === m ? null : b)), 4000);
  };

  const calistir = async (is: () => Promise<IsEmriDurumu>, basari?: string) => {
    setGonderiliyor(true);
    try {
      setVeri(await is());
      setHata(null);
      if (basari) bildir(basari);
      return true;
    } catch (h) {
      setHata(hataMetni(h));
      return false;
    } finally {
      setGonderiliyor(false);
    }
  };

  const dosyaSecildi = async (dosya: File | undefined | null) => {
    if (!dosya) return;
    setBolme(null);
    setSecili(new Set());
    const ok = await calistir(() => raporYukle(dosya));
    if (ok) bildir(`${dosya.name} işlendi.`);
  };

  const birak = (o: DragEvent<HTMLDivElement>) => {
    o.preventDefault();
    setSurukle(false);
    void dosyaSecildi(o.dataTransfer.files?.[0]);
  };

  /* ---------------- Türetilen veriler ---------------- */

  const isler = veri?.isler ?? [];
  const obekRengi = useMemo(() => {
    const m = new Map<string, Renk>();
    (veri?.obekler ?? []).forEach((o, i) => m.set(o.ad, PALET[i % PALET.length]));
    return m;
  }, [veri?.obekler]);

  const ilceSayilari = useMemo(() => {
    const m = new Map<string, number>();
    isler.forEach((i) => m.set(`${i.il}/${i.ilce}`, (m.get(`${i.il}/${i.ilce}`) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [isler]);
  const taskSayilari = useMemo(() => {
    const m = new Map<string, number>();
    isler.forEach((i) => m.set(i.task, (m.get(i.task) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [isler]);
  const durumSayilari = useMemo(() => {
    const m = new Map<string, number>();
    isler.forEach((i) => i.durum && m.set(i.durum, (m.get(i.durum) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [isler]);

  const suzulen = useMemo(() => {
    const a = arama.trim().toLocaleLowerCase('tr');
    return isler.filter(
      (i) =>
        (!ilceler.size || ilceler.has(`${i.il}/${i.ilce}`)) &&
        (!obekFiltre || (obekFiltre === OBEKSIZ ? !i.obek : i.obek === obekFiltre)) &&
        (!tasklar.size || tasklar.has(i.task)) &&
        (!durumlar.size || durumlar.has(i.durum)) &&
        (!a ||
          `${i.mahalle} ${i.adres} ${i.task_no ?? ''} ${i.obek} ${i.ilce}`.toLocaleLowerCase('tr').includes(a)),
    );
  }, [isler, ilceler, obekFiltre, tasklar, durumlar, arama]);

  const mahalleler = useMemo(() => {
    const m = new Map<string, { ref: string; il: string; ilce: string; mahalle: string; is: number; obek: string }>();
    for (const i of suzulen) {
      if (!i.mahalle) continue;
      const ref = mahalleRef(i.il, i.ilce, i.mahalle);
      const s = m.get(ref) ?? { ref, il: i.il, ilce: i.ilce, mahalle: i.mahalle, is: 0, obek: i.obek };
      s.is += 1;
      m.set(ref, s);
    }
    return [...m.values()].sort((a, b) => b.is - a.is || a.mahalle.localeCompare(b.mahalle, 'tr'));
  }, [suzulen]);

  const obekKartlari = useMemo(() => {
    const m = new Map<string, Is[]>();
    for (const i of suzulen) {
      const k = i.obek || OBEKSIZ;
      m.set(k, [...(m.get(k) ?? []), i]);
    }
    return [...m.entries()]
      .map(([ad, liste]) => ({
        ad,
        isler: liste,
        mahalle: new Set(liste.map((i) => mahalleRef(i.il, i.ilce, i.mahalle))).size,
        ilceler: [...new Set(liste.map((i) => i.ilce))],
        yaricap: yaricap(liste),
      }))
      .sort((a, b) => (a.ad === OBEKSIZ ? 1 : b.ad === OBEKSIZ ? -1 : b.isler.length - a.isler.length));
  }, [suzulen]);
  const enCok = Math.max(1, ...obekKartlari.map((o) => o.isler.length));

  /* Yalnız gerçekten bakılacaklar: mahalle yok, il bölge dışı, çelişen ilçe, konum yok. */
  const kontrol = useMemo(() => isler.filter((i) => i.not), [isler]);
  const parcalar = useMemo(() => {
    const m = new Map<string, number>();
    isler.forEach((i) => i.parca && m.set(i.parca, (m.get(i.parca) ?? 0) + 1));
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0], 'tr', { numeric: true }));
  }, [isler]);

  /* ---------------- Harita ---------------- */

  const onizleme = bolme?.sonuc ?? null;
  const noktalar = useMemo<IsNoktasi[]>(() => {
    const onIds = onizleme ? new Set(bolme?.ids) : null;
    const kaynak = onizleme ? isler.filter((i) => onIds!.has(i.id) || suzulen.includes(i)) : suzulen;
    return kaynak
      .filter((i) => i.lat != null && i.lon != null)
      .map((i) => {
        const p = onizleme?.atama[String(i.id)];
        const renk = onizleme
          ? p
            ? PALET[(p - 1) % PALET.length]
            : GRI
          : i.obek
            ? obekRengi.get(i.obek) ?? GRI
            : GRI;
        return {
          id: i.id,
          lat: i.lat as number,
          lon: i.lon as number,
          renk,
          kaba: i.konum.startsWith('ilçe'),
          soluk: onizleme ? p == null : false,
          baslik: `${i.task}${i.task_no ? ' · ' + i.task_no : ''}`,
          alt: `${i.ilce} / ${i.mahalle || '?'}${i.obek ? ' · ' + i.obek : ''}`,
        };
      });
  }, [suzulen, isler, onizleme, bolme?.ids, obekRengi]);

  const etiketler = useMemo<HaritaEtiketi[]>(
    () =>
      (onizleme?.parcalar ?? [])
        .filter((p) => p.merkez && p.parca > 0)
        .map((p, n) => ({
          lat: p.merkez![0],
          lon: p.merkez![1],
          metin: `${bolme?.adlar[n] ?? p.ad} · ${p.is}`,
          renk: PALET[(p.parca - 1) % PALET.length],
        })),
    [onizleme, bolme?.adlar],
  );

  const sigdirmaAnahtari = `${veri?.yukleme?.zaman}|${[...ilceler].join()}|${obekFiltre}|${[...tasklar].join()}|${[...durumlar].join()}|${bolme ? 'b' + bolme.obek + bolme.ids.length : ''}`;

  /* ---------------- Eylemler ---------------- */

  const mahalleSec = (ref: string) =>
    setSecili((s) => {
      const y = new Set(s);
      if (y.has(ref)) y.delete(ref);
      else y.add(ref);
      return y;
    });

  const obekYap = async () => {
    const ad = obekAdi.trim();
    if (!ad || !secili.size) return;
    const ok = await calistir(
      () => obekIslemi({ islem: 'ata', ad, mahalleler: [...secili] }),
      `${secili.size} mahalle "${ad}" öbeğine alındı.`,
    );
    if (ok) {
      setSecili(new Set());
      setObekAdi('');
    }
  };

  const obektenCikar = async () => {
    if (!secili.size) return;
    const ok = await calistir(
      () => obekIslemi({ islem: 'cikar', mahalleler: [...secili] }),
      `${secili.size} mahalle öbeğinden çıkarıldı.`,
    );
    if (ok) setSecili(new Set());
  };

  const bolmeBaslat = (obek: string | null, liste: Is[]) =>
    setBolme({
      obek,
      ids: liste.map((i) => i.id),
      k: 2,
      birim: new Set(liste.map((i) => i.mahalle)).size >= 2 ? 'mahalle' : 'bina',
      sonuc: null,
      adlar: [],
      calisiyor: false,
    });

  const onizle = async (h: BolmeHedefi) => {
    setBolme({ ...h, calisiyor: true });
    try {
      const kok = h.obek && h.obek !== OBEKSIZ ? h.obek : 'Parça';
      const sonuc = await bol({ ids: h.ids, k: h.k, birim: h.birim, ad: kok });
      setBolme({ ...h, sonuc, adlar: sonuc.parcalar.filter((p) => p.parca > 0).map((p) => p.ad), calisiyor: false });
      setHata(null);
    } catch (e) {
      setBolme({ ...h, calisiyor: false });
      setHata(hataMetni(e));
    }
  };

  const bolmeUygula = async () => {
    if (!bolme?.sonuc) return;
    const gecerli = bolme.sonuc.parcalar.filter((p) => p.parca > 0);
    const ad = (n: number) => (bolme.adlar[n] || gecerli[n].ad).trim();
    let ok: boolean;
    if (bolme.birim === 'mahalle') {
      ok = await calistir(
        () =>
          parcaKaydet({
            obek_olarak: gecerli.map((p, n) => ({ ad: ad(n), mahalleler: p.mahalleler })),
            eski_obek: bolme.obek && bolme.obek !== OBEKSIZ ? bolme.obek : null,
          }),
        `${gecerli.length} öbek kaydedildi.`,
      );
    } else {
      const adi = new Map(gecerli.map((p, n) => [p.parca, ad(n)]));
      const atama: Record<number, string | null> = {};
      Object.entries(bolme.sonuc.atama).forEach(([id, p]) => {
        atama[Number(id)] = p ? adi.get(p) ?? null : null;
      });
      ok = await calistir(() => parcaKaydet({ atama }), `${gecerli.length} parça bugünkü listeye yazıldı.`);
    }
    if (ok) {
      setBolme(null);
      if (bolme.obek && bolme.birim === 'mahalle') setObekFiltre('');
    }
  };

  const ilceDegistir = (k: string) =>
    setIlceler((s) => {
      const y = new Set(s);
      if (y.has(k)) y.delete(k);
      else y.add(k);
      return y;
    });

  const tumMahalleleriSec = () => setSecili(new Set(mahalleler.map((m) => m.ref)));

  /* ---------------- Çizim ---------------- */

  const y = veri?.yukleme;
  const oz = y?.ozet;
  const obekAdlari = (veri?.obekler ?? []).map((o) => o.ad);

  return (
    <>
      <YonUst
        baslik="İş emirleri · öbekler"
        altYazi={
          y
            ? `${y.dosya} · ${new Date(y.zaman).toLocaleString('tr-TR', { dateStyle: 'short', timeStyle: 'short' })}`
            : 'BOSS Teknik Task Detay Raporu’nu bırakın: kurulum ve 2. donanım çıkar, mahalleler adresten bulunur.'
        }
      >
        <input
          ref={dosyaGirdi}
          type="file"
          accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(o) => {
            void dosyaSecildi(o.target.files?.[0]);
            o.target.value = '';
          }}
        />
        <button className="yd birincil" onClick={() => dosyaGirdi.current?.click()} disabled={gonderiliyor}>
          {gonderiliyor ? 'İşleniyor…' : 'Rapor yükle'}
        </button>
        {y ? (
          <button
            className="yd"
            onClick={() => excelIndir(y.dosya).catch((h) => setHata(hataMetni(h)))}
            disabled={gonderiliyor}
          >
            Excel indir
          </button>
        ) : null}
      </YonUst>

      <Icerik>
        <div
          className={`ie-birak${surukle ? ' uzerinde' : ''}${y ? ' ince' : ''}`}
          onDragOver={(o) => {
            o.preventDefault();
            setSurukle(true);
          }}
          onDragLeave={() => setSurukle(false)}
          onDrop={birak}
          onClick={() => !y && dosyaGirdi.current?.click()}
          role={y ? undefined : 'button'}
        >
          {oz ? (
            <div className="ie-ozet">
              <span>
                <b>{sayi(oz.toplam_satir)}</b> satır
              </span>
              <span className="ok">→</span>
              <span>
                <b>{sayi(oz.cikarilan)}</b> çıkarıldı
                {Object.keys(oz.cikarilan_neden).length
                  ? ` (${Object.entries(oz.cikarilan_neden)
                      .map(([k, v]) => `${k === 'KURULUM' ? 'kurulum' : '2. donanım'} ${sayi(v)}`)
                      .join(', ')})`
                  : ''}
              </span>
              <span className="ok">→</span>
              <span>
                <b>{sayi(oz.kalan)}</b> iş
              </span>
              <span className="ayrac" />
              <span>
                mahalle bulunan <b>{sayi(oz.mahalle_bulunan)}</b> · {sayi(oz.mahalle_sayisi)} mahalle
              </span>
              <span>
                öbeği belli <b>{sayi(oz.obekli)}</b>
              </span>
              <span className="ipucu">Yeni rapor için dosyayı buraya sürükleyin</span>
            </div>
          ) : (
            <div className="ie-birak-ic">
              <b>BOSS raporunu buraya sürükleyin</b>
              <span>ya da tıklayıp seçin · TeknikTaskDetayRaporu.xlsx</span>
            </div>
          )}
        </div>

        {bildiri ? <div className="ie-bildiri" role="status">{bildiri}</div> : null}
        {hata ? <HataKutusu mesaj={hata} yenile={() => void yenile()} /> : null}
        {yukleniyor ? <Iskelet yukseklik={320} /> : null}

        {y ? (
          <>
            {/* ---------------- Süzgeçler ---------------- */}
            <div className="ie-suzgec">
              <div className="ie-cipler" aria-label="İlçe">
                <span className="ie-etiket">İlçe</span>
                {ilceSayilari.map(([k, n]) => (
                  <button
                    key={k}
                    className={`ie-cip${ilceler.has(k) ? ' secili' : ''}`}
                    aria-pressed={ilceler.has(k)}
                    onClick={() => ilceDegistir(k)}
                    title={k}
                  >
                    {k.split('/')[1]} <b>{n}</b>
                  </button>
                ))}
                {ilceler.size ? (
                  <button className="ie-cip temizle" onClick={() => setIlceler(new Set())}>
                    Tümü
                  </button>
                ) : null}
              </div>
              <div className="ie-cipler" aria-label="Task">
                <span className="ie-etiket">Task</span>
                {taskSayilari.map(([k, n]) => (
                  <button
                    key={k}
                    className={`ie-cip${tasklar.has(k) ? ' secili' : ''}`}
                    aria-pressed={tasklar.has(k)}
                    onClick={() =>
                      setTasklar((s) => {
                        const y2 = new Set(s);
                        if (y2.has(k)) y2.delete(k);
                        else y2.add(k);
                        return y2;
                      })
                    }
                  >
                    {k} <b>{n}</b>
                  </button>
                ))}
              </div>
              <div className="ie-satir">
                <div className="ie-cipler" aria-label="Durum">
                  <span className="ie-etiket">Durum</span>
                  {durumSayilari.map(([k, n]) => (
                    <button
                      key={k}
                      className={`ie-cip${durumlar.has(k) ? ' secili' : ''}`}
                      aria-pressed={durumlar.has(k)}
                      onClick={() =>
                        setDurumlar((s) => {
                          const y2 = new Set(s);
                          if (y2.has(k)) y2.delete(k);
                          else y2.add(k);
                          return y2;
                        })
                      }
                    >
                      {k} <b>{n}</b>
                    </button>
                  ))}
                </div>
                <select
                  className="yon-alan"
                  value={obekFiltre}
                  onChange={(o) => setObekFiltre(o.target.value)}
                  aria-label="Öbek süzgeci"
                  style={{ width: 220 }}
                >
                  <option value="">Bütün öbekler</option>
                  <option value={OBEKSIZ}>Öbeği olmayanlar</option>
                  {obekAdlari.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                <input
                  className="yon-alan"
                  placeholder="Ara: mahalle, adres, task no…"
                  value={arama}
                  onChange={(o) => setArama(o.target.value)}
                  style={{ width: 240 }}
                />
                <span className="ie-sayac">
                  <b>{sayi(suzulen.length)}</b> iş gösteriliyor
                </span>
              </div>
            </div>

            <div className="ie-izgara">
              {/* ---------------- Mahalleler ---------------- */}
              <Kart
                baslik="Mahalleler"
                altYazi="Seçin → öbek yapın. Aynı ad farklı ilçede ayrı mahalledir."
                sikis
                sag={
                  <button className="yd ie-kucuk" onClick={tumMahalleleriSec} disabled={!mahalleler.length}>
                    Hepsini seç
                  </button>
                }
              >
                <div className="ie-obek-yap">
                  <input
                    className="yon-alan"
                    list="ie-obek-adlari"
                    placeholder={secili.size ? `${secili.size} mahalle → öbek adı` : 'Önce mahalle seçin'}
                    value={obekAdi}
                    onChange={(o) => setObekAdi(o.target.value)}
                    onKeyDown={(o) => o.key === 'Enter' && void obekYap()}
                    disabled={!secili.size}
                  />
                  <datalist id="ie-obek-adlari">
                    {obekAdlari.map((a) => (
                      <option key={a} value={a} />
                    ))}
                  </datalist>
                  <button
                    className="yd birincil"
                    onClick={() => void obekYap()}
                    disabled={!secili.size || !obekAdi.trim() || gonderiliyor}
                  >
                    Öbek yap
                  </button>
                  {secili.size ? (
                    <div className="ie-secim-satir">
                      <span>{secili.size} seçili</span>
                      <button className="bag" onClick={() => void obektenCikar()} disabled={gonderiliyor}>
                        Öbekten çıkar
                      </button>
                      <button className="bag" onClick={() => setSecili(new Set())}>
                        Seçimi temizle
                      </button>
                    </div>
                  ) : null}
                </div>
                <div className="ie-mahalle-liste" role="list">
                  {mahalleler.map((m) => {
                    const r = m.obek ? obekRengi.get(m.obek) ?? GRI : null;
                    return (
                      <label key={m.ref} className={`ie-mahalle${secili.has(m.ref) ? ' secili' : ''}`} role="listitem">
                        <input type="checkbox" checked={secili.has(m.ref)} onChange={() => mahalleSec(m.ref)} />
                        <span className="ad">
                          <span className="mh">{m.mahalle}</span>
                          <span className="ilce">{m.ilce}</span>
                        </span>
                        {m.obek ? (
                          <span className="obek" style={{ borderColor: rgb(r!), color: rgb(r!) }} title={m.obek}>
                            {m.obek}
                          </span>
                        ) : null}
                        <span className="sayi">{m.is}</span>
                      </label>
                    );
                  })}
                  {!mahalleler.length ? <div className="ie-bos">Bu süzgeçte iş yok.</div> : null}
                </div>
              </Kart>

              {/* ---------------- Harita ---------------- */}
              <div className="ie-harita-sutun">
                <IsHaritasi
                  noktalar={noktalar}
                  etiketler={etiketler}
                  sigdirmaAnahtari={sigdirmaAnahtari}
                  odak={bolme?.ids}
                  yerTiklandi={(ids) => {
                    const refler = new Set(
                      isler.filter((i) => ids.includes(i.id) && i.mahalle).map((i) => mahalleRef(i.il, i.ilce, i.mahalle)),
                    );
                    setSecili((s) => new Set([...s, ...refler]));
                  }}
                  yukseklik="min(68vh, 720px)"
                />
                <div className="ie-lejant">
                  {onizleme ? (
                    <span>Önizleme: renkler parçaları gösteriyor. Uygula ya da vazgeç.</span>
                  ) : (
                    <>
                      <span>Renk = öbek · gri = öbeksiz · büyüklük = iş sayısı · halka = yalnız ilçe merkezi biliniyor</span>
                    </>
                  )}
                </div>
              </div>

              {/* ---------------- Öbekler + bölme ---------------- */}
              <div className="ie-sag">
                {bolme ? (
                  <Kart
                    baslik={bolme.obek ? `Böl: ${bolme.obek}` : 'Süzülen işleri böl'}
                    altYazi={`${sayi(bolme.ids.length)} iş · yakınlığa göre eşit parçalar`}
                    sikis
                  >
                    <div className="ie-bol">
                      <div className="ie-bol-satir">
                        <span>Parça</span>
                        <div className="ie-adim">
                          <button
                            onClick={() => setBolme({ ...bolme, k: Math.max(2, bolme.k - 1), sonuc: null })}
                            aria-label="Azalt"
                          >
                            −
                          </button>
                          <b>{bolme.k}</b>
                          <button
                            onClick={() => setBolme({ ...bolme, k: Math.min(30, bolme.k + 1), sonuc: null })}
                            aria-label="Artır"
                          >
                            +
                          </button>
                        </div>
                      </div>
                      <Segment<Birim>
                        etiket="Bölme birimi"
                        secenekler={[
                          { deger: 'mahalle', etiket: 'Mahalleye göre' },
                          { deger: 'bina', etiket: 'Binaya göre' },
                        ]}
                        deger={bolme.birim}
                        degisti={(b) => setBolme({ ...bolme, birim: b, sonuc: null })}
                      />
                      <div className="ie-not">
                        {bolme.birim === 'mahalle'
                          ? 'Mahalleler bölünmez; parçalar kalıcı öbek olarak kaydedilir.'
                          : 'Aynı binadaki işler birlikte kalır; parçalar bugünkü dağıtım listesine yazılır (öbekler değişmez).'}
                      </div>
                      <button
                        className="yd birincil"
                        onClick={() => void onizle(bolme)}
                        disabled={bolme.calisiyor}
                      >
                        {bolme.calisiyor ? 'Bölünüyor…' : bolme.sonuc ? 'Yeniden böl' : 'Önizle'}
                      </button>
                      {bolme.sonuc ? (
                        <div className="ie-parcalar">
                          {bolme.sonuc.parcalar.map((p) =>
                            p.parca > 0 ? (
                              <div key={p.parca} className="ie-parca">
                                <span className="renk" style={{ background: rgb(PALET[(p.parca - 1) % PALET.length]) }} />
                                <input
                                  className="yon-alan"
                                  value={bolme.adlar[p.parca - 1] ?? p.ad}
                                  onChange={(o) => {
                                    const adlar = [...bolme.adlar];
                                    adlar[p.parca - 1] = o.target.value;
                                    setBolme({ ...bolme, adlar });
                                  }}
                                  aria-label={`${p.parca}. parçanın adı`}
                                />
                                <span className="sayi">{p.is} iş</span>
                                <span className="alt">
                                  {p.yaricap_km != null ? `yarıçap ${p.yaricap_km.toLocaleString('tr-TR')} km · ` : ''}
                                  {p.mahalleler.length} mahalle
                                </span>
                              </div>
                            ) : (
                              <div key="0" className="ie-parca konumsuz">
                                <span className="sayi">{p.is} iş konumsuz</span>
                                <span className="alt">parçaya girmedi</span>
                              </div>
                            ),
                          )}
                          <div className="ie-bol-dugmeler">
                            <button className="yd birincil" onClick={() => void bolmeUygula()} disabled={gonderiliyor}>
                              {bolme.birim === 'mahalle' ? 'Öbek olarak kaydet' : 'Bugünkü listeye yaz'}
                            </button>
                            <button className="yd" onClick={() => setBolme(null)}>
                              Vazgeç
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button className="bag" onClick={() => setBolme(null)}>
                          Vazgeç
                        </button>
                      )}
                    </div>
                  </Kart>
                ) : null}

                <Kart
                  baslik="Öbekler"
                  altYazi="Süzgece göre iş sayısı ve yayılım"
                  sikis
                  sag={
                    <button
                      className="yd ie-kucuk"
                      onClick={() => bolmeBaslat(null, suzulen)}
                      disabled={suzulen.length < 2}
                      title="Süzülen işlerin tamamını yakınlığa göre parçalara böl"
                    >
                      Süzüleni böl
                    </button>
                  }
                >
                  <div className="ie-obekler">
                    {obekKartlari.map((o) => {
                      const r = o.ad === OBEKSIZ ? GRI : obekRengi.get(o.ad) ?? GRI;
                      const adDegisiyor = adDegisen?.eski === o.ad;
                      return (
                        <div
                          key={o.ad}
                          className={`ie-obek${obekFiltre === o.ad ? ' secili' : ''}`}
                          style={{ borderLeftColor: rgb(r) }}
                        >
                          <div className="bas">
                            {adDegisiyor ? (
                              <input
                                className="yon-alan"
                                autoFocus
                                value={adDegisen!.yeni}
                                onChange={(e) => setAdDegisen({ eski: o.ad, yeni: e.target.value })}
                                onKeyDown={(e) => {
                                  if (e.key === 'Escape') setAdDegisen(null);
                                  if (e.key === 'Enter' && adDegisen!.yeni.trim()) {
                                    void calistir(
                                      () => obekIslemi({ islem: 'ad', ad: o.ad, yeni_ad: adDegisen!.yeni.trim() }),
                                      'Öbek adı değişti.',
                                    ).then(() => setAdDegisen(null));
                                  }
                                }}
                              />
                            ) : (
                              <button
                                className="ad"
                                onClick={() => setObekFiltre(obekFiltre === o.ad ? '' : o.ad)}
                                title="Yalnız bu öbeği göster"
                              >
                                {o.ad}
                              </button>
                            )}
                            <span className="sayi">{o.isler.length}</span>
                          </div>
                          <div className="cubuk">
                            <span style={{ width: `${(o.isler.length / enCok) * 100}%`, background: rgb(r) }} />
                          </div>
                          <div className="alt">
                            {o.mahalle} mahalle · {o.ilceler.slice(0, 3).join(', ')}
                            {o.ilceler.length > 3 ? '…' : ''}
                            {o.yaricap != null ? ` · yarıçap ${o.yaricap.toFixed(1).replace('.', ',')} km` : ''}
                          </div>
                          <div className="eylem">
                            <button className="bag" onClick={() => bolmeBaslat(o.ad, o.isler)} disabled={o.isler.length < 2}>
                              Böl
                            </button>
                            {o.ad !== OBEKSIZ ? (
                              <>
                                <button className="bag" onClick={() => setAdDegisen({ eski: o.ad, yeni: o.ad })}>
                                  Ad değiştir
                                </button>
                                <button
                                  className="bag tehlike"
                                  onClick={() => {
                                    if (window.confirm(`"${o.ad}" öbeği silinsin mi? Mahalleleri öbeksiz kalır.`)) {
                                      void calistir(() => obekIslemi({ islem: 'sil', ad: o.ad }), 'Öbek silindi.');
                                    }
                                  }}
                                >
                                  Sil
                                </button>
                              </>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Kart>

                {parcalar.length ? (
                  <Kart
                    baslik="Bugünkü parçalar"
                    altYazi="Binaya göre bölmeden — Excel'de Parça sütunu"
                    sikis
                    sag={
                      <button
                        className="yd ie-kucuk"
                        onClick={() => void calistir(() => parcaKaydet({ temizle: true }), 'Parçalar temizlendi.')}
                      >
                        Temizle
                      </button>
                    }
                  >
                    <div className="ie-parca-ozet">
                      {parcalar.map(([ad, n]) => (
                        <span key={ad}>
                          {ad} <b>{n}</b>
                        </span>
                      ))}
                    </div>
                  </Kart>
                ) : null}
              </div>
            </div>

            {/* ---------------- Kontrol ---------------- */}
            <Kart
              baslik={`Kontrol edilecek adresler (${kontrol.length})`}
              altYazi="Mahalle adresten kesin çıkmadı ya da OneMap'teki binanın mahallesi farklı"
              sikis
              sag={
                <button className="yd ie-kucuk" onClick={() => setKontrolAcik((a) => !a)}>
                  {kontrolAcik ? 'Gizle' : 'Göster'}
                </button>
              }
            >
              {kontrolAcik ? (
                <div className="yon-tablo-sarmal">
                  <table className="yon-tablo ie-kontrol">
                    <thead>
                      <tr>
                        <th>İlçe</th>
                        <th>Bulunan mahalle</th>
                        <th>Not</th>
                        <th>Adres</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kontrol.map((i) => (
                        <tr key={i.id}>
                          <td>{i.ilce}</td>
                          <td>
                            <b>{i.mahalle || '—'}</b>
                          </td>
                          <td>{i.not || i.mahalle_kaynak}</td>
                          <td className="adres">{i.adres}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </Kart>
          </>
        ) : null}
      </Icerik>
    </>
  );
}
