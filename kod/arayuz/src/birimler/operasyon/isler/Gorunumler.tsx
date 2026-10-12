/**
 * Görünümler — task başlığına göre kaydedilmiş süzgeçler ("Emre": Arıza + Nakil…).
 *
 *   · `useGorunumler()`  liste + seçili görünüm (TASKS ↔ MAP ortak süzgeçte, kişi başına sunucuda) + `uyar(is)`.
 *   · `OzelFiltreler`    TASKS araç çubuğu: seç = uygula, Task adı süzgecini görünüm olarak kaydet, düzenle.
 *   · `GorunumSecici`    "Tümü" + kayıtlı adlar (MAP).
 *   · `GorunumPaneli`    yönetim (yalnız is.ata): ad · task başlıkları · kişi.
 *
 * Bütün işler her zaman çekilir; süzme istemcide (task_adi ∈ görünümün başlıkları).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { IsSatir } from '../../../cekirdek/is/tipler';
import {
  gorunumlerGetir,
  gorunumlerYaz,
  hataMetni,
  type Gorunum,
  type GorunumlerYanit,
  type GorunumYaz,
} from '../../../cekirdek/is/api';
import { Panel } from '../../../cekirdek/ortak/Panel';
import { useBildirim } from '../../../cekirdek/ortak/Bildirim';
import { eslesir } from '../../../cekirdek/ortak/ara';
import { useDisariKapat, useEkranaSigdir } from './acilir';
import { suzgecYaz, useTercih } from './tercihDeposu';

/** Karşılaştırma biçimi: boşluk kırpılmış, Türkçe küçük harf. */
export const baslikAnahtari = (m: string | null | undefined) => String(m ?? '').trim().toLocaleLowerCase('tr-TR');

/* Modül önbelleği: liste ve harita aynı yanıtı paylaşır. */
let ONBELLEK: GorunumlerYanit | null = null;
let ISTEK: Promise<GorunumlerYanit> | null = null;
const dinleyiciler = new Set<(y: GorunumlerYanit) => void>();
function yay(y: GorunumlerYanit) {
  ONBELLEK = y;
  dinleyiciler.forEach((f) => f(y));
}

export function useGorunumler() {
  const [veri, setVeri] = useState<GorunumlerYanit | null>(ONBELLEK);
  const [hata, setHata] = useState<string | null>(null);
  /* Seçili Özel filtre TASKS ↔ MAP ortak süzgecin parçası (kişi başına sunucuda, tercihDeposu.ts). */
  const seciliId = useTercih().suzgec.gorunum_id;

  const tazele = useCallback(async () => {
    try {
      ISTEK ??= gorunumlerGetir();
      yay(await ISTEK);
      setHata(null);
    } catch (e) {
      setHata(hataMetni(e));
    } finally {
      ISTEK = null;
    }
  }, []);

  useEffect(() => {
    dinleyiciler.add(setVeri);
    void tazele();
    return () => {
      dinleyiciler.delete(setVeri);
    };
  }, [tazele]);

  const sec = useCallback((id: number | null) => suzgecYaz((o) => ({ ...o, gorunum_id: id })), []);

  const secili: Gorunum | null = useMemo(
    () => (seciliId === null ? null : veri?.gorunumler.find((g) => g.id === seciliId) ?? null),
    [veri, seciliId],
  );
  const kume = useMemo(() => (secili ? new Set(secili.task_adlari.map(baslikAnahtari)) : null), [secili]);
  const uyar = useCallback((s: Pick<IsSatir, 'task_adi'>) => !kume || kume.has(baslikAnahtari(s.task_adi)), [kume]);

  const kaydet = useCallback(async (liste: GorunumYaz[]) => {
    const y = await gorunumlerYaz(liste);
    yay(y);
    return y;
  }, []);

  return { veri, hata, secili, sec, uyar, tazele, kaydet };
}

export type GorunumDepo = ReturnType<typeof useGorunumler>;

/* ================================================================== TASKS: Özel filtreler */

export function OzelFiltreler({
  g,
  taskAdlari,
  kaydedilebilir,
  kaydedildi,
  duzenle,
}: {
  g: GorunumDepo;
  /** Task adı sütununun ▾ süzgecinde seçili değerler (süzgeç yoksa null). */
  taskAdlari: string[] | null;
  /** is.ata: kaydetme ve düzenleme. */
  kaydedilebilir: boolean;
  /** Kayıttan sonra: Task adı süzgeci kalkar (aynı işi artık görünüm yapar). */
  kaydedildi: () => void;
  duzenle: () => void;
}) {
  const bildirim = useBildirim();
  const [acik, setAcik] = useState(false);
  const [ad, setAd] = useState('');
  const [gidiyor, setGidiyor] = useState(false);
  const kok = useRef<HTMLDivElement>(null);
  const kapat = useCallback(() => setAcik(false), []);
  useDisariKapat(kok, kapat, acik);
  const acilirRef = useRef<HTMLDivElement>(null);
  useEkranaSigdir(acilirRef, acik);
  const liste = g.veri?.gorunumler ?? [];

  const sec = (id: number | null) => {
    g.sec(id);
    setAcik(false);
  };
  const kaydet = async () => {
    if (!taskAdlari?.length || !ad.trim()) return;
    setGidiyor(true);
    try {
      const y = await g.kaydet([
        ...liste.map((x) => ({ id: x.id, ad: x.ad, task_adlari: x.task_adlari, kisi_id: x.kisi_id })),
        { ad: ad.trim(), task_adlari: taskAdlari, kisi_id: null },
      ]);
      const yeni = y.gorunumler.find((x) => !liste.some((e) => e.id === x.id)) ?? y.gorunumler.find((x) => x.ad === ad.trim());
      if (yeni) g.sec(yeni.id);
      kaydedildi();
      setAd('');
      setAcik(false);
      bildirim.goster(`“${ad.trim()}” kaydedildi.`, 'basari');
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setGidiyor(false);
    }
  };

  return (
    <div className="xg-bolunmus" ref={kok}>
      <button type="button" className={`xg-arac-dugme${g.secili ? ' etkin' : ''}`} aria-expanded={acik} onClick={() => setAcik((a) => !a)}>
        {g.secili ? `Özel filtre: ${g.secili.ad}` : 'Özel filtreler'} ▾
      </button>
      {acik ? (
        <div ref={acilirRef} className="xg-acilir xg-ozel" role="dialog" aria-label="Özel filtreler">
          <button type="button" className={`xg-menu-satir${!g.secili ? ' secili' : ''}`} onClick={() => sec(null)}>
            Tümü (özel filtre yok)
          </button>
          {liste.map((x) => (
            <button key={x.id} type="button" className={`xg-menu-satir${g.secili?.id === x.id ? ' secili' : ''}`} onClick={() => sec(x.id)}>
              <span className="xg-deger-ad">{x.ad}</span>
              <span className="xg-sayi">
                {x.kisi ? `${x.kisi.ad} · ` : ''}
                {x.task_adlari.length} task
              </span>
            </button>
          ))}
          {!liste.length ? <div className="xg-not">Henüz kayıtlı filtre yok.</div> : null}
          {kaydedilebilir ? (
            <>
              <hr />
              <div className="xg-menu-etiket">Şu anki Task adı süzgecini kaydet</div>
              {taskAdlari?.length ? (
                <div className="xg-ozel-kaydet">
                  <input
                    className="o-girdi kucuk"
                    value={ad}
                    maxLength={60}
                    placeholder={`Ad (${taskAdlari.length} task)`}
                    onChange={(o) => setAd(o.target.value)}
                    onKeyDown={(o) => o.key === 'Enter' && void kaydet()}
                  />
                  <button type="button" className="o-dugme kucuk vurgu" disabled={gidiyor || !ad.trim()} onClick={() => void kaydet()}>
                    {gidiyor ? 'Kaydediliyor…' : 'Kaydet'}
                  </button>
                </div>
              ) : (
                <div className="xg-not">Önce “Task adı” başlığındaki ▾ ile task seçin.</div>
              )}
              <button
                type="button"
                className="xg-menu-satir"
                onClick={() => {
                  setAcik(false);
                  duzenle();
                }}
              >
                Filtreleri düzenle…
              </button>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/* ================================================================== seçici (MAP) */

export function GorunumSecici({ g }: { g: GorunumDepo }) {
  const liste = g.veri?.gorunumler ?? [];
  if (!liste.length) return null;
  return (
    <label className="gr-secici">
      <span>Görünüm</span>
      <select
        className="o-girdi"
        value={g.secili ? String(g.secili.id) : ''}
        onChange={(o) => g.sec(o.target.value ? Number(o.target.value) : null)}
        aria-label="Görünüm seçin"
      >
        <option value="">Tümü</option>
        {liste.map((x) => (
          <option key={x.id} value={x.id}>
            {x.ad}
            {x.kisi ? ` · ${x.kisi.ad}` : ''}
          </option>
        ))}
      </select>
    </label>
  );
}

/* ================================================================== yönetim */

interface Taslak {
  anahtar: string;
  id?: number;
  ad: string;
  task_adlari: string[];
  kisi_id: number | null;
}

let SAYAC = 0;
const taslakla = (g: Gorunum): Taslak => ({ anahtar: `g${g.id}`, id: g.id, ad: g.ad, task_adlari: [...g.task_adlari], kisi_id: g.kisi_id });

export function GorunumPaneli({ acik, kapat, g }: { acik: boolean; kapat: () => void; g: GorunumDepo }) {
  const bildirim = useBildirim();
  const [taslaklar, setTaslaklar] = useState<Taslak[]>([]);
  const [acikAnahtar, setAcikAnahtar] = useState<string | null>(null);
  const [kaydediliyor, setKaydediliyor] = useState(false);

  /* Panel her açılışta sunucudaki listeden başlar. */
  useEffect(() => {
    if (!acik) return;
    const l = (g.veri?.gorunumler ?? []).map(taslakla);
    setTaslaklar(l);
    setAcikAnahtar(l.length ? null : 'yeni');
    void g.tazele();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acik]);

  const degistir = (anahtar: string, d: Partial<Taslak>) =>
    setTaslaklar((l) => l.map((t) => (t.anahtar === anahtar ? { ...t, ...d } : t)));

  const ekle = () => {
    const t: Taslak = { anahtar: `y${++SAYAC}`, ad: '', task_adlari: [], kisi_id: null };
    setTaslaklar((l) => [...l, t]);
    setAcikAnahtar(t.anahtar);
  };

  const kaydet = async () => {
    const bos = taslaklar.find((t) => !t.ad.trim());
    if (bos) {
      setAcikAnahtar(bos.anahtar);
      bildirim.goster('Her görünüme bir ad verin.', 'uyari');
      return;
    }
    setKaydediliyor(true);
    try {
      const y = await g.kaydet(
        taslaklar.map((t) => ({ ...(t.id ? { id: t.id } : null), ad: t.ad.trim(), task_adlari: t.task_adlari, kisi_id: t.kisi_id })),
      );
      setTaslaklar(y.gorunumler.map(taslakla));
      bildirim.goster('Görünümler kaydedildi.', 'basari');
      kapat();
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setKaydediliyor(false);
    }
  };

  const basliklar = g.veri?.basliklar ?? [];
  const kisiler = g.veri?.kisiler ?? [];

  return (
    <Panel
      acik={acik}
      kapat={kapat}
      baslik="Görünümler"
      kilitli={kaydediliyor}
      alt={
        <div className="gr-alt">
          <button type="button" className="o-dugme metin" onClick={ekle} disabled={kaydediliyor}>
            + Yeni görünüm
          </button>
          <button type="button" className="o-dugme vurgu" onClick={() => void kaydet()} disabled={kaydediliyor}>
            {kaydediliyor ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      }
    >
      {g.hata && !g.veri ? <p className="ip-uyari amber">{g.hata}</p> : null}
      {!taslaklar.length ? <p className="ip-sessiz">Henüz görünüm yok. “+ Yeni görünüm” ile başlayın.</p> : null}
      <div className="gr-liste">
        {taslaklar.map((t) => (
          <GorunumKarti
            key={t.anahtar}
            t={t}
            acik={acikAnahtar === t.anahtar}
            ac={() => setAcikAnahtar((a) => (a === t.anahtar ? null : t.anahtar))}
            degistir={(d) => degistir(t.anahtar, d)}
            sil={() => setTaslaklar((l) => l.filter((x) => x.anahtar !== t.anahtar))}
            basliklar={basliklar}
            kisiler={kisiler}
          />
        ))}
      </div>
    </Panel>
  );
}

function GorunumKarti({
  t,
  acik,
  ac,
  degistir,
  sil,
  basliklar,
  kisiler,
}: {
  t: Taslak;
  acik: boolean;
  ac: () => void;
  degistir: (d: Partial<Taslak>) => void;
  sil: () => void;
  basliklar: GorunumlerYanit['basliklar'];
  kisiler: GorunumlerYanit['kisiler'];
}) {
  const [sorgu, setSorgu] = useState('');
  const secili = useMemo(() => new Set(t.task_adlari.map(baslikAnahtari)), [t.task_adlari]);
  /* Seçili olup açık işlerde artık olmayan başlıklar da listede kalsın. */
  const tum = useMemo(() => {
    const l = [...basliklar];
    const var_ = new Set(l.map((b) => baslikAnahtari(b.ad)));
    t.task_adlari.forEach((a) => {
      if (!var_.has(baslikAnahtari(a))) l.push({ ad: a, adet: 0 });
    });
    return l;
  }, [basliklar, t.task_adlari]);
  const gorunen = tum.filter((b) => eslesir(b.ad, sorgu));
  const toplam = tum.filter((b) => secili.has(baslikAnahtari(b.ad))).reduce((s, b) => s + b.adet, 0);

  const ayarla = (ad: string, ekle: boolean) => {
    const k = baslikAnahtari(ad);
    const kalan = t.task_adlari.filter((x) => baslikAnahtari(x) !== k);
    degistir({ task_adlari: ekle ? [...kalan, ad] : kalan });
  };
  const hepsi = () => {
    const l = [...t.task_adlari];
    const k = new Set(l.map(baslikAnahtari));
    gorunen.forEach((b) => !k.has(baslikAnahtari(b.ad)) && l.push(b.ad));
    degistir({ task_adlari: l });
  };
  const temizle = () => {
    const g = new Set(gorunen.map((b) => baslikAnahtari(b.ad)));
    degistir({ task_adlari: t.task_adlari.filter((x) => !g.has(baslikAnahtari(x))) });
  };

  const ofis = kisiler.filter((k) => k.tur === 'ofis');
  const ekip = kisiler.filter((k) => k.tur === 'ekip');

  return (
    <article className={`gr-kart${acik ? ' acik' : ''}`}>
      <button type="button" className="gr-kart-bas" onClick={ac} aria-expanded={acik}>
        <span className="gr-ad">{t.ad.trim() || 'Adsız görünüm'}</span>
        <span className="gr-ozet">
          {t.task_adlari.length} başlık · {toplam.toLocaleString('tr-TR')} iş
        </span>
      </button>
      {acik ? (
        <div className="gr-govde">
          <label className="gr-alan">
            <span>Ad</span>
            <input className="o-girdi" value={t.ad} maxLength={60} placeholder="ör. Emre" onChange={(o) => degistir({ ad: o.target.value })} autoFocus={!t.ad} />
          </label>
          <label className="gr-alan">
            <span>Kişi (isteğe bağlı)</span>
            <select
              className="o-girdi"
              value={t.kisi_id ?? ''}
              onChange={(o) => degistir({ kisi_id: o.target.value ? Number(o.target.value) : null })}
            >
              <option value="">— Kişi yok —</option>
              {ofis.length ? (
                <optgroup label="Ofis">
                  {ofis.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.ad}
                    </option>
                  ))}
                </optgroup>
              ) : null}
              {ekip.length ? (
                <optgroup label="BOSS ekipleri">
                  {ekip.map((k) => (
                    <option key={k.id} value={k.id}>
                      {k.ad}
                    </option>
                  ))}
                </optgroup>
              ) : null}
            </select>
          </label>
          <div className="gr-alan">
            <span>Task başlıkları</span>
            <div className="gr-arac">
              <input type="search" className="o-girdi" value={sorgu} placeholder="Başlık ara…" aria-label="Başlık ara" onChange={(o) => setSorgu(o.target.value)} />
              <button type="button" className="o-dugme kucuk metin" onClick={hepsi}>
                Hepsini seç
              </button>
              <button type="button" className="o-dugme kucuk metin" onClick={temizle}>
                Temizle
              </button>
            </div>
            <div className="gr-basliklar" role="group" aria-label="Task başlıkları">
              {gorunen.length ? (
                gorunen.map((b) => {
                  const s = secili.has(baslikAnahtari(b.ad));
                  return (
                    <label key={b.ad} className={`gr-baslik${s ? ' secili' : ''}`}>
                      <input type="checkbox" checked={s} onChange={(o) => ayarla(b.ad, o.target.checked)} />
                      <span className="gr-baslik-ad">{b.ad}</span>
                      <span className="gr-adet">{b.adet.toLocaleString('tr-TR')}</span>
                    </label>
                  );
                })
              ) : (
                <p className="ip-sessiz">{basliklar.length ? 'Bu aramayla başlık yok.' : 'Açık işlerde başlık yok.'}</p>
              )}
            </div>
          </div>
          <div className="ip-satir-eylemler sag">
            <button type="button" className="o-dugme kucuk metin gr-sil" onClick={sil}>
              Görünümü sil
            </button>
          </div>
        </div>
      ) : null}
    </article>
  );
}
