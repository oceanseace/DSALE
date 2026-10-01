/**
 * Mahalle seçici (§6.4, F2): Bursa ve Yalova'nın 23 ilçesinin TAMAMI, rapordan
 * bağımsız (`GET /api/mahalleler`). Türkçe harf duyarsız arama ("gursu" →
 * Gürsu, "gocmen" → Göçmen); ilçeye göre gruplu; her ilçenin başında
 * "İlçenin tamamı"; her satırda bugünkü iş sayısı ve ŞU ANKİ öbeği.
 *
 * İki kip:
 *   · çoklu (öbek çekmecesi): seç → alt çubukta tek cümlelik taşıma onayı
 *     ("1 mahalle Yıldırım öbeğinden taşınacak.") → [2 mahalleyi ekle ve taşı]
 *   · tek (iş çekmecesi "Mahalleyi seç", Kontrol): dokununca seçilir.
 *
 * Listede yoksa: "'Göçmen' listede yok. [Yeni mahalle olarak ekle]" → ilçe →
 * benzer ad varsa önce sorulur ("Aynı yer mi?"; Evet → yazım farkı kaydı).
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { esadEkle, hataMetni, IsHatasi, ilceler as ilceleriGetir, mahalleAra, mahalleEkle } from '../../is/api';
import type { IlceKaydi, MahalleKaydi, Obek } from '../../is/tipler';
import { katla } from '../../ortak/ara';
import { useBildirim } from '../../ortak/Bildirim';
import { ayrilma, tamlayan } from '../isler/dil';

export interface MahalleSecimi {
  mahalleler: MahalleKaydi[];
  ilceler: IlceKaydi[];
  tasinacak: number;
}

type Grup = { ilce: IlceKaydi; mahalleler: MahalleKaydi[] | null };

function ilceAnahtari(i: { il: string; ilce: string }) {
  return `${i.il}/${i.ilce}`;
}

export function MahalleSecici({
  tek = false,
  tekSec,
  baslangicSorgu = '',
  ilce,
  hedefObek,
  ekle,
  vazgec,
}: {
  tek?: boolean;
  tekSec?: (m: MahalleKaydi) => void;
  baslangicSorgu?: string;
  /** Bu ilçe açık başlar (iş çekmecesinde işin ilçesi). */
  ilce?: { il: string; ilce: string } | null;
  /** Çoklu kipte: mahallelerin ekleneceği öbek. */
  hedefObek?: Obek;
  ekle?: (s: MahalleSecimi) => Promise<void>;
  vazgec?: () => void;
}) {
  const bildirim = useBildirim();
  const [sorgu, setSorgu] = useState(baslangicSorgu);
  const [tumIlceler, setTumIlceler] = useState<IlceKaydi[] | null>(null);
  const [acikIlceler, setAcikIlceler] = useState<Set<string>>(() => new Set(ilce ? [ilceAnahtari(ilce)] : []));
  const [ilceMahalleleri, setIlceMahalleleri] = useState<Record<string, MahalleKaydi[]>>({});
  const [arama, setArama] = useState<{ sorgu: string; ilceler: IlceKaydi[]; mahalleler: MahalleKaydi[] } | null>(null);
  const [araniyor, setAraniyor] = useState(false);
  const [secMahalle, setSecMahalle] = useState<Map<number, MahalleKaydi>>(new Map());
  const [secIlce, setSecIlce] = useState<Map<string, IlceKaydi>>(new Map());
  const [yeni, setYeni] = useState<{ ad: string; ilce: string } | null>(null);
  const [benzer, setBenzer] = useState<{ ad: string; il: string; ilce: string; oneri: { id: number; ad: string } } | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const istekNo = useRef(0);

  const kendiRefleri = useMemo(() => new Set(hedefObek?.mahalleler.map((m) => m.ref) ?? []), [hedefObek]);

  useEffect(() => {
    ilceleriGetir()
      .then(setTumIlceler)
      .catch((e) => bildirim.goster(hataMetni(e), 'uyari'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* Açılan ilçenin bütün mahalleleri (bir kez). */
  useEffect(() => {
    if (!tumIlceler) return;
    acikIlceler.forEach((a) => {
      if (ilceMahalleleri[a]) return;
      const [il, ad] = a.split('/');
      mahalleAra({ il, ilce: ad, limit: 500 })
        .then((y) => setIlceMahalleleri((o) => ({ ...o, [a]: y.mahalleler })))
        .catch(() => setIlceMahalleleri((o) => ({ ...o, [a]: [] })));
    });
  }, [acikIlceler, tumIlceler, ilceMahalleleri]);

  /* Arama (yazmayı bitirince). */
  useEffect(() => {
    const s = sorgu.trim();
    if (!s) {
      setArama(null);
      return;
    }
    const no = ++istekNo.current;
    setAraniyor(true);
    const t = window.setTimeout(() => {
      mahalleAra({ q: s, limit: 200, il: ilce && tek ? ilce.il : undefined })
        .then((y) => {
          if (no === istekNo.current) setArama({ sorgu: s, ilceler: y.ilceler, mahalleler: y.mahalleler });
        })
        .catch(() => undefined)
        .finally(() => no === istekNo.current && setAraniyor(false));
    }, 220);
    return () => window.clearTimeout(t);
  }, [sorgu, ilce, tek]);

  const gruplar: Grup[] = useMemo(() => {
    if (arama) {
      const harita = new Map<string, Grup>();
      for (const i of arama.ilceler) harita.set(ilceAnahtari(i), { ilce: i, mahalleler: [] });
      for (const m of arama.mahalleler) {
        const a = ilceAnahtari(m);
        if (!harita.has(a)) {
          const i = tumIlceler?.find((x) => ilceAnahtari(x) === a) ?? {
            il: m.il, ilce: m.ilce, il_k: '', ilce_k: '', mahalle_sayisi: 0, tum_ilce_obek: null,
          };
          harita.set(a, { ilce: i, mahalleler: [] });
        }
        harita.get(a)!.mahalleler!.push(m);
      }
      return [...harita.values()];
    }
    return (tumIlceler ?? []).map((i) => ({
      ilce: i,
      mahalleler: acikIlceler.has(ilceAnahtari(i)) ? ilceMahalleleri[ilceAnahtari(i)] ?? null : null,
    }));
  }, [arama, tumIlceler, acikIlceler, ilceMahalleleri]);

  const tamEslesme = useMemo(() => {
    const k = katla(sorgu).trim();
    if (!k || !arama) return true;
    return arama.mahalleler.some((m) => katla(m.ad) === k) || arama.ilceler.some((i) => katla(i.ilce) === k);
  }, [arama, sorgu]);

  /* Yeni mahalle için ilçe tahmini: aramada ilçe adı geçiyorsa o, tek grup varsa o, işin ilçesi. */
  const tahminiIlce = (): string => {
    const k = katla(sorgu);
    const gecen = (tumIlceler ?? []).find((i) => k.split(/\s+/).includes(katla(i.ilce)));
    if (gecen) return ilceAnahtari(gecen);
    if (ilce) return ilceAnahtari(ilce);
    if (arama && arama.ilceler.length === 1) return ilceAnahtari(arama.ilceler[0]);
    return '';
  };

  const mahalleTikla = (m: MahalleKaydi) => {
    if (tek) {
      tekSec?.(m);
      return;
    }
    if (kendiRefleri.has(m.ref)) return;
    setSecMahalle((o) => {
      const y = new Map(o);
      if (y.has(m.id)) y.delete(m.id);
      else y.set(m.id, m);
      return y;
    });
  };

  const ilceTikla = (i: IlceKaydi) => {
    const a = ilceAnahtari(i);
    setSecIlce((o) => {
      const y = new Map(o);
      if (y.has(a)) y.delete(a);
      else y.set(a, i);
      return y;
    });
  };

  const eklendi = (m: MahalleKaydi) => {
    setYeni(null);
    setBenzer(null);
    setSorgu(m.ad);
    if (tek) {
      tekSec?.(m);
      return;
    }
    setSecMahalle((o) => new Map(o).set(m.id, m));
    bildirim.goster(`${m.ad} mahalle listesine eklendi.`, 'basari');
  };

  const yeniEkle = async (benzerineRagmen = false) => {
    if (!yeni) return;
    const [il, ilceAdi] = yeni.ilce.split('/');
    if (!il || !ilceAdi) {
      bildirim.goster('Önce ilçeyi seçin.', 'uyari');
      return;
    }
    setGonderiliyor(true);
    try {
      const y = await mahalleEkle({ il, ilce: ilceAdi, ad: yeni.ad.trim(), benzerine_ragmen: benzerineRagmen });
      eklendi(y.mahalle);
    } catch (e) {
      if (e instanceof IsHatasi && e.kod === 'benzer_var' && e.govde.oneriler?.length) {
        const o = e.govde.oneriler[0];
        setBenzer({ ad: yeni.ad.trim(), il, ilce: ilceAdi, oneri: { id: o.id, ad: o.ad } });
      } else if (e instanceof IsHatasi && e.kod === 'var' && e.govde.mahalle) {
        eklendi(e.govde.mahalle as unknown as MahalleKaydi);
      } else bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setGonderiliyor(false);
    }
  };

  const ayniYer = async () => {
    if (!benzer) return;
    setGonderiliyor(true);
    try {
      const y = await esadEkle({ il: benzer.il, ilce: benzer.ilce, esad: benzer.ad, mahalle_id: benzer.oneri.id });
      bildirim.goster(`“${benzer.ad}” yazımı artık ${benzer.oneri.ad} sayılacak.`, 'basari');
      eklendi(y.mahalle);
    } catch (e) {
      bildirim.goster(hataMetni(e), 'uyari');
    } finally {
      setGonderiliyor(false);
    }
  };

  /* Taşıma cümlesi: seçilenlerden başka öbekte olanlar. */
  const secMahalleler = [...secMahalle.values()];
  const secIlceler = [...secIlce.values()];
  const tasinanlar = [
    ...secMahalleler.filter((m) => m.obek && m.obek.id !== hedefObek?.id).map((m) => m.obek!.ad),
    ...secIlceler.filter((i) => i.tum_ilce_obek && i.tum_ilce_obek.id !== hedefObek?.id).map((i) => i.tum_ilce_obek!.ad),
  ];
  const kaynakObekler = [...new Set(tasinanlar)];
  const toplam = secMahalleler.length + secIlceler.length;
  const tasimaCumlesi = tasinanlar.length
    ? kaynakObekler.length === 1
      ? `${tasinanlar.length} mahalle ${ayrilma(kaynakObekler[0])} öbeğinden taşınacak.`
      : `${tasinanlar.length} mahalle başka öbeklerden (${kaynakObekler.join(', ')}) taşınacak.`
    : null;
  const birincilMetin =
    secIlceler.length && !secMahalleler.length && secIlceler.length === 1
      ? `${tamlayan(secIlceler[0].ilce)} tamamını ekle${tasinanlar.length ? ' ve taşı' : ''}`
      : `${toplam} mahalleyi ekle${tasinanlar.length ? ' ve taşı' : ''}`;

  const gonder = async () => {
    if (!ekle || !toplam) return;
    setGonderiliyor(true);
    try {
      await ekle({ mahalleler: secMahalleler, ilceler: secIlceler, tasinacak: tasinanlar.length });
    } finally {
      setGonderiliyor(false);
    }
  };

  return (
    <div className={`ms${tek ? ' tek' : ''}`}>
      <div className="ms-arama">
        <input
          className="o-girdi"
          type="search"
          value={sorgu}
          placeholder="Mahalle ya da ilçe yazın"
          aria-label="Mahalle ya da ilçe ara"
          autoFocus
          onChange={(o) => setSorgu(o.target.value)}
        />
        {araniyor ? <span className="ms-araniyor">Aranıyor…</span> : null}
      </div>

      <div className="ms-liste" role="list">
        {!tumIlceler && !arama ? <div className="o-iskelet"><span style={{ height: 44 }} /><span style={{ height: 44 }} /></div> : null}
        {gruplar.map((g) => {
          const a = ilceAnahtari(g.ilce);
          const acik = Boolean(arama) || acikIlceler.has(a);
          const tumuSecili = secIlce.has(a);
          const tumuBurada = g.ilce.tum_ilce_obek?.id === hedefObek?.id && Boolean(hedefObek);
          return (
            <section key={a} className="ms-grup" role="listitem">
              <button
                type="button"
                className="ms-grup-bas"
                aria-expanded={acik}
                onClick={() =>
                  !arama &&
                  setAcikIlceler((o) => {
                    const y = new Set(o);
                    if (y.has(a)) y.delete(a);
                    else y.add(a);
                    return y;
                  })
                }
              >
                <span className="ad">{g.ilce.ilce}</span>
                <span className="il">{g.ilce.il}</span>
                <span className="sayi">{g.ilce.mahalle_sayisi ? `${g.ilce.mahalle_sayisi} mahalle` : ''}</span>
                {!arama ? <span className={`ok${acik ? ' acik' : ''}`} aria-hidden="true">›</span> : null}
              </button>
              {acik ? (
                <div className="ms-grup-govde">
                  {!tek ? (
                    <label className={`ms-satir tumu${tumuSecili ? ' secili' : ''}`}>
                      <input type="checkbox" checked={tumuSecili || tumuBurada} disabled={tumuBurada} onChange={() => ilceTikla(g.ilce)} />
                      <span className="ad">İlçenin tamamı</span>
                      <span className="bilgi">
                        {tumuBurada
                          ? 'bu öbekte'
                          : g.ilce.tum_ilce_obek
                            ? `${g.ilce.tum_ilce_obek.ad} öbeğinde`
                            : 'sözlükte mahallesi olmasa da çalışır'}
                      </span>
                    </label>
                  ) : null}
                  {g.mahalleler === null ? <div className="o-iskelet"><span style={{ height: 44 }} /></div> : null}
                  {g.mahalleler?.map((m) => {
                    const burada = kendiRefleri.has(m.ref);
                    const secili = secMahalle.has(m.id);
                    return tek ? (
                      <button key={m.id} type="button" className="ms-satir" onClick={() => mahalleTikla(m)}>
                        <span className="ad">{m.ad}</span>
                        <span className="bilgi">
                          {m.acik ? `bugün ${m.acik} iş` : 'bugün iş yok'}
                          {m.obek ? ` · ${m.obek.ad} öbeğinde` : ' · öbeği yok'}
                        </span>
                      </button>
                    ) : (
                      <label key={m.id} className={`ms-satir${secili ? ' secili' : ''}${burada ? ' soluk' : ''}`}>
                        <input type="checkbox" checked={secili || burada} disabled={burada} onChange={() => mahalleTikla(m)} />
                        <span className="ad">{m.ad}</span>
                        <span className="bilgi">
                          {m.acik ? `bugün ${m.acik} iş` : 'bugün iş yok'}
                          {burada ? ' · bu öbekte' : m.obek ? ` · ${m.obek.ad} öbeğinde` : ''}
                        </span>
                      </label>
                    );
                  })}
                  {g.mahalleler && !g.mahalleler.length && !arama ? (
                    <p className="ms-bos">Bu ilçede sözlükte mahalle yok. “İlçenin tamamı”nı seçebilirsiniz.</p>
                  ) : null}
                </div>
              ) : null}
            </section>
          );
        })}

        {arama && !tamEslesme && !yeni && !benzer ? (
          <div className="ms-yok">
            <p>
              “{sorgu.trim()}” listede yok.
            </p>
            <button
              type="button"
              className="o-dugme kucuk"
              onClick={() => setYeni({ ad: sorgu.trim().replace(/\s+(mah(allesi)?\.?|mh\.?)$/i, ''), ilce: tahminiIlce() })}
            >
              Yeni mahalle olarak ekle
            </button>
          </div>
        ) : null}

        {yeni && !benzer ? (
          <div className="ms-yeni">
            <label className="o-alan">
              <span className="etiket">Mahalle adı</span>
              <input className="o-girdi" value={yeni.ad} onChange={(o) => setYeni({ ...yeni, ad: o.target.value })} />
            </label>
            <label className="o-alan">
              <span className="etiket">İlçe</span>
              <select className="o-girdi" value={yeni.ilce} onChange={(o) => setYeni({ ...yeni, ilce: o.target.value })}>
                <option value="">İlçe seçin…</option>
                {(tumIlceler ?? []).map((i) => (
                  <option key={ilceAnahtari(i)} value={ilceAnahtari(i)}>
                    {i.ilce} · {i.il}
                  </option>
                ))}
              </select>
            </label>
            <div className="ms-dugmeler">
              <button type="button" className="o-dugme kucuk metin" onClick={() => setYeni(null)} disabled={gonderiliyor}>
                Vazgeç
              </button>
              <button
                type="button"
                className="o-dugme kucuk"
                disabled={!yeni.ad.trim() || !yeni.ilce || gonderiliyor}
                onClick={() => void yeniEkle(false)}
              >
                Listeye ekle
              </button>
            </div>
          </div>
        ) : null}

        {benzer ? (
          <div className="ms-yeni">
            <p>
              Aynı ilçede “{benzer.oneri.ad}” var. Aynı yer mi?
            </p>
            <div className="ms-dugmeler">
              <button type="button" className="o-dugme kucuk" disabled={gonderiliyor} onClick={() => void ayniYer()}>
                Evet, aynı
              </button>
              <button type="button" className="o-dugme kucuk metin" disabled={gonderiliyor} onClick={() => void yeniEkle(true)}>
                Hayır, yeni mahalle
              </button>
            </div>
          </div>
        ) : null}
      </div>

      {!tek ? (
        <div className="ms-alt">
          <p className="ms-cumle" aria-live="polite">
            {toplam ? tasimaCumlesi ?? `${toplam} seçim ${hedefObek ? `${hedefObek.ad} öbeğine` : ''} eklenecek.` : 'Eklemek istediğiniz mahalleleri işaretleyin.'}
          </p>
          <div className="ms-dugmeler">
            {vazgec ? (
              <button type="button" className="o-dugme" onClick={vazgec} disabled={gonderiliyor}>
                Vazgeç
              </button>
            ) : null}
            <button type="button" className="o-dugme birincil" disabled={!toplam || gonderiliyor} onClick={() => void gonder()}>
              {gonderiliyor ? 'Bekleyin…' : birincilMetin}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
